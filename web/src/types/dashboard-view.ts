/**
 * 历史分析页面 统一数据契约 Schema
 * 所有数据访问必须通过此契约，禁止直接调用旧数据接口
 * 版本：v1.0
 * 生成时间：2026-05-11
 * 字段数量：187个显示字段 + 派生计算字段
 */

// ==============================
// 基础类型定义
// ==============================

/** 四象限状态类型 */
export type QuadrantState =
  | 'positive+positive'  // 产业链强+个股强
  | 'positive+neutral'   // 产业链强+个股中
  | 'positive+negative'  // 产业链强+个股弱
  | 'neutral+positive'   // 产业链中+个股强
  | 'neutral+neutral'    // 产业链中+个股中
  | 'neutral+negative'   // 产业链中+个股弱
  | 'negative+positive'  // 产业链弱+个股强
  | 'negative+neutral'   // 产业链弱+个股中
  | 'negative+negative'; // 产业链弱+个股弱

/** 行业Beta状态 */
export type BetaState = 'positive' | 'neutral' | 'negative';

/** 个股Alpha状态 */
export type AlphaState = 'positive' | 'neutral' | 'negative';

/** 风险等级 */
export type RiskLevel = 'low' | 'medium' | 'high';

/** 信号类型 */
export type SignalType = 'beta' | 'alpha' | 'volume' | 'rotation' | 'abnormal';

/** 趋势状态 */
export type TrendStatus = 'trend_improving' | 'trend_deteriorating' | 'trend_stable' | 'trend_insufficient';

/** 性格模式类型 */
export type HabitType = 'likes' | 'dislikes' | 'counter_intuitive' | 'trap' | 'context';

/** 关系类型 */
export type RelationshipType = 'follows' | 'leads' | 'lags' | 'mean_reverts' | 'diverges' | 'unstable';

/** 置信度等级 */
export type ConfidenceLevel = 'high' | 'medium' | 'low';

/** 操作建议倾向 */
export type StanceType = 'active_watch' | 'cautious_watch' | 'wait';

/** 信号角色类型 */
export type SignalRoleType = 'primary_trigger' | 'confirmation' | 'risk_invalidator' | 'context_only' | 'ignore';

/** 信号结论类型 */
export type SignalVerdictType = 'works_in_condition' | 'fails_in_condition' | 'insufficient';

/** 组合结论类型 */
export type CombinationVerdictType = 'useful_confirmation' | 'no_incremental_edge';

/** 制度状态类型 */
export type RegimeStatusType = 'stable' | 'weakening' | 'invalid';

/** 模式显著性 */
export type SignificanceLevel = 'strong' | 'suggestive' | 'weak' | 'insufficient';

// ==============================
// 子结构类型定义
// ==============================

/** 页面元数据 */
export interface Meta {
  /** 分析日期范围 */
  dateRange: string;
  /** 数据更新时间 */
  dataUpdateTime: string;
  /** 标的名称 */
  stockName: string;
  /** 标的代码 */
  stockCode: string;
  /** 样本天数 */
  sampleDays: number;
  /** 有效样本天数 */
  validSampleDays: number;
}

/** 筛选配置 */
export interface Filter {
  /** 筛选起始日期 */
  startDate: string;
  /** 筛选结束日期 */
  endDate: string;
  /** 筛选信号类别 */
  signalCategory: 'all' | 'preference' | 'avoid' | 'counter_intuitive' | 'trap';
}

/** 四象限统计 */
export interface QuadrantStat {
  /** 象限标识 */
  quadrant: QuadrantState;
  /** 象限中文名称 */
  quadrantName: string;
  /** 样本天数 */
  count: number;
  /** 次日平均收益 */
  avgNext1d: number | null;
  /** 3日平均收益 */
  avgNext3d: number | null;
  /** 5日平均收益 */
  avgNext5d: number | null;
  /** 次日超额收益相对行业 */
  avgNext1dExcess: number | null;
  /** 次日胜率 */
  winRate1d: number | null;
  /** 平均相对强度 */
  avgRelativeStrength: number | null;
}

