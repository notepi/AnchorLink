"""
历史分析数据模型

定义历史时间序列分析的输入输出结构。
所有百分比字段使用"百分点"口径（2.71 表示 2.71%，不是 0.0271）。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class HistoryRow:
    """汇总表单行：一天的全量状态 + 前瞻收益"""
    date: str
    anchor_return: Optional[float]
    direct_peers_median: Optional[float]
    industry_chain_median: Optional[float]
    theme_pool_median: Optional[float]
    trading_watchlist_median: Optional[float]
    relative_strength_vs_direct: Optional[float]
    relative_strength_vs_industry_chain: Optional[float]
    relative_strength_vs_theme: Optional[float]
    direct_up_ratio: Optional[float]
    chain_up_ratio: Optional[float]
    amount_expansion_ratio: Optional[float]
    moneyflow_positive_ratio: Optional[float]
    strongest_group: str
    weakest_group: str
    industry_beta: str
    anchor_alpha: str
    risk_level: str
    signal_labels: str
    signal_categories: str
    signal_pairs: str  # JSON: [{"label":"xxx","category":"yyy"}, ...]
    data_quality_status: str
    next_1d_return: Optional[float]
    next_3d_return: Optional[float]
    next_5d_return: Optional[float]
    next_1d_excess_vs_chain: Optional[float]
    next_3d_excess_vs_chain: Optional[float]
    next_5d_excess_vs_chain: Optional[float]


@dataclass(frozen=True)
class RollingMetrics:
    """滚动指标：累计超额 + 连续性 streak"""
    date: str
    excess_5d: Optional[float]
    excess_10d: Optional[float]
    outperform_streak: int
    beta_streak: int
    theme_vs_core_streak: int
    risk_high_streak: int


@dataclass(frozen=True)
class QuadrantStats:
    """四象限统计"""
    quadrant: str
    count: int
    avg_next_1d: Optional[float]
    avg_next_3d: Optional[float]
    avg_next_5d: Optional[float]
    avg_next_1d_excess: Optional[float]
    win_rate_1d: Optional[float]
    avg_relative_strength: Optional[float]


@dataclass(frozen=True)
class ExtremeDivergence:
    """极端背离日期"""
    date: str
    anchor_return: float
    industry_chain_median: float
    divergence: float
    industry_beta: str
    anchor_alpha: str
    risk_level: str
    signal_labels: str


@dataclass(frozen=True)
class EventPath:
    """极端背离事件的 T-N 到 T+N 路径"""
    event_date: str
    offset: int
    date: Optional[str]
    anchor_return: Optional[float]
    chain_median: Optional[float]
    excess: Optional[float]


@dataclass(frozen=True)
class SignalPair:
    """单个标签-类别对（用于后端表达和测试，不直接写入 CSV）"""
    label: str
    category: str


@dataclass(frozen=True)
class SignalLift:
    """信号 lift：相对 baseline 的提升"""
    label: str
    category: str
    appearance_count: int
    avg_next_1d: Optional[float]
    avg_next_3d: Optional[float]
    avg_next_5d: Optional[float]
    avg_next_1d_excess: Optional[float]
    win_rate_1d: Optional[float]
    baseline_avg_next_1d: Optional[float]
    baseline_win_rate_1d: Optional[float]
    avg_next_1d_delta_pp: Optional[float]
    lift_next_1d: Optional[float]
    lift_win_rate: Optional[float]
    min_count_passed: bool


@dataclass(frozen=True)
class StateTransition:
    """状态转移"""
    from_state: str
    to_state: str
    count: int
    probability: float


@dataclass(frozen=True)
class CounterIntuitiveSignal:
    """反直觉信号：信号语义直觉与历史实际表现相反。"""
    label: str
    display_label: str
    category: str
    appearance_count: int
    avg_next_1d: Optional[float]
    win_rate_1d: Optional[float]
    avg_next_1d_delta_pp: Optional[float]
    intuitive_direction: str
    actual_direction: str
    degree: float
    verdict: str
    explanation: str


@dataclass(frozen=True)
class ConditionalSignalEffect:
    """信号在特定象限内的条件效果。"""
    label: str
    display_label: str
    category: str
    quadrant: str
    quadrant_count: int
    signal_in_quadrant_count: int
    avg_next_1d_in_quadrant: Optional[float]
    win_rate_in_quadrant: Optional[float]
    avg_next_1d_delta_pp_vs_quadrant: Optional[float]
    overall_avg_next_1d: Optional[float]
    verdict: str


@dataclass(frozen=True)
class HistoryRegime:
    """历史规律当前可用性。"""
    confidence: str
    status: str
    headline: str
    reasons: list[str]
    risk_points: list[str]
    latest_rolling_date: Optional[str]


@dataclass(frozen=True)
class OperatorSignalRole:
    """面向操盘判断的信号角色。"""
    label: str
    display_label: str
    category: str
    business_tag: str
    role: str
    insight_type: str
    priority: float
    count: int
    avg_next_1d: Optional[float]
    delta_pp: Optional[float]
    win_rate: Optional[float]
    trend: str
    best_condition_quadrant: Optional[str]
    conclusion: str
    reason: str


@dataclass(frozen=True)
class OperatorConfirmationPair:
    """可作为确认条件的信号组合。"""
    labels: list[str]
    display_labels: list[str]
    count: int
    avg_next_1d: float
    win_rate: Optional[float]
    best_single_label: str
    synergy: float
    verdict: str
    conclusion: str


@dataclass(frozen=True)
class OperatorPlaybook:
    """交易观察建议。"""
    stance: str
    headline: str
    watch_for: list[str]
    confirmations: list[str]
    invalidations: list[str]
    sample_note: str


@dataclass(frozen=True)
class PersonalitySummaryMetrics:
    """历史性格画像顶部摘要指标。"""
    baseline_win_rate_1d: float | None
    median_excess_3d: float | None
    median_adverse_3d_proxy: float | None
    payoff_ratio: float | None
    sharpe_like_ratio: float | None
    signal_coverage_ratio: float | None
    information_ratio: float | None = None
    expectancy_1d: float | None = None


@dataclass(frozen=True)
class PersonalitySummary:
    """历史性格摘要。"""
    headline: str
    traits: list[str]
    strongest_pattern_label: str | None
    weakest_pattern_label: str | None
    confidence: str
    generation_method: str


@dataclass(frozen=True)
class ConditionEffect:
    """条件效果（用于 PersonalityPattern 的 best/worst condition）。"""
    quadrant: str
    count: int
    avg_next_1d: float | None
    win_rate_1d: float | None
    delta_pp_vs_quadrant: float | None


@dataclass(frozen=True)
class PersonalityPattern:
    """性格模式：喜欢/讨厌/反直觉/陷阱。"""
    label: str
    display_label: str
    category: str
    pattern_kind: str
    habit_type: str
    count: int
    avg_next_1d: float | None
    avg_next_3d: float | None
    avg_next_5d: float | None
    avg_next_1d_excess: float | None
    avg_next_1d_delta_pp: float | None
    win_rate_1d: float | None
    effect_score: float | None
    significance: str
    confidence: str
    best_condition: ConditionEffect | None
    worst_condition: ConditionEffect | None
    explanation: str
    source: str


@dataclass(frozen=True)
class RelationshipPattern:
    """与参照池的关系模式。"""
    relation: str
    confidence: str
    sample_count: int
    evidence: list[str]
    same_day_corr: float | None
    anchor_leads_corr: float | None
    anchor_lags_corr: float | None
    avg_relative_strength: float | None
    outperform_ratio: float | None
    repair_after_underperform_ratio: float | None
    continuation_after_outperform_ratio: float | None
    stability: str


@dataclass(frozen=True)
class RelationshipProfile:
    """产业联动画像：与4个参照池的关系。"""
    anchor_vs_chain: RelationshipPattern
    anchor_vs_theme: RelationshipPattern
    anchor_vs_core: RelationshipPattern
    anchor_vs_trading_watchlist: RelationshipPattern


@dataclass(frozen=True)
class PathPatternPoint:
    """路径画像的单个点。"""
    offset: int
    anchor_return: float | None
    chain_median: float | None
    excess: float | None


@dataclass(frozen=True)
class PathPattern:
    """路径画像：按事件类型聚合的 T-5 到 T+5 路径。"""
    event_label: str
    count: int
    avg_path: list[PathPatternPoint]
    summary: str
    confidence: str


@dataclass(frozen=True)
class PersonalityStability:
    """性格稳定性评估。"""
    status: str
    recent_window_days: int
    early_vs_recent_notes: list[str]


@dataclass(frozen=True)
class HistoryPersonalityProfile:
    """历史性格画像主模型。"""
    as_of_date: str
    date_range_start: str
    date_range_end: str
    sample_days: int
    valid_sample_days: int
    summary_metrics: PersonalitySummaryMetrics
    personality_summary: PersonalitySummary
    habit_patterns: list[PersonalityPattern]
    counter_intuitive_patterns: list[PersonalityPattern]
    trap_patterns: list[PersonalityPattern]
    relationship_profile: RelationshipProfile
    path_patterns: list[PathPattern]
    stability: PersonalityStability
    sample_warnings: list[str]


@dataclass(frozen=True)
class OperatorHistoryView:
    """历史验证工作台后端视图模型。"""
    as_of_date: str
    date_range_start: str
    date_range_end: str
    sample_days: int
    regime: HistoryRegime
    playbook: OperatorPlaybook
    signal_roles: list[OperatorSignalRole]
    counter_intuitive_signals: list[CounterIntuitiveSignal]
    signal_traps: list[CounterIntuitiveSignal]
    conditional_effects: list[ConditionalSignalEffect]
    confirmation_pairs: list[OperatorConfirmationPair]


# ============================================================
# 预测准确度评估相关模型
# ============================================================

@dataclass(frozen=True)
class PredictionAccuracy:
    """单日预测准确度评估结果"""
    target_date: str
    predicted_return_1d: float | None
    predicted_return_3d: float | None
    predicted_return_5d: float | None
    actual_return_1d: float | None
    actual_return_3d: float | None
    actual_return_5d: float | None
    prediction_error_1d: float | None
    prediction_error_3d: float | None
    prediction_error_5d: float | None
    direction_correct_1d: bool | None
    direction_correct_3d: bool | None
    direction_correct_5d: bool | None
    sample_count: int
    avg_similarity: float
    confidence_score: float


@dataclass(frozen=True)
class BacktestMetricsWindow:
    """单窗口回测指标"""
    ic: float | None
    direction_accuracy: float | None
    rmse: float | None
    mae: float | None
    mean_error: float | None


@dataclass(frozen=True)
class BacktestMetrics:
    """回测评估指标汇总"""
    window_1d: BacktestMetricsWindow
    window_3d: BacktestMetricsWindow
    window_5d: BacktestMetricsWindow
    total_predictions: int
    valid_predictions_1d: int
    valid_predictions_3d: int
    valid_predictions_5d: int
    quintile_returns: tuple[dict, ...] | None


@dataclass(frozen=True)
class BacktestMetricsByPeriod:
    """分时段回测指标"""
    period_days: int
    metrics: BacktestMetrics


@dataclass(frozen=True)
class StabilityMetrics:
    """预测稳定性指标"""
    prediction_volatility_1d: float | None
    stability_score: float | None
    similarity_distribution: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ConfidenceInterval:
    """置信区间"""
    window: str
    point_estimate: float
    lower_bound: float
    upper_bound: float
    sample_size: int


@dataclass(frozen=True)
class PredictionBacktestResult:
    """预测回测完整结果"""
    metrics_by_period: tuple[BacktestMetricsByPeriod, ...]
    stability_metrics: StabilityMetrics
    recent_predictions: tuple[PredictionAccuracy, ...]
    confidence_intervals: tuple[ConfidenceInterval, ...] | None
