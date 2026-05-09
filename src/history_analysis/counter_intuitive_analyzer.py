"""反直觉信号分析。"""

from src.history_analysis.display import format_signal_label
from src.history_analysis.models import CounterIntuitiveSignal, SignalLift


POSITIVE_INTUITION = {
    "行业Beta为正",
    "个股Alpha为正",
    "跑赢主线池",
    "跑赢核心池",
    "跑赢核心同类",
    "放量上涨",
    "资金价格共振",
    "主力资金领先",
    "处于行业前排",
    "主线池强于主题情绪",
    "核心池强于主题",
}

NEGATIVE_INTUITION = {
    "行业Beta为负",
    "个股Alpha为负",
    "跑输主线池",
    "跑输核心池",
    "跑输核心同类",
    "放量下跌",
    "资金价格背离",
    "行业强但个股弱",
}


def intuitive_direction(label: str) -> str:
    if label in POSITIVE_INTUITION:
        return "positive"
    if label in NEGATIVE_INTUITION:
        return "negative"
    return "neutral"


def actual_direction(avg_next_1d: float | None, delta_pp: float | None) -> str:
    value = delta_pp if delta_pp is not None else avg_next_1d
    if value is None:
        return "neutral"
    if value > 0.1:
        return "positive"
    if value < -0.1:
        return "negative"
    return "neutral"


def identify_counter_intuitive_signals(
    signal_lifts: list[SignalLift],
    min_count: int = 5,
) -> list[CounterIntuitiveSignal]:
    """识别直觉方向与实际历史表现相反的信号。"""
    result: list[CounterIntuitiveSignal] = []

    for lift in signal_lifts:
        if lift.appearance_count < min_count:
            continue

        expected = intuitive_direction(lift.label)
        actual = actual_direction(lift.avg_next_1d, lift.avg_next_1d_delta_pp)
        if expected == "neutral" or actual == "neutral" or expected == actual:
            continue

        verdict = (
            "counter_intuitive_opportunity"
            if expected == "negative" and actual == "positive"
            else "signal_trap"
        )
        delta = lift.avg_next_1d_delta_pp or 0.0
        severity = 2.0 if (expected, actual) in {
            ("positive", "negative"),
            ("negative", "positive"),
        } else 1.0
        degree = round(abs(delta) * severity, 6)
        display_label = format_signal_label(lift.label)
        if verdict == "counter_intuitive_opportunity":
            explanation = (
                f"直觉偏风险，但历史表现为正，可能是反直觉机会"
            )
        else:
            explanation = (
                f"直觉偏正面，但历史表现偏弱，出现时需防信号陷阱"
            )

        result.append(CounterIntuitiveSignal(
            label=lift.label,
            display_label=display_label,
            category=lift.category,
            appearance_count=lift.appearance_count,
            avg_next_1d=lift.avg_next_1d,
            win_rate_1d=lift.win_rate_1d,
            avg_next_1d_delta_pp=lift.avg_next_1d_delta_pp,
            intuitive_direction=expected,
            actual_direction=actual,
            degree=degree,
            verdict=verdict,
            explanation=explanation,
        ))

    return sorted(result, key=lambda s: s.degree, reverse=True)
