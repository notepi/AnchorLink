"""
Group Rotation 模块 - 数据模型

按 architecture.md 第 8 节设计：
  - GroupRotation dataclass
  - 组间强弱排名
  - 组间差值（spread）
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class GroupRotation:
    """
    组间轮动分析结果

    包含：
      - 组间强弱排名（最强/最弱池子）
      - 组间差值（spread）
      - 池子中位数涨跌幅
      - 数据质量标记
    """

    # 基础标识
    trade_date: str  # 交易日期 YYYYMMDD

    # 组间强弱排名
    strongest_group: str  # median_return 最高的池子ID
    weakest_group: str  # median_return 最低的池子ID
    group_ranking: list[str] = field(default_factory=list)  # 池子ID按强弱排序（降序）

    # 组间差值（spread）
    core_pool_id: str = "direct_peers"  # 当前 spread 计算使用的核心池
    spreads: dict[str, float] = field(default_factory=dict)  # universe_id -> spread vs core_pool
    core_vs_theme_spread: Optional[float] = None  # direct_peers - theme_pool
    core_vs_chain_spread: Optional[float] = None  # direct_peers - industry_chain
    core_vs_trading_spread: Optional[float] = None  # direct_peers - trading_watchlist

    # 池子中位数涨跌幅
    group_medians: dict[str, float] = field(default_factory=dict)  # universe_id -> median_return

    # 数据质量
    data_status: str = "ok"  # "ok" | "insufficient_data"
    missing_groups: list[str] = field(default_factory=list)  # 数据缺失的池子
    partial_reason: Optional[str] = None  # 数据不足原因
