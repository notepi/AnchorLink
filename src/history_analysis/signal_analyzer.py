"""
信号 lift 分析模块

计算每个信号标签出现后的前瞻收益、胜率、相对 baseline 的 lift。
"""

import json
from typing import Optional

from src.history_analysis.models import HistoryRow, SignalLift, SignalPair


def _parse_signal_pairs(row: HistoryRow) -> list[tuple[str, str]]:
    """
    从 HistoryRow 提取 (label, category) 列表。
    优先使用 signal_pairs JSON；若解析失败则 fallback 到 signal_labels + signal_categories。
    """
    if row.signal_pairs:
        try:
            pairs = json.loads(row.signal_pairs)
            result = []
            for p in pairs:
                label = p.get("label", "").strip()
                category = p.get("category", "").strip()
                if label:
                    result.append((label, category))
            if result:
                return result
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback: 从 signal_labels + signal_categories 重建
    labels = [l.strip() for l in row.signal_labels.split(",") if l.strip()] if row.signal_labels else []
    categories = [c.strip() for c in row.signal_categories.split(",") if c.strip()] if row.signal_categories else []
    result = []
    for i, label in enumerate(labels):
        cat = categories[i] if i < len(categories) else ""
        result.append((label, cat))
    return result


def explode_signals(rows: list[HistoryRow]) -> list[tuple[str, int]]:
    """
    展开 signal_labels：每行 → 多个 (label, row_index) 对。

    signal_labels 是逗号分隔的字符串。
    """
    pairs: list[tuple[str, int]] = []
    for i, row in enumerate(rows):
        if not row.signal_labels:
            continue
        for label in row.signal_labels.split(","):
            label = label.strip()
            if label:
                pairs.append((label, i))
    return pairs


def explode_signals_with_category(rows: list[HistoryRow]) -> list[tuple[str, str, int]]:
    """
    展开 signal_pairs：每行 → 多个 (label, category, row_index) 三元组。
    """
    triples: list[tuple[str, str, int]] = []
    for i, row in enumerate(rows):
        for label, category in _parse_signal_pairs(row):
            triples.append((label, category, i))
    return triples


def _safe_avg(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _safe_win_rate(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(1 for v in values if v > 0) / len(values), 6)


def build_signal_lifts(
    rows: list[HistoryRow],
    min_count: int = 5,
) -> list[SignalLift]:
    """
    计算每个信号标签的 lift。

    Args:
        rows: 历史汇总行
        min_count: 最低出现次数阈值，低于此值 min_count_passed=False
    """
    triples = explode_signals_with_category(rows)

    # 按 label 分组，同时记录 category
    label_data: dict[str, tuple[str, list[int]]] = {}
    for label, category, idx in triples:
        if label not in label_data:
            label_data[label] = (category, [])
        label_data[label][1].append(idx)

    # 计算 baseline（全样本）
    all_next_1d = [r.next_1d_return for r in rows if r.next_1d_return is not None]
    baseline_avg = _safe_avg(all_next_1d)
    baseline_wr = _safe_win_rate(all_next_1d)

    lifts: list[SignalLift] = []

    for label, (category, indices) in sorted(label_data.items()):
        signal_rows = [rows[i] for i in indices]

        next_1ds = [r.next_1d_return for r in signal_rows if r.next_1d_return is not None]
        next_3ds = [r.next_3d_return for r in signal_rows if r.next_3d_return is not None]
        next_5ds = [r.next_5d_return for r in signal_rows if r.next_5d_return is not None]
        excess_1ds = [r.next_1d_excess_vs_chain for r in signal_rows if r.next_1d_excess_vs_chain is not None]

        avg_next_1d = _safe_avg(next_1ds)
        avg_next_3d = _safe_avg(next_3ds)
        avg_next_5d = _safe_avg(next_5ds)
        avg_next_1d_excess = _safe_avg(excess_1ds)
        wr = _safe_win_rate(next_1ds)

        # delta_pp: signal_avg - baseline，简单差值，避免 baseline 接近 0 时 ratio lift 误导
        delta_pp: Optional[float] = None
        if avg_next_1d is not None and baseline_avg is not None:
            delta_pp = round(avg_next_1d - baseline_avg, 6)

        # lift 计算（ratio，baseline 接近 0 时需参考 delta_pp）
        lift_next_1d: Optional[float] = None
        if avg_next_1d is not None and baseline_avg is not None:
            if baseline_avg != 0:
                lift_next_1d = round((avg_next_1d - baseline_avg) / abs(baseline_avg), 6)
            else:
                lift_next_1d = round(avg_next_1d - baseline_avg, 6)

        lift_wr: Optional[float] = None
        if wr is not None and baseline_wr is not None:
            lift_wr = round(wr - baseline_wr, 6)

        lifts.append(SignalLift(
            label=label,
            category=category,
            appearance_count=len(indices),
            avg_next_1d=avg_next_1d,
            avg_next_3d=avg_next_3d,
            avg_next_5d=avg_next_5d,
            avg_next_1d_excess=avg_next_1d_excess,
            win_rate_1d=wr,
            baseline_avg_next_1d=baseline_avg,
            baseline_win_rate_1d=baseline_wr,
            avg_next_1d_delta_pp=delta_pp,
            lift_next_1d=lift_next_1d,
            lift_win_rate=lift_wr,
            min_count_passed=len(indices) >= min_count,
        ))

    return lifts