/** 核心指标 */
export interface CoreMetrics {
  /** 样本收益统计 */
  sampleReturn: {
    /** 日均收益 */
    avgDailyReturn: number | null;
    /** 中位数收益 */
    medianReturn: number | null;
    /** 正收益占比 */
    positiveRatio: number | null;
  };
  /** 相对行业统计 */
  relativeToIndustry: {
    /** 行业日均中位数 */
    avgChainMedian: number | null;
    /** 日均当日超额 */
    avgDailyExcess: number | null;
    /** 跑赢行业占比 */
    outperformRatio: number | null;
  };
  /** 场景质量统计 */
  scenarioQuality: {
    /** 最佳象限 */
    bestQuadrant: QuadrantStat | null;
    /** 最差象限 */
    worstQuadrant: QuadrantStat | null;
    /** 有效象限数量 */
    validQuadrantCount: number;
  };
  /** 事件风险统计 */
  eventRisk: {
    /** 极端背离次数 */
    divergenceCount: number;
    /** 最大正背离 */
    maxPositiveDivergence: number | null;
    /** 最大负背离 */
    maxNegativeDivergence: number | null;
  };
}

/** 样本内结论 */
export interface Conclusion {
  /** 样本天数 */
  sampleDays: number;
  /** 日期范围 */
  dateRange: { start: string; end: string };
  /** 最佳象限 */
  bestQuadrant: QuadrantStat | null;
  /** 最差象限 */
  worstQuadrant: QuadrantStat | null;
  /** 均值回归统计 */
  meanReversion: {
    /** 跑赢后次日反转率 */
    outperformThenReverseRate: number | null;
    /** 跑输后次日反转率 */
    underperformThenReverseRate: number | null;
  };
  /** 警告文案 */
  warning: string;
}

/** 信号表现 */
export interface SignalLift {
  /** 信号标识 */
  label: string;
  /** 信号显示名称 */
  displayLabel: string;
  /** 信号类别 */
  category: string;
  /** 出现次数 */
  appearanceCount: number;
  /** 次日平均收益 */
  avgNext1d: number | null;
  /** 3日平均收益 */
  avgNext3d: number | null;
  /** 5日平均收益 */
  avgNext5d: number | null;
  /** 次日超额收益 */
  avgNext1dExcess: number | null;
  /** 次日胜率 */
  winRate1d: number | null;
  /** 基线次日平均收益 */
  baselineAvgNext1d: number | null;
  /** 基线次日胜率 */
  baselineWinRate1d: number | null;
  /** 次日收益增量相对基线 */
  avgNext1dDeltaPp: number | null;
  /** 次日收益提升率 */
  liftNext1d: number | null;
  /** 胜率提升率 */
  liftWinRate: number | null;
  /** 是否满足最小样本量 */
  minCountPassed: boolean;
  /** 信号趋势 */
  trend?: TrendStatus;
  /** 近期增量 */
  recentDelta?: number | null;
  /** 历史增量 */
  historicalDelta?: number | null;
}

/** 极端背离事件 */
export interface ExtremeDivergence {
  /** 事件日期 */
  date: string;
  /** 个股收益 */
  anchorReturn: number | null;
  /** 行业中位数收益 */
  industryChainMedian: number | null;
  /** 背离幅度 */
  divergence: number;
  /** 行业Beta状态 */
  industryBeta: BetaState | null;
  /** 个股Alpha状态 */
  anchorAlpha: AlphaState | null;
  /** 风险等级 */
  riskLevel: RiskLevel | null;
  /** 信号标签 */
  signalLabels: string | null;
  /** T+1收益 */
  t1Return: number | null;
  /** T+3收益 */
  t3Return: number | null;
  /** T+1超额收益 */
  t1Excess: number | null;
  /** T+3超额收益 */
  t3Excess: number | null;
}

/** 事件路径点 */
export interface EventPathPoint {
  /** 事件日期 */
  eventDate: string;
  /** 偏移天数 */
  offset: number;
  /** 具体日期 */
  date: string;
  /** 个股收益 */
  anchorReturn: number | null;
  /** 行业中位数收益 */
  chainMedian: number | null;
  /** 超额收益 */
  excess: number | null;
}

