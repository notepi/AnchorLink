"""历史性格画像分析器。

从已有分析结果聚合生成纯历史视角的个股性格档案，不含今日判断。
"""

import statistics
from typing import Optional

from src.history_analysis.conditional_signal_analyzer import _safe_avg, _safe_win_rate
from src.history_analysis.display import format_signal_label
from src.history_analysis.models import (
    ConditionEffect,
    ConditionalSignalEffect,
    CounterIntuitiveSignal,
    ExtremeDivergence,
    EventPath,
    HistoryPersonalityProfile,
    HistoryRow,
    PathPattern,
    PathPatternPoint,
    PersonalityPattern,
    PersonalityStability,
    PersonalitySummary,
    PersonalitySummaryMetrics,
    QuadrantStats,
    RelationshipPattern,
    RelationshipProfile,
    SignalLift,
)


def _valid_rows(rows: list[HistoryRow]) -> list[HistoryRow]:
    return [
        r for r in rows
        if r.data_quality_status != "insufficient_data" and r.next_1d_return is not None
    ]


def _compute_baseline(rows: list[HistoryRow]) -> tuple[float | None, float | None]:
    valid = _valid_rows(rows)
    returns = [r.next_1d_return for r in valid if r.next_1d_return is not None]
    baseline_avg = _safe_avg(returns)
    baseline_win_rate = _safe_win_rate(returns)
    return baseline_avg, baseline_win_rate


def _shrink_effect_score(avg_delta: float | None, count: int) -> float | None:
    if avg_delta is None:
        return None
    shrink_factor = min(1.0, (count / 20.0) ** 0.5)
    return round(avg_delta * shrink_factor, 6)


