// ============================================================
// 历史分析派生函数库
// 纯函数，不依赖 React 状态
// ============================================================

import type {
  HistorySummaryRow,
  QuadrantStat,
  SignalLiftRow,
  StateTransition,
  ExtremeDivergence,
  EventPathRow,
  SignalInsight,
  BusinessGroup,
  SignalTrend,
  TrendStatus,
  Combination,
  TradingRule,
  CombinationSynergy,
  DecisionSummary,
  TradingPlaybook,
  DecisionSummaryInput,
  TradingPlaybookInput,
  SignalCardConclusionInput,
} from '@/types';
import { formatSignalLabel } from '@/lib/utils';

// ============================================================
// View Models (页面展示用的派生类型)
// ============================================================

export interface CoreMetrics {
  sampleReturn: {
    avgDailyReturn: number | null;
    medianReturn: number | null;
    positiveRatio: number | null;
  };
  relativeToIndustry: {
    avgChainMedian: number | null;
    avgDailyExcess: number | null;
    outperformRatio: number | null;
  };
  scenarioQuality: {
    bestQuadrant: QuadrantStat | null;
    worstQuadrant: QuadrantStat | null;
    validQuadrantCount: number;
  };
  eventRisk: {
    divergenceCount: number;
    maxPositiveDivergence: number | null;
    maxNegativeDivergence: number | null;
  };
}

export interface Conclusion {
  sampleDays: number;
  dateRange: { start: string; end: string };
  bestQuadrant: QuadrantStat | null;
  worstQuadrant: QuadrantStat | null;
  meanReversion: {
    outperformThenReverseRate: number | null;
    underperformThenReverseRate: number | null;
  };
  warning: string;
}

export interface DivergenceWithFollowThrough extends ExtremeDivergence {
  t1Return: number | null;
  t3Return: number | null;
  t1Excess: number | null;
  t3Excess: number | null;
}

// ============================================================
// 工具函数
// ============================================================

function avg(arr: (number | null)[]): number | null {
  const valid = arr.filter((x): x is number => x !== null);
  if (valid.length === 0) return null;
  return valid.reduce((a, b) => a + b, 0) / valid.length;
}