/** 滚动指标 */
export interface RollingMetric {
  /** 日期 */
  date: string;
  /** 当日收盘价 */
  price: number | null;
  /** 5日超额 */
  excess5d: number | null;
  /** 10日超额 */
  excess10d: number | null;
  /** 跑赢连胜天数 */
  outperformStreak: number | null;
  /** Beta连胜天数 */
  betaStreak: number | null;
  /** 主题相对核心连胜天数 */
  themeVsCoreStreak: number | null;
  /** 高风险连胜天数 */
  riskHighStreak: number | null;
}

/** 状态转移 */
export interface StateTransition {
  /** 来源状态 */
  fromState: QuadrantState;
  /** 目标状态 */
  toState: QuadrantState;
  /** 来源状态中文标签 */
  fromStateLabel: string;
  /** 目标状态中文标签 */
  toStateLabel: string;
  /** 出现次数 */
  count: number;
  /** 转移概率 */
  probability: number;
  /** 目标状态次日平均收益 */
  avgNext1dReturn: number | null;
  /** 目标状态3日平均收益 */
  avgNext3dReturn: number | null;
  /** 目标状态5日平均收益 */
  avgNext5dReturn: number | null;
  /** 目标状态次日胜率 */
  winRate1d: number | null;
  /** 目标状态3日胜率 */
  winRate3d: number | null;
  /** 目标状态5日胜率 */
  winRate5d: number | null;
}

/** 信号组合 */
export interface SignalCombination {
  /** 信号标签列表 */
  labels: string[];
  /** 显示名称列表 */
  displayLabels: string[];
  /** 出现次数 */
  count: number;
  /** 次日平均收益 */
  avgNext1d: number | null;
  /** 次日胜率 */
  winRate: number | null;
}

/** 组合协同效应 */
export interface CombinationSynergy {
  /** 信号标签列表 */
  labels: string[];
  /** 显示名称列表 */
  displayLabels: string[];
  /** 出现次数 */
  count: number;
  /** 次日平均收益 */
  avgNext1d: number;
  /** 次日胜率 */
  winRate: number | null;
  /** 协同增量 */
  synergy: number;
  /** 最佳单信号标签 */
  bestSingleLabel: string;
}

/** 决策摘要 */
export interface DecisionSummary {
  /** 置信度 */
  confidence: ConfidenceLevel;
  /** 操作倾向 */
  stance: StanceType;
  /** 结论标题 */
  headline: string;
  /** 风险点列表 */
  riskPoints: string[];
  /** 理由列表 */
  reasons: string[];
}

/** 交易观察建议 */
export interface TradingPlaybook {
  /** 操作倾向 */
  stance: StanceType;
  /** 置信度 */
  confidence: ConfidenceLevel;
  /** 结论摘要 */
  summary: string;
  /** 证据列表 */
  evidence: string[];
  /** 触发条件列表 */
  triggers: string[];
  /** 失效条件列表 */
  invalidations: string[];
  /** 样本说明 */
  sampleNote: string;
}

/** 当前映射信息 */
export interface CurrentMapping {
  /** 当前映射日期 */
  date: string;
  /** 当前状态描述 */
  state: string;
  /** 当前状态标签列表 */
  tags: string[];
  /** 相似样本数量 */
  similarSampleCount: number;
  /** 行业Beta状态 */
  industryBeta: BetaState;
  /** 个股Alpha状态 */
  anchorAlpha: AlphaState;
  /** 风险等级 */
  riskLevel: RiskLevel;
  /** 最强板块 */
  strongestGroup: string;
  /** 最弱板块 */
  weakestGroup: string;
  /** 信号标签列表 */
  signalLabels: string[];
}

/** 路径标签 */
export type PathLabelType =
  | 'strong_rise'
  | 'pullback_after_rise'
  | 'continue_fall'
  | 'weak_repair'
  | 'range_bound'
  | 'disagreement'
  | 'unknown';

/** 窗口统计 */
export interface WindowStat {
  /** 窗口类型 */
  window: '1d' | '3d' | '5d';
  /** 平均收益 */
  avgReturn: number | null;
  /** 胜率 */
  winRate: number | null;
  /** 平均超额收益 */
  avgExcess: number | null;
}

