"""
深度量化分析（M-P）
=================
M. 5d/10d 滚动超额的均值回归量化（自相关衰减、半衰期、极端档反转）
N. 行业联动结构分析（4池相关性、脱钩信号、Lead-Lag、Dispersion）
P. 机器学习模型（Ridge / RandomForest，walk-forward 严格回测）

学术依据：
  - A 股均值回归 > 动量（Wu 2004, 半衰期约 232 天）
  - 反向投资策略跑赢动量策略（HKIMR working paper）
  - Lead-lag 在行业间常用 60d 滚动相关性 + Transfer Entropy

输入（只读）：
  - data/output/history_summary.csv
  - data/output/history_rolling_metrics.csv
  - data/output/dashboard_view.json （poolCorrelations）
  - data/output/history_2nd_order_analysis.json

输出：
  - data/output/history_deep_quant_analysis.json
"""

from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor

ROOT = Path(__file__).parent.parent
HISTORY_CSV   = ROOT / "data/output/history_summary.csv"
ROLLING_CSV   = ROOT / "data/output/history_rolling_metrics.csv"
DASHBOARD_JSON = ROOT / "data/output/dashboard_view.json"
SECOND_ORDER_JSON = ROOT / "data/output/history_2nd_order_analysis.json"
OUTPUT_JSON   = ROOT / "data/output/history_deep_quant_analysis.json"

POOLS = ["industryChain", "directPeers", "themePool", "tradingWatchlist"]
POOL_LABELS = {
    "industryChain": "产业链", "directPeers": "同业",
    "themePool": "主题情绪池", "tradingWatchlist": "交易观察池"
}

# ── 工具函数 ──────────────────────────────────────────────────────────────────

def safe_float(v) -> float | None:
    try:
        if v is None or v == "": return None
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None

def percentile(vals: list[float], p: float) -> float:
    if not vals: return 0
    s = sorted(vals)
    idx = int(len(s) * p / 100)
    return s[min(idx, len(s)-1)]

def fmt_pct(v) -> str:
    if v is None: return "  -   "
    return f"{'+' if v>=0 else ''}{v:.2f}%"

def fmt_num(v, decimals=3) -> str:
    if v is None: return "  -   "
    return f"{v:+.{decimals}f}"

def autocorr(x: list[float], lag: int = 1) -> float | None:
    """计算滞后 lag 的自相关系数"""
    if not x or len(x) < lag + 5:
        return None
    n = len(x)
    m = sum(x) / n
    num = sum((x[i] - m) * (x[i+lag] - m) for i in range(n - lag))
    den = sum((v - m) ** 2 for v in x)
    return num / den if den > 0 else None

def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 5: return None
    mx, my = sum(xs)/n, sum(ys)/n
    num = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    dx  = sum((x-mx)**2 for x in xs)
    dy  = sum((y-my)**2 for y in ys)
    den = math.sqrt(dx * dy)
    return num / den if den > 0 else None