def _build_personality_patterns(
    signal_lifts: list[SignalLift],
    quadrant_stats: list[QuadrantStats],
    counter_intuitive: list[CounterIntuitiveSignal],
    conditional_effects: list[ConditionalSignalEffect],
    rows: list[HistoryRow],
    baseline_avg: float | None,
) -> tuple[list[PersonalityPattern], list[PersonalityPattern], list[PersonalityPattern], list[PersonalityPattern]]:
    counter_by_label = {s.label: s for s in counter_intuitive}
    conditional_by_label: dict[str, list[ConditionalSignalEffect]] = {}
    for e in conditional_effects:
        conditional_by_label.setdefault(e.label, []).append(e)

    all_patterns: list[PersonalityPattern] = []

    for lift in signal_lifts:
        label = lift.label
        display_label = format_signal_label(label)
        count = lift.appearance_count
        avg_next_1d = lift.avg_next_1d
        avg_next_1d_delta_pp = lift.avg_next_1d_delta_pp
        win_rate_1d = lift.win_rate_1d

        if count < 5:
            continue

        effect_score = _shrink_effect_score(avg_next_1d_delta_pp, count)
        significance = "weak"
        confidence = "low"

        if count >= 20 and effect_score is not None and abs(effect_score) >= 0.5:
            significance = "strong"
            confidence = "high"
        elif count >= 10 and effect_score is not None and abs(effect_score) >= 0.8:
            significance = "suggestive"
            confidence = "medium"

        habit_type = "context"
        if label in counter_by_label:
            if counter_by_label[label].verdict == "counter_intuitive_opportunity":
                habit_type = "counter_intuitive"
            elif counter_by_label[label].verdict == "signal_trap":
                habit_type = "trap"
        elif avg_next_1d_delta_pp is not None:
            if avg_next_1d_delta_pp > 0.3:
                habit_type = "likes"
            elif avg_next_1d_delta_pp < -0.3:
                habit_type = "dislikes"

        best_condition: ConditionEffect | None = None
        worst_condition: ConditionEffect | None = None

        cond_effects = conditional_by_label.get(label, [])
        if cond_effects:
            works = [e for e in cond_effects if e.verdict == "works_in_condition"]
            fails = [e for e in cond_effects if e.verdict == "fails_in_condition"]

            if works:
                best_e = max(works, key=lambda e: e.avg_next_1d_delta_pp_vs_quadrant or -999)
                best_condition = ConditionEffect(
                    quadrant=best_e.quadrant,
                    count=best_e.signal_in_quadrant_count,
                    avg_next_1d=best_e.avg_next_1d_in_quadrant,
                    win_rate_1d=best_e.win_rate_in_quadrant,
                    delta_pp_vs_quadrant=best_e.avg_next_1d_delta_pp_vs_quadrant,
                )
            if fails:
                worst_e = min(fails, key=lambda e: e.avg_next_1d_delta_pp_vs_quadrant or 999)
                worst_condition = ConditionEffect(
                    quadrant=worst_e.quadrant,
                    count=worst_e.signal_in_quadrant_count,
                    avg_next_1d=worst_e.avg_next_1d_in_quadrant,
                    win_rate_1d=worst_e.win_rate_in_quadrant,
                    delta_pp_vs_quadrant=worst_e.avg_next_1d_delta_pp_vs_quadrant,
                )

        explanation = ""
        if habit_type == "likes":
            explanation = f"出现后次日平均 {avg_next_1d:+.2f}pp，相对基线 {avg_next_1d_delta_pp:+.2f}pp"
        elif habit_type == "dislikes":
            explanation = f"出现后次日平均 {avg_next_1d:+.2f}pp，相对基线 {avg_next_1d_delta_pp:+.2f}pp"
        elif habit_type == "counter_intuitive":
            explanation = "直觉偏风险但历史表现偏强"
        elif habit_type == "trap":
            explanation = "直觉偏正面但历史表现偏弱"
        else:
            explanation = f"出现后次日平均 {avg_next_1d:+.2f}pp"

        all_patterns.append(PersonalityPattern(
            label=label,
            display_label=display_label,
            category=lift.category,
            pattern_kind="signal",
            habit_type=habit_type,
            count=count,
            avg_next_1d=avg_next_1d,
            avg_next_3d=lift.avg_next_3d,
            avg_next_5d=lift.avg_next_5d,
            avg_next_1d_excess=lift.avg_next_1d_excess,
            avg_next_1d_delta_pp=avg_next_1d_delta_pp,
            win_rate_1d=win_rate_1d,
            effect_score=effect_score,
            significance=significance,
            confidence=confidence,
            best_condition=best_condition,
            worst_condition=worst_condition,
            explanation=explanation,
            source="signal_lift",
        ))

    for quad in quadrant_stats:
        if quad.count < 5:
            continue
        quad_delta = None
        if quad.avg_next_1d is not None and baseline_avg is not None:
            quad_delta = quad.avg_next_1d - baseline_avg

        quad_habit = "context"
        if quad.avg_next_1d is not None:
            if quad.avg_next_1d > 0.3:
                quad_habit = "likes"
            elif quad.avg_next_1d < -0.3:
                quad_habit = "dislikes"

        quad_effect = _shrink_effect_score(quad_delta, quad.count) if quad_delta is not None else None

        all_patterns.append(PersonalityPattern(
            label=quad.quadrant,
            display_label=quad.quadrant,
            category="quadrant",
            pattern_kind="quadrant",
            habit_type=quad_habit,
            count=quad.count,
            avg_next_1d=quad.avg_next_1d,
            avg_next_3d=quad.avg_next_3d,
            avg_next_5d=quad.avg_next_5d,
            avg_next_1d_excess=quad.avg_next_1d_excess,
            avg_next_1d_delta_pp=quad_delta,
            win_rate_1d=quad.win_rate_1d,
            effect_score=quad_effect,
            significance="suggestive" if quad.count >= 10 else "weak",
            confidence="medium" if quad.count >= 20 else "low",
            best_condition=None,
            worst_condition=None,
            explanation=f"处于该象限时次日平均 {quad.avg_next_1d:+.2f}pp",
            source="quadrant_stats",
        ))

    likes = [p for p in all_patterns if p.habit_type == "likes"]
    dislikes = [p for p in all_patterns if p.habit_type == "dislikes"]
    counter_intuitive_pats = [p for p in all_patterns if p.habit_type == "counter_intuitive"]
    trap_pats = [p for p in all_patterns if p.habit_type == "trap"]

    likes_sorted = sorted(likes, key=lambda p: (-p.effect_score or -999, -p.count))
    dislikes_sorted = sorted(dislikes, key=lambda p: (p.effect_score or 999, -p.count))
    counter_sorted = sorted(counter_intuitive_pats, key=lambda p: (-p.effect_score or -999, -p.count))
    traps_sorted = sorted(trap_pats, key=lambda p: (p.effect_score or 999, -p.count))

    return likes_sorted[:5], dislikes_sorted[:5], counter_sorted[:5], traps_sorted[:5]


