"""
事件研究模块

对极端背离日期，生成 T-N 到 T+N 的路径，
看背离后是修复、延续还是反转。
"""

from typing import Optional

from src.history_analysis.models import HistoryRow, EventPath


def build_event_paths(
    event_dates: list[str],
    rows: list[HistoryRow],
    window: int = 5,
) -> list[EventPath]:
    """
    为每个事件日期生成 T-window 到 T+window 的路径。

    Args:
        event_dates: 极端背离日期列表 (YYYYMMDD)
        rows: 按 date 排序的 HistoryRow 列表
        window: 前后查看的交易日数

    Returns:
        EventPath 列表，每个事件日期生成 (2*window+1) 行
    """
    date_index = {row.date: i for i, row in enumerate(rows)}
    paths: list[EventPath] = []

    for event_date in event_dates:
        if event_date not in date_index:
            continue

        center_idx = date_index[event_date]

        for offset in range(-window, window + 1):
            idx = center_idx + offset
            if 0 <= idx < len(rows):
                row = rows[idx]
                excess = None
                if row.anchor_return is not None and row.industry_chain_median is not None:
                    excess = round(row.anchor_return - row.industry_chain_median, 6)

                paths.append(EventPath(
                    event_date=event_date,
                    offset=offset,
                    date=row.date,
                    anchor_return=row.anchor_return,
                    chain_median=row.industry_chain_median,
                    excess=excess,
                ))
            else:
                paths.append(EventPath(
                    event_date=event_date,
                    offset=offset,
                    date=None,
                    anchor_return=None,
                    chain_median=None,
                    excess=None,
                ))

    return paths