/** 相似历史案例 */
export interface SimilarCase {
  /** 案例日期 */
  date: string;
  /** 案例状态 */
  state: string;
  /** 当日收盘价 */
  price: number | null;
  /** T+1收益 */
  next1dReturn: number | null;
  /** T+3收益 */
  next3dReturn: number | null;
  /** T+5收益 */
  next5dReturn: number | null;
  /** 相似度 0-1 */
  similarity: number;
  /** 匹配状态字段列表 */
  matchingStates: string[];
  /** 匹配信号标签列表 */
  matchingSignals: string[];
}

/** 单日映射索引条目 */
export interface DateEntry {
  /** 当日映射 */
  currentMapping: CurrentMapping;
  /** 相似案例 */
  similarCases: SimilarCase[];
  /** 窗口统计 */
  windowStats: WindowStat[];
  /** 路径标签 */
  pathLabel: PathLabelType;
  /** 按日变化的卡片指标 */
  cards: Array<{
    title?: string;
    label?: string;
    value: string | number;
    badge?: string;
    description: string;
  }>;
}

/** 状态转移摘要 */
export interface TransitionSummary {
  /** 转移路径描述 */
  path: string;
  /** 转移概率 */
  probability: number;
  /** 样本次数 */
  count: number;
  /** 平均收益 */
  avgReturn: number | null;
}

/** 信号趋势 */
export interface SignalTrend {
  /** 信号标签 */
  label: string;
  /** 趋势状态 */
  trend: TrendStatus;
  /** 近期增量 */
  recentDelta: number | null;
  /** 历史增量 */
  historicalDelta: number | null;
}

/** 反直觉信号 */
export interface CounterIntuitiveSignal {
  /** 信号标签 */
  label: string;
  /** 显示名称 */
  displayLabel: string;
  /** 信号类别 */
  category: string;
  /** 出现次数 */
  appearanceCount: number;
  /** 次日平均收益 */
  avgNext1d: number | null;
  /** 次日胜率 */
  winRate1d: number | null;
  /** 次日收益增量相对基线 */
  avgNext1dDeltaPp: number | null;
  /** 直觉预期方向 */
  intuitiveDirection: 'positive' | 'negative' | 'neutral';
  /** 实际方向 */
  actualDirection: 'positive' | 'negative' | 'neutral';
  /** 偏差程度 */
  degree: number;
  /** 结论类型 */
  verdict: 'counter_intuitive_opportunity' | 'signal_trap';
  /** 解释说明 */
  explanation: string;
}

/** 条件信号效应 */
export interface ConditionalSignalEffect {
  /** 信号标签 */
  label: string;
  /** 显示名称 */
  displayLabel: string;
  /** 信号类别 */
  category: string;
  /** 象限 */
  quadrant: QuadrantState;
  /** 象限名称 */
  quadrantName: string;
  /** 象限样本数 */
  quadrantCount: number;
  /** 象限内信号出现次数 */
  signalInQuadrantCount: number;
  /** 象限内信号次日平均收益 */
  avgNext1dInQuadrant: number | null;
  /** 象限内信号胜率 */
  winRateInQuadrant: number | null;
  /** 相对象限平均收益增量 */
  avgNext1dDeltaPpVsQuadrant: number | null;
  /** 全量样本次日平均收益 */
  overallAvgNext1d: number | null;
  /** 结论 */
  verdict: SignalVerdictType;
}

/** 制度判断 */
export interface Regime {
  /** 置信度 */
  confidence: ConfidenceLevel;
  /** 状态 */
  status: RegimeStatusType;
  /** 结论标题 */
  headline: string;
  /** 理由列表 */
  reasons: string[];
  /** 风险点列表 */
  riskPoints: string[];
  /** 最新滚动日期 */
  latestRollingDate: string | null;
}

/** 信号角色 */
export interface OperatorSignalRole {
  /** 信号标签 */
  label: string;
  /** 显示名称 */
  displayLabel: string;
  /** 信号类别 */
  category: string;
  /** 业务标签 */
  businessTag: string;
  /** 角色类型 */
  role: SignalRoleType;
  /** 洞察类型 */
  insightType: 'counter_intuitive' | 'trap' | 'normal';
  /** 优先级 */
  priority: number;
  /** 出现次数 */
  count: number;
  /** 次日平均收益 */
  avgNext1d: number | null;
  /** 收益增量 */
  deltaPp: number | null;
  /** 胜率 */
  winRate: number | null;
  /** 趋势 */
  trend: TrendStatus;
  /** 最佳条件象限 */
  bestConditionQuadrant: string | null;
  /** 结论 */
  conclusion: string;
  /** 理由 */
  reason: string;
}