def _build_summary_metrics(rows: list[HistoryRow]) -> PersonalitySummaryMetrics:
    """计算历史性格画像顶部 6 个摘要指标。"""
    valid = _valid_rows(rows)
    if not valid:
        return PersonalitySummaryMetrics(
            baseline_win_rate_1d=None,
            median_excess_3d=None,
            median_adverse_3d_proxy=None,
            payoff_ratio=None,
            sharpe_like_ratio=None,
            signal_coverage_ratio=None,
            information_ratio=None,
            expectancy_1d=None,
        )

    # baseline_win_rate_1d: valid rows 中 next_1d_return > 0 的比例
    returns_1d = [r.next_1d_return for r in valid if r.next_1d_return is not None]
    baseline_win_rate = (
        sum(1 for r in returns_1d if r > 0) / len(returns_1d) if returns_1d else None
    )

    # median_excess_3d: next_3d_excess_vs_chain 中位数
    excess_3d = [r.next_3d_excess_vs_chain for r in valid if r.next_3d_excess_vs_chain is not None]
    median_excess_3d = statistics.median(excess_3d) if excess_3d else None

    # median_adverse_3d_proxy: 负向 next_3d_return 的中位数；负样本为空返回 None
    adverse_3d = [r.next_3d_return for r in valid if r.next_3d_return is not None and r.next_3d_return < 0]
    median_adverse = statistics.median(adverse_3d) if adverse_3d else None

    # payoff_ratio: 正收益平均 / |负收益平均|；无负样本返回 None
    pos_returns = [r for r in returns_1d if r > 0]
    neg_returns = [r for r in returns_1d if r < 0]
    payoff = None
    if pos_returns and neg_returns:
        payoff = round(sum(pos_returns) / len(pos_returns) / abs(sum(neg_returns) / len(neg_returns)), 2)

    # sharpe_like_ratio: 平均日收益 / 日收益标准差 × √252；标准差为 0 返回 None
    sharpe = None
    if len(returns_1d) >= 2:
        avg_ret = sum(returns_1d) / len(returns_1d)
        try:
            std_ret = statistics.stdev(returns_1d)
            if std_ret > 0:
                sharpe = round((avg_ret / std_ret) * (252 ** 0.5), 2)
        except statistics.StatisticsError:
            pass

    # signal_coverage_ratio: signal_labels 非空非 "[]" 的天数 / valid rows 总数
    signal_days = sum(
        1 for r in valid
        if r.signal_labels and r.signal_labels.strip() and r.signal_labels.strip() != "[]"
    )
    signal_coverage = signal_days / len(valid) if valid else None

    # information_ratio: mean(active_return) / stdev(active_return) × √252
    # active_return = anchor_return - industry_chain_median
    active_returns = [
        r.anchor_return - r.industry_chain_median
        for r in valid
        if r.anchor_return is not None and r.industry_chain_median is not None
    ]
    information_ratio = None
    if len(active_returns) >= 2:
        avg_active = sum(active_returns) / len(active_returns)
        try:
            std_active = statistics.stdev(active_returns)
            if std_active > 0:
                information_ratio = round((avg_active / std_active) * (252 ** 0.5), 2)
        except statistics.StatisticsError:
            pass

    # expectancy_1d: win_rate × avg_win - (1 - win_rate) × |avg_loss|
    expectancy = None
    if baseline_win_rate is not None and pos_returns and neg_returns:
        avg_win = sum(pos_returns) / len(pos_returns)
        avg_loss = abs(sum(neg_returns) / len(neg_returns))
        expectancy = round(baseline_win_rate * avg_win - (1 - baseline_win_rate) * avg_loss, 4)

    return PersonalitySummaryMetrics(
        baseline_win_rate_1d=round(baseline_win_rate, 4) if baseline_win_rate is not None else None,
        median_excess_3d=round(median_excess_3d, 2) if median_excess_3d is not None else None,
        median_adverse_3d_proxy=round(median_adverse, 2) if median_adverse is not None else None,
        payoff_ratio=payoff,
        sharpe_like_ratio=sharpe,
        signal_coverage_ratio=round(signal_coverage, 4) if signal_coverage is not None else None,
        information_ratio=information_ratio,
        expectancy_1d=expectancy,
    )


