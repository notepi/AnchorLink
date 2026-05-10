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
  linkage_analysis: LinkageAnalysis | null;
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
  valuation_percentile: number | null;  // 估值分位（0-100，仅 direct_peers 有意义）
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
  anchor_return?: number;  // 锚定标的涨跌幅（Volume类信号）
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
// 联动分析类型（linkage_analysis）
// ============================================================

export interface LinkageAnalysis {
  trade_date: string;
  anchor_symbol: string;
  status: string;
  windows: number[];
  partial_reason: string | null;
  pools: Record<string, PoolLinkage>;
}

export interface PoolLinkage {
  universe_id: string;
  status: string;
  avg_corr_20d: number | null;
  avg_beta_20d: number | null;
  avg_direction_consistency_20d: number | null;
  partial_reason: string | null;
  top_members: LinkageMember[];
  members: LinkageMember[];
}

export interface LinkageMember {
  universe_id: string;
  symbol: string;
  name: string;
  role: string;
  relevance: number;
  weight: number;
  corr_5d: number | null;
  corr_10d: number | null;
  corr_20d: number | null;
  beta_5d: number | null;
  beta_10d: number | null;
  beta_20d: number | null;
  direction_consistency_5d: number | null;
  direction_consistency_10d: number | null;
  direction_consistency_20d: number | null;
  observations: number;
  data_status: string;
  partial_reason: string | null;
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

// ============================================================
// 历史分析类型（history_*.csv）
// ============================================================

export interface HistorySummaryRow {
  date: string;
  anchor_return: number | null;
  direct_peers_median: number | null;
  industry_chain_median: number | null;
  theme_pool_median: number | null;
  trading_watchlist_median: number | null;
  relative_strength_vs_direct: number | null;
  relative_strength_vs_industry_chain: number | null;
  relative_strength_vs_theme: number | null;
  direct_up_ratio: number | null;
  chain_up_ratio: number | null;
  amount_expansion_ratio: number | null;
  moneyflow_positive_ratio: number | null;
  strongest_group: string | null;
  weakest_group: string | null;
  industry_beta: string | null;
  anchor_alpha: string | null;
  risk_level: string | null;
  signal_labels: string | null;
  signal_categories: string | null;
  signal_pairs: string | null;
  data_quality_status: string;
  next_1d_return: number | null;
  next_3d_return: number | null;
  next_5d_return: number | null;
  next_1d_excess_vs_chain: number | null;
  next_3d_excess_vs_chain: number | null;
  next_5d_excess_vs_chain: number | null;
}

export interface QuadrantStat {
  quadrant: string;
  count: number;
  avg_next_1d: number | null;
  avg_next_3d: number | null;
  avg_next_5d: number | null;
  avg_next_1d_excess: number | null;
  win_rate_1d: number | null;
  avg_relative_strength: number | null;
}

export interface SignalLiftRow {
  label: string;
  category: string;
  appearance_count: number;
  avg_next_1d: number | null;
  avg_next_3d: number | null;
  avg_next_5d: number | null;
  avg_next_1d_excess: number | null;
  win_rate_1d: number | null;
  baseline_avg_next_1d: number | null;
  baseline_win_rate_1d: number | null;
  avg_next_1d_delta_pp: number | null;
  lift_next_1d: number | null;
  lift_win_rate: number | null;
  min_count_passed: boolean;
}

export interface ExtremeDivergence {
  date: string;
  anchor_return: number | null;
  industry_chain_median: number | null;
  divergence: number;
  industry_beta: string | null;
  anchor_alpha: string | null;
  risk_level: string | null;
  signal_labels: string | null;
}

export interface RollingMetricRow {
  date: string;
  excess_5d: number | null;
  excess_10d: number | null;
  outperform_streak: number | null;
  beta_streak: number | null;
  theme_vs_core_streak: number | null;
  risk_high_streak: number | null;
}

export interface StateTransition {
  from_state: string;
  to_state: string;
  count: number;
  probability: number;
}

export interface EventPathRow {
  event_date: string;
  offset: number;
  date: string;
  anchor_return: number | null;
  chain_median: number | null;
  excess: number | null;
}

// ============================================================
// 信号洞察派生类型
// ============================================================

export interface SignalInsight {
  label: string;
  category: string;
  deltaPp: number;
  winRate: number;
  count: number;
  stabilityScore: number;
}

export interface BusinessGroup {
  name: string;
  description: string;
  signals: SignalLiftRow[];
}

export type TrendStatus = 'trend_improving' | 'trend_deteriorating' | 'trend_stable' | 'trend_insufficient';

export interface SignalTrend {
  label: string;
  trend: TrendStatus;
  recentDelta: number | null;
  historicalDelta: number | null;
}

export interface Combination {
  labels: string[];
  count: number;
  avgNext1d: number | null;
  winRate: number | null;
}

export interface TradingRule {
  type: 'long' | 'caution';
  conditions: string[];
  stats: { avg: number; winRate: number; count: number };
  dateRange: { start: string; end: string };
}

// 新增：历史分析优化相关类型
export interface CombinationSynergy {
  labels: string[];
  count: number;
  avgNext1d: number;
  winRate: number | null;
  synergy: number;
  bestSingleLabel: string;
}

export interface DecisionSummary {
  confidence: 'high' | 'medium' | 'low';
  stance: 'active_watch' | 'cautious_watch' | 'wait';
  headline: string;
  riskPoints: string[];
  reasons: string[];
}

export interface TradingPlaybook {
  stance: DecisionSummary['stance'];
  confidence: DecisionSummary['confidence'];
  summary: string;
  evidence: string[];
  triggers: string[];
  invalidations: string[];
  sampleNote: string;
}

// View Model types (re-exported from history-analysis)
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

// Input types for history analysis functions
export interface DecisionSummaryInput {
  coreMetrics: CoreMetrics;
  signalInsights: {
    highValue: SignalInsight[];
    lowValue: SignalInsight[];
  };
  combinationSynergies: CombinationSynergy[];
  rollingMetrics: RollingMetricRow[];
  sampleDays: number;
}

export interface TradingPlaybookInput {
  decisionSummary: DecisionSummary;
  signalInsights: {
    highValue: SignalInsight[];
    lowValue: SignalInsight[];
  };
  combinationSynergies: CombinationSynergy[];
  signalTrends: SignalTrend[];
  sampleDays: number;
  latestRolling: RollingMetricRow | null;
}

export interface SignalCardConclusionInput {
  signal: SignalInsight;
  kind: 'high_value' | 'caution';
  trend: SignalTrend | null;
}

// ============================================================
// 历史验证工作台后端视图（history_operator_playbook.json）
// ============================================================

export interface CounterIntuitiveSignal {
  label: string;
  display_label: string;
  category: string;
  appearance_count: number;
  avg_next_1d: number | null;
  win_rate_1d: number | null;
  avg_next_1d_delta_pp: number | null;
  intuitive_direction: 'positive' | 'negative' | 'neutral';
  actual_direction: 'positive' | 'negative' | 'neutral';
  degree: number;
  verdict: 'counter_intuitive_opportunity' | 'signal_trap';
  explanation: string;
}

export interface ConditionalSignalEffect {
  label: string;
  display_label: string;
  category: string;
  quadrant: string;
  quadrant_count: number;
  signal_in_quadrant_count: number;
  avg_next_1d_in_quadrant: number | null;
  win_rate_in_quadrant: number | null;
  avg_next_1d_delta_pp_vs_quadrant: number | null;
  overall_avg_next_1d: number | null;
  verdict: 'works_in_condition' | 'fails_in_condition' | 'insufficient';
}

export interface HistoryRegime {
  confidence: 'high' | 'medium' | 'low';
  status: 'stable' | 'weakening' | 'invalid';
  headline: string;
  reasons: string[];
  risk_points: string[];
  latest_rolling_date: string | null;
}

export interface OperatorSignalRole {
  label: string;
  display_label: string;
  category: string;
  business_tag: string;
  role: 'primary_trigger' | 'confirmation' | 'risk_invalidator' | 'context_only' | 'ignore';
  insight_type: 'counter_intuitive' | 'trap' | 'normal';
  priority: number;
  count: number;
  avg_next_1d: number | null;
  delta_pp: number | null;
  win_rate: number | null;
  trend: TrendStatus;
  best_condition_quadrant: string | null;
  conclusion: string;
  reason: string;
}

export interface OperatorConfirmationPair {
  labels: string[];
  display_labels: string[];
  count: number;
  avg_next_1d: number;
  win_rate: number | null;
  best_single_label: string;
  synergy: number;
  verdict: 'useful_confirmation' | 'no_incremental_edge';
  conclusion: string;
}

export interface OperatorPlaybook {
  stance: 'active_watch' | 'cautious_watch' | 'wait';
  headline: string;
  watch_for: string[];
  confirmations: string[];
  invalidations: string[];
  sample_note: string;
}

export interface OperatorHistoryView {
  as_of_date: string;
  date_range_start: string;
  date_range_end: string;
  sample_days: number;
  regime: HistoryRegime;
  playbook: OperatorPlaybook;
  signal_roles: OperatorSignalRole[];
  counter_intuitive_signals: CounterIntuitiveSignal[];
  signal_traps: CounterIntuitiveSignal[];
  conditional_effects: ConditionalSignalEffect[];
  confirmation_pairs: OperatorConfirmationPair[];
}

// ============================================================
// 历史性格画像（history_personality_profile.json）
// ============================================================

export interface ConditionEffect {
  quadrant: string;
  count: number;
  avg_next_1d: number | null;
  win_rate_1d: number | null;
  delta_pp_vs_quadrant: number | null;
}

export interface PersonalityPattern {
  label: string;
  display_label: string;
  category: string;
  pattern_kind: 'environment' | 'signal' | 'quadrant' | 'relationship' | 'event';
  habit_type: 'likes' | 'dislikes' | 'counter_intuitive' | 'trap' | 'context';
  count: number;
  avg_next_1d: number | null;
  avg_next_3d: number | null;
  avg_next_5d: number | null;
  avg_next_1d_excess: number | null;
  avg_next_1d_delta_pp: number | null;
  win_rate_1d: number | null;
  effect_score: number | null;
  significance: 'strong' | 'suggestive' | 'weak' | 'insufficient';
  confidence: 'high' | 'medium' | 'low';
  best_condition: ConditionEffect | null;
  worst_condition: ConditionEffect | null;
  explanation: string;
  source: 'signal_lift' | 'quadrant_stats' | 'conditional_signal_effects' | 'counter_intuitive' | 'event_study';
}

export interface PersonalitySummaryMetrics {
  baseline_win_rate_1d: number | null;
  median_excess_3d: number | null;
  median_adverse_3d_proxy: number | null;
  payoff_ratio: number | null;
  sharpe_like_ratio: number | null;
  signal_coverage_ratio: number | null;
}

export interface PersonalitySummary {
  headline: string;
  traits: string[];
  strongest_pattern_label: string | null;
  weakest_pattern_label: string | null;
  confidence: 'high' | 'medium' | 'low';
  generation_method: string;
}

export interface RelationshipPattern {
  relation: 'follows' | 'leads' | 'lags' | 'mean_reverts' | 'diverges' | 'unstable';
  confidence: 'high' | 'medium' | 'low';
  sample_count: number;
  evidence: string[];
  same_day_corr: number | null;
  anchor_leads_corr: number | null;
  anchor_lags_corr: number | null;
  avg_relative_strength: number | null;
  outperform_ratio: number | null;
  repair_after_underperform_ratio: number | null;
  continuation_after_outperform_ratio: number | null;
  stability: 'stable' | 'changed' | 'unstable' | 'insufficient';
}

export interface RelationshipProfile {
  anchor_vs_chain: RelationshipPattern;
  anchor_vs_theme: RelationshipPattern;
  anchor_vs_core: RelationshipPattern;
  anchor_vs_trading_watchlist: RelationshipPattern;
}

export interface PathPatternPoint {
  offset: number;
  anchor_return: number | null;
  chain_median: number | null;
  excess: number | null;
}

export interface PathPattern {
  event_label: string;
  count: number;
  avg_path: PathPatternPoint[];
  summary: string;
  confidence: 'high' | 'medium' | 'low';
}

export interface PersonalityStability {
  status: 'stable' | 'changed' | 'insufficient';
  recent_window_days: number;
  early_vs_recent_notes: string[];
}

export interface HistoryPersonalityProfile {
  as_of_date: string;
  date_range_start: string;
  date_range_end: string;
  sample_days: number;
  valid_sample_days: number;
  summary_metrics: PersonalitySummaryMetrics;
  personality_summary: PersonalitySummary;
  habit_patterns: PersonalityPattern[];
  counter_intuitive_patterns: PersonalityPattern[];
  trap_patterns: PersonalityPattern[];
  relationship_profile: RelationshipProfile;
  path_patterns: PathPattern[];
  stability: PersonalityStability;
  sample_warnings: string[];
}
