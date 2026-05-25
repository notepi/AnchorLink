/**
 * V2 评分系统数据类型
 */

export type Regime = 'mean_reverting' | 'trending' | 'transition';

export interface V2SignalBreakdown {
  signal: string;
  rawWeight: number;
  adjustedWeight: number;
  category: 'v1' | 'v2_new';
}

export interface V2TechnicalIndicators {
  rsi14: number | null;
  macdHist: number | null;
  stochK: number | null;
  bbPctb: number | null;
  adx14: number | null;
  atr14: number | null;
  squeezeOn: boolean | null;
}

export interface V2DailyResult {
  date: string;
  score: number;
  veto: boolean;
  regime: Regime;
  thresholdBuy: number;
  thresholdSell: number;
  signals: string[];
  signalBreakdown: V2SignalBreakdown[];
  kellyPosition: number | null;
  holdPeriodDays: number;
  technicalIndicators: V2TechnicalIndicators;
  next1dExcess: number | null;
  next1dAbs: number | null;
}

export interface V2StrategyStats {
  label: string;
  n: number;
  avg1dExc?: number;
  avg1dAbs?: number;
  winRateExc?: number;
  winRateAbs?: number;
  cumLogExc?: number;
  cumLogAbs?: number;
}

export interface V2StrategyResult {
  threshold: number;
  longDays: V2StrategyStats;
  shortDays: V2StrategyStats;
  neutralDays: { n: number };
  buyAndHold: V2StrategyStats;
}

export interface V2LatestRegime {
  regime: Regime;
  adx: number | null;
  thresholdBuy: number;
  thresholdSell: number;
  holdPeriodGuidance: string;
}

export interface V2ScoringData {
  generatedAt: string;
  trainWindow: number;
  regimeThresholds: Record<string, number>;
  strategyResults: Record<string, V2StrategyResult>;
  dailyResults: V2DailyResult[];
  latestRegime: V2LatestRegime;
}