def _pearson_corr(x: list[float], y: list[float]) -> float | None:
    """计算皮尔逊相关系数，长度不等取最短。"""
    n = min(len(x), len(y))
    if n < 3:
        return None
    try:
        mean_x = sum(x[:n]) / n
        mean_y = sum(y[:n]) / n
        num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        den_x = sum((x[i] - mean_x) ** 2 for i in range(n)) ** 0.5
        den_y = sum((y[i] - mean_y) ** 2 for i in range(n)) ** 0.5
        if den_x == 0 or den_y == 0:
            return None
        return round(num / (den_x * den_y), 4)
    except Exception:
        return None


def _build_simple_relationship_pattern(
    rows: list[HistoryRow],
    relation_name: str,
    rs_field: str,
    pool_median_field: str,
) -> RelationshipPattern:
    valid = _valid_rows(rows)
    if len(valid) < 20:
        return RelationshipPattern(
            relation="unstable",
            confidence="low",
            sample_count=len(valid),
            evidence=["样本或参照池历史序列不足"],
            same_day_corr=None,
            anchor_leads_corr=None,
            anchor_lags_corr=None,
            avg_relative_strength=None,
            outperform_ratio=None,
            repair_after_underperform_ratio=None,
            continuation_after_outperform_ratio=None,
            stability="insufficient",
        )

    # 取 rs 序列
    rs_list: list[float] = []
    for r in valid:
        rs = getattr(r, rs_field, None)
        # fallback: trading_watchlist 没有预计算 rs，现场计算
        if rs is None and "trading_watchlist" in rs_field:
            pool_med = getattr(r, pool_median_field, None)
            if r.anchor_return is not None and pool_med is not None:
                rs = r.anchor_return - pool_med
        if rs is not None:
            rs_list.append(rs)

    avg_rs = _safe_avg(rs_list) if rs_list else None
    outperform_ratio = sum(1 for rs in rs_list if rs > 0) / len(rs_list) if rs_list else None

    # corr 计算（需要 pool median 字段）
    anchor_returns = [r.anchor_return for r in valid if r.anchor_return is not None]
    pool_medians = [getattr(r, pool_median_field, None) for r in valid]
    pool_medians_clean = [v for v in pool_medians if v is not None]

    same_day_corr = None
    anchor_leads_corr = None
    anchor_lags_corr = None
    if len(anchor_returns) >= 3 and len(pool_medians_clean) >= 3:
        # same_day_corr: anchor_return 与 pool median(t)
        n = min(len(anchor_returns), len(pool_medians_clean))
        same_day_corr = _pearson_corr(anchor_returns[:n], pool_medians_clean[:n])
        # anchor_leads_corr: anchor_return(t) 与 pool median(t+1)
        if n >= 4:
            anchor_leads_corr = _pearson_corr(anchor_returns[:n-1], pool_medians_clean[1:n])
        # anchor_lags_corr: anchor_return(t) 与 pool median(t-1)
        if n >= 4:
            anchor_lags_corr = _pearson_corr(anchor_returns[1:n], pool_medians_clean[:n-1])

    # 修复率/延续率计算
    repair_ratio = None
    continuation_ratio = None
    if len(rs_list) >= 2:
        # repair_after_underperform_ratio: rs < 0 后 3 日内 rs > 0 的比例
        underperform_indices = [i for i, rs in enumerate(rs_list) if rs < 0]
        repairs = 0
        for i in underperform_indices:
            if i + 1 < len(rs_list) and rs_list[i + 1] > 0:
                repairs += 1
        repair_ratio = repairs / len(underperform_indices) if underperform_indices else None

        # continuation_after_outperform_ratio: rs > 0 后 3 日内 rs > 0 的比例
        outperform_indices = [i for i, rs in enumerate(rs_list) if rs > 0]
        continuations = 0
        for i in outperform_indices:
            if i + 1 < len(rs_list) and rs_list[i + 1] > 0:
                continuations += 1
        continuation_ratio = continuations / len(outperform_indices) if outperform_indices else None

    # 按阈值规则判定 relation
    relation = "unstable"
    if avg_rs is not None and same_day_corr is not None:
        if abs(avg_rs) > 2.0:
            relation = "diverges"
        elif same_day_corr > 0.5:
            relation = "follows"
        elif same_day_corr < -0.3:
            relation = "mean_reverts"
        elif anchor_leads_corr is not None and anchor_leads_corr > 0.4 and (anchor_lags_corr is None or anchor_lags_corr < anchor_leads_corr):
            relation = "leads"
        elif anchor_lags_corr is not None and anchor_lags_corr > 0.4 and (anchor_leads_corr is None or anchor_leads_corr < anchor_lags_corr):
            relation = "lags"
        else:
            relation = "unstable"

    # evidence 改为可读中文短句
    evidence_parts: list[str] = []
    evidence_parts.append(f"与{relation_name}关系为「{relation}」")
    if avg_rs is not None:
        evidence_parts.append(f"平均相对强弱 {avg_rs:+.2f}pp")
    if repair_ratio is not None:
        evidence_parts.append(f"弱势后修复率 {repair_ratio*100:.0f}%")
    if continuation_ratio is not None:
        evidence_parts.append(f"强势后延续率 {continuation_ratio*100:.0f}%")
    if same_day_corr is not None:
        evidence_parts.append(f"同向相关系数 {same_day_corr:+.2f}")

    stability = "stable"
    if same_day_corr is not None and abs(same_day_corr) < 0.2:
        stability = "unstable"
    elif repair_ratio is not None and repair_ratio < 0.3:
        stability = "changed"

    return RelationshipPattern(
        relation=relation,
        confidence="high" if len(valid) >= 60 else "medium" if len(valid) >= 30 else "low",
        sample_count=len(valid),
        evidence=evidence_parts,
        same_day_corr=same_day_corr,
        anchor_leads_corr=anchor_leads_corr,
        anchor_lags_corr=anchor_lags_corr,
        avg_relative_strength=avg_rs,
        outperform_ratio=outperform_ratio,
        repair_after_underperform_ratio=round(repair_ratio, 4) if repair_ratio is not None else None,
        continuation_after_outperform_ratio=round(continuation_ratio, 4) if continuation_ratio is not None else None,
        stability=stability,
    )


