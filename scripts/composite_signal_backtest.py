"""
综合信号策略回测
=================
把 A-P 维度发现的所有强信号整合为一个综合评分系统，
回测：score 阈值化操作 vs buy-and-hold 的累计超额收益对比。

设计：
  - 每个强信号给一个权重（基于历史 lift 强度）
  - 当日综合分 = Σ(signal_active × weight)
  - 策略：score >= +threshold 时做多（持有1日），score <= -threshold 时空仓
  - 比较：策略累计超额 vs 永久持有累计超额

输入：
  - data/output/history_summary.csv
  - data/output/history_rolling_metrics.csv
  - data/output/dashboard_view.json
  - data/output/history_2nd_order_analysis.json

输出：
  - data/output/composite_signal_backtest.json
  - 控制台打印回测报告
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
HISTORY_CSV  = ROOT / "data/output/history_summary.csv"
ROLLING_CSV  = ROOT / "data/output/history_rolling_metrics.csv"
DASHBOARD_JSON = ROOT / "data/output/dashboard_view.json"
SECOND_ORDER_JSON = ROOT / "data/output/history_2nd_order_analysis.json"
OUTPUT_JSON  = ROOT / "data/output/composite_signal_backtest.json"

# ── 工具 ──────────────────────────────────────────────────────────────────────

def safe_float(v):
    try:
        if v is None or v == "": return None
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None

def parse_signals(raw):
    return {s.strip() for s in (raw or "").split(",") if s.strip()}

def fmt_pct(v):
    if v is None: return "  -   "
    return f"{'+' if v>=0 else ''}{v:.2f}%"

def percentile(vals, p):
    if not vals: return 0
    s = sorted(vals)
    idx = int(len(s) * p / 100)
    return s[min(idx, len(s)-1)]

# ── 信号定义与权重（基于 M/N/J/K/H 维度的发现）──────────────────────────────

# 买入信号（正分）
BUY_SIGNALS = {
    # M 维：5d/10d 超额极端档（最强反转）
    "excess_5d_P15-(过冷≤-4.91%)": 3,
    "excess_10d_P15-(过冷≤-6.11%)": 3,
    "delta_excess_5d_温和回调[-3,-1]": 2,

    # J 维：连续跑输区间反转
    "outperform_streak_≤-3(连续跑输)": 3,

    # H 维：量价背离买入
    "跌但资金支撑(anchor<0 & moneyflow>0.6)": 2,
    "缩量阴跌(anchor<-0.5% & amount<0.85)": 1,

    # K 维：Alpha 信号激活（每个 +1，最多 +3）
    "alpha_signal_count_≥3": 2,

    # N 维：交易观察池相关性回归
    "trading_corr_快速上升(回归)": 1,

    # G 维：rs_vs_chain Q2 档（偏弱）
    "rs_vs_chain_Q2(偏弱档)": 1,

    # 路径信号
    "path_弱+弱→中或强(动能延续)": 2,
}

# 卖出/警惕信号（负分）
SELL_SIGNALS = {
    # M 维：5d/10d 超额过热
    "excess_5d_P85+(过热≥+5.74%)": -3,
    "excess_10d_P70-P85(温热)": -1,
    "delta_excess_5d_最快上升(>+3.7%)": -2,

    # J 维：连续跑赢警惕
    "outperform_streak_≥+3(连续跑赢)": -2,

    # H 维：量价警示
    "放量大涨(anchor>1% & amount>1.3)": -3,
    "放量大跌(anchor<-1% & amount>1.3)": -1,

    # K 维：Beta 骑乘陷阱
    "Beta骑乘组合(Beta+ & 处于行业前排)": -2,

    # G 维：rs_vs_chain Q5 极强档（均值回归）
    "rs_vs_chain_Q5(极强档≥+1.7%)": -2,

    # F 维：放量上涨陷阱
    "信号_放量上涨": -2,

    # 路径警示
    "path_强+强→强+弱(衰竭)": -1,
}

# 一票否决：直接跳过当日做多
VETO_SIGNALS = {
    "放量大涨(anchor>1% & amount>1.3)",
}

# ── 评分函数 ──────────────────────────────────────────────────────────────────

ALPHA_SIGNALS_SET = {
    "资金价格背离", "主力资金拖累", "行业扩散不足",
    "交易观察池降温", "行业Beta为中性",
    "主题情绪强但主线池弱", "行业Beta为负",
    "情绪池强于产业链", "放量下跌",
}

def state_key(row):
    beta = (row.get("industry_beta") or "neutral").strip().lower()
    alpha = (row.get("anchor_alpha") or "neutral").strip().lower()
    return f"{beta}+{alpha}"

def compute_active_signals(
    row, prev_row, rolling, prev_rolling, trading_corr_change,
    excess_5d_p15, excess_5d_p85, excess_10d_p15, excess_10d_p70, excess_10d_p85,
    delta_e5d, prev_state=None, today_state=None,
):
    """
    返回 (active_signal_list, score, veto_triggered)
    每个 active_signal 是 (signal_name, weight)
    """
    active = []
    veto = False

    ar = safe_float(row.get("anchor_return"))
    mf = safe_float(row.get("moneyflow_positive_ratio"))
    ae = safe_float(row.get("amount_expansion_ratio"))
    rs_chain = safe_float(row.get("relative_strength_vs_industry_chain"))
    e5 = safe_float(rolling.get("excess_5d")) if rolling else None
    e10 = safe_float(rolling.get("excess_10d")) if rolling else None
    out_streak = safe_float(rolling.get("outperform_streak")) if rolling else None
    sigs = parse_signals(row.get("signal_labels"))

    # ─── 一票否决（放量大涨）───
    if ar is not None and ae is not None and ar > 1.0 and ae > 1.3:
        veto = True
        active.append(("放量大涨(anchor>1% & amount>1.3)", SELL_SIGNALS["放量大涨(anchor>1% & amount>1.3)"]))

    # ─── 买入信号 ───
    if e5 is not None:
        if e5 <= excess_5d_p15:
            active.append(("excess_5d_P15-(过冷≤-4.91%)", BUY_SIGNALS["excess_5d_P15-(过冷≤-4.91%)"]))
        elif e5 >= excess_5d_p85:
            active.append(("excess_5d_P85+(过热≥+5.74%)", SELL_SIGNALS["excess_5d_P85+(过热≥+5.74%)"]))

    if e10 is not None:
        if e10 <= excess_10d_p15:
            active.append(("excess_10d_P15-(过冷≤-6.11%)", BUY_SIGNALS["excess_10d_P15-(过冷≤-6.11%)"]))
        elif excess_10d_p70 <= e10 < excess_10d_p85:
            active.append(("excess_10d_P70-P85(温热)", SELL_SIGNALS["excess_10d_P70-P85(温热)"]))

    if delta_e5d is not None:
        if -3.1 <= delta_e5d <= -1.0:
            active.append(("delta_excess_5d_温和回调[-3,-1]", BUY_SIGNALS["delta_excess_5d_温和回调[-3,-1]"]))
        elif delta_e5d > 3.7:
            active.append(("delta_excess_5d_最快上升(>+3.7%)", SELL_SIGNALS["delta_excess_5d_最快上升(>+3.7%)"]))

    if out_streak is not None:
        if out_streak <= -3:
            active.append(("outperform_streak_≤-3(连续跑输)", BUY_SIGNALS["outperform_streak_≤-3(连续跑输)"]))
        elif out_streak >= 3:
            active.append(("outperform_streak_≥+3(连续跑赢)", SELL_SIGNALS["outperform_streak_≥+3(连续跑赢)"]))

    if ar is not None and mf is not None:
        if ar < 0 and mf > 0.6:
            active.append(("跌但资金支撑(anchor<0 & moneyflow>0.6)", BUY_SIGNALS["跌但资金支撑(anchor<0 & moneyflow>0.6)"]))

    if ar is not None and ae is not None:
        if ar < -0.5 and ae < 0.85:
            active.append(("缩量阴跌(anchor<-0.5% & amount<0.85)", BUY_SIGNALS["缩量阴跌(anchor<-0.5% & amount<0.85)"]))
        if ar < -1.0 and ae > 1.3:
            active.append(("放量大跌(anchor<-1% & amount>1.3)", SELL_SIGNALS["放量大跌(anchor<-1% & amount>1.3)"]))

    # Alpha 信号计数
    alpha_count = len(sigs & ALPHA_SIGNALS_SET)
    if alpha_count >= 3:
        active.append((f"alpha_signal_count_≥3 (实际{alpha_count})", BUY_SIGNALS["alpha_signal_count_≥3"]))

    # 交易观察池相关性快速上升
    if trading_corr_change is not None and trading_corr_change > 0.05:  # 5日变化>0.05
        active.append(("trading_corr_快速上升(回归)", BUY_SIGNALS["trading_corr_快速上升(回归)"]))

    # rs_vs_chain 分档
    if rs_chain is not None:
        if -2.1 <= rs_chain <= -0.8:
            active.append(("rs_vs_chain_Q2(偏弱档)", BUY_SIGNALS["rs_vs_chain_Q2(偏弱档)"]))
        elif rs_chain >= 1.7:
            active.append(("rs_vs_chain_Q5(极强档≥+1.7%)", SELL_SIGNALS["rs_vs_chain_Q5(极强档≥+1.7%)"]))

    # Beta 骑乘组合
    if "行业Beta为正" in sigs and "处于行业前排" in sigs:
        active.append(("Beta骑乘组合(Beta+ & 处于行业前排)", SELL_SIGNALS["Beta骑乘组合(Beta+ & 处于行业前排)"]))

    # 放量上涨信号
    if "放量上涨" in sigs:
        active.append(("信号_放量上涨", SELL_SIGNALS["信号_放量上涨"]))

    # 路径信号
    if prev_state and today_state:
        # 从弱格走来的强势格
        if prev_state in {"negative+negative", "negative+neutral"} and today_state in {"positive+positive", "positive+negative", "positive+neutral"}:
            active.append(("path_弱+弱→中或强(动能延续)", BUY_SIGNALS["path_弱+弱→中或强(动能延续)"]))
        # 强强转衰竭
        if prev_state == "positive+positive" and today_state in {"positive+negative", "neutral+negative"}:
            active.append(("path_强+强→强+弱(衰竭)", SELL_SIGNALS["path_强+强→强+弱(衰竭)"]))

    score = sum(w for _, w in active)
    return active, score, veto

# ── 回测引擎 ──────────────────────────────────────────────────────────────────

def backtest(history, rolling, pool_corr, signal_lift=None):
    """
    用 history_summary + rolling + pool_corr 回测综合信号策略
    """
    # 按日期 join
    rolling_by_date = {r["date"]: r for r in rolling}
    pc_by_date = {c["date"]: c for c in pool_corr}

    # 先算阈值（用全样本数据，是 in-sample，但作为基线参考）
    e5_vals = [safe_float(r["excess_5d"]) for r in rolling if safe_float(r["excess_5d"]) is not None]
    e10_vals = [safe_float(r["excess_10d"]) for r in rolling if safe_float(r["excess_10d"]) is not None]
    excess_5d_p15 = percentile(e5_vals, 15)
    excess_5d_p85 = percentile(e5_vals, 85)
    excess_10d_p15 = percentile(e10_vals, 15)
    excess_10d_p70 = percentile(e10_vals, 70)
    excess_10d_p85 = percentile(e10_vals, 85)

    print(f"[阈值] excess_5d  P15={excess_5d_p15:+.2f}%  P85={excess_5d_p85:+.2f}%")
    print(f"[阈值] excess_10d P15={excess_10d_p15:+.2f}%  P70={excess_10d_p70:+.2f}%  P85={excess_10d_p85:+.2f}%")

    # 按日期遍历
    rows_sorted = sorted(history, key=lambda r: r["date"])
    daily_results = []

    for i, row in enumerate(rows_sorted):
        date = row["date"]
        prev_row = rows_sorted[i-1] if i >= 1 else None
        rolling = rolling_by_date.get(date, {})
        prev_rolling = rolling_by_date.get(prev_row["date"], {}) if prev_row else {}

        # 计算 delta_e5d
        delta_e5d = None
        e5_today = safe_float(rolling.get("excess_5d"))
        e5_prev = safe_float(prev_rolling.get("excess_5d"))
        if e5_today is not None and e5_prev is not None:
            delta_e5d = e5_today - e5_prev

        # 计算 trading_corr 5日变化
        trading_corr_change = None
        if i >= 5:
            curr_pc = pc_by_date.get(date, {})
            prev_pc = pc_by_date.get(rows_sorted[i-5]["date"], {})
            t_now = safe_float(curr_pc.get("tradingWatchlist", {}).get("corr20d"))
            t_prev = safe_float(prev_pc.get("tradingWatchlist", {}).get("corr20d"))
            if t_now is not None and t_prev is not None:
                trading_corr_change = t_now - t_prev

        # 路径
        prev_state = state_key(prev_row) if prev_row else None
        today_state = state_key(row)

        # 评分
        active, score, veto = compute_active_signals(
            row, prev_row, rolling, prev_rolling, trading_corr_change,
            excess_5d_p15, excess_5d_p85, excess_10d_p15, excess_10d_p70, excess_10d_p85,
            delta_e5d, prev_state, today_state,
        )

        # 当日实际收益（用作 ground truth）
        next_1d_return = safe_float(row.get("next_1d_return"))
        next_1d_excess = safe_float(row.get("next_1d_excess_vs_chain"))
        next_3d_return = safe_float(row.get("next_3d_return"))
        next_3d_excess = safe_float(row.get("next_3d_excess_vs_chain"))

        daily_results.append({
            "date": date,
            "score": score,
            "veto": veto,
            "active_signals": [name for name, _ in active],
            "active_weights": active,
            "next_1d_return": next_1d_return,
            "next_1d_excess": next_1d_excess,
            "next_3d_return": next_3d_return,
            "next_3d_excess": next_3d_excess,
        })

    return daily_results, {
        "excess_5d_p15": excess_5d_p15,
        "excess_5d_p85": excess_5d_p85,
        "excess_10d_p15": excess_10d_p15,
        "excess_10d_p70": excess_10d_p70,
        "excess_10d_p85": excess_10d_p85,
    }

# ── 评估器 ────────────────────────────────────────────────────────────────────

def evaluate_strategy(daily_results, score_threshold=2):
    """
    对一个 score 阈值评估策略。
    多头：score >= +threshold → 做多（持有1日）
    空头：score <= -threshold → 空仓（收益 = 0）
    中性：abs(score) < threshold → 不操作（收益 = 0）

    评估指标：
      - 操作次数（信号触发频率）
      - 多头胜率
      - 累计绝对收益
      - 累计超额收益（vs chain）
      - vs buy-and-hold（永久持有）
    """
    long_days, short_days, neutral_days = [], [], []

    for d in daily_results:
        if d["next_1d_return"] is None:
            continue
        if d["veto"]:
            short_days.append(d)  # 一票否决归为空仓
            continue
        if d["score"] >= score_threshold:
            long_days.append(d)
        elif d["score"] <= -score_threshold:
            short_days.append(d)
        else:
            neutral_days.append(d)

    # 多头组（做多）
    long_abs = [d["next_1d_return"] for d in long_days]
    long_exc = [d["next_1d_excess"] for d in long_days if d["next_1d_excess"] is not None]
    long_abs_3d = [d["next_3d_return"] for d in long_days if d["next_3d_return"] is not None]
    long_exc_3d = [d["next_3d_excess"] for d in long_days if d["next_3d_excess"] is not None]

    # 空仓组（被警示，理论收益 = 0，但实际看真实收益是不是负的）
    short_abs = [d["next_1d_return"] for d in short_days]
    short_exc = [d["next_1d_excess"] for d in short_days if d["next_1d_excess"] is not None]

    # buy-and-hold（基准）
    all_abs = [d["next_1d_return"] for d in daily_results if d["next_1d_return"] is not None]
    all_exc = [d["next_1d_excess"] for d in daily_results if d["next_1d_excess"] is not None]

    def cum_log(vals):
        """累计对数收益，避免复利偏差"""
        s = 0.0
        for v in vals:
            if v is not None:
                s += math.log(1 + v / 100)
        return (math.exp(s) - 1) * 100  # 转回百分比

    return {
        "threshold": score_threshold,
        "long_days": {
            "n": len(long_days),
            "avg_1d_abs": round(sum(long_abs)/len(long_abs), 3) if long_abs else 0,
            "avg_1d_exc": round(sum(long_exc)/len(long_exc), 3) if long_exc else 0,
            "win_rate_abs": round(sum(1 for v in long_abs if v > 0)/len(long_abs), 3) if long_abs else 0,
            "win_rate_exc": round(sum(1 for v in long_exc if v > 0)/len(long_exc), 3) if long_exc else 0,
            "avg_3d_abs": round(sum(long_abs_3d)/len(long_abs_3d), 3) if long_abs_3d else 0,
            "avg_3d_exc": round(sum(long_exc_3d)/len(long_exc_3d), 3) if long_exc_3d else 0,
            "cum_log_abs": round(cum_log(long_abs), 2),
            "cum_log_exc": round(cum_log(long_exc), 2),
        },
        "short_days": {
            "n": len(short_days),
            "avg_1d_abs": round(sum(short_abs)/len(short_abs), 3) if short_abs else 0,
            "avg_1d_exc": round(sum(short_exc)/len(short_exc), 3) if short_exc else 0,
            "win_rate_abs": round(sum(1 for v in short_abs if v < 0)/len(short_abs), 3) if short_abs else 0,  # 跌的胜率
        },
        "neutral_days": {"n": len(neutral_days)},
        "buy_and_hold": {
            "n": len(all_abs),
            "avg_1d_abs": round(sum(all_abs)/len(all_abs), 3),
            "avg_1d_exc": round(sum(all_exc)/len(all_exc), 3),
            "win_rate_abs": round(sum(1 for v in all_abs if v > 0)/len(all_abs), 3),
            "cum_log_abs": round(cum_log(all_abs), 2),
            "cum_log_exc": round(cum_log(all_exc), 2),
        },
    }

# ── 打印 ──────────────────────────────────────────────────────────────────────

def print_strategy(eval_result):
    t = eval_result["threshold"]
    long_ = eval_result["long_days"]
    short = eval_result["short_days"]
    neutral = eval_result["neutral_days"]
    bah = eval_result["buy_and_hold"]
    print(f"\n  ━━ Threshold = ±{t} ━━")
    print(f"  操作天数：做多 {long_['n']}  | 空仓 {short['n']}  | 中性 {neutral['n']}  | 总 {bah['n']}")
    print(f"  做多组：")
    print(f"    平均 T+1 绝对收益: {fmt_pct(long_['avg_1d_abs'])}  超额: {fmt_pct(long_['avg_1d_exc'])}")
    print(f"    绝对胜率: {long_['win_rate_abs']*100:.1f}%  超额胜率: {long_['win_rate_exc']*100:.1f}%")
    print(f"    平均 T+3 绝对: {fmt_pct(long_['avg_3d_abs'])}  超额: {fmt_pct(long_['avg_3d_exc'])}")
    print(f"    累计绝对收益（持仓所有做多日）: {fmt_pct(long_['cum_log_abs'])}")
    print(f"    累计超额收益（vs 产业链）: {fmt_pct(long_['cum_log_exc'])}")
    print(f"  空仓组（被警示）：")
    print(f"    平均 T+1 绝对: {fmt_pct(short['avg_1d_abs'])}  超额: {fmt_pct(short['avg_1d_exc'])}")
    print(f"    跌幅胜率: {short['win_rate_abs']*100:.1f}% (validate 警示是否有效)")
    print(f"  Buy-and-Hold 基准：")
    print(f"    平均 T+1 绝对: {fmt_pct(bah['avg_1d_abs'])}  超额: {fmt_pct(bah['avg_1d_exc'])}")
    print(f"    绝对胜率: {bah['win_rate_abs']*100:.1f}%")
    print(f"    累计绝对（持仓所有日子）: {fmt_pct(bah['cum_log_abs'])}")
    print(f"    累计超额: {fmt_pct(bah['cum_log_exc'])}")

    # 计算策略 alpha
    alpha_per_trade = long_['avg_1d_exc'] - bah['avg_1d_exc']
    print(f"\n  📊 策略 Alpha（每次做多 vs buy-and-hold）: {fmt_pct(alpha_per_trade)} per trade")
    win_rate_lift = (long_['win_rate_abs'] - bah['win_rate_abs']) * 100
    print(f"  📊 胜率提升: {win_rate_lift:+.1f}pp (策略 {long_['win_rate_abs']*100:.1f}% vs 基准 {bah['win_rate_abs']*100:.1f}%)")


def print_score_distribution(daily_results):
    """打印综合分的分布"""
    scores = [d["score"] for d in daily_results]
    counts = defaultdict(int)
    for s in scores:
        bucket = min(max(s, -8), 8)
        counts[bucket] += 1
    print(f"\n  综合分分布（共 {len(scores)} 个交易日）:")
    for s in sorted(counts.keys()):
        bar = "█" * counts[s]
        print(f"  {s:+3d}  n={counts[s]:>3}  {bar}")


def print_top_signal_days(daily_results, n=5):
    """打印评分最高/最低的几个交易日"""
    valid = [d for d in daily_results if d["next_1d_return"] is not None]
    sorted_by_score = sorted(valid, key=lambda d: d["score"])

    print(f"\n  ▎评分最低的 {n} 天（最强卖出信号）:")
    print(f"  {'日期':<10} {'分数':>4}  {'实际T+1':>8}  {'实际T+1超额':>10}  激活信号")
    for d in sorted_by_score[:n]:
        sigs_str = " | ".join(d["active_signals"])[:80]
        print(f"  {d['date']:<10} {d['score']:>+4d}  {fmt_pct(d['next_1d_return']):>8}  "
              f"{fmt_pct(d['next_1d_excess']):>10}  {sigs_str}")

    print(f"\n  ▎评分最高的 {n} 天（最强买入信号）:")
    for d in sorted_by_score[-n:][::-1]:
        sigs_str = " | ".join(d["active_signals"])[:80]
        print(f"  {d['date']:<10} {d['score']:>+4d}  {fmt_pct(d['next_1d_return']):>8}  "
              f"{fmt_pct(d['next_1d_excess']):>10}  {sigs_str}")


def print_today_signal(daily_results):
    """打印今日（最后一天）的信号详情"""
    today = daily_results[-1]
    print(f"\n  ▎今日（{today['date']}）综合信号详情:")
    print(f"  综合分：{today['score']:+d}")
    if today['veto']:
        print(f"  ⛔ 一票否决触发！当日不操作。")
    print(f"  激活信号（{len(today['active_signals'])} 个）:")
    for name, weight in today["active_weights"]:
        sign = "🟢" if weight > 0 else "🔴" if weight < 0 else "⬜"
        print(f"    {sign} ({weight:+d}) {name}")

    # 操作建议
    print(f"\n  💡 操作建议：")
    if today['veto']:
        print(f"    ⛔ 当日不做多（一票否决）")
    elif today['score'] >= 4:
        print(f"    ⭐⭐⭐ 强买入信号（分数≥4）")
    elif today['score'] >= 2:
        print(f"    ⭐⭐ 中等买入信号（分数=2-3）")
    elif today['score'] >= 1:
        print(f"    ⭐ 弱买入信号")
    elif today['score'] <= -4:
        print(f"    🔴🔴🔴 强卖出/空仓（分数≤-4）")
    elif today['score'] <= -2:
        print(f"    🔴🔴 中等卖出（分数=-2~-3）")
    elif today['score'] <= -1:
        print(f"    🔴 弱卖出参考")
    else:
        print(f"    ⏸ 中性，不操作")


# ── 主函数 ────────────────────────────────────────────────────────────────────

def main():
    print("="*75)
    print("  综合信号策略回测（叠加 A-P 所有强信号）")
    print("="*75)

    # 加载数据
    with open(HISTORY_CSV, encoding="utf-8") as f:
        history = list(csv.DictReader(f))
    with open(ROLLING_CSV, encoding="utf-8") as f:
        rolling = list(csv.DictReader(f))
    with open(DASHBOARD_JSON, encoding="utf-8") as f:
        dash = json.load(f)
    pool_corr = dash.get("trends", {}).get("poolCorrelations", [])

    print(f"\n[INFO] history: {len(history)} 行, rolling: {len(rolling)} 行, poolCorr: {len(pool_corr)} 行")

    # 回测
    daily_results, thresholds = backtest(history, rolling, pool_corr)

    # 打印分布
    print_score_distribution(daily_results)

    # 对多个阈值评估
    print("\n" + "="*75)
    print("  各阈值的策略表现对比")
    print("="*75)
    results_by_threshold = {}
    for t in [1, 2, 3, 4, 5]:
        eval_r = evaluate_strategy(daily_results, score_threshold=t)
        results_by_threshold[t] = eval_r
        print_strategy(eval_r)

    # 最高/最低分日的实际表现
    print("\n" + "="*75)
    print("  极端信号日的实际验证")
    print("="*75)
    print_top_signal_days(daily_results, n=8)

    # 今日信号
    print("\n" + "="*75)
    print("  今日信号操作建议")
    print("="*75)
    print_today_signal(daily_results)

    # 输出 JSON
    output = {
        "generatedAt": history[-1]["date"] if history else "",
        "thresholds": thresholds,
        "signal_weights": {"buy": BUY_SIGNALS, "sell": SELL_SIGNALS},
        "strategy_results_by_threshold": results_by_threshold,
        "daily_results": [
            {
                "date": d["date"],
                "score": d["score"],
                "veto": d["veto"],
                "signals": d["active_signals"],
                "next_1d_return": d["next_1d_return"],
                "next_1d_excess": d["next_1d_excess"],
            } for d in daily_results
        ],
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    sz = OUTPUT_JSON.stat().st_size / 1024
    print(f"\n[OK] 结果写入：{OUTPUT_JSON}  ({sz:.1f} KB)")


if __name__ == "__main__":
    main()
