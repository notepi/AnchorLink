"""
虚拟 ETF / 自定义指数 — 数据模型

所有结构使用 @dataclass(frozen=True)，不可变。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class IndexMember:
    symbol: str
    raw_config_weight: float           # pools.yaml 中的原始 weight（如 0.8）
    normalized_target_weight: float    # 归一化后的目标权重（如 0.1111）
    role: str
    membership_scope: str              # "benchmark" | "ranking"


@dataclass(frozen=True)
class IndexDefinition:
    index_id: str                      # "{universe_id}_index"，如 "industry_chain_index"
    display_name: str
    can_be_benchmark: bool
    pool_config_version: str
    members: tuple[IndexMember, ...]


@dataclass(frozen=True)
class IndexNAVRecord:
    index_id: str
    trade_date: str                    # YYYYMMDD
    nav: float
    index_return_1d: Optional[float]   # 百分比，首日为 None
    index_return_3d: Optional[float]   # 百分比，前 2 日为 None
    index_return_5d: Optional[float]   # 百分比，前 4 日为 None
    index_return_10d: Optional[float]  # 百分比，前 9 日为 None
    is_rebalance_day: bool
    rebalance_uses_stale_price: bool   # 当日再平衡是否有成员使用了 stale 报价
    rebalance_reason: str              # "monthly_rebalance" | "late_member_join" | "none"
    included_member_count: int
    configured_member_count: int
    fresh_price_count: int
    stale_price_count: int
    stale_days_max: int
    stale_symbols: str                 # 逗号分隔
    fresh_quote_ratio: float           # fresh_price_count / included_member_count
    universe_inclusion_ratio: float    # included_member_count / configured_member_count
    data_status: str                   # "ok" | "partial" | "insufficient_data"
    rebalance_flag: str                # "" | "monthly"
    pool_config_version: str
    price_adjustment_mode: str         # "qfq"
    universe_mode: str                 # "constant_universe_research_view"
    source_data_as_of: str             # YYYYMMDD
    build_mode: str                    # "full_rebuild"
    generated_at: str                  # ISO 8601


@dataclass(frozen=True)
class MemberDayRecord:
    index_id: str
    trade_date: str                    # YYYYMMDD
    symbol: str
    raw_config_weight: float
    normalized_target_weight: float
    actual_weight: Optional[float]     # included=false 时为 None
    close: Optional[float]             # included=false 时为 None
    quote_status: str                  # "fresh" | "carried_forward" | "zero_volume_raw" | ""
    price_is_stale: bool
    source_trade_date: Optional[str]   # included=false 时为 None
    stale_days: int
    included: bool
    membership_role: str
    membership_event: str              # "base_init" | "late_member_join" | "none"
    pool_config_version: str
    price_adjustment_mode: str
    universe_mode: str
    source_data_as_of: str
    build_mode: str
    generated_at: str


@dataclass(frozen=True)
class AnchorExcessRecord:
    date: str                          # YYYYMMDD
    anchor_symbol: str
    anchor_close: float
    # Anchor 多周期收益（百分比）
    anchor_return_1d: Optional[float]
    anchor_return_3d: Optional[float]
    anchor_return_5d: Optional[float]
    anchor_return_10d: Optional[float]
    # industry_chain_index
    excess_vs_industry_chain_index_1d: Optional[float]
    excess_vs_industry_chain_index_3d: Optional[float]
    excess_vs_industry_chain_index_5d: Optional[float]
    excess_vs_industry_chain_index_10d: Optional[float]
    # direct_peers_index
    excess_vs_direct_peers_index_1d: Optional[float]
    excess_vs_direct_peers_index_3d: Optional[float]
    excess_vs_direct_peers_index_5d: Optional[float]
    excess_vs_direct_peers_index_10d: Optional[float]
    # theme_pool_index
    excess_vs_theme_pool_index_1d: Optional[float]
    excess_vs_theme_pool_index_3d: Optional[float]
    excess_vs_theme_pool_index_5d: Optional[float]
    excess_vs_theme_pool_index_10d: Optional[float]
    # trading_watchlist_index
    excess_vs_trading_watchlist_index_1d: Optional[float]
    excess_vs_trading_watchlist_index_3d: Optional[float]
    excess_vs_trading_watchlist_index_5d: Optional[float]
    excess_vs_trading_watchlist_index_10d: Optional[float]
    # 元数据
    pool_config_version: str
    price_adjustment_mode: str
    universe_mode: str
    source_data_as_of: str
    build_mode: str
    generated_at: str
