"""
Group Rotation 模块 - 组间轮动分析

职责：
  - 比较四类池子之间谁强谁弱
  - 找出最强和最弱池子
  - 生成组间排名

按 architecture.md 第 8 节设计：
  - 只比较 can_be_benchmark=True 的池子
  - 按 median_return 降序排名
  - 过滤 data_status="insufficient_data" 的池子
  - 至少需要 2 个有效池子才能计算

市场含义：
  - 核心同类强，主题池也强 → 行业和主题共振
  - 主题池强，核心同类弱 → 主题炒作，核心未确认
  - 产业链强，核心同类弱 → 上下游先动，Anchor 未跟
  - 交易观察池强，其他池弱 → 短期资金异动
"""

from typing import Optional

from src.config.loader import PoolRegistry
from src.pool_state.models import PoolState
from src.group_rotation.models import GroupRotation


# 最少有效池子数
MIN_VALID_GROUPS = 2


def analyze_group_rotation(
    pool_states: dict[str, PoolState],
    trade_date: str,
    registry: Optional[PoolRegistry] = None,
) -> GroupRotation:
    """
    分析组间轮动

    Args:
        pool_states: 各池子的 PoolState（universe_id -> PoolState）
        trade_date: 交易日期 YYYYMMDD
        registry: PoolRegistry 配置注册表（可选，用于过滤 can_be_benchmark）

    Returns:
        GroupRotation 完整结构

    Note:
        - 只比较 can_be_benchmark=True 的池子（如果提供 registry）
        - 过滤 data_status="insufficient_data" 的池子
        - 至少需要 MIN_VALID_GROUPS 个有效池子才能计算
    """
    # 1. 过滤有效池子
    valid_groups = _filter_valid_groups(pool_states, registry)

    # 2. 提取中位数涨跌幅
    group_medians = _extract_medians(valid_groups)

    # 3. 数据质量检查
    data_status, missing_groups, partial_reason = _check_rotation_quality(
        pool_states, valid_groups, registry
    )

    # 4. 如果数据不足，返回空结果
    if data_status == "insufficient_data":
        return _empty_rotation_result(trade_date, missing_groups, partial_reason)

    # 5. 确定最强/最弱池子
    strongest_group, weakest_group, group_ranking = determine_strongest_weakest(
        group_medians
    )

    return GroupRotation(
        trade_date=trade_date,
        strongest_group=strongest_group,
        weakest_group=weakest_group,
        group_ranking=group_ranking,
        spreads={},  # 由 SpreadCalculator 填充
        core_vs_theme_spread=None,
        core_vs_chain_spread=None,
        core_vs_trading_spread=None,
        group_medians=group_medians,
        data_status=data_status,
        missing_groups=missing_groups,
        partial_reason=partial_reason,
    )


def determine_strongest_weakest(
    group_medians: dict[str, float]
) -> tuple[str, str, list[str]]:
    """
    找出最强和最弱池子

    Args:
        group_medians: 各池子中位数涨跌幅（universe_id -> median_return）

    Returns:
        (strongest_group, weakest_group, ranking_list)
        - strongest_group: median_return 最高的池子ID
        - weakest_group: median_return 最低的池子ID
        - ranking_list: 池子ID按强弱排序（降序）

    Note:
        - 降序排序：median_return 高 → 强
        - 相同值按出现顺序处理（不特别处理并列）
    """
    if not group_medians:
        return "", "", []

    # 按 median_return 降序排序
    sorted_groups = sorted(
        group_medians.items(), key=lambda x: x[1], reverse=True
    )

    ranking_list = [group_id for group_id, _ in sorted_groups]
    strongest_group = ranking_list[0]
    weakest_group = ranking_list[-1]

    return strongest_group, weakest_group, ranking_list


def _filter_valid_groups(
    pool_states: dict[str, PoolState],
    registry: Optional[PoolRegistry],
) -> dict[str, PoolState]:
    """
    过滤有效池子

    Args:
        pool_states: 所有池子状态
        registry: 配置注册表（可选）

    Returns:
        有效池子状态 dict

    过滤规则：
        1. can_be_benchmark=True（如果提供 registry）
        2. data_status != "insufficient_data"
    """
    valid = {}

    for universe_id, pool_state in pool_states.items():
        # 检查 can_be_benchmark
        if registry:
            universe = registry.get_universe(universe_id)
            if universe and not universe.can_be_benchmark:
                continue

        # 检查数据状态
        if pool_state.data_status == "insufficient_data":
            continue

        # 检查 median_return 是否有效
        if pool_state.median_return is None:
            continue

        valid[universe_id] = pool_state

    return valid


def _extract_medians(valid_groups: dict[str, PoolState]) -> dict[str, float]:
    """
    提取中位数涨跌幅

    Args:
        valid_groups: 有效池子状态

    Returns:
        universe_id -> median_return
    """
    return {
        universe_id: pool_state.median_return
        for universe_id, pool_state in valid_groups.items()
    }


def _check_rotation_quality(
    pool_states: dict[str, PoolState],
    valid_groups: dict[str, PoolState],
    registry: Optional[PoolRegistry],
) -> tuple[str, list[str], Optional[str]]:
    """
    检查组间轮动数据质量

    Args:
        pool_states: 所有池子状态
        valid_groups: 有效池子状态
        registry: 配置注册表

    Returns:
        (data_status, missing_groups, partial_reason)

    Quality Rules:
        - valid_groups >= MIN_VALID_GROUPS → ok
        - valid_groups < MIN_VALID_GROUPS → insufficient_data
    """
    # 识别缺失池子
    expected_groups = []
    if registry:
        # 只期望 can_be_benchmark=True 的池子
        for universe in registry.get_all_universes():
            if universe.can_be_benchmark:
                expected_groups.append(universe.universe_id)
    else:
        # 期望所有输入池子
        expected_groups = list(pool_states.keys())

    missing_groups = [
        group_id
        for group_id in expected_groups
        if group_id not in valid_groups
    ]

    # 判断数据状态
    if len(valid_groups) < MIN_VALID_GROUPS:
        return (
            "insufficient_data",
            missing_groups,
            f"valid_groups({len(valid_groups)}) < min_valid_groups({MIN_VALID_GROUPS})",
        )

    if missing_groups:
        return "ok", missing_groups, None

    return "ok", [], None


def _empty_rotation_result(
    trade_date: str,
    missing_groups: list[str],
    partial_reason: Optional[str],
) -> GroupRotation:
    """返回空轮动结果"""
    return GroupRotation(
        trade_date=trade_date,
        strongest_group="",
        weakest_group="",
        group_ranking=[],
        spreads={},
        core_vs_theme_spread=None,
        core_vs_chain_spread=None,
        core_vs_trading_spread=None,
        group_medians={},
        data_status="insufficient_data",
        missing_groups=missing_groups,
        partial_reason=partial_reason,
    )