"""
日线股价联动分析数据模型。

该层只基于已落地的日线行情，验证股票池成员对 Anchor 的短期解释力。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class LinkageMember:
    """单个股票与 Anchor 的联动指标。"""

    universe_id: str
    symbol: str
    name: str
    role: str
    relevance: float
    weight: float
    corr_5d: Optional[float] = None
    corr_10d: Optional[float] = None
    corr_20d: Optional[float] = None
    beta_5d: Optional[float] = None
    beta_10d: Optional[float] = None
    beta_20d: Optional[float] = None
    direction_consistency_5d: Optional[float] = None
    direction_consistency_10d: Optional[float] = None
    direction_consistency_20d: Optional[float] = None
    observations: int = 0
    data_status: str = "ok"  # "ok" | "partial" | "insufficient_data"
    partial_reason: Optional[str] = None


@dataclass(frozen=True)
class PoolLinkage:
    """单个股票池的联动分析结果。"""

    universe_id: str
    status: str
    members: list[LinkageMember] = field(default_factory=list)
    top_members: list[LinkageMember] = field(default_factory=list)
    avg_corr_20d: Optional[float] = None
    avg_beta_20d: Optional[float] = None
    avg_direction_consistency_20d: Optional[float] = None
    partial_reason: Optional[str] = None


@dataclass(frozen=True)
class LinkageAnalysis:
    """完整日线联动分析结果。"""

    trade_date: str
    anchor_symbol: str
    status: str
    windows: list[int] = field(default_factory=lambda: [5, 10, 20])
    pools: dict[str, PoolLinkage] = field(default_factory=dict)
    partial_reason: Optional[str] = None