/** 确认组合 */
export interface OperatorConfirmationPair {
  /** 信号标签列表 */
  labels: string[];
  /** 显示名称列表 */
  displayLabels: string[];
  /** 出现次数 */
  count: number;
  /** 次日平均收益 */
  avgNext1d: number;
  /** 胜率 */
  winRate: number | null;
  /** 最佳单信号标签 */
  bestSingleLabel: string;
  /** 协同增量 */
  synergy: number;
  /** 结论 */
  verdict: CombinationVerdictType;
  /** 结论描述 */
  conclusion: string;
}

/** 操作手册 */
export interface OperatorPlaybook {
  /** 操作倾向 */
  stance: StanceType;
  /** 结论标题 */
  headline: string;
  /** 观察要点列表 */
  watch: string[];
  /** 确认条件列表 */
  confirm: string[];
  /** 失效条件列表 */
  failure: string[];
  /** 样本约束 */
  constraint: string;
}

/** 条件效应 */
export interface ConditionEffect {
  /** 象限 */
  quadrant: string;
  /** 样本数 */
  count: number;
  /** 次日平均收益 */
  avgNext1d: number | null;
  /** 次日胜率 */
  winRate1d: number | null;
  /** 相对象限收益增量 */
  deltaPpVsQuadrant: number | null;
}

/** 性格模式 */
export interface PersonalityPattern {
  /** 信号标签 */
  label: string;
  /** 显示名称 */
  displayLabel: string;
  /** 类别 */
  category: string;
  /** 模式类型 */
  patternKind: 'environment' | 'signal' | 'quadrant' | 'relationship' | 'event';
  /** 习惯类型 */
  habitType: HabitType;
  /** 出现次数 */
  count: number;
  /** 次日平均收益 */
  avgNext1d: number | null;
  /** 3日平均收益 */
  avgNext3d: number | null;
  /** 5日平均收益 */
  avgNext5d: number | null;
  /** 次日超额收益 */
  avgNext1dExcess: number | null;
  /** 次日收益增量相对基线 */
  avgNext1dDeltaPp: number | null;
  /** 次日胜率 */
  winRate1d: number | null;
  /** 效应分数 */
  effectScore: number | null;
  /** 显著性 */
  significance: SignificanceLevel;
  /** 置信度 */
  confidence: ConfidenceLevel;
  /** 最佳条件 */
  bestCondition: ConditionEffect | null;
  /** 最差条件 */
  worstCondition: ConditionEffect | null;
  /** 解释说明 */
  explanation: string;
  /** 数据来源 */
  source: 'signal_lift' | 'quadrant_stats' | 'conditional_signal_effects' | 'counter_intuitive' | 'event_study';
}

/** 性格摘要指标 */
export interface PersonalitySummaryMetrics {
  /** 基线次日胜率 */
  baselineWinRate1d: number | null;
  /** 3日超额中位数 */
  medianExcess3d: number | null;
  /** 3日不利中位数代理 */
  medianAdverse3dProxy: number | null;
  /** 盈亏比 */
  payoffRatio: number | null;
  /** 类似夏普比率 */
  sharpeLikeRatio: number | null;
  /** 信号覆盖率 */
  signalCoverageRatio: number | null;
  /** 信息比率（相对板块超额收益的稳定性） */
  informationRatio: number | null;
  /** 单日期望值（胜率×平均赚 - 败率×平均亏） */
  expectancy1d: number | null;
}

/** 性格摘要 */
export interface PersonalitySummary {
  /** 结论标题 */
  headline: string;
  /** 特征标签列表 */
  traits: string[];
  /** 最强模式标签 */
  strongestPatternLabel: string | null;
  /** 最弱模式标签 */
  weakestPatternLabel: string | null;
  /** 置信度 */
  confidence: ConfidenceLevel;
  /** 生成方法说明 */
  generationMethod: string;
}

