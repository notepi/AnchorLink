import { readFile, writeFile } from 'fs/promises';
import { join } from 'path';
import { NextRequest, NextResponse } from 'next/server';
import YAML from 'yaml';
import type { AnchorConfig, Membership, PoolConfig, Universe } from '@/types';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const PROJECT_ROOT = join(process.cwd(), '..');
const CONFIG_PATH = join(PROJECT_ROOT, 'config', 'pools.yaml');

type ConfigPatch =
  | { action: 'updateMembership'; index: number; membership: Membership }
  | { action: 'addMembership'; membership: Membership }
  | { action: 'deleteMembership'; index: number }
  | { action: 'updateUniverse'; index: number; universe: Universe }
  | { action: 'updateAnchor'; anchor: AnchorConfig };

const MEMBERSHIP_KEYS: Array<keyof Membership> = [
  'universe_id',
  'symbol',
  'role',
  'relevance',
  'weight',
  'enabled',
  'include_in_state',
  'include_in_benchmark',
  'include_in_ranking',
  'include_in_report',
  'include_in_rotation',
  'reason',
  'added_at',
  'reviewed_at',
];

const UNIVERSE_KEYS: Array<keyof Universe> = [
  'universe_id',
  'display_name',
  'purpose',
  'can_be_benchmark',
  'min_size',
  'description',
];

const ANCHOR_KEYS: Array<keyof AnchorConfig> = [
  'symbol',
  'name',
  'reason',
  'added_date',
];

async function readConfigFile(): Promise<{ content: string; config: PoolConfig }> {
  const content = await readFile(CONFIG_PATH, 'utf-8');
  return { content, config: YAML.parse(content) as PoolConfig };
}

function normalizeMembership(membership: Membership): Membership {
  return {
    universe_id: membership.universe_id.trim(),
    symbol: membership.symbol.trim(),
    role: membership.role.trim(),
    relevance: Number(membership.relevance),
    weight: Number(membership.weight),
    enabled: Boolean(membership.enabled),
    include_in_state: membership.include_in_state ?? Boolean(membership.enabled),
    include_in_benchmark: Boolean(membership.include_in_benchmark),
    include_in_ranking: Boolean(membership.include_in_ranking),
    include_in_report: Boolean(membership.include_in_report),
    include_in_rotation: membership.include_in_rotation ?? (membership.include_in_state ?? Boolean(membership.enabled)),
    reason: membership.reason.trim(),
    added_at: membership.added_at.trim(),
    reviewed_at: membership.reviewed_at.trim(),
  };
}

function validateMembership(config: PoolConfig, membership: Membership, currentIndex?: number): string[] {
  const errors: string[] = [];

  if (!membership.universe_id) errors.push('universe_id is required');
  if (!membership.symbol) errors.push('symbol is required');
  if (!membership.role) errors.push('role is required');
  if (!membership.reason) errors.push('reason is required');
  if (!membership.added_at) errors.push('added_at is required');
  if (!membership.reviewed_at) errors.push('reviewed_at is required');
  if (!Number.isFinite(membership.relevance) || membership.relevance < 0 || membership.relevance > 1) {
    errors.push('relevance must be between 0 and 1');
  }
  if (!Number.isFinite(membership.weight) || membership.weight < 0) {
    errors.push('weight must be a non-negative number');
  }
  if (!config.universes.some((universe) => universe.universe_id === membership.universe_id)) {
    errors.push(`universe_id not found: ${membership.universe_id}`);
  }
  if (!config.instruments.some((instrument) => instrument.symbol === membership.symbol)) {
    errors.push(`symbol not found in instruments: ${membership.symbol}`);
  }

  const duplicateIndex = config.memberships.findIndex((item, index) => (
    index !== currentIndex
    && item.universe_id === membership.universe_id
    && item.symbol === membership.symbol
  ));
  if (duplicateIndex >= 0) {
    errors.push(`duplicate membership: ${membership.universe_id}/${membership.symbol}`);
  }

  return errors;
}

function validateUniverse(config: PoolConfig, universe: Universe, currentIndex: number): string[] {
  const errors: string[] = [];

  if (!universe.universe_id.trim()) errors.push('universe_id is required');
  if (!universe.display_name.trim()) errors.push('display_name is required');
  if (!universe.purpose.trim()) errors.push('purpose is required');
  if (!Number.isInteger(Number(universe.min_size)) || Number(universe.min_size) < 0) {
    errors.push('min_size must be a non-negative integer');
  }

  const duplicateIndex = config.universes.findIndex((item, index) => (
    index !== currentIndex && item.universe_id === universe.universe_id
  ));
  if (duplicateIndex >= 0) {
    errors.push(`duplicate universe_id: ${universe.universe_id}`);
  }

  return errors;
}

