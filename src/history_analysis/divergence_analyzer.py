"""
极端背离分析模块

筛选 |anchor_return - industry_chain_median| 超过阈值的日期。
"""

from typing import Optional

from src.history_analysis.models import HistoryRow, ExtremeDivergence


def compute_divergence(row: HistoryRow) -> Optional[float]:
    """计算 anchor_return - industry_chain_median"""
    if row.anchor_return is None or row.industry_chain_median is None:
        return None
    return round(row.anchor_return - row.industry_chain_median, 6)


def find_extreme_divergences(
    rows: list[HistoryRow],
    threshold: float = 8.0,
) -> list[ExtremeDivergence]:
    """
    筛选极端背离日期，按 |divergence| 降序。

    Args:
        rows: 历史汇总行
        threshold: 绝对值阈值（百分点）
    """
    divergences: list[ExtremeDivergence] = []

    for row in rows:
        div = compute_divergence(row)
        if div is None:
            continue
        if abs(div) >= threshold:
            divergences.append(ExtremeDivergence(
                date=row.date,
                anchor_return=row.anchor_return,
                industry_chain_median=row.industry_chain_median,
                divergence=div,
                industry_beta=row.industry_beta,
                anchor_alpha=row.anchor_alpha,
                risk_level=row.risk_level,
                signal_labels=row.signal_labels,
            ))

    divergences.sort(key=lambda d: abs(d.divergence), reverse=True)
    return divergences