def _build_relationship_profile(rows: list[HistoryRow]) -> RelationshipProfile:
    return RelationshipProfile(
        anchor_vs_chain=_build_simple_relationship_pattern(
            rows, "产业链", "relative_strength_vs_industry_chain", "industry_chain_median"
        ),
        anchor_vs_theme=_build_simple_relationship_pattern(
            rows, "主题池", "relative_strength_vs_theme", "theme_pool_median"
        ),
        anchor_vs_core=_build_simple_relationship_pattern(
            rows, "主线池", "relative_strength_vs_direct", "direct_peers_median"
        ),
        anchor_vs_trading_watchlist=_build_simple_relationship_pattern(
            rows, "交易观察池", "relative_strength_vs_trading_watchlist", "trading_watchlist_median"
        ),
    )


def _build_event_cum_path(
    event_dates: set[str],
    rows: list[HistoryRow],
    label: str,
) -> PathPattern | None:
    """为事件日期集合构建 T-5~T+5 累计收益路径。"""
    if not event_dates or len(rows) < 10:
        return None

    # 建立 date -> index 映射
    date_to_idx = {r.date: i for i, r in enumerate(rows)}
    valid_events = [d for d in event_dates if d in date_to_idx]
    if not valid_events:
        return None

    # 收集每个事件的 cum 序列
    paths_anchor: dict[int, list[float]] = {o: [] for o in range(-5, 6)}
    paths_chain: dict[int, list[float]] = {o: [] for o in range(-5, 6)}
    paths_excess: dict[int, list[float]] = {o: [] for o in range(-5, 6)}

    for ed in valid_events:
        i = date_to_idx[ed]
        for offset in range(-5, 6):
            j = i + offset
            if j < 0 or j >= len(rows):
                continue
            r = rows[j]
            if r.anchor_return is None:
                continue

            # 累计收益：以 T0 为基准，T0=0
            # T+N (N>0) = sum(returns[i+1..i+N])
            # T-N (N>0) = -sum(returns[i-N..i-1])
            if offset == 0:
                cum_anchor = 0.0
                cum_chain = 0.0
                cum_excess = 0.0
            elif offset > 0:
                cum_anchor = sum(
                    rows[i + k].anchor_return or 0.0
                    for k in range(1, offset + 1)
                    if i + k < len(rows) and rows[i + k].anchor_return is not None
                )
                cum_chain = sum(
                    rows[i + k].industry_chain_median or 0.0
                    for k in range(1, offset + 1)
                    if i + k < len(rows) and rows[i + k].industry_chain_median is not None
                )
                cum_excess = sum(
                    (rows[i + k].anchor_return or 0.0) - (rows[i + k].industry_chain_median or 0.0)
                    for k in range(1, offset + 1)
                    if i + k < len(rows) and rows[i + k].anchor_return is not None
                )
            else:
                cum_anchor = -sum(
                    rows[i + k].anchor_return or 0.0
                    for k in range(offset, 0)
                    if i + k >= 0 and rows[i + k].anchor_return is not None
                )
                cum_chain = -sum(
                    rows[i + k].industry_chain_median or 0.0
                    for k in range(offset, 0)
                    if i + k >= 0 and rows[i + k].industry_chain_median is not None
                )
                cum_excess = -sum(
                    (rows[i + k].anchor_return or 0.0) - (rows[i + k].industry_chain_median or 0.0)
                    for k in range(offset, 0)
                    if i + k >= 0 and rows[i + k].anchor_return is not None
                )

            paths_anchor[offset].append(cum_anchor)
            paths_chain[offset].append(cum_chain)
            paths_excess[offset].append(cum_excess)

    # 按 offset 求平均
    avg_path: list[PathPatternPoint] = []
    for offset in range(-5, 6):
        a_vals = paths_anchor[offset]
        c_vals = paths_chain[offset]
        e_vals = paths_excess[offset]
        avg_path.append(PathPatternPoint(
            offset=offset,
            anchor_return=round(sum(a_vals) / len(a_vals), 2) if a_vals else None,
            chain_median=round(sum(c_vals) / len(c_vals), 2) if c_vals else None,
            excess=round(sum(e_vals) / len(e_vals), 2) if e_vals else None,
        ))

    # summary 中文结论
    t_plus_3 = next((p for p in avg_path if p.offset == 3), None)
    t_minus_3 = next((p for p in avg_path if p.offset == -3), None)
    summary_parts: list[str] = []
    if t_minus_3 and t_minus_3.anchor_return is not None:
        summary_parts.append(f"事件前3日累计{t_minus_3.anchor_return:+.2f}pp")
    if t_plus_3 and t_plus_3.anchor_return is not None:
        summary_parts.append(f"事件后3日累计{t_plus_3.anchor_return:+.2f}pp")
    summary = "；".join(summary_parts) if summary_parts else f"共 {len(valid_events)} 次事件"

    # 计算有效点数量
    valid_points = sum(1 for p in avg_path if p.anchor_return is not None)
    confidence = "high" if valid_points >= 10 else "medium" if valid_points >= 6 else "low"

    return PathPattern(
        event_label=label,
        count=len(valid_events),
        avg_path=avg_path,
        summary=summary,
        confidence=confidence,
    )


