"""面向操盘工作台的历史分析视图模型。"""

from itertools import combinations
from typing import Optional

from src.history_analysis.conditional_signal_analyzer import _safe_avg, _safe_win_rate
from src.history_analysis.display import business_tag_for_label, format_signal_label
from src.history_analysis.models import (
    ConditionalSignalEffect,
    CounterIntuitiveSignal,
    HistoryRegime,
    HistoryRow,
    OperatorConfirmationPair,
    OperatorHistoryView,
    OperatorPlaybook,
    OperatorSignalRole,
    RollingMetrics,
    SignalLift,
)
from src.history_analysis.signal_analyzer import _parse_signal_pairs


def _valid_rows(rows: list[HistoryRow]) -> list[HistoryRow]:
    return [
        r for r in rows
        if r.data_quality_status != "insufficient_data" and r.next_1d_return is not None
    ]


def _latest_rolling(rolling: list[RollingMetrics]) -> RollingMetrics | None:
    if not rolling:
        return None
    return sorted(rolling, key=lambda r: r.date)[-1]


def _is_rolling_deteriorating(rolling: list[RollingMetrics]) -> bool:
    if not rolling:
        return True
    sorted_rows = sorted(rolling, key=lambda r: r.date)
    latest = sorted_rows[-1]
    previous = sorted_rows[-2] if len(sorted_rows) >= 2 else None
    if latest.excess_5d is not None and latest.excess_10d is not None:
        if latest.excess_5d < 0 and latest.excess_10d < 0:
            return True
    if previous and previous.excess_10d is not None and latest.excess_10d is not None:
        if previous.excess_10d >= 0 and latest.excess_10d < 0:
            return True
    if latest.risk_high_streak >= 3:
        return True
    if latest.outperform_streak <= -3:
        return True
    return False


def _is_rolling_stable(rolling: list[RollingMetrics]) -> bool:
    if not rolling:
        return False
    sorted_rows = sorted(rolling, key=lambda r: r.date)
    latest = sorted_rows[-1]
    recent = sorted_rows[-3:]
    negative_5d = sum(1 for r in recent if r.excess_5d is not None and r.excess_5d < 0)
    return (
        latest.excess_10d is not None
        and latest.excess_10d >= 0
        and negative_5d <= 1
        and latest.risk_high_streak < 3
    )


def _derive_trend(label: str, rows: list[HistoryRow], lift: SignalLift) -> str:
    matching: list[HistoryRow] = []
    for row in sorted(_valid_rows(rows), key=lambda r: r.date):
        if any(pair_label == label for pair_label, _ in _parse_signal_pairs(row)):
            matching.append(row)
    if len(matching) < 20:
        return "trend_insufficient"

    recent = matching[-20:]
    historical = matching[:-20]
    recent_avg = _safe_avg([r.next_1d_return for r in recent if r.next_1d_return is not None])
    historical_avg = _safe_avg([r.next_1d_return for r in historical if r.next_1d_return is not None])
    if recent_avg is None or historical_avg is None:
        return "trend_insufficient"
    diff = recent_avg - historical_avg
    if abs(diff) < 0.2:
        return "trend_stable"
    return "trend_improving" if diff > 0 else "trend_deteriorating"


def _build_regime(
    rows: list[HistoryRow],
    rolling: list[RollingMetrics],
    has_primary_trigger: bool,
) -> HistoryRegime:
    sample_days = len(_valid_rows(rows))
    latest = _latest_rolling(rolling)
    deteriorating = _is_rolling_deteriorating(rolling)
    stable = _is_rolling_stable(rolling)
    reasons: list[str] = []
    risk_points: list[str] = []

    confidence = "medium"
    status = "weakening"

    if sample_days < 20:
        confidence = "low"
        status = "invalid"
        risk_points.append(f"有效样本仅 {sample_days} 天")
    elif sample_days < 40:
        confidence = "medium"
        risk_points.append(f"有效样本 {sample_days} 天，统计结论需降级")

    if deteriorating:
        risk_points.append("滚动超额收益恶化")
        status = "weakening" if has_primary_trigger else "invalid"
        if confidence == "high":
            confidence = "medium"
    elif stable and has_primary_trigger:
        status = "stable"
        if sample_days >= 40:
            confidence = "high"
        reasons.append("滚动指标稳定且存在主触发信号")

    if not has_primary_trigger:
        risk_points.append("当前无明确主触发信号")

    if status == "stable":
        headline = "历史规律稳定，可作为观察依据"
    elif status == "weakening":
        headline = "近期指标转弱，历史结论降级使用"
    else:
        headline = "历史规律近期失效或样本不足，建议等待"

    return HistoryRegime(
        confidence=confidence,
        status=status,
        headline=headline,
        reasons=reasons,
        risk_points=risk_points[:5],
        latest_rolling_date=latest.date if latest else None,
    )


