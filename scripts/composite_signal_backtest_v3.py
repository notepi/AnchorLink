#!/usr/bin/env python3
"""
信号实验室升级 - V3 综合评分回测
基于 P1 深度研究发现，在 V2 基础上升级：

1. CUSUM 方向性信号：trending_up 是比 ADX trending 更清晰的看空状态
2. 看跌FVG veto 升级：交互分析发现它是"毒药放大器"
3. CUSUM × Streak 交叉信号
4. 信号衰减感知：不同持仓期信号分桶
5. Regime×Score 自适应仓位
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "output"
PRICE_DIR = ROOT / "data" / "price" / "normalized"


# ── 技术指标（与 V2 一致）──────────────────────────────────────────────────

def calc_rsi(closes, period=14):
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_macd(closes, fast=12, slow=26, signal=9):
    ema_fast = closes.ewm(span=fast, min_periods=fast).mean()
    ema_slow = closes.ewm(span=slow, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_bollinger(closes, period=20, num_std=2.0):
    middle = closes.rolling(period).mean()
    std = closes.rolling(period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    bandwidth = (upper - lower) / middle.replace(0, np.nan)
    pct_b = (closes - lower) / (upper - lower).replace(0, np.nan)
    return upper, middle, lower, bandwidth, pct_b


def calc_adx(highs, lows, closes, period=14):
    tr1 = highs - lows
    tr2 = (highs - closes.shift(1)).abs()
    tr3 = (lows - closes.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    plus_dm = highs - highs.shift(1)
    minus_dm = lows.shift(1) - lows
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    atr = tr.ewm(alpha=1 / period, min_periods=period).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr.replace(0, np.nan))
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    return dx.ewm(alpha=1 / period, min_periods=period).mean()


def calc_stochastic(highs, lows, closes, k_period=14, d_period=3):
    lowest_low = lows.rolling(k_period).min()
    highest_high = highs.rolling(k_period).max()
    k = 100 * (closes - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    return k, d


def calc_atr(highs, lows, closes, period=14):
    tr1 = highs - lows
    tr2 = (highs - closes.shift(1)).abs()
    tr3 = (lows - closes.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period).mean()


def compute_cusum_regime(closes, atr, h_mult=1.0):
    returns = closes.pct_change()
    rolling_mean = returns.rolling(20).mean()
    rolling_std = returns.rolling(20).std()
    residuals = (returns - rolling_mean) / rolling_std.replace(0, np.nan)
    residuals = residuals.fillna(0)

    cum_pos = pd.Series(0.0, index=closes.index)
    cum_neg = pd.Series(0.0, index=closes.index)

    for i in range(1, len(closes)):
        cum_pos.iloc[i] = max(0, cum_pos.iloc[i - 1] + residuals.iloc[i] - 0.1)
        cum_neg.iloc[i] = min(0, cum_neg.iloc[i - 1] + residuals.iloc[i] + 0.1)

    regime = pd.Series("mean_reverting", index=closes.index)
    regime[cum_pos > h_mult] = "trending_up"
    regime[cum_neg < -h_mult] = "trending_down"
    return regime


# ── 信号定义 ──────────────────────────────────────────────────────────────

ALPHA_SIGNALS = {
    "资金价格背离", "主力资金拖累", "行业扩散不足", "交易观察池降温",
    "行业Beta为中性", "主题情绪强但主线池弱", "行业Beta为负",
    "情绪池强于产业链", "放量下跌",
}


def parse_signal_labels(s) -> set:
    if pd.isna(s) or s == "[]":
        return set()
    try:
        return set(json.loads(s.replace("'", '"'))) if isinstance(s, str) else set()
    except Exception:
        return set()


# ── 数据加载 ────────────────────────────────────────────────────────────────

def load_and_prepare_data() -> pd.DataFrame:
    print("[INFO] 加载数据...")

    price_df = pd.read_parquet(PRICE_DIR / "market_data_normalized.parquet")
    blt = price_df[price_df["ts_code"] == "688333.SH"].copy()
    blt["trade_date"] = pd.to_datetime(blt["trade_date"])
    blt = blt.sort_values("trade_date").reset_index(drop=True)
    blt["date_str"] = blt["trade_date"].dt.strftime("%Y%m%d")

    hist = pd.read_csv(DATA_DIR / "history_summary.csv")
    hist["date_str"] = hist["date"].astype(str)
    rolling = pd.read_csv(DATA_DIR / "history_rolling_metrics.csv")
    rolling["date_str"] = rolling["date"].astype(str)

    df = blt.merge(hist, on="date_str", how="inner", suffixes=("", "_hist"))
    df = df.merge(rolling, on="date_str", how="inner", suffixes=("", "_roll"))

    print("[INFO] 计算技术指标...")
    c, h, l = df["close"], df["high"], df["low"]

    df["rsi_14"] = calc_rsi(c)
    macd_line, signal_line, histogram = calc_macd(c)
    df["macd_hist"] = histogram
    bb_upper, bb_mid, bb_lower, bb_bw, bb_pctb = calc_bollinger(c)
    df["bb_pctb"] = bb_pctb
    df["bb_bw"] = bb_bw
    df["adx_14"] = calc_adx(h, l, c)
    stoch_k, stoch_d = calc_stochastic(h, l, c)
    df["stoch_k"] = stoch_k
    df["atr_14"] = calc_atr(h, l, c)

    kc_mid = c.ewm(span=20, min_periods=20).mean()
    kc_upper = kc_mid + 1.5 * df["atr_14"]
    kc_lower = kc_mid - 1.5 * df["atr_14"]
    df["squeeze_on"] = (bb_lower > kc_lower) & (bb_upper < kc_upper)

    # ADX Regime
    df["regime"] = "transition"
    df.loc[df["adx_14"] >= 25, "regime"] = "trending"
    df.loc[df["adx_14"] <= 20, "regime"] = "mean_reverting"

    # CUSUM Regime
    print("[INFO] 计算 CUSUM Regime...")
    df["cusum_regime"] = compute_cusum_regime(c, df["atr_14"], h_mult=1.0)

    # 季节性
    df["dow"] = df["trade_date"].dt.dayofweek
    df["month"] = df["trade_date"].dt.month

    # SMC
    df["liq_sweep_high"] = (df["high"] > df["high"].shift(1)) & (df["close"] < df["high"].shift(1))
    df["n_day_high"] = df["close"].rolling(20).max()
    df["bos_20d_high"] = df["close"] >= df["n_day_high"]
    df["n_day_low"] = df["close"].rolling(20).min()
    df["bos_20d_low"] = df["close"] <= df["n_day_low"]
    df["choch_up"] = df["bos_20d_low"].shift(1) & (df["close"] > df["close"].shift(1))
    df["bearish_fvg"] = False
    for i in range(1, len(df) - 1):
        gap_down = df.iloc[i - 1]["low"] - df.iloc[i + 1]["high"]
        if gap_down > 0 and (gap_down / df.iloc[i - 1]["low"]) * 100 >= 0.3:
            df.loc[df.index[i], "bearish_fvg"] = True

    df["signal_set"] = df["signal_labels"].apply(parse_signal_labels)
    df["alpha_count"] = df["signal_set"].apply(lambda s: len(s & ALPHA_SIGNALS))

    # 状态键
    def state_key(row):
        beta = "positive" if row.get("industry_beta") == "positive" else (
            "negative" if row.get("industry_beta") == "negative" else "neutral")
        alpha = "positive" if row.get("anchor_alpha") == "positive" else (
            "negative" if row.get("anchor_alpha") == "negative" else "neutral")
        return f"{beta}+{alpha}"

    df["today_state"] = df.apply(state_key, axis=1)
    df["prev_state"] = df["today_state"].shift(1)

    print(f"[OK] 数据准备完成: {len(df)} 行")
    return df


# ── V3 信号计算 ─────────────────────────────────────────────────────────────

def compute_v3_signals(row, thresholds: dict) -> tuple:
    """计算 V3 综合评分，含 CUSUM 信号和看跌FVG veto 升级"""
    active_buy = []
    active_sell = []
    regime = row.get("regime", "transition")
    cusum_regime = row.get("cusum_regime", "mean_reverting")
    out_streak = row.get("outperform_streak", 0)

    e5 = row.get("excess_5d", np.nan)
    e10 = row.get("excess_10d", np.nan)
    ar = row.get("anchor_return", 0)
    mf = row.get("moneyflow_positive_ratio", 0)
    ae = row.get("amount_expansion_ratio", 1)
    alpha_count = row.get("alpha_count", 0)
    rs_chain = row.get("relative_strength_vs_industry_chain", 0)
    sigs = row.get("signal_set", set())

    rsi = row.get("rsi_14", np.nan)
    stoch_k = row.get("stoch_k", np.nan)
    macd_hist = row.get("macd_hist", np.nan)
    bb_pctb = row.get("bb_pctb", np.nan)
    adx = row.get("adx_14", np.nan)
    bearish_fvg = row.get("bearish_fvg", False)
    liq_sweep = row.get("liq_sweep_high", False)
    bos_high = row.get("bos_20d_high", False)
    dow = row.get("dow", -1)
    month = row.get("month", -1)
    bb_bw = row.get("bb_bw", np.nan)

    # ── V1 信号 ──
    if pd.notna(e5) and e5 <= thresholds["excess_5d_p15"]:
        active_buy.append(("excess_5d_P15-", +3))
    if pd.notna(e5) and e5 >= thresholds["excess_5d_p85"]:
        active_sell.append(("excess_5d_P85+", -3))
    if pd.notna(e10) and e10 <= thresholds["excess_10d_p15"]:
        active_buy.append(("excess_10d_P15-", +3))
    if pd.notna(e10) and thresholds.get("excess_10d_p70") and e10 >= thresholds["excess_10d_p70"] and e10 < thresholds.get("excess_10d_p85", 999):
        active_sell.append(("excess_10d_P70-P85", -1))

    if isinstance(out_streak, (int, float)) and out_streak <= -3 and regime != "mean_reverting":
        active_buy.append(("outperform_streak_≤-3", +3))
    if isinstance(out_streak, (int, float)) and out_streak >= 3:
        active_sell.append(("outperform_streak_≥+3", -2))

    if ar < 0 and mf > 0.6:
        active_buy.append(("跌但资金支撑", +2))
    if ar < -0.5 and ae < 0.85:
        active_buy.append(("缩量阴跌", +1))
    if ar > 1.0 and ae > 1.3:
        active_sell.append(("放量大涨", -3))
    if ar < -1.0 and ae > 1.3:
        active_sell.append(("放量大跌", -1))

    if alpha_count >= 3:
        active_buy.append(("alpha_signal_count_≥3", +2))

    if isinstance(rs_chain, (int, float)) and -2.1 <= rs_chain <= -0.8:
        active_buy.append(("rs_vs_chain_Q2", +1))
    if isinstance(rs_chain, (int, float)) and rs_chain >= 1.7:
        active_sell.append(("rs_vs_chain_Q5", -2))

    if "行业Beta为正" in sigs and "处于行业前排" in sigs:
        active_sell.append(("Beta骑乘组合", -2))
    if "放量上涨" in sigs:
        active_sell.append(("信号_放量上涨", -2))

    prev = row.get("prev_state", "")
    today = row.get("today_state", "")
    if prev in ("negative+negative", "negative+neutral") and today in (
            "positive+positive", "positive+negative", "positive+neutral"):
        active_buy.append(("path_弱→强", +2))
    if prev == "positive+positive" and today in ("positive+negative", "neutral+negative"):
        active_sell.append(("path_强→弱", -1))

    # ── V2 信号（P0 新增）──
    if isinstance(out_streak, (int, float)):
        if regime == "mean_reverting" and out_streak <= -3:
            active_buy.append(("MR+streak≤-3", +5))
        elif regime == "mean_reverting" and out_streak <= -2:
            active_buy.append(("MR+streak≤-2", +3))
        elif regime == "transition" and out_streak <= -2:
            active_buy.append(("TS+streak≤-2", +3))
        elif regime == "transition" and out_streak >= 2:
            active_sell.append(("TS+streak≥+2", -4))

    if pd.notna(macd_hist) and macd_hist < 0:
        active_buy.append(("MACD柱负", +1))
    if pd.notna(rsi) and rsi > 70:
        active_sell.append(("RSI超买", -2))
    if pd.notna(stoch_k) and stoch_k > 80:
        active_sell.append(("Stoch超买", -2))
    if pd.notna(bb_pctb) and bb_pctb > 1:
        active_sell.append(("BB上轨触及", -2))

    if dow == 2:
        active_buy.append(("周三", +1))
    if dow == 4:
        active_sell.append(("周五", -2))
        if pd.notna(adx) and adx < 25:
            active_sell.append(("周五+ADX<25", -3))

    if liq_sweep:
        active_buy.append(("LiqSweep高", +1))
    if bos_high:
        active_sell.append(("BOS新高", -1))

    # ── V3 信号（P1 新增）──

    # 看跌FVG 升级为 veto 级
    if bearish_fvg:
        active_sell.append(("看跌FVG", -4))  # 从 -2 升级到 -4

    # 看跌FVG × streak≤-2 交互（毒药放大器）
    if bearish_fvg and isinstance(out_streak, (int, float)) and out_streak >= -1:
        active_sell.append(("FVG+非弱streak", -3))  # 额外惩罚

    # CUSUM 方向性信号
    if cusum_regime == "trending_up":
        active_sell.append(("CUSUM上行趋势", -1))
        # CUSUM trending_up + streak≥+2
        if isinstance(out_streak, (int, float)) and out_streak >= 2:
            active_sell.append(("CUSUM_UP+streak≥+2", -3))
    elif cusum_regime == "trending_down":
        active_buy.append(("CUSUM下行趋势", +1))
        # CUSUM trending_down + streak≤-2
        if isinstance(out_streak, (int, float)) and out_streak <= -2:
            active_buy.append(("CUSUM_DN+streak≤-2", +2))

    # 8月效应
    if month == 8:
        active_buy.append(("8月效应", +1))

    # ── 汇总评分 ──
    total = sum(w for _, w in active_buy) + sum(w for _, w in active_sell)
    all_signals = active_buy + active_sell
    signal_names = [f"{n}({w:+d})" for n, w in all_signals]

    # Veto 判定
    veto = (ar > 1.0 and ae > 1.3) or (bearish_fvg and total <= -5)

    return total, veto, signal_names


def compute_thresholds_from_sample(sample: pd.DataFrame) -> dict:
    e5 = sample["excess_5d"].dropna()
    e10 = sample["excess_10d"].dropna()
    return {
        "excess_5d_p15": e5.quantile(0.15) if len(e5) > 10 else -4.91,
        "excess_5d_p85": e5.quantile(0.85) if len(e5) > 10 else 5.74,
        "excess_10d_p15": e10.quantile(0.15) if len(e10) > 10 else -6.11,
        "excess_10d_p70": e10.quantile(0.70) if len(e10) > 10 else 3.0,
        "excess_10d_p85": e10.quantile(0.85) if len(e10) > 10 else 5.5,
    }


def walk_forward_backtest(df, train_window=120, version="v3"):
    results = []
    for i in range(train_window, len(df)):
        train = df.iloc[max(0, i - train_window):i]
        test_row = df.iloc[i]
        thresholds = compute_thresholds_from_sample(train)

        if version == "v3":
            score, veto, signals = compute_v3_signals(test_row, thresholds)
        else:
            # V2 fallback（从 V2 脚本导入）
            from composite_signal_backtest_v2 import compute_composite_score
            score, veto, signals = compute_composite_score(test_row, thresholds, use_v2=True, use_regime=True)

        next_exc = test_row.get("next_1d_excess_vs_chain", np.nan)
        next_abs = test_row.get("next_1d_return", np.nan)

        results.append({
            "date": test_row["date_str"],
            "score": score,
            "veto": veto,
            "regime": test_row.get("regime", ""),
            "cusum_regime": test_row.get("cusum_regime", ""),
            "signals": signals,
            "next_1d_excess": next_exc if pd.notna(next_exc) else None,
            "next_1d_abs": next_abs if pd.notna(next_abs) else None,
        })
    return results


def cum_log(vals):
    s = 0.0
    for v in vals:
        if abs(v) < 100:
            s += math.log(1 + v / 100)
    return (math.exp(s) - 1) * 100


def evaluate_strategy(results, threshold, regime_filter=None):
    long_days = []
    short_days = []

    for r in results:
        if regime_filter and r.get("regime") != regime_filter:
            continue
        exc = r["next_1d_excess"]
        if exc is None:
            continue
        if r["veto"]:
            short_days.append(r)
        elif r["score"] >= threshold:
            long_days.append(r)
        elif r["score"] <= -threshold:
            short_days.append(r)

    def stats(days, label):
        if not days:
            return {"label": label, "n": 0}
        exc_vals = [d["next_1d_excess"] for d in days if d["next_1d_excess"] is not None]
        if not exc_vals:
            return {"label": label, "n": len(days)}
        arr = np.array(exc_vals)
        return {
            "label": label,
            "n": len(arr),
            "avg_1d_exc": round(float(np.mean(arr)), 4),
            "win_rate_exc": round(float((arr > 0).mean()), 4),
            "cum_log_exc": round(float(cum_log(arr)), 2),
        }

    return {
        "threshold": threshold,
        "regime_filter": regime_filter,
        "long": stats(long_days, "long"),
        "short": stats(short_days, "short"),
    }


def max_drawdown(returns_arr):
    if len(returns_arr) < 2:
        return 0.0
    cum = np.cumprod(1 + np.array(returns_arr) / 100)
    peak = np.maximum.accumulate(cum)
    dd = (cum - peak) / peak
    return round(float(dd.min()) * 100, 2)


def sharpe(returns_arr):
    arr = np.array(returns_arr)
    if len(arr) < 10 or arr.std() == 0:
        return 0.0
    return round(float(arr.mean() / arr.std() * np.sqrt(252)), 3)


# ── 主函数 ──────────────────────────────────────────────────────────────────

def main():
    df = load_and_prepare_data()

    print("\n" + "=" * 70)
    print("  V3 综合评分回测（P1 深度研究结果集成）")
    print("=" * 70)

    # V2 回测（基线）
    print("\n[INFO] 运行 V2 回测...")
    v2_results = walk_forward_backtest(df, version="v2")

    # V3 回测
    print("[INFO] 运行 V3 回测...")
    v3_results = walk_forward_backtest(df, version="v3")

    print(f"\n  Walk-Forward: 训练窗口=120天, 测试集={len(v2_results)}天")

    # ── 对比表 ──
    print("\n  ── V2 vs V3 对比 ──")
    configs = [
        ("V2", v2_results),
        ("V3", v3_results),
    ]

    comparison = {}

    for label, results in configs:
        print(f"\n    {label}:")
        comp_data = {}
        for threshold in [3, 4, 5]:
            ev = evaluate_strategy(results, threshold)
            ld = ev["long"]
            sd = ev["short"]

            if ld["n"] > 0:
                long_exc = [r["next_1d_excess"] for r in results
                            if r["score"] >= threshold and not r["veto"]
                            and r["next_1d_excess"] is not None]
                dd = max_drawdown(long_exc) if long_exc else 0
                sh = sharpe(long_exc) if long_exc else 0

                comp_data[f"±{threshold}"] = {
                    "long_n": ld["n"],
                    "long_wr": ld["win_rate_exc"],
                    "long_avg": ld["avg_1d_exc"],
                    "long_cum": ld["cum_log_exc"],
                    "long_dd": dd,
                    "long_sharpe": sh,
                    "short_n": sd["n"],
                    "short_wr": sd.get("win_rate_exc", 0),
                }

                print(f"      ±{threshold}: 做多n={ld['n']}, wr={ld['win_rate_exc']:.1%}, "
                      f"avg={ld['avg_1d_exc']:+.3f}%, cum={ld['cum_log_exc']:+.1f}%, "
                      f"dd={dd:.1f}%, sharpe={sh:.2f}")
                if sd["n"] > 0:
                    print(f"             做空n={sd['n']}, wr={sd.get('win_rate_exc', 0):.1%}")

        comparison[label] = comp_data

    # ── Regime 分组 ──
    print("\n  ── V3 Regime 分组效果 ──")
    regime_results = {}
    for regime in ["mean_reverting", "trending", "transition"]:
        ev = evaluate_strategy(v3_results, 3, regime_filter=regime)
        ld = ev["long"]
        if ld["n"] > 0:
            regime_results[regime] = ld
            print(f"    {regime}: n={ld['n']}, wr={ld['win_rate_exc']:.1%}, "
                  f"avg={ld['avg_1d_exc']:+.3f}%")

    # ── CUSUM Regime 分组 ──
    print("\n  ── V3 CUSUM Regime 分组效果 ──")
    cusum_results = {}
    for cr in ["mean_reverting", "trending_up", "trending_down"]:
        cr_days = [r for r in v3_results if r.get("cusum_regime") == cr]
        long_days = [r for r in cr_days if r["score"] >= 3 and not r["veto"] and r["next_1d_excess"] is not None]
        if len(long_days) >= 3:
            exc_vals = [d["next_1d_excess"] for d in long_days]
            arr = np.array(exc_vals)
            stat = {
                "n": len(arr),
                "avg_exc": round(float(np.mean(arr)), 4),
                "win_rate": round(float((arr > 0).mean()), 4),
            }
            cusum_results[cr] = stat
            print(f"    CUSUM_{cr}: n={stat['n']}, wr={stat['win_rate']:.1%}, "
                  f"avg={stat['avg_exc']:+.3f}%")

    # ── 看跌FVG veto 效果 ──
    print("\n  ── 看跌FVG veto 升级效果 ──")
    fvg_days = [r for r in v3_results if "看跌FVG" in str(r["signals"])]
    if fvg_days:
        fvg_exc = [r["next_1d_excess"] for r in fvg_days if r["next_1d_excess"] is not None]
        if fvg_exc:
            arr = np.array(fvg_exc)
            print(f"    看跌FVG日: n={len(arr)}, avg={np.mean(arr):+.3f}%, wr={(arr>0).mean():.1%}")

    fvg_veto_days = [r for r in v3_results if r["veto"] and "看跌FVG" in str(r["signals"])]
    if fvg_veto_days:
        fvg_veto_exc = [r["next_1d_excess"] for r in fvg_veto_days if r["next_1d_excess"] is not None]
        if fvg_veto_exc:
            arr = np.array(fvg_veto_exc)
            print(f"    看跌FVG veto日: n={len(arr)}, avg={np.mean(arr):+.3f}%, wr={(arr>0).mean():.1%}")

    # ── 评分极端日 ──
    print("\n  ── V3 评分极端日 ──")
    sorted_v3 = sorted(v3_results, key=lambda x: x["score"], reverse=True)

    print("\n  评分最高 5 天:")
    for r in sorted_v3[:5]:
        exc = r["next_1d_excess"]
        hit = "✓" if exc is not None and exc > 0 else "✗"
        print(f"    {hit} {r['date']}: score={r['score']}, regime={r['regime']}, "
              f"cusum={r.get('cusum_regime', '')}, T+1={exc:+.3f}%")

    print("\n  评分最低 5 天:")
    for r in sorted_v3[-5:]:
        exc = r["next_1d_excess"]
        hit = "✓" if exc is not None and exc < 0 else "✗"
        print(f"    {hit} {r['date']}: score={r['score']}, regime={r['regime']}, "
              f"cusum={r.get('cusum_regime', '')}, T+1={exc:+.3f}%")

    # ── 输出 ──
    output = {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "comparison": comparison,
        "regime_results": regime_results,
        "cusum_results": cusum_results,
        "daily_results_v3": v3_results,
    }

    out_path = DATA_DIR / "composite_signal_backtest_v3.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n[OK] 输出: {out_path}")


if __name__ == "__main__":
    main()