/** 关系模式 */
export interface RelationshipPattern {
  /** 关系类型 */
  relation: RelationshipType;
  /** 置信度 */
  confidence: ConfidenceLevel;
  /** 样本数 */
  sampleCount: number;
  /** 证据列表 */
  evidence: string[];
  /** 当日相关性 */
  sameDayCorr: number | null;
  /** 个股领先相关性 */
  anchorLeadsCorr: number | null;
  /** 个股滞后相关性 */
  anchorLagsCorr: number | null;
  /** 平均相对强度 */
  avgRelativeStrength: number | null;
  /** 跑赢比例 */
  outperformRatio: number | null;
  /** 跑输后修复比例 */
  repairAfterUnderperformRatio: number | null;
  /** 跑赢后延续比例 */
  continuationAfterOutperformRatio: number | null;
  /** 稳定性 */
  stability: 'stable' | 'changed' | 'unstable' | 'insufficient';
}

/** 关系画像 */
export interface RelationshipProfile {
  /** 相对行业产业链关系 */
  anchorVsChain: RelationshipPattern;
  /** 相对主题池关系 */
  anchorVsTheme: RelationshipPattern;
  /** 相对核心池关系 */
  anchorVsCore: RelationshipPattern;
  /** 相对交易观察池关系 */
  anchorVsTradingWatchlist: RelationshipPattern;
}

/** 路径模式点 */
export interface PathPatternPoint {
  /** 偏移天数 */
  offset: number;
  /** 个股收益 */
  anchorReturn: number | null;
  /** 行业中位数收益 */
  chainMedian: number | null;
  /** 超额收益 */
  excess: number | null;
}

/** 路径模式 */
export interface PathPattern {
  /** 事件标签 */
  eventLabel: string;
  /** 出现次数 */
  count: number;
  /** 平均路径 */
  avgPath: PathPatternPoint[];
  /** 模式总结 */
  summary: string;
  /** 置信度 */
  confidence: ConfidenceLevel;
}

/** 性格稳定性 */
export interface PersonalityStability {
  /** 状态 */
  status: 'stable' | 'changed' | 'insufficient';
  /** 近期窗口天数 */
  recentWindowDays: number;
  /** 早期和近期差异说明列表 */
  earlyVsRecentNotes: string[];
}

/** 转移判断 */
export interface TransitionVerdict {
  /** 判断标题 */
  title: string;
  /** 判断描述 */
  description: string;
  /** 观察要点列表 */
  watchPoints: string[];
}

/** 转移路径排名 */
export interface RankedPath {
  /** 排名 */
  rank: number;
  /** 来源状态 */
  fromState: QuadrantState;
  /** 目标状态 */
  toState: QuadrantState;
  /** 来源状态中文标签 */
  fromStateLabel: string;
  /** 目标状态中文标签 */
  toStateLabel: string;
  /** 转移概率 */
  probability: number;
  /** 样本数 */
  count: number;
  /** 3日平均收益 */
  avgReturn3d: number | null;
  /** 3日胜率 */
  winRate3d: number | null;
}

// ==============================
// 顶层契约定义
// ==============================

export interface DashboardView {
  /** 页面元数据 */
  meta: Meta;

  /** 筛选配置 */
  filter: Filter;

  /** 核心摘要数据 */
  summary: {
    /** 当前映射信息 */
    currentMapping: CurrentMapping;
    /** 路径标签 */
    pathLabel: PathLabelType;
    /** 迁移判断 */
    transitionVerdict: TransitionVerdict;
    /** 稳定性结论 */
    stabilityVerdict: 'stable' | 'changed' | 'insufficient';
    /** 性格档案 */
    profile: {
      /** 性格环形图数据 */
      donutData: Record<HabitType, number>;
      /** 性格标签 */
      tags: string[];
      /** 档案标题 */
      title: string;
      /** 档案描述 */
      description: string;
    };
  };

  /** 指标卡片数据 */
  cards: Array<{
    /** 卡片标题/标签 */
    title?: string;
    label?: string;
    /** 卡片值 */
    value: string | number;
    /** 卡片徽章 */
    badge?: string;
    /** 卡片描述 */
    description: string;
  }>;

