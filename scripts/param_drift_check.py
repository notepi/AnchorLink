"""
参数漂移检测
============

对比 V2 评分系统中的硬编码参数与当前数据重新校准的结果，
输出差异报告，超阈值告警。

检测项：
  A. 百分位阈值漂移 — config fallback 值 vs 当前数据实际百分位
  B. 信号权重漂移 — 各信号最近 60 天 vs 全样本命中率差异
  C. Regime 分布漂移 — 最近 60 天 vs 全样本 regime 分布差异
  D. 策略整体漂移 — 最近 60 天 V2 保守策略胜率 vs 回测期胜率

输入：
  - data/output/history_rolling_metrics.csv
  - data/output/v2_scoring.json
  - data/output/composite_signal_backtest.json

输出：
  - data/output/param_drift_report.json
  - 控制台摘要
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

from src.v2_scorer import compute_thresholds_from_sample
from src.v2_scorer.config import REGIME_MULTIPLIER

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "output"

ROLLING_CSV = DATA_DIR / "history_rolling_metrics.csv"
V2_SCORING_JSON = DATA_DIR / "v2_scoring.json"
BACKTEST_JSON = DATA_DIR / "composite_signal_backtest.json"
OUTPUT_JSON = DATA_DIR / "param_drift_report.json"

# config.py 中的 fallback 值（硬编码基准）
CONFIG_FALLBACKS = {
    "excess_5d_p15": -4.91,
    "excess_5d_p85": 6.24,
    "excess_10d_p15": -6.36,
    "excess_10d_p70": 4.25,
    "excess_10d_p85": 7.26,
}

# V2 保守策略回测基准胜率（来自 signal_lab_research.md）
BACKTEST_WIN_RATE = 0.613

RECENT_WINDOW = 60

# 告警阈值
THRESHOLD_PCT_DEVIATION = 0.20  # 百分位值偏离 20%
THRESHOLD_HIT_RATE_DROP = 0.15  # 命中率下降 15pp
THRESHOLD_WIN_RATE_DROP = 0.10  # 策略胜率下降 10pp
THRESHOLD_CHI2_PVALUE = 0.05    # 卡方检验 p 值


def safe_float(v):
    try:
        if v is None or v == "":
            return None
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def chi2_test(observed: list[int], expected: list[int]) -> float:
    """简易卡方检验，返回 p 值近似。"""
    chi2 = 0.0
    for o, e in zip(observed, expected):
        if e > 0:
            chi2 += (o - e) ** 2 / e
    df = max(len(observed) - 1, 1)
    # 用 gamma 近似 p 值（避免 scipy 依赖）
    x = chi2 / 2.0
    k = df / 2.0
    # 不完全 gamma 函数近似（Wilson-Hilferty）
    if df > 0:
        z = ((chi2 / df) ** (1 / 3) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
        # 标准正态 CDF 近似
        p = 0.5 * (1 + math.erf(-z / math.sqrt(2)))
        return max(p, 0.0)
    return 1.0


def check_percentile_thresholds(rolling_df: pd.DataFrame) -> dict:
    """A. 百分位阈值漂移检测"""
    current = compute_thresholds_from_sample(rolling_df)
    details = []
    drift = False

    for param, config_val in CONFIG_FALLBACKS.items():
        current_val = current.get(param, config_val)
        # 偏差 = |current - config| / |config|
        if config_val != 0:
            deviation = abs(current_val - config_val) / abs(config_val)
        else:
            deviation = abs(current_val - config_val)

        is_drift = deviation > THRESHOLD_PCT_DEVIATION
        if is_drift:
            drift = True

        details.append({
            "param": param,
            "configValue": round(config_val, 4),
            "currentValue": round(current_val, 4),
            "deviation": f"{deviation:.1%}",
            "deviationRaw": round(deviation, 4),
            "drift": is_drift,
        })

    return {"drift": drift, "details": details}


def check_signal_hit_rates(backtest_json: dict) -> dict:
    """B. 信号权重漂移检测 — 各信号最近 N 天 vs 全样本命中率"""
    daily = backtest_json.get("daily_results", [])
    if not daily:
        return {"drift": False, "details": [], "note": "无 daily_results 数据"}

    n = len(daily)
    recent_start = max(0, n - RECENT_WINDOW)
    full_data = daily
    recent_data = daily[recent_start:]

    # 收集每个信号在各时段的触发及对应 T+1 方向
    signal_full_hits = Counter()  # signal -> (positive outcomes)
    signal_full_total = Counter()
    signal_recent_hits = Counter()
    signal_recent_total = Counter()

    for d in full_data:
        exc = safe_float(d.get("next_1d_excess"))
        if exc is None:
            continue
        for sig in d.get("signals", []):
            signal_full_total[sig] += 1
            if exc > 0:
                signal_full_hits[sig] += 1

    for d in recent_data:
        exc = safe_float(d.get("next_1d_excess"))
        if exc is None:
            continue
        for sig in d.get("signals", []):
            signal_recent_total[sig] += 1
            if exc > 0:
                signal_recent_hits[sig] += 1

    details = []
    drift = False
    all_signals = set(signal_full_total.keys()) | set(signal_recent_total.keys())

    for sig in sorted(all_signals):
        f_total = signal_full_total[sig]
        f_hits = signal_full_hits[sig]
        r_total = signal_recent_total[sig]
        r_hits = signal_recent_hits[sig]

        full_rate = f_hits / f_total if f_total > 0 else None
        recent_rate = r_hits / r_total if r_total > 0 else None

        if full_rate is not None and recent_rate is not None and r_total >= 5:
            drop = full_rate - recent_rate
            is_drift = drop > THRESHOLD_HIT_RATE_DROP
            if is_drift:
                drift = True
            details.append({
                "signal": sig,
                "fullSampleHitRate": round(full_rate, 3),
                "fullSampleN": f_total,
                "recentHitRate": round(recent_rate, 3),
                "recentN": r_total,
                "drop": f"{drop:.1%}" if drop > 0 else f"{drop:.1%}",
                "dropRaw": round(drop, 4),
                "drift": is_drift,
            })

    return {"drift": drift, "details": details}


def check_regime_distribution(v2_scoring_json: dict) -> dict:
    """C. Regime 分布漂移检测"""
    daily = v2_scoring_json.get("dailyResults", [])
    if not daily:
        return {"drift": False, "details": {}, "note": "无 dailyResults 数据"}

    n = len(daily)
    recent_start = max(0, n - RECENT_WINDOW)

    regimes = ["mean_reverting", "trending", "transition"]

    full_counts = Counter(d.get("regime", "unknown") for d in daily)
    recent_counts = Counter(d.get("regime", "unknown") for d in daily[recent_start:])

    full_total = sum(full_counts.get(r, 0) for r in regimes)
    recent_total = sum(recent_counts.get(r, 0) for r in regimes)

    if full_total == 0 or recent_total == 0:
        return {"drift": False, "details": {}, "note": "数据不足"}

    # 期望频次：用全样本比例 × 近期总量
    expected = [full_counts.get(r, 0) / full_total * recent_total for r in regimes]
    observed = [recent_counts.get(r, 0) for r in regimes]

    p_value = chi2_test(observed, expected)

    drift = p_value < THRESHOLD_CHI2_PVALUE

    full_dist = {r: round(full_counts.get(r, 0) / full_total, 3) for r in regimes}
    recent_dist = {r: round(recent_counts.get(r, 0) / recent_total, 3) for r in regimes}

    return {
        "drift": drift,
        "details": {
            "chi2PValue": round(p_value, 4),
            "fullDistribution": full_dist,
            "recentDistribution": recent_dist,
            "fullTotal": full_total,
            "recentTotal": recent_total,
        },
    }


def check_strategy_performance(v2_scoring_json: dict) -> dict:
    """D. 策略整体漂移检测 — V2 保守策略近 N 天胜率"""
    daily = v2_scoring_json.get("dailyResults", [])
    if not daily:
        return {"drift": False, "details": {}, "note": "无 dailyResults 数据"}

    # V2 保守：MR>=3, TR/TS>=4 做多
    regime_thresholds = v2_scoring_json.get("regimeThresholds", {})
    mr_threshold = regime_thresholds.get("mean_reverting", 3)

    n = len(daily)
    recent_start = max(0, n - RECENT_WINDOW)
    recent = daily[recent_start:]

    # 全样本做多胜率
    full_long = [
        d for d in daily
        if d.get("score", 0) >= mr_threshold
        and not d.get("veto", False)
        and safe_float(d.get("next1dExc")) is not None
    ]
    # 近期做多胜率
    recent_long = [
        d for d in recent
        if d.get("score", 0) >= mr_threshold
        and not d.get("veto", False)
        and safe_float(d.get("next1dExc")) is not None
    ]

    def win_rate(entries):
        if not entries:
            return None
        wins = sum(1 for d in entries if safe_float(d.get("next1dExc", 0)) > 0)
        return wins / len(entries)

    full_wr = win_rate(full_long)
    recent_wr = win_rate(recent_long)

    # 也用 strategyResults 中的全量胜率
    sr = v2_scoring_json.get("strategyResults", {})
    strat_key = f"±{mr_threshold}"
    baseline_wr = sr.get(strat_key, {}).get("longDays", {}).get("winRateExc")
    if baseline_wr is None:
        baseline_wr = BACKTEST_WIN_RATE

    if recent_wr is not None and full_wr is not None:
        drop = baseline_wr - recent_wr
        drift = drop > THRESHOLD_WIN_RATE_DROP
    else:
        drop = 0.0
        drift = False

    return {
        "drift": drift,
        "details": {
            "backtestWinRate": round(baseline_wr, 3),
            "fullSampleWinRate": round(full_wr, 3) if full_wr is not None else None,
            "recentWinRate": round(recent_wr, 3) if recent_wr is not None else None,
            "recentN": len(recent_long),
            "drop": f"{drop:.1%}" if drop > 0 else f"{drop:.1%}",
            "dropRaw": round(drop, 4) if drop else 0,
        },
    }


def main():
    print("=" * 60)
    print("  参数漂移检测")
    print("=" * 60)

    # 加载数据
    rolling_df = pd.read_csv(ROLLING_CSV)
    print(f"[INFO] rolling_metrics: {len(rolling_df)} 行")

    with open(V2_SCORING_JSON, encoding="utf-8") as f:
        v2_data = json.load(f)
    print(f"[INFO] v2_scoring: {len(v2_data.get('dailyResults', []))} 天")

    with open(BACKTEST_JSON, encoding="utf-8") as f:
        backtest_data = json.load(f)
    print(f"[INFO] backtest: {len(backtest_data.get('daily_results', []))} 天")

    # 四项检测
    check_a = check_percentile_thresholds(rolling_df)
    check_b = check_signal_hit_rates(backtest_data)
    check_c = check_regime_distribution(v2_data)
    check_d = check_strategy_performance(v2_data)

    drift_count = sum([check_a["drift"], check_b["drift"], check_c["drift"], check_d["drift"]])
    drift_detected = drift_count > 0

    # 控制台输出
    print()
    label_a = "⚠ 漂移" if check_a["drift"] else "✓ 无显著漂移"
    label_b = "⚠ 漂移" if check_b["drift"] else "✓ 无显著漂移"
    label_c = "⚠ 漂移" if check_c["drift"] else "✓ 无显著漂移"
    label_d = "⚠ 漂移" if check_d["drift"] else "✓ 无显著漂移"

    print(f"  百分位阈值：{label_a}")
    if check_a["drift"]:
        for item in check_a["details"]:
            if item["drift"]:
                print(f"    → {item['param']}: config={item['configValue']} → current={item['currentValue']} (偏差 {item['deviation']})")

    print(f"  信号权重：  {label_b}")
    if check_b["drift"]:
        for item in check_b["details"]:
            if item["drift"]:
                print(f"    → {item['signal']}: 全样本 {item['fullSampleHitRate']:.1%} → 近{RECENT_WINDOW}天 {item['recentHitRate']:.1%} (下降 {item['drop']})")

    print(f"  Regime分布：{label_c}")
    if check_c["drift"]:
        det = check_c["details"]
        print(f"    → 卡方 p={det['chi2PValue']:.4f}")
        print(f"    → 全样本: {det['fullDistribution']}")
        print(f"    → 近期:   {det['recentDistribution']}")

    print(f"  策略整体：  {label_d}")
    det_d = check_d["details"]
    if check_d["drift"]:
        print(f"    → 回测胜率 {det_d['backtestWinRate']:.1%} → 近{RECENT_WINDOW}天 {det_d['recentWinRate']:.1%} (下降 {det_d['drop']})")
    else:
        if det_d.get("recentWinRate") is not None:
            print(f"    → 回测胜率 {det_d['backtestWinRate']:.1%} → 近{RECENT_WINDOW}天 {det_d['recentWinRate']:.1%}")

    print("-" * 60)
    if drift_detected:
        print(f"  ⚠ {drift_count}/4 项检测到漂移，建议重新校准参数")
    else:
        print("  ✓ 4/4 项无显著漂移，当前参数有效")
    print("=" * 60)

    # 生成日期
    gen_date = v2_data.get("generatedAt", "")
    if not gen_date and v2_data.get("dailyResults"):
        gen_date = v2_data["dailyResults"][-1].get("date", "")

    # 输出 JSON
    report = {
        "generatedAt": gen_date,
        "driftDetected": drift_detected,
        "summary": f"{drift_count}/4 项{'检测到漂移' if drift_detected else '无显著漂移'}",
        "checks": {
            "percentileThresholds": check_a,
            "signalWeights": check_b,
            "regimeDistribution": check_c,
            "strategyPerformance": check_d,
        },
    }

    # 输出前确保所有值可 JSON 序列化
    def sanitize(obj):
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize(v) for v in obj]
        if isinstance(obj, (bool, int, float, str, type(None))):
            return obj
        # numpy bool_ / int64 等
        if hasattr(obj, "item"):
            return obj.item()
        return str(obj)

    report = sanitize(report)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 漂移报告写入：{OUTPUT_JSON}  ({OUTPUT_JSON.stat().st_size / 1024:.1f} KB)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
