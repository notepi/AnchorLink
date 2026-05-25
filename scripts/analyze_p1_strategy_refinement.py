#!/usr/bin/env python3
"""
信号实验室 - V3.1 策略精炼
1. CUSUM 仅用于卖出侧（trending_up 信号有效，trending_down 买入信号稀释质量）
2. 多持仓期策略（信号衰减分析 → 不同信号持有不同天数）
3. 看跌FVG veto 保留
4. Regime 自适应阈值（与 V2 保守策略一致）
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


# ── 技术指标（同 V2/V3）───────────────────────────────────────────────────

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
    return macd_line, signal_line, macd_line - signal_line


def calc_bollinger(closes, period=20, num_std=2.0):
    middle = closes.rolling(period).mean()
    std = closes.rolling(period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    bw = (upper - lower) / middle.replace(0, np.nan)
    pct_b = (closes - lower) / (upper - lower).replace(0, np.nan)
    return upper, middle, lower, bw, pct_b


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
    ll = lows.rolling(k_period).min()
    hh = highs.rolling(k_period).max()
    k = 100 * (closes - ll) / (hh - ll).replace(0, np.nan)
    return k, k.rolling(d_period).mean()


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


def load_and_prepare_data():
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

    print("[INFO] 计算指标...")
    c, h, l = df["close"], df["high"], df["low"]
    df["rsi_14"] = calc_rsi(c)
    _, _, df["macd_hist"] = calc_macd(c)
    _, _, _, df["bb_bw"], df["bb_pctb"] = calc_bollinger(c)
    df["adx_14"] = calc_adx(h, l, c)
    df["stoch_k"], _ = calc_stochastic(h, l, c)
    df["atr_14"] = calc_atr(h, l, c)

    kc_mid = c.ewm(span=20, min_periods=20).mean()
    df["squeeze_on"] = (c - 2 * c.rolling(20).std() > kc_mid - 1.5 * df["atr_14"]) & \
                       (c + 2 * c.rolling(20).std() < kc_mid + 1.5 * df["atr_14"])

    df["regime"] = "transition"
    df.loc[df["adx_14"] >= 25, "regime"] = "trending"
    df.loc[df["adx_14"] <= 20, "regime"] = "mean_reverting"
    df["cusum_regime"] = compute_cusum_regime(c, df["atr_14"], 1.0)

    df["dow"] = df["trade_date"].dt.dayofweek
    df["month"] = df["trade_date"].dt.month

    df["liq_sweep_high"] = (df["high"] > df["high"].shift(1)) & (df["close"] < df["high"].shift(1))
    df["n_day_high"] = df["close"].rolling(20).max()
    df["bos_20d_high"] = df["close"] >= df["n_day_high"]
    df["n_day_low"] = df["close"].rolling(20).min()
    df["bos_20d_low"] = df["close"] <= df["n_day_low"]
    df["bearish_fvg"] = False
    for i in range(1, len(df) - 1):
        gap = df.iloc[i - 1]["low"] - df.iloc[i + 1]["high"]
        if gap > 0 and (gap / df.iloc[i - 1]["low"]) * 100 >= 0.3:
            df.loc[df.index[i], "bearish_fvg"] = True

    df["signal_set"] = df["signal_labels"].apply(parse_signal_labels)
    df["alpha_count"] = df["signal_set"].apply(lambda s: len(s & ALPHA_SIGNALS))

    def state_key(row):
        beta = "positive" if row.get("industry_beta") == "positive" else (
            "negative" if row.get("industry_beta") == "negative" else "neutral")
        alpha = "positive" if row.get("anchor_alpha") == "positive" else (
            "negative" if row.get("anchor_alpha") == "negative" else "neutral")
        return f"{beta}+{alpha}"

    df["today_state"] = df.apply(state_key, axis=1)
    df["prev_state"] = df["today_state"].shift(1)

    # 多日收益
    for d in [2, 3, 5]:
        df[f"next_{d}d_return"] = df["close"].shift(-d) / df["close"] - 1

    print(f"[OK] 数据准备完成: {len(df)} 行")
    return df


# ── V3.1 评分（CUSUM 仅卖侧 + 看跌FVG veto）─────────────────────────────

def compute_v31_score(row, thresholds):
    """V3.1: V2 评分 + CUSUM 卖出信号 + 看跌FVG veto"""
    buy = []
    sell = []
    regime = row.get("regime", "transition")
    cusum = row.get("cusum_regime", "mean_reverting")
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

    # V1 信号
    if pd.notna(e5) and e5 <= thresholds["excess_5d_p15"]:
        buy.append(("excess_5d_P15-", +3))
    if pd.notna(e5) and e5 >= thresholds["excess_5d_p85"]:
        sell.append(("excess_5d_P85+", -3))
    if pd.notna(e10) and e10 <= thresholds["excess_10d_p15"]:
        buy.append(("excess_10d_P15-", +3))
    if pd.notna(e10) and thresholds.get("excess_10d_p70") and e10 >= thresholds["excess_10d_p70"] and e10 < thresholds.get("excess_10d_p85", 999):
        sell.append(("excess_10d_P70-P85", -1))

    if isinstance(out_streak, (int, float)):
        if out_streak <= -3 and regime != "mean_reverting":
            buy.append(("streak≤-3", +3))
        if out_streak >= 3:
            sell.append(("streak≥+3", -2))

    if ar < 0 and mf > 0.6:
        buy.append(("跌但资金支撑", +2))
    if ar < -0.5 and ae < 0.85:
        buy.append(("缩量阴跌", +1))
    if ar > 1.0 and ae > 1.3:
        sell.append(("放量大涨", -3))
    if ar < -1.0 and ae > 1.3:
        sell.append(("放量大跌", -1))

    if alpha_count >= 3:
        buy.append(("alpha≥3", +2))

    if isinstance(rs_chain, (int, float)):
        if -2.1 <= rs_chain <= -0.8:
            buy.append(("rs_Q2", +1))
        if rs_chain >= 1.7:
            sell.append(("rs_Q5", -2))

    if "行业Beta为正" in sigs and "处于行业前排" in sigs:
        sell.append(("Beta骑乘", -2))
    if "放量上涨" in sigs:
        sell.append(("信号_放量上涨", -2))

    prev = row.get("prev_state", "")
    today = row.get("today_state", "")
    if prev in ("negative+negative", "negative+neutral") and today in (
            "positive+positive", "positive+negative", "positive+neutral"):
        buy.append(("path弱→强", +2))
    if prev == "positive+positive" and today in ("positive+negative", "neutral+negative"):
        sell.append(("path强→弱", -1))

    # V2 新增
    if isinstance(out_streak, (int, float)):
        if regime == "mean_reverting" and out_streak <= -3:
            buy.append(("MR+streak≤-3", +5))
        elif regime == "mean_reverting" and out_streak <= -2:
            buy.append(("MR+streak≤-2", +3))
        elif regime == "transition" and out_streak <= -2:
            buy.append(("TS+streak≤-2", +3))
        elif regime == "transition" and out_streak >= 2:
            sell.append(("TS+streak≥+2", -4))

    if pd.notna(macd_hist) and macd_hist < 0:
        buy.append(("MACD柱负", +1))
    if pd.notna(rsi) and rsi > 70:
        sell.append(("RSI超买", -2))
    if pd.notna(stoch_k) and stoch_k > 80:
        sell.append(("Stoch超买", -2))
    if pd.notna(bb_pctb) and bb_pctb > 1:
        sell.append(("BB上轨", -2))

    if dow == 2:
        buy.append(("周三", +1))
    if dow == 4:
        sell.append(("周五", -2))
        if pd.notna(adx) and adx < 25:
            sell.append(("周五+ADX<25", -3))

    if liq_sweep:
        buy.append(("LiqSweep高", +1))
    if bos_high:
        sell.append(("BOS新高", -1))

    # V3.1 P1 新增
    # 看跌FVG 升级（毒药放大器）
    if bearish_fvg:
        sell.append(("看跌FVG", -4))

    # CUSUM 仅卖侧
    if cusum == "trending_up":
        sell.append(("CUSUM上行", -1))
        if isinstance(out_streak, (int, float)) and out_streak >= 2:
            sell.append(("CUSUM_UP+streak≥+2", -3))

    # 8月效应
    if month == 8:
        buy.append(("8月", +1))

    total = sum(w for _, w in buy) + sum(w for _, w in sell)
    all_sigs = buy + sell
    sig_names = [f"{n}({w:+d})" for n, w in all_sigs]

    # Veto
    veto = (ar > 1.0 and ae > 1.3) or (bearish_fvg and total <= -5)

    # 持仓期建议（基于信号衰减分析）
    hold_days = 1  # 默认 T+1
    if regime == "mean_reverting" and isinstance(out_streak, (int, float)) and out_streak <= -3:
        hold_days = 5  # MR+streak≤-3: T+5 还在涨
    elif regime == "mean_reverting" and isinstance(out_streak, (int, float)) and out_streak <= -2:
        hold_days = 3  # MR+streak≤-2: T+3 稳定
    elif pd.notna(macd_hist) and macd_hist.shift(1) if hasattr(macd_hist, 'shift') else False:
        hold_days = 5  # MACD死叉: T+5 最强
    elif total >= 5:
        hold_days = 3  # 高分信号: 持有稍长

    return total, veto, sig_names, hold_days


def compute_thresholds_from_sample(sample):
    e5 = sample["excess_5d"].dropna()
    e10 = sample["excess_10d"].dropna()
    return {
        "excess_5d_p15": e5.quantile(0.15) if len(e5) > 10 else -4.91,
        "excess_5d_p85": e5.quantile(0.85) if len(e5) > 10 else 5.74,
        "excess_10d_p15": e10.quantile(0.15) if len(e10) > 10 else -6.11,
        "excess_10d_p70": e10.quantile(0.70) if len(e10) > 10 else 3.0,
        "excess_10d_p85": e10.quantile(0.85) if len(e10) > 10 else 5.5,
    }


def cum_log(vals):
    s = 0.0
    for v in vals:
        if abs(v) < 100:
            s += math.log(1 + v / 100)
    return (math.exp(s) - 1) * 100


def max_drawdown_pct(returns_arr):
    if len(returns_arr) < 2:
        return 0.0
    cum = np.cumprod(1 + np.array(returns_arr) / 100)
    peak = np.maximum.accumulate(cum)
    dd = (cum - peak) / peak
    return round(float(dd.min()) * 100, 2)


def sharpe_ratio(returns_arr):
    arr = np.array(returns_arr)
    if len(arr) < 10 or arr.std() == 0:
        return 0.0
    return round(float(arr.mean() / arr.std() * np.sqrt(252)), 3)


# ── 主函数 ──────────────────────────────────────────────────────────────────

def main():
    df = load_and_prepare_data()

    print("\n" + "=" * 70)
    print("  V3.1 策略精炼回测")
    print("  (CUSUM 仅卖侧 + 看跌FVG veto + 信号衰减持仓期)")
    print("=" * 70)

    # Walk-Forward 回测
    train_window = 120
    results = []

    # V2 基线
    from composite_signal_backtest_v2 import (
        compute_composite_score, compute_thresholds_from_sample as v2_thresholds
    )

    v2_results = []
    for i in range(train_window, len(df)):
        train = df.iloc[max(0, i - train_window):i]
        thresholds = v2_thresholds(train)
        score, veto, signals = compute_composite_score(
            df.iloc[i], thresholds, use_v2=True, use_regime=True)
        exc = df.iloc[i].get("next_1d_excess_vs_chain", np.nan)
        v2_results.append({
            "date": df.iloc[i]["date_str"],
            "score": score, "veto": veto,
            "regime": df.iloc[i].get("regime", ""),
            "next_1d_exc": exc if pd.notna(exc) else None,
        })

    # V3.1
    v31_results = []
    for i in range(train_window, len(df)):
        train = df.iloc[max(0, i - train_window):i]
        thresholds = compute_thresholds_from_sample(train)
        score, veto, signals, hold_days = compute_v31_score(df.iloc[i], thresholds)
        exc = df.iloc[i].get("next_1d_excess_vs_chain", np.nan)
        next_3d = df.iloc[i].get("next_3d_return", np.nan)
        next_5d = df.iloc[i].get("next_5d_return", np.nan)
        v31_results.append({
            "date": df.iloc[i]["date_str"],
            "score": score, "veto": veto,
            "regime": df.iloc[i].get("regime", ""),
            "hold_days": hold_days,
            "next_1d_exc": exc if pd.notna(exc) else None,
            "next_3d_abs": float(next_3d * 100) if pd.notna(next_3d) else None,
            "next_5d_abs": float(next_5d * 100) if pd.notna(next_5d) else None,
        })

    # ── Regime 自适应阈值 ──
    print("\n  ── V2 vs V3.1 固定阈值对比 ──")

    for label, results in [("V2", v2_results), ("V3.1", v31_results)]:
        print(f"\n    {label}:")
        for threshold in [3, 4, 5]:
            long_exc = [r["next_1d_exc"] for r in results
                        if r["score"] >= threshold and not r["veto"]
                        and r["next_1d_exc"] is not None]
            if len(long_exc) >= 3:
                arr = np.array(long_exc)
                dd = max_drawdown_pct(long_exc)
                sh = sharpe_ratio(long_exc)
                print(f"      ±{threshold}: n={len(arr)}, wr={(arr>0).mean():.1%}, "
                      f"avg={arr.mean():+.3f}%, cum={cum_log(arr):+.1f}%, "
                      f"dd={dd:.1f}%, sharpe={sh:.2f}")

    # ── Regime 自适应阈值（核心推荐）──
    print("\n  ── V3.1 Regime 自适应阈值 ──")

    # MR: ±3, TR: ±4, TS: ±4（V2 保守参数）
    regime_thresholds = {
        "mean_reverting": 3,
        "trending": 4,
        "transition": 4,
    }

    adaptive_long = []
    adaptive_short = []
    for r in v31_results:
        thr = regime_thresholds.get(r["regime"], 4)
        if r["veto"]:
            adaptive_short.append(r)
        elif r["score"] >= thr and r["next_1d_exc"] is not None:
            adaptive_long.append(r)
        elif r["score"] <= -thr and r["next_1d_exc"] is not None:
            adaptive_short.append(r)

    if adaptive_long:
        long_exc = np.array([r["next_1d_exc"] for r in adaptive_long])
        dd = max_drawdown_pct(long_exc.tolist())
        sh = sharpe_ratio(long_exc.tolist())

        print(f"    做多: n={len(long_exc)}, wr={(long_exc>0).mean():.1%}, "
              f"avg={long_exc.mean():+.3f}%, cum={cum_log(long_exc):+.1f}%")
        print(f"          dd={dd:.1f}%, sharpe={sh:.2f}")

        # 按Regime分组
        for regime in ["mean_reverting", "trending", "transition"]:
            regime_days = [r for r in adaptive_long if r["regime"] == regime]
            if regime_days:
                r_exc = np.array([r["next_1d_exc"] for r in regime_days])
                print(f"      {regime}: n={len(r_exc)}, wr={(r_exc>0).mean():.1%}, "
                      f"avg={r_exc.mean():+.3f}%")

    if adaptive_short:
        short_vals = [r["next_1d_exc"] for r in adaptive_short if r["next_1d_exc"] is not None]
        if short_vals:
            short_exc = np.array(short_vals)
            neg_rate = (short_exc < 0).mean()
            print(f"    做空/回避: n={len(short_exc)}, 负超额率={neg_rate:.1%}")

    # ── 多持仓期分析 ──
    print("\n  ── V3.1 多持仓期分析（信号衰减）──")
    for label, results in [("V3.1自适应", adaptive_long)]:
        if not results:
            continue

        # T+1 超额
        exc_t1 = np.array([r["next_1d_exc"] for r in results if r["next_1d_exc"] is not None])

        # T+3 绝对收益
        abs_t3 = np.array([r["next_3d_abs"] for r in results if r.get("next_3d_abs") is not None])

        # T+5 绝对收益
        abs_t5 = np.array([r["next_5d_abs"] for r in results if r.get("next_5d_abs") is not None])

        print(f"    {label}:")
        if len(exc_t1) > 0:
            print(f"      T+1超额: n={len(exc_t1)}, wr={(exc_t1>0).mean():.1%}, avg={exc_t1.mean():+.3f}%")
        if len(abs_t3) > 0:
            print(f"      T+3绝对: n={len(abs_t3)}, wr={(abs_t3>0).mean():.1%}, avg={abs_t3.mean():+.3f}%")
        if len(abs_t5) > 0:
            print(f"      T+5绝对: n={len(abs_t5)}, wr={(abs_t5>0).mean():.1%}, avg={abs_t5.mean():+.3f}%")

    # ── CUSUM 卖出信号效果 ──
    print("\n  ── CUSUM 卖出信号效果 ──")
    cusum_up_days = [r for r in v31_results
                     if r.get("next_1d_exc") is not None
                     and "CUSUM上行" in str(r.get("signals", ""))]
    if cusum_up_days:
        arr = np.array([r["next_1d_exc"] for r in cusum_up_days])
        print(f"    CUSUM上行信号日: n={len(arr)}, avg={arr.mean():+.3f}%, wr={(arr>0).mean():.1%}")

    cusum_up_streak = [r for r in v31_results
                       if r.get("next_1d_exc") is not None
                       and "CUSUM_UP+streak≥+2" in str(r.get("signals", ""))]
    if cusum_up_streak:
        arr = np.array([r["next_1d_exc"] for r in cusum_up_streak])
        print(f"    CUSUM_UP+streak≥+2: n={len(arr)}, avg={arr.mean():+.3f}%, wr={(arr>0).mean():.1%}")

    # ── 极端日 ──
    print("\n  ── V3.1 评分极端日 ──")
    sorted_v31 = sorted(v31_results, key=lambda x: x["score"], reverse=True)

    print("  评分最高 5 天:")
    for r in sorted_v31[:5]:
        exc = r["next_1d_exc"]
        hit = "✓" if exc is not None and exc > 0 else "✗"
        print(f"    {hit} {r['date']}: score={r['score']}, regime={r['regime']}, "
              f"T+1={exc:+.3f}%, T+3={r.get('next_3d_abs', 0):+.3f}%, "
              f"T+5={r.get('next_5d_abs', 0):+.3f}%")

    print("  评分最低 5 天:")
    for r in sorted_v31[-5:]:
        exc = r["next_1d_exc"]
        hit = "✓" if exc is not None and exc < 0 else "✗"
        print(f"    {hit} {r['date']}: score={r['score']}, regime={r['regime']}, "
              f"T+1={exc:+.3f}%")

    # ── V2保守 vs V3.1自适应 最终对比 ──
    print("\n" + "=" * 70)
    print("  最终策略对比：V2保守 vs V3.1自适应")
    print("=" * 70)

    # V2 保守（同样使用 Regime 自适应阈值）
    v2_adaptive_long = []
    for r in v2_results:
        thr = regime_thresholds.get(r["regime"], 4)
        if not r["veto"] and r["score"] >= thr and r["next_1d_exc"] is not None:
            v2_adaptive_long.append(r)

    for label, data in [("V2保守", v2_adaptive_long), ("V3.1自适应", adaptive_long)]:
        if data:
            arr = np.array([r["next_1d_exc"] for r in data])
            dd = max_drawdown_pct(arr.tolist())
            sh = sharpe_ratio(arr.tolist())
            print(f"\n  {label}:")
            print(f"    n={len(arr)}, wr={(arr>0).mean():.1%}, avg={arr.mean():+.3f}%, "
                  f"cum={cum_log(arr):+.1f}%")
            print(f"    dd={dd:.1f}%, sharpe={sh:.2f}")

    # ── 输出 ──
    output = {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "v31_adaptive": {
            "long_n": len(adaptive_long),
            "long_wr": round(float((np.array([r["next_1d_exc"] for r in adaptive_long]) > 0).mean()), 4),
            "long_avg": round(float(np.mean([r["next_1d_exc"] for r in adaptive_long])), 4),
            "long_cum": round(float(cum_log(np.array([r["next_1d_exc"] for r in adaptive_long]))), 2),
        },
        "daily_results": v31_results,
    }

    out_path = DATA_DIR / "composite_signal_backtest_v31.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n[OK] 输出: {out_path}")


if __name__ == "__main__":
    main()
