'use client';

import { useMemo, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Plus,
  RefreshCcw,
  Save,
  Search,
  SlidersHorizontal,
  Trash2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { Membership, PoolConfig, PoolType, Universe } from '@/types';

const POOL_ORDER: PoolType[] = [
  'direct_peers',
  'industry_chain',
  'theme_pool',
  'trading_watchlist',
];

const POOL_NAMES: Record<PoolType, string> = {
  direct_peers: '增材制造本业确认池',
  industry_chain: '商业航天硬科技主池',
  theme_pool: '商业航天主题温度计',
  trading_watchlist: '交易联动与风险映射池',
};

type SaveState =
  | { kind: 'idle'; message: string }
  | { kind: 'saving'; message: string }
  | { kind: 'saved'; message: string }
  | { kind: 'error'; message: string };

type ConfigPatch =
  | { action: 'updateMembership'; index: number; membership: Membership }
  | { action: 'addMembership'; membership: Membership }
  | { action: 'deleteMembership'; index: number }
  | { action: 'updateUniverse'; index: number; universe: Universe };

interface PoolsConfigWorkbenchProps {
  initialConfig: PoolConfig;
}

interface IndexedMembership {
  membership: Membership;
  index: number;
  name: string;
}

function todayText() {
  return new Date().toISOString().slice(0, 10);
}

function getStateScope(member: Membership) {
  return member.include_in_state ?? member.enabled;
}

function getRotationScope(member: Membership) {
  return member.include_in_rotation ?? getStateScope(member);
}

function getMembershipScopes(member: Membership): Array<[string, boolean]> {
  return [
    ['E', member.enabled],
    ['S', getStateScope(member)],
    ['B', member.include_in_benchmark],
    ['R', member.include_in_ranking],
    ['P', member.include_in_report],
    ['T', getRotationScope(member)],
  ];
}

function normalizeMembership(member: Membership): Membership {
  const enabled = Boolean(member.enabled);
  const includeInState = member.include_in_state ?? enabled;

  return {
    universe_id: member.universe_id,
    symbol: member.symbol,
    role: member.role,
    relevance: Number(member.relevance),
    weight: Number(member.weight),
    enabled,
    include_in_state: includeInState,
    include_in_benchmark: Boolean(member.include_in_benchmark),
    include_in_ranking: Boolean(member.include_in_ranking),
    include_in_report: Boolean(member.include_in_report),
    include_in_rotation: member.include_in_rotation ?? includeInState,
    reason: member.reason,
    added_at: member.added_at,
    reviewed_at: member.reviewed_at,
  };
}

function createDraftMembership(config: PoolConfig, poolId: PoolType): Membership {
  const existingSymbols = new Set(
    config.memberships
      .filter((membership) => membership.universe_id === poolId)
      .map((membership) => membership.symbol)
  );
  const instrument = config.instruments.find((item) => (
    item.symbol !== config.anchor.symbol && !existingSymbols.has(item.symbol)
  )) ?? config.instruments[0];

  return {
    universe_id: poolId,
    symbol: instrument?.symbol ?? '',
    role: poolId === 'direct_peers'
      ? 'direct_comparable'
      : poolId === 'industry_chain'
        ? 'downstream_demand'
        : poolId === 'theme_pool'
          ? 'theme_heat_proxy'
          : 'trading_signal',
    relevance: 0.5,
    weight: 1,
    enabled: true,
    include_in_state: true,
    include_in_benchmark: poolId === 'direct_peers' || poolId === 'industry_chain',
    include_in_ranking: true,
    include_in_report: true,
    include_in_rotation: true,
    reason: '',
    added_at: todayText(),
    reviewed_at: todayText(),
  };
}

function sortMemberships(items: IndexedMembership[]) {
  return [...items].sort((a, b) => {
    const poolA = POOL_ORDER.indexOf(a.membership.universe_id as PoolType);
    const poolB = POOL_ORDER.indexOf(b.membership.universe_id as PoolType);
    if (poolA !== poolB) return poolA - poolB;
    return b.membership.relevance - a.membership.relevance;
  });
}

async function patchConfig(patch: ConfigPatch): Promise<PoolConfig> {
  const response = await fetch('/api/config', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  const payload = await response.json() as { config?: PoolConfig; error?: string };
  if (!response.ok || !payload.config) {
    throw new Error(payload.error ?? '配置保存失败');
  }
  return payload.config;
}

async function fetchConfig(): Promise<PoolConfig> {
  const response = await fetch('/api/config', { cache: 'no-store' });
  if (!response.ok) throw new Error('配置刷新失败');
  return response.json() as Promise<PoolConfig>;
}

function ScopeToggle({
  checked,
  label,
  onChange,
}: {
  checked: boolean;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-center justify-between gap-2 rounded-sm border border-anchor-border bg-anchor-bg px-2 py-1">
      <span className="text-xs text-anchor-textSecondary">{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-3.5 w-3.5 accent-blue-500"
      />
    </label>
  );
}

function TextInput({
  label,
  value,
  onChange,
  type = 'text',
  step,
  min,
  max,
}: {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  type?: string;
  step?: string;
  min?: string;
  max?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-anchor-textMuted">{label}</span>
      <input
        type={type}
        value={value}
        step={step}
        min={min}
        max={max}
        onChange={(event) => onChange(event.target.value)}
        className="h-8 w-full rounded-sm border border-anchor-border bg-anchor-bg px-2 text-xs text-anchor-text outline-none focus:border-anchor-accent"
      />
    </label>
  );
}

export function PoolsConfigWorkbench({ initialConfig }: PoolsConfigWorkbenchProps) {
  const [config, setConfig] = useState(initialConfig);
  const [selectedPool, setSelectedPool] = useState<PoolType>('direct_peers');
  const [selectedIndex, setSelectedIndex] = useState<number | null>(0);
  const [draft, setDraft] = useState<Membership | null>(() => (
    initialConfig.memberships[0] ? normalizeMembership(initialConfig.memberships[0]) : null
  ));
  const [isCreating, setIsCreating] = useState(false);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<SaveState>({ kind: 'idle', message: 'config/pools.yaml' });
  const [universeDraft, setUniverseDraft] = useState<Universe>(() => {
    const universe = initialConfig.universes.find((item) => item.universe_id === 'direct_peers');
    return universe ?? initialConfig.universes[0];
  });

  const instrumentsBySymbol = useMemo(() => (
    new Map(config.instruments.map((instrument) => [instrument.symbol, instrument]))
  ), [config.instruments]);

  const indexedMemberships = useMemo<IndexedMembership[]>(() => (
    config.memberships.map((membership, index) => ({
      membership,
      index,
      name: instrumentsBySymbol.get(membership.symbol)?.name ?? membership.symbol,
    }))
  ), [config.memberships, instrumentsBySymbol]);

  const filteredMemberships = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return sortMemberships(indexedMemberships.filter((item) => {
      const inPool = item.membership.universe_id === selectedPool;
      if (!normalizedQuery) return inPool;
      const haystack = [
        item.membership.symbol,
        item.name,
        item.membership.role,
        item.membership.reason,
      ].join(' ').toLowerCase();
      return inPool && haystack.includes(normalizedQuery);
    }));
  }, [indexedMemberships, query, selectedPool]);

  const poolStats = useMemo(() => (
    POOL_ORDER.map((poolId) => {
      const members = config.memberships.filter((membership) => membership.universe_id === poolId);
      return {
        poolId,
        members,
        enabled: members.filter((membership) => membership.enabled).length,
        state: members.filter(getStateScope).length,
        benchmark: members.filter((membership) => membership.include_in_benchmark).length,
        ranking: members.filter((membership) => membership.include_in_ranking).length,
        report: members.filter((membership) => membership.include_in_report).length,
        rotation: members.filter(getRotationScope).length,
      };
    })
  ), [config.memberships]);

  const selectedUniverseIndex = useMemo(() => (
    config.universes.findIndex((universe) => universe.universe_id === selectedPool)
  ), [config.universes, selectedPool]);

  const handleSelectPool = (poolId: PoolType) => {
    setSelectedPool(poolId);
    const universe = config.universes.find((item) => item.universe_id === poolId);
    if (universe) setUniverseDraft({ ...universe });
    const firstMembership = sortMemberships(indexedMemberships).find((item) => item.membership.universe_id === poolId);
    setSelectedIndex(firstMembership?.index ?? null);
    setDraft(firstMembership ? normalizeMembership(firstMembership.membership) : null);
    setIsCreating(false);
  };

  const handleSelectMembership = (item: IndexedMembership) => {
    setSelectedIndex(item.index);
    setDraft(normalizeMembership(item.membership));
    setIsCreating(false);
  };

  const updateDraft = <K extends keyof Membership>(key: K, value: Membership[K]) => {
    setDraft((current) => current ? { ...current, [key]: value } : current);
  };

  const updateUniverseDraft = <K extends keyof Universe>(key: K, value: Universe[K]) => {
    setUniverseDraft((current) => ({ ...current, [key]: value }));
  };

  const handleCreate = () => {
    setDraft(createDraftMembership(config, selectedPool));
    setSelectedIndex(null);
    setIsCreating(true);
    setStatus({ kind: 'idle', message: '新增 membership' });
  };

  const handleRefresh = async () => {
    setStatus({ kind: 'saving', message: '刷新中' });
    try {
      const nextConfig = await fetchConfig();
      setConfig(nextConfig);
      const firstMembership = sortMemberships(nextConfig.memberships.map((membership, index) => ({
        membership,
        index,
        name: nextConfig.instruments.find((instrument) => instrument.symbol === membership.symbol)?.name ?? membership.symbol,
      }))).find((item) => item.membership.universe_id === selectedPool);
      setSelectedIndex(firstMembership?.index ?? null);
      setDraft(firstMembership ? normalizeMembership(firstMembership.membership) : null);
      setIsCreating(false);
      setStatus({ kind: 'saved', message: '已刷新' });
    } catch (error) {
      const message = error instanceof Error ? error.message : '刷新失败';
      setStatus({ kind: 'error', message });
    }
  };

  const handleSaveMembership = async () => {
    if (!draft) return;

    setStatus({ kind: 'saving', message: '保存 membership' });
    try {
      const membership = normalizeMembership(draft);
      const nextConfig = await patchConfig(isCreating
        ? { action: 'addMembership', membership }
        : { action: 'updateMembership', index: selectedIndex ?? -1, membership }
      );

      setConfig(nextConfig);
      const nextIndex = isCreating
        ? nextConfig.memberships.findIndex((item) => item.universe_id === membership.universe_id && item.symbol === membership.symbol)
        : selectedIndex;
      setSelectedIndex(nextIndex);
      setDraft(nextIndex !== null && nextIndex >= 0 ? normalizeMembership(nextConfig.memberships[nextIndex]) : membership);
      setIsCreating(false);
      setSelectedPool(membership.universe_id as PoolType);
      setStatus({ kind: 'saved', message: 'membership 已保存' });
    } catch (error) {
      const message = error instanceof Error ? error.message : '保存失败';
      setStatus({ kind: 'error', message });
    }
  };

  const handleDeleteMembership = async () => {
    if (selectedIndex === null || isCreating) return;
    const target = config.memberships[selectedIndex];
    if (!target) return;
    if (!window.confirm(`删除 ${target.universe_id}/${target.symbol} ?`)) return;

    setStatus({ kind: 'saving', message: '删除 membership' });
    try {
      const nextConfig = await patchConfig({ action: 'deleteMembership', index: selectedIndex });
      setConfig(nextConfig);
      const firstMembership = sortMemberships(nextConfig.memberships.map((membership, index) => ({
        membership,
        index,
        name: nextConfig.instruments.find((instrument) => instrument.symbol === membership.symbol)?.name ?? membership.symbol,
      }))).find((item) => item.membership.universe_id === selectedPool);
      setSelectedIndex(firstMembership?.index ?? null);
      setDraft(firstMembership ? normalizeMembership(firstMembership.membership) : null);
      setStatus({ kind: 'saved', message: 'membership 已删除' });
    } catch (error) {
      const message = error instanceof Error ? error.message : '删除失败';
      setStatus({ kind: 'error', message });
    }
  };

  const handleSaveUniverse = async () => {
    if (selectedUniverseIndex < 0) return;

    setStatus({ kind: 'saving', message: '保存 universe' });
    try {
      const universe = {
        ...universeDraft,
        min_size: Number(universeDraft.min_size),
      };
      const nextConfig = await patchConfig({
        action: 'updateUniverse',
        index: selectedUniverseIndex,
        universe,
      });
      setConfig(nextConfig);
      const nextUniverse = nextConfig.universes.find((item) => item.universe_id === universe.universe_id);
      if (nextUniverse) setUniverseDraft({ ...nextUniverse });
      setSelectedPool(universe.universe_id as PoolType);
      setStatus({ kind: 'saved', message: 'universe 已保存' });
    } catch (error) {
      const message = error instanceof Error ? error.message : '保存失败';
      setStatus({ kind: 'error', message });
    }
  };

  const selectedInstrument = draft ? instrumentsBySymbol.get(draft.symbol) : null;
  const totalStats = {
    instruments: config.instruments.length,
    memberships: config.memberships.length,
    state: config.memberships.filter(getStateScope).length,
    benchmark: config.memberships.filter((membership) => membership.include_in_benchmark).length,
    ranking: config.memberships.filter((membership) => membership.include_in_ranking).length,
    report: config.memberships.filter((membership) => membership.include_in_report).length,
  };

  return (
    <div className="min-h-[calc(100vh-3rem)] overflow-x-hidden bg-anchor-bg text-anchor-text">
      <div className="sticky top-0 z-20 border-b border-anchor-border bg-anchor-bgSecondary px-3 py-3 sm:px-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4 shrink-0 text-anchor-accent" />
              <h1 className="text-sm font-medium">股票池配置工作台</h1>
              <Badge variant="outline" className="font-mono">{config.version}</Badge>
            </div>
            <div className="mt-1 flex flex-wrap gap-3 text-xs text-anchor-textMuted">
              <span>{config.anchor.name} {config.anchor.symbol}</span>
              <span>{totalStats.instruments} instruments</span>
              <span>{totalStats.memberships} memberships</span>
              <span>{totalStats.state} state</span>
              <span>{totalStats.benchmark} benchmark</span>
              <span>{totalStats.ranking} ranking</span>
              <span>{totalStats.report} report</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className={cn(
              'flex items-center gap-1 rounded-sm border px-2 py-1 text-xs',
              status.kind === 'error'
                ? 'border-anchor-negative/30 text-anchor-negative'
                : status.kind === 'saved'
                  ? 'border-anchor-positive/30 text-anchor-positive'
                  : 'border-anchor-border text-anchor-textMuted'
            )}>
              {status.kind === 'error' ? (
                <AlertCircle className="h-3.5 w-3.5" />
              ) : status.kind === 'saved' ? (
                <CheckCircle2 className="h-3.5 w-3.5" />
              ) : (
                <span className="h-3.5 w-3.5 rounded-full border border-current" />
              )}
              <span>{status.message}</span>
            </div>
            <Button variant="outline" onClick={handleRefresh} disabled={status.kind === 'saving'}>
              <RefreshCcw className="mr-1 h-3.5 w-3.5" />
              刷新
            </Button>
          </div>
        </div>
      </div>

      <div className="space-y-3 p-3 sm:p-4">
        <section className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {poolStats.map((item) => (
            <button
              key={item.poolId}
              type="button"
              onClick={() => handleSelectPool(item.poolId)}
              className={cn(
                'min-w-0 rounded-sm border p-3 text-left transition-colors',
                selectedPool === item.poolId
                  ? 'border-anchor-accent bg-anchor-accent/10'
                  : 'border-anchor-border bg-anchor-bgSecondary hover:border-anchor-textMuted'
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="truncate text-sm font-medium">{POOL_NAMES[item.poolId]}</div>
                <Badge variant={selectedPool === item.poolId ? 'accent' : 'neutral'}>
                  {item.members.length}
                </Badge>
              </div>
              <div className="mt-2 grid grid-cols-3 gap-x-2 gap-y-1 text-xs text-anchor-textMuted">
                <span>enable {item.enabled}</span>
                <span>state {item.state}</span>
                <span>bench {item.benchmark}</span>
                <span>rank {item.ranking}</span>
                <span>report {item.report}</span>
                <span>rotate {item.rotation}</span>
              </div>
            </button>
          ))}
        </section>

        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0 space-y-3">
            <section className="grid gap-3 lg:grid-cols-[300px_minmax(0,1fr)]">
              <aside className="rounded-sm border border-anchor-border bg-anchor-bgSecondary p-3">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <div>
                    <div className="text-xs font-medium text-anchor-textSecondary">Universe 配置</div>
                    <div className="mt-1 truncate text-xs text-anchor-textMuted">{selectedPool}</div>
                  </div>
                  <Button size="sm" variant="outline" onClick={handleSaveUniverse} disabled={status.kind === 'saving'}>
                    <Save className="mr-1 h-3 w-3" />
                    保存
                  </Button>
                </div>

                <div className="space-y-2">
                  <TextInput
                    label="display_name"
                    value={universeDraft.display_name}
                    onChange={(value) => updateUniverseDraft('display_name', value)}
                  />
                  <TextInput
                    label="purpose"
                    value={universeDraft.purpose}
                    onChange={(value) => updateUniverseDraft('purpose', value)}
                  />
                  <TextInput
                    label="min_size"
                    type="number"
                    min="0"
                    value={universeDraft.min_size}
                    onChange={(value) => updateUniverseDraft('min_size', Number(value))}
                  />
                  <ScopeToggle
                    label="can_be_benchmark"
                    checked={universeDraft.can_be_benchmark}
                    onChange={(checked) => updateUniverseDraft('can_be_benchmark', checked)}
                  />
                  <label className="block">
                    <span className="mb-1 block text-xs text-anchor-textMuted">description</span>
                    <textarea
                      value={universeDraft.description ?? ''}
                      onChange={(event) => updateUniverseDraft('description', event.target.value)}
                      rows={5}
                      className="w-full rounded-sm border border-anchor-border bg-anchor-bg px-2 py-1 text-xs text-anchor-text outline-none focus:border-anchor-accent"
                    />
                  </label>
                </div>
              </aside>

              <main className="min-w-0 rounded-sm border border-anchor-border bg-anchor-bg">
                <div className="flex flex-col gap-3 border-b border-anchor-border bg-anchor-bgSecondary p-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-anchor-textSecondary">Membership 列表</div>
                    <div className="mt-1 text-xs text-anchor-textMuted">
                      {POOL_NAMES[selectedPool]} / {filteredMemberships.length} 条
                    </div>
                  </div>
                  <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
                    <div className="relative w-full sm:w-80">
                      <Search className="pointer-events-none absolute left-2 top-2 h-3.5 w-3.5 text-anchor-textMuted" />
                      <input
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                        placeholder="symbol / name / role / reason"
                        className="h-8 w-full rounded-sm border border-anchor-border bg-anchor-bg pl-7 pr-2 text-xs text-anchor-text outline-none focus:border-anchor-accent"
                      />
                    </div>

                    <Button onClick={handleCreate} className="w-full sm:w-auto">
                      <Plus className="mr-1 h-3.5 w-3.5" />
                      新增成员
                    </Button>
                  </div>
                </div>

                <div className="min-h-64 overflow-auto xl:max-h-[calc(100vh-22rem)]">
                  <table className="w-full min-w-[700px] text-xs">
                    <thead className="sticky top-0 z-10 bg-anchor-bgSecondary text-anchor-textMuted">
                      <tr className="border-b border-anchor-border">
                        <th className="px-2 py-2 text-left font-medium">Symbol</th>
                        <th className="px-2 py-2 text-left font-medium">Name</th>
                        <th className="px-2 py-2 text-left font-medium">Role</th>
                        <th className="px-2 py-2 text-right font-medium">关联度</th>
                        <th className="px-2 py-2 text-left font-medium">Scopes</th>
                        <th className="px-2 py-2 text-left font-medium">Reviewed</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredMemberships.map((item) => (
                        <tr
                          key={`${item.index}-${item.membership.universe_id}-${item.membership.symbol}`}
                          onClick={() => handleSelectMembership(item)}
                          className={cn(
                            'cursor-pointer border-b border-anchor-border/40 hover:bg-anchor-bgSecondary',
                            selectedIndex === item.index && !isCreating && 'bg-anchor-accent/10'
                          )}
                        >
                          <td className="whitespace-nowrap px-2 py-2 font-mono text-anchor-accent">{item.membership.symbol}</td>
                          <td className="whitespace-nowrap px-2 py-2 text-anchor-text">{item.name}</td>
                          <td className="max-w-[180px] truncate px-2 py-2 text-anchor-textSecondary">{item.membership.role}</td>
                          <td className="whitespace-nowrap px-2 py-2 text-right font-mono">{item.membership.relevance.toFixed(2)}</td>
                          <td className="px-2 py-2">
                            <div className="flex flex-wrap gap-1">
                              {getMembershipScopes(item.membership).map(([label, active]) => (
                                <span
                                  key={label}
                                  className={cn(
                                    'inline-flex h-4 min-w-4 items-center justify-center rounded-sm border px-1 font-mono text-[10px]',
                                    active
                                      ? 'border-anchor-accent/30 bg-anchor-accent/10 text-anchor-accent'
                                      : 'border-anchor-border text-anchor-textMuted'
                                  )}
                                >
                                  {label}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="whitespace-nowrap px-2 py-2 font-mono text-anchor-textMuted">{item.membership.reviewed_at}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </main>
            </section>
          </div>

          <aside className="rounded-sm border border-anchor-border bg-anchor-bgSecondary p-3 xl:sticky xl:top-16 xl:self-start">
          <div className="mb-3 flex items-center justify-between gap-2">
            <div>
              <div className="text-xs font-medium text-anchor-textSecondary">
                {isCreating ? '新增 Membership' : 'Membership 编辑'}
              </div>
              {draft && (
                <div className="mt-1 text-xs text-anchor-textMuted">
                  {selectedInstrument?.name ?? draft.symbol}
                </div>
              )}
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                onClick={handleSaveMembership}
                disabled={!draft || status.kind === 'saving'}
              >
                <Save className="mr-1 h-3.5 w-3.5" />
                保存
              </Button>
              <Button
                variant="destructive"
                size="icon"
                onClick={handleDeleteMembership}
                disabled={selectedIndex === null || isCreating || status.kind === 'saving'}
                title="删除成员"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>

          {draft ? (
            <div className="space-y-3">
              <label className="block">
                <span className="mb-1 block text-xs text-anchor-textMuted">universe_id</span>
                <select
                  value={draft.universe_id}
                  onChange={(event) => updateDraft('universe_id', event.target.value)}
                  className="h-8 w-full rounded-sm border border-anchor-border bg-anchor-bg px-2 text-xs text-anchor-text outline-none focus:border-anchor-accent"
                >
                  {config.universes.map((universe) => (
                    <option key={universe.universe_id} value={universe.universe_id}>
                      {universe.universe_id}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="mb-1 block text-xs text-anchor-textMuted">symbol</span>
                <select
                  value={draft.symbol}
                  onChange={(event) => updateDraft('symbol', event.target.value)}
                  className="h-8 w-full rounded-sm border border-anchor-border bg-anchor-bg px-2 text-xs text-anchor-text outline-none focus:border-anchor-accent"
                >
                  {config.instruments.map((instrument) => (
                    <option key={instrument.symbol} value={instrument.symbol}>
                      {instrument.symbol} {instrument.name}
                    </option>
                  ))}
                </select>
              </label>

              <TextInput
                label="role"
                value={draft.role}
                onChange={(value) => updateDraft('role', value)}
              />

              <div className="grid grid-cols-2 gap-2">
                <TextInput
                  label="关联度 relevance"
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  value={draft.relevance}
                  onChange={(value) => updateDraft('relevance', Number(value))}
                />
                <TextInput
                  label="weight"
                  type="number"
                  min="0"
                  step="0.1"
                  value={draft.weight}
                  onChange={(value) => updateDraft('weight', Number(value))}
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <TextInput
                  label="added_at"
                  type="date"
                  value={draft.added_at}
                  onChange={(value) => updateDraft('added_at', value)}
                />
                <TextInput
                  label="reviewed_at"
                  type="date"
                  value={draft.reviewed_at}
                  onChange={(value) => updateDraft('reviewed_at', value)}
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <ScopeToggle
                  label="enabled"
                  checked={draft.enabled}
                  onChange={(checked) => updateDraft('enabled', checked)}
                />
                <ScopeToggle
                  label="state"
                  checked={getStateScope(draft)}
                  onChange={(checked) => updateDraft('include_in_state', checked)}
                />
                <ScopeToggle
                  label="benchmark"
                  checked={draft.include_in_benchmark}
                  onChange={(checked) => updateDraft('include_in_benchmark', checked)}
                />
                <ScopeToggle
                  label="ranking"
                  checked={draft.include_in_ranking}
                  onChange={(checked) => updateDraft('include_in_ranking', checked)}
                />
                <ScopeToggle
                  label="report"
                  checked={draft.include_in_report}
                  onChange={(checked) => updateDraft('include_in_report', checked)}
                />
                <ScopeToggle
                  label="rotation"
                  checked={getRotationScope(draft)}
                  onChange={(checked) => updateDraft('include_in_rotation', checked)}
                />
              </div>

              <label className="block">
                <span className="mb-1 block text-xs text-anchor-textMuted">reason</span>
                <textarea
                  value={draft.reason}
                  onChange={(event) => updateDraft('reason', event.target.value)}
                  rows={8}
                  className="w-full rounded-sm border border-anchor-border bg-anchor-bg px-2 py-1 text-xs text-anchor-text outline-none focus:border-anchor-accent"
                />
              </label>

              {selectedInstrument && (
                <div className="rounded-sm border border-anchor-border bg-anchor-bg p-2">
                  <div className="mb-1 text-xs text-anchor-textMuted">fact_tags</div>
                  <div className="flex flex-wrap gap-1">
                    {selectedInstrument.fact_tags.map((tag) => (
                      <Badge key={tag} variant="neutral">{tag}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex h-56 items-center justify-center rounded-sm border border-anchor-border bg-anchor-bg text-xs text-anchor-textMuted">
              选择或新增 membership
            </div>
          )}
          </aside>
        </div>
      </div>
    </div>
  );
}
