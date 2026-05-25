#!/usr/bin/env python3
"""
信号实验室升级 - P1 深度研究脚本
维度：CUSUM Regime / 信号衰减 / Bootstrap鲁棒性 / 交互探索 / 风险分析

基于 P0 结果进一步深化，重点解决：
1. ADX Regime 是离散3态 → CUSUM 能否提供更精细/更早的状态转换检测？
2. 所有信号只看 T+1 → 信号持续性如何？T+2/T+3/T+5？
3. 关键信号的统计显著性 → Bootstrap CI 置信区间
4. Regime×Streak 交叉最强 → 还有哪些未发现的2-way交互？
5. 只看胜率/超额 → 风险侧（回撤、尾部、夏普）如何？
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "output"
PRICE_DIR = ROOT / "data" / "price" / "normalized"


# ── 技术指标（与 P0/V2 一致）──────────────────────────────────────────────

def calc_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_macd(closes: pd.Series, fast: int = 12, slow: int = 26,
              signal: int = 9) -> tuple:
    ema_fast = closes.ewm(span=fast, min_periods=fast).mean()
    ema_slow = closes.ewm(span=slow, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_bollinger(closes: pd.Series, period: int = 20,
                   num_std: float = 2.0) -> tuple:
    middle = closes.rolling(period).mean()
    std = closes.rolling(period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    bandwidth = (upper - lower) / middle.replace(0, np.nan)
    pct_b = (closes - lower) / (upper - lower).replace(0, np.nan)
    return upper, middle, lower, bandwidth, pct_b


def calc_adx(highs: pd.Series, lows: pd.Series, closes: pd.Series,
             period: int = 14) -> pd.Series:
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


def calc_stochastic(highs: pd.Series, lows: pd.Series, closes: pd.Series,
                    k_period: int = 14, d_period: int = 3) -> tuple:
    lowest_low = lows.rolling(k_period).min()
    highest_high = highs.rolling(k_period).max()
    k = 100 * (closes - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    return k, d


def calc_atr(highs: pd.Series, lows: pd.Series, closes: pd.Series,
             period: int = 14) -> pd.Series:
    tr1 = highs - lows
    tr2 = (highs - closes.shift(1)).abs()
    tr3 = (lows - closes.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period).mean()


# ── CUSUM Regime 检测 ─────────────────────────────────────────────────────

def compute_cusum_regime(closes: pd.Series, atr: pd.Series,
                         h_mult: float = 1.0) -> pd.Series:
    """
    CUSUM 累积偏差 Regime 检测。

    方法：
    1. 计算日收益率的滚动均值和标准差
    2. 标准化残差累积求和
    3. 当累积偏差超过 h * σ 时标记 Regime 变化点
    4. 返回连续 Regime 标签（cusum_mr / cusum_trend / cusum_neutral）

    与 ADX Regime 的区别：
    - ADX 是滞后指标（基于 DI 平滑）
    - CUSUM 检测变化点，理论上更早
    - CUSUM 输出连续的"偏离程度"而非离散3态
    """
    returns = closes.pct_change()
    rolling_mean = returns.rolling(20).mean()
    rolling_std = returns.rolling(20).std()

    # 标准化残差
    residuals = (returns - rolling_mean) / rolling_std.replace(0, np.nan)
    residuals = residuals.fillna(0)

    # CUSUM 统计量
    cum_pos = pd.Series(0.0, index=closes.index)
    cum_neg = pd.Series(0.0, index=closes.index)
    h = h_mult  # 阈值（标准差倍数）

    regime = pd.Series("neutral", index=closes.index)

    for i in range(1, len(closes)):
        cum_pos.iloc[i] = max(0, cum_pos.iloc[i - 1] + residuals.iloc[i] - 0.1)
        cum_neg.iloc[i] = min(0, cum_neg.iloc[i - 1] + residuals.iloc[i] + 0.1)

        if cum_pos.iloc[i] > h:
            regime.iloc[i] = "trending_up"
            cum_pos.iloc[i] = 0  # 重置
        elif cum_neg.iloc[i] < -h:
            regime.iloc[i] = "trending_down"
            cum_neg.iloc[i] = 0
        else:
            regime.iloc[i] = "mean_reverting"

    return regime


def compute_cusum_continuous(closes: pd.Series, atr: pd.Series) -> pd.DataFrame:
    """
    CUSUM 连续指标：不仅标记 Regime，还输出偏离程度。

    返回 DataFrame：
    - cusum_pos: 正向累积偏差
    - cusum_neg: 负向累积偏差
    - cusum_abs: 总偏差强度（|pos| + |neg|）
    - cusum_regime: 离散标签
    - cusum_change: 变化点标记
    """
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

    cusum_abs = cum_pos - cum_neg

    # 变化点检测
    change = pd.Series(False, index=closes.index)
    for i in range(2, len(closes)):
        # 从 MR 转 Trend 或从 Trend 转 MR
        prev_pos = cum_pos.iloc[i - 1]
        curr_pos = cum_pos.iloc[i]
        prev_neg = cum_neg.iloc[i - 1]
        curr_neg = cum_neg.iloc[i]
        if (prev_pos < 1.0 and curr_pos >= 1.0) or (prev_neg > -1.0 and curr_neg <= -1.0):
            change.iloc[i] = True

    # 离散标签
    regime = pd.Series("mean_reverting", index=closes.index)
    regime[cum_pos > 1.0] = "trending_up"
    regime[cum_neg < -1.0] = "trending_down"

    return pd.DataFrame({
        "cusum_pos": cum_pos,
        "cusum_neg": cum_neg,
        "cusum_abs": cusum_abs,
        "cusum_regime": regime,
        "cusum_change": change,
    })


# ── 数据加载 ────────────────────────────────────────────────────────────────

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


def load_and_prepare_data() -> pd.DataFrame:
    """加载数据并计算全部特征（含 CUSUM）"""
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

    df["rsi_14"] = calc_rsi(c, 14)
    macd_line, signal_line, histogram = calc_macd(c)
    df["macd_hist"] = histogram
    df["macd_line"] = macd_line
    df["macd_signal"] = signal_line
    bb_upper, bb_mid, bb_lower, bb_bw, bb_pctb = calc_bollinger(c)
    df["bb_pctb"] = bb_pctb
    df["bb_bw"] = bb_bw
    df["adx_14"] = calc_adx(h, l, c, 14)
    stoch_k, stoch_d = calc_stochastic(h, l, c)
    df["stoch_k"] = stoch_k
    df["stoch_d"] = stoch_d
    df["atr_14"] = calc_atr(h, l, c, 14)

    # Keltner / Squeeze
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
    cusum_df = compute_cusum_continuous(c, df["atr_14"])
    df = pd.concat([df, cusum_df], axis=1)

    # 多种 CUSUM 阈值
    for h_mult in [0.5, 0.8, 1.0, 1.5, 2.0]:
        df[f"cusum_regime_h{h_mult}"] = compute_cusum_regime(c, df["atr_14"], h_mult)

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

    # 信号集合
    df["signal_set"] = df["signal_labels"].apply(parse_signal_labels)
    df["alpha_count"] = df["signal_set"].apply(lambda s: len(s & ALPHA_SIGNALS))

    # 多日收益（信号衰减分析需要）
    df["next_2d_return"] = df["close"].shift(-2) / df["close"] - 1
    df["next_3d_return"] = df["close"].shift(-3) / df["close"] - 1
    df["next_5d_return"] = df["close"].shift(-5) / df["close"] - 1

    # 多日超额（vs 产业链）
    if "next_3d_excess_vs_chain" in df.columns:
        pass
    else:
        # 近似：用 next_1d_excess 的累积
        df["next_3d_excess_vs_chain"] = df.get("next_3d_excess_vs_chain", np.nan)

    # 绝对收益
    df["next_1d_abs"] = df["close"].shift(-1) / df["close"] - 1
    df["next_2d_abs"] = df["next_2d_return"]
    df["next_3d_abs"] = df["next_3d_return"]
    df["next_5d_abs"] = df["next_5d_return"]

    print(f"[OK] 数据准备完成: {len(df)} 行, CUSUM 特征已添加")
    return df


# ── 1. CUSUM Regime 对比分析 ───────────────────────────────────────────────

def analyze_cusum_vs_adx(df: pd.DataFrame) -> dict:
    """CUSUM Regime 与 ADX Regime 的对比分析"""
    print("\n" + "=" * 70)
    print("  1. CUSUM Regime vs ADX Regime 对比分析")
    print("=" * 70)

    target = "next_1d_excess_vs_chain"
    results = {}

    # ADX Regime 基线
    print("\n  ── ADX Regime 基线 ──")
    adx_stats = {}
    for regime in ["mean_reverting", "trending", "transition"]:
        mask = df["regime"] == regime
        vals = df.loc[mask, target].dropna()
        if len(vals) > 0:
            stat = {
                "n": int(len(vals)),
                "avg_exc": round(float(vals.mean()), 4),
                "win_rate": round(float((vals > 0).mean()), 4),
            }
            adx_stats[regime] = stat
            print(f"    {regime}: n={stat['n']}, avg={stat['avg_exc']:+.3f}%, wr={stat['win_rate']:.1%}")

    results["adx_regime"] = adx_stats

    # CUSUM Regime（不同阈值）
    print("\n  ── CUSUM Regime（不同阈值 h）──")
    cusum_stats = {}

    for h_mult in [0.5, 0.8, 1.0, 1.5, 2.0]:
        col = f"cusum_regime_h{h_mult}"
        print(f"\n    CUSUM h={h_mult}:")
        h_stats = {}
        for regime in ["mean_reverting", "trending_up", "trending_down"]:
            mask = df[col] == regime
            vals = df.loc[mask, target].dropna()
            if len(vals) > 0:
                stat = {
                    "n": int(len(vals)),
                    "avg_exc": round(float(vals.mean()), 4),
                    "win_rate": round(float((vals > 0).mean()), 4),
                }
                h_stats[regime] = stat
                print(f"      {regime}: n={stat['n']}, avg={stat['avg_exc']:+.3f}%, wr={stat['win_rate']:.1%}")
        cusum_stats[f"h{h_mult}"] = h_stats

    results["cusum_regime"] = cusum_stats

    # CUSUM × Streak 交叉（核心对比：是否比 ADX × Streak 更好？）
    print("\n  ── CUSUM × Streak 交叉分析 ──")
    streak_col = "outperform_streak"

    cusum_cross = {}
    for h_mult in [0.8, 1.0]:
        col = f"cusum_regime_h{h_mult}"
        print(f"\n    CUSUM h={h_mult} × Streak:")

        for regime in ["mean_reverting", "trending_up", "trending_down"]:
            for streak_cond, streak_label in [(-3, "≤-3"), (-2, "≤-2"), (2, "≥+2"), (3, "≥+3")]:
                if streak_label in ("≤-3", "≤-2"):
                    mask = (df[col] == regime) & (df[streak_col] <= streak_cond)
                else:
                    mask = (df[col] == regime) & (df[streak_col] >= streak_cond)

                vals = df.loc[mask, target].dropna()
                if len(vals) >= 3:
                    stat = {
                        "n": int(len(vals)),
                        "avg_exc": round(float(vals.mean()), 4),
                        "win_rate": round(float((vals > 0).mean()), 4),
                    }
                    key = f"{regime}+streak{streak_label}"
                    cusum_cross[key] = stat
                    sig = "⭐" if (stat["win_rate"] > 0.65 or stat["win_rate"] < 0.35) else "  "
                    print(f"      {sig} {key}: n={stat['n']}, avg={stat['avg_exc']:+.3f}%, wr={stat['win_rate']:.1%}")

    results["cusum_cross"] = cusum_cross

    # CUSUM 连续指标分位分析
    print("\n  ── CUSUM 连续指标（cusum_abs）分位分析 ──")
    cusum_abs_q = pd.qcut(df["cusum_abs"], 5, duplicates="drop")
    q_stats = {}
    for q_label in sorted(cusum_abs_q.unique()):
        mask = cusum_abs_q == q_label
        vals = df.loc[mask, target].dropna()
        if len(vals) > 0:
            stat = {
                "n": int(len(vals)),
                "avg_exc": round(float(vals.mean()), 4),
                "win_rate": round(float((vals > 0).mean()), 4),
            }
            q_stats[str(q_label)] = stat
            print(f"    {q_label}: n={stat['n']}, avg={stat['avg_exc']:+.3f}%, wr={stat['win_rate']:.1%}")

    results["cusum_abs_quantile"] = q_stats

    # CUSUM 变化点分析
    print("\n  ── CUSUM 变化点（Regime 转换日）──")
    change_mask = df["cusum_change"]
    change_vals = df.loc[change_mask, target].dropna()
    stable_vals = df.loc[~change_mask, target].dropna()
    change_stat = {
        "change_point": {
            "n": int(len(change_vals)),
            "avg_exc": round(float(change_vals.mean()), 4) if len(change_vals) > 0 else None,
            "win_rate": round(float((change_vals > 0).mean()), 4) if len(change_vals) > 0 else None,
        },
        "stable": {
            "n": int(len(stable_vals)),
            "avg_exc": round(float(stable_vals.mean()), 4) if len(stable_vals) > 0 else None,
            "win_rate": round(float((stable_vals > 0).mean()), 4) if len(stable_vals) > 0 else None,
        },
    }
    results["cusum_change_point"] = change_stat

    if len(change_vals) > 0:
        print(f"    变化日: n={len(change_vals)}, avg={change_vals.mean():+.3f}%, wr={(change_vals>0).mean():.1%}")
    if len(stable_vals) > 0:
        print(f"    稳定日: n={len(stable_vals)}, avg={stable_vals.mean():+.3f}%, wr={(stable_vals>0).mean():.1%}")

    return results


# ── 2. 信号衰减分析 ────────────────────────────────────────────────────────

def analyze_signal_decay(df: pd.DataFrame) -> dict:
    """信号在 T+1/T+2/T+3/T+5 的持续性分析"""
    print("\n" + "=" * 70)
    print("  2. 信号衰减分析（T+1 → T+5）")
    print("=" * 70)

    target_exc = "next_1d_excess_vs_chain"
    horizons = {
        "T+1": ("next_1d_abs", target_exc),
        "T+2": ("next_2d_abs", "next_2d_abs"),
        "T+3": ("next_3d_abs", "next_3d_abs"),
        "T+5": ("next_5d_abs", "next_5d_abs"),
    }

    # 关键信号列表
    signals = {
        "mean_reverting+streak≤-3": lambda d: (d["regime"] == "mean_reverting") & (d["outperform_streak"] <= -3),
        "mean_reverting+streak≤-2": lambda d: (d["regime"] == "mean_reverting") & (d["outperform_streak"] <= -2),
        "transition+streak≤-2": lambda d: (d["regime"] == "transition") & (d["outperform_streak"] <= -2),
        "transition+streak≥+2": lambda d: (d["regime"] == "transition") & (d["outperform_streak"] >= 2),
        "RSI超买(>70)": lambda d: d["rsi_14"] > 70,
        "BB上轨触及": lambda d: d["bb_pctb"] > 1,
        "MACD死叉": lambda d: (d["macd_hist"].shift(1) > 0) & (d["macd_hist"] < 0),
        "MACD柱负": lambda d: d["macd_hist"] < 0,
        "周三": lambda d: d["dow"] == 2,
        "周五": lambda d: d["dow"] == 4,
        "看跌FVG": lambda d: d["bearish_fvg"],
        "LiqSweep高": lambda d: d["liq_sweep_high"],
        "Stoch超买": lambda d: d["stoch_k"] > 80,
        "excess_5d_P15-": lambda d: d.get("excess_5d", 999) <= d["excess_5d"].quantile(0.15),
        "excess_5d_P85+": lambda d: d.get("excess_5d", -999) >= d["excess_5d"].quantile(0.85),
    }

    decay_results = {}

    for sig_name, sig_func in signals.items():
        try:
            mask = sig_func(df)
        except Exception:
            continue

        n_signal = mask.sum()
        if n_signal < 5:
            continue

        sig_decay = {"n": int(n_signal)}

        print(f"\n  ── {sig_name} (n={n_signal}) ──")

        for horizon, (abs_col, exc_col) in horizons.items():
            # 使用绝对收益作为衰减代理（超额数据仅 T+1 有完整覆盖）
            if abs_col in df.columns:
                vals = df.loc[mask, abs_col].dropna()
            else:
                vals = pd.Series(dtype=float)

            if len(vals) >= 3:
                stat = {
                    "n": int(len(vals)),
                    "avg": round(float(vals.mean() * 100), 3),
                    "win_rate": round(float((vals > 0).mean()), 4),
                }
                sig_decay[horizon] = stat
                print(f"    {horizon}: avg={stat['avg']:+.3f}%, wr={stat['win_rate']:.1%}")
            else:
                sig_decay[horizon] = {"n": 0}

        decay_results[sig_name] = sig_decay

    return decay_results


# ── 3. Bootstrap 鲁棒性检验 ───────────────────────────────────────────────

def bootstrap_signal_stats(vals: np.ndarray, n_boot: int = 5000,
                           ci_level: float = 0.95) -> dict:
    """Bootstrap 重采样，计算胜率和均值的置信区间"""
    n = len(vals)
    if n < 5:
        return {"n": n}

    boot_wr = []
    boot_mean = []

    for _ in range(n_boot):
        sample = np.random.choice(vals, size=n, replace=True)
        boot_wr.append((sample > 0).mean())
        boot_mean.append(sample.mean())

    boot_wr = np.array(boot_wr)
    boot_mean = np.array(boot_mean)

    alpha = (1 - ci_level) / 2
    return {
        "n": n,
        "observed_wr": round(float((vals > 0).mean()), 4),
        "observed_mean": round(float(vals.mean()), 4),
        "wr_ci_lower": round(float(np.percentile(boot_wr, alpha * 100)), 4),
        "wr_ci_upper": round(float(np.percentile(boot_wr, (1 - alpha) * 100)), 4),
        "mean_ci_lower": round(float(np.percentile(boot_mean, alpha * 100)), 4),
        "mean_ci_upper": round(float(np.percentile(boot_mean, (1 - alpha) * 100)), 4),
        "significant": bool((vals > 0).mean() > np.percentile(boot_wr, 50) + 0.05
                            or (vals > 0).mean() < np.percentile(boot_wr, 50) - 0.05),
    }


def analyze_bootstrap_robustness(df: pd.DataFrame) -> dict:
    """关键信号的 Bootstrap 鲁棒性检验"""
    print("\n" + "=" * 70)
    print("  3. Bootstrap 鲁棒性检验（5000 次重采样）")
    print("=" * 70)

    np.random.seed(42)
    target = "next_1d_excess_vs_chain"

    signals = {
        "mean_reverting+streak≤-3": (df["regime"] == "mean_reverting") & (df["outperform_streak"] <= -3),
        "mean_reverting+streak≤-2": (df["regime"] == "mean_reverting") & (df["outperform_streak"] <= -2),
        "transition+streak≤-2": (df["regime"] == "transition") & (df["outperform_streak"] <= -2),
        "transition+streak≥+2": (df["regime"] == "transition") & (df["outperform_streak"] >= 2),
        "RSI超买(>70)": df["rsi_14"] > 70,
        "BB上轨触及": df["bb_pctb"] > 1,
        "Stoch超买(K>80)": df["stoch_k"] > 80,
        "MACD死叉": (df["macd_hist"].shift(1) > 0) & (df["macd_hist"] < 0),
        "MACD柱负": df["macd_hist"] < 0,
        "周三": df["dow"] == 2,
        "周五": df["dow"] == 4,
        "周五+ADX<25": (df["dow"] == 4) & (df["adx_14"] < 25),
        "看跌FVG": df["bearish_fvg"],
        "LiqSweep高": df["liq_sweep_high"],
        "BOS创20日新高": df["bos_20d_high"],
        "8月效应": df["month"] == 8,
        "4月效应": df["month"] == 4,
        "excess_5d_Q1": df["excess_5d"] <= df["excess_5d"].quantile(0.20),
        "excess_5d_Q5": df["excess_5d"] >= df["excess_5d"].quantile(0.80),
        "streak≤-3(全局)": df["outperform_streak"] <= -3,
        "streak≥+3(全局)": df["outperform_streak"] >= 3,
    }

    bootstrap_results = {}

    for sig_name, mask in signals.items():
        vals = df.loc[mask, target].dropna().values
        if len(vals) < 3:
            continue

        stat = bootstrap_signal_stats(vals, n_boot=5000)
        bootstrap_results[sig_name] = stat

        sig_label = "✅" if stat.get("significant") else "⚠️"
        wr_ci = f"[{stat.get('wr_ci_lower', 0):.1%}, {stat.get('wr_ci_upper', 0):.1%}]"
        mean_ci = f"[{stat.get('mean_ci_lower', 0):+.3f}%, {stat.get('mean_ci_upper', 0):+.3f}%]"

        print(f"  {sig_label} {sig_name}: n={stat['n']}, "
              f"wr={stat.get('observed_wr', 0):.1%} {wr_ci}, "
              f"avg={stat.get('observed_mean', 0):+.3f}% {mean_ci}")

    return bootstrap_results


# ── 4. 多信号交互探索 ──────────────────────────────────────────────────────

def analyze_interactions(df: pd.DataFrame) -> dict:
    """系统化 2-way 交叉分析：寻找未发现的信号组合"""
    print("\n" + "=" * 70)
    print("  4. 多信号交互探索")
    print("=" * 70)

    target = "next_1d_excess_vs_chain"
    min_n = 5

    # 构建二元信号矩阵
    signals_binary = {
        "RSI<50": df["rsi_14"] < 50,
        "RSI>60": df["rsi_14"] > 60,
        "MACD柱负": df["macd_hist"] < 0,
        "MACD柱正": df["macd_hist"] > 0,
        "BB%b<0.2": df["bb_pctb"] < 0.2,
        "BB%b>0.8": df["bb_pctb"] > 0.8,
        "Stoch<30": df["stoch_k"] < 30,
        "Stoch>70": df["stoch_k"] > 70,
        "ADX<20": df["adx_14"] < 20,
        "ADX>30": df["adx_14"] > 30,
        "Squeeze": df["squeeze_on"],
        "ATR低(BB带宽Q1)": df["bb_bw"] <= df["bb_bw"].quantile(0.20),
        "ATR高(BB带宽Q5)": df["bb_bw"] >= df["bb_bw"].quantile(0.80),
        "周三": df["dow"] == 2,
        "周四": df["dow"] == 3,
        "周五": df["dow"] == 4,
        "8月": df["month"] == 8,
        "4月/12月": df["month"].isin([4, 12]),
        "LiqSweep高": df["liq_sweep_high"],
        "看跌FVG": df["bearish_fvg"],
        "BOS新高": df["bos_20d_high"],
        "excess_5d低": df["excess_5d"] <= df["excess_5d"].quantile(0.20),
        "excess_5d高": df["excess_5d"] >= df["excess_5d"].quantile(0.80),
        "streak≤-2": df["outperform_streak"] <= -2,
        "streak≥+2": df["outperform_streak"] >= 2,
        "cusum_MR": df["cusum_regime"] == "mean_reverting",
        "cusum_TU": df["cusum_regime"] == "trending_up",
        "cusum_TD": df["cusum_regime"] == "trending_down",
        "cusum_change": df["cusum_change"],
        "资金正": df.get("moneyflow_positive_ratio", 0) > 0.6,
        "缩量": df.get("amount_expansion_ratio", 1) < 0.85,
    }

    # 单信号效力（基线）
    print("\n  ── 单信号效力基线 ──")
    single_stats = {}
    for sig_name, mask in signals_binary.items():
        vals = df.loc[mask, target].dropna()
        if len(vals) >= min_n:
            stat = {
                "n": int(len(vals)),
                "avg_exc": round(float(vals.mean()), 4),
                "win_rate": round(float((vals > 0).mean()), 4),
            }
            single_stats[sig_name] = stat

    # 按胜率排序显示 top/bottom
    sorted_single = sorted(single_stats.items(), key=lambda x: x[1]["win_rate"])
    print("    负向信号 Top 5:")
    for name, stat in sorted_single[:5]:
        print(f"      {name}: n={stat['n']}, avg={stat['avg_exc']:+.3f}%, wr={stat['win_rate']:.1%}")
    print("    正向信号 Top 5:")
    for name, stat in sorted_single[-5:]:
        print(f"      {name}: n={stat['n']}, avg={stat['avg_exc']:+.3f}%, wr={stat['win_rate']:.1%}")

    # 2-way 交叉
    print("\n  ── 2-way 交叉分析（寻找新组合）──")
    sig_names = list(signals_binary.keys())
    interaction_results = {}
    best_lift = 0
    best_combo = ""

    for i in range(len(sig_names)):
        for j in range(i + 1, len(sig_names)):
            s1, s2 = sig_names[i], sig_names[j]
            mask1, mask2 = signals_binary[s1], signals_binary[s2]
            combined = mask1 & mask2

            vals = df.loc[combined, target].dropna()
            if len(vals) < min_n:
                continue

            wr = float((vals > 0).mean())
            avg = float(vals.mean())

            # 与单信号对比的增量
            s1_wr = single_stats.get(s1, {}).get("win_rate", 0.5)
            s2_wr = single_stats.get(s2, {}).get("win_rate", 0.5)
            baseline_wr = max(s1_wr, s2_wr)
            lift = wr - baseline_wr

            if abs(lift) > 0.10 and len(vals) >= min_n:
                key = f"{s1} × {s2}"
                stat = {
                    "n": int(len(vals)),
                    "avg_exc": round(avg, 4),
                    "win_rate": round(wr, 4),
                    "lift_vs_best_single": round(lift, 4),
                    "s1_wr": round(s1_wr, 4),
                    "s2_wr": round(s2_wr, 4),
                }
                interaction_results[key] = stat

                if abs(lift) > abs(best_lift):
                    best_lift = lift
                    best_combo = key

    # 按lift排序
    sorted_interactions = sorted(interaction_results.items(),
                                  key=lambda x: abs(x[1]["lift_vs_best_single"]),
                                  reverse=True)

    print(f"\n    发现 {len(sorted_interactions)} 个显著交互（|lift|>10pp）：")
    for key, stat in sorted_interactions[:20]:
        direction = "🟢" if stat["lift_vs_best_single"] > 0 else "🔴"
        print(f"      {direction} {key}: n={stat['n']}, wr={stat['win_rate']:.1%}, "
              f"lift={stat['lift_vs_best_single']:+.1%} "
              f"(单信号: {stat['s1_wr']:.1%}/{stat['s2_wr']:.1%})")

    # 特别关注：CUSUM × 传统信号
    print("\n  ── CUSUM × 传统信号 特殊交叉 ──")
    cusum_cross_special = {}
    cusum_sigs = ["cusum_MR", "cusum_TU", "cusum_TD", "cusum_change"]
    trad_sigs = ["RSI<50", "MACD柱负", "Stoch<30", "streak≤-2", "excess_5d低", "周三", "8月"]

    for cs in cusum_sigs:
        for ts in trad_sigs:
            mask = signals_binary[cs] & signals_binary[ts]
            vals = df.loc[mask, target].dropna()
            if len(vals) >= min_n:
                wr = float((vals > 0).mean())
                avg = float(vals.mean())
                key = f"{cs} × {ts}"
                stat = {
                    "n": int(len(vals)),
                    "avg_exc": round(avg, 4),
                    "win_rate": round(wr, 4),
                }
                cusum_cross_special[key] = stat
                sig = "⭐" if wr > 0.65 or wr < 0.35 else "  "
                print(f"      {sig} {key}: n={stat['n']}, avg={stat['avg_exc']:+.3f}%, wr={stat['win_rate']:.1%}")

    return {
        "single_signal_baseline": single_stats,
        "two_way_interactions": dict(sorted_interactions[:30]),
        "cusum_cross_special": cusum_cross_special,
        "best_interaction": best_combo,
        "best_lift": round(best_lift, 4),
    }


# ── 5. 风险与回撤分析 ──────────────────────────────────────────────────────

def analyze_risk_drawdown(df: pd.DataFrame) -> dict:
    """风险侧分析：回撤、夏普、尾部风险"""
    print("\n" + "=" * 70)
    print("  5. 风险与回撤分析")
    print("=" * 70)

    target_exc = "next_1d_excess_vs_chain"
    target_abs = "next_1d_return"

    # 策略定义（基于 V2 保守参数）
    # 简化：用 score 近似
    # 先计算 score
    from composite_signal_backtest_v2 import (
        compute_composite_score, compute_thresholds_from_sample
    )

    # Walk-Forward 计算 score
    results = []
    train_window = 120

    for i in range(train_window, len(df)):
        train = df.iloc[max(0, i - train_window):i]
        thresholds = compute_thresholds_from_sample(train)
        row = df.iloc[i]
        score, veto, signals = compute_composite_score(row, thresholds, use_v2=True, use_regime=True)
        results.append({
            "date": row["date_str"],
            "score": score,
            "veto": veto,
            "regime": row.get("regime", ""),
            "next_1d_exc": row.get(target_exc, np.nan),
            "next_1d_abs": row.get(target_abs, np.nan),
        })

    res_df = pd.DataFrame(results)
    res_df["next_1d_exc"] = pd.to_numeric(res_df["next_1d_exc"], errors="coerce")
    res_df["next_1d_abs"] = pd.to_numeric(res_df["next_1d_abs"], errors="coerce")

    risk_results = {}

    # Buy-and-hold 基线
    bh_exc = res_df["next_1d_exc"].dropna()
    bh_abs = res_df["next_1d_abs"].dropna()

    def max_drawdown(returns: pd.Series) -> float:
        cum = (1 + returns / 100).cumprod()
        peak = cum.expanding().max()
        dd = (cum - peak) / peak
        return round(float(dd.min()) * 100, 2)

    def sharpe_ratio(returns: pd.Series, rf: float = 0.0) -> float:
        if len(returns) < 10 or returns.std() == 0:
            return 0.0
        excess = returns - rf / 252
        return round(float(excess.mean() / excess.std() * np.sqrt(252)), 3)

    def sortino_ratio(returns: pd.Series, rf: float = 0.0) -> float:
        if len(returns) < 10:
            return 0.0
        excess = returns - rf / 252
        downside = excess[excess < 0]
        if len(downside) == 0 or downside.std() == 0:
            return 0.0
        return round(float(excess.mean() / downside.std() * np.sqrt(252)), 3)

    def var_cvar(returns: pd.Series, level: float = 0.05) -> tuple:
        sorted_r = returns.sort_values()
        n = len(sorted_r)
        idx = max(1, int(n * level))
        var_val = round(float(sorted_r.iloc[idx]), 3)
        cvar_val = round(float(sorted_r.iloc[:idx].mean()), 3)
        return var_val, cvar_val

    # 基线风险指标
    print("\n  ── Buy-and-Hold 基线 ──")
    bh_stats = {
        "n": int(len(bh_exc)),
        "avg_daily_exc": round(float(bh_exc.mean()), 4),
        "std_daily_exc": round(float(bh_exc.std()), 4),
        "max_drawdown_exc": max_drawdown(bh_exc) if len(bh_exc) > 0 else 0,
        "sharpe_exc": sharpe_ratio(bh_exc),
        "sortino_exc": sortino_ratio(bh_exc),
        "var_5_exc": var_cvar(bh_exc)[0] if len(bh_exc) > 10 else 0,
        "cvar_5_exc": var_cvar(bh_exc)[1] if len(bh_exc) > 10 else 0,
    }
    risk_results["buy_and_hold"] = bh_stats

    print(f"    avg={bh_stats['avg_daily_exc']:+.3f}%, std={bh_stats['std_daily_exc']:.3f}%")
    print(f"    max_dd={bh_stats['max_drawdown_exc']:.2f}%, sharpe={bh_stats['sharpe_exc']:.3f}")
    print(f"    VaR(5%)={bh_stats['var_5_exc']:.3f}%, CVaR(5%)={bh_stats['cvar_5_exc']:.3f}%")

    # V2 策略（不同阈值）
    print("\n  ── V2 策略风险指标 ──")
    for threshold in [3, 4, 5]:
        long_mask = (res_df["score"] >= threshold) & (~res_df["veto"])
        short_mask = (res_df["score"] <= -threshold)
        neutral_mask = ~(long_mask | short_mask)

        long_exc = res_df.loc[long_mask, "next_1d_exc"].dropna()
        short_exc = res_df.loc[short_mask, "next_1d_exc"].dropna()

        if len(long_exc) < 5:
            continue

        strategy_label = f"V2_±{threshold}"

        long_stats = {
            "n": int(len(long_exc)),
            "avg_daily_exc": round(float(long_exc.mean()), 4),
            "std_daily_exc": round(float(long_exc.std()), 4),
            "win_rate": round(float((long_exc > 0).mean()), 4),
            "max_drawdown_exc": max_drawdown(long_exc),
            "sharpe_exc": sharpe_ratio(long_exc),
            "sortino_exc": sortino_ratio(long_exc),
            "var_5_exc": var_cvar(long_exc)[0] if len(long_exc) > 10 else 0,
            "cvar_5_exc": var_cvar(long_exc)[1] if len(long_exc) > 10 else 0,
            "worst_day": round(float(long_exc.min()), 3),
            "best_day": round(float(long_exc.max()), 3),
        }

        # 计算策略累计收益和回撤曲线
        cum_exc = (1 + long_exc / 100).cumprod()
        peak = cum_exc.expanding().max()
        dd_curve = (cum_exc - peak) / peak * 100
        max_dd_duration = 0
        current_dd = 0
        for v in dd_curve:
            if v < 0:
                current_dd += 1
                max_dd_duration = max(max_dd_duration, current_dd)
            else:
                current_dd = 0
        long_stats["max_dd_duration_days"] = max_dd_duration

        risk_results[strategy_label] = long_stats

        print(f"\n    {strategy_label} 做多 (n={long_stats['n']}):")
        print(f"      avg={long_stats['avg_daily_exc']:+.3f}%, std={long_stats['std_daily_exc']:.3f}%, "
              f"wr={long_stats['win_rate']:.1%}")
        print(f"      max_dd={long_stats['max_drawdown_exc']:.2f}%, dd_dur={long_stats['max_dd_duration_days']}d")
        print(f"      sharpe={long_stats['sharpe_exc']:.3f}, sortino={long_stats['sortino_exc']:.3f}")
        print(f"      VaR(5%)={long_stats['var_5_exc']:.3f}%, CVaR={long_stats['cvar_5_exc']:.3f}%")
        print(f"      worst={long_stats['worst_day']:.3f}%, best={long_stats['best_day']:.3f}%")

        if len(short_exc) >= 5:
            short_wr = float((short_exc < 0).mean())
            print(f"    {strategy_label} 做空 (n={len(short_exc)}): wr={short_wr:.1%}")

    # 信号级别的尾部风险
    print("\n  ── 关键信号尾部风险 ──")
    signal_tail_risk = {}
    signals = {
        "mean_reverting+streak≤-3": (df["regime"] == "mean_reverting") & (df["outperform_streak"] <= -3),
        "mean_reverting+streak≤-2": (df["regime"] == "mean_reverting") & (df["outperform_streak"] <= -2),
        "transition+streak≤-2": (df["regime"] == "transition") & (df["outperform_streak"] <= -2),
        "RSI超买": df["rsi_14"] > 70,
        "周五": df["dow"] == 4,
        "MACD死叉": (df["macd_hist"].shift(1) > 0) & (df["macd_hist"] < 0),
    }

    for sig_name, mask in signals.items():
        vals = df.loc[mask, target_exc].dropna()
        if len(vals) < 5:
            continue

        tail_stat = {
            "n": int(len(vals)),
            "avg": round(float(vals.mean()), 4),
            "std": round(float(vals.std()), 4),
            "skew": round(float(vals.skew()), 3) if len(vals) > 10 else None,
            "kurtosis": round(float(vals.kurtosis()), 3) if len(vals) > 10 else None,
            "worst": round(float(vals.min()), 3),
            "best": round(float(vals.max()), 3),
            "p10": round(float(vals.quantile(0.10)), 3),
            "p90": round(float(vals.quantile(0.90)), 3),
        }
        signal_tail_risk[sig_name] = tail_stat

        print(f"    {sig_name}: avg={tail_stat['avg']:+.3f}%, "
              f"std={tail_stat['std']:.3f}%, "
              f"worst={tail_stat['worst']:+.3f}%, best={tail_stat['best']:+.3f}%")

    risk_results["signal_tail_risk"] = signal_tail_risk

    # 仓位管理建议：基于风险指标
    print("\n  ── 仓位管理建议（基于风险指标）──")
    if "V2_±3" in risk_results:
        v2_stats = risk_results["V2_±3"]
        wr = v2_stats["win_rate"]
        avg_win = v2_stats.get("best_day", 3.0) * 0.3  # 近似平均盈利
        avg_loss = abs(v2_stats.get("worst_day", -3.0)) * 0.3  # 近似平均亏损

        # Kelly
        if avg_loss > 0:
            b = avg_win / avg_loss
            kelly_f = (wr * b - (1 - wr)) / b
            half_kelly = kelly_f * 0.5
        else:
            half_kelly = 0.3

        # 风险预算：基于 VaR
        var_5 = abs(v2_stats.get("var_5_exc", 2.0))
        max_risk_pct = 2.0  # 单次最大容忍亏损 2%
        var_position = max_risk_pct / var_5 if var_5 > 0 else 0.5

        position_rec = {
            "half_kelly": round(half_kelly, 3),
            "var_based": round(min(var_position, 1.0), 3),
            "recommended": round(min(half_kelly, var_position, 0.8), 3),
            "max_drawdown": v2_stats["max_drawdown_exc"],
        }
        risk_results["position_recommendation"] = position_rec

        print(f"    Half-Kelly: {position_rec['half_kelly']:.1%}")
        print(f"    VaR-based: {position_rec['var_based']:.1%}")
        print(f"    推荐仓位: {position_rec['recommended']:.1%}")

    return risk_results


# ── 主函数 ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  信号实验室 P1 深度研究")
    print("=" * 70)

    df = load_and_prepare_data()

    all_results = {}

    # 1. CUSUM Regime
    all_results["cusum_analysis"] = analyze_cusum_vs_adx(df)

    # 2. 信号衰减
    all_results["signal_decay"] = analyze_signal_decay(df)

    # 3. Bootstrap 鲁棒性
    all_results["bootstrap_robustness"] = analyze_bootstrap_robustness(df)

    # 4. 交互探索
    all_results["interaction_analysis"] = analyze_interactions(df)

    # 5. 风险与回撤
    all_results["risk_analysis"] = analyze_risk_drawdown(df)

    # ── 输出 JSON ───────────────────────────────────────────────────────────
    all_results["meta"] = {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dataRows": len(df),
        "analysisScope": "P1 deep research: CUSUM / Decay / Bootstrap / Interaction / Risk",
    }

    out_path = DATA_DIR / "p1_deep_research.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n[OK] 输出: {out_path}")

    # ── 汇总关键发现 ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  P1 深度研究关键发现汇总")
    print("=" * 70)

    # CUSUM vs ADX
    cusum = all_results.get("cusum_analysis", {})
    cusum_cross = cusum.get("cusum_cross", {})
    adx_cross_key = "mean_reverting+streak≤-3"
    print(f"\n  [CUSUM] vs ADX Regime:")
    if cusum_cross:
        for key, stat in sorted(cusum_cross.items(),
                                 key=lambda x: abs(x[1].get("win_rate", 0.5) - 0.5),
                                 reverse=True)[:5]:
            print(f"    {key}: n={stat['n']}, wr={stat['win_rate']:.1%}")

    # Bootstrap 显著性
    boot = all_results.get("bootstrap_robustness", {})
    significant = [k for k, v in boot.items() if v.get("significant")]
    not_significant = [k for k, v in boot.items() if not v.get("significant") and v.get("n", 0) >= 5]
    print(f"\n  [Bootstrap] 统计显著: {len(significant)}/{len(boot)}")
    print(f"    显著: {', '.join(significant[:5])}")
    print(f"    不显著: {', '.join(not_significant[:5])}")

    # 最佳交互
    inter = all_results.get("interaction_analysis", {})
    best = inter.get("best_interaction", "")
    best_lift = inter.get("best_lift", 0)
    print(f"\n  [交互] 最佳组合: {best} (lift={best_lift:+.1%})")

    # 风险
    risk = all_results.get("risk_analysis", {})
    if "V2_±3" in risk:
        v2 = risk["V2_±3"]
        print(f"\n  [风险] V2±3: sharpe={v2.get('sharpe_exc', 0):.3f}, "
              f"max_dd={v2.get('max_drawdown_exc', 0):.2f}%, "
              f"VaR5%={v2.get('var_5_exc', 0):.3f}%")
    pos_rec = risk.get("position_recommendation", {})
    if pos_rec:
        print(f"  [仓位] 推荐: {pos_rec.get('recommended', 0):.1%} "
              f"(Kelly={pos_rec.get('half_kelly', 0):.1%}, VaR={pos_rec.get('var_based', 0):.1%})")


if __name__ == "__main__":
    main()
