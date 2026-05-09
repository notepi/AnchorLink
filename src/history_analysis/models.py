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