def _build_path_patterns(
    rows: list[HistoryRow],
    extreme_divergences: list[ExtremeDivergence],
    event_paths: list[EventPath],
) -> list[PathPattern]:
    """构建多事件类型的路径画像。"""
    patterns: list[PathPattern] = []

    # 1. 极端正背离
    pos_div_dates = {d.date for d in extreme_divergences if d.divergence > 0}
    pp = _build_event_cum_path(pos_div_dates, rows, "极端正背离")
    if pp:
        patterns.append(pp)

    # 2. 极端负背离
    neg_div_dates = {d.date for d in extreme_divergences if d.divergence < 0}
    pp = _build_event_cum_path(neg_div_dates, rows, "极端负背离")
    if pp:
        patterns.append(pp)

    # 3. 放量上涨: amount_expansion_ratio > 1.5 and anchor_return > 1.0
    vol_up_dates = {
        r.date for r in rows
        if r.amount_expansion_ratio is not None and r.amount_expansion_ratio > 1.5
        and r.anchor_return is not None and r.anchor_return > 1.0
    }
    pp = _build_event_cum_path(vol_up_dates, rows, "放量上涨")
    if pp:
        patterns.append(pp)

    # 4. 放量下跌: amount_expansion_ratio > 1.5 and anchor_return < -1.0
    vol_down_dates = {
        r.date for r in rows
        if r.amount_expansion_ratio is not None and r.amount_expansion_ratio > 1.5
        and r.anchor_return is not None and r.anchor_return < -1.0
    }
    pp = _build_event_cum_path(vol_down_dates, rows, "放量下跌")
    if pp:
        patterns.append(pp)

    # 5. 资金价格背离: 资金流入(>0.5)但跌 或 资金流出(<0.5)但涨
    fund_div_dates = {
        r.date for r in rows
        if r.moneyflow_positive_ratio is not None and r.anchor_return is not None
        and (
            (r.moneyflow_positive_ratio > 0.5 and r.anchor_return < 0)
            or (r.moneyflow_positive_ratio < 0.5 and r.anchor_return > 0)
        )
    }
    pp = _build_event_cum_path(fund_div_dates, rows, "资金价格背离")
    if pp:
        patterns.append(pp)

    # 兜底：如果没有足够事件，生成一个历史平均路径
    if len(patterns) < 2:
        valid = _valid_rows(rows)
        if len(valid) >= 10:
            avg_path: list[PathPatternPoint] = []
            for offset in range(-5, 6):
                avg_path.append(PathPatternPoint(
                    offset=offset,
                    anchor_return=0.0 if offset == 0 else None,
                    chain_median=0.0 if offset == 0 else None,
                    excess=0.0 if offset == 0 else None,
                ))
            patterns.append(PathPattern(
                event_label="历史平均路径",
                count=len(valid),
                avg_path=avg_path,
                summary="历史平均走势",
                confidence="low",
            ))

    return patterns


