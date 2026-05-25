#!/usr/bin/env python3
"""
V2 评分计算（管道步骤 3.5）

位于 build_history_analysis.py 之后、build_dashboard_view.py 之前。
输入：OHLCV + history CSVs → 输出：data/output/v2_scoring.json
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.regime_detector import RegimeInfo, classify_regime
from src.technical_indicators import compute_all_indicators
from src.v2_scorer import (
    ALPHA_SIGNALS,
    compute_composite_score,
    compute_thresholds_from_sample,
    compute_v1_signals,
    compute_v2_new_signals,
    determine_hold_period,
    kelly_position,
    parse_signal_labels,
    apply_regime_multiplier,
)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "output"
PRICE_DIR = ROOT / "data" / "price" / "normalized"
TRAIN_WINDOW = 120


def cum_log(vals: np.ndarray) -> float:
    s = 0.0
    for v in vals:
        if abs(v) < 100:
            s += math.log(1 + v / 100)
    return (math.exp(s) - 1) * 100


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
    df = compute_all_indicators(df)

    # Regime
    df["regime"] = "transition"
    df.loc[df["adx_14"] >= 25, "regime"] = "trending"
    df.loc[df["adx_14"] <= 20, "regime"] = "mean_reverting"

    # 季节性
    df["dow"] = df["trade_date"].dt.dayofweek
    df["month"] = df["trade_date"].dt.month

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


def evaluate_strategy(results: list[dict], threshold: int) -> dict:
    long_days = []
    short_days = []
    neutral_days = []

    for r in results:
        if r["veto"]:
            short_days.append(r)
        elif r["score"] >= threshold and r["next1dExcess"] is not None:
            long_days.append(r)
        elif r["score"] <= -threshold and r["next1dExcess"] is not None:
            short_days.append(r)
        else:
            neutral_days.append(r)

    def stats(days, label):
        if not days:
            return {"label": label, "n": 0}
        exc_vals = [d["next1dExcess"] for d in days if d["next1dExcess"] is not None]
        abs_vals = [d["next1dAbs"] for d in days if d["next1dAbs"] is not None]
        if not exc_vals:
            return {"label": label, "n": len(days)}
        exc_arr = np.array(exc_vals)
        abs_arr = np.array(abs_vals)
        return {
            "label": label,
            "n": len(days),
            "avg1dExc": round(float(np.mean(exc_arr)), 4),
            "avg1dAbs": round(float(np.mean(abs_arr)), 4),
            "winRateExc": round(float((exc_arr > 0).mean()), 4),
            "winRateAbs": round(float((abs_arr > 0).mean()), 4),
            "cumLogExc": round(float(cum_log(exc_arr)), 2),
            "cumLogAbs": round(float(cum_log(abs_arr)), 2),
        }

    all_exc = [r["next1dExcess"] for r in results if r["next1dExcess"] is not None]
    bh = {
        "label": "buy_and_hold",
        "n": len(all_exc),
        "avg1dExc": round(float(np.mean(all_exc)), 4) if all_exc else 0,
        "cumLogExc": round(float(cum_log(np.array(all_exc))), 2) if all_exc else 0,
        "winRateExc": round(float((np.array(all_exc) > 0).mean()), 4) if all_exc else 0,
    }

    return {
        "threshold": threshold,
        "longDays": stats(long_days, "long"),
        "shortDays": stats(short_days, "short"),
        "neutralDays": {"n": len(neutral_days)},
        "buyAndHold": bh,
    }


def build_signal_breakdown(row, thresholds: dict, use_regime: bool = True) -> list[dict]:
    """构建详细的信号分解（含 rawWeight/adjustedWeight/category）"""
    v1_active = compute_v1_signals(row, thresholds)
    v2_active = compute_v2_new_signals(row)
    all_active = v1_active + v2_active

    regime = row.get("regime", "transition") if use_regime else "transition"
    breakdown = []

    v1_names = set(dict(v1_active).keys())
    for name, raw_weight in all_active:
        if use_regime:
            adjusted = apply_regime_multiplier(name, raw_weight, regime)
        else:
            adjusted = raw_weight
        category = "v1" if name in v1_names else "v2_new"
        breakdown.append({
            "signal": name,
            "rawWeight": raw_weight,
            "adjustedWeight": adjusted,
            "category": category,
        })

    return breakdown


def walk_forward_backtest(df: pd.DataFrame) -> list[dict]:
    print(f"[INFO] Walk-Forward 回测: 训练窗口={TRAIN_WINDOW}天...")
    results = []

    for i in range(TRAIN_WINDOW, len(df)):
        train = df.iloc[max(0, i - TRAIN_WINDOW):i]
        test_row = df.iloc[i]

        thresholds = compute_thresholds_from_sample(train)
        score, veto, signal_names = compute_composite_score(test_row, thresholds)

        regime_info = classify_regime(test_row.get("adx_14"))
        breakdown = build_signal_breakdown(test_row, thresholds)

        next_exc = test_row.get("next_1d_excess_vs_chain", np.nan)
        next_abs = test_row.get("next_1d_return", np.nan)

        # 技术指标摘要
        ti = test_row
        technical_indicators = {
            "rsi14": round(float(ti.get("rsi_14", np.nan)), 2) if pd.notna(ti.get("rsi_14")) else None,
            "macdHist": round(float(ti.get("macd_hist", np.nan)), 4) if pd.notna(ti.get("macd_hist")) else None,
            "stochK": round(float(ti.get("stoch_k", np.nan)), 2) if pd.notna(ti.get("stoch_k")) else None,
            "bbPctb": round(float(ti.get("bb_pctb", np.nan)), 4) if pd.notna(ti.get("bb_pctb")) else None,
            "adx14": round(float(ti.get("adx_14", np.nan)), 2) if pd.notna(ti.get("adx_14")) else None,
            "atr14": round(float(ti.get("atr_14", np.nan)), 2) if pd.notna(ti.get("atr_14")) else None,
            "squeezeOn": bool(ti.get("squeeze_on", False)) if pd.notna(ti.get("squeeze_on")) else None,
        }

        results.append({
            "date": test_row["date_str"],
            "score": score,
            "veto": veto,
            "regime": regime_info.regime,
            "thresholdBuy": regime_info.thresholdBuy,
            "thresholdSell": regime_info.thresholdSell,
            "signals": signal_names,
            "signalBreakdown": breakdown,
            "kellyPosition": None,  # 后面算
            "holdPeriodDays": determine_hold_period(signal_names, regime_info.regime),
            "technicalIndicators": technical_indicators,
            "next1dExcess": round(float(next_exc), 4) if pd.notna(next_exc) else None,
            "next1dAbs": round(float(next_abs), 4) if pd.notna(next_abs) else None,
        })

    # 计算 Kelly 仓位（需要全局统计）
    long_exc = [r["next1dExcess"] for r in results
                if r["score"] >= 3 and r["next1dExcess"] is not None]
    if long_exc:
        arr = np.array(long_exc)
        wins = arr[arr > 0]
        losses = arr[arr < 0]
        avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.5
        avg_loss = abs(float(np.mean(losses))) if len(losses) > 0 else 0.5
        hist_wr = float((arr > 0).mean())

        for r in results:
            atr_val = r["technicalIndicators"].get("atr14")
            atr_pct = (atr_val / 50) if atr_val else 0.5  # 近似
            r["kellyPosition"] = round(
                kelly_position(r["score"], hist_wr, avg_win, avg_loss, atr_pct), 3
            )

    print(f"[OK] 回测完成: {len(results)} 天")
    return results


def main():
    df = load_and_prepare_data()

    daily_results = walk_forward_backtest(df)

    # 策略表现
    strategy_results = {}
    for threshold in [3, 5]:
        key = f"±{threshold}"
        strategy_results[key] = evaluate_strategy(daily_results, threshold)

    # 最新 Regime
    latest = daily_results[-1] if daily_results else {}
    latest_regime_info = classify_regime(latest.get("technicalIndicators", {}).get("adx14"))
    hold_guidance_map = {
        "mean_reverting": "MR环境：score>=3做多，2-5天持仓",
        "trending": "趋势环境：score>=4做多，1天持仓",
        "transition": "过渡环境：score>=4做多，2天持仓",
    }

    output = {
        "generatedAt": datetime.now().strftime("%Y%m%d"),
        "trainWindow": TRAIN_WINDOW,
        "regimeThresholds": {
            "mean_reverting": 3,
            "trending": 4,
            "transition": 4,
        },
        "strategyResults": strategy_results,
        "dailyResults": daily_results,
        "latestRegime": {
            "regime": latest_regime_info.regime,
            "adx": latest.get("technicalIndicators", {}).get("adx14"),
            "thresholdBuy": latest_regime_info.thresholdBuy,
            "thresholdSell": latest_regime_info.thresholdSell,
            "holdPeriodGuidance": hold_guidance_map.get(latest_regime_info.regime, ""),
        },
    }

    out_path = DATA_DIR / "v2_scoring.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"[OK] 输出: {out_path}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("  V2 评分系统摘要")
    print("=" * 60)
    print(f"  最新日期: {latest.get('date', 'N/A')}")
    print(f"  Regime: {latest_regime_info.regime} (ADX={latest.get('technicalIndicators', {}).get('adx14', 'N/A')})")
    print(f"  评分: {latest.get('score', 'N/A')}")
    print(f"  Veto: {latest.get('veto', False)}")
    print(f"  做多阈值: >= {latest_regime_info.thresholdBuy}")
    print(f"  做空阈值: <= {latest_regime_info.thresholdSell}")
    print(f"  持仓建议: {latest.get('holdPeriodDays', 1)} 天")
    print()

    # 策略表现
    for key, res in strategy_results.items():
        ld = res.get("longDays", {})
        if ld.get("n", 0) > 0:
            print(f"  {key}: n={ld['n']}, wr={ld['winRateExc']:.1%}, "
                  f"avg_exc={ld['avg1dExc']:+.3f}%, cum={ld['cumLogExc']:+.1f}%")

    print("=" * 60)


if __name__ == "__main__":
    main()
