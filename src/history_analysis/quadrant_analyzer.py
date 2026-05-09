"""
四象限分析模块

按 industry_beta × anchor_alpha 分组，统计前瞻收益和胜率。
"""

from typing import Optional

from src.history_analysis.models import HistoryRow, QuadrantStats


def classify_quadrant(industry_beta: str, anchor_alpha: str) -> str:
    """
    将 (beta, alpha) 组合映射为中文标签。

    9 种组合：4 个干净象限 + 5 个含 neutral 的。
    """
    beta_label = {"positive": "行业强", "neutral": "行业中", "negative": "行业弱"}
    alpha_label = {"positive": "个股强", "neutral": "个股中", "negative": "个股弱"}

    b = beta_label.get(industry_beta, industry_beta)
    a = alpha_label.get(anchor_alpha, anchor_alpha)
    return f"{b}+{a}"


def _safe_avg(values: list[float]) -> Optional[float]:
    """安全平均，空列表返回 None"""
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _safe_win_rate(values: list[float]) -> Optional[float]:
    """胜率：正收益占比，空列表返回 None"""
    if not values:
        return None
    return round(sum(1 for v in values if v > 0) / len(values), 6)


ALL_QUADRANTS = [
    classify_quadrant(b, a)
    for b in ("positive", "neutral", "negative")
    for a in ("positive", "neutral", "negative")
]


def build_quadrant_stats(rows: list[HistoryRow]) -> list[QuadrantStats]:
    """
    按象限分组统计前瞻收益和胜率。

    固定输出全部 9 种象限，未出现的 count=0 其余 None。
    只统计有有效 next_1d_return 的行。
    """
    groups: dict[str, list[HistoryRow]] = {q: [] for q in ALL_QUADRANTS}

    for row in rows:
        if row.next_1d_return is None:
            continue
        q = classify_quadrant(row.industry_beta, row.anchor_alpha)
        if q in groups:
            groups[q].append(row)

    stats: list[QuadrantStats] = []

    for quadrant in ALL_QUADRANTS:
        group_rows = groups[quadrant]

        if not group_rows:
            stats.append(QuadrantStats(
                quadrant=quadrant,
                count=0,
                avg_next_1d=None,
                avg_next_3d=None,
                avg_next_5d=None,
                avg_next_1d_excess=None,
                win_rate_1d=None,
                avg_relative_strength=None,
            ))
            continue

        next_1ds = [r.next_1d_return for r in group_rows if r.next_1d_return is not None]
        next_3ds = [r.next_3d_return for r in group_rows if r.next_3d_return is not None]
        next_5ds = [r.next_5d_return for r in group_rows if r.next_5d_return is not None]
        excess_1ds = [r.next_1d_excess_vs_chain for r in group_rows if r.next_1d_excess_vs_chain is not None]
        rel_strengths = [r.relative_strength_vs_industry_chain for r in group_rows if r.relative_strength_vs_industry_chain is not None]

        stats.append(QuadrantStats(
            quadrant=quadrant,
            count=len(group_rows),
            avg_next_1d=_safe_avg(next_1ds),
            avg_next_3d=_safe_avg(next_3ds),
            avg_next_5d=_safe_avg(next_5ds),
            avg_next_1d_excess=_safe_avg(excess_1ds),
            win_rate_1d=_safe_win_rate(next_1ds),
            avg_relative_strength=_safe_avg(rel_strengths),
        ))

    return stats
