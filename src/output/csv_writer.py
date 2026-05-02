"""
CSV 输出模块

职责：
  - 生成 peer_matrix.csv 文件
  - 同一股票在不同池子中占多行（每个 membership 一行）
  - 包含 universe, symbol, role, relevance, 行情数据, 排名等字段

按 PRD 第17.2节定义的 CSV 结构
"""

import csv
from pathlib import Path
from typing import Optional

from src.config.loader import PoolRegistry, Membership, Instrument
from src.pool_state.models import MemberData
from src.anchor_position.relative_strength import RelativeStrength


# ============================================================
# CSV 字段定义
# ============================================================

CSV_FIELDS = [
    "universe",
    "symbol",
    "name",
    "role",
    "relevance",
    "include_in_benchmark",
    "include_in_ranking",
    "pct_chg",
    "amount",
    "turnover_rate",
    "fund_flow",
    "return_rank",
    "valuation_percentile",
]


# ============================================================
# CSV 行构建
# ============================================================

def build_csv_row(
    membership: Membership,
    instrument: Optional[Instrument],
    member_data: Optional[MemberData],
    ranking_data: Optional[dict],
) -> dict:
    """
    构建 CSV 单行数据

    Args:
        membership: 成员关系
        instrument: 证券主数据
        member_data: 当日行情数据
        ranking_data: 排名数据（可选）

    Returns:
        CSV 行 dict
    """
    row = {
        "universe": membership.universe_id,
        "symbol": membership.symbol,
        "name": instrument.name if instrument else "",
        "role": membership.role,
        "relevance": membership.relevance,
        "include_in_benchmark": membership.include_in_benchmark,
        "include_in_ranking": membership.include_in_ranking,
        "pct_chg": member_data.pct_chg if member_data and member_data.pct_chg is not None else "",
        "amount": member_data.amount if member_data and member_data.amount is not None else "",
        "turnover_rate": member_data.turnover_rate if member_data and member_data.turnover_rate is not None else "",
        "fund_flow": member_data.net_mf_amount if member_data and member_data.net_mf_amount is not None else "",
        "return_rank": ranking_data.get("rank_return", "") if ranking_data else "",
        "valuation_percentile": ranking_data.get("valuation_percentile", "") if ranking_data else "",
    }

    return row


# ============================================================
# CSV 写入
# ============================================================

def write_peer_matrix(
    registry: PoolRegistry,
    market_data: dict[str, MemberData],
    anchor_positions: dict[str, RelativeStrength],
    path: str | Path,
) -> None:
    """
    写入 peer_matrix.csv 文件

    Args:
        registry: 配置注册表
        market_data: 所有成员的当日行情数据
        anchor_positions: 相对位置数据（用于获取排名）
        path: 输出路径

    关键特性：
        - 遍历所有 Membership(include_in_report=true)
        - 同一股票在不同 universe 中占多行
    """
    path = Path(path)

    # 确保目录存在
    path.parent.mkdir(parents=True, exist_ok=True)

    # 收集所有 CSV 行
    rows = []

    for universe in registry.get_all_universes():
        universe_id = universe.universe_id

        # 获取该池子的所有成员
        memberships = registry.get_members(universe_id)

        for membership in memberships:
            # 只输出 include_in_report=true 的成员
            if not membership.include_in_report:
                continue

            # 获取证券主数据
            instrument = registry.instruments.get(membership.symbol)

            # 获取当日行情数据
            member_data = market_data.get(membership.symbol)

            # 获取排名数据（从 anchor_positions）
            ranking_data = _get_ranking_data(membership.symbol, universe_id, anchor_positions)

            # 构建行
            row = build_csv_row(membership, instrument, member_data, ranking_data)
            rows.append(row)

    # 写入 CSV
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _get_ranking_data(
    symbol: str,
    universe_id: str,
    anchor_positions: dict[str, RelativeStrength],
) -> Optional[dict]:
    """
    获取排名数据

    Args:
        symbol: 股票代码
        universe_id: 池子ID
        anchor_positions: 相对位置数据

    Returns:
        排名数据 dict（仅对 Anchor 有效）

    注意：
        - 目前只对 Anchor 本身的排名有效
        - 其他股票的排名需要额外计算（暂不实现）
    """
    # 从 anchor_positions 获取（仅对 Anchor）
    position = anchor_positions.get(universe_id)
    if position:
        return {
            "rank_return": position.rank_return,
            "rank_volume": position.rank_volume,
            "rank_turnover": position.rank_turnover,
            "rank_fund": position.rank_fund,
            "valuation_percentile": position.valuation_percentile,
        }

    return None