  /** 矩阵/热力图数据 */
  mapData: {
    /** 迁移热力矩阵数据 */
    transitionMatrix: Record<QuadrantState, Record<QuadrantState, number>>;
    /** 信号标记数据 */
    signalMarks: Array<{
      date: string;
      signalName: string;
      signalType: SignalType;
      return: number;
    }>;
    /** 信号轨道数据 */
    signalLanes: Record<string, boolean[]>;
  };

  /** 趋势/时间轴数据 */
  trends: {
    /** 滚动超额收益趋势数据 */
    excessReturn: RollingMetric[];
    /** 跟随偏离趋势数据 */
    followDeviation: Array<{
      date: string;
      anchor: number | null;
      industry: number | null;
      excess: number | null;
      deviation: number | null;
    }>;
    /** 信号时间轴数据 */
    signalTimeline: Array<{
      date: string;
      price: number | null;
      return: number | null;
      signals: string[];
      groups: {
        pref: string[];
        avoid: string[];
        contra: string[];
        trap: string[];
      };
    }>;
    /** 路径模式特征数据 */
    pathPatterns: Record<string, PathPatternPoint[]>;
  };

  /** 表格/列表数据 */
  tableData: {
    /** 核心指标 */
    coreMetrics: CoreMetrics;
    /** 样本结论 */
    conclusion: Conclusion;
    /** 四象限统计 */
    quadrantStats: QuadrantStat[];
    /** 信号表现列表 */
    signalLifts: SignalLift[];
    /** 极端背离事件列表 */
    extremeDivergences: ExtremeDivergence[];
    /** 状态转移列表 */
    stateTransitions: StateTransition[];
    /** 状态转移摘要列表 */
    transitionSummaries: string[];
    /** 状态转移路径排名 */
    rankedTransitionPaths: RankedPath[];
    /** 信号组合列表 */
    signalCombinations: SignalCombination[];
    /** 组合协同效应列表 */
    combinationSynergies: CombinationSynergy[];
    /** 决策摘要 */
    decisionSummary: DecisionSummary;
    /** 交易建议 */
    tradingPlaybook: TradingPlaybook;
    /** 历史路径统计数据 */
    pathStats: Array<{
      path: string;
      count: number;
      avgReturn: number | null;
      winRate: number | null;
    }>;
    /** 窗口统计数据（T+1/T+3/T+5） */
    windowStats: WindowStat[];
    /** 相似历史案例数据 */
    similarCases: SimilarCase[];
    /** 信号详情面板数据 */
    signalDetail: SignalLift[];
    /** 信号变迁面板数据 */
    signalShift: {
      signalName: string;
      recent30dAvgReturn: number | null;
      historicalAvgReturn: number | null;
      recent30dWinRate: number | null;
      historicalWinRate: number | null;
      trend: '提升' | '下降' | '稳定';
    } | null;
    /** 偏好环境列表数据 */
    preferenceList: Array<{
      name: string;
      description: string;
      count: number;
      avgReturn: number | null;
      winRate: number | null;
      starLevel: 1 | 2 | 3 | 4 | 5;
    }>;
    /** 规避环境列表数据 */
    avoidList: Array<{
      name: string;
      description: string;
      count: number;
      avgReturn: number | null;
      winRate: number | null;
      starLevel: 1 | 2 | 3 | 4 | 5;
    }>;
    /** 产业联动关系数据 */
    relationshipProfile: RelationshipProfile;
    /** 反直觉机会列表数据 */
    contraList: CounterIntuitiveSignal[];
    /** 信号陷阱列表数据 */
    trapList: CounterIntuitiveSignal[];
  };

  /** 历史性格档案数据 */
  personality: {
    /** 数据截止日期 */
    asOfDate: string;
    /** 日期范围开始 */
    dateRangeStart: string;
    /** 日期范围结束 */
    dateRangeEnd: string;
    /** 样本天数 */
    sampleDays: number;
    /** 有效样本天数 */
    validSampleDays: number;
    /** 摘要指标 */
    summaryMetrics: PersonalitySummaryMetrics;
    /** 性格摘要 */
    summary: PersonalitySummary;
    /** 习惯模式列表 */
    habitPatterns: PersonalityPattern[];
    /** 反直觉模式列表 */
    counterIntuitivePatterns: CounterIntuitiveSignal[];
    /** 陷阱模式列表 */
    trapPatterns: CounterIntuitiveSignal[];
    /** 关系画像 */
    relationshipProfile: RelationshipProfile;
    /** 路径模式列表 */
    pathPatterns: PathPattern[];
    /** 稳定性分析 */
    stability: PersonalityStability;
    /** 样本警告列表 */
    sampleWarnings: string[];
  };

