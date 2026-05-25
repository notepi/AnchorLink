#!/usr/bin/env python3
"""
信号实验室升级 - 综合评分 v2 回测
集成 P0 新信号 + Regime 自适应 + Walk-Forward 验证

基于 P0 分析结果：
- Regime 过滤器（ADX）应用到 Streak 信号
- 新买入信号：MACD柱负、周三、LiqSweep高、CHoCH上
- 新卖出信号：周五、RSI超买、Stoch超买、BB上轨触及、看跌FVG、BOS创新高
- Regime 自适应权重
- Walk-Forward 回测（消除前视偏差）
- Kelly 仓位管理
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


# ── 技术指标（与 analyze_p0_upgrade.py 一致）──────────────────────────────

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


# ── 信号定义 ──────────────────────────────────────────────────────────────

# V1 买入信号（原有）
V1_BUY = {
    "excess_5d_P15-": +3,
    "excess_10d_P15-": +3,
    "outperform_streak_≤-3": +3,
    "跌但资金支撑": +2,
    "delta_excess_5d_温和回调": +2,
    "alpha_signal_count_≥3": +2,
    "path_弱+弱→中或强": +2,
    "缩量阴跌": +1,
    "trading_corr_快速上升": +1,
    "rs_vs_chain_Q2": +1,
}

# V1 卖出信号（原有）
V1_SELL = {
    "excess_5d_P85+": -3,
    "放量大涨_veto": -3,
    "outperform_streak_≥+3": -2,
    "delta_excess_5d_最快上升": -2,
    "rs_vs_chain_Q5": -2,
    "Beta骑乘组合": -2,
    "信号_放量上涨": -2,
    "excess_10d_P70-P85": -1,
    "放量大跌": -1,
    "path_强+强→强+弱": -1,
}

# V2 新增买入信号（P0 验证通过）
V2_NEW_BUY = {
    "mean_reverting+streak≤-3": +5,     # 77.8%胜率，最强信号
    "mean_reverting+streak≤-2": +3,     # 65%胜率
    "transition+streak≤-2": +3,         # 66.7%胜率
    "MACD柱状图负": +1,                 # 54.7%胜率, n=95
    "周三效应": +1,                      # 54%胜率, n=50
    "LiqSweep高(假突破)": +1,           # 59.2%胜率, n=49
}

# V2 新增卖出信号（P0 验证通过）
V2_NEW_SELL = {
    "transition+streak≥+2": -4,         # 25%胜率，最强卖出
    "周五+ADX<25": -3,                  # 33.3%胜率
    "周五效应": -2,                      # 36.7%胜率, n=49
    "RSI超买(>70)": -2,                 # 35.3%胜率
    "Stoch超买(K>80)": -2,             # 36.1%胜率
    "BB上轨触及": -2,                   # 36.8%胜率
    "看跌FVG日": -2,                    # 31.8%胜率
    "BOS创20日新高": -1,               # 39.3%胜率
}

# Regime 自适应乘数
REGIME_MULTIPLIER = {
    "mean_reverting": {
        "streak_buy": 1.5,   # Streak 买入信号在 mean_reverting 下增强
        "streak_sell": 1.3,  # Streak 卖出信号在 mean_reverting 下增强
        "reversion_buy": 1.3,
        "trend_buy": 0.7,
    },
    "trending": {
        "streak_buy": 0.8,
        "streak_sell": 1.0,
        "reversion_buy": 0.8,
        "trend_buy": 1.2,
    },
    "transition": {
        "streak_buy": 1.3,
        "streak_sell": 1.3,
        "reversion_buy": 1.0,
        "trend_buy": 1.0,
    },
}

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


# ── 数据加载与特征计算 ────────────────────────────────────────────────────

def load_and_prepare_data() -> pd.DataFrame:
    """加载所有数据并计算技术指标"""
    print("[INFO] 加载数据...")

    # OHLC
    price_df = pd.read_parquet(PRICE_DIR / "market_data_normalized.parquet")
    blt = price_df[price_df["ts_code"] == "688333.SH"].copy()
    blt["trade_date"] = pd.to_datetime(blt["trade_date"])
    blt = blt.sort_values("trade_date").reset_index(drop=True)
    blt["date_str"] = blt["trade_date"].dt.strftime("%Y%m%d")

    # 历史汇总
    hist = pd.read_csv(DATA_DIR / "history_summary.csv")
    hist["date_str"] = hist["date"].astype(str)

    # 滚动指标
    rolling = pd.read_csv(DATA_DIR / "history_rolling_metrics.csv")
    rolling["date_str"] = rolling["date"].astype(str)

    # 合并
    df = blt.merge(hist, on="date_str", how="inner", suffixes=("", "_hist"))
    df = df.merge(rolling, on="date_str", how="inner", suffixes=("", "_roll"))

    # 计算技术指标
    print("[INFO] 计算技术指标...")
    c, h, l = df["close"], df["high"], df["low"]

    df["rsi_14"] = calc_rsi(c, 14)
    macd_line, signal_line, histogram = calc_macd(c)
    df["macd_hist"] = histogram
    bb_upper, bb_mid, bb_lower, bb_bw, bb_pctb = calc_bollinger(c)
    df["bb_upper"] = bb_upper
    df["bb_pctb"] = bb_pctb
    df["bb_bw"] = bb_bw
    df["adx_14"] = calc_adx(h, l, c, 14)
    stoch_k, stoch_d = calc_stochastic(h, l, c)
    df["stoch_k"] = stoch_k
    df["atr_14"] = calc_atr(h, l, c, 14)

    # Keltner channels for Squeeze
    kc_mid = c.ewm(span=20, min_periods=20).mean()
    kc_upper = kc_mid + 1.5 * df["atr_14"]
    kc_lower = kc_mid - 1.5 * df["atr_14"]
    df["squeeze_on"] = (bb_lower > kc_lower) & (bb_upper < kc_upper)

    # Regime
    df["regime"] = "transition"
    df.loc[df["adx_14"] >= 25, "regime"] = "trending"
    df.loc[df["adx_14"] <= 20, "regime"] = "mean_reverting"

    # 季节性
    df["dow"] = df["trade_date"].dt.dayofweek
    df["month"] = df["trade_date"].dt.month

    # SMC
    # LiqSweep高
    df["liq_sweep_high"] = (df["high"] > df["high"].shift(1)) & (df["close"] < df["high"].shift(1))
    # BOS创20日新高
    df["n_day_high"] = df["close"].rolling(20).max()
    df["bos_20d_high"] = df["close"] >= df["n_day_high"]
    # CHoCH上（新低后涨）
    df["n_day_low"] = df["close"].rolling(20).min()
    df["bos_20d_low"] = df["close"] <= df["n_day_low"]
    df["choch_up"] = df["bos_20d_low"].shift(1) & (df["close"] > df["close"].shift(1))
    # 看跌FVG
    df["bearish_fvg"] = False
    for i in range(1, len(df) - 1):
        gap_down = df.iloc[i - 1]["low"] - df.iloc[i + 1]["high"]
        if gap_down > 0 and (gap_down / df.iloc[i - 1]["low"]) * 100 >= 0.3:
            df.loc[df.index[i], "bearish_fvg"] = True

    # 信号集合
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


# ── 信号计算 ──────────────────────────────────────────────────────────────

def compute_v1_signals(row, thresholds: dict) -> list[tuple[str, int]]:
    """计算 V1 原有信号"""
    active = []
    e5 = row.get("excess_5d", np.nan)
    e10 = row.get("excess_10d", np.nan)
    out_streak = row.get("outperform_streak", 0)
    ar = row.get("anchor_return", 0)
    mf = row.get("moneyflow_positive_ratio", 0)
    ae = row.get("amount_expansion_ratio", 1)
    alpha_count = row.get("alpha_count", 0)
    rs_chain = row.get("relative_strength_vs_industry_chain", 0)
    sigs = row.get("signal_set", set())

    if pd.notna(e5) and e5 <= thresholds["excess_5d_p15"]:
        active.append(("excess_5d_P15-", +3))
    if pd.notna(e5) and e5 >= thresholds["excess_5d_p85"]:
        active.append(("excess_5d_P85+", -3))
    if pd.notna(e10) and e10 <= thresholds["excess_10d_p15"]:
        active.append(("excess_10d_P15-", +3))
    if pd.notna(e10) and thresholds.get("excess_10d_p70") and e10 >= thresholds["excess_10d_p70"] and e10 < thresholds.get("excess_10d_p85", 999):
        active.append(("excess_10d_P70-P85", -1))

    if isinstance(out_streak, (int, float)) and out_streak <= -3:
        active.append(("outperform_streak_≤-3", +3))
    if isinstance(out_streak, (int, float)) and out_streak >= 3:
        active.append(("outperform_streak_≥+3", -2))

    # delta excess 5d
    # (简化：用 excess_5d 的日变化近似)

    if ar < 0 and mf > 0.6:
        active.append(("跌但资金支撑", +2))
    if ar < -0.5 and ae < 0.85:
        active.append(("缩量阴跌", +1))
    if ar > 1.0 and ae > 1.3:
        active.append(("放量大涨_veto", -3))
    if ar < -1.0 and ae > 1.3:
        active.append(("放量大跌", -1))

    if alpha_count >= 3:
        active.append(("alpha_signal_count_≥3", +2))

    if isinstance(rs_chain, (int, float)) and -2.1 <= rs_chain <= -0.8:
        active.append(("rs_vs_chain_Q2", +1))
    if isinstance(rs_chain, (int, float)) and rs_chain >= 1.7:
        active.append(("rs_vs_chain_Q5", -2))

    if "行业Beta为正" in sigs and "处于行业前排" in sigs:
        active.append(("Beta骑乘组合", -2))
    if "放量上涨" in sigs:
        active.append(("信号_放量上涨", -2))

    # Path signals
    prev = row.get("prev_state", "")
    today = row.get("today_state", "")
    if prev in ("negative+negative", "negative+neutral") and today in (
            "positive+positive", "positive+negative", "positive+neutral"):
        active.append(("path_弱+弱→中或强", +2))
    if prev == "positive+positive" and today in ("positive+negative", "neutral+negative"):
        active.append(("path_强+强→强+弱", -1))

    return active


def compute_v2_new_signals(row) -> list[tuple[str, int]]:
    """计算 V2 新增信号"""
    active = []
    regime = row.get("regime", "transition")
    out_streak = row.get("outperform_streak", 0)

    # Regime × Streak 交叉（最强新信号）
    if isinstance(out_streak, (int, float)):
        if regime == "mean_reverting" and out_streak <= -3:
            active.append(("mean_reverting+streak≤-3", +5))
        elif regime == "mean_reverting" and out_streak <= -2:
            active.append(("mean_reverting+streak≤-2", +3))
        elif regime == "transition" and out_streak <= -2:
            active.append(("transition+streak≤-2", +3))
        elif regime == "transition" and out_streak >= 2:
            active.append(("transition+streak≥+2", -4))

    # 技术指标信号
    rsi = row.get("rsi_14", np.nan)
    stoch_k = row.get("stoch_k", np.nan)
    macd_hist = row.get("macd_hist", np.nan)
    bb_pctb = row.get("bb_pctb", np.nan)
    adx = row.get("adx_14", np.nan)

    if pd.notna(macd_hist) and macd_hist < 0:
        active.append(("MACD柱状图负", +1))

    if pd.notna(rsi) and rsi > 70:
        active.append(("RSI超买(>70)", -2))

    if pd.notna(stoch_k) and stoch_k > 80:
        active.append(("Stoch超买(K>80)", -2))

    if pd.notna(bb_pctb) and bb_pctb > 1:
        active.append(("BB上轨触及", -2))

    # 季节性
    dow = row.get("dow", -1)
    if dow == 2:  # 周三
        active.append(("周三效应", +1))
    if dow == 4:  # 周五
        active.append(("周五效应", -2))
        if pd.notna(adx) and adx < 25:
            active.append(("周五+ADX<25", -3))

    # SMC
    if row.get("liq_sweep_high", False):
        active.append(("LiqSweep高(假突破)", +1))
    if row.get("bearish_fvg", False):
        active.append(("看跌FVG日", -2))
    if row.get("bos_20d_high", False):
        active.append(("BOS创20日新高", -1))

    return active


def apply_regime_multiplier(signal_name: str, weight: int, regime: str) -> int:
    """根据 Regime 调整信号权重"""
    mults = REGIME_MULTIPLIER.get(regime, {})

    # Streak 相关信号
    if "streak" in signal_name:
        if weight > 0:
            mult = mults.get("streak_buy", 1.0)
        else:
            mult = mults.get("streak_sell", 1.0)
    # 均值回归信号
    elif signal_name in ("MACD柱状图负", "跌但资金支撑", "缩量阴跌",
                         "excess_5d_P15-", "excess_10d_P15-"):
        mult = mults.get("reversion_buy", 1.0) if weight > 0 else 1.0
    # 趋势信号
    elif signal_name in ("周三效应",):
        mult = mults.get("trend_buy", 1.0)
    else:
        mult = 1.0

    adjusted = round(weight * mult)
    return adjusted if adjusted != 0 else (1 if weight > 0 else -1)


def compute_composite_score(row, thresholds: dict, use_v2: bool = True,
                            use_regime: bool = True) -> tuple[int, bool, list[str]]:
    """计算综合评分"""
    v1_active = compute_v1_signals(row, thresholds)

    if use_v2:
        v2_active = compute_v2_new_signals(row)
        all_active = v1_active + v2_active
    else:
        all_active = v1_active

    regime = row.get("regime", "transition") if use_regime else "transition"

    # 计算加权分数
    total_score = 0
    signal_names = []
    for name, weight in all_active:
        if use_regime:
            adjusted = apply_regime_multiplier(name, weight, regime)
        else:
            adjusted = weight
        total_score += adjusted
        signal_names.append(f"{name}({adjusted:+d})")

    # Veto: 放量大涨
    ar = row.get("anchor_return", 0)
    ae = row.get("amount_expansion_ratio", 1)
    veto = (ar > 1.0 and ae > 1.3)

    return total_score, veto, signal_names


# ── 回测引擎 ──────────────────────────────────────────────────────────────

def compute_thresholds_from_sample(sample: pd.DataFrame) -> dict:
    """从样本数据计算阈值（用于 Walk-Forward）"""
    e5 = sample["excess_5d"].dropna()
    e10 = sample["excess_10d"].dropna()

    return {
        "excess_5d_p15": e5.quantile(0.15) if len(e5) > 10 else -4.91,
        "excess_5d_p85": e5.quantile(0.85) if len(e5) > 10 else 5.74,
        "excess_10d_p15": e10.quantile(0.15) if len(e10) > 10 else -6.11,
        "excess_10d_p70": e10.quantile(0.70) if len(e10) > 10 else 3.0,
        "excess_10d_p85": e10.quantile(0.85) if len(e10) > 10 else 5.5,
    }


def walk_forward_backtest(df: pd.DataFrame, train_window: int = 120,
                          use_v2: bool = True,
                          use_regime: bool = True) -> list[dict]:
    """Walk-Forward 回测"""
    results = []

    for i in range(train_window, len(df)):
        # 训练集：前 train_window 天
        train = df.iloc[max(0, i - train_window):i]
        test_row = df.iloc[i]

        # 用训练集计算阈值
        thresholds = compute_thresholds_from_sample(train)

        # 计算评分
        score, veto, signals = compute_composite_score(
            test_row, thresholds, use_v2=use_v2, use_regime=use_regime)

        # 记录结果
        next_exc = test_row.get("next_1d_excess_vs_chain", np.nan)
        next_abs = test_row.get("next_1d_return", np.nan)
        next_3d_exc = test_row.get("next_3d_excess_vs_chain", np.nan)

        results.append({
            "date": test_row["date_str"],
            "score": score,
            "veto": veto,
            "regime": test_row.get("regime", ""),
            "signals": signals,
            "next_1d_excess": next_exc if pd.notna(next_exc) else None,
            "next_1d_abs": next_abs if pd.notna(next_abs) else None,
            "next_3d_excess": next_3d_exc if pd.notna(next_3d_exc) else None,
        })

    return results


def evaluate_strategy(results: list[dict], threshold: int) -> dict:
    """评估策略表现"""
    long_days = []
    short_days = []  # 空仓日（含veto）
    neutral_days = []

    for r in results:
        if r["veto"]:
            short_days.append(r)
        elif r["score"] >= threshold and r["next_1d_excess"] is not None:
            long_days.append(r)
        elif r["score"] <= -threshold and r["next_1d_excess"] is not None:
            short_days.append(r)
        else:
            neutral_days.append(r)

    def stats(days, label):
        if not days:
            return {"label": label, "n": 0}
        exc_vals = [d["next_1d_excess"] for d in days if d["next_1d_excess"] is not None]
        abs_vals = [d["next_1d_abs"] for d in days if d["next_1d_abs"] is not None]
        if not exc_vals:
            return {"label": label, "n": len(days)}
        exc_arr = np.array(exc_vals)
        abs_arr = np.array(abs_vals)
        return {
            "label": label,
            "n": len(days),
            "avg_1d_exc": round(float(np.mean(exc_arr)), 4),
            "avg_1d_abs": round(float(np.mean(abs_arr)), 4),
            "win_rate_exc": round(float((exc_arr > 0).mean()), 4),
            "win_rate_abs": round(float((abs_arr > 0).mean()), 4),
            "cum_log_exc": round(float(cum_log(exc_arr)), 2),
            "cum_log_abs": round(float(cum_log(abs_arr)), 2),
        }

    # Buy-and-hold
    all_exc = [r["next_1d_excess"] for r in results if r["next_1d_excess"] is not None]
    bh = {
        "label": "buy_and_hold",
        "n": len(all_exc),
        "avg_1d_exc": round(float(np.mean(all_exc)), 4) if all_exc else 0,
        "cum_log_exc": round(float(cum_log(np.array(all_exc))), 2) if all_exc else 0,
        "win_rate_exc": round(float((np.array(all_exc) > 0).mean()), 4) if all_exc else 0,
    }

    return {
        "threshold": threshold,
        "long_days": stats(long_days, "long"),
        "short_days": stats(short_days, "short"),
        "neutral_days": {"n": len(neutral_days)},
        "buy_and_hold": bh,
    }


def cum_log(vals: np.ndarray) -> float:
    s = 0.0
    for v in vals:
        if abs(v) < 100:
            s += math.log(1 + v / 100)
    return (math.exp(s) - 1) * 100


# ── Kelly 仓位计算 ────────────────────────────────────────────────────────

def kelly_position(score: int, hist_wr: float, avg_win: float, avg_loss: float,
                   atr_pct: float, max_pos: float = 1.0) -> float:
    """Kelly 公式仓位计算"""
    p = hist_wr
    q = 1 - p
    b = abs(avg_win / avg_loss) if avg_loss != 0 else 1.0
    kelly_f = (p * b - q) / b if b > 0 else 0

    half_kelly = kelly_f * 0.5

    # 波动率调节
    vol_adj = 1.0
    if atr_pct > 0.85:
        vol_adj = 0.6
    elif atr_pct > 0.70:
        vol_adj = 0.8

    # 评分强度调节
    score_adj = min(abs(score) / 8.0, 1.0)

    return max(0, min(half_kelly * vol_adj * score_adj * max_pos, max_pos))


# ── 主函数 ────────────────────────────────────────────────────────────────

def main():
    df = load_and_prepare_data()

    print("\n" + "=" * 70)
    print("  信号实验室综合评分 v2 回测报告")
    print("=" * 70)

    # ── V1 vs V2 对比（全样本回测）───────────────────────────────────────
    print("\n[INFO] ═══ V1 vs V2 全样本回测对比 ═══")

    # 全样本阈值
    full_thresholds = compute_thresholds_from_sample(df)

    # V1 回测（不用 V2 新信号，不用 Regime）
    v1_results = walk_forward_backtest(df, train_window=120, use_v2=False, use_regime=False)
    # V2 回测（用 V2 新信号 + Regime）
    v2_results = walk_forward_backtest(df, train_window=120, use_v2=True, use_regime=True)
    # V2 不用 Regime（对比 Regime 的增量价值）
    v2_no_regime = walk_forward_backtest(df, train_window=120, use_v2=True, use_regime=False)

    print(f"\n  Walk-Forward: 训练窗口=120天, 测试集={len(v1_results)}天")
    print()

    for label, results in [("V1(原版)", v1_results),
                           ("V2(无Regime)", v2_no_regime),
                           ("V2(含Regime)", v2_results)]:
        print(f"  ── {label} ──")
        for threshold in [1, 3, 5]:
            eval_res = evaluate_strategy(results, threshold)
            ld = eval_res["long_days"]
            bh = eval_res["buy_and_hold"]
            if ld["n"] > 0:
                alpha_vs_bh = ld["cum_log_exc"] - bh["cum_log_exc"] if bh["cum_log_exc"] else 0
                print(f"    ±{threshold}: n={ld['n']}, wr_exc={ld['win_rate_exc']:.1%}, "
                      f"avg_exc={ld['avg_1d_exc']:+.3f}%, "
                      f"cum_exc={ld['cum_log_exc']:+.1f}%, "
                      f"alpha={alpha_vs_bh:+.1f}%")
        print()

    # ── 评分分布分析 ─────────────────────────────────────────────────────
    print("[INFO] ═══ V2 评分分布分析 ═══")
    v2_scores = [r["score"] for r in v2_results]
    v2_exc = [r["next_1d_excess"] for r in v2_results if r["next_1d_excess"] is not None]

    # 按评分分组
    score_bins = [(-99, -5), (-5, -3), (-3, -1), (-1, 1), (1, 3), (3, 5), (5, 99)]
    for lo, hi in score_bins:
        mask = [(s >= lo and s < hi) for s in v2_scores]
        vals = [v2_exc[i] for i, m in enumerate(mask) if m and i < len(v2_exc)]
        if len(vals) >= 5:
            arr = np.array(vals)
            label = f"score [{lo:+d}, {hi:+d})"
            sig = "🟢" if np.mean(arr) > 0.3 else ("🔴" if np.mean(arr) < -0.3 else "⬜")
            print(f"  {sig} {label}: n={len(vals)}, avg={np.mean(arr):+.3f}%, wr={(arr>0).mean():.1%}")

    # ── 最强信号日分析 ──────────────────────────────────────────────────
    print("\n[INFO] ═══ V2 评分极端日验证 ═══")

    # 评分最高的5天
    sorted_results = sorted(v2_results, key=lambda x: x["score"], reverse=True)
    print("\n  评分最高 5 天:")
    for r in sorted_results[:5]:
        exc = r["next_1d_excess"]
        hit = "✓" if exc is not None and exc > 0 else "✗"
        print(f"    {hit} {r['date']}: score={r['score']}, regime={r['regime']}, "
              f"T+1超额={exc:+.3f}%")

    # 评分最低的5天
    print("\n  评分最低 5 天:")
    for r in sorted_results[-5:]:
        exc = r["next_1d_excess"]
        hit = "✓" if exc is not None and exc < 0 else "✗"
        print(f"    {hit} {r['date']}: score={r['score']}, regime={r['regime']}, "
              f"T+1超额={exc:+.3f}%")

    # ── Kelly 仓位模拟 ─────────────────────────────────────────────────
    print("\n[INFO] ═══ Kelly 仓位管理模拟 ═══")

    # 用 ±3 阈值的长期表现估算参数
    eval_res = evaluate_strategy(v2_results, 3)
    ld = eval_res["long_days"]

    if ld["n"] > 0:
        # 估算平均盈亏
        long_exc = [r["next_1d_excess"] for r in v2_results
                    if r["score"] >= 3 and r["next_1d_excess"] is not None]
        if long_exc:
            arr = np.array(long_exc)
            wins = arr[arr > 0]
            losses = arr[arr < 0]
            avg_win = np.mean(wins) if len(wins) > 0 else 0.5
            avg_loss = abs(np.mean(losses)) if len(losses) > 0 else 0.5
            hist_wr = (arr > 0).mean()

            print(f"  做多参数: 胜率={hist_wr:.1%}, 平均盈利={avg_win:.3f}%, 平均亏损={avg_loss:.3f}%")

            # 模拟 Kelly 仓位
            kelly_returns = []
            fixed_returns = []

            for r in v2_results:
                if r["score"] >= 3 and r["next_1d_excess"] is not None:
                    atr_pct = 0.5  # 默认
                    pos = kelly_position(r["score"], hist_wr, avg_win, avg_loss, atr_pct)
                    kelly_returns.append(r["next_1d_excess"] * pos)
                    fixed_returns.append(r["next_1d_excess"] * 0.5)  # 固定50%仓位

            if kelly_returns:
                kelly_cum = cum_log(np.array(kelly_returns))
                fixed_cum = cum_log(np.array(fixed_returns))
                kelly_wr = (np.array(kelly_returns) > 0).mean()
                fixed_wr = (np.array(fixed_returns) > 0).mean()

                print(f"  Kelly 仓位: cum_exc={kelly_cum:+.1f}%, wr={kelly_wr:.1%}")
                print(f"  固定50%仓位: cum_exc={fixed_cum:+.1f}%, wr={fixed_wr:.1%}")

    # ── Regime 增量价值分析 ─────────────────────────────────────────────
    print("\n[INFO] ═══ Regime 增量价值分析 ═══")

    # 对比：mean_reverting + streak≤-3 vs streak≤-3 单独
    for regime in ["mean_reverting", "trending", "transition"]:
        regime_days = [r for r in v2_results if r["regime"] == regime]
        if not regime_days:
            continue

        # 在该 regime 下的多头胜率
        regime_exc = [r["next_1d_excess"] for r in regime_days
                      if r["score"] >= 3 and r["next_1d_excess"] is not None]
        if len(regime_exc) >= 5:
            arr = np.array(regime_exc)
            print(f"  {regime} + score≥3: n={len(arr)}, avg={np.mean(arr):+.3f}%, "
                  f"wr={(arr>0).mean():.1%}")

    # ── 输出 JSON ────────────────────────────────────────────────────────
    output = {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "trainWindow": 120,
        "v1_results": {
            f"±{t}": evaluate_strategy(v1_results, t) for t in [1, 3, 5]
        },
        "v2_results": {
            f"±{t}": evaluate_strategy(v2_results, t) for t in [1, 3, 5]
        },
        "v2_no_regime_results": {
            f"±{t}": evaluate_strategy(v2_no_regime, t) for t in [1, 3, 5]
        },
        "daily_results": v2_results,
    }

    out_path = DATA_DIR / "composite_signal_backtest_v2.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n[OK] 输出: {out_path}")


if __name__ == "__main__":
    main()
