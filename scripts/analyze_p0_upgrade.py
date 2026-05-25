#!/usr/bin/env python3
"""
信号实验室升级 - P0 阶段分析脚本
维度：R（经典技术指标）+ V（波动率体系）+ U（季节性效应）

对 AnchorLink 现有数据计算新维度信号，验证其预测效力。
输出 JSON 供前端和综合评分使用。
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

# ── 路径 ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "output"
PRICE_DIR = ROOT / "data" / "price" / "normalized"


# ── 技术指标计算 ──────────────────────────────────────────────────────────

def calc_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """标准 RSI"""
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_macd(closes: pd.Series, fast: int = 12, slow: int = 26,
              signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    """标准 MACD: (macd_line, signal_line, histogram)"""
    ema_fast = closes.ewm(span=fast, min_periods=fast).mean()
    ema_slow = closes.ewm(span=slow, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_bollinger(closes: pd.Series, period: int = 20,
                   num_std: float = 2.0) -> tuple:
    """标准 Bollinger Bands: (upper, middle, lower, bandwidth, pct_b)"""
    middle = closes.rolling(period).mean()
    std = closes.rolling(period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    bandwidth = (upper - lower) / middle.replace(0, np.nan)
    pct_b = (closes - lower) / (upper - lower).replace(0, np.nan)
    return upper, middle, lower, bandwidth, pct_b


def calc_adx(highs: pd.Series, lows: pd.Series, closes: pd.Series,
             period: int = 14) -> pd.Series:
    """标准 ADX"""
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
    adx = dx.ewm(alpha=1 / period, min_periods=period).mean()
    return adx


def calc_stochastic(highs: pd.Series, lows: pd.Series, closes: pd.Series,
                    k_period: int = 14, d_period: int = 3) -> tuple[pd.Series, pd.Series]:
    """标准 Stochastic: (%K, %D)"""
    lowest_low = lows.rolling(k_period).min()
    highest_high = highs.rolling(k_period).max()
    k = 100 * (closes - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    return k, d


def calc_atr(highs: pd.Series, lows: pd.Series, closes: pd.Series,
             period: int = 14) -> pd.Series:
    """标准 ATR"""
    tr1 = highs - lows
    tr2 = (highs - closes.shift(1)).abs()
    tr3 = (lows - closes.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period).mean()


def calc_keltner(closes: pd.Series, atr: pd.Series, period: int = 20,
                 mult: float = 1.5) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Keltner Channels: (upper, middle, lower)"""
    middle = closes.ewm(span=period, min_periods=period).mean()
    upper = middle + mult * atr
    lower = middle - mult * atr
    return upper, middle, lower


# ── 信号评估工具 ──────────────────────────────────────────────────────────

def eval_signal(hits: pd.Series, target: pd.Series, baseline_mean: float,
                label: str, min_n: int = 8) -> Optional[dict]:
    """
    评估信号预测效力。
    hits: bool 序列，信号是否激活
    target: 连续目标变量（next_1d_excess_vs_chain）
    baseline_mean: 全样本基线均值
    """
    valid = hits & target.notna()
    n = valid.sum()
    if n < min_n:
        return None

    vals = target[valid]
    avg = vals.mean()
    lift = avg - baseline_mean
    win_rate = (vals > 0).mean()

    # Pearson r
    if hits.sum() > 5 and hits.sum() < len(hits) - 5:
        r = np.corrcoef(hits.astype(float), target.fillna(0))[0, 1]
    else:
        r = None

    return {
        "label": label,
        "n": int(n),
        "avg": round(avg, 4),
        "lift": round(lift, 4),
        "win_rate": round(win_rate, 4),
        "pearson_r": round(r, 4) if r is not None and not np.isnan(r) else None,
    }


def eval_continuous_signal(feature: pd.Series, target: pd.Series,
                           label: str, n_bins: int = 5) -> list[dict]:
    """评估连续变量的分位预测效力"""
    results = []
    # 对齐索引
    common_idx = feature.dropna().index.intersection(target.dropna().index)
    feat_aligned = feature.loc[common_idx]
    target_aligned = target.loc[common_idx]

    try:
        quantiles = pd.qcut(feat_aligned, n_bins, duplicates="drop")
    except ValueError:
        return results

    baseline = target_aligned.mean()
    for cat in quantiles.cat.categories:
        mask = quantiles == cat
        vals = target_aligned[mask]
        n = len(vals)
        if n < 5:
            continue
        results.append({
            "label": label,
            "bucket": str(cat),
            "n": int(n),
            "avg": round(vals.mean(), 4),
            "lift": round(vals.mean() - baseline, 4),
            "win_rate": round((vals > 0).mean(), 4),
        })
    return results