  /** 交易员视角数据 */
  operator: {
    /** 数据截止日期 */
    asOfDate: string;
    /** 日期范围开始 */
    dateRangeStart: string;
    /** 日期范围结束 */
    dateRangeEnd: string;
    /** 样本天数 */
    sampleDays: number;
    /** 制度判断 */
    regime: Regime;
    /** 操作手册 */
    playbook: OperatorPlaybook;
    /** 信号角色列表 */
    signalRoles: OperatorSignalRole[];
    /** 反直觉信号列表 */
    counterIntuitiveSignals: CounterIntuitiveSignal[];
    /** 信号陷阱列表 */
    signalTraps: CounterIntuitiveSignal[];
    /** 条件信号效应列表 */
    conditionalEffects: ConditionalSignalEffect[];
    /** 确认组合列表 */
    confirmationPairs: OperatorConfirmationPair[];
  };

  /** AI研判/建议文本 */
  aiInsight: {
    /** 操作建议 */
    advice: {
      /** 看什么建议 */
      watch: string;
      /** 用什么确认建议 */
      confirm: string;
      /** 什么会失效建议 */
      failure: string;
      /** 样本约束建议 */
      constraint: string;
    };
    /** 观察要点列表 */
    watchPoints: string[];
    /** 研究明细内容 */
    researchDetails: string;
  };

  /** 预测准确度评估 */
  predictionEvaluation: {
    /** 分时段回测指标 */
    metricsByPeriod: Array<{
      periodDays: number;
      metrics: {
        window1d: BacktestMetricsWindow;
        window3d: BacktestMetricsWindow;
        window5d: BacktestMetricsWindow;
        totalPredictions: number;
        validPredictions1d: number;
        validPredictions3d: number;
        validPredictions5d: number;
        quintileReturns: QuintileReturn[] | null;
      };
    }>;
    /** 稳定性指标 */
    stabilityMetrics: {
      predictionVolatility1d: number | null;
      stabilityScore: number | null;
      similarityDistribution: Record<string, number>;
    } | null;
    /** 最近预测记录 */
    recentPredictions: PredictionAccuracy[];
    /** 置信区间 */
    confidenceIntervals: ConfidenceInterval[];
  };

  /** 按日期索引的映射数据 */
  dateIndex: Record<string, DateEntry>;
}

/** 回测指标窗口 */
export interface BacktestMetricsWindow {
  /** IC (Spearman 相关系数) */
  ic: number | null;
  /** 方向准确率 */
  directionAccuracy: number | null;
  /** RMSE */
  rmse: number | null;
  /** MAE */
  mae: number | null;
  /** 平均误差 */
  meanError: number | null;
}

/** 分组收益统计 */
export interface QuintileReturn {
  quintile: number;
  count: number;
  avgPredicted: number | null;
  avgActual: number | null;
  directionAccuracy: number | null;
}

/** 预测准确度记录 */
export interface PredictionAccuracy {
  targetDate: string;
  predictedReturn1d: number | null;
  predictedReturn3d: number | null;
  predictedReturn5d: number | null;
  actualReturn1d: number | null;
  actualReturn3d: number | null;
  actualReturn5d: number | null;
  predictionError1d: number | null;
  predictionError3d: number | null;
  predictionError5d: number | null;
  directionCorrect1d: boolean | null;
  directionCorrect3d: boolean | null;
  directionCorrect5d: boolean | null;
  sampleCount: number;
  avgSimilarity: number;
  confidenceScore: number;
}

/** 置信区间 */
export interface ConfidenceInterval {
  window: string;
  pointEstimate: number;
  lowerBound: number;
  upperBound: number;
  sampleSize: number;
}
