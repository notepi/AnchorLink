"""
Output 层数据模型

定义 IndustrySnapshot 和相关输出结构，按 PRD 第13节规范

数据类：
  - AnchorInfo: 锚定标的信息
  - DataQuality: 数据质量状态
  - IndustryState: 行业状态指标
  - AnchorPositionOutput: 锚定标的相对位置
  - GroupRotationOutput: 组间轮动输出
  - SignalOutput: 信号标签输出
  - Conclusion: 综合结论
  - IndustrySnapshot: 完整输出结构
"""

from dataclasses import dataclass, field
from typing import Optional, Literal

from src.linkage.models import LinkageAnalysis


# 类型定义
BetaLevel = Literal["positive", "neutral", "negative"]
AlphaLevel = Literal["positive", "neutral", "negative"]
RiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class AnchorInfo:
    """锚定标的信息"""
    symbol: str
    name: str
    themes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DataQuality:
    """数据质量状态"""
    status: str  # "ok" | "partial" | "insufficient_data"
    missing_fields: list[str] = field(default_factory=list)
    insufficient_universes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IndustryState:
    """行业状态指标"""
    direct_peers_return_median: Optional[float] = None
    industry_chain_return_median: Optional[float] = None
    theme_pool_return_median: Optional[float] = None
    up_ratio: Optional[float] = None
    amount_expansion_ratio: Optional[float] = None
    moneyflow_positive_ratio: Optional[float] = None


@dataclass(frozen=True)
class AnchorPositionOutput:
    """锚定标的相对位置"""
    anchor_return: float
    relative_strength_vs_direct_peers: Optional[float] = None
    relative_strength_vs_industry_chain: Optional[float] = None
    relative_strength_vs_theme_pool: Optional[float] = None
    return_rank: Optional[int] = None
    amount_rank: Optional[int] = None
    turnover_rank: Optional[int] = None
    moneyflow_rank: Optional[int] = None
    total_count: Optional[int] = None


@dataclass(frozen=True)
class GroupRotationOutput:
    """组间轮动输出"""
    strongest_group: str
    weakest_group: str
    core_pool_id: str = "direct_peers"
    group_ranking: list[str] = field(default_factory=list)
    core_vs_theme_spread: Optional[float] = None
    core_vs_chain_spread: Optional[float] = None
    core_vs_trading_spread: Optional[float] = None
    group_medians: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class SignalOutput:
    """信号标签输出"""
    label: str
    category: str  # "beta" | "alpha" | "volume" | "rotation" | "abnormal"
    confidence: str  # "high" | "medium" | "low"
    evidence: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Conclusion:
    """综合结论"""
    industry_beta: BetaLevel
    anchor_alpha: AlphaLevel
    risk_level: RiskLevel
    summary: str
    next_watch: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IndustrySnapshot:
    """
    行业快照 - 完整输出结构

    按 PRD 第13节定义，包含：
      - anchor: 锚定标的信息
      - as_of_date: 分析日期
      - data_quality: 数据质量
      - industry_state: 行业状态
      - anchor_position: 锚定标的相对位置
      - group_rotation: 组间轮动
      - signals: 信号标签列表
      - conclusion: 综合结论
    """
    anchor: AnchorInfo
    as_of_date: str  # YYYY-MM-DD 格式
    data_quality: DataQuality
    industry_state: IndustryState
    anchor_position: AnchorPositionOutput
    group_rotation: GroupRotationOutput
    conclusion: Conclusion
    signals: list[SignalOutput] = field(default_factory=list)
    linkage_analysis: Optional[LinkageAnalysis] = None
