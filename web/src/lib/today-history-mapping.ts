// ============================================================
// 今日历史映射 - 从当前状态到历史相似路径
// 纯函数，不依赖 React 状态
// ============================================================

import type { HistorySummaryRow } from '@/types';
import { extractLabelCategoryPairs, type SignalPairJson } from '@/lib/history-analysis';

// ============================================================
// 导出类型
// ============================================================

export interface HistoricalPathStat {
  window: '1d' | '3d' | '5d';
  avgReturn: number | null;
  winRate: number | null;
  avgExcess: number | null;
}

export interface SimilarHistoryCase {
  date: string;
  similarity: number;
  matchedSignals: Array<{ category: string | null; label: string }>;
  matchedStateFields: string[];
  next1d: number | null;
  next3d: number | null;
  next5d: number | null;
}

export interface TodayHistoryMapping {
  targetDate: string;
  sampleCount: number;
  pathLabel: string;
  stateSummary: string;
  coreSignals: string[];
  pathStats: HistoricalPathStat[];
  similarCases: SimilarHistoryCase[];
  notes: string[];
}

// ============================================================
// 内部工具
// ============================================================

type OrderedLevel = 'positive' | 'neutral' | 'negative';
type RiskLevel = 'low' | 'medium' | 'high';

const BETA_ALPHA_ORDER: OrderedLevel[] = ['positive', 'neutral', 'negative'];
const RISK_ORDER: RiskLevel[] = ['low', 'medium', 'high'];

function ordinalScore(
  a: string | null,
  b: string | null,
  order: string[]
): { score: number; comparable: boolean } {
  if (!a || !b) return { score: 0, comparable: false };
  const na = a.trim().toLowerCase();
  const nb = b.trim().toLowerCase();
  const ia = order.indexOf(na);
  const ib = order.indexOf(nb);
  if (ia === -1 || ib === -1) {
    // unknown enum: exact match only
    return { score: na === nb ? 1 : 0, comparable: true };
  }
  if (ia === ib) return { score: 1, comparable: true };
  if (Math.abs(ia - ib) === 1) return { score: 0.5, comparable: true };
  return { score: 0, comparable: true };
}

function exactMatchScore(a: string | null, b: string | null): { score: number; comparable: boolean } {
  if (!a || !b) return { score: 0, comparable: false };
  return { score: a.trim().toLowerCase() === b.trim().toLowerCase() ? 1 : 0, comparable: true };
}

function signalSet(row: HistorySummaryRow): Set<string> {
  const pairs = extractLabelCategoryPairs(row);
  if (pairs.length > 0) {
    return new Set(pairs.map((p) => `${p.category}::${p.label}`));
  }
  // fallback: signal_labels only
  if (!row.signal_labels) return new Set();
  return new Set(
    row.signal_labels.split(',').map((s) => s.trim()).filter(Boolean).map((l) => `::${l}`)
  );
}

function jaccard(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 && b.size === 0) return 0;
  let intersection = 0;
  for (const item of a) {
    if (b.has(item)) intersection++;
  }
  return intersection / (a.size + b.size - intersection);
}

function intersectedSignals(
  targetPairs: SignalPairJson[],
  candidatePairs: SignalPairJson[]
): Array<{ category: string | null; label: string }> {
  const candidateSet = new Set(candidatePairs.map((p) => `${p.category}::${p.label}`));
  return targetPairs
    .filter((p) => candidateSet.has(`${p.category}::${p.label}`))
    .map((p) => ({ category: p.category || null, label: p.label }));
}