function validateAnchor(anchor: AnchorConfig): string[] {
  const errors: string[] = [];
  if (!anchor.symbol.trim()) errors.push('anchor.symbol is required');
  if (!anchor.name.trim()) errors.push('anchor.name is required');
  if (!anchor.reason.trim()) errors.push('anchor.reason is required');
  if (!anchor.added_date.trim()) errors.push('anchor.added_date is required');
  return errors;
}

async function updateDocument(patch: ConfigPatch): Promise<PoolConfig> {
  const { content, config } = await readConfigFile();
  const doc = YAML.parseDocument(content, { keepSourceTokens: true });

  if (doc.errors.length > 0) {
    throw new Error(doc.errors.map((error) => error.message).join('; '));
  }

  if (patch.action === 'updateMembership') {
    if (!Number.isInteger(patch.index) || patch.index < 0 || patch.index >= config.memberships.length) {
      throw new Error('membership index is out of range');
    }
    const membership = normalizeMembership(patch.membership);
    const errors = validateMembership(config, membership, patch.index);
    if (errors.length > 0) throw new Error(errors.join('; '));

    for (const key of MEMBERSHIP_KEYS) {
      doc.setIn(['memberships', patch.index, key], membership[key]);
    }
  }

  if (patch.action === 'addMembership') {
    const membership = normalizeMembership(patch.membership);
    const errors = validateMembership(config, membership);
    if (errors.length > 0) throw new Error(errors.join('; '));

    const memberships = doc.get('memberships', true);
    if (!YAML.isSeq(memberships)) throw new Error('memberships must be a YAML sequence');
    memberships.add(membership);
  }

  if (patch.action === 'deleteMembership') {
    if (!Number.isInteger(patch.index) || patch.index < 0 || patch.index >= config.memberships.length) {
      throw new Error('membership index is out of range');
    }
    const memberships = doc.get('memberships', true);
    if (!YAML.isSeq(memberships)) throw new Error('memberships must be a YAML sequence');
    memberships.items.splice(patch.index, 1);
  }

  if (patch.action === 'updateUniverse') {
    if (!Number.isInteger(patch.index) || patch.index < 0 || patch.index >= config.universes.length) {
      throw new Error('universe index is out of range');
    }
    const universe: Universe = {
      universe_id: patch.universe.universe_id.trim(),
      display_name: patch.universe.display_name.trim(),
      purpose: patch.universe.purpose.trim(),
      can_be_benchmark: Boolean(patch.universe.can_be_benchmark),
      min_size: Number(patch.universe.min_size),
      description: patch.universe.description?.trim() ?? '',
    };
    const errors = validateUniverse(config, universe, patch.index);
    if (errors.length > 0) throw new Error(errors.join('; '));

    for (const key of UNIVERSE_KEYS) {
      doc.setIn(['universes', patch.index, key], universe[key]);
    }
  }

  if (patch.action === 'updateAnchor') {
    const anchor: AnchorConfig = {
      symbol: patch.anchor.symbol.trim(),
      name: patch.anchor.name.trim(),
      reason: patch.anchor.reason.trim(),
      added_date: patch.anchor.added_date.trim(),
    };
    const errors = validateAnchor(anchor);
    if (errors.length > 0) throw new Error(errors.join('; '));

    for (const key of ANCHOR_KEYS) {
      doc.setIn(['anchor', key], anchor[key]);
    }
  }

  const nextContent = doc.toString({ lineWidth: 0 });
  YAML.parse(nextContent);
  await writeFile(CONFIG_PATH, nextContent, 'utf-8');
  return YAML.parse(nextContent) as PoolConfig;
}

export async function GET() {
  try {
    const { config } = await readConfigFile();
    return NextResponse.json(config);
  } catch (error) {
    console.error('Failed to fetch config:', error);
    return NextResponse.json({ error: 'Failed to fetch config' }, { status: 500 });
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const patch = await request.json() as ConfigPatch;
    const config = await updateDocument(patch);
    return NextResponse.json({ config });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to update config';
    console.error('Failed to update config:', error);
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