def stat_block(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0, "avg": 0, "wr": 0, "p50": 0, "std": 0}
    avg = sum(vals) / len(vals)
    return {
        "n": len(vals),
        "avg": round(avg, 4),
        "wr":  round(sum(1 for v in vals if v > 0) / len(vals), 4),
        "p50": round(sorted(vals)[len(vals)//2], 4),
        "std": round((sum((v - avg) ** 2 for v in vals) / len(vals)) ** 0.5, 4),
    }

def print_section(title: str) -> None:
    print(f"\n{'='*70}\n  {title}\n{'='*70}")

# ── 数据加载 ──────────────────────────────────────────────────────────────────

def load_all():
    """加载并连接所有数据"""
    # history_summary
    with open(HISTORY_CSV, encoding="utf-8") as f:
        history = list(csv.DictReader(f))
    history.sort(key=lambda r: r.get("date") or "")

    # rolling_metrics
    with open(ROLLING_CSV, encoding="utf-8") as f:
        rolling = list(csv.DictReader(f))
    rolling.sort(key=lambda r: r.get("date") or "")

    # dashboard 的 poolCorrelations
    with open(DASHBOARD_JSON, encoding="utf-8") as f:
        dashboard = json.load(f)
    pool_corr = dashboard.get("trends", {}).get("poolCorrelations", [])

    print(f"[INFO] history: {len(history)} 行, rolling: {len(rolling)} 行, poolCorr: {len(pool_corr)} 行")
    return history, rolling, pool_corr

# ─────────────────────────────────────────────────────────────────────────────
# M. 5d/10d 滚动超额的均值回归量化
# ─────────────────────────────────────────────────────────────────────────────

def analyze_excess_mean_reversion(history: list[dict], rolling: list[dict]) -> dict:
    """
    核心问题：
    1. excess_5d / excess_10d 的均值真的接近 0 吗？（验证均值假设）
    2. 自相关衰减速度（半衰期估计）
    3. 极端档（P85+ / P15-）的反转效力
    4. 5d 超额变化率（动量 vs 反转）
    """
    rolling_by_date = {r["date"]: r for r in rolling}
    history_by_date = {r["date"]: r for r in history}

    # 1. 分布统计 + t-test (vs 0)
    e5  = [safe_float(r["excess_5d"])  for r in rolling if safe_float(r["excess_5d"])  is not None]
    e10 = [safe_float(r["excess_10d"]) for r in rolling if safe_float(r["excess_10d"]) is not None]

    def t_test_vs_zero(vals: list[float]) -> dict:
        n = len(vals)
        if n < 5: return {}
        mean = sum(vals) / n
        std = (sum((v - mean) ** 2 for v in vals) / (n - 1)) ** 0.5
        t = mean / (std / n ** 0.5) if std > 0 else 0
        # 简单显著性判断：|t| > 1.96 ≈ p<0.05
        return {
            "n": n, "mean": round(mean, 4), "std": round(std, 4),
            "t_stat": round(t, 3),
            "significant_vs_zero": abs(t) > 1.96,
        }

    dist_stats = {
        "excess_5d":  t_test_vs_zero(e5),
        "excess_10d": t_test_vs_zero(e10),
    }

    # 2. 自相关衰减（用于估算半衰期）
    def autocorr_decay(vals: list[float], max_lag: int = 30) -> dict:
        """计算 lag 1-30 的自相关，估算半衰期 = autocorr 降到 0.5 的 lag"""
        ac = {lag: autocorr(vals, lag) for lag in range(1, max_lag + 1)}
        half_life = None
        for lag, val in ac.items():
            if val is not None and val < 0.5:
                half_life = lag
                break
        return {
            "lag1":  round(ac[1], 3) if ac[1] is not None else None,
            "lag5":  round(ac[5], 3) if ac[5] is not None else None,
            "lag10": round(ac[10], 3) if ac[10] is not None else None,
            "lag20": round(ac[20], 3) if ac[20] is not None else None,
            "lag30": round(ac[30], 3) if ac[30] is not None else None,
            "half_life_days": half_life,
        }

    decay_5d  = autocorr_decay(e5)
    decay_10d = autocorr_decay(e10)

    # 3. 极端档的反转测试
    # 把 excess_5d 按分位数分档，看后续 T+1/T+3/T+5 收益
    def extreme_reversal(rolling_data, excess_col: str, periods: list[str]) -> dict:
        """
        对每个日期：
          - 当 excess_5d 突破 P85 → 后续 T+1/T+3/T+5 收益
          - 当 excess_5d 突破 P15 → 同上
        """
        vals_with_date = [
            (r["date"], safe_float(r[excess_col]))
            for r in rolling_data
            if safe_float(r[excess_col]) is not None
        ]
        vals = [v for _, v in vals_with_date]
        p85 = percentile(vals, 85)
        p70 = percentile(vals, 70)
        p30 = percentile(vals, 30)
        p15 = percentile(vals, 15)

        result = {
            "thresholds": {"p15": round(p15, 2), "p30": round(p30, 2),
                           "p70": round(p70, 2), "p85": round(p85, 2)},
            "buckets": {}
        }

        for label, filter_fn in [
            ("P85+(过热)", lambda v: v >= p85),
            ("P70-P85", lambda v: p70 <= v < p85),
            ("P30-P70(中性)", lambda v: p30 <= v < p70),
            ("P15-P30", lambda v: p15 <= v < p30),
            ("P15-(过冷)", lambda v: v < p15),
        ]:
            matching = [(date, v) for date, v in vals_with_date if filter_fn(v)]
            future_returns = {p: [] for p in periods}
            for date, _ in matching:
                hist_row = history_by_date.get(date)
                if not hist_row: continue
                for p in periods:
                    col = f"next_{p}_return"
                    rv = safe_float(hist_row.get(col))
                    if rv is not None:
                        future_returns[p].append(rv)
                    # 也算超额
                    col_e = f"next_{p}_excess_vs_chain"
                    if col_e:
                        ev = safe_float(hist_row.get(col_e))
                        if ev is not None:
                            future_returns.setdefault(f"{p}_exc", []).append(ev)

            result["buckets"][label] = {
                "n": len(matching),
                **{f"abs_{p}": stat_block(future_returns.get(p, [])) for p in periods},
                **{f"exc_{p}": stat_block(future_returns.get(f"{p}_exc", [])) for p in periods},
            }
        return result

    extreme_5d  = extreme_reversal(rolling, "excess_5d",  ["1d", "3d", "5d"])
    extreme_10d = extreme_reversal(rolling, "excess_10d", ["1d", "3d", "5d"])

    # 4. 5d 超额变化率（一阶差分）：动量 vs 反转
    # delta_5d[t] = excess_5d[t] - excess_5d[t-1]，看下一日方向
    sorted_rolling = sorted(rolling, key=lambda r: r["date"])
    delta_pairs = []  # (delta_5d, next_1d_return, next_1d_excess_vs_chain)
    for i in range(1, len(sorted_rolling)):
        prev_e5 = safe_float(sorted_rolling[i-1]["excess_5d"])
        curr_e5 = safe_float(sorted_rolling[i]["excess_5d"])
        if prev_e5 is None or curr_e5 is None: continue
        delta = curr_e5 - prev_e5
        date = sorted_rolling[i]["date"]
        h = history_by_date.get(date)
        if not h: continue
        n1 = safe_float(h.get("next_1d_return"))
        n1e = safe_float(h.get("next_1d_excess_vs_chain"))
        if n1 is None: continue
        delta_pairs.append((delta, n1, n1e if n1e is not None else 0))

    # 把 delta 分五档看反转效力
    sorted_pairs = sorted(delta_pairs, key=lambda p: p[0])
    n = len(sorted_pairs)
    qsize = max(1, n // 5)
    delta_quintiles = []
    for q in range(5):
        s, e = q * qsize, (q + 1) * qsize if q < 4 else n
        chunk = sorted_pairs[s:e]
        chunk_n1 = [p[1] for p in chunk]
        chunk_n1e = [p[2] for p in chunk]
        delta_quintiles.append({
            "quintile": q + 1,
            "label": ["最快下降(Δ最负)", "下降", "中性", "上升", "最快上升(Δ最正)"][q],
            "deltaRange": [round(chunk[0][0], 2), round(chunk[-1][0], 2)] if chunk else None,
            "n": len(chunk),
            "abs1d": stat_block(chunk_n1),
            "exc1d": stat_block(chunk_n1e),
        })

    # Pearson r：delta 与 next_1d 的相关性
    delta_corr_abs = pearson([p[0] for p in delta_pairs], [p[1] for p in delta_pairs])
    delta_corr_exc = pearson([p[0] for p in delta_pairs], [p[2] for p in delta_pairs])

    return {
        "distributionStats": dist_stats,
        "autocorrelationDecay": {
            "excess_5d":  decay_5d,
            "excess_10d": decay_10d,
        },
        "extremeReversal": {
            "by_excess_5d":  extreme_5d,
            "by_excess_10d": extreme_10d,
        },
        "deltaMomentum": {
            "quintiles": delta_quintiles,
            "pearsonR_abs": round(delta_corr_abs, 4) if delta_corr_abs else None,
            "pearsonR_exc": round(delta_corr_exc, 4) if delta_corr_exc else None,
        },
    }

# ─────────────────────────────────────────────────────────────────────────────
# N. 行业联动结构分析
# ─────────────────────────────────────────────────────────────────────────────

def analyze_pool_linkage(history: list[dict], pool_corr: list[dict]) -> dict:
    """
    1. 4 池子相关性的统计分布
    2. 脱钩信号：当 industry_chain 相关性 < P15 时的 T+1 反应
    3. 池子分散度（4 池相关性的标准差）vs T+1
    4. Lead-lag：用历史日期 t 和 t+k 的池子序列做 cross-corr
    """
    history_by_date = {r["date"]: r for r in history}

    # 1. 各池子 20d / 60d 相关性的分布
    pool_stats = {}
    for pool in POOLS:
        corr20 = [safe_float(c[pool]["corr20d"]) for c in pool_corr
                  if c.get(pool, {}).get("corr20d") is not None]
        corr60 = [safe_float(c[pool]["corr60d"]) for c in pool_corr
                  if c.get(pool, {}).get("corr60d") is not None]
        full = pool_corr[0].get(pool, {}).get("fullCorr") if pool_corr else None
        pool_stats[pool] = {
            "label": POOL_LABELS[pool],
            "fullSampleCorr": round(full, 3) if full else None,
            "corr20d_stats": {
                "n": len(corr20),
                "mean": round(sum(corr20) / len(corr20), 3) if corr20 else None,
                "min":  round(min(corr20), 3) if corr20 else None,
                "max":  round(max(corr20), 3) if corr20 else None,
                "p15":  round(percentile(corr20, 15), 3) if corr20 else None,
                "p85":  round(percentile(corr20, 85), 3) if corr20 else None,
            },
            "corr60d_stats": {
                "n": len(corr60),
                "mean": round(sum(corr60) / len(corr60), 3) if corr60 else None,
                "min":  round(min(corr60), 3) if corr60 else None,
                "max":  round(max(corr60), 3) if corr60 else None,
            },
        }

    # 2. 脱钩信号：每个池子分别测试，当 20d corr 落在 P15 以下时 T+1 反应
    decoupling_signal = {}
    for pool in POOLS:
        corr20_with_date = [
            (c["date"], safe_float(c[pool]["corr20d"]))
            for c in pool_corr
            if c.get(pool, {}).get("corr20d") is not None
        ]
        vals = [v for _, v in corr20_with_date]
        p15 = percentile(vals, 15)
        p85 = percentile(vals, 85)

        # 低相关（脱钩）
        decoupled_dates = [date for date, v in corr20_with_date if v <= p15]
        # 高相关（紧密耦合）
        coupled_dates = [date for date, v in corr20_with_date if v >= p85]

        def collect_returns(dates: list[str]) -> dict:
            out = {"abs1d": [], "exc1d": [], "abs3d": [], "exc3d": [], "abs5d": [], "exc5d": []}
            for d in dates:
                row = history_by_date.get(d)
                if not row: continue
                for k in ["1d", "3d", "5d"]:
                    av = safe_float(row.get(f"next_{k}_return"))
                    if av is not None: out[f"abs{k}"].append(av)
                    ev = safe_float(row.get(f"next_{k}_excess_vs_chain"))
                    if ev is not None: out[f"exc{k}"].append(ev)
            return out

        dec_data = collect_returns(decoupled_dates)
        cou_data = collect_returns(coupled_dates)

        decoupling_signal[pool] = {
            "label": POOL_LABELS[pool],
            "p15_threshold": round(p15, 3),
            "p85_threshold": round(p85, 3),
            "decoupled(P15-)": {
                "n": len(decoupled_dates),
                **{k: stat_block(v) for k, v in dec_data.items()},
            },
            "coupled(P85+)": {
                "n": len(coupled_dates),
                **{k: stat_block(v) for k, v in cou_data.items()},
            },
        }

    # 3. 池子分散度（4池 20d 相关性的标准差）
    dispersion_pairs = []  # (dispersion, next_1d_excess)
    for c in pool_corr:
        corrs = [safe_float(c[pool]["corr20d"]) for pool in POOLS]
        corrs = [v for v in corrs if v is not None]
        if len(corrs) < 4: continue
        mean = sum(corrs) / len(corrs)
        disp = (sum((v - mean) ** 2 for v in corrs) / len(corrs)) ** 0.5
        row = history_by_date.get(c["date"])
        if not row: continue
        e1 = safe_float(row.get("next_1d_excess_vs_chain"))
        if e1 is None: continue
        dispersion_pairs.append((disp, e1))

    # 把 dispersion 分三档
    sorted_disp = sorted(dispersion_pairs, key=lambda p: p[0])
    n = len(sorted_disp)
    third = n // 3
    dispersion_buckets = {}
    for i, (lo, hi, label) in enumerate([
        (0, third, "低分散(4池同步)"),
        (third, 2*third, "中分散"),
        (2*third, n, "高分散(4池分化)"),
    ]):
        chunk = sorted_disp[lo:hi]
        vals = [p[1] for p in chunk]
        dispersion_buckets[label] = {
            "n": len(chunk),
            "dispersionRange": [round(chunk[0][0], 3), round(chunk[-1][0], 3)] if chunk else None,
            "next1d_exc": stat_block(vals),
        }
    disp_corr = pearson([p[0] for p in dispersion_pairs], [p[1] for p in dispersion_pairs])

    # 4. Lead-lag：当 industry_chain corr 20d 大幅下降（脱钩转向）后的 T+1
    lead_lag = {}
    for pool in POOLS:
        sorted_corr = sorted(
            [(c["date"], safe_float(c[pool]["corr20d"])) for c in pool_corr
             if c.get(pool, {}).get("corr20d") is not None],
            key=lambda p: p[0]
        )
        # 计算 5 日相关性变化
        change_pairs = []
        for i in range(5, len(sorted_corr)):
            prev = sorted_corr[i-5][1]
            curr = sorted_corr[i][1]
            if prev is None or curr is None: continue
            delta = curr - prev
            date = sorted_corr[i][0]
            row = history_by_date.get(date)
            if not row: continue
            e1 = safe_float(row.get("next_1d_excess_vs_chain"))
            if e1 is None: continue
            change_pairs.append((delta, e1))

        # 按 delta 三档
        sorted_change = sorted(change_pairs, key=lambda p: p[0])
        n = len(sorted_change)
        third = n // 3
        buckets = {}
        for i, (lo, hi, label) in enumerate([
            (0, third, f"相关性快速下降(脱钩中)"),
            (third, 2*third, "相关性平稳"),
            (2*third, n, "相关性快速上升(回归)"),
        ]):
            chunk = sorted_change[lo:hi]
            vals = [p[1] for p in chunk]
            buckets[label] = {
                "n": len(chunk),
                "deltaRange": [round(chunk[0][0], 3), round(chunk[-1][0], 3)] if chunk else None,
                "next1d_exc": stat_block(vals),
            }
        lead_lag[pool] = {"label": POOL_LABELS[pool], "buckets": buckets}

    return {
        "poolDistribution": pool_stats,
        "decouplingSignal": decoupling_signal,
        "dispersion": {
            "buckets": dispersion_buckets,
            "pearsonR": round(disp_corr, 4) if disp_corr else None,
        },
        "correlationLeadLag": lead_lag,
    }

# ─────────────────────────────────────────────────────────────────────────────
# P. 机器学习模型（Walk-forward 严格回测）
# ─────────────────────────────────────────────────────────────────────────────

def build_feature_matrix(history: list[dict], rolling: list[dict], pool_corr: list[dict]):
    """
    构造特征矩阵 X 和目标 y。
    特征来源：
      - 当日数值：anchor_return, rs_vs_chain, direct_up_ratio, moneyflow, amount_expansion
      - 滚动：excess_5d, excess_10d, outperform_streak, beta_streak
      - 池子相关性：industry_chain_corr20d, direct_corr20d
      - lag 特征：anchor_return_lag1/lag3
      - 状态：industry_beta_pos/neg, anchor_alpha_pos/neg
    目标：next_1d_excess_vs_chain
    """
    rolling_by_date = {r["date"]: r for r in rolling}
    pool_corr_by_date = {c["date"]: c for c in pool_corr}

    rows_sorted = sorted(history, key=lambda r: r["date"])

    X_list, y_list, dates = [], [], []

    feature_names = [
        "anchor_return",
        "rs_vs_chain", "rs_vs_direct",
        "direct_up_ratio", "chain_up_ratio",
        "moneyflow_positive", "amount_expansion",
        "excess_5d", "excess_10d",
        "outperform_streak", "beta_streak",
        "chain_corr_20d", "direct_corr_20d",
        "theme_corr_20d", "trading_corr_20d",
        "anchor_return_lag1", "anchor_return_lag3", "anchor_return_lag5",
        "rs_chain_lag1", "rs_chain_lag3",
        "anchor_return_5d_mean", "anchor_return_5d_std",
        "industry_beta_pos", "industry_beta_neg",
        "anchor_alpha_pos", "anchor_alpha_neg",
        "signal_count",
    ]

    for i, row in enumerate(rows_sorted):
        date = row["date"]
        # 目标
        y = safe_float(row.get("next_1d_excess_vs_chain"))
        if y is None: continue

        # 当日数值
        ar = safe_float(row.get("anchor_return"))
        rs_chain = safe_float(row.get("relative_strength_vs_industry_chain"))
        rs_direct = safe_float(row.get("relative_strength_vs_direct"))
        dur = safe_float(row.get("direct_up_ratio"))
        cur = safe_float(row.get("chain_up_ratio"))
        mf = safe_float(row.get("moneyflow_positive_ratio"))
        ae = safe_float(row.get("amount_expansion_ratio"))
        if ar is None: continue  # 跳过空行

        # rolling
        roll = rolling_by_date.get(date, {})
        e5  = safe_float(roll.get("excess_5d"))
        e10 = safe_float(roll.get("excess_10d"))
        os  = safe_float(roll.get("outperform_streak"))
        bs  = safe_float(roll.get("beta_streak"))

        # 池子相关性
        pc = pool_corr_by_date.get(date, {})
        cc20 = safe_float(pc.get("industryChain", {}).get("corr20d")) if pc else None
        dc20 = safe_float(pc.get("directPeers", {}).get("corr20d")) if pc else None
        tc20 = safe_float(pc.get("themePool", {}).get("corr20d")) if pc else None
        wc20 = safe_float(pc.get("tradingWatchlist", {}).get("corr20d")) if pc else None

        # lag 特征
        ar_lag1 = safe_float(rows_sorted[i-1]["anchor_return"]) if i >= 1 else None
        ar_lag3 = safe_float(rows_sorted[i-3]["anchor_return"]) if i >= 3 else None
        ar_lag5 = safe_float(rows_sorted[i-5]["anchor_return"]) if i >= 5 else None
        rs_lag1 = safe_float(rows_sorted[i-1]["relative_strength_vs_industry_chain"]) if i >= 1 else None
        rs_lag3 = safe_float(rows_sorted[i-3]["relative_strength_vs_industry_chain"]) if i >= 3 else None

        # 滚动 5d 统计
        if i >= 5:
            window = [safe_float(rows_sorted[j]["anchor_return"]) for j in range(i-5, i)]
            window = [v for v in window if v is not None]
            ar_5d_mean = sum(window) / len(window) if window else None
            if window:
                m = ar_5d_mean
                ar_5d_std = (sum((v - m) ** 2 for v in window) / len(window)) ** 0.5
            else:
                ar_5d_std = None
        else:
            ar_5d_mean = ar_5d_std = None

        # 状态 one-hot
        beta = (row.get("industry_beta") or "neutral").strip().lower()
        alpha = (row.get("anchor_alpha") or "neutral").strip().lower()
        beta_pos = 1.0 if beta == "positive" else 0.0
        beta_neg = 1.0 if beta == "negative" else 0.0
        alpha_pos = 1.0 if alpha == "positive" else 0.0
        alpha_neg = 1.0 if alpha == "negative" else 0.0

        # signal count
        sigs = row.get("signal_labels") or ""
        sig_count = len([s for s in sigs.split(",") if s.strip()])

        # 组装特征向量（缺失值用 0 填充，保留 lag 缺失的天数）
        def fill(v): return v if v is not None else 0.0

        x = [
            fill(ar),
            fill(rs_chain), fill(rs_direct),
            fill(dur), fill(cur),
            fill(mf), fill(ae),
            fill(e5), fill(e10),
            fill(os), fill(bs),
            fill(cc20), fill(dc20),
            fill(tc20), fill(wc20),
            fill(ar_lag1), fill(ar_lag3), fill(ar_lag5),
            fill(rs_lag1), fill(rs_lag3),
            fill(ar_5d_mean), fill(ar_5d_std),
            beta_pos, beta_neg,
            alpha_pos, alpha_neg,
            float(sig_count),
        ]

        X_list.append(x)
        y_list.append(y)
        dates.append(date)

    return np.array(X_list), np.array(y_list), dates, feature_names


def walk_forward_evaluate(X, y, dates, feature_names, train_window: int = 120):
    """
    Walk-forward validation：
      - 每次用前 train_window 天训练，预测当前一天
      - 评估：方向命中率、Pearson r、MAE
      - 测试模型：Ridge / RandomForest / GradientBoosting
    """
    n = len(X)
    if n < train_window + 20:
        return {"error": f"样本不足，需要 >= {train_window + 20}"}

    models = {
        "Ridge(α=1.0)":    lambda: Ridge(alpha=1.0),
        "RandomForest":    lambda: RandomForestRegressor(n_estimators=100, max_depth=5,
                                                         min_samples_leaf=5, random_state=42),
        "GradientBoosting":lambda: GradientBoostingRegressor(n_estimators=100, max_depth=3,
                                                              learning_rate=0.05, random_state=42),
    }

    results = {}

    for name, model_factory in models.items():
        preds, actuals = [], []
        feat_importances = []

        for i in range(train_window, n):
            X_train = X[i - train_window:i]
            y_train = y[i - train_window:i]
            X_test  = X[i:i+1]
            y_test  = y[i]

            model = model_factory()
            model.fit(X_train, y_train)
            pred = model.predict(X_test)[0]
            preds.append(pred)
            actuals.append(y_test)

            # 收集特征重要性（最后一次的）
            if i == n - 1:
                if hasattr(model, "feature_importances_"):
                    feat_importances = list(model.feature_importances_)
                elif hasattr(model, "coef_"):
                    feat_importances = list(np.abs(model.coef_))

        # 评估
        preds_a = np.array(preds)
        actuals_a = np.array(actuals)
        # 方向命中率
        sign_match = ((preds_a > 0) == (actuals_a > 0)).sum() / len(preds_a)
        # Pearson r
        if len(preds_a) > 5:
            xs = preds_a.tolist()
            ys = actuals_a.tolist()
            r = pearson(xs, ys)
        else:
            r = None
        # MAE
        mae = float(np.mean(np.abs(preds_a - actuals_a)))
        # 按预测分五档看真实收益
        pairs = list(zip(preds, actuals))
        sorted_pairs = sorted(pairs, key=lambda p: p[0])
        qsize = max(1, len(sorted_pairs) // 5)
        quintiles = []
        for q in range(5):
            s, e = q * qsize, (q + 1) * qsize if q < 4 else len(sorted_pairs)
            chunk = sorted_pairs[s:e]
            chunk_ys = [y for _, y in chunk]
            chunk_xs = [x for x, _ in chunk]
            hits = sum(1 for x, y in chunk if (x > 0) == (y > 0))
            quintiles.append({
                "quintile": q + 1,
                "predRange": [round(min(chunk_xs), 3), round(max(chunk_xs), 3)] if chunk_xs else None,
                "n": len(chunk),
                "actual_exc1d": stat_block(chunk_ys),
                "direction_hit_rate": round(hits / len(chunk), 3) if chunk else None,
            })

        # 特征重要性排序
        if feat_importances:
            fi_list = sorted(
                [{"feature": f, "importance": round(float(v), 4)}
                 for f, v in zip(feature_names, feat_importances)],
                key=lambda x: x["importance"], reverse=True
            )[:15]  # top 15
        else:
            fi_list = []

        results[name] = {
            "test_samples": len(preds),
            "direction_accuracy": round(float(sign_match), 4),
            "pearson_r": round(r, 4) if r else None,
            "mae": round(mae, 4),
            "quintile_test": quintiles,
            "top_features": fi_list,
        }

    return results


# ─────────────────────────────────────────────────────────────────────────────
# 打印工具
# ─────────────────────────────────────────────────────────────────────────────

def print_excess_analysis(M: dict) -> None:
    print_section("M. 5d/10d 滚动超额的均值回归量化")

    # 分布
    print("\n  ▎分布统计（验证均值是否真的接近 0）")
    for k, s in M["distributionStats"].items():
        if not s: continue
        sig = "❗显著偏离零" if s["significant_vs_zero"] else "✓ 接近零"
        print(f"  {k}: mean={s['mean']:+.3f}, std={s['std']:.3f}, t={s['t_stat']:+.2f}  {sig}")

    # 自相关
    print("\n  ▎自相关衰减（半衰期估计）")
    for k, d in M["autocorrelationDecay"].items():
        if not d: continue
        hl = d.get("half_life_days")
        hl_str = f"{hl}天" if hl else "未在30天内降到0.5"
        print(f"  {k}: lag1={d['lag1']:+.3f}, lag5={d['lag5']:+.3f}, lag10={d['lag10']:+.3f}, "
              f"lag20={d['lag20']:+.3f}  | 半衰期={hl_str}")

    # 极端档反转
    print("\n  ▎5d 超额分档 → 后续 T+1/T+3/T+5 反应")
    e5 = M["extremeReversal"]["by_excess_5d"]
    t = e5["thresholds"]
    print(f"  阈值：P15={t['p15']:+.2f}%  P30={t['p30']:+.2f}%  P70={t['p70']:+.2f}%  P85={t['p85']:+.2f}%")
    print(f"  {'档位':<14} {'n':>4}  {'T+1绝对':>8} {'T+1超额':>8}  {'T+3绝对':>8} {'T+3超额':>8}  胜率")
    print(f"  {'-'*75}")
    for label, b in e5["buckets"].items():
        a1 = b.get("abs_1d", {}); e1 = b.get("exc_1d", {})
        a3 = b.get("abs_3d", {}); e3 = b.get("exc_3d", {})
        print(f"  {label:<14} {b['n']:>4}  "
              f"{fmt_pct(a1.get('avg')):>8} {fmt_pct(e1.get('avg')):>8}  "
              f"{fmt_pct(a3.get('avg')):>8} {fmt_pct(e3.get('avg')):>8}  "
              f"{a1.get('wr', 0)*100:.0f}%")

    print("\n  ▎10d 超额分档")
    e10 = M["extremeReversal"]["by_excess_10d"]
    t = e10["thresholds"]
    print(f"  阈值：P15={t['p15']:+.2f}%  P85={t['p85']:+.2f}%")
    for label, b in e10["buckets"].items():
        a1 = b.get("abs_1d", {}); e1 = b.get("exc_1d", {})
        print(f"  {label:<14} {b['n']:>4}  T+1绝对={fmt_pct(a1.get('avg'))} T+1超额={fmt_pct(e1.get('avg'))} 胜率={a1.get('wr', 0)*100:.0f}%")

    # delta 动量
    print("\n  ▎5d 超额变化率 Δ → T+1 反应（短期反转 vs 动量）")
    dm = M["deltaMomentum"]
    print(f"  Pearson r: Δ vs T+1 绝对收益 = {dm['pearsonR_abs']:+.4f}")
    print(f"  Pearson r: Δ vs T+1 超额收益 = {dm['pearsonR_exc']:+.4f}")
    for q in dm["quintiles"]:
        e1 = q.get("exc1d", {})
        rng = f"[{q['deltaRange'][0]:+.2f}, {q['deltaRange'][1]:+.2f}]"
        print(f"  {q['label']:<16} {rng:>20}  n={q['n']}  T+1超额={fmt_pct(e1.get('avg'))} 胜率={e1.get('wr', 0)*100:.0f}%")


def print_pool_linkage(N: dict) -> None:
    print_section("N. 行业联动结构分析")

    # 分布
    print("\n  ▎各池子 20d/60d 相关性的统计分布")
    print(f"  {'池子':<12} {'全样本r':>8}  {'20d均值':>8}  {'20d最小':>8}  {'20d最大':>8}  {'P15':>7}  {'P85':>7}")
    for pool, s in N["poolDistribution"].items():
        c20 = s.get("corr20d_stats", {})
        print(f"  {s['label']:<12} {fmt_num(s.get('fullSampleCorr')):>8}  "
              f"{fmt_num(c20.get('mean')):>8}  {fmt_num(c20.get('min')):>8}  "
              f"{fmt_num(c20.get('max')):>8}  {fmt_num(c20.get('p15')):>7}  {fmt_num(c20.get('p85')):>7}")

    # 脱钩 vs 紧密耦合
    print("\n  ▎脱钩信号：当池子 20d 相关性进入 P15(脱钩)/P85(紧密) 时的 T+1 反应")
    for pool, sig in N["decouplingSignal"].items():
        dec = sig["decoupled(P15-)"]
        cou = sig["coupled(P85+)"]
        de1 = dec.get("exc1d", {})
        ce1 = cou.get("exc1d", {})
        print(f"  {sig['label']:<10} "
              f"脱钩(n={dec['n']}): T+1超额={fmt_pct(de1.get('avg'))} 胜率={de1.get('wr', 0)*100:.0f}%  | "
              f"紧密(n={cou['n']}): T+1超额={fmt_pct(ce1.get('avg'))} 胜率={ce1.get('wr', 0)*100:.0f}%")

    # 分散度
    print("\n  ▎4 池相关性的分散度（标准差） vs T+1 超额")
    disp = N["dispersion"]
    print(f"  Pearson r = {disp['pearsonR']:+.4f}")
    for label, b in disp["buckets"].items():
        e1 = b.get("next1d_exc", {})
        rng = f"[{b['dispersionRange'][0]:.3f}, {b['dispersionRange'][1]:.3f}]"
        print(f"  {label:<16} {rng:>22}  n={b['n']}  T+1超额={fmt_pct(e1.get('avg'))} 胜率={e1.get('wr', 0)*100:.0f}%")

    # Lead-lag
    print("\n  ▎相关性 5 日变化 → T+1 反应（识别脱钩转向）")
    for pool, ll in N["correlationLeadLag"].items():
        print(f"\n  {ll['label']}：")
        for label, b in ll["buckets"].items():
            e1 = b.get("next1d_exc", {})
            print(f"    {label:<20} n={b['n']}  T+1超额={fmt_pct(e1.get('avg'))} 胜率={e1.get('wr', 0)*100:.0f}%")


def print_ml_results(P: dict) -> None:
    print_section("P. 机器学习模型（Walk-forward 严格回测）")

    if "error" in P:
        print(f"  ⚠️  {P['error']}")
        return

    for model_name, r in P.items():
        print(f"\n  ━━ {model_name} ━━")
        print(f"  测试样本：{r['test_samples']}")
        print(f"  方向命中率：{r['direction_accuracy']*100:.1f}%   "
              f"Pearson r：{r.get('pearson_r', 0):+.4f}   "
              f"MAE：{r['mae']:.4f}")
        # 五分位
        print(f"  ▎分五档（按预测分排序，看实际 T+1 超额）")
        print(f"  {'分档':>4} {'预测区间':>20} {'n':>4}  {'实际T+1超额':>12}  {'方向命中':>8}")
        for q in r["quintile_test"]:
            rng = f"[{q['predRange'][0]:+.3f}, {q['predRange'][1]:+.3f}]"
            a = q.get("actual_exc1d", {})
            hit = q.get("direction_hit_rate")
            print(f"  Q{q['quintile']:>1}  {rng:>20}  {q['n']:>4}  "
                  f"{fmt_pct(a.get('avg')):>12}  {hit*100:.0f}%")
        # Top 特征
        if r.get("top_features"):
            print(f"\n  ▎Top 10 特征重要性")
            for fi in r["top_features"][:10]:
                bar = "█" * int(fi["importance"] * 50)
                print(f"    {fi['feature']:<24} {fi['importance']:>7.4f}  {bar}")


# ─────────────────────────────────────────────────────────────────────────────
# 主函数
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  深度量化分析（M 超额均值回归 + N 行业联动 + P 机器学习）")
    print("=" * 70)

    history, rolling, pool_corr = load_all()

    print("\n[INFO] 计算 M. 5d/10d 超额均值回归量化...")
    M = analyze_excess_mean_reversion(history, rolling)

    print("[INFO] 计算 N. 行业联动结构分析...")
    N = analyze_pool_linkage(history, pool_corr)

    print("[INFO] 构造特征矩阵...")
    X, y, dates, feature_names = build_feature_matrix(history, rolling, pool_corr)
    print(f"  特征矩阵 shape: {X.shape}, 目标 y 长度: {len(y)}, 特征数: {len(feature_names)}")

    print("[INFO] 计算 P. 机器学习模型（walk-forward 训练）...")
    P = walk_forward_evaluate(X, y, dates, feature_names, train_window=120)

    # 打印
    print_excess_analysis(M)
    print_pool_linkage(N)
    print_ml_results(P)

    # 输出 JSON
    output = {
        "generatedAt": history[-1]["date"] if history else "",
        "M_excessMeanReversion": M,
        "N_poolLinkage": N,
        "P_machineLearning": P,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    sz = os.path.getsize(OUTPUT_JSON) / 1024
    print(f"\n[OK] 结果写入：{OUTPUT_JSON}  ({sz:.1f} KB)")


if __name__ == "__main__":
    main()