function median(arr: (number | null)[]): number | null {
  const valid = arr.filter((x): x is number => x !== null);
  if (valid.length === 0) return null;
  const sorted = [...valid].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function ratio(numerator: number, denominator: number): number | null {
  if (denominator === 0) return null;
  return numerator / denominator;
}

function max(arr: (number | null)[]): number | null {
  const valid = arr.filter((x): x is number => x !== null);
  if (valid.length === 0) return null;
  return Math.max(...valid);
}

function min(arr: (number | null)[]): number | null {
  const valid = arr.filter((x): x is number => x !== null);
  if (valid.length === 0) return null;
  return Math.min(...valid);
}

function parseSignalLabels(labelsStr: string | null): string[] {
  if (!labelsStr) return [];
  return labelsStr.split(',').map((s) => s.trim()).filter(Boolean);
}

function parseSignalCategories(categoriesStr: string | null): string[] {
  if (!categoriesStr) return [];
  return categoriesStr.split(',').map((s) => s.trim()).filter(Boolean);
}

interface SignalPairJson {
  label: string;
  category: string;
}

function parseSignalPairs(pairsStr: string | null): SignalPairJson[] {
  if (!pairsStr) return [];
  try {
    const parsed = JSON.parse(pairsStr);
    if (Array.isArray(parsed)) return parsed;
  } catch {
    // fallback below
  }
  return [];
}

function extractLabelCategoryPairs(row: HistorySummaryRow): SignalPairJson[] {
  // Prefer signal_pairs JSON
  const pairs = parseSignalPairs(row.signal_pairs);
  if (pairs.length > 0) return pairs;

  // Fallback: rebuild from signal_labels + signal_categories
  const labels = parseSignalLabels(row.signal_labels);
  const categories = parseSignalCategories(row.signal_categories);
  return labels.map((label, i) => ({
    label,
    category: categories[i] || '',
  }));
}

// ============================================================
// 筛选函数
// ============================================================

export function filterSummaryByDateRange(
  summary: HistorySummaryRow[],
  startDate: string,
  endDate: string
): HistorySummaryRow[] {
  return summary.filter((row) => row.date >= startDate && row.date <= endDate);
}

// ============================================================
// 象限重算函数
// ============================================================

function classifyQuadrant(industryBeta: string | null, anchorAlpha: string | null): string {
  const beta = industryBeta || 'neutral';
  const alpha = anchorAlpha || 'neutral';
  return `${beta}+${alpha}`;
}

const ALL_QUADRANTS: string[] = [
  'positive+positive', 'positive+neutral', 'positive+negative',
  'neutral+positive', 'neutral+neutral', 'neutral+negative',
  'negative+positive', 'negative+neutral', 'negative+negative',
];

export function deriveQuadrantsFromSummary(summary: HistorySummaryRow[]): QuadrantStat[] {
  const quadrantMap = new Map<string, {
    count: number;
    next1dReturns: (number | null)[];
    next3dReturns: (number | null)[];
    next5dReturns: (number | null)[];
    next1dExcesses: (number | null)[];
    relativeStrengths: (number | null)[];
  }>();

  // 初始化所有 9 个象限
  for (const quadrant of ALL_QUADRANTS) {
    quadrantMap.set(quadrant, {
      count: 0,
      next1dReturns: [],
      next3dReturns: [],
      next5dReturns: [],
      next1dExcesses: [],
      relativeStrengths: [],
    });
  }

  // 填充数据
  for (const row of summary) {
    if (row.data_quality_status === 'insufficient_data') continue;
    const quadrant = classifyQuadrant(row.industry_beta, row.anchor_alpha);
    const data = quadrantMap.get(quadrant)!;
    if (row.next_1d_return !== null) {
      data.count++;
      data.next1dReturns.push(row.next_1d_return);
      data.next3dReturns.push(row.next_3d_return);
      data.next5dReturns.push(row.next_5d_return);
      data.next1dExcesses.push(row.next_1d_excess_vs_chain);
      data.relativeStrengths.push(row.relative_strength_vs_industry_chain);
    }
  }

  // 生成结果
  const result: QuadrantStat[] = [];
  for (const quadrant of ALL_QUADRANTS) {
    const data = quadrantMap.get(quadrant)!;
    result.push({
      quadrant,
      count: data.count,
      avg_next_1d: data.count > 0 ? avg(data.next1dReturns) : null,
      avg_next_3d: data.count > 0 ? avg(data.next3dReturns) : null,
      avg_next_5d: data.count > 0 ? avg(data.next5dReturns) : null,
      avg_next_1d_excess: data.count > 0 ? avg(data.next1dExcesses) : null,
      win_rate_1d: data.count > 0
        ? ratio(data.next1dReturns.filter((r) => r !== null && r > 0).length, data.count)
        : null,
      avg_relative_strength: data.count > 0 ? avg(data.relativeStrengths) : null,
    });
  }

  return result;
}

// ============================================================
// 信号 Lift 重算函数
// ============================================================

export function deriveSignalLiftsFromSummary(
  summary: HistorySummaryRow[],
  category?: string
): SignalLiftRow[] {
  const validRows = summary.filter(
    (row) => row.data_quality_status !== 'insufficient_data' && row.next_1d_return !== null
  );

  if (validRows.length === 0) return [];

  // 计算基线
  const baselineNext1dReturns = validRows.map((r) => r.next_1d_return!);
  const baselineAvgNext1d = avg(baselineNext1dReturns)!;
  const baselineWinRate1d = ratio(
    baselineNext1dReturns.filter((r) => r > 0).length,
    baselineNext1dReturns.length
  )!;

  // 按信号分组
  const signalMap = new Map<string, {
    category: string;
    count: number;
    next1dReturns: number[];
    next3dReturns: (number | null)[];
    next5dReturns: (number | null)[];
    next1dExcesses: (number | null)[];
  }>();

  for (const row of validRows) {
    const pairs = extractLabelCategoryPairs(row);

    for (const { label, category: cat } of pairs) {
      // 如果指定了类别，过滤
      if (category && category !== 'all' && cat !== category) continue;

      if (!signalMap.has(label)) {
        signalMap.set(label, {
          category: cat,
          count: 0,
          next1dReturns: [],
          next3dReturns: [],
          next5dReturns: [],
          next1dExcesses: [],
        });
      }
      const data = signalMap.get(label)!;
      data.count++;
      data.next1dReturns.push(row.next_1d_return!);
      data.next3dReturns.push(row.next_3d_return);
      data.next5dReturns.push(row.next_5d_return);
      data.next1dExcesses.push(row.next_1d_excess_vs_chain);
    }
  }

  // 生成结果
  const result: SignalLiftRow[] = [];
  for (const [label, data] of signalMap.entries()) {
    const avgNext1d = avg(data.next1dReturns)!;
    const avgNext1dExcess = avg(data.next1dExcesses);
    const winRate1d = ratio(data.next1dReturns.filter((r) => r > 0).length, data.count);
    const avgNext1dDeltaPp = avgNext1d - baselineAvgNext1d;
    const liftNext1d = Math.abs(baselineAvgNext1d) > 0.001
      ? avgNext1dDeltaPp / Math.abs(baselineAvgNext1d)
      : null;
    const liftWinRate = winRate1d !== null && baselineWinRate1d !== null
      ? winRate1d - baselineWinRate1d
      : null;

    result.push({
      label,
      category: data.category,
      appearance_count: data.count,
      avg_next_1d: avgNext1d,
      avg_next_3d: avg(data.next3dReturns),
      avg_next_5d: avg(data.next5dReturns),
      avg_next_1d_excess: avgNext1dExcess,
      win_rate_1d: winRate1d,
      baseline_avg_next_1d: baselineAvgNext1d,
      baseline_win_rate_1d: baselineWinRate1d,
      avg_next_1d_delta_pp: avgNext1dDeltaPp,
      lift_next_1d: liftNext1d,
      lift_win_rate: liftWinRate,
      min_count_passed: data.count >= 5,
    });
  }

  // 按 delta_pp 降序排序
  return result.sort((a, b) => (b.avg_next_1d_delta_pp ?? 0) - (a.avg_next_1d_delta_pp ?? 0));
}

// ============================================================
// 状态转移重算函数
// ============================================================

export function deriveTransitionsFromSummary(summary: HistorySummaryRow[]): StateTransition[] {
  const validRows = summary.filter((row) => row.data_quality_status !== 'insufficient_data');

  const transitionCount = new Map<string, number>();
  const fromStateCount = new Map<string, number>();

  // 初始化所有 9x9=81 种可能的转移（count=0）
  for (const from of ALL_QUADRANTS) {
    for (const to of ALL_QUADRANTS) {
      transitionCount.set(`${from}|${to}`, 0);
    }
    fromStateCount.set(from, 0);
  }

  // 统计转移
  for (let i = 0; i < validRows.length - 1; i++) {
    const fromState = classifyQuadrant(validRows[i].industry_beta, validRows[i].anchor_alpha);
    const toState = classifyQuadrant(validRows[i + 1].industry_beta, validRows[i + 1].anchor_alpha);
    const key = `${fromState}|${toState}`;
    transitionCount.set(key, (transitionCount.get(key) || 0) + 1);
    fromStateCount.set(fromState, (fromStateCount.get(fromState) || 0) + 1);
  }

  // 生成结果
  const result: StateTransition[] = [];
  for (const from of ALL_QUADRANTS) {
    for (const to of ALL_QUADRANTS) {
      const key = `${from}|${to}`;
      const count = transitionCount.get(key) || 0;
      const totalFrom = fromStateCount.get(from) || 0;
      const probability = totalFrom > 0 ? count / totalFrom : 0;
      result.push({ from_state: from, to_state: to, count, probability });
    }
  }

  return result;
}

// ============================================================
// 最佳/最差象限算法
// ============================================================

export function deriveQuadrantHighlights(quadrants: QuadrantStat[]): {
  best: QuadrantStat | null;
  worst: QuadrantStat | null;
} {
  const eligible = quadrants.filter((q) => q.count >= 5 && q.avg_next_1d !== null);

  if (eligible.length === 0) return { best: null, worst: null };

  // 排序：优先用 avg_next_1d_excess，没有则用 avg_next_1d
  const sorted = [...eligible].sort((a, b) => {
    const scoreA = a.avg_next_1d_excess ?? a.avg_next_1d ?? 0;
    const scoreB = b.avg_next_1d_excess ?? b.avg_next_1d ?? 0;
    if (scoreB !== scoreA) return scoreB - scoreA;
    const winRateA = a.win_rate_1d ?? 0;
    const winRateB = b.win_rate_1d ?? 0;
    if (winRateB !== winRateA) return winRateB - winRateA;
    return b.count - a.count;
  });

  const best = sorted[0];
  const worst = sorted[sorted.length - 1];

  return { best, worst };
}

// ============================================================
// 核心指标派生
// ============================================================

export function deriveCoreMetrics(
  summary: HistorySummaryRow[],
  divergences: ExtremeDivergence[]
): CoreMetrics {
  const validRows = summary.filter((row) => row.data_quality_status !== 'insufficient_data');

  // 样本收益
  const anchorReturns = validRows.map((r) => r.anchor_return);
  const sampleReturn = {
    avgDailyReturn: avg(anchorReturns),
    medianReturn: median(anchorReturns),
    positiveRatio: ratio(
      anchorReturns.filter((r) => r !== null && r > 0).length,
      anchorReturns.filter((r) => r !== null).length
    ),
  };

  // 相对行业
  const chainMedians = validRows.map((r) => r.industry_chain_median);
  const excesses = validRows.map((r) => r.relative_strength_vs_industry_chain);
  const relativeToIndustry = {
    avgChainMedian: avg(chainMedians),
    avgDailyExcess: avg(excesses),
    outperformRatio: ratio(
      excesses.filter((r) => r !== null && r > 0).length,
      excesses.filter((r) => r !== null).length
    ),
  };

  // 场景质量
  const quadrants = deriveQuadrantsFromSummary(summary);
  const { best, worst } = deriveQuadrantHighlights(quadrants);
  const scenarioQuality = {
    bestQuadrant: best,
    worstQuadrant: worst,
    validQuadrantCount: quadrants.filter((q) => q.count >= 5).length,
  };

  // 事件风险
  const divergenceValues = divergences.map((d) => d.divergence);
  const eventRisk = {
    divergenceCount: divergences.length,
    maxPositiveDivergence: max(divergenceValues),
    maxNegativeDivergence: min(divergenceValues),
  };

  return { sampleReturn, relativeToIndustry, scenarioQuality, eventRisk };
}

// ============================================================
// 样本内结论派生
// ============================================================

export function deriveConclusion(
  summary: HistorySummaryRow[],
  quadrants: QuadrantStat[]
): Conclusion {
  const validRows = summary.filter((row) => row.data_quality_status !== 'insufficient_data');
  const sampleDays = validRows.length;

  // 日期范围
  const sortedDates = validRows.map((r) => r.date).sort();
  const dateRange = {
    start: sortedDates[0] || '',
    end: sortedDates[sortedDates.length - 1] || '',
  };

  // 最佳/最差象限
  const { best, worst } = deriveQuadrantHighlights(quadrants);

  // 均值回归计算
  const rowsWithNext = validRows.filter((r) => r.next_1d_excess_vs_chain !== null);
  let outperformThenReverse = 0;
  let outperformCount = 0;
  let underperformThenReverse = 0;
  let underperformCount = 0;

  for (const row of rowsWithNext) {
    const excess = row.relative_strength_vs_industry_chain;
    const nextExcess = row.next_1d_excess_vs_chain!;

    if (excess !== null) {
      if (excess > 0) {
        outperformCount++;
        if (nextExcess < 0) outperformThenReverse++;
      } else if (excess < 0) {
        underperformCount++;
        if (nextExcess > 0) underperformThenReverse++;
      }
    }
  }

  const meanReversion = {
    outperformThenReverseRate: ratio(outperformThenReverse, outperformCount),
    underperformThenReverseRate: ratio(underperformThenReverse, underperformCount),
  };

  // 警告文案
  let warning = '';
  if (sampleDays < 30) {
    warning = '样本不足，不生成方向性结论';
  } else if (sampleDays < 80) {
    warning = '样本有限，结论仅供观察';
  } else {
    warning = '结论仅代表样本内表现，需持续验证';
  }

  return { sampleDays, dateRange, bestQuadrant: best, worstQuadrant: worst, meanReversion, warning };
}

// ============================================================
// 状态转移摘要
// ============================================================

export function deriveTransitionSummary(transitions: StateTransition[]): string[] {
  // 对每个 from_state，找概率最大的 to_state
  const fromStateMap = new Map<string, StateTransition>();

  for (const t of transitions) {
    if (t.count === 0) continue;
    const existing = fromStateMap.get(t.from_state);
    if (!existing || t.probability > existing.probability) {
      fromStateMap.set(t.from_state, t);
    }
  }

  // 筛选并排序
  const candidates = Array.from(fromStateMap.values())
    .filter((t) => t.probability >= 0.3 && t.count >= 3)
    .sort((a, b) => b.probability - a.probability)
    .slice(0, 3);

  // 生成文案
  const quadrantDisplayName: Record<string, string> = {
    'positive+positive': '行业强+个股强',
    'positive+neutral': '行业强+个股中性',
    'positive+negative': '行业强+个股弱',
    'neutral+positive': '行业中性+个股强',
    'neutral+neutral': '行业中性+个股中性',
    'neutral+negative': '行业中性+个股弱',
    'negative+positive': '行业弱+个股强',
    'negative+neutral': '行业弱+个股中性',
    'negative+negative': '行业弱+个股弱',
  };

  return candidates.map((t) => {
    const fromDisplay = quadrantDisplayName[t.from_state] || t.from_state;
    const toDisplay = quadrantDisplayName[t.to_state] || t.to_state;
    return `${fromDisplay} 次日最常转向 ${toDisplay}，样本 ${t.count} 次，概率 ${(t.probability * 100).toFixed(0)}%`;
  });
}

// ============================================================
// 极端背离后续表现
// ============================================================

export function deriveDivergenceFollowThrough(
  divergences: ExtremeDivergence[],
  events: EventPathRow[]
): DivergenceWithFollowThrough[] {
  // 按日期索引事件路径
  const eventMap = new Map<string, EventPathRow[]>();
  for (const e of events) {
    if (!eventMap.has(e.event_date)) eventMap.set(e.event_date, []);
    eventMap.get(e.event_date)!.push(e);
  }

  return divergences.map((d) => {
    const eventPaths = eventMap.get(d.date) || [];
    const t1 = eventPaths.find((e) => e.offset === 1);
    const t3 = eventPaths.find((e) => e.offset === 3);

    return {
      ...d,
      t1Return: t1?.anchor_return ?? null,
      t3Return: t3?.anchor_return ?? null,
      t1Excess: t1?.excess ?? null,
      t3Excess: t3?.excess ?? null,
    };
  });
}

// ============================================================
// 信号洞察：高价值/低价值信号
// ============================================================

function segmentScore(value: number, lowThreshold: number, highThreshold: number): number {
  if (value <= lowThreshold) return 0;
  if (value >= highThreshold) return 100;
  return ((value - lowThreshold) / (highThreshold - lowThreshold)) * 100;
}

export function deriveSignalInsights(signals: SignalLiftRow[]): {
  highValue: SignalInsight[];
  lowValue: SignalInsight[];
} {
  const highValue: SignalInsight[] = [];
  const lowValue: SignalInsight[] = [];

  for (const s of signals) {
    if (!s.min_count_passed) continue;
    const dp = s.avg_next_1d_delta_pp ?? 0;
    const wr = s.win_rate_1d ?? 0;
    const cnt = s.appearance_count;

    const returnScore = segmentScore(dp, 0, 1.5);
    const winRateScore = segmentScore(wr, 0.45, 0.65);
    const sampleScore = segmentScore(cnt, 5, 20);
    const stabilityScore = returnScore * 0.4 + winRateScore * 0.3 + sampleScore * 0.3;

    const insight: SignalInsight = {
      label: s.label,
      category: s.category,
      deltaPp: dp,
      winRate: wr,
      count: cnt,
      stabilityScore: Math.round(stabilityScore),
    };

    if (dp > 0.5 && wr > 0.5 && cnt >= 10) {
      highValue.push(insight);
    } else if (dp < 0 || wr < 0.5) {
      lowValue.push(insight);
    }
  }

  highValue.sort((a, b) => b.stabilityScore - a.stabilityScore);
  lowValue.sort((a, b) => a.deltaPp - b.deltaPp);

  return { highValue, lowValue };
}

// ============================================================
// 信号趋势：近期 vs 历史表现对比
// ============================================================

export function deriveSignalTrends(
  signals: SignalLiftRow[],
  filteredSummary: HistorySummaryRow[]
): SignalTrend[] {
  const validRows = filteredSummary.filter(
    (r) => r.data_quality_status !== 'insufficient_data' && r.next_1d_return !== null
  );

  // 按日期排序，取最近 20 个有效样本作为"近期"
  const sortedRows = [...validRows].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  const recentCount = 20;

  return signals.map((s) => {
    // 找出包含该信号的所有行
    const matchingRows = sortedRows.filter((row) => {
      const pairs = extractLabelCategoryPairs(row);
      return pairs.some((p) => p.label === s.label);
    });

    if (matchingRows.length < recentCount) {
      return {
        label: s.label,
        trend: 'trend_insufficient' as TrendStatus,
        recentDelta: null,
        historicalDelta: s.avg_next_1d_delta_pp,
      };
    }

    const recentRows = matchingRows.slice(-recentCount);
    const historicalRows = matchingRows.slice(0, -recentCount);

    const recentReturns = recentRows.map((r) => r.next_1d_return!);
    const recentAvg = avg(recentReturns) ?? 0;

    // 计算 baseline
    const allReturns = validRows.map((r) => r.next_1d_return!);
    const baselineAvg = avg(allReturns) ?? 0;

    const recentDelta = recentAvg - baselineAvg;
    const historicalDelta = s.avg_next_1d_delta_pp ?? 0;

    const diff = recentDelta - historicalDelta;
    let trend: TrendStatus;
    if (Math.abs(diff) < 0.2) {
      trend = 'trend_stable';
    } else if (diff > 0) {
      trend = 'trend_improving';
    } else {
      trend = 'trend_deteriorating';
    }

    return { label: s.label, trend, recentDelta, historicalDelta };
  });
}

// ============================================================
// 信号业务分组
// ============================================================

const BUSINESS_GROUPS: { name: string; description: string; labels: string[] }[] = [
  {
    name: '趋势跟随',
    description: '市场方向明确时有效',
    labels: ['行业Beta为正', '行业Beta为负', '个股Alpha为正', '个股Alpha为负'],
  },
  {
    name: '资金验证',
    description: '量价配合验证信号',
    labels: ['放量上涨', '放量下跌', '主力资金领先'],
  },
  {
    name: '情绪拐点',
    description: '情绪与基本面背离时关注',
    labels: ['主线池强于主题情绪', '交易观察池升温'],
  },
  {
    name: '相对强弱',
    description: '个股相对行业池的位置',
    labels: ['跑赢主线池', '跑输主线池', '处于行业前排'],
  },
  {
    name: '异常信号',
    description: '行业与个股方向背离',
    labels: ['行业强但个股弱', '行业弱但个股强'],
  },
];

export function groupSignalsByBusinessLogic(signals: SignalLiftRow[]): BusinessGroup[] {
  const assignedLabels = new Set<string>();

  const groups: BusinessGroup[] = BUSINESS_GROUPS.map((g) => {
    const groupSignals = signals.filter(
      (s) => g.labels.includes(s.label)
    );
    groupSignals.forEach((s) => assignedLabels.add(s.label));

    return {
      name: g.name,
      description: g.description,
      signals: groupSignals.sort(
        (a, b) => (b.avg_next_1d_delta_pp ?? 0) - (a.avg_next_1d_delta_pp ?? 0)
      ),
    };
  }).filter((g) => g.signals.length > 0);

  // 未匹配的信号归入"其他"
  const unassigned = signals.filter((s) => !assignedLabels.has(s.label));
  if (unassigned.length > 0) {
    groups.push({
      name: '其他信号',
      description: '未归入以上分类',
      signals: unassigned.sort(
        (a, b) => (b.avg_next_1d_delta_pp ?? 0) - (a.avg_next_1d_delta_pp ?? 0)
      ),
    });
  }

  return groups;
}

// ============================================================
// 信号组合分析
// ============================================================

export function analyzeSignalCombinations(
  filteredSummary: HistorySummaryRow[],
  minCount: number = 3
): Combination[] {
  const validRows = filteredSummary.filter(
    (r) => r.data_quality_status !== 'insufficient_data' && r.next_1d_return !== null
  );

  // 统计 2 信号组合
  const comboMap = new Map<string, { count: number; returns: number[] }>();

  for (const row of validRows) {
    const pairs = extractLabelCategoryPairs(row);
    const labels = pairs.map((p) => p.label).sort();
    if (labels.length < 2) continue;

    // 只取 2 信号组合
    for (let i = 0; i < labels.length - 1; i++) {
      for (let j = i + 1; j < labels.length; j++) {
        const key = `${labels[i]}+${labels[j]}`;
        if (!comboMap.has(key)) {
          comboMap.set(key, { count: 0, returns: [] });
        }
        const data = comboMap.get(key)!;
        data.count++;
        data.returns.push(row.next_1d_return!);
      }
    }
  }

  const combinations: Combination[] = [];
  for (const [key, data] of comboMap.entries()) {
    if (data.count < minCount) continue;
    const avgReturn = avg(data.returns);
    const winRate = ratio(
      data.returns.filter((r) => r > 0).length,
      data.count
    );
    combinations.push({
      labels: key.split('+'),
      count: data.count,
      avgNext1d: avgReturn,
      winRate,
    });
  }

  return combinations.sort((a, b) => (b.avgNext1d ?? 0) - (a.avgNext1d ?? 0));
}

// ============================================================
// 交易建议生成
// ============================================================

export function generateTradingRules(
  insights: { highValue: SignalInsight[]; lowValue: SignalInsight[] },
  combinations: Combination[],
  dateRange: { start: string; end: string }
): TradingRule[] {
  const rules: TradingRule[] = [];

  // 基于高价值信号生成做多建议（样本 >= 10）
  const reliableHigh = insights.highValue.filter((s) => s.count >= 10);
  if (reliableHigh.length > 0) {
    const best = reliableHigh[0];
    rules.push({
      type: 'long',
      conditions: reliableHigh.map((s) => s.label),
      stats: { avg: best.deltaPp, winRate: best.winRate, count: best.count },
      dateRange,
    });
  }

  // 基于高 Lift 的组合生成建议（样本 >= 8）
  const reliableCombos = combinations.filter((c) => c.count >= 8 && (c.avgNext1d ?? 0) > 0);
  for (const combo of reliableCombos.slice(0, 2)) {
    rules.push({
      type: 'long',
      conditions: combo.labels,
      stats: {
        avg: combo.avgNext1d ?? 0,
        winRate: combo.winRate ?? 0,
        count: combo.count,
      },
      dateRange,
    });
  }

  // 基于低价值信号生成谨慎提示
  const reliableLow = insights.lowValue.filter((s) => s.count >= 10);
  if (reliableLow.length > 0) {
    const worst = reliableLow[0];
    rules.push({
      type: 'caution',
      conditions: reliableLow.map((s) => s.label),
      stats: { avg: worst.deltaPp, winRate: worst.winRate, count: worst.count },
      dateRange,
    });
  }

  return rules;
}

// ============================================================
// 新增：历史分析优化相关函数
// ============================================================

/**
 * 计算组合协同效应
 */
export function deriveCombinationSynergy(
  combinations: Combination[],
  signals: SignalLiftRow[],
  options?: { minCount?: number }
): CombinationSynergy[] {
  const minCount = options?.minCount ?? 8;

  return combinations
    .filter((c) => c.count >= minCount && c.avgNext1d !== null)
    .map((c) => {
      // 找出组合内最强的单信号
      const singleSignals = signals.filter((s) =>
        c.labels.some((l) => s.label === l)
      );
      const bestSingle = singleSignals.reduce(
        (best, s) =>
          (s.avg_next_1d ?? -Infinity) > (best?.avg_next_1d ?? -Infinity)
            ? s
            : best,
        singleSignals[0]
      );

      const synergy =
        c.avgNext1d! - (bestSingle?.avg_next_1d ?? c.avgNext1d!);

      return {
        labels: c.labels,
        count: c.count,
        avgNext1d: c.avgNext1d!,
        winRate: c.winRate,
        synergy,
        bestSingleLabel: bestSingle?.label || c.labels[0],
      };
    })
    .filter((s) => s.synergy > 0)
    .sort((a, b) => b.synergy - a.synergy);
}

/**
 * 生成决策摘要
 */
export function deriveDecisionSummary(input: DecisionSummaryInput): DecisionSummary {
  const { coreMetrics, signalInsights, rollingMetrics, sampleDays } = input;

  // 默认结论
  let confidence: 'high' | 'medium' | 'low' = 'medium';
  let stance: 'active_watch' | 'cautious_watch' | 'wait' = 'cautious_watch';
  const riskPoints: string[] = [];
  const reasons: string[] = [];

  // 样本不足检查
  if (sampleDays < 20) {
    confidence = 'low';
    stance = 'wait';
    riskPoints.push(`有效样本仅 ${sampleDays} 天，建议观望`);
  } else if (sampleDays < 40) {
    confidence = 'medium';
    riskPoints.push(`样本天数 ${sampleDays} 天，结论仅供参考`);
  }

  // 高价值信号检查
  if (signalInsights.highValue.length === 0) {
    if (confidence !== 'low') {
      confidence = 'medium';
    }
    riskPoints.push('当前无明确高价值信号支持');
  } else {
    reasons.push(`发现 ${signalInsights.highValue.length} 个高价值信号`);
  }

  // 低价值信号检查
  if (signalInsights.lowValue.length > 0) {
    riskPoints.push(`存在 ${signalInsights.lowValue.length} 个需警惕信号`);
    // 如果有低价值信号，降级观察倾向（active_watch -> cautious_watch）
    if ((stance as string) === 'active_watch') {
      stance = 'cautious_watch';
    }
  }

  // 生成一句话结论
  let headline = '';
  if (stance === 'wait') {
    headline = '当前样本或信号不足以形成明确判断，建议观望';
  } else if (stance === 'cautious_watch') {
    headline = '历史规律存在一定警示信号，建议在积极信号出现后再做决策';
  } else {
    headline = '历史规律稳定且存在高价值信号支持，可积极关注';
  }

  return {
    confidence,
    stance,
    headline,
    riskPoints,
    reasons,
  };
}

/**
 * 生成交易观察建议
 */
export function deriveTradingPlaybook(input: TradingPlaybookInput): TradingPlaybook {
  const { decisionSummary, signalInsights, combinationSynergies, sampleDays } = input;

  const { confidence, stance } = decisionSummary;

  // 生成样本说明
  const sampleNote =
    sampleDays < 20
      ? `样本仅${sampleDays}天，结论可靠性低`
      : sampleDays < 40
        ? `样本${sampleDays}天，谨慎参考`
        : `样本${sampleDays}天，统计意义较强`;

  // 生成证据列表
  const evidence: string[] = [];
  if (signalInsights.highValue.length > 0) {
    evidence.push(
      `发现${signalInsights.highValue.length}个高价值信号：${signalInsights.highValue
        .slice(0, 2)
        .map((s) => formatSignalLabel(s.label))
        .join('、')}`
    );
  }
  if (combinationSynergies.length > 0) {
    evidence.push(`发现${combinationSynergies.length}组有效协同效应`);
  }

  // 生成触发条件
  const triggers: string[] = [];
  if (signalInsights.highValue.length > 0) {
    signalInsights.highValue.slice(0, 2).forEach((s) => {
      triggers.push(`出现「${formatSignalLabel(s.label)}」`);
    });
  }
  if (combinationSynergies.length > 0 && combinationSynergies[0]) {
    const combo = combinationSynergies[0];
    triggers.push(
      `同时出现「${combo.labels.map(formatSignalLabel).join('」+「')}」`
    );
  }

  // 生成反证条件
  const invalidations: string[] = [];
  if (signalInsights.lowValue.length > 0) {
    signalInsights.lowValue.slice(0, 2).forEach((s) => {
      invalidations.push(`出现「${formatSignalLabel(s.label)}」`);
    });
  }

  // 生成一句话总结
  let summary = '';
  if (stance === 'wait') {
    summary = '当前样本或信号条件不足，建议观望等待更明确的信号出现。';
  } else if (stance === 'cautious_watch') {
    summary =
      '历史规律存在一定警示信号，建议在积极信号出现后再做决策，当前以谨慎观察为主。';
  } else {
    summary = '历史规律稳定且存在高价值信号支持，可积极关注相关机会。';
  }

  return {
    stance,
    confidence,
    summary,
    evidence,
    triggers,
    invalidations,
    sampleNote,
  };
}

/**
 * 生成信号卡片的一句话结论
 */
export function deriveSignalCardConclusion(input: SignalCardConclusionInput): string {
  const { signal, kind, trend } = input;

  if (!trend) {
    return kind === 'high_value'
      ? '历史表现良好，但缺少近期趋势数据'
      : '历史表现偏弱，暂不做为强反证';
  }

  const { trend: trendStatus } = trend;

  // 高价值信号
  if (kind === 'high_value') {
    if (trendStatus === 'trend_improving') {
      return '近期表现增强，可作为重点观察信号';
    }
    if (trendStatus === 'trend_deteriorating') {
      return '全区间有效，但近期转弱，降级为观察';
    }
    return '历史表现稳定，可继续跟踪';
  }

  // 警惕信号
  if (trendStatus === 'trend_deteriorating') {
    return '近期仍在转弱，出现时优先降风险';
  }
  if (trendStatus === 'trend_improving') {
    return '历史偏弱但近期修复，暂不作为强反证';
  }
  return '历史表现偏弱，出现时保持警惕';
}

/**
 * 获取信号所属业务分组
 */
export function getSignalBusinessGroup(
  label: string,
  groups: BusinessGroup[]
): string | null {
  for (const group of groups) {
    if (group.signals.some((s) => s.label === label)) {
      return group.name;
    }
  }
  return null;
}