def _build_personality_summary(
    likes: list[PersonalityPattern],
    dislikes: list[PersonalityPattern],
    counter_intuitive_pats: list[PersonalityPattern],
    trap_pats: list[PersonalityPattern],
    relationship_profile: RelationshipProfile,
    valid_sample_days: int,
) -> PersonalitySummary:
    primary_trait = "样本观察型"
    chain_relation = relationship_profile.anchor_vs_chain.relation

    if chain_relation == "follows":
        primary_trait = "产业链跟随型"
    elif chain_relation == "diverges":
        primary_trait = "独立走势型"

    top_like = likes[0].display_label if likes else "无明显偏好"
    top_dislike = dislikes[0].display_label if dislikes else "无明显厌恶"
    top_counter = counter_intuitive_pats[0].display_label if counter_intuitive_pats else "无反直觉信号"
    top_trap = trap_pats[0].display_label if trap_pats else "无明显陷阱"

    traits = [primary_trait]
    if likes:
        traits.append(f"偏好「{top_like}」")
    if dislikes:
        traits.append(f"规避「{top_dislike}」")

    confidence = "high" if valid_sample_days >= 40 else "medium" if valid_sample_days >= 20 else "low"

    headline = (
        f"过去样本显示，锚定个股更像「{primary_trait}」。它较喜欢「{top_like}」，不太喜欢「{top_dislike}」；「{top_counter}」属于反直觉机会线索，「{top_trap}」容易形成信号陷阱。"
    )

    return PersonalitySummary(
        headline=headline,
        traits=traits[:5],
        strongest_pattern_label=top_like if likes else None,
        weakest_pattern_label=top_dislike if dislikes else None,
        confidence=confidence,
        generation_method="rule_template_v1",
    )


