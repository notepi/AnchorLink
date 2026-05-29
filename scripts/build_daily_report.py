#!/usr/bin/env python3
"""
每日分析报告生成（管道步骤 3.6）

读取 v2_scoring.json + 行业快照 + 滚动指标，生成每日 Markdown 报告。
输出：data/output/{date}/v2_report.md
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "output"

REGIME_LABEL = {
    "mean_reverting": "均值回归",
    "trending": "趋势市",
    "transition": "过渡期",
}

SIGNAL_MEANING = {
    "excess_5d_P15-": "5日超额过冷，均值回归概率高",
    "excess_5d_P85+": "5日超额过热，回调风险大",
    "excess_10d_P15-": "10日超额过冷，均值回归概率高",
    "excess_10d_P70-P85": "10日超额偏热",
    "outperform_streak_≤-3": "连续跑输3天+，极端弱",
    "outperform_streak_≥+3": "连续跑赢3天+，追高风险",
    "跌但资金支撑": "价格跌但资金流入",
    "缩量阴跌": "缩量下跌，卖压衰减",
    "放量大涨_veto": "放量大涨，一票否决",
    "放量大跌": "放量下跌，恐慌出逃",
    "alpha_signal_count_≥3": "Alpha信号≥3个",
    "rs_vs_chain_Q2": "相对行业链偏弱（Q2）",
    "rs_vs_chain_Q5": "相对行业链极强（Q5），追高风险",
    "Beta骑乘组合": "Beta正+行业前排，趋势跟涨",
    "信号_放量上涨": "放量上涨信号",
    "path_弱+弱→中或强": "状态从弱转强",
    "path_强+强→强+弱": "状态从强转弱",
    "mean_reverting+streak≤-3": "MR环境+连续跑输3天+，最强买入",
    "mean_reverting+streak≤-2": "MR环境+连续跑输2天+，强买入",
    "transition+streak≤-2": "过渡期+连续跑输2天+，有效买入",
    "transition+streak≥+2": "过渡期+连续跑赢2天+，最强卖出",
    "MACD柱状图负": "MACD柱状图为负",
    "周三效应": "周三偏多",
    "LiqSweep高(假突破)": "假突破上方阻力",
    "周五效应": "周五偏空",
    "周五+ADX<25": "周五+低ADX，绝对回避",
    "RSI超买(>70)": "RSI超买",
    "Stoch超买(K>80)": "随机指标超买",
    "BB上轨触及": "突破布林上轨",
    "看跌FVG日": "看跌公允价值缺口",
    "BOS创20日新高": "创20日收盘新高",
}


def load_v2_data() -> dict:
    with open(DATA_DIR / "v2_scoring.json", encoding="utf-8") as f:
        return json.load(f)


def load_summary() -> list[dict]:
    rows = []
    with open(DATA_DIR / "history_summary.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def load_rolling() -> list[dict]:
    rows = []
    with open(DATA_DIR / "history_rolling_metrics.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def load_snapshot(date: str) -> dict | None:
    path = DATA_DIR / date / "industry_snapshot.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt_pct(v, suffix="%") -> str:
    if v is None:
        return "—"
    try:
        f = float(v)
        return f"{f:+.2f}{suffix}"
    except (ValueError, TypeError):
        return str(v)


def action_label(score: int, veto: bool, threshold_buy: int, threshold_sell: int) -> str:
    if veto:
        return "不做多 (Veto)"
    if score >= threshold_buy:
        return "做多"
    if score <= threshold_sell:
        return "减仓/不做多"
    return "观望"


def compute_historical_stats(daily_results: list[dict], threshold: int) -> dict:
    """计算评分 <= threshold 的历史 T+1 统计"""
    days = [r for r in daily_results if r["score"] <= threshold and r["next1dExcess"] is not None]
    if not days:
        return {"n": 0}
    exc = np.array([r["next1dExcess"] for r in days])
    abs_vals = np.array([r["next1dAbs"] for r in days])
    return {
        "n": len(days),
        "exc_mean": float(np.mean(exc)),
        "exc_pos_rate": float((exc > 0).mean()),
        "abs_mean": float(np.mean(abs_vals)),
        "abs_pos_rate": float((abs_vals > 0).mean()),
        "exc_median": float(np.median(exc)),
    }


def generate_daily_report(
    date: str,
    day_result: dict,
    daily_results: list[dict],
    summary_map: dict[str, dict],
    rolling_map: dict[str, dict],
) -> str:
    score = day_result["score"]
    regime = day_result["regime"]
    regime_label = REGIME_LABEL.get(regime, regime)
    adx = day_result["technicalIndicators"].get("adx14")
    veto = day_result["veto"]
    threshold_buy = day_result["thresholdBuy"]
    threshold_sell = day_result["thresholdSell"]
    hold_days = day_result["holdPeriodDays"]
    kelly = day_result.get("kellyPosition")

    summary_row = summary_map.get(date, {})
    rolling_row = rolling_map.get(date, {})

    # ── 一、今日概览 ──
    action = action_label(score, veto, threshold_buy, threshold_sell)

    lines = [
        f"# 铂力特 {date[:4]}-{date[4:6]}-{date[6:]} 评分分析报告",
        "",
        f"> **日期**: {date[:4]}-{date[4:6]}-{date[6:]} | **评分**: {score} | **Regime**: {regime_label} (ADX={adx:.1f})" if adx else f"> **日期**: {date} | **评分**: {score} | **Regime**: {regime_label}",
        "",
        "---",
        "",
        "## 一、今日概览",
        "",
        "| 指标 | 值 | 判断 |",
        "|------|-----|------|",
        f"| 综合评分 | **{score}** | {'远超做空阈值' if score <= threshold_sell - 2 else '偏空' if score <= threshold_sell else '中性' if abs(score) < threshold_buy else '偏多'} |",
        f"| Regime | {regime_label} (ADX={adx:.1f}) | {'均值回归环境，超买信号效力增强' if regime == 'mean_reverting' else '趋势主导' if regime == 'trending' else '信号效力混合'} |" if adx else f"| Regime | {regime_label} | — |",
        f"| Veto | {'是' if veto else '否'} | {'触发放量大涨否决' if veto else '未触发否决'} |",
        f"| 操作建议 | **{action}** | {'做空阈值 ' + str(threshold_sell) + ' 已触发' if score <= threshold_sell else ''} |",
        f"| 持仓建议 | {hold_days} 天 | {'卖出信号衰减极快' if hold_days == 1 else '可持续持有'} |",
    ]

    # ── 二、触发信号详解 ──
    lines.extend([
        "",
        "## 二、触发信号详解",
        "",
        "| 信号 | 权重 | 类别 | 含义 |",
        "|------|------|------|------|",
    ])

    for s in day_result.get("signalBreakdown", []):
        meaning = SIGNAL_MEANING.get(s["signal"], "")
        cat = "V2" if s["category"] == "v2_new" else "V1"
        lines.append(f"| {s['signal']} | {s['adjustedWeight']:+d} | {cat} | {meaning} |")

    buy_count = sum(1 for s in day_result.get("signalBreakdown", []) if s["adjustedWeight"] > 0)
    sell_count = sum(1 for s in day_result.get("signalBreakdown", []) if s["adjustedWeight"] < 0)
    lines.extend([
        "",
        f"**信号一致性**：{buy_count} 个买入，{sell_count} 个卖出。{'方向 100% 一致偏空' if buy_count == 0 and sell_count > 0 else '方向 100% 一致偏多' if sell_count == 0 and buy_count > 0 else '多空信号并存'}。",
    ])

    # ── 三、极端特征 ──
    ti = day_result.get("technicalIndicators", {})
    e5 = rolling_row.get("excess_5d")
    e10 = rolling_row.get("excess_10d")
    streak = rolling_row.get("outperform_streak", 0)
    anchor_ret = summary_row.get("anchor_return")
    chain_med = summary_row.get("industry_chain_median")
    rs_chain = summary_row.get("relative_strength_vs_industry_chain")

    lines.extend([
        "",
        "## 三、极端特征",
        "",
    ])

    extremes = []
    if e5 is not None:
        try:
            e5f = float(e5)
            if abs(e5f) > 10:
                extremes.append(f"**excess_5d = {e5f:+.2f}%**：5 日超额收益{'历史极值' if abs(e5f) > 15 else '偏高'}")
        except (ValueError, TypeError):
            pass
    if e10 is not None:
        try:
            e10f = float(e10)
            if abs(e10f) > 10:
                extremes.append(f"**excess_10d = {e10f:+.2f}%**：10 日超额收益{'历史极值' if abs(e10f) > 15 else '偏高'}")
        except (ValueError, TypeError):
            pass
    if ti.get("stochK") is not None and ti["stochK"] > 85:
        extremes.append(f"**Stoch K = {ti['stochK']:.1f}**：{'极度超买' if ti['stochK'] > 90 else '超买'}")
    if ti.get("bbPctb") is not None and ti["bbPctb"] > 1.05:
        extremes.append(f"**BB %b = {ti['bbPctb']:.2f}**：突破布林上轨")
    if ti.get("rsi14") is not None and ti["rsi14"] > 70:
        extremes.append(f"**RSI = {ti['rsi14']:.1f}**：超买")

    if anchor_ret and chain_med:
        try:
            ar = float(anchor_ret)
            cm = float(chain_med)
            if abs(ar - cm) > 10:
                extremes.append(f"**个股 {ar:+.1f}%，行业链 {cm:+.1f}%**：单日超额 {ar-cm:+.1f}%，个股与行业严重脱钩")
        except (ValueError, TypeError):
            pass

    if extremes:
        for i, e in enumerate(extremes, 1):
            lines.append(f"{i}. {e}")
    else:
        lines.append("无极端特征，各项指标在正常范围内。")

    # ── 四、历史类比 ──
    lines.extend([
        "",
        "## 四、历史类比",
        "",
    ])

    # 按当前评分的档位计算
    score_abs = abs(score)
    if score_abs >= 8:
        threshold_for_stats = -8
    elif score_abs >= 6:
        threshold_for_stats = -6
    elif score_abs >= 3:
        threshold_for_stats = -3
    else:
        threshold_for_stats = 0

    if score < 0 and threshold_for_stats < 0:
        stats = compute_historical_stats(daily_results, threshold_for_stats)
        if stats["n"] > 0:
            lines.extend([
                f"### 评分 ≤ {threshold_for_stats} 的历史表现（n={stats['n']}）",
                "",
                "| 指标 | 值 |",
                "|------|-----|",
                f"| T+1 超额均值 | {stats['exc_mean']:+.2f}% |",
                f"| T+1 超额正比例 | {stats['exc_pos_rate']:.1%} |",
                f"| T+1 超额中位数 | {stats['exc_median']:+.2f}% |",
                f"| T+1 绝对收益正比例 | {stats['abs_pos_rate']:.1%} |",
                "",
            ])

    # 极端档
    if score < -6:
        stats_extreme = compute_historical_stats(daily_results, -8)
        if stats_extreme["n"] > 0:
            lines.extend([
                f"### 评分 ≤ -8 的极端日（n={stats_extreme['n']}）",
                "",
                "| 指标 | 值 |",
                "|------|-----|",
                f"| T+1 超额均值 | **{stats_extreme['exc_mean']:+.2f}%** |",
                f"| T+1 超额正比例 | **{stats_extreme['exc_pos_rate']:.1%}** |",
                f"| T+1 绝对收益正比例 | {stats_extreme['abs_pos_rate']:.1%} |",
                "",
            ])

    # ── 五、近5天评分趋势 ──
    # 找当前日期在 daily_results 中的 index
    idx = next((i for i, r in enumerate(daily_results) if r["date"] == date), -1)
    if idx >= 4:
        recent = daily_results[idx - 4:idx + 1]
    elif idx >= 0:
        recent = daily_results[max(0, idx - 4):idx + 1]
    else:
        recent = daily_results[-5:]

    lines.extend([
        "## 五、近5天评分趋势",
        "",
        "| 日期 | 评分 | Veto | T+1超额 | 说明 |",
        "|------|------|------|---------|------|",
    ])

    for r in recent:
        exc = f"{r['next1dExcess']:+.2f}%" if r["next1dExcess"] is not None else "待验证"
        v = "是" if r["veto"] else "否"
        is_today = r["date"] == date
        marker = " **← 今日**" if is_today else ""
        lines.append(f"| {r['date'][:4]}-{r['date'][4:6]}-{r['date'][6:]} | {r['score']:+d} | {v} | {exc} |{marker}")

    # ── 六、次日展望 ──
    lines.extend([
        "",
        "## 六、次日展望",
        "",
    ])

    # 方向判断
    if score <= threshold_sell:
        direction = "偏空，超额大概率回落"
    elif score >= threshold_buy:
        direction = "偏多，超额可能上行"
    else:
        direction = "中性，超额方向不确定"
    lines.append(f"**倾向**：{direction}。")
    lines.append("")

    # 理由
    reasons = []
    if score <= threshold_sell:
        stats = compute_historical_stats(daily_results, score)
        if stats["n"] >= 5:
            reasons.append(f"评分 {score}，历史同档 T+1 超额正比例 {stats['exc_pos_rate']:.0%}")
    if buy_count == 0 and sell_count > 0:
        reasons.append("所有触发信号方向一致偏空")
    if ti.get("stochK") is not None and ti["stochK"] > 80:
        reasons.append(f"Stoch K={ti['stochK']:.0f} 超买，均值回归力度强")
    if e5 is not None:
        try:
            if abs(float(e5)) > 10:
                reasons.append(f"excess_5d={float(e5):+.1f}%，半衰期仅 2 天")
        except (ValueError, TypeError):
            pass
    if regime == "mean_reverting" and score <= threshold_sell:
        reasons.append("MR 环境下卖出信号效力增强")

    if reasons:
        lines.append("**理由**：")
        for r in reasons:
            lines.append(f"1. {r}")
        lines.append("")

    # 不确定性
    uncertainties = []
    dow = day_result.get("technicalIndicators", {}).get("dow")
    # 简单判断是否周三
    if score > 0 and score < threshold_buy:
        uncertainties.append("评分在中性区间，方向不确定")
    stats_near = compute_historical_stats(daily_results, score)
    if stats_near["n"] > 0 and 0.3 < stats_near["exc_pos_rate"] < 0.7:
        uncertainties.append(f"历史同档 T+1 超额正比例 {stats_near['exc_pos_rate']:.0%}，方向不明确")

    if uncertainties:
        lines.append("**不确定性**：")
        for u in uncertainties:
            lines.append(f"1. {u}")
        lines.append("")

    # 操作建议
    if score <= threshold_sell:
        lines.extend([
            "**操作建议**：",
            f"- 有仓位 → 减仓（框架做空阈值 {threshold_sell}，今日 {score}）",
            "- 无仓位 → 不追涨（均值回归股追涨必亏）",
            f"- 关注 streak 何时转负 → 可能出现买入信号",
        ])
    elif score >= threshold_buy:
        lines.extend([
            "**操作建议**：",
            f"- 可做多（评分 {score} 超过做多阈值 {threshold_buy}）",
            f"- 建议持仓 {hold_days} 天",
            f"- Kelly 仓位 {kelly*100:.0f}%" if kelly else "- 参考仓位见 V2 评分页",
        ])
    else:
        lines.extend([
            "**操作建议**：",
            "- 观望，评分未触及操作阈值",
        ])

    # 免责
    lines.extend([
        "",
        "---",
        "",
        f"*本报告基于 V2 保守评分系统（MR±3/TR±4/TS±4），Walk-Forward 120 天验证。统计结论力度有限，仅供参考，不构成投资建议。生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*",
    ])

    return "\n".join(lines)


def main():
    print("[INFO] 加载 V2 评分数据...")
    v2_data = load_v2_data()
    daily_results = v2_data["dailyResults"]

    print("[INFO] 加载历史数据...")
    summary_rows = load_summary()
    rolling_rows = load_rolling()

    summary_map = {str(r["date"]): r for r in summary_rows}
    rolling_map = {str(r["date"]): r for r in rolling_rows}

    print(f"[INFO] 生成 {len(daily_results)} 份报告...")

    generated = 0
    for day_result in daily_results:
        date = day_result["date"]
        report = generate_daily_report(date, day_result, daily_results, summary_map, rolling_map)

        # 写入 data/output/{date}/v2_report.md
        date_dir = DATA_DIR / date
        date_dir.mkdir(parents=True, exist_ok=True)
        out_path = date_dir / "v2_report.md"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        generated += 1

    print(f"[OK] 已生成 {generated} 份报告")

    # 打印最新报告预览
    if daily_results:
        latest = daily_results[-1]
        lines = generate_daily_report(
            latest["date"], latest, daily_results, summary_map, rolling_map
        ).split("\n")
        print(f"\n{'=' * 60}")
        print(f"  最新报告预览: {latest['date']}")
        print(f"{'=' * 60}")
        for line in lines[:20]:
            print(f"  {line}")
        print(f"  ... (共 {len(lines)} 行)")


if __name__ == "__main__":
    main()
