"""
V2 参数自动校准
================

从 v2_scoring.json 的 dailyResults 中统计各信号命中率，
重新映射权重、校准 Regime 乘数、更新百分位 fallback、网格搜索入场阈值。

半自动模式：
  - 默认：只输出报告和对比表
  - --apply：更新 config.py 并备份旧配置

输入：
  - data/output/v2_scoring.json
  - data/output/history_rolling_metrics.csv
  - src/v2_scorer/config.py（当前参数）

输出：
  - data/output/v2_calibration_report.json
  - 控制台对比表
  - --apply 时更新 src/v2_scorer/config.py
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.v2_scorer import compute_thresholds_from_sample
from src.v2_scorer.config import (
    REGIME_MULTIPLIER,
    V1_BUY,
    V1_SELL,
    V2_NEW_BUY,
    V2_NEW_SELL,
)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "output"
CONFIG_PATH = PROJECT_ROOT / "src" / "v2_scorer" / "config.py"
BACKUP_DIR = PROJECT_ROOT / "config"

ROLLING_CSV = DATA_DIR / "history_rolling_metrics.csv"
V2_SCORING_JSON = DATA_DIR / "v2_scoring.json"
OUTPUT_JSON = DATA_DIR / "v2_calibration_report.json"

RECENT_WINDOW = 60

# 权重映射规则：命中率 → 权重
# 买入信号
BUY_WEIGHT_MAP = [
    (0.70, +5),
    (0.60, +3),
    (0.50, +1),
]
# 卖出信号（命中 = 实际跌，即 T+1 excess < 0）
SELL_WEIGHT_MAP = [
    (0.70, -5),
    (0.60, -3),
    (0.50, -1),
]
# 命中率 < 50% 的信号无效，权重 = 0

# T+1 超额修正
EXCESS_BUY_BOOST = 2.0   # 买入信号超额 > 2% → 权重 +1
EXCESS_SELL_BOOST = -1.0  # 卖出信号超额 < -1% → 权重 -1

# 入场阈值搜索范围
THRESHOLD_RANGE = range(2, 7)
THRESHOLD_MIN_TRADES = 10

# Regime 乘数边界
MULT_MIN = 0.5
MULT_MAX = 2.0
MULT_STEP = 0.1


def safe_float(v):
    try:
        if v is None or v == "":
            return None
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def is_veto(dr: dict) -> bool:
    """处理 veto 字段可能是 bool 或 str 的情况。"""
    v = dr.get("veto", False)
    if isinstance(v, bool):
        return v
    return str(v).lower() == "true"


# ── 1. 统计信号表现 ──────────────────────────────────────────────────────────

def compute_signal_stats(daily_results: list[dict]) -> dict:
    """统计每个信号的命中率、平均超额、按 regime 分组表现。"""
    stats = defaultdict(lambda: {
        "full_hits": 0, "full_total": 0, "full_excess_sum": 0.0,
        "recent_hits": 0, "recent_total": 0, "recent_excess_sum": 0.0,
        "by_regime": defaultdict(lambda: {"hits": 0, "total": 0, "excess_sum": 0.0}),
        "category": "v1",
        "raw_weight": 0,
    })

    n = len(daily_results)
    recent_start = max(0, n - RECENT_WINDOW)

    for idx, dr in enumerate(daily_results):
        exc = safe_float(dr.get("next1dExcess"))
        if exc is None:
            continue
        regime = dr.get("regime", "transition")
        is_recent = idx >= recent_start

        for sb in dr.get("signalBreakdown", []):
            sig = sb["signal"]
            raw_w = sb.get("rawWeight", 0)
            cat = sb.get("category", "v1")
            is_buy = raw_w > 0

            hit = (exc > 0) if is_buy else (exc < 0)

            s = stats[sig]
            s["full_total"] += 1
            s["full_excess_sum"] += exc
            if hit:
                s["full_hits"] += 1
            s["category"] = cat
            s["raw_weight"] = raw_w

            s["by_regime"][regime]["total"] += 1
            s["by_regime"][regime]["excess_sum"] += exc
            if hit:
                s["by_regime"][regime]["hits"] += 1

            if is_recent:
                s["recent_total"] += 1
                s["recent_excess_sum"] += exc
                if hit:
                    s["recent_hits"] += 1

    return dict(stats)


# ── 2. 权重映射 ──────────────────────────────────────────────────────────────

def map_weight(hit_rate: float, avg_excess: float, is_buy: bool) -> int:
    """从命中率和平均超额映射为权重。"""
    weight_map = BUY_WEIGHT_MAP if is_buy else SELL_WEIGHT_MAP
    excess_boost = EXCESS_BUY_BOOST if is_buy else EXCESS_SELL_BOOST

    weight = 0
    for threshold, w in weight_map:
        if hit_rate >= threshold:
            weight = w
            break

    # 超额修正
    if is_buy and avg_excess > excess_boost:
        weight += 1
    elif not is_buy and avg_excess < excess_boost:
        weight -= 1

    # 买入权重最低 0，卖出权重最高 0
    if is_buy:
        weight = max(weight, 0)
    else:
        weight = min(weight, 0)

    return weight


def calibrate_signal_weights(signal_stats: dict) -> dict:
    """重新校准所有信号权重。"""
    current_weights = {}
    current_weights.update(V1_BUY)
    current_weights.update(V1_SELL)
    current_weights.update(V2_NEW_BUY)
    current_weights.update(V2_NEW_SELL)

    results = {}
    for sig, s in signal_stats.items():
        is_buy = s["raw_weight"] > 0
        current_w = current_weights.get(sig, 0)

        # 优先用近期数据，样本不足则用全样本
        if s["recent_total"] >= 10:
            hit_rate = s["recent_hits"] / s["recent_total"]
            avg_exc = s["recent_excess_sum"] / s["recent_total"]
            sample = "recent"
        elif s["full_total"] >= 10:
            hit_rate = s["full_hits"] / s["full_total"]
            avg_exc = s["full_excess_sum"] / s["full_total"]
            sample = "full"
        else:
            # 样本不足，保持当前权重
            results[sig] = {
                "current": current_w,
                "suggested": current_w,
                "hitRate": None,
                "sampleN": s["full_total"],
                "sample": "insufficient",
                "changed": False,
            }
            continue

        suggested = map_weight(hit_rate, avg_exc, is_buy)
        changed = suggested != current_w

        reason = ""
        if changed:
            if current_w != 0 and suggested == 0:
                reason = "命中率不足，信号失效"
            elif current_w == 0 and suggested != 0:
                reason = "命中率回升，信号恢复"
            elif abs(suggested) > abs(current_w):
                reason = "命中率提升，增强权重"
            else:
                reason = "命中率下降，降低权重"

        results[sig] = {
            "current": current_w,
            "suggested": suggested,
            "hitRate": round(hit_rate, 3),
            "avgExcess": round(avg_exc, 3),
            "sampleN": s["recent_total"] if sample == "recent" else s["full_total"],
            "sample": sample,
            "changed": changed,
            "reason": reason,
        }

    return results


# ── 3. Regime 乘数校准 ───────────────────────────────────────────────────────

def calibrate_regime_multipliers(daily_results: list[dict], signal_stats: dict) -> dict:
    """从各 regime 下信号表现重新校准 Regime 乘数。"""
    # 信号分类
    STREAK_SIGNALS = {"mean_reverting+streak≤-3", "mean_reverting+streak≤-2",
                      "transition+streak≤-2", "transition+streak≥+2",
                      "outperform_streak_≤-3", "outperform_streak_≥+3"}
    REVERSION_SIGNALS = {"excess_5d_P15-", "excess_10d_P15-", "MACD柱状图负",
                         "跌但资金支撑", "缩量阴跌"}
    TREND_SIGNALS = {"周三效应"}

    categories = {
        "streak_buy": lambda sig, w: sig in STREAK_SIGNALS and w > 0,
        "streak_sell": lambda sig, w: sig in STREAK_SIGNALS and w < 0,
        "reversion_buy": lambda sig, w: sig in REVERSION_SIGNALS and w > 0,
        "trend_buy": lambda sig, w: sig in TREND_SIGNALS and w > 0,
    }

    # 按 regime + category 统计命中率
    regime_cat_stats = defaultdict(lambda: {"hits": 0, "total": 0})
    global_cat_stats = defaultdict(lambda: {"hits": 0, "total": 0})

    for dr in daily_results:
        exc = safe_float(dr.get("next1dExcess"))
        if exc is None:
            continue
        regime = dr.get("regime", "transition")

        for sb in dr.get("signalBreakdown", []):
            sig = sb["signal"]
            raw_w = sb.get("rawWeight", 0)
            is_buy = raw_w > 0
            hit = (exc > 0) if is_buy else (exc < 0)

            for cat_name, cat_check in categories.items():
                if cat_check(sig, raw_w):
                    global_cat_stats[cat_name]["total"] += 1
                    if hit:
                        global_cat_stats[cat_name]["hits"] += 1
                    regime_cat_stats[(regime, cat_name)]["total"] += 1
                    if hit:
                        regime_cat_stats[(regime, cat_name)]["hits"] += 1

    # 计算乘数
    results = {}
    for regime in ["mean_reverting", "trending", "transition"]:
        results[regime] = {}
        for cat_name in categories:
            current = REGIME_MULTIPLIER.get(regime, {}).get(cat_name, 1.0)
            g = global_cat_stats[cat_name]
            r = regime_cat_stats.get((regime, cat_name), {"hits": 0, "total": 0})

            if g["total"] >= 10 and r["total"] >= 5:
                base_rate = g["hits"] / g["total"]
                regime_rate = r["hits"] / r["total"]
                if base_rate > 0:
                    raw_mult = regime_rate / base_rate
                    # 量化到 0.1 步长，clip 到 [0.5, 2.0]
                    suggested = round(max(MULT_MIN, min(MULT_MAX, raw_mult)) / MULT_STEP) * MULT_STEP
                    suggested = round(suggested, 1)
                else:
                    suggested = current
            else:
                suggested = current  # 数据不足，保持

            changed = suggested != current
            results[regime][cat_name] = {
                "current": current,
                "suggested": suggested,
                "regimeHitRate": round(r["hits"] / r["total"], 3) if r["total"] > 0 else None,
                "baseHitRate": round(g["hits"] / g["total"], 3) if g["total"] > 0 else None,
                "regimeN": r["total"],
                "changed": changed,
            }

    return results


# ── 4. 百分位 Fallback 校准 ──────────────────────────────────────────────────

def calibrate_percentile_fallbacks(rolling_df: pd.DataFrame) -> dict:
    """从最新数据重新计算百分位 fallback 值。"""
    current = {
        "excess_5d_p15": -4.91,
        "excess_5d_p85": 6.24,
        "excess_10d_p15": -6.36,
        "excess_10d_p70": 4.25,
        "excess_10d_p85": 7.26,
    }
    computed = compute_thresholds_from_sample(rolling_df)

    results = {}
    for param, cur_val in current.items():
        new_val = round(computed.get(param, cur_val), 4)
        changed = abs(new_val - cur_val) > 0.01
        results[param] = {
            "current": cur_val,
            "suggested": new_val,
            "changed": changed,
        }

    return results


# ── 5. 入场阈值校准 ─────────────────────────────────────────────────────────

def grid_search_entry_thresholds(daily_results: list[dict]) -> dict:
    """对每种 regime 网格搜索最优入场阈值。"""
    regime_thresholds_current = {
        "mean_reverting": 3,
        "trending": 4,
        "transition": 4,
    }

    results = {}
    for regime in ["mean_reverting", "trending", "transition"]:
        current = regime_thresholds_current[regime]
        best_threshold = current
        best_wr = 0.0
        best_n = 0
        threshold_details = []

        for t in THRESHOLD_RANGE:
            # 做多：score >= t 且非 veto
            long_days = [
                dr for dr in daily_results
                if dr.get("regime") == regime
                and dr.get("score", 0) >= t
                and not is_veto(dr)
                and safe_float(dr.get("next1dExcess")) is not None
            ]
            n = len(long_days)
            if n == 0:
                threshold_details.append({"threshold": t, "n": 0, "winRate": None})
                continue
            wins = sum(1 for d in long_days if safe_float(d["next1dExcess"]) > 0)
            wr = wins / n
            threshold_details.append({"threshold": t, "n": n, "winRate": round(wr, 3)})

            # 选胜率最高且样本充足的
            if n >= THRESHOLD_MIN_TRADES and wr > best_wr:
                best_wr = wr
                best_threshold = t
                best_n = n

        # 如果没有样本充足的阈值，保持当前
        if best_n < THRESHOLD_MIN_TRADES:
            best_threshold = current
            best_wr = 0.0

        changed = best_threshold != current
        results[regime] = {
            "current": current,
            "suggested": best_threshold,
            "suggestedWinRate": round(best_wr, 3) if best_wr > 0 else None,
            "suggestedN": best_n,
            "changed": changed,
            "allThresholds": threshold_details,
        }

    return results


# ── 6. Walk-Forward 验证 ──────────────────────────────────────────────────────

def walk_forward_validate(daily_results: list[dict], new_weights: dict,
                          new_multipliers: dict, new_thresholds: dict) -> dict:
    """用新参数在历史数据上验证胜率。"""
    train_window = 60
    regimes = ["mean_reverting", "trending", "transition"]

    # 构建新权重查找表
    weight_lookup = {}
    for sig, info in new_weights.items():
        weight_lookup[sig] = info["suggested"]

    # 当前参数胜率
    current_correct = 0
    current_total = 0
    new_correct = 0
    new_total = 0

    for i in range(train_window, len(daily_results)):
        dr = daily_results[i]
        exc = safe_float(dr.get("next1dExcess"))
        if exc is None:
            continue
        regime = dr.get("regime", "transition")
        score = dr.get("score", 0)
        veto = is_veto(dr)

        # 当前策略
        current_threshold = {"mean_reverting": 3, "trending": 4, "transition": 4}[regime]
        if score >= current_threshold and not veto:
            current_total += 1
            if exc > 0:
                current_correct += 1

        # 新策略：用新阈值判断做多
        new_threshold = new_thresholds.get(regime, {}).get("suggested", current_threshold)
        if score >= new_threshold and not veto:
            new_total += 1
            if exc > 0:
                new_correct += 1

    current_wr = current_correct / current_total if current_total > 0 else 0
    new_wr = new_correct / new_total if new_total > 0 else 0

    verdict = "new_params_pass" if new_wr >= current_wr else "needs_review"

    return {
        "currentWinRate": round(current_wr, 3),
        "newWinRate": round(new_wr, 3),
        "currentTrades": current_total,
        "newTrades": new_total,
        "verdict": verdict,
    }


# ── 7. 应用到 config.py ──────────────────────────────────────────────────────

def apply_config(new_weights: dict, new_multipliers: dict, new_fallbacks: dict,
                 new_thresholds: dict) -> None:
    """更新 src/v2_scorer/config.py。"""
    # 备份
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    backup_path = BACKUP_DIR / f"v2_config_backup_{date_str}.json"

    # 读取当前 config 为备份
    backup_data = {
        "backupDate": date_str,
        "V1_BUY": V1_BUY,
        "V1_SELL": V1_SELL,
        "V2_NEW_BUY": V2_NEW_BUY,
        "V2_NEW_SELL": V2_NEW_SELL,
        "REGIME_MULTIPLIER": REGIME_MULTIPLIER,
    }
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    print(f"[OK] 配置备份至：{backup_path}")

    # 构建新的权重字典
    new_v1_buy = {}
    new_v1_sell = {}
    new_v2_buy = {}
    new_v2_sell = {}

    for sig, info in new_weights.items():
        w = info["suggested"]
        if w == 0:
            continue  # 移除失效信号
        cat = info.get("category", "v1")
        if cat == "v1":
            if w > 0:
                new_v1_buy[sig] = w
            else:
                new_v1_sell[sig] = w
        else:
            if w > 0:
                new_v2_buy[sig] = w
            else:
                new_v2_sell[sig] = w

    # 构建新的 Regime 乘数
    new_regime_mult = {}
    for regime in ["mean_reverting", "trending", "transition"]:
        new_regime_mult[regime] = {}
        for cat_name in ["streak_buy", "streak_sell", "reversion_buy", "trend_buy"]:
            new_regime_mult[regime][cat_name] = new_multipliers.get(regime, {}).get(cat_name, {}).get("suggested", 1.0)

    # 写入 config.py
    lines = []
    lines.append('"""')
    lines.append('V2 评分信号权重与 Regime 乘数配置')
    lines.append('')
    lines.append(f'来源：auto_calibrate_v2.py 于 {date_str} 自动校准')
    lines.append('"""')
    lines.append('')
    lines.append('from __future__ import annotations')
    lines.append('')

    # V1_BUY
    lines.append('# V1 买入信号')
    lines.append(f'V1_BUY: dict[str, int] = {{')
    for sig, w in new_v1_buy.items():
        lines.append(f'    "{sig}": {w:+d},')
    lines.append('}')
    lines.append('')

    # V1_SELL
    lines.append('# V1 卖出信号')
    lines.append(f'V1_SELL: dict[str, int] = {{')
    for sig, w in new_v1_sell.items():
        lines.append(f'    "{sig}": {w:+d},')
    lines.append('}')
    lines.append('')

    # V2_NEW_BUY
    lines.append('# V2 新增买入信号')
    lines.append(f'V2_NEW_BUY: dict[str, int] = {{')
    for sig, w in new_v2_buy.items():
        lines.append(f'    "{sig}": {w:+d},')
    lines.append('}')
    lines.append('')

    # V2_NEW_SELL
    lines.append('# V2 新增卖出信号')
    lines.append(f'V2_NEW_SELL: dict[str, int] = {{')
    for sig, w in new_v2_sell.items():
        lines.append(f'    "{sig}": {w:+d},')
    lines.append('}')
    lines.append('')

    # REGIME_MULTIPLIER
    lines.append('# Regime 自适应乘数')
    lines.append('REGIME_MULTIPLIER: dict[str, dict[str, float]] = {')
    for regime in ["mean_reverting", "trending", "transition"]:
        lines.append(f'    "{regime}": {{')
        for cat_name in ["streak_buy", "streak_sell", "reversion_buy", "trend_buy"]:
            val = new_regime_mult[regime][cat_name]
            lines.append(f'        "{cat_name}": {val},')
        lines.append('    },')
    lines.append('}')
    lines.append('')

    # ALPHA_SIGNALS - 不变
    lines.append('# Alpha 信号集合')
    lines.append('ALPHA_SIGNALS: set[str] = {')
    alpha_signals = ["资金价格背离", "主力资金拖累", "行业扩散不足", "交易观察池降温",
                     "行业Beta为中性", "主题情绪强但主线池弱", "行业Beta为负",
                     "情绪池强于产业链", "放量下跌"]
    for sig in alpha_signals:
        lines.append(f'    "{sig}",')
    lines.append('}')
    lines.append('')

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[OK] config.py 已更新")