function avgOf(arr: number[]): number | null {
  if (arr.length === 0) return null;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function winRateOf(arr: (number | null)[]): number | null {
  const valid = arr.filter((x): x is number => x !== null);
  if (valid.length === 0) return null;
  return valid.filter((x) => x > 0).length / valid.length;
}

const MIN_EFFECTIVE_SAMPLES = 5;
const MAX_TOP_N = 12;
const TOP_N_RATIO = 0.15;

// ============================================================
// 状态相似评分
// ============================================================

interface StateFieldResult {
  score: number;
  comparable: boolean;
  fieldName: string;
}

function computeStateScore(
  target: HistorySummaryRow,
  candidate: HistorySummaryRow
): { score: number; matchedFields: string[] } {
  const fields: StateFieldResult[] = [
    { ...ordinalScore(target.industry_beta, candidate.industry_beta, BETA_ALPHA_ORDER), fieldName: 'industry_beta' },
    { ...ordinalScore(target.anchor_alpha, candidate.anchor_alpha, BETA_ALPHA_ORDER), fieldName: 'anchor_alpha' },
    { ...ordinalScore(target.risk_level, candidate.risk_level, RISK_ORDER), fieldName: 'risk_level' },
    { ...exactMatchScore(target.strongest_group, candidate.strongest_group), fieldName: 'strongest_group' },
    { ...exactMatchScore(target.weakest_group, candidate.weakest_group), fieldName: 'weakest_group' },
  ];

  const weights: Record<string, number> = {
    industry_beta: 0.25,
    anchor_alpha: 0.25,
    risk_level: 0.20,
    strongest_group: 0.15,
    weakest_group: 0.15,
  };

  const comparable = fields.filter((f) => f.comparable);
  if (comparable.length === 0) return { score: 0, matchedFields: [] };

  let weightedSum = 0;
  let weightSum = 0;
  const matchedFields: string[] = [];

  for (const f of comparable) {
    const w = weights[f.fieldName];
    weightedSum += f.score * w;
    weightSum += w;
    if (f.score > 0) matchedFields.push(f.fieldName);
  }

  return { score: weightSum > 0 ? weightedSum / weightSum : 0, matchedFields };
}

// ============================================================
// 路径标签
// ============================================================

function derivePathLabel(stats: HistoricalPathStat[]): string {
  const s1 = stats.find((s) => s.window === '1d');
  const s3 = stats.find((s) => s.window === '3d');
  const s5 = stats.find((s) => s.window === '5d');

  const r1: number | null = s1 ? s1.avgReturn : null;
  const r3: number | null = s3 ? s3.avgReturn : null;
  const r5: number | null = s5 ? s5.avgReturn : null;
  const w1: number | null = s1 ? s1.winRate : null;
  const w3: number | null = s3 ? s3.winRate : null;
  const w5: number | null = s5 ? s5.winRate : null;

  // 强势延续
  if (
    r1 !== null && r1 > 0 &&
    r3 !== null && r3 > 0 &&
    r5 !== null && r5 > 0 &&
    w1 !== null && w1 >= 0.55 &&
    w3 !== null && w3 >= 0.55 &&
    w5 !== null && w5 >= 0.55
  ) {
    return '强势延续';
  }

  // 冲高回落
  if (r1 !== null && r1 > 0.5 && r5 !== null && (r1 - r5) >= 0.7) {
    return '冲高回落';
  }

  // 继续走弱
  const negativeWindows = [r1, r3, r5].filter((r) => r !== null && r < -0.3);
  if (negativeWindows.length >= 2) {
    return '继续走弱';
  }

  // 弱势修复
  if (
    (r1 !== null && r1 > 0.3) || (r3 !== null && r3 > 0.3)
  ) {
    if (r5 === null || r5 <= 0 || (w5 !== null && w5 < 0.5)) {
      return '弱势修复';
    }
  }

  // 窄幅震荡
  const allSmall = [r1, r3, r5].every((r) => r === null || Math.abs(r) < 0.2);
  const allWinRateNarrow = [w1, w3, w5].every((w) => w === null || (w >= 0.45 && w <= 0.55));
  if (allSmall && allWinRateNarrow) {
    return '窄幅震荡';
  }

  return '样本分歧';
}

// ============================================================
// 状态摘要
// ============================================================

function buildStateSummary(row: HistorySummaryRow): string {
  const betaMap: Record<string, string> = { positive: '行业偏强', neutral: '行业中性', negative: '行业偏弱' };
  const alphaMap: Record<string, string> = { positive: '个股偏强', neutral: '个股中性', negative: '个股偏弱' };
  const riskMap: Record<string, string> = { low: '低风险', medium: '中风险', high: '高风险' };

  const beta = betaMap[String(row.industry_beta)] || '行业未知';
  const alpha = alphaMap[String(row.anchor_alpha)] || '个股未知';
  const risk = riskMap[String(row.risk_level)] || '风险未知';

  return `${beta} + ${alpha} + ${risk}`;
}

// ============================================================
// 主派生函数
// ============================================================

export function deriveTodayHistoryMapping(
  summary: HistorySummaryRow[],
  targetDate?: string
): TodayHistoryMapping | null {
  if (summary.length === 0) return null;

  // 找目标日
  const validRows = summary.filter(
    (r) =>
      r.data_quality_status !== 'insufficient_data' &&
      (r.industry_beta || r.anchor_alpha || r.risk_level) &&
      (r.signal_pairs || r.signal_labels)
  );

  if (validRows.length === 0) return null;

  const sorted = [...validRows].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  const target = targetDate
    ? sorted.find((r) => String(r.date) === targetDate)
    : sorted[sorted.length - 1];

  if (!target) return null;

  // 候选样本：目标日之前、有前瞻收益
  const candidates = sorted.filter(
    (r) =>
      String(r.date) < String(target.date) &&
      (r.next_1d_return !== null || r.next_3d_return !== null || r.next_5d_return !== null)
  );

  if (candidates.length < MIN_EFFECTIVE_SAMPLES) return null;

  // 计算相似度
  const targetSignals = signalSet(target);
  const targetPairs = extractLabelCategoryPairs(target);

  const scored = candidates.map((c) => {
    const { score: stateScore, matchedFields } = computeStateScore(target, c);
    const candidateSignals = signalSet(c);
    const signalJaccard = jaccard(targetSignals, candidateSignals);
    const similarity = stateScore * 0.6 + signalJaccard * 0.4;
    const candidatePairs = extractLabelCategoryPairs(c);
    const matched = intersectedSignals(targetPairs, candidatePairs);

    return { row: c, similarity, matchedFields, matchedSignals: matched };
  });

  scored.sort((a, b) => b.similarity - a.similarity);

  // 自适应 Top N
  const topN = Math.min(MAX_TOP_N, Math.max(MIN_EFFECTIVE_SAMPLES, Math.round(candidates.length * TOP_N_RATIO)));
  const topSamples = scored.slice(0, topN);

  // 路径统计
  const returns1d = topSamples.map((s) => s.row.next_1d_return);
  const returns3d = topSamples.map((s) => s.row.next_3d_return);
  const returns5d = topSamples.map((s) => s.row.next_5d_return);
  const excess1d = topSamples.map((s) => s.row.next_1d_excess_vs_chain);
  const excess3d = topSamples.map((s) => s.row.next_3d_excess_vs_chain);
  const excess5d = topSamples.map((s) => s.row.next_5d_excess_vs_chain);

  const pathStats: HistoricalPathStat[] = [
    {
      window: '1d',
      avgReturn: avgOf(returns1d.filter((x): x is number => x !== null)),
      winRate: winRateOf(returns1d),
      avgExcess: avgOf(excess1d.filter((x): x is number => x !== null)),
    },
    {
      window: '3d',
      avgReturn: avgOf(returns3d.filter((x): x is number => x !== null)),
      winRate: winRateOf(returns3d),
      avgExcess: avgOf(excess3d.filter((x): x is number => x !== null)),
    },
    {
      window: '5d',
      avgReturn: avgOf(returns5d.filter((x): x is number => x !== null)),
      winRate: winRateOf(returns5d),
      avgExcess: avgOf(excess5d.filter((x): x is number => x !== null)),
    },
  ];

  const pathLabel = derivePathLabel(pathStats);

  // 相似案例 Top 5
  const similarCases: SimilarHistoryCase[] = topSamples.slice(0, 5).map((s) => ({
    date: s.row.date,
    similarity: s.similarity,
    matchedSignals: s.matchedSignals,
    matchedStateFields: s.matchedFields,
    next1d: s.row.next_1d_return,
    next3d: s.row.next_3d_return,
    next5d: s.row.next_5d_return,
  }));

  // 核心信号
  const coreSignals = targetPairs.slice(0, 5).map((p) => p.label);

  // 备注
  const notes: string[] = [];
  if (candidates.length < 20) {
    notes.push(`候选样本仅 ${candidates.length} 个，路径参考有限`);
  }
  if (topSamples[0] && topSamples[0].similarity < 0.3) {
    notes.push('最高相似度低于 0.3，路径参考价值较低');
  }

  return {
    targetDate: target.date,
    sampleCount: topSamples.length,
    pathLabel,
    stateSummary: buildStateSummary(target),
    coreSignals,
    pathStats,
    similarCases,
    notes,
  };
}
