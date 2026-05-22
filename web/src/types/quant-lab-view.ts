/**
 * 量化实验室视图类型定义
 * 对应 3 个数据源：
 * - composite_signal_backtest.json
 * - history_deep_quant_analysis.json
 * - history_2nd_order_analysis.json (alphaSignalRank)
 */

// ── 通用 ──────────────────────────────────────────────────────────────────

export interface StatBlock {
  n: number;
  avg: number;
  wr: number;
  p50: number;
  std?: number;
}

// ── composite_signal_backtest.json ────────────────────────────────────────

export interface BacktestThresholds {
  excess_5d_p15: number;
  excess_5d_p85: number;
  excess_10d_p15: number;
  excess_10d_p70: number;
  excess_10d_p85: number;
}

export interface SignalWeights {
  buy: Record<string, number>;
  sell: Record<string, number>;
}

export interface LongDaysStats {
  n: number;
  avg_1d_abs: number;
  avg_1d_exc: number;
  win_rate_abs: number;
  win_rate_exc: number;
  avg_3d_abs: number;
  avg_3d_exc: number;
  cum_log_abs: number;
  cum_log_exc: number;
}

export interface ShortDaysStats {
  n: number;
  avg_1d_abs: number;
  avg_1d_exc: number;
  win_rate_abs: number;
}

export interface BuyAndHoldStats {
  n: number;
  avg_1d_abs: number;
  avg_1d_exc: number;
  win_rate_abs: number;
  cum_log_abs: number;
  cum_log_exc: number;
}

export interface ThresholdResult {
  threshold: number;
  long_days: LongDaysStats;
  short_days: ShortDaysStats;
  neutral_days: { n: number };
  buy_and_hold: BuyAndHoldStats;
}

export interface DailyResult {
  date: string;
  score: number;
  veto: boolean;
  signals: string[];
  next_1d_return: number | null;
  next_1d_excess: number | null;
}

export interface CompositeBacktest {
  generatedAt: string;
  thresholds: BacktestThresholds;
  signal_weights: SignalWeights;
  strategy_results_by_threshold: Record<string, ThresholdResult>;
  daily_results: DailyResult[];
}

// ── history_deep_quant_analysis.json ──────────────────────────────────────

// M: 均值回归
export interface DistributionStat {
  n: number;
  mean: number;
  std: number;
  t_stat: number;
  significant_vs_zero: boolean;
}

export interface AutocorrDecay {
  lag1: number | null;
  lag5: number | null;
  lag10: number | null;
  lag20: number | null;
  lag30: number | null;
  half_life_days: number | null;
}

export interface ExtremeBucket {
  n: number;
  abs_1d: StatBlock;
  abs_3d: StatBlock;
  abs_5d: StatBlock;
  exc_1d: StatBlock;
  exc_3d: StatBlock;
  exc_5d: StatBlock;
}

export interface ExtremeReversal {
  thresholds: { p15: number; p30: number; p70: number; p85: number };
  buckets: Record<string, ExtremeBucket>;
}

export interface DeltaQuintile {
  quintile: number;
  label: string;
  deltaRange: [number, number];
  n: number;
  abs1d: StatBlock;
  exc1d: StatBlock;
}

export interface DeltaMomentum {
  quintiles: DeltaQuintile[];
  pearsonR_abs: number | null;
  pearsonR_exc: number | null;
}

export interface MeanReversionAnalysis {
  distributionStats: {
    excess_5d: DistributionStat;
    excess_10d: DistributionStat;
  };
  autocorrelationDecay: {
    excess_5d: AutocorrDecay;
    excess_10d: AutocorrDecay;
  };
  extremeReversal: {
    by_excess_5d: ExtremeReversal;
    by_excess_10d: ExtremeReversal;
  };
  deltaMomentum: DeltaMomentum;
}

// N: 行业联动
export interface PoolStats {
  label: string;
  fullSampleCorr: number | null;
  corr20d_stats: { n: number; mean: number | null; min: number | null; max: number | null; p15: number | null; p85: number | null };
  corr60d_stats: { n: number; mean: number | null; min: number | null; max: number | null };
}

export interface PoolDecoupling {
  label: string;
  p15_threshold: number;
  p85_threshold: number;
  'decoupled(P15-)': { n: number; abs1d: StatBlock; exc1d: StatBlock; abs3d: StatBlock; exc3d: StatBlock; abs5d?: StatBlock; exc5d?: StatBlock };
  'coupled(P85+)': { n: number; abs1d: StatBlock; exc1d: StatBlock; abs3d: StatBlock; exc3d: StatBlock; abs5d?: StatBlock; exc5d?: StatBlock };
}

export interface PoolLeadLag {
  label: string;
  buckets: Record<string, { n: number; deltaRange: [number, number]; next1d_exc: StatBlock }>;
}

export interface PoolLinkageAnalysis {
  poolDistribution: Record<string, PoolStats>;
  decouplingSignal: Record<string, PoolDecoupling>;
  dispersion: {
    buckets: Record<string, { n: number; dispersionRange: [number, number]; next1d_exc: StatBlock }>;
    pearsonR: number | null;
  };
  correlationLeadLag: Record<string, PoolLeadLag>;
}

// P: 机器学习
export interface MLQuintile {
  quintile: number;
  predRange: [number, number];
  n: number;
  actual_exc1d: StatBlock;
  direction_hit_rate: number | null;
}

export interface MLFeatureImportance {
  feature: string;
  importance: number;
}

export interface MLModelResult {
  test_samples: number;
  direction_accuracy: number;
  pearson_r: number | null;
  mae: number;
  quintile_test: MLQuintile[];
  top_features: MLFeatureImportance[];
}

export type MLAnalysis = Record<string, MLModelResult>;

// 顶层
export interface DeepQuantAnalysis {
  generatedAt: string;
  M_excessMeanReversion: MeanReversionAnalysis;
  N_poolLinkage: PoolLinkageAnalysis;
  P_machineLearning: MLAnalysis;
}

// ── history_2nd_order_analysis.json (alphaSignalRank only) ────────────────

export type SignalType = '纯Alpha（绝对+超额均正）' | '隐藏Alpha（超额正但绝对弱）' | '负向信号（绝对+超额均负）' | '中性' | string;

export interface AlphaSignalRow {
  signal: string;
  n: number;
  avgAbs1d: number;
  avgExc1d: number;
  absLift: number;
  excLift: number;
  avgAbs3d: number;
  avgExc3d: number;
  avgAbs5d: number;
  avgExc5d: number;
  wr1d: number;
  wrExc1d: number;
  signalType: SignalType;
}

export interface SecondOrderAnalysis {
  generatedAt: string;
  alphaSignalRank: AlphaSignalRow[];
  // 其他字段不在此页面使用
}

// ── 顶层视图 ──────────────────────────────────────────────────────────────

export interface QuantLabView {
  backtest: CompositeBacktest;
  deepQuant: DeepQuantAnalysis;
  secondOrder: SecondOrderAnalysis;
}
