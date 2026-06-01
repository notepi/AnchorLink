"""
超额收益网格画像分析（v3: 中位数价格收益 + 四层指标）
=================================================
读取每日数据 CSV，按 Q×G 网格聚合，
计算四层指标（空间/常态/路径/风险）、跨档趋势、综合画像，
输出汇总 CSV、结构化 JSON 和可读报告。

四层架构：
  1. 空间层：Oracle MFE/MAE/RR（理论上界）
  2. 常态表现层：中位数价格收益/天数/留存率
  3. 路径层：达峰/达谷天数
  4. 风险层：WinRate/PF/VaR（基于中位数价格收益）

输入：
  - docs/excess_backtest/excess_grade_daily.csv
  - docs/excess_backtest/excess_grade_thresholds.json

输出：
  - docs/excess_backtest/excess_grade_summary.csv
  - docs/excess_backtest/excess_grade_backtest.json
  - docs/excess_backtest/excess_grade_backtest.md
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).parent.parent
DAILY_CSV = ROOT / "docs/excess_backtest/excess_grade_daily.csv"
THRESHOLDS_JSON = ROOT / "docs/excess_backtest/excess_grade_thresholds.json"
SUMMARY_CSV = ROOT / "docs/excess_backtest/excess_grade_summary.csv"
OUTPUT_JSON = ROOT / "docs/excess_backtest/excess_grade_backtest.json"
REPORT_MD = ROOT / "docs/excess_backtest/excess_grade_backtest.md"

Q_LABEL = {1: "极冷", 2: "偏冷", 3: "中性", 4: "偏热", 5: "极热"}
G_LABEL = {1: "大降", 2: "小降", 3: "稳定", 4: "小升", 5: "大升"}

INDICATOR_LABELS = {
    "excess_5d": "5日超额",
    "excess_10d": "10日超额",
    "daily_excess": "当日超额",
}

PF_CAP = 9.9


# ── 空间层指标（Oracle） ─────────────────────────────────────────────────────

def compute_space_stats(upside: pd.Series, adverse: pd.Series) -> dict:
    """空间层：Oracle MFE/MAE，理论上界"""
    up_valid = upside.dropna()
    adv_valid = adverse.dropna()
    n = len(up_valid)
    if n < 2:
        return {
            "n": n, "upsideMean": None, "upsideMedian": None,
            "adverseMean": None, "upsideAdverseRatio": None,
            "std": None, "p25": None, "p75": None,
            "skew": None, "maxUpside": None, "maxAdverse": None,
        }

    up_mean = float(up_valid.mean())
    adv_mean = float(adv_valid.mean())
    adv_abs = abs(adv_mean) if abs(adv_mean) > 1e-9 else 1e-9
    ratio = round(up_mean / adv_abs, 4)

    return {
        "n": n,
        "upsideMean": round(up_mean, 4),
        "upsideMedian": round(float(up_valid.median()), 4),
        "adverseMean": round(adv_mean, 4),
        "upsideAdverseRatio": ratio,
        "std": round(float(up_valid.std()), 4),
        "p25": round(float(up_valid.quantile(0.25)), 4),
        "p75": round(float(up_valid.quantile(0.75)), 4),
        "skew": round(float(up_valid.skew()), 4),
        "maxUpside": round(float(up_valid.max()), 4),
        "maxAdverse": round(float(adv_valid.min()), 4),
    }


# ── 常态/风险层指标（中位数收益） ─────────────────────────────────────────────

def compute_return_stats(median_return: pd.Series, retention: pd.Series) -> dict:
    """常态表现层 + 风险层：基于中位数价格收益"""
    ret_valid = median_return.dropna()
    n = len(ret_valid)
    if n < 2:
        return {
            "retMean": None, "retMedian": None,
            "winRate": None, "profitFactor": None,
            "var95": None, "retentionMean": None, "retentionMedian": None,
        }

    ret_mean = float(ret_valid.mean())
    ret_median = float(ret_valid.median())
    win_rate = round(float((ret_valid > 0).mean()), 4)

    pos_sum = float(ret_valid[ret_valid > 0].sum())
    neg_sum = abs(float(ret_valid[ret_valid <= 0].sum()))
    pf = min(pos_sum / neg_sum, PF_CAP) if neg_sum > 1e-9 else PF_CAP

    var95 = round(float(ret_valid.quantile(0.05)), 4)

    ret_valid2 = retention.dropna()
    retention_mean = round(float(ret_valid2.mean()), 4) if len(ret_valid2) > 0 else None
    retention_median = round(float(ret_valid2.median()), 4) if len(ret_valid2) > 0 else None

    return {
        "retMean": round(ret_mean, 4),
        "retMedian": round(ret_median, 4),
        "winRate": win_rate,
        "profitFactor": round(float(pf), 4),
        "var95": var95,
        "retentionMean": retention_mean,
        "retentionMedian": retention_median,
    }


# ── 路径指标 ──────────────────────────────────────────────────────────────────

def compute_path_metrics(subset: pd.DataFrame, direction: str) -> dict:
    """路径层：达峰/达谷天数 + 中位数天数"""
    valid = subset[subset["tradeable"] == 1].dropna(subset=["fwd_20d_peak_day"])

    if direction == "long":
        day_col = "fwd_20d_peak_day"
        favorable = valid["fwd_20d_peak_day"] < valid["fwd_20d_trough_day"]
    else:
        day_col = "fwd_20d_trough_day"
        favorable = valid["fwd_20d_trough_day"] < valid["fwd_20d_peak_day"]

    if len(valid) == 0:
        return {
            "peakDayMedian": None, "peakDayMean": None,
            "medianDayMean": None, "medianDayMedian": None,
            "favorableFirstRate": None,
        }

    median_days = valid["fwd_20d_median_day"].dropna()

    return {
        "peakDayMedian": round(float(valid[day_col].median()), 1),
        "peakDayMean": round(float(valid[day_col].mean()), 1),
        "medianDayMean": round(float(median_days.mean()), 1) if len(median_days) > 0 else None,
        "medianDayMedian": round(float(median_days.median()), 1) if len(median_days) > 0 else None,
        "favorableFirstRate": round(float(favorable.mean()), 4),
    }


# ── 跨档趋势分析 ──────────────────────────────────────────────────────────────

def compute_cross_grade_trends(ind_data: pd.DataFrame) -> dict:
    """计算 Q 和 G 两个维度的跨档趋势（基于中位数收益）"""
    Q_COLD = [1, 2]
    Q_HOT = [4, 5]
    G_DOWN = [1, 2]
    G_UP = [4, 5]

    tradeable = ind_data[ind_data["tradeable"] == 1]

    cold_data = tradeable[tradeable["q_grade"].isin(Q_COLD)]
    hot_data = tradeable[tradeable["q_grade"].isin(Q_HOT)]
    down_data = tradeable[tradeable["g_grade"].isin(G_DOWN)]
    up_data = tradeable[tradeable["g_grade"].isin(G_UP)]

    # Q 维度 spread（基于中位数收益）
    long_cold_mean = cold_data["long_upside"].mean() if len(cold_data) > 0 else 0
    long_hot_mean = hot_data["long_upside"].mean() if len(hot_data) > 0 else 0
    short_cold_mean = cold_data["short_upside"].mean() if len(cold_data) > 0 else 0
    short_hot_mean = hot_data["short_upside"].mean() if len(hot_data) > 0 else 0

    long_q_spread = long_cold_mean - long_hot_mean
    short_q_spread = short_hot_mean - short_cold_mean
    long_q_spread_pct = long_q_spread / abs(long_cold_mean) if abs(long_cold_mean) > 1e-9 else 0
    short_q_spread_pct = short_q_spread / abs(short_cold_mean) if abs(short_cold_mean) > 1e-9 else 0

    # 中位数收益的 Q spread
    ret_cold_mean = cold_data["fwd_20d_median_return"].mean() if len(cold_data) > 0 else 0
    ret_hot_mean = hot_data["fwd_20d_median_return"].mean() if len(hot_data) > 0 else 0
    ret_q_spread = ret_cold_mean - ret_hot_mean
    ret_q_spread_pct = ret_q_spread / abs(ret_cold_mean) if abs(ret_cold_mean) > 1e-9 else 0

    # G 维度 spread
    long_down_mean = down_data["long_upside"].mean() if len(down_data) > 0 else 0
    long_up_mean = up_data["long_upside"].mean() if len(up_data) > 0 else 0
    short_down_mean = down_data["short_upside"].mean() if len(down_data) > 0 else 0
    short_up_mean = up_data["short_upside"].mean() if len(up_data) > 0 else 0

    long_g_spread = long_down_mean - long_up_mean
    short_g_spread = short_up_mean - short_down_mean
    long_g_spread_pct = long_g_spread / abs(long_down_mean) if abs(long_down_mean) > 1e-9 else 0
    short_g_spread_pct = short_g_spread / abs(short_down_mean) if abs(short_down_mean) > 1e-9 else 0

    # 中位数收益的 G spread
    ret_down_mean = down_data["fwd_20d_median_return"].mean() if len(down_data) > 0 else 0
    ret_up_mean = up_data["fwd_20d_median_return"].mean() if len(up_data) > 0 else 0
    ret_g_spread = ret_down_mean - ret_up_mean
    ret_g_spread_pct = ret_g_spread / abs(ret_down_mean) if abs(ret_down_mean) > 1e-9 else 0

    # Spearman rho
    g3_data = tradeable[tradeable["g_grade"] == 3]
    q_rho_long, q_rho_short = _compute_spearman(g3_data, "q_grade")

    q3_data = tradeable[tradeable["q_grade"] == 3]
    g_rho_long, g_rho_short = _compute_spearman(q3_data, "g_grade")

    # 中位数收益的 Spearman rho
    q_rho_ret, _ = _compute_spearman_ret(g3_data, "q_grade")
    g_rho_ret, _ = _compute_spearman_ret(q3_data, "g_grade")

    # ── 条件趋势：每个 Q 档内的 G 趋势 ─────────────────────────────
    conditional_g = {}
    for q in range(1, 6):
        q_sub = tradeable[tradeable["q_grade"] == q]
        q_down = q_sub[q_sub["g_grade"].isin(G_DOWN)]
        q_up = q_sub[q_sub["g_grade"].isin(G_UP)]
        l_down = q_down["long_upside"].mean() if len(q_down) > 0 else 0
        l_up = q_up["long_upside"].mean() if len(q_up) > 0 else 0
        s_down = q_down["short_upside"].mean() if len(q_down) > 0 else 0
        s_up = q_up["short_upside"].mean() if len(q_up) > 0 else 0
        r_down = q_down["fwd_20d_median_return"].mean() if len(q_down) > 0 else 0
        r_up = q_up["fwd_20d_median_return"].mean() if len(q_up) > 0 else 0
        g_rho_l, g_rho_s = _compute_spearman(q_sub, "g_grade")
        g_rho_r, _ = _compute_spearman_ret(q_sub, "g_grade")
        conditional_g[str(q)] = {
            "n": len(q_sub),
            "longDownMean": round(float(l_down), 4),
            "longUpMean": round(float(l_up), 4),
            "longSpread": round(float(l_down - l_up), 4),
            "longSpreadPct": round(float((l_down - l_up) / abs(l_down)), 4) if abs(l_down) > 1e-9 else 0,
            "shortDownMean": round(float(s_down), 4),
            "shortUpMean": round(float(s_up), 4),
            "shortSpread": round(float(s_up - s_down), 4),
            "shortSpreadPct": round(float((s_up - s_down) / abs(s_down)), 4) if abs(s_down) > 1e-9 else 0,
            "longRho": round(float(g_rho_l), 4),
            "shortRho": round(float(g_rho_s), 4),
            "retSpread": round(float(r_down - r_up), 4),
            "retSpreadPct": round(float((r_down - r_up) / abs(r_down)), 4) if abs(r_down) > 1e-9 else 0,
            "retRho": round(float(g_rho_r), 4),
        }

    # ── 条件趋势：每个 G 档内的 Q 趋势 ─────────────────────────────
    conditional_q = {}
    for g in range(1, 6):
        g_sub = tradeable[tradeable["g_grade"] == g]
        g_cold = g_sub[g_sub["q_grade"].isin(Q_COLD)]
        g_hot = g_sub[g_sub["q_grade"].isin(Q_HOT)]
        l_cold = g_cold["long_upside"].mean() if len(g_cold) > 0 else 0
        l_hot = g_hot["long_upside"].mean() if len(g_hot) > 0 else 0
        s_cold = g_cold["short_upside"].mean() if len(g_cold) > 0 else 0
        s_hot = g_hot["short_upside"].mean() if len(g_hot) > 0 else 0
        r_cold = g_cold["fwd_20d_median_return"].mean() if len(g_cold) > 0 else 0
        r_hot = g_hot["fwd_20d_median_return"].mean() if len(g_hot) > 0 else 0
        q_rho_l, q_rho_s = _compute_spearman(g_sub, "q_grade")
        q_rho_r, _ = _compute_spearman_ret(g_sub, "q_grade")
        conditional_q[str(g)] = {
            "n": len(g_sub),
            "longColdMean": round(float(l_cold), 4),
            "longHotMean": round(float(l_hot), 4),
            "longSpread": round(float(l_cold - l_hot), 4),
            "longSpreadPct": round(float((l_cold - l_hot) / abs(l_cold)), 4) if abs(l_cold) > 1e-9 else 0,
            "shortColdMean": round(float(s_cold), 4),
            "shortHotMean": round(float(s_hot), 4),
            "shortSpread": round(float(s_hot - s_cold), 4),
            "shortSpreadPct": round(float((s_hot - s_cold) / abs(s_cold)), 4) if abs(s_cold) > 1e-9 else 0,
            "longRho": round(float(q_rho_l), 4),
            "shortRho": round(float(q_rho_s), 4),
            "retSpread": round(float(r_cold - r_hot), 4),
            "retSpreadPct": round(float((r_cold - r_hot) / abs(r_cold)), 4) if abs(r_cold) > 1e-9 else 0,
            "retRho": round(float(q_rho_r), 4),
        }

    # ── 四象限分析（基于中位数收益） ──────────────────────────────
    quadrants = {}
    for q_tag, q_filter in [("cold", Q_COLD), ("hot", Q_HOT)]:
        for g_tag, g_filter in [("down", G_DOWN), ("up", G_UP)]:
            sub = tradeable[
                tradeable["q_grade"].isin(q_filter)
                & tradeable["g_grade"].isin(g_filter)
            ]
            l_mean = sub["long_upside"].mean() if len(sub) > 0 else 0
            s_mean = sub["short_upside"].mean() if len(sub) > 0 else 0
            r_mean = sub["fwd_20d_median_return"].mean() if len(sub) > 0 else 0
            sc = s_mean / abs(l_mean) if abs(l_mean) > 1e-9 else 0
            key = f"{q_tag}_{g_tag}"
            quadrants[key] = {
                "n": len(sub),
                "longUpsideMean": round(float(l_mean), 4),
                "shortUpsideMean": round(float(s_mean), 4),
                "medianReturnMean": round(float(r_mean), 4),
                "shortCompetitiveness": round(float(sc), 4),
            }

    # ── 交互效应 ────────────────────────────────────────────────────
    cd = quadrants["cold_down"]
    cu = quadrants["cold_up"]
    hd = quadrants["hot_down"]
    hu = quadrants["hot_up"]

    long_interaction = (cd["longUpsideMean"] - cu["longUpsideMean"]) - (hd["longUpsideMean"] - hu["longUpsideMean"])
    short_interaction = (cd["shortUpsideMean"] - cu["shortUpsideMean"]) - (hd["shortUpsideMean"] - hu["shortUpsideMean"])
    ret_interaction = (cd["medianReturnMean"] - cu["medianReturnMean"]) - (hd["medianReturnMean"] - hu["medianReturnMean"])

    return {
        "q": {
            "longColdMean": round(float(long_cold_mean), 4),
            "longHotMean": round(float(long_hot_mean), 4),
            "longSpread": round(float(long_q_spread), 4),
            "longSpreadPct": round(float(long_q_spread_pct), 4),
            "shortColdMean": round(float(short_cold_mean), 4),
            "shortHotMean": round(float(short_hot_mean), 4),
            "shortSpread": round(float(short_q_spread), 4),
            "shortSpreadPct": round(float(short_q_spread_pct), 4),
            "longRho": round(float(q_rho_long), 4),
            "shortRho": round(float(q_rho_short), 4),
            "retSpread": round(float(ret_q_spread), 4),
            "retSpreadPct": round(float(ret_q_spread_pct), 4),
            "retRho": round(float(q_rho_ret), 4),
        },
        "g": {
            "longDownMean": round(float(long_down_mean), 4),
            "longUpMean": round(float(long_up_mean), 4),
            "longSpread": round(float(long_g_spread), 4),
            "longSpreadPct": round(float(long_g_spread_pct), 4),
            "shortDownMean": round(float(short_down_mean), 4),
            "shortUpMean": round(float(short_up_mean), 4),
            "shortSpread": round(float(short_g_spread), 4),
            "shortSpreadPct": round(float(short_g_spread_pct), 4),
            "longRho": round(float(g_rho_long), 4),
            "shortRho": round(float(g_rho_short), 4),
            "retSpread": round(float(ret_g_spread), 4),
            "retSpreadPct": round(float(ret_g_spread_pct), 4),
            "retRho": round(float(g_rho_ret), 4),
        },
        "conditionalG": conditional_g,
        "conditionalQ": conditional_q,
        "quadrants": quadrants,
        "interaction": {
            "long": round(float(long_interaction), 4),
            "short": round(float(short_interaction), 4),
            "ret": round(float(ret_interaction), 4),
        },
    }


def _compute_spearman(data: pd.DataFrame, grade_col: str) -> tuple[float, float]:
    """对某维度计算 Spearman rho（Oracle 做多/做空空间 vs 档位）"""
    if len(data) < 3:
        return 0.0, 0.0

    grouped = data.groupby(grade_col).agg(
        long_mean=("long_upside", "mean"),
        short_mean=("short_upside", "mean"),
    )

    if len(grouped) < 3:
        return 0.0, 0.0

    grades = grouped.index.tolist()
    rho_long, _ = stats.spearmanr(grades, grouped["long_mean"].values)
    rho_short, _ = stats.spearmanr(grades, grouped["short_mean"].values)
    return rho_long, rho_short


def _compute_spearman_ret(data: pd.DataFrame, grade_col: str) -> tuple[float, float]:
    """对某维度计算 Spearman rho（中位数收益 vs 档位）"""
    if len(data) < 3:
        return 0.0, 0.0

    grouped = data.groupby(grade_col).agg(
        ret_mean=("fwd_20d_median_return", "mean"),
    )

    if len(grouped) < 3:
        return 0.0, 0.0

    grades = grouped.index.tolist()
    rho_ret, _ = stats.spearmanr(grades, grouped["ret_mean"].values)
    return rho_ret, 0.0


# ── 综合画像 ──────────────────────────────────────────────────────────────────

def determine_profile(
    long_space: dict, short_space: dict,
    long_ret: dict, short_ret: dict,
    long_path: dict, short_path: dict,
    trend_data: dict, q_grade: int, g_grade: int,
) -> dict:
    """判定网格画像：spaceBias + normalPerformance + pathTag + confidence + summary"""
    n = long_space.get("n") or 0

    # 样本量门槛
    if n == 0:
        return {
            "spaceBias": "无样本", "shortCompetitiveness": None,
            "normalPerformance": "-",
            "pathTag": "-", "favorableFirstRate": None,
            "confidence": "无效", "summary": "无触发样本",
        }
    if n < 5:
        return {
            "spaceBias": "样本不足", "shortCompetitiveness": None,
            "normalPerformance": "-",
            "pathTag": "-", "favorableFirstRate": None,
            "confidence": "无效", "summary": f"仅{n}个样本，不足以生成画像",
        }

    long_mean = long_space.get("upsideMean") or 0
    short_mean = short_space.get("upsideMean") or 0

    # 做空竞争力比
    short_competitiveness = short_mean / abs(long_mean) if abs(long_mean) > 1e-9 else 0

    # 空间偏向标签（基于 Oracle 空间）
    if short_competitiveness < 0.4:
        space_bias = "偏多"
    elif short_competitiveness < 0.7:
        space_bias = "多空拉扯"
    elif short_competitiveness < 0.9:
        space_bias = "多空拉扯偏空"
    else:
        space_bias = "偏空"

    # 趋势修正
    q_rho_long = trend_data.get("q", {}).get("longRho", 0)
    q_rho_short = trend_data.get("q", {}).get("shortRho", 0)

    if q_rho_short > 0.7 and q_grade >= 4 and space_bias in ("偏多", "多空拉扯"):
        space_bias = "多空拉扯偏空"
    if q_rho_long < -0.7 and q_grade <= 2 and space_bias in ("多空拉扯", "多空拉扯偏空", "偏空"):
        space_bias = "偏多"

    # 常态表现标签（基于中位数价格收益，启发式阈值）
    ret_mean = long_ret.get("retMean") or 0
    if ret_mean > 1.0:
        normal_performance = "正向"
    elif ret_mean >= -1.0:
        normal_performance = "中性"
    else:
        normal_performance = "负向"

    # 路径标签（绑定方向）
    if space_bias == "偏多":
        ffr = long_path.get("favorableFirstRate") or 0.5
    elif space_bias in ("偏空", "多空拉扯偏空"):
        ffr = short_path.get("favorableFirstRate") or 0.5
    else:
        l_ffr = long_path.get("favorableFirstRate") or 0.5
        s_ffr = short_path.get("favorableFirstRate") or 0.5
        ffr = (l_ffr + s_ffr) / 2

    if ffr > 0.6:
        path_tag = "先有利"
    elif ffr >= 0.4:
        path_tag = "路径拉锯"
    else:
        path_tag = "先不利"

    # 置信度（5 ≤ n < 10 时至少"低"）
    rho = abs(trend_data.get("q", {}).get("retRho", 0))
    spread_pct = abs(trend_data.get("q", {}).get("retSpreadPct", 0))

    grade_n_ok = n >= 20
    trend_ok = rho >= 0.7
    spread_ok = spread_pct >= 0.2

    if grade_n_ok and trend_ok and spread_ok:
        confidence = "高"
    elif n >= 10 and (trend_ok or spread_ok):
        confidence = "中"
    else:
        confidence = "低"

    if n < 10:
        confidence = "低"

    # 一句话总结
    summary = _build_summary(space_bias, normal_performance, path_tag)

    return {
        "spaceBias": space_bias,
        "shortCompetitiveness": round(float(short_competitiveness), 4),
        "normalPerformance": normal_performance,
        "pathTag": path_tag,
        "favorableFirstRate": round(float(ffr), 4),
        "confidence": confidence,
        "summary": summary,
    }


def _build_summary(space_bias: str, normal_performance: str, path_tag: str) -> str:
    parts = []
    # 空间偏向
    if space_bias == "偏多":
        parts.append("做多空间优势明显")
    elif space_bias == "偏空":
        parts.append("做空空间优势明显")
    elif space_bias == "多空拉扯偏空":
        parts.append("做空竞争力上升")
    else:
        parts.append("多空空间接近")
    # 常态表现
    if normal_performance == "正向":
        parts.append("中位数价格收益为正")
    elif normal_performance == "负向":
        parts.append("中位数价格收益为负")
    # 路径
    if space_bias == "多空拉扯":
        return "多空空间接近，不宜单边操作"
    if path_tag == "先有利":
        parts.append("路径先有利")
    elif path_tag == "先不利":
        parts.append("但常先浮亏再反转，执行压力大")
    else:
        parts.append("路径拉锯")
    return "，".join(parts)


# ── 网格分析 ──────────────────────────────────────────────────────────────────

def analyze_grids() -> tuple[list[dict], dict]:
    """对每个 Q×G 网格做画像分析"""
    daily_df = pd.read_csv(DAILY_CSV)
    tradeable = daily_df[daily_df["tradeable"] == 1]

    summary_rows = []
    grid_profiles = {}

    for ind_key in INDICATOR_LABELS:
        ind_data = tradeable[tradeable["indicator"] == ind_key]

        trend_data = compute_cross_grade_trends(ind_data)

        ind_profiles = {}

        for q_grade in range(1, 6):
            for g_grade in range(1, 6):
                subset = ind_data[
                    (ind_data["q_grade"] == q_grade) & (ind_data["g_grade"] == g_grade)
                ]
                q_lbl = Q_LABEL.get(q_grade, "")
                g_lbl = G_LABEL.get(g_grade, "")

                # 空间层（Oracle）
                long_space = compute_space_stats(subset["long_upside"], subset["long_adverse"])
                short_space = compute_space_stats(subset["short_upside"], subset["short_adverse"])

                # 常态/风险层（中位数价格收益）
                long_ret = compute_return_stats(subset["fwd_20d_median_return"], subset["fwd_20d_retention"])
                # 做空侧：取反中位数收益，重算留存率
                short_median_return = -subset["fwd_20d_median_return"]
                short_retention_raw = short_median_return / subset["short_upside"].replace(0, np.nan)
                short_ret = compute_return_stats(short_median_return, short_retention_raw)

                # 路径层
                long_path = compute_path_metrics(subset, "long")
                short_path = compute_path_metrics(subset, "short")

                # 综合画像
                profile = determine_profile(
                    long_space, short_space,
                    long_ret, short_ret,
                    long_path, short_path,
                    trend_data, q_grade, g_grade,
                )

                # 汇总行
                row = {
                    "indicator": ind_key,
                    "q_grade": q_grade,
                    "q_label": q_lbl,
                    "g_grade": g_grade,
                    "g_label": g_lbl,
                    "n_triggers": long_space["n"],
                }
                # 空间层
                for k, v in long_space.items():
                    row[f"long_{k}"] = v
                for k, v in short_space.items():
                    row[f"short_{k}"] = v
                # 常态/风险层
                for k, v in long_ret.items():
                    row[f"long_{k}"] = v
                for k, v in short_ret.items():
                    row[f"short_{k}"] = v
                # 路径层
                row["long_peak_day_median"] = long_path["peakDayMedian"]
                row["long_peak_day_mean"] = long_path["peakDayMean"]
                row["long_median_day_mean"] = long_path["medianDayMean"]
                row["long_median_day_median"] = long_path["medianDayMedian"]
                row["long_favorable_first_rate"] = long_path["favorableFirstRate"]
                row["short_peak_day_median"] = short_path["peakDayMedian"]
                row["short_peak_day_mean"] = short_path["peakDayMean"]
                row["short_median_day_mean"] = short_path["medianDayMean"]
                row["short_median_day_median"] = short_path["medianDayMedian"]
                row["short_favorable_first_rate"] = short_path["favorableFirstRate"]
                # 画像
                row["space_bias"] = profile["spaceBias"]
                row["normal_performance"] = profile["normalPerformance"]
                row["short_competitiveness"] = profile["shortCompetitiveness"]
                row["path_tag"] = profile["pathTag"]
                row["confidence"] = profile["confidence"]
                row["summary"] = profile["summary"]
                summary_rows.append(row)

                # JSON 结构
                grid_key = f"Q{q_grade}_{q_lbl}_G{g_grade}_{g_lbl}"
                ind_profiles[grid_key] = {
                    "qGrade": q_grade,
                    "gGrade": g_grade,
                    "nTriggers": long_space["n"],
                    "longSpace": long_space,
                    "shortSpace": short_space,
                    "longReturn": long_ret,
                    "shortReturn": short_ret,
                    "longPath": long_path,
                    "shortPath": short_path,
                    "profile": profile,
                }

        ind_profiles["_trends"] = trend_data
        grid_profiles[ind_key] = ind_profiles

    return summary_rows, grid_profiles


# ── 月度分布 ──────────────────────────────────────────────────────────────────

def compute_monthly(daily_df: pd.DataFrame) -> dict:
    """按月度统计各指标的做多/做空空间均值 + 中位数收益均值"""
    tradeable = daily_df[daily_df["tradeable"] == 1].copy()
    tradeable["month"] = tradeable["date"].astype(str).str[:6]

    result = {}
    for ind_key in INDICATOR_LABELS:
        ind_data = tradeable[tradeable["indicator"] == ind_key]
        months = {}
        for m, mdf in ind_data.groupby("month"):
            months[m] = {
                "nDays": len(mdf),
                "longUpsideMean": round(float(mdf["long_upside"].mean()), 4) if len(mdf) > 0 else None,
                "shortUpsideMean": round(float(mdf["short_upside"].mean()), 4) if len(mdf) > 0 else None,
                "medianReturnMean": round(float(mdf["fwd_20d_median_return"].mean()), 4) if len(mdf) > 0 else None,
            }
        result[ind_key] = months
    return result


# ── 报告生成 ──────────────────────────────────────────────────────────────────

def fmt_pct(v) -> str:
    if v is None:
        return "  -   "
    return f"{'+' if v >= 0 else ''}{v:.2f}%"


def fmt_ratio(v) -> str:
    if v is None:
        return "-"
    return f"{v:.2f}"


def fmt_int(v) -> str:
    if v is None:
        return "-"
    return f"{v:.0f}d"


def generate_report(grid_profiles: dict, thresholds_data: dict) -> str:
    lines = []
    lines.append("# 超额收益网格画像报告（v3: 中位数价格收益 + 四层指标）")
    lines.append("")
    lines.append(f"> 标的：铂力特 (688333.SH) | 日期：{datetime.now().strftime('%Y-%m-%d')}")
    lines.append(">")
    lines.append("> **空间层**用 Oracle 退出（20天最高/最低价），是理论上界。")
    lines.append("> **常态/风险层**使用未来 20 日收盘价中位数收益，描述典型价格水平。")
    lines.append("> 该指标比 Oracle 上下沿更接近常态，但仍不是可交易退出收益。")
    lines.append("> **PF / VaR / 胜率**基于中位数价格收益计算，有真实区分度。")
    lines.append("> 做空仅理论参考（科创板融券困难）。")
    lines.append("")

    for ind_key, profiles in grid_profiles.items():
        label = INDICATOR_LABELS[ind_key]
        trends = profiles.get("_trends", {})
        q_t = trends.get("q", {})
        g_t = trends.get("g", {})

        lines.append(f"## {label}")
        lines.append("")

        # Q 维度趋势
        q_long_spread = q_t.get("longSpread", 0)
        q_short_spread = q_t.get("shortSpread", 0)
        q_long_pct = q_t.get("longSpreadPct", 0)
        q_short_pct = q_t.get("shortSpreadPct", 0)
        q_rho_l = q_t.get("longRho", 0)
        q_rho_s = q_t.get("shortRho", 0)

        lines.append(f"**Q维度趋势**：做多空间从冷端到热端变化 {fmt_pct(q_long_spread)}（{q_long_pct:+.0%}），做空空间变化 {fmt_pct(q_short_spread)}（{q_short_pct:+.0%}）。")
        lines.append(f"**G维度趋势**：做多空间从下降到上升变化 {fmt_pct(g_t.get('longSpread', 0))}（{g_t.get('longSpreadPct', 0):+.0%}），做空空间变化 {fmt_pct(g_t.get('shortSpread', 0))}（{g_t.get('shortSpreadPct', 0):+.0%}）。")
        lines.append(f"单调性 Q_ρ={q_rho_l:.2f}(多)/{q_rho_s:.2f}(空)，G_ρ={g_t.get('longRho', 0):.2f}(多)/{g_t.get('shortRho', 0):.2f}(空)。")
        lines.append("")

        # 中位数收益趋势
        lines.append(f"**中位数价格收益趋势**：Q维度 {fmt_pct(q_t.get('retSpread', 0))}（{q_t.get('retSpreadPct', 0):+.0%}，ρ={q_t.get('retRho', 0):.2f}），G维度 {fmt_pct(g_t.get('retSpread', 0))}（{g_t.get('retSpreadPct', 0):+.0%}，ρ={g_t.get('retRho', 0):.2f}）。")
        lines.append("")

        # ── 条件趋势 ──────────────────────────────────────────────
        cond_g = trends.get("conditionalG", {})
        cond_q = trends.get("conditionalQ", {})

        lines.append("**条件趋势**：")
        for q, tag in [("1", "Q1_极冷"), ("5", "Q5_极热")]:
            cg = cond_g.get(q, {})
            if cg.get("n", 0) > 0:
                lines.append(f"- {tag}内 G 趋势：做多空间 G降→G升 {fmt_pct(cg.get('longSpread', 0))}（ρ={cg.get('longRho', 0):.2f}），做空空间 {fmt_pct(cg.get('shortSpread', 0))}（ρ={cg.get('shortRho', 0):.2f}），中位数价格收益 {fmt_pct(cg.get('retSpread', 0))}（ρ={cg.get('retRho', 0):.2f}）")
        for g, tag in [("1", "G1_大降"), ("5", "G5_大升")]:
            cq = cond_q.get(g, {})
            if cq.get("n", 0) > 0:
                lines.append(f"- {tag}内 Q 趋势：做多空间 Q冷→Q热 {fmt_pct(cq.get('longSpread', 0))}（ρ={cq.get('longRho', 0):.2f}），做空空间 {fmt_pct(cq.get('shortSpread', 0))}（ρ={cq.get('shortRho', 0):.2f}），中位数价格收益 {fmt_pct(cq.get('retSpread', 0))}（ρ={cq.get('retRho', 0):.2f}）")
        lines.append("")

        # ── 四象限 ────────────────────────────────────────────────
        quads = trends.get("quadrants", {})
        lines.append("**四象限**：")
        lines.append("")
        lines.append("| 象限 | n | 做多空间 | 做空空间 | 空/多比 | 中位数价格收益 |")
        lines.append("|------|---|---------|---------|--------|---------------|")
        for q_tag, q_lbl in [("cold", "Q冷"), ("hot", "Q热")]:
            for g_tag, g_lbl in [("down", "G降"), ("up", "G升")]:
                qd = quads.get(f"{q_tag}_{g_tag}", {})
                n = qd.get("n", 0)
                l = qd.get("longUpsideMean")
                s = qd.get("shortUpsideMean")
                sc = qd.get("shortCompetitiveness")
                rm = qd.get("medianReturnMean")
                sc_str = f"{sc:.2f}" if sc is not None else "-"
                lines.append(f"| {q_lbl}×{g_lbl} | {n} | {fmt_pct(l)} | {fmt_pct(s)} | {sc_str} | {fmt_pct(rm)} |")
        lines.append("")

        # ── 交互效应 ──────────────────────────────────────────────
        inter = trends.get("interaction", {})
        long_i = inter.get("long", 0)
        short_i = inter.get("short", 0)
        ret_i = inter.get("ret", 0)
        if long_i > 0.5:
            inter_desc = "G方向在Q冷端效果更强（冷端更依赖方向信号）"
        elif long_i < -0.5:
            inter_desc = "G方向在Q热端效果更强（热端更依赖方向信号）"
        else:
            inter_desc = "Q和G接近独立，无明显交互"
        lines.append(f"**交互效应**：做多交互项={long_i:+.2f}，做空交互项={short_i:+.2f}，中位数价格收益交互项={ret_i:+.2f} → {inter_desc}")
        lines.append("")

        # 网格表格 — 按 Q 分组
        for q_grade in range(1, 6):
            q_lbl = Q_LABEL.get(q_grade, "")
            lines.append(f"### Q{q_grade}_{q_lbl}")
            lines.append("")
            lines.append("| G档 | n | 做多空间 | 做空空间 | 空/多比 | 空间风险比 | 中位数价格收益 | 胜率 | PF | VaR_95 | 留存率中位数 | 多头达峰 | 空头达谷 | 先有利 | 空间偏向 | 常态表现 | 置信度 | 说明 |")
            lines.append("|-----|---|---------|---------|--------|-----------|---------------|------|-----|--------|-------------|---------|---------|--------|----------|----------|--------|------|")

            for g_grade in range(1, 6):
                g_lbl = G_LABEL.get(g_grade, "")
                grid_key = f"Q{q_grade}_{q_lbl}_G{g_grade}_{g_lbl}"
                p = profiles.get(grid_key, {})
                if not p:
                    continue

                ls = p.get("longSpace", {})
                ss = p.get("shortSpace", {})
                lr = p.get("longReturn", {})
                lp = p.get("longPath", {})
                sp = p.get("shortPath", {})
                prof = p.get("profile", {})

                n = ls.get("n", 0)
                l_mean = ls.get("upsideMean")
                s_mean = ss.get("upsideMean")
                sc = prof.get("shortCompetitiveness")
                l_ratio = ls.get("upsideAdverseRatio")
                ret_mean = lr.get("retMean")
                win_rate = lr.get("winRate")
                pf = lr.get("profitFactor")
                var95 = lr.get("var95")
                retention_med = lr.get("retentionMedian")
                l_peak = lp.get("peakDayMean")
                s_trough = sp.get("peakDayMean")
                ffr = prof.get("favorableFirstRate")
                space_bias = prof.get("spaceBias", "-")
                normal_perf = prof.get("normalPerformance", "-")
                conf = prof.get("confidence", "-")
                summary = prof.get("summary", "")

                lines.append(
                    f"| G{g_grade}_{g_lbl} | {n} | {fmt_pct(l_mean)} | {fmt_pct(s_mean)} "
                    f"| {fmt_ratio(sc)} | {fmt_ratio(l_ratio)} | {fmt_pct(ret_mean)} "
                    f"| {fmt_pct(win_rate * 100) if win_rate is not None else '-'} "
                    f"| {fmt_ratio(pf)} | {fmt_pct(var95)} | {fmt_ratio(retention_med)} "
                    f"| {fmt_int(l_peak)} | {fmt_int(s_trough)} "
                    f"| {f'{ffr:.0%}' if ffr is not None else '-'} "
                    f"| {space_bias} | {normal_perf} | {conf} | {summary} |"
                )

            lines.append("")

    return "\n".join(lines)


# ── 主函数 ────────────────────────────────────────────────────────────────────

def main():
    print("[INFO] 超额收益网格画像分析（v3: 中位数价格收益 + 四层指标）")

    # 1. 分析网格
    summary_rows, grid_profiles = analyze_grids()

    # 2. 汇总 CSV
    summary_df = pd.DataFrame(summary_rows)
    SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(SUMMARY_CSV, index=False)
    print(f"[OK] 汇总画像已保存到 {SUMMARY_CSV} ({len(summary_df)} 行)")

    # 3. 月度分布
    daily_df = pd.read_csv(DAILY_CSV)
    monthly = compute_monthly(daily_df)

    # 4. 读取阈值
    with open(THRESHOLDS_JSON, encoding="utf-8") as f:
        thresholds_data = json.load(f)

    # 5. JSON 输出
    output = {
        "generatedAt": datetime.now().strftime("%Y%m%d"),
        "disclaimer": "空间层用Oracle退出（理论上界）；常态/风险层用中位数价格收益（描述典型价格水平，非可交易退出收益）",
        "gradeThresholds": thresholds_data.get("gradeThresholds", {}),
        "gridProfiles": grid_profiles,
        "monthly": monthly,
        "buyAndHold": thresholds_data.get("buyAndHold", {}),
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[OK] 结构化数据已保存到 {OUTPUT_JSON}")

    # 6. 报告
    report = generate_report(grid_profiles, thresholds_data)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[OK] 报告已保存到 {REPORT_MD}")


if __name__ == "__main__":
    main()
