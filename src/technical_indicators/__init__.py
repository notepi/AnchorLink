"""
技术指标计算模块

纯计算函数，零 I/O 依赖。所有函数接受 pd.Series，返回 pd.Series。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def calc_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_macd(
    closes: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = closes.ewm(span=fast, min_periods=fast).mean()
    ema_slow = closes.ewm(span=slow, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_bollinger(
    closes: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    middle = closes.rolling(period).mean()
    std = closes.rolling(period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    bandwidth = (upper - lower) / middle.replace(0, np.nan)
    pct_b = (closes - lower) / (upper - lower).replace(0, np.nan)
    return upper, middle, lower, bandwidth, pct_b


def calc_adx(
    highs: pd.Series,
    lows: pd.Series,
    closes: pd.Series,
    period: int = 14,
) -> pd.Series:
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


def calc_stochastic(
    highs: pd.Series,
    lows: pd.Series,
    closes: pd.Series,
    k_period: int = 14,
    d_period: int = 3,
) -> tuple[pd.Series, pd.Series]:
    lowest_low = lows.rolling(k_period).min()
    highest_high = highs.rolling(k_period).max()
    k = 100 * (closes - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    return k, d


def calc_atr(
    highs: pd.Series,
    lows: pd.Series,
    closes: pd.Series,
    period: int = 14,
) -> pd.Series:
    tr1 = highs - lows
    tr2 = (highs - closes.shift(1)).abs()
    tr3 = (lows - closes.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period).mean()


def calc_squeeze(
    closes: pd.Series,
    atr: pd.Series,
    bb_lower: pd.Series,
    bb_upper: pd.Series,
    kc_span: int = 20,
) -> pd.Series:
    kc_mid = closes.ewm(span=kc_span, min_periods=kc_span).mean()
    kc_upper = kc_mid + 1.5 * atr
    kc_lower = kc_mid - 1.5 * atr
    return (bb_lower > kc_lower) & (bb_upper < kc_upper)


def compute_smc_patterns(
    highs: pd.Series,
    lows: pd.Series,
    closes: pd.Series,
    window: int = 20,
    fvg_threshold_pct: float = 0.3,
) -> pd.DataFrame:
    n = len(closes)
    liq_sweep_high = (highs > highs.shift(1)) & (closes < highs.shift(1))
    n_day_high = closes.rolling(window).max()
    bos_20d_high = closes >= n_day_high
    n_day_low = closes.rolling(window).min()
    bos_20d_low = closes <= n_day_low
    choch_up = bos_20d_low.shift(1) & (closes > closes.shift(1))

    bearish_fvg = pd.Series(False, index=closes.index)
    for i in range(1, n - 1):
        gap_down = lows.iloc[i - 1] - highs.iloc[i + 1]
        if gap_down > 0 and (gap_down / lows.iloc[i - 1]) * 100 >= fvg_threshold_pct:
            bearish_fvg.iloc[i] = True

    return pd.DataFrame({
        "liq_sweep_high": liq_sweep_high,
        "bos_20d_high": bos_20d_high,
        "bos_20d_low": bos_20d_low,
        "choch_up": choch_up,
        "bearish_fvg": bearish_fvg,
    })


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """生产入口：接受含 [close, high, low] 列的 DataFrame，追加所有指标列后返回。"""
    c = df["close"]
    h = df["high"]
    l = df["low"]

    df = df.copy()
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

    atr = calc_atr(h, l, c, 14)
    df["atr_14"] = atr

    df["squeeze_on"] = calc_squeeze(c, atr, bb_lower, bb_upper)

    smc = compute_smc_patterns(h, l, c)
    for col in smc.columns:
        df[col] = smc[col]

    return df