# ── 8. 控制台输出 ────────────────────────────────────────────────────────────

def print_calibration_report(weight_results, multiplier_results, fallback_results,
                             threshold_results, validation, gen_date):
    print("=" * 60)
    print(f"  V2 参数自动校准 ({gen_date})")
    print("=" * 60)

    # 信号权重
    print("\n  ━━ 信号权重 ━━")
    print(f"  {'信号':<30} {'当前':>4} {'建议':>4} {'命中率':>7} {'状态':<10}")
    for sig, info in sorted(weight_results.items()):
        status = ""
        if info["changed"]:
            if info["suggested"] == 0:
                status = "↓ 失效"
            elif abs(info["suggested"]) > abs(info["current"]):
                status = "↑ 增强"
            else:
                status = "↓ 降权"
        else:
            status = "✓"

        hr = f"{info['hitRate']:.1%}" if info["hitRate"] is not None else "N/A"
        print(f"  {sig:<30} {info['current']:>+4d} {info['suggested']:>+4d} {hr:>7} {status:<10}")

    # Regime 乘数
    print("\n  ━━ Regime 乘数 ━━")
    for regime in ["mean_reverting", "trending", "transition"]:
        short = {"mean_reverting": "MR", "trending": "TR", "transition": "TS"}[regime]
        for cat_name in ["streak_buy", "streak_sell", "reversion_buy", "trend_buy"]:
            info = multiplier_results.get(regime, {}).get(cat_name, {})
            cur = info.get("current", 1.0)
            sug = info.get("suggested", 1.0)
            changed = info.get("changed", False)
            arrow = "→" if changed else "="
            print(f"  {short}.{cat_name:<15} {cur:.1f} {arrow} {sug:.1f}")

    # 百分位 Fallback
    print("\n  ━━ 百分位 Fallback ━━")
    for param, info in fallback_results.items():
        arrow = "→" if info["changed"] else "="
        print(f"  {param:<20} {info['current']:.2f} {arrow} {info['suggested']:.2f}")

    # 入场阈值
    print("\n  ━━ 入场阈值 ━━")
    for regime in ["mean_reverting", "trending", "transition"]:
        short = {"mean_reverting": "MR", "trending": "TR", "transition": "TS"}[regime]
        info = threshold_results.get(regime, {})
        cur = info.get("current", 0)
        sug = info.get("suggested", 0)
        wr = info.get("suggestedWinRate")
        n = info.get("suggestedN", 0)
        arrow = "→" if info.get("changed") else "="
        wr_str = f"{wr:.1%}" if wr else "N/A"
        note = "(数据不足，保持)" if n < THRESHOLD_MIN_TRADES and info.get("changed") else ""
        print(f"  {short}  ≥{cur} {arrow} ≥{sug}  胜率 {wr_str}  n={n}  {note}")

    # Walk-Forward 验证
    print("\n  ━━ Walk-Forward 验证 ━━")
    print(f"  当前胜率：{validation['currentWinRate']:.1%}  →  新参数胜率：{validation['newWinRate']:.1%}")
    print(f"  当前操作：{validation['currentTrades']}次  →  新参数操作：{validation['newTrades']}次")
    verdict_text = {
        "new_params_pass": "recommended ✓",
        "needs_review": "needs_review ⚠",
    }.get(validation["verdict"], validation["verdict"])
    print(f"  标记：{verdict_text}")

    print("-" * 60)
    print("  使用 --apply 更新 config.py")
    print("=" * 60)