def _best_condition(
    label: str,
    conditional_effects: list[ConditionalSignalEffect],
    verdict: str = "works_in_condition",
) -> ConditionalSignalEffect | None:
    candidates = [
        e for e in conditional_effects
        if e.label == label and e.verdict == verdict and e.avg_next_1d_delta_pp_vs_quadrant is not None
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda e: e.avg_next_1d_delta_pp_vs_quadrant or 0, reverse=True)[0]


def _build_signal_roles(
    rows: list[HistoryRow],
    signal_lifts: list[SignalLift],
    counter_intuitive: list[CounterIntuitiveSignal],
    conditional_effects: list[ConditionalSignalEffect],
) -> list[OperatorSignalRole]:
    counter_by_label = {s.label: s for s in counter_intuitive}
    roles: list[OperatorSignalRole] = []

    for lift in signal_lifts:
        trend = _derive_trend(lift.label, rows, lift)
        insight_type = "normal"
        if lift.label in counter_by_label:
            insight_type = "counter_intuitive" if counter_by_label[lift.label].verdict == "counter_intuitive_opportunity" else "trap"

        delta = lift.avg_next_1d_delta_pp or 0.0
        win_rate = lift.win_rate_1d or 0.0
        role = "context_only"
        if not lift.min_count_passed or lift.appearance_count < 5:
            role = "ignore"
        elif (
            lift.appearance_count >= 10
            and delta > 0.5
            and win_rate >= 0.5
            and trend != "trend_deteriorating"
            and insight_type != "trap"
        ):
            role = "primary_trigger"
        elif delta < 0 or win_rate < 0.5 or insight_type == "trap":
            role = "risk_invalidator"
        elif lift.appearance_count >= 8 and delta > 0:
            role = "confirmation"

        best = _best_condition(lift.label, conditional_effects)
        priority = round(delta * 10 + win_rate * 3 + min(lift.appearance_count, 30) / 10, 6)
        if insight_type == "counter_intuitive":
            priority += 5
        if role == "risk_invalidator":
            priority = round(abs(delta) * 10 + (1 - win_rate) * 3, 6)

        display_label = format_signal_label(lift.label)
        if role == "primary_trigger":
            conclusion = "可作为重点观察信号"
        elif role == "confirmation":
            conclusion = "适合作为确认条件"
        elif role == "risk_invalidator":
            conclusion = "出现时优先降级或回避"
        elif role == "context_only":
            conclusion = "仅解释环境，不直接触发行动"
        else:
            conclusion = "样本不足，暂不进入主视图"

        if insight_type == "counter_intuitive":
            reason = "直觉偏风险但历史表现强"
        elif insight_type == "trap":
            reason = "直觉偏正面但历史表现弱"
        elif best:
            reason = f"在「{best.quadrant}」条件下效果较好"
        else:
            reason = f"相对基线 {delta:+.2f}pp，胜率 {win_rate * 100:.0f}%"

        roles.append(OperatorSignalRole(
            label=lift.label,
            display_label=display_label,
            category=lift.category,
            business_tag=business_tag_for_label(lift.label, lift.category),
            role=role,
            insight_type=insight_type,
            priority=priority,
            count=lift.appearance_count,
            avg_next_1d=lift.avg_next_1d,
            delta_pp=lift.avg_next_1d_delta_pp,
            win_rate=lift.win_rate_1d,
            trend=trend,
            best_condition_quadrant=best.quadrant if best else None,
            conclusion=conclusion,
            reason=reason,
        ))

    return sorted(roles, key=lambda r: (r.role == "ignore", -r.priority, r.display_label))


