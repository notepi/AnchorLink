"""象限条件下的信号效果分析。"""

from typing import Optional

from src.history_analysis.display import format_signal_label
from src.history_analysis.models import ConditionalSignalEffect, HistoryRow, SignalLift
from src.history_analysis.quadrant_analyzer import ALL_QUADRANTS, classify_quadrant
from src.history_analysis.signal_analyzer import _parse_signal_pairs


def _safe_avg(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _safe_win_rate(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(1 for v in values if v > 0) / len(values), 6)


def build_conditional_signal_effects(
    rows: list[HistoryRow],
    signal_lifts: list[SignalLift],
    min_count: int = 3,
) -> list[ConditionalSignalEffect]:
    """计算每个信号在 9 象限内相对该象限基线的效果。"""
    valid_rows = [r for r in rows if r.next_1d_return is not None]
    lift_by_label = {s.label: s for s in signal_lifts}

    quadrant_rows: dict[str, list[HistoryRow]] = {q: [] for q in ALL_QUADRANTS}
    for row in valid_rows:
        q = classify_quadrant(row.industry_beta, row.anchor_alpha)
        if q in quadrant_rows:
            quadrant_rows[q].append(row)

    result: list[ConditionalSignalEffect] = []
    for quadrant, q_rows in quadrant_rows.items():
        q_returns = [r.next_1d_return for r in q_rows if r.next_1d_return is not None]
        q_baseline = _safe_avg(q_returns)
        signal_returns: dict[str, tuple[str, list[float]]] = {}

        for row in q_rows:
            for label, category in _parse_signal_pairs(row):
                if row.next_1d_return is None:
                    continue
                if label not in signal_returns:
                    signal_returns[label] = (category, [])
                signal_returns[label][1].append(row.next_1d_return)

        for label, (category, returns) in signal_returns.items():
            if len(returns) < min_count:
                continue
            avg_return = _safe_avg(returns)
            win_rate = _safe_win_rate(returns)
            delta = None
            if avg_return is not None and q_baseline is not None:
                delta = round(avg_return - q_baseline, 6)

            if delta is None:
                verdict = "insufficient"
            elif delta > 0.3 and (win_rate or 0) >= 0.5:
                verdict = "works_in_condition"
            elif delta < -0.3 or (win_rate is not None and win_rate < 0.45):
                verdict = "fails_in_condition"
            else:
                verdict = "insufficient"

            result.append(ConditionalSignalEffect(
                label=label,
                display_label=format_signal_label(label),
                category=category,
                quadrant=quadrant,
                quadrant_count=len(q_rows),
                signal_in_quadrant_count=len(returns),
                avg_next_1d_in_quadrant=avg_return,
                win_rate_in_quadrant=win_rate,
                avg_next_1d_delta_pp_vs_quadrant=delta,
                overall_avg_next_1d=lift_by_label.get(label).avg_next_1d if label in lift_by_label else None,
                verdict=verdict,
            ))

    return sorted(
        result,
        key=lambda e: (
            e.quadrant,
            -(e.avg_next_1d_delta_pp_vs_quadrant or 0),
            -e.signal_in_quadrant_count,
        ),
    )