# ── 主分析 ──────────────────────────────────────────────────────────────────

def main():
    print("[INFO] 加载数据...")

    # 1. 加载 OHLC 数据
    price_df = pd.read_parquet(PRICE_DIR / "market_data_normalized.parquet")
    blt = price_df[price_df["ts_code"] == "688333.SH"].copy()
    blt["trade_date"] = pd.to_datetime(blt["trade_date"])
    blt = blt.sort_values("trade_date").reset_index(drop=True)
    blt["date_str"] = blt["trade_date"].dt.strftime("%Y%m%d")

    # 2. 加载历史汇总
    hist = pd.read_csv(DATA_DIR / "history_summary.csv")
    hist["date_str"] = hist["date"].astype(str)

    # 3. 合并
    df = blt.merge(hist, left_on="date_str", right_on="date_str", how="inner",
                   suffixes=("", "_hist"))
    print(f"[OK] 合并后 {len(df)} 行，日期 {df['date_str'].iloc[0]} ~ {df['date_str'].iloc[-1]}")

    # 4. 计算技术指标
    print("[INFO] 计算技术指标...")
    c = df["close"]
    h = df["high"]
    l = df["low"]

    df["rsi_14"] = calc_rsi(c, 14)
    macd_line, signal_line, histogram = calc_macd(c)
    df["macd_hist"] = histogram
    df["macd_line"] = macd_line
    df["macd_signal"] = signal_line
    bb_upper, bb_mid, bb_lower, bb_bw, bb_pctb = calc_bollinger(c)
    df["bb_upper"] = bb_upper
    df["bb_lower"] = bb_lower
    df["bb_mid"] = bb_mid
    df["bb_bw"] = bb_bw
    df["bb_pctb"] = bb_pctb
    df["adx_14"] = calc_adx(h, l, c, 14)
    stoch_k, stoch_d = calc_stochastic(h, l, c)
    df["stoch_k"] = stoch_k
    df["stoch_d"] = stoch_d

    # ATR & Keltner
    df["atr_14"] = calc_atr(h, l, c, 14)
    kc_upper, kc_mid, kc_lower = calc_keltner(c, df["atr_14"])
    df["kc_upper"] = kc_upper
    df["kc_lower"] = kc_lower

    # 历史波动率
    df["hist_vol_20d"] = c.pct_change().rolling(20).std() * math.sqrt(252)
    df["hist_vol_60d"] = c.pct_change().rolling(60).std() * math.sqrt(252)

    # TTM Squeeze
    df["squeeze_on"] = (bb_lower > kc_lower) & (bb_upper < kc_upper)
    df["squeeze_release"] = df["squeeze_on"].shift(1) & ~df["squeeze_on"]
    # 动量方向（Squeeze 释放时用）
    df["squeeze_momentum"] = c - c.rolling(20).mean()

    # ATR 分位
    df["atr_pct"] = df["atr_14"].rank(pct=True)

    # 波动率比（短期/长期）
    df["vol_ratio"] = df["hist_vol_20d"] / df["hist_vol_60d"].replace(0, np.nan)

    # 5. 目标变量
    target = df["next_1d_excess_vs_chain"]
    baseline = target.mean()
    print(f"[INFO] 基线 T+1 超额均值: {baseline:.4f}")

    # ── R 维：经典技术指标信号 ────────────────────────────────────────────
    print("\n[INFO] ═══ R 维：经典技术指标信号 ═══")

    r_signals = {}

    # RSI 信号
    r_signals["RSI超卖(<30)"] = df["rsi_14"] < 30
    r_signals["RSI超买(>70)"] = df["rsi_14"] > 70
    r_signals["RSI偏低(<40)"] = df["rsi_14"] < 40
    r_signals["RSI偏高(>60)"] = df["rsi_14"] > 60
    r_signals["RSI中性区(40-60)"] = (df["rsi_14"] >= 40) & (df["rsi_14"] <= 60)

    # RSI 背离：价格新低但 RSI 没有新低（看涨背离）
    rsi_5d_low = df["rsi_14"].rolling(5).min()
    price_5d_low = df["close"].rolling(5).min()
    r_signals["RSI看涨背离(5d)"] = (df["close"] == price_5d_low) & (df["rsi_14"] > rsi_5d_low.shift(5))

    rsi_5d_high = df["rsi_14"].rolling(5).max()
    price_5d_high = df["close"].rolling(5).max()
    r_signals["RSI看跌背离(5d)"] = (df["close"] == price_5d_high) & (df["rsi_14"] < rsi_5d_high.shift(5))

    # MACD 信号
    r_signals["MACD金叉"] = (df["macd_line"] > df["macd_signal"]) & (df["macd_line"].shift(1) <= df["macd_signal"].shift(1))
    r_signals["MACD死叉"] = (df["macd_line"] < df["macd_signal"]) & (df["macd_line"].shift(1) >= df["macd_signal"].shift(1))
    r_signals["MACD柱状图正"] = df["macd_hist"] > 0
    r_signals["MACD柱状图负"] = df["macd_hist"] < 0
    r_signals["MACD柱状图转正"] = (df["macd_hist"] > 0) & (df["macd_hist"].shift(1) <= 0)

    # Bollinger 信号
    r_signals["BB下轨触及"] = df["close"] <= df["bb_lower"]
    r_signals["BB上轨触及"] = df["close"] >= df["bb_upper"]
    r_signals["BB带宽压缩(P15)"] = df["bb_bw"] <= df["bb_bw"].quantile(0.15)
    r_signals["BB带宽扩张(P85)"] = df["bb_bw"] >= df["bb_bw"].quantile(0.85)
    r_signals["BB%b<0(破下轨)"] = df["bb_pctb"] < 0
    r_signals["BB%b>1(破上轨)"] = df["bb_pctb"] > 1

    # ADX 信号
    r_signals["ADX趋势确立(>25)"] = df["adx_14"] > 25
    r_signals["ADX震荡市(<20)"] = df["adx_14"] < 20
    r_signals["ADX强趋势(>35)"] = df["adx_14"] > 35

    # Stochastic 信号
    r_signals["Stoch超卖(K<20)"] = df["stoch_k"] < 20
    r_signals["Stoch超买(K>80)"] = df["stoch_k"] > 80
    r_signals["Stoch金叉"] = (df["stoch_k"] > df["stoch_d"]) & (df["stoch_k"].shift(1) <= df["stoch_d"].shift(1))
    r_signals["Stoch死叉"] = (df["stoch_k"] < df["stoch_d"]) & (df["stoch_k"].shift(1) >= df["stoch_d"].shift(1))

    r_results = []
    for label, mask in r_signals.items():
        res = eval_signal(mask, target, baseline, label)
        if res:
            r_results.append(res)
            sig = "🟢" if res["lift"] > 0.3 else ("🔴" if res["lift"] < -0.3 else "⬜")
            print(f"  {sig} {label}: n={res['n']}, lift={res['lift']:+.3f}%, wr={res['win_rate']:.1%}")

    # RSI 连续变量分析
    print("\n  [RSI 分位分析]")
    rsi_quintile = eval_continuous_signal(df["rsi_14"].dropna(), target, "RSI_14")
    for r in rsi_quintile:
        print(f"    RSI {r['bucket']}: n={r['n']}, avg={r['avg']:+.3f}%, lift={r['lift']:+.3f}%, wr={r['win_rate']:.1%}")

    # ── V 维：波动率信号 ──────────────────────────────────────────────────
    print("\n[INFO] ═══ V 维：波动率信号 ═══")

    v_signals = {}

    # ATR 分位信号
    v_signals["ATR极高(P85+)"] = df["atr_pct"] > 0.85
    v_signals["ATR极低(P15-)"] = df["atr_pct"] < 0.15
    v_signals["ATR偏高(P70+)"] = df["atr_pct"] > 0.70
    v_signals["ATR偏低(P30-)"] = df["atr_pct"] < 0.30

    # 波动率比信号
    v_signals["Vol压缩(短/长<0.7)"] = df["vol_ratio"] < 0.7
    v_signals["Vol扩张(短/长>1.3)"] = df["vol_ratio"] > 1.3

    # TTM Squeeze
    v_signals["Squeeze压缩中"] = df["squeeze_on"]
    v_signals["Squeeze释放"] = df["squeeze_release"]
    v_signals["Squeeze释放+正动量"] = df["squeeze_release"] & (df["squeeze_momentum"] > 0)
    v_signals["Squeeze释放+负动量"] = df["squeeze_release"] & (df["squeeze_momentum"] <= 0)

    v_results = []
    for label, mask in v_signals.items():
        res = eval_signal(mask, target, baseline, label)
        if res:
            v_results.append(res)
            sig = "🟢" if res["lift"] > 0.3 else ("🔴" if res["lift"] < -0.3 else "⬜")
            print(f"  {sig} {label}: n={res['n']}, lift={res['lift']:+.3f}%, wr={res['win_rate']:.1%}")

    # ATR 分位连续分析
    print("\n  [ATR 分位分析]")
    atr_quintile = eval_continuous_signal(df["atr_pct"].dropna(), target, "ATR_pct")
    for r in atr_quintile:
        print(f"    ATR {r['bucket']}: n={r['n']}, avg={r['avg']:+.3f}%, lift={r['lift']:+.3f}%, wr={r['win_rate']:.1%}")

    # BB带宽分位
    print("\n  [BB带宽分位分析]")
    bbw_quintile = eval_continuous_signal(df["bb_bw"].dropna(), target, "BB_BW")
    for r in bbw_quintile:
        print(f"    BBW {r['bucket']}: n={r['n']}, avg={r['avg']:+.3f}%, lift={r['lift']:+.3f}%, wr={r['win_rate']:.1%}")

    # ── U 维：季节性信号 ──────────────────────────────────────────────────
    print("\n[INFO] ═══ U 维：季节性信号 ═══")

    df["dow"] = df["trade_date"].dt.dayofweek  # 0=周一, 4=周五
    df["dom"] = df["trade_date"].dt.day  # 月内日
    df["month"] = df["trade_date"].dt.month

    u_signals = {}
    u_signals["周一效应"] = df["dow"] == 0
    u_signals["周五效应"] = df["dow"] == 4
    u_signals["周二效应"] = df["dow"] == 1
    u_signals["周三效应"] = df["dow"] == 2
    u_signals["周四效应"] = df["dow"] == 3
    u_signals["月初(1-5日)"] = df["dom"] <= 5
    u_signals["月末(26-31日)"] = df["dom"] >= 26

    # 月份效应
    for m in range(1, 13):
        u_signals[f"{m}月效应"] = df["month"] == m

    u_results = []
    for label, mask in u_signals.items():
        res = eval_signal(mask, target, baseline, label)
        if res:
            u_results.append(res)
            sig = "🟢" if res["lift"] > 0.3 else ("🔴" if res["lift"] < -0.3 else "⬜")
            print(f"  {sig} {label}: n={res['n']}, lift={res['lift']:+.3f}%, wr={res['win_rate']:.1%}")

    # 周内 × 月份交叉
    print("\n  [周内效应细分]")
    dow_names = ["周一", "周二", "周三", "周四", "周五"]
    for dow_idx, dow_name in enumerate(dow_names):
        mask = df["dow"] == dow_idx
        vals = target[mask].dropna()
        if len(vals) >= 5:
            print(f"    {dow_name}: n={len(vals)}, avg={vals.mean():+.3f}%, wr={(vals>0).mean():.1%}")

    # ── 交叉验证：新信号 × 现有最强信号 ──────────────────────────────────
    print("\n[INFO] ═══ 交叉验证：新信号 × 现有最强信号 ═══")

    # 现有最强：outperform_streak <= -3
    if "outperform_streak" not in df.columns:
        # 从 history_rolling_metrics.csv 加载
        try:
            rolling = pd.read_csv(DATA_DIR / "history_rolling_metrics.csv")
            rolling["date_str"] = rolling["date"].astype(str)
            df = df.merge(rolling, left_on="date_str", right_on="date_str", how="left",
                         suffixes=("", "_roll"))
        except Exception:
            print("[WARN] 无法加载 rolling metrics，跳过交叉验证")
            rolling = None

    # 现有信号解析
    def parse_signal_labels(s):
        if pd.isna(s) or s == "[]":
            return set()
        try:
            return set(json.loads(s.replace("'", '"'))) if isinstance(s, str) else set()
        except Exception:
            return set()

    if "signal_labels" in df.columns:
        df["signal_set"] = df["signal_labels"].apply(parse_signal_labels)
        df["has_放量上涨"] = df["signal_set"].apply(lambda s: "放量上涨" in s)
        df["has_行业Beta为正"] = df["signal_set"].apply(lambda s: "行业Beta为正" in s)

    # 交叉 1：RSI超卖 + outperform_streak<=-2
    if "outperform_streak" in df.columns:
        cross1 = (df["rsi_14"] < 40) & (df["outperform_streak"] <= -2)
        res = eval_signal(cross1, target, baseline, "RSI<40 + Streak≤-2")
        if res:
            print(f"  🟢 RSI<40 + Streak≤-2: n={res['n']}, lift={res['lift']:+.3f}%, wr={res['win_rate']:.1%}")

        cross2 = (df["rsi_14"] < 40) & (df["adx_14"] < 25)
        res = eval_signal(cross2, target, baseline, "RSI<40 + ADX<25(震荡)")
        if res:
            print(f"  🟢 RSI<40 + ADX<25: n={res['n']}, lift={res['lift']:+.3f}%, wr={res['win_rate']:.1%}")

    # 交叉 2：BB压缩 + 现有excess_5d过冷
    if "excess_5d" in df.columns:
        cross3 = (df["bb_bw"] < df["bb_bw"].quantile(0.15)) & (df["excess_5d"] < df["excess_5d"].quantile(0.30))
        res = eval_signal(cross3, target, baseline, "BBW压缩 + excess_5d偏冷")
        if res:
            print(f"  🟢 BBW压缩 + excess_5d偏冷: n={res['n']}, lift={res['lift']:+.3f}%, wr={res['win_rate']:.1%}")

    # 交叉 3：周一 + 现有负信号（双杀）
    if "has_放量上涨" in df.columns:
        cross4 = (df["dow"] == 0) & df["has_放量上涨"]
        res = eval_signal(cross4, target, baseline, "周一 + 放量上涨")
        if res:
            print(f"  🔴 周一 + 放量上涨: n={res['n']}, lift={res['lift']:+.3f}%, wr={res['win_rate']:.1%}")

    # 交叉 4：周五 + 缺少负信号
    if "has_放量上涨" in df.columns:
        cross5 = (df["dow"] == 4) & ~df["has_放量上涨"] & ~df["has_行业Beta为正"]
        res = eval_signal(cross5, target, baseline, "周五 + 无负信号")
        if res:
            print(f"  🟢 周五 + 无负信号: n={res['n']}, lift={res['lift']:+.3f}%, wr={res['win_rate']:.1%}")

    # ── CUSUM Regime 检测 ─────────────────────────────────────────────────
    print("\n[INFO] ═══ S 维：Regime 检测 ═══")

    # 基于 ADX 的简单 Regime
    df["regime"] = "transition"
    df.loc[df["adx_14"] >= 25, "regime"] = "trending"
    df.loc[df["adx_14"] <= 20, "regime"] = "mean_reverting"

    for regime_name in ["trending", "mean_reverting", "transition"]:
        mask = df["regime"] == regime_name
        vals = target[mask].dropna()
        n = len(vals)
        if n >= 5:
            print(f"  {regime_name}: n={n}, avg={vals.mean():+.3f}%, wr={(vals>0).mean():.1%}")

    # Regime × 现有最强信号
    print("\n  [Regime × Streak 交叉]")
    if "outperform_streak" in df.columns:
        for regime_name in ["trending", "mean_reverting", "transition"]:
            for streak_cond, streak_label in [(-3, "≤-3"), (-2, "≤-2"), (2, "≥+2"), (3, "≥+3")]:
                if streak_label.startswith("≤"):
                    mask = (df["regime"] == regime_name) & (df["outperform_streak"] <= streak_cond)
                else:
                    mask = (df["regime"] == regime_name) & (df["outperform_streak"] >= streak_cond)
                vals = target[mask].dropna()
                n = len(vals)
                if n >= 5:
                    sig = "🟢" if vals.mean() > 0.3 else ("🔴" if vals.mean() < -0.3 else "⬜")
                    print(f"    {sig} {regime_name} + streak{streak_label}: n={n}, avg={vals.mean():+.3f}%, wr={(vals>0).mean():.1%}")

    # CUSUM 检测
    print("\n  [CUSUM 变点检测]")
    returns = df["anchor_return"].dropna().values
    cusum = np.zeros(len(returns))
    regimes_cusum = [0]
    current_regime = 0
    threshold = 2.0 * np.std(returns[:60]) if len(returns) > 60 else 2.0 * np.std(returns)

    for i in range(1, len(returns)):
        cusum[i] = cusum[i-1] + (returns[i] - np.mean(returns[:min(i, 60)]))
        if abs(cusum[i]) > threshold:
            current_regime += 1
            cusum[i] = 0
        regimes_cusum.append(current_regime)

    df_cusum = pd.DataFrame({"regime_cusum": regimes_cusum})
    df_cusum["target"] = target.values[:len(regimes_cusum)]

    for rg in sorted(df_cusum["regime_cusum"].unique()):
        vals = df_cusum[df_cusum["regime_cusum"] == rg]["target"].dropna()
        if len(vals) >= 5:
            print(f"    CUSUM regime {rg}: n={len(vals)}, avg={vals.mean():+.3f}%, wr={(vals>0).mean():.1%}")

    # ── SMC 信号 ──────────────────────────────────────────────────────────
    print("\n[INFO] ═══ T 维：SMC 信号 ═══")

    # Fair Value Gap 检测
    fvg_bullish = []
    fvg_bearish = []
    for i in range(1, len(df) - 1):
        # 看涨 FVG: bar[i-1].high < bar[i+1].low
        gap_up = df.iloc[i+1]["low"] - df.iloc[i-1]["high"]
        if gap_up > 0 and (gap_up / df.iloc[i-1]["high"]) * 100 >= 0.3:
            fvg_bullish.append({"idx": i, "gap_pct": (gap_up / df.iloc[i-1]["high"]) * 100})

        # 看跌 FVG: bar[i-1].low > bar[i+1].high
        gap_down = df.iloc[i-1]["low"] - df.iloc[i+1]["high"]
        if gap_down > 0 and (gap_down / df.iloc[i-1]["low"]) * 100 >= 0.3:
            fvg_bearish.append({"idx": i, "gap_pct": (gap_down / df.iloc[i-1]["low"]) * 100})

    print(f"  看涨 FVG: {len(fvg_bullish)} 个")
    print(f"  看跌 FVG: {len(fvg_bearish)} 个")

    # 标记今日是否有未填补 FVG
    df["has_bullish_fvg"] = False
    df["has_bearish_fvg"] = False
    for fvg in fvg_bullish:
        df.loc[fvg["idx"], "has_bullish_fvg"] = True
    for fvg in fvg_bearish:
        df.loc[fvg["idx"], "has_bearish_fvg"] = True

    # FVG 信号评估
    res = eval_signal(df["has_bullish_fvg"], target, baseline, "看涨FVG日")
    if res:
        sig = "🟢" if res["lift"] > 0.3 else ("🔴" if res["lift"] < -0.3 else "⬜")
        print(f"  {sig} 看涨FVG日: n={res['n']}, lift={res['lift']:+.3f}%, wr={res['win_rate']:.1%}")

    res = eval_signal(df["has_bearish_fvg"], target, baseline, "看跌FVG日")
    if res:
        sig = "🟢" if res["lift"] > 0.3 else ("🔴" if res["lift"] < -0.3 else "⬜")
        print(f"  {sig} 看跌FVG日: n={res['n']}, lift={res['lift']:+.3f}%, wr={res['win_rate']:.1%}")

    # BOS/CHoCH: 创 N 日新高/新低
    lookback = 20
    df["n_day_high"] = df["close"].rolling(lookback).max()
    df["n_day_low"] = df["close"].rolling(lookback).min()
    df["bos_up"] = df["close"] >= df["n_day_high"]  # 创新高
    df["bos_down"] = df["close"] <= df["n_day_low"]  # 创新低

    # CHoCH: 创新高后次日下跌 或 创新低后次日上涨（简化版）
    df["choch_down"] = df["bos_up"].shift(1) & (df["close"] < df["close"].shift(1))
    df["choch_up"] = df["bos_down"].shift(1) & (df["close"] > df["close"].shift(1))

    for label, mask in [("BOS创20日新高", df["bos_up"]), ("BOS创20日新低", df["bos_down"]),
                        ("CHoCH上(新低后涨)", df["choch_up"]), ("CHoCH下(新高后跌)", df["choch_down"])]:
        res = eval_signal(mask, target, baseline, label)
        if res:
            sig = "🟢" if res["lift"] > 0.3 else ("🔴" if res["lift"] < -0.3 else "⬜")
            print(f"  {sig} {label}: n={res['n']}, lift={res['lift']:+.3f}%, wr={res['win_rate']:.1%}")

    # Liquidity Sweep: 价格穿透前日高/低但收盘未站稳
    df["liq_sweep_high"] = (df["high"] > df["high"].shift(1)) & (df["close"] < df["high"].shift(1))
    df["liq_sweep_low"] = (df["low"] < df["low"].shift(1)) & (df["close"] > df["low"].shift(1))

    for label, mask in [("LiqSweep高(假突破)", df["liq_sweep_high"]),
                        ("LiqSweep低(假突破)", df["liq_sweep_low"])]:
        res = eval_signal(mask, target, baseline, label)
        if res:
            sig = "🟢" if res["lift"] > 0.3 else ("🔴" if res["lift"] < -0.3 else "⬜")
            print(f"  {sig} {label}: n={res['n']}, lift={res['lift']:+.3f}%, wr={res['win_rate']:.1%}")

    # ── 汇总与输出 ────────────────────────────────────────────────────────
    print("\n[INFO] ═══ 信号效力汇总 ═══")

    all_results = r_results + v_results + u_results

    # 按绝对 lift 排序
    all_results.sort(key=lambda x: abs(x["lift"]), reverse=True)

    # 分类
    strong_positive = [r for r in all_results if r["lift"] > 0.3 and r["win_rate"] > 0.52]
    strong_negative = [r for r in all_results if r["lift"] < -0.3 and r["win_rate"] < 0.48]
    neutral = [r for r in all_results if r not in strong_positive and r not in strong_negative]

    print(f"\n  🟢 强正向信号 ({len(strong_positive)} 个):")
    for r in strong_positive[:10]:
        print(f"    {r['label']}: lift={r['lift']:+.3f}%, wr={r['win_rate']:.1%}, n={r['n']}")

    print(f"\n  🔴 强负向信号 ({len(strong_negative)} 个):")
    for r in strong_negative[:10]:
        print(f"    {r['label']}: lift={r['lift']:+.3f}%, wr={r['win_rate']:.1%}, n={r['n']}")

    print(f"\n  ⬜ 中性信号 ({len(neutral)} 个)")

    # 与现有最强信号对比
    print("\n[INFO] ═══ 与现有信号对比 ═══")
    if "outperform_streak" in df.columns:
        streak_mask = df["outperform_streak"] <= -3
        res = eval_signal(streak_mask, target, baseline, "outperform_streak≤-3(现有最强)")
        if res:
            print(f"  基准: streak≤-3: n={res['n']}, lift={res['lift']:+.3f}%, wr={res['win_rate']:.1%}")

    # 输出 JSON
    output = {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "baseline_excess_1d": round(baseline, 4),
        "R_technicalIndicators": {
            "signals": r_results,
            "rsi_quintile": rsi_quintile,
        },
        "V_volatility": {
            "signals": v_results,
            "atr_quintile": atr_quintile,
            "bbw_quintile": bbw_quintile,
        },
        "U_seasonality": {
            "signals": u_results,
            "dow_stats": {
                dow_names[d]: {
                    "n": int((df["dow"] == d).sum()),
                    "avg": round(target[df["dow"] == d].mean(), 4) if (df["dow"] == d).sum() > 0 else None,
                    "win_rate": round((target[df["dow"] == d] > 0).mean(), 4) if (df["dow"] == d).sum() > 0 else None,
                }
                for d in range(5)
            },
        },
        "summary": {
            "strong_positive": strong_positive[:10],
            "strong_negative": strong_negative[:10],
            "new_signal_count": len(all_results),
            "effective_count": len(strong_positive) + len(strong_negative),
        },
    }

    out_path = DATA_DIR / "p0_upgrade_analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 输出: {out_path}")

    # 输出特征 CSV（供 ML 使用）
    feature_cols = ["date_str", "rsi_14", "macd_hist", "bb_bw", "bb_pctb", "adx_14",
                    "stoch_k", "atr_14", "atr_pct", "hist_vol_20d", "hist_vol_60d",
                    "vol_ratio", "squeeze_on", "squeeze_release", "squeeze_momentum",
                    "regime", "dow", "month"]
    available_cols = [c for c in feature_cols if c in df.columns]
    feat_path = DATA_DIR / "p0_ti_features.csv"
    df[available_cols].to_csv(feat_path, index=False)
    print(f"[OK] 特征 CSV: {feat_path}")


if __name__ == "__main__":
    main()