def _build_confirmation_pairs(
    rows: list[HistoryRow],
    signal_lifts: list[SignalLift],
    min_count: int,
) -> list[OperatorConfirmationPair]:
    signal_by_label = {s.label: s for s in signal_lifts}
    combo_returns: dict[tuple[str, str], list[float]] = {}

    for row in _valid_rows(rows):
        labels = sorted({label for label, _ in _parse_signal_pairs(row)})
        for left, right in combinations(labels, 2):
            combo_returns.setdefault((left, right), []).append(row.next_1d_return)  # type: ignore[arg-type]

    result: list[OperatorConfirmationPair] = []
    for labels, returns in combo_returns.items():
        if len(returns) < min_count:
            continue
        singles = [signal_by_label.get(label) for label in labels]
        if any(s is None or s.avg_next_1d is None for s in singles):
            continue
        avg_return = _safe_avg(returns)
        if avg_return is None:
            continue
        best_single = max((s for s in singles if s is not None), key=lambda s: s.avg_next_1d or -999)
        synergy = round(avg_return - (best_single.avg_next_1d or avg_return), 6)
        win_rate = _safe_win_rate(returns)
        if synergy <= 0 or (win_rate is not None and win_rate < 0.5):
            continue

        display_labels = [format_signal_label(label) for label in labels]
        result.append(OperatorConfirmationPair(
            labels=list(labels),
            display_labels=display_labels,
            count=len(returns),
            avg_next_1d=avg_return,
            win_rate=win_rate,
            best_single_label=best_single.label,
            synergy=synergy,
            verdict="useful_confirmation",
            conclusion=f"{' + '.join(display_labels)} 比最强单信号多 {synergy:+.2f}pp",
        ))

    return sorted(result, key=lambda p: p.synergy, reverse=True)[:3]


def _build_playbook(
    regime: HistoryRegime,
    roles: list[OperatorSignalRole],
    pairs: list[OperatorConfirmationPair],
    sample_days: int,
) -> OperatorPlaybook:
    primary = [r for r in roles if r.role == "primary_trigger"][:3]
    confirmations = [r for r in roles if r.role == "confirmation"][:3]
    invalidators = [r for r in roles if r.role == "risk_invalidator"][:3]

    if regime.status == "invalid" or (invalidators and not primary):
        stance = "wait"
        headline = "等待更明确的主触发信号"
    elif primary and regime.status == "stable":
        stance = "active_watch"
        headline = "主触发有效，允许积极观察"
    else:
        stance = "cautious_watch"
        headline = "历史规律降级使用，只做谨慎观察"

    watch_for = [f"出现「{r.display_label}」" for r in primary] or ["等待主触发信号重新出现"]
    confirmation_text = [p.conclusion for p in pairs]
    confirmation_text.extend(f"用「{r.display_label}」确认" for r in confirmations)
    if not confirmation_text:
        confirmation_text = ["当前无有效组合确认"]

    invalidations = [f"出现「{r.display_label}」" for r in invalidators]
    invalidations.extend(regime.risk_points[:2])
    if not invalidations:
        invalidations = ["5日与10日超额同时转负"]

    if sample_days < 20:
        sample_note = f"有效样本 {sample_days} 天，统计意义不足"
    elif sample_days < 40:
        sample_note = f"有效样本 {sample_days} 天，结论需谨慎参考"
    else:
        sample_note = f"有效样本 {sample_days} 天"

    return OperatorPlaybook(
        stance=stance,
        headline=headline,
        watch_for=watch_for[:3],
        confirmations=confirmation_text[:3],
        invalidations=invalidations[:3],
        sample_note=sample_note,
    )


def build_operator_playbook(
    rows: list[HistoryRow],
    rolling: list[RollingMetrics],
    signal_lifts: list[SignalLift],
    counter_intuitive: list[CounterIntuitiveSignal],
    conditional_effects: list[ConditionalSignalEffect],
    min_signal_count: int = 5,
    min_combo_count: int = 8,
) -> OperatorHistoryView:
    """生成历史验证工作台使用的后端视图模型。"""
    valid_rows = _valid_rows(rows)
    date_range = sorted(r.date for r in rows)
    roles = _build_signal_roles(rows, signal_lifts, counter_intuitive, conditional_effects)
    has_primary = any(r.role == "primary_trigger" for r in roles)
    regime = _build_regime(rows, rolling, has_primary)
    pairs = _build_confirmation_pairs(rows, signal_lifts, min_combo_count)
    playbook = _build_playbook(regime, roles, pairs, len(valid_rows))

    return OperatorHistoryView(
        as_of_date=date_range[-1] if date_range else "",
        date_range_start=date_range[0] if date_range else "",
        date_range_end=date_range[-1] if date_range else "",
        sample_days=len(valid_rows),
        regime=regime,
        playbook=playbook,
        signal_roles=[r for r in roles if r.role != "ignore"],
        counter_intuitive_signals=[
            s for s in counter_intuitive if s.verdict == "counter_intuitive_opportunity"
        ][:5],
        signal_traps=[
            s for s in counter_intuitive if s.verdict == "signal_trap"
        ][:5],
        conditional_effects=conditional_effects,
        confirmation_pairs=pairs,
    )
