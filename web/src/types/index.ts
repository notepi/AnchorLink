// ============================================================
// AnchorLink TypeScript 类型定义
// 与 Python 数据模型对齐（src/output/models.py, src/signal/models.py）
// ============================================================

// ============================================================
// 行业快照类型（industry_snapshot.json）
// ============================================================

export interface IndustrySnapshot {
  anchor: AnchorInfo;
  as_of_date: string;
  data_quality: DataQuality;
  industry_state: IndustryState;
  anchor_position: AnchorPosition;
  group_rotation: GroupRotation;
  signals: Signal[];
  conclusion: Conclusion;
}

export interface AnchorInfo {
  symbol: string;
  name: string;
  themes: string[];
}

export interface DataQuality {
  status: 'ok' | 'partial' | 'insufficient_data';
  missing_fields: string[];
  insufficient_universes: string[];
}

export interface IndustryState {
  direct_peers_return_median: number | null;
  industry_chain_return_median: number | null;
  theme_pool_return_median: number | null;
  up_ratio: number | null;
  amount_expansion_ratio: number | null;
  moneyflow_positive_ratio: number | null;
}

export interface AnchorPosition {
  anchor_return: number;
  relative_strength_vs_direct_peers: number | null;
  relative_strength_vs_industry_chain: number | null;
  relative_strength_vs_theme_pool: number | null;
  return_rank: number | null;
  amount_rank: number | null;
  turnover_rank: number | null;
  moneyflow_rank: number | null;
  total_count: number | null;
}

export interface GroupRotation {
  strongest_group: string;
  weakest_group: string;
  group_ranking: string[];
  core_vs_theme_spread: number | null;
  core_vs_chain_spread: number | null;
  core_vs_trading_spread: number | null;
  group_medians: Record<string, number>;
}

export interface Signal {
  label: string;
  category: 'beta' | 'alpha' | 'volume' | 'rotation' | 'abnormal';
  confidence: 'high' | 'medium' | 'low';
  evidence: Evidence;
}

export interface Evidence {
  value: number;
  threshold: number;
  source_pool?: string;
  source_field?: string;
  secondary_value?: number;
  percentile?: number;
}

export interface Conclusion {
  industry_beta: 'positive' | 'neutral' | 'negative';
  anchor_alpha: 'positive' | 'neutral' | 'negative';
  risk_level: 'low' | 'medium' | 'high';
  summary: string;
  next_watch: string[];
}

// ============================================================
// Peer Matrix 类型（peer_matrix.csv）
// ============================================================

export interface PeerMatrixRow {
  universe: string;
  symbol: string;
  name: string;
  role: string;
  relevance: number;
  include_in_benchmark: boolean;
  include_in_ranking: boolean;
  pct_chg: number | null;
  amount: number | null;
  turnover_rate: number | null;
  fund_flow: number | null;
  return_rank: number | null;
  valuation_percentile: number | null;
}

// ============================================================
// 池子配置类型（pools.yaml）
// ============================================================

export interface PoolConfig {
  version: string;
  changelog: ChangelogEntry[];
  anchor: AnchorConfig;
  instruments: Instrument[];
  universes: Universe[];
  memberships: Membership[];
  reference_indices: ReferenceIndex[];
  data_source: string;
  lookback_days: number;
  event_keywords: EventKeywords;
}

export interface ChangelogEntry {
  date: string;
  change: string;
}

export interface AnchorConfig {
  symbol: string;
  name: string;
  reason: string;
  added_date: string;
}

export interface Instrument {
  symbol: string;
  name: string;
  market: string;
  exchange: string;
  fact_tags: string[];
}

export interface Universe {
  universe_id: string;
  display_name: string;
  purpose: string;
  can_be_benchmark: boolean;
  min_size: number;
  description: string;
}

export interface Membership {
  universe_id: string;
  symbol: string;
  role: string;
  relevance: number;
  weight: number;
  enabled: boolean;
  include_in_state?: boolean;
  include_in_benchmark: boolean;
  include_in_ranking: boolean;
  include_in_report: boolean;
  include_in_rotation?: boolean;
  reason: string;
  added_at: string;
  reviewed_at: string;
}

export interface ReferenceIndex {
  symbol: string;
  name: string;
}

export interface EventKeywords {
  company: string[];
  sector: string[];
}

// ============================================================
// 工具类型
// ============================================================

export type PoolType = 'direct_peers' | 'industry_chain' | 'theme_pool' | 'trading_watchlist';

export type SignalCategory = 'beta' | 'alpha' | 'volume' | 'rotation' | 'abnormal';

export type ConfidenceLevel = 'high' | 'medium' | 'low';

export type BetaStatus = 'positive' | 'neutral' | 'negative';

export type RiskLevel = 'low' | 'medium' | 'high';

export interface PoolMember {
  symbol: string;
  name: string;
  pct_chg: number | null;
  role: string;
  relevance: number;
  universe_id: PoolType;
}

export interface DateInfo {
  date: string;
  hasSnapshot: boolean;
  hasMatrix: boolean;
}