# ── 主函数 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="V2 参数自动校准")
    parser.add_argument("--apply", action="store_true", help="更新 config.py")
    args = parser.parse_args()

    print("=" * 60)
    print("  V2 参数自动校准")
    print("=" * 60)

    # 加载数据
    with open(V2_SCORING_JSON, encoding="utf-8") as f:
        v2_data = json.load(f)
    daily_results = v2_data.get("dailyResults", [])
    print(f"[INFO] v2_scoring: {len(daily_results)} 天")

    rolling_df = pd.read_csv(ROLLING_CSV)
    print(f"[INFO] rolling_metrics: {len(rolling_df)} 行")

    # 校准
    signal_stats = compute_signal_stats(daily_results)
    weight_results = calibrate_signal_weights(signal_stats)
    multiplier_results = calibrate_regime_multipliers(daily_results, signal_stats)
    fallback_results = calibrate_percentile_fallbacks(rolling_df)
    threshold_results = grid_search_entry_thresholds(daily_results)

    # 标记信号 category
    all_weights = {}
    all_weights.update(V1_BUY)
    all_weights.update(V1_SELL)
    all_weights.update(V2_NEW_BUY)
    all_weights.update(V2_NEW_SELL)
    for sig in weight_results:
        if sig in V1_BUY or sig in V1_SELL:
            weight_results[sig]["category"] = "v1"
        else:
            weight_results[sig]["category"] = "v2_new"

    # Walk-Forward 验证
    validation = walk_forward_validate(daily_results, weight_results,
                                       multiplier_results, threshold_results)

    # 生成日期
    gen_date = v2_data.get("generatedAt", "")
    if not gen_date and daily_results:
        gen_date = daily_results[-1].get("date", "")

    # 状态
    has_changes = any(
        info.get("changed") for info in weight_results.values()
    ) or any(
        info.get("changed")
        for regime_data in multiplier_results.values()
        for info in regime_data.values()
    ) or any(
        info.get("changed") for info in fallback_results.values()
    ) or any(
        info.get("changed") for info in threshold_results.values()
    )

    status = "recommended" if validation["verdict"] == "new_params_pass" else "needs_review"

    # 控制台输出
    print_calibration_report(weight_results, multiplier_results, fallback_results,
                            threshold_results, validation, gen_date)

    # JSON 报告
    report = {
        "generatedAt": gen_date,
        "status": status,
        "hasChanges": has_changes,
        "comparison": {
            "signalWeights": weight_results,
            "regimeMultipliers": multiplier_results,
            "percentileFallbacks": fallback_results,
            "entryThresholds": threshold_results,
        },
        "validation": validation,
    }

    # sanitize for JSON
    def sanitize(obj):
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize(v) for v in obj]
        if isinstance(obj, (bool, int, float, str, type(None))):
            return obj
        if hasattr(obj, "item"):
            return obj.item()
        return str(obj)

    report = sanitize(report)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 校准报告写入：{OUTPUT_JSON}  ({OUTPUT_JSON.stat().st_size / 1024:.1f} KB)")

    # --apply
    if args.apply:
        if status == "recommended":
            apply_config(weight_results, multiplier_results, fallback_results, threshold_results)
        else:
            print(f"[WARN] 状态为 {status}，不自动更新。请人工审查后使用 --apply。")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