def _build_stability(
    rows: list[HistoryRow],
    likes: list[PersonalityPattern],
    recent_window_days: int = 30,
) -> PersonalityStability:
    valid = _valid_rows(rows)
    if len(valid) < 20:
        return PersonalityStability(
            status="insufficient",
            recent_window_days=recent_window_days,
            early_vs_recent_notes=["样本不足"],
        )

    recent = valid[-recent_window_days:]
    early = valid[:-recent_window_days]

    if len(recent) < 5:
        return PersonalityStability(
            status="insufficient",
            recent_window_days=recent_window_days,
            early_vs_recent_notes=["近期样本不足"],
        )

    # 近期跑赢率：anchor_return > industry_chain_median 的占比
    recent_wins = sum(
        1 for r in recent
        if r.anchor_return is not None and r.industry_chain_median is not None
        and r.anchor_return > r.industry_chain_median
    )
    recent_valid = sum(
        1 for r in recent
        if r.anchor_return is not None and r.industry_chain_median is not None
    )
    recent_win_rate = recent_wins / recent_valid if recent_valid > 0 else 0.0

    # 近期超额均值
    recent_excesses = [
        r.anchor_return - r.industry_chain_median
        for r in recent
        if r.anchor_return is not None and r.industry_chain_median is not None
    ]
    recent_avg_excess = sum(recent_excesses) / len(recent_excesses) if recent_excesses else 0.0

    # 早期跑赢率（如有）
    early_win_rate = None
    early_avg_excess = None
    if len(early) >= 5:
        early_wins = sum(
            1 for r in early
            if r.anchor_return is not None and r.industry_chain_median is not None
            and r.anchor_return > r.industry_chain_median
        )
        early_valid = sum(
            1 for r in early
            if r.anchor_return is not None and r.industry_chain_median is not None
        )
        early_win_rate = early_wins / early_valid if early_valid > 0 else 0.0
        early_excesses = [
            r.anchor_return - r.industry_chain_median
            for r in early
            if r.anchor_return is not None and r.industry_chain_median is not None
        ]
        early_avg_excess = sum(early_excesses) / len(early_excesses) if early_excesses else 0.0

    notes: list[str] = []

    # 跑赢率描述
    wr_pct = f"{recent_win_rate * 100:.0f}%"
    if early_win_rate is not None:
        delta = recent_win_rate - early_win_rate
        if delta > 0.1:
            notes.append(f"近期跑赢率 {wr_pct}，明显高于早期 {early_win_rate * 100:.0f}%")
        elif delta < -0.1:
            notes.append(f"近期跑赢率 {wr_pct}，明显低于早期 {early_win_rate * 100:.0f}%")
        else:
            notes.append(f"近期跑赢率 {wr_pct}，与早期 {early_win_rate * 100:.0f}% 接近")
    else:
        notes.append(f"近期跑赢率 {wr_pct}")

    # 超额方向描述
    if recent_avg_excess > 0.2:
        notes.append("超额均值偏正，性格偏强")
    elif recent_avg_excess < -0.2:
        notes.append("超额均值偏负，性格偏弱")
    else:
        notes.append("超额均值接近零，跟随为主")

    # 判定 status
    win_rate_shifted = early_win_rate is not None and abs(recent_win_rate - early_win_rate) > 0.1
    excess_shifted = early_avg_excess is not None and abs(recent_avg_excess - early_avg_excess) > 0.5

    if win_rate_shifted or excess_shifted:
        status = "changed"
    else:
        status = "stable"

    return PersonalityStability(
        status=status,
        recent_window_days=recent_window_days,
        early_vs_recent_notes=notes,
    )


def build_personality_profile(
    rows: list[HistoryRow],
    signal_lifts: list[SignalLift],
    quadrant_stats: list[QuadrantStats],
    counter_intuitive: list[CounterIntuitiveSignal],
    conditional_effects: list[ConditionalSignalEffect],
    extreme_divergences: list[ExtremeDivergence],
    event_paths: list[EventPath],
) -> HistoryPersonalityProfile:
    valid = _valid_rows(rows)
    date_range = sorted(r.date for r in rows)
    baseline_avg, _ = _compute_baseline(rows)

    likes, dislikes, counter_intuitive_pats, trap_pats = _build_personality_patterns(
        signal_lifts, quadrant_stats, counter_intuitive, conditional_effects, rows, baseline_avg
    )

    summary_metrics = _build_summary_metrics(rows)
    relationship_profile = _build_relationship_profile(rows)
    path_patterns = _build_path_patterns(rows, extreme_divergences, event_paths)
    personality_summary = _build_personality_summary(
        likes, dislikes, counter_intuitive_pats, trap_pats, relationship_profile, len(valid)
    )
    stability = _build_stability(rows, likes)

    warnings: list[str] = []
    if len(valid) < 20:
        warnings.append(f"有效样本仅 {len(valid)} 天，统计意义不足")
    elif len(valid) < 40:
        warnings.append(f"有效样本 {len(valid)} 天，结论需谨慎参考")

    return HistoryPersonalityProfile(
        as_of_date=date_range[-1] if date_range else "",
        date_range_start=date_range[0] if date_range else "",
        date_range_end=date_range[-1] if date_range else "",
        sample_days=len(rows),
        valid_sample_days=len(valid),
        summary_metrics=summary_metrics,
        personality_summary=personality_summary,
        habit_patterns=likes + dislikes,
        counter_intuitive_patterns=counter_intuitive_pats,
        trap_patterns=trap_pats,
        relationship_profile=relationship_profile,
        path_patterns=path_patterns,
        stability=stability,
        sample_warnings=warnings,
    )
