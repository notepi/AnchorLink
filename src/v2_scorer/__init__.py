"""
V2 评分引擎

信号计算 + Regime 自适应权重 + Walk-Forward 阈值 + Kelly 仓位 + 持仓建议
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from src.v2_scorer.config import (
    ALPHA_SIGNALS,
    REGIME_MULTIPLIER,
    V1_BUY,
    V1_SELL,
    V2_NEW_BUY,
    V2_NEW_SELL,
)


def parse_signal_labels(s) -> set:
    if pd.isna(s) or s == "[]":
        return set()
    try:
        return set(json.loads(s.replace("'", '"'))) if isinstance(s, str) else set()
    except Exception:
        return set()


def compute_v1_signals(row, thresholds: dict) -> list[tuple[str, int]]:
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

    prev = row.get("prev_state", "")
    today = row.get("today_state", "")
    if prev in ("negative+negative", "negative+neutral") and today in (
            "positive+positive", "positive+negative", "positive+neutral"):
        active.append(("path_弱+弱→中或强", +2))
    if prev == "positive+positive" and today in ("positive+negative", "neutral+negative"):
        active.append(("path_强+强→强+弱", -1))

    return active


def compute_v2_new_signals(row) -> list[tuple[str, int]]:
    active = []
    regime = row.get("regime", "transition")
    out_streak = row.get("outperform_streak", 0)

    if isinstance(out_streak, (int, float)):
        if regime == "mean_reverting" and out_streak <= -3:
            active.append(("mean_reverting+streak≤-3", +5))
        elif regime == "mean_reverting" and out_streak <= -2:
            active.append(("mean_reverting+streak≤-2", +3))
        elif regime == "transition" and out_streak <= -2:
            active.append(("transition+streak≤-2", +3))
        elif regime == "transition" and out_streak >= 2:
            active.append(("transition+streak≥+2", -4))

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

    dow = row.get("dow", -1)
    if dow == 2:
        active.append(("周三效应", +1))
    if dow == 4:
        active.append(("周五效应", -2))
        if pd.notna(adx) and adx < 25:
            active.append(("周五+ADX<25", -3))

    if row.get("liq_sweep_high", False):
        active.append(("LiqSweep高(假突破)", +1))
    if row.get("bearish_fvg", False):
        active.append(("看跌FVG日", -2))
    if row.get("bos_20d_high", False):
        active.append(("BOS创20日新高", -1))

    return active


def apply_regime_multiplier(signal_name: str, weight: int, regime: str) -> int:
    mults = REGIME_MULTIPLIER.get(regime, {})

    if "streak" in signal_name:
        mult = mults.get("streak_buy" if weight > 0 else "streak_sell", 1.0)
    elif signal_name in ("MACD柱状图负", "跌但资金支撑", "缩量阴跌",
                         "excess_5d_P15-", "excess_10d_P15-"):
        mult = mults.get("reversion_buy", 1.0) if weight > 0 else 1.0
    elif signal_name in ("周三效应",):
        mult = mults.get("trend_buy", 1.0)
    else:
        mult = 1.0

    adjusted = round(weight * mult)
    return adjusted if adjusted != 0 else (1 if weight > 0 else -1)


def compute_composite_score(
    row,
    thresholds: dict,
    use_v2: bool = True,
    use_regime: bool = True,
) -> tuple[int, bool, list[str]]:
    v1_active = compute_v1_signals(row, thresholds)

    if use_v2:
        v2_active = compute_v2_new_signals(row)
        all_active = v1_active + v2_active
    else:
        all_active = v1_active

    regime = row.get("regime", "transition") if use_regime else "transition"

    total_score = 0
    signal_names = []
    for name, weight in all_active:
        if use_regime:
            adjusted = apply_regime_multiplier(name, weight, regime)
        else:
            adjusted = weight
        total_score += adjusted
        signal_names.append(f"{name}({adjusted:+d})")

    ar = row.get("anchor_return", 0)
    ae = row.get("amount_expansion_ratio", 1)
    veto = (ar > 1.0 and ae > 1.3)

    return total_score, veto, signal_names


def compute_thresholds_from_sample(sample: pd.DataFrame) -> dict:
    e5 = sample["excess_5d"].dropna()
    e10 = sample["excess_10d"].dropna()

    return {
        "excess_5d_p15": e5.quantile(0.15) if len(e5) > 10 else -4.91,
        "excess_5d_p85": e5.quantile(0.85) if len(e5) > 10 else 6.24,
        "excess_10d_p15": e10.quantile(0.15) if len(e10) > 10 else -6.36,
        "excess_10d_p70": e10.quantile(0.70) if len(e10) > 10 else 4.25,
        "excess_10d_p85": e10.quantile(0.85) if len(e10) > 10 else 7.26,
    }


def kelly_position(
    score: int,
    hist_wr: float,
    avg_win: float,
    avg_loss: float,
    atr_pct: float,
    max_pos: float = 1.0,
) -> float:
    p = hist_wr
    q = 1 - p
    b = abs(avg_win / avg_loss) if avg_loss != 0 else 1.0
    kelly_f = (p * b - q) / b if b > 0 else 0
    half_kelly = kelly_f * 0.5

    vol_adj = 1.0
    if atr_pct > 0.85:
        vol_adj = 0.6
    elif atr_pct > 0.70:
        vol_adj = 0.8

    score_adj = min(abs(score) / 8.0, 1.0)

    return max(0, min(half_kelly * vol_adj * score_adj * max_pos, max_pos))


def determine_hold_period(signals: list[str], regime: str) -> int:
    """根据触发的信号和 Regime 给出持仓建议天数。

    规则来源：analysis_framework.md 5.3 节
    """
    signal_str = " ".join(signals)

    # 最强买入信号：MR + streak<=-3
    if regime == "mean_reverting" and ("streak≤-3" in signal_str or "streak_≤-3" in signal_str):
        return 5
    # 次强买入信号：MR + streak<=-2
    if regime == "mean_reverting" and ("streak≤-2" in signal_str or "streak_≤-2" in signal_str):
        return 3
    # TS + streak<=-2
    if regime == "transition" and ("streak≤-2" in signal_str or "streak_≤-2" in signal_str):
        return 2
    # 卖出信号或 veto
    if "veto" in signal_str or "streak≥+2" in signal_str or "streak_≥+2" in signal_str:
        return 1
    # 默认
    return 1
