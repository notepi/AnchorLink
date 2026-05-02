"""
Group Rotation 模块 - Spread 差值计算

职责：
  - 计算核心池与其他池的差值
  - 生成 spreads dict

Spread 含义：
  - spread > 0 → 核心池更强
  - spread < 0 → 其他池更强
  - spread 绝对值越大 → 差异越显著

计算公式：
  spread = core_pool_median - other_pool_median
"""

from typing import Optional

from src.config.loader import PoolRegistry
from src.pool_state.models import PoolState
from src.group_rotation.models import GroupRotation
from src.group_rotation.rotation_analyzer import analyze_group_rotation


# 核心池ID（默认）
DEFAULT_CORE_POOL_ID = "direct_peers"


class SpreadCalculator:
    """
    Spread 差值计算器

    计算核心池与其他池的中位数差值
    """

    def __init__(self, core_pool_id: str = DEFAULT_CORE_POOL_ID):
        """
        初始化计算器

        Args:
            core_pool_id: 核心池ID（默认 direct_peers）
        """
        self.core_pool_id = core_pool_id

    def calculate_spreads(
        self,
        group_medians: dict[str, float],
    ) -> dict[str, float]:
        """
        计算核心池与其他池的差值

        Args:
            group_medians: 各池子中位数涨跌幅（universe_id -> median_return）

        Returns:
            universe_id -> spread (core_pool_median - other_pool_median)

        Note:
            - 核心池本身不计算 spread（不在返回 dict 中）
            - 其他池没有数据时不计算
        """
        spreads = {}

        # 获取核心池中位数
        core_median = group_medians.get(self.core_pool_id)
        if core_median is None:
            # 核心池数据缺失，无法计算
            return spreads

        # 计算其他池的 spread
        for universe_id, other_median in group_medians.items():
            if universe_id == self.core_pool_id:
                continue  # 不计算核心池本身

            if other_median is None:
                continue  # 其他池数据缺失

            spread = calculate_single_spread(core_median, other_median)
            spreads[universe_id] = spread

        return spreads

    def enrich_rotation(
        self,
        rotation: GroupRotation,
    ) -> GroupRotation:
        """
        将 spread 数据填充到 GroupRotation

        Args:
            rotation: 基础轮动结果（不含 spread）

        Returns:
            带 spread 的完整 GroupRotation

        Note:
            - 使用 rotation.group_medians 计算
            - 自动提取特定池子的 spread（theme_pool, industry_chain, trading_watchlist）
        """
        # 计算 spreads
        spreads = self.calculate_spreads(rotation.group_medians)

        # 提取特定池子的 spread
        core_vs_theme_spread = spreads.get("theme_pool")
        core_vs_chain_spread = spreads.get("industry_chain")
        core_vs_trading_spread = spreads.get("trading_watchlist")

        # 创建新的 GroupRotation（frozen dataclass 不可变，需要重建）
        from dataclasses import replace

        return replace(
            rotation,
            spreads=spreads,
            core_vs_theme_spread=core_vs_theme_spread,
            core_vs_chain_spread=core_vs_chain_spread,
            core_vs_trading_spread=core_vs_trading_spread,
        )


def calculate_single_spread(
    core_median: float,
    other_median: float,
) -> float:
    """
    计算单个 spread

    Args:
        core_median: 核心池中位数涨跌幅
        other_median: 其他池中位数涨跌幅

    Returns:
        spread = core_median - other_median

    Interpretation:
        - spread > 0: 核心池更强（涨得更多或跌得更少）
        - spread < 0: 其他池更强
        - spread = 0: 相同强弱
    """
    return core_median - other_median


def analyze_rotation_with_spreads(
    pool_states: dict[str, PoolState],
    trade_date: str,
    registry: Optional[PoolRegistry] = None,
    core_pool_id: str = DEFAULT_CORE_POOL_ID,
) -> GroupRotation:
    """
    完整轮动分析（包含 spread）

    Args:
        pool_states: 各池子状态
        trade_date: 交易日期
        registry: 配置注册表（可选）
        core_pool_id: 核心池ID

    Returns:
        带 spread 的完整 GroupRotation

    Workflow:
        1. analyze_group_rotation() → 基础轮动结果
        2. SpreadCalculator.enrich_rotation() → 填充 spread
    """
    # Step 1: 基础轮动分析
    rotation = analyze_group_rotation(pool_states, trade_date, registry)

    # Step 2: 计算 spread 并填充
    calculator = SpreadCalculator(core_pool_id)
    return calculator.enrich_rotation(rotation)