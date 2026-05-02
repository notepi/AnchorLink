"""
Anchor Position 模块 - 相对强弱计算

基于 architecture.md 第 7 节设计：
  - RelativeStrength dataclass
  - 相对强弱计算（anchor_return - pool_median）
  - 位置判断（outperform/underperform/neutral）

职责：
  - 计算 Anchor 相对单个池子的强弱位置
  - 判断位置
  - 协调 RankingCalculator 获取排名数据
"""

from dataclasses import dataclass, field
from typing import Optional

from src.config.loader import PoolRegistry
from src.pool_state.models import PoolState, MemberData


# 位置判断阈值（可配置）
NEUTRAL_THRESHOLD = 0.5  # relative_strength 绝对值 < 0.5% 视为 neutral


@dataclass(frozen=True)
class RelativeStrength:
    """
    Anchor 相对单个池子的强弱位置

    按 architecture.md 第 7 节定义，包含：
      - 相对强弱计算
      - 五个排名维度
      - 位置判断
    """

    # 基础标识
    universe_id: str           # 池子ID
    trade_date: str            # 交易日期 YYYYMMDD

    # 相对强弱核心指标
    anchor_return: float       # Anchor 当日涨跌幅（%）
    pool_median: float         # 池子中位数涨跌幅（%）
    relative_strength: float   # anchor_return - pool_median（%）

    # 位置判断
    position: str              # "outperform" | "underperform" | "neutral"

    # 五个排名维度（1 = 最高，N = 最低）
    rank_return: int           # 涨幅排名（在 ranking_scope 中）
    rank_volume: int           # 成交额排名
    rank_turnover: int         # 换手率排名
    rank_fund: int             # 资金净流入排名
    total_count: int           # ranking_scope 总成员数（用于计算分位）

    # 估值分位（仅核心同类池有意义）
    valuation_percentile: Optional[float]  # Anchor 估值在核心同类中的分位（0-100）

    # 数据质量标记
    data_status: str           # "ok" | "insufficient_data" | "partial"
    partial_reason: Optional[str] = None  # partial 状态原因


def determine_position(relative_strength: float) -> str:
    """
    判断位置

    Args:
        relative_strength: 相对强弱值（%）

    Returns:
        "outperform" | "underperform" | "neutral"

    判断标准：
        - relative_strength > NEUTRAL_THRESHOLD (0.5%) → outperform
        - relative_strength < -NEUTRAL_THRESHOLD (-0.5%) → underperform
        - 其他 → neutral
    """
    if relative_strength > NEUTRAL_THRESHOLD:
        return "outperform"
    elif relative_strength < -NEUTRAL_THRESHOLD:
        return "underperform"
    else:
        return "neutral"


def check_relative_strength_quality(
    anchor_data: MemberData,
    pool_state: PoolState,
    ranking_data: dict,
) -> tuple[str, Optional[str]]:
    """
    检查相对强弱数据质量

    Args:
        anchor_data: Anchor 数据
        pool_state: 池子状态
        ranking_data: 排名数据

    Returns:
        (data_status, partial_reason)

    降级规则：
        - Anchor 无涨跌幅 → insufficient_data
        - 池子状态 insufficient_data → insufficient_data
        - 排名数据缺失 → partial
    """
    # Anchor 无涨跌幅
    if anchor_data.pct_chg is None:
        return "insufficient_data", "anchor has no return data"

    # 池子数据不足
    if pool_state.data_status == "insufficient_data":
        return "insufficient_data", "pool has insufficient data"

    # 排名数据缺失
    if ranking_data.get("total_count", 0) == 0:
        return "partial", "no ranking data available"

    # 部分排名缺失（资金排名）
    if ranking_data.get("rank_fund", 0) == 0:
        return "partial", "fund ranking missing"

    return "ok", None


def calculate_relative_strength(
    universe_id: str,
    trade_date: str,
    anchor_data: MemberData,
    pool_state: PoolState,
    ranking_data: dict,
) -> RelativeStrength:
    """
    计算 Anchor 相对单个池子的相对强弱

    Args:
        universe_id: 池子ID
        trade_date: 交易日期
        anchor_data: Anchor 当日数据（MemberData）
        pool_state: 该池子的 PoolState
        ranking_data: 排名数据（从 RankingCalculator.calculate_ranks() 获取）

    Returns:
        RelativeStrength 完整结构
    """
    # 1. 获取 Anchor 涨跌幅
    anchor_return = anchor_data.pct_chg if anchor_data.pct_chg is not None else 0.0

    # 2. 获取池子中位数
    pool_median = pool_state.median_return if pool_state.median_return is not None else 0.0

    # 3. 计算相对强弱
    relative_strength = anchor_return - pool_median

    # 4. 判断位置
    position = determine_position(relative_strength)

    # 5. 获取排名数据
    rank_return = ranking_data.get("rank_return", 0)
    rank_volume = ranking_data.get("rank_volume", 0)
    rank_turnover = ranking_data.get("rank_turnover", 0)
    rank_fund = ranking_data.get("rank_fund", 0)
    total_count = ranking_data.get("total_count", 0)
    valuation_percentile = ranking_data.get("valuation_percentile")

    # 6. 数据质量检查
    data_status, partial_reason = check_relative_strength_quality(
        anchor_data, pool_state, ranking_data
    )

    return RelativeStrength(
        universe_id=universe_id,
        trade_date=trade_date,
        anchor_return=anchor_return,
        pool_median=pool_median,
        relative_strength=relative_strength,
        position=position,
        rank_return=rank_return,
        rank_volume=rank_volume,
        rank_turnover=rank_turnover,
        rank_fund=rank_fund,
        total_count=total_count,
        valuation_percentile=valuation_percentile,
        data_status=data_status,
        partial_reason=partial_reason,
    )


class RelativeStrengthCalculator:
    """
    相对强弱计算器（多池聚合）

    职责：
      - 遍历所有池子计算相对强弱
      - 返回 dict[universe_id, RelativeStrength]
    """

    def __init__(
        self,
        registry: PoolRegistry,
        ranking_calculator,  # RankingCalculator 类型
    ):
        self.registry = registry
        self.ranking_calculator = ranking_calculator

    def calculate_all(
        self,
        trade_date: str,
        anchor_data: MemberData,
        pool_states: dict[str, PoolState],
        market_data: dict[str, MemberData],  # symbol -> MemberData
    ) -> dict[str, RelativeStrength]:
        """
        计算 Anchor 相对所有池子的相对强弱

        Args:
            trade_date: 交易日期
            anchor_data: Anchor 当日数据
            pool_states: 各池子的 PoolState
            market_data: 所有成员的当日数据

        Returns:
            universe_id -> RelativeStrength
        """
        result = {}

        for universe in self.registry.get_all_universes():
            universe_id = universe.universe_id

            # 获取池子状态
            pool_state = pool_states.get(universe_id)
            if pool_state is None:
                continue

            # 获取排名数据
            ranking_data = self.ranking_calculator.calculate_ranks(
                universe_id, trade_date, anchor_data, market_data
            )

            # 计算相对强弱
            rs = calculate_relative_strength(
                universe_id, trade_date, anchor_data, pool_state, ranking_data
            )

            result[universe_id] = rs

        return result