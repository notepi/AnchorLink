"""
二阶信号分析脚本（扩展版）
===========================
从现有数据计算六类二阶信号：

  A. 象限路径信号（2-gram）：(昨日象限, 今日象限) → T+1/T+3/T+5 期望
  B. 信号 Delta：今日新增/消失信号 vs 持续信号的 T+1/T+3/T+5 差异
  C. 象限 Streak：在同一象限连续 N 天的 T+1/T+3/T+5 均值回归测试
  D. 综合信号分：当日所有激活信号的 lift 加权求和与 T+1/T+3/T+5 的相关性
  E. 相似度加权 kNN 预测：以相似案例 similarity 为权重预测未来涨幅
  F. 三周期一致性信号：T+1/T+3/T+5 方向一致的信号，比单周期更稳定

输出：
  data/output/history_2nd_order_analysis.json
"""

from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
HISTORY_CSV   = ROOT / "data/output/history_summary.csv"
LIFT_CSV      = ROOT / "data/output/history_signal_lift.csv"
ROLLING_CSV   = ROOT / "data/output/history_rolling_metrics.csv"
DASHBOARD_JSON = ROOT / "data/output/dashboard_view.json"
OUTPUT_JSON   = ROOT / "data/output/history_2nd_order_analysis.json"

PERIODS = ["1d", "3d", "5d"]
PERIOD_COLS       = {"1d": "next_1d_return",           "3d": "next_3d_return",           "5d": "next_5d_return"}
EXCESS_PERIOD_COLS = {"1d": "next_1d_excess_vs_chain", "3d": "next_3d_excess_vs_chain",  "5d": "next_5d_excess_vs_chain"}

# ── 工具函数 ──────────────────────────────────────────────────────────────────

def safe_float(v: object) -> float | None:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

def safe_avg(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None

def safe_wr(vals: list[float]) -> float | None:
    return sum(1 for v in vals if v > 0) / len(vals) if vals else None

def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 5:
        return None
    mx, my = sum(xs)/n, sum(ys)/n
    num  = sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    dx   = sum((x-mx)**2 for x in xs)
    dy   = sum((y-my)**2 for y in ys)
    denom = math.sqrt(dx*dy)
    return num/denom if denom > 0 else None

def fmt_pct(v: float | None) -> str:
    if v is None: return "  -   "
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"

def fmt_wr(v: float | None) -> str:
    if v is None: return " -  "
    return f"{v*100:.0f}%"

def state_key(row: dict) -> str:
    beta  = (row.get("industry_beta")  or "neutral").strip().lower()
    alpha = (row.get("anchor_alpha")   or "neutral").strip().lower()
    return f"{beta}+{alpha}"

STATE_LABELS = {
    "positive+positive": "行业强+个股强", "positive+neutral": "行业强+个股中",
    "positive+negative": "行业强+个股弱", "neutral+positive": "行业中+个股强",
    "neutral+neutral":   "行业中+个股中", "neutral+negative": "行业中+个股弱",
    "negative+positive": "行业弱+个股强", "negative+neutral": "行业弱+个股中",
    "negative+negative": "行业弱+个股弱",
}
def state_label(k: str) -> str: return STATE_LABELS.get(k, k)

def parse_signals(raw: object) -> set[str]:
    if not raw: return set()
    return {s.strip() for s in str(raw).split(",") if s.strip()}

def stat_block(vals: list[float]) -> dict:
    return {
        "count": len(vals),
        "avg":   round(safe_avg(vals) or 0, 4),
        "wr":    round(safe_wr(vals)  or 0, 4),
        "p50":   round(sorted(vals)[len(vals)//2], 4) if vals else 0,
    }

# ── 数据加载 ──────────────────────────────────────────────────────────────────

def load_history() -> list[dict]:
    rows = []
    with open(HISTORY_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    rows.sort(key=lambda r: r.get("date") or "")
    print(f"[INFO] history_summary: {len(rows)} 行")
    return rows

def load_lift_map() -> dict[str, float]:
    m: dict[str, float] = {}
    with open(LIFT_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            label = (row.get("label") or row.get("signal_label") or "").strip()
            v = safe_float(row.get("avg_next_1d"))
            if label and v is not None:
                m[label] = v
    print(f"[INFO] signal_lift: {len(m)} 个信号")
    return m

def load_dashboard() -> dict:
    with open(DASHBOARD_JSON, encoding="utf-8") as f:
        return json.load(f)

def load_rolling() -> list[dict]:
    if not ROLLING_CSV.exists():
        print(f"[WARN] {ROLLING_CSV} 不存在，跳过滚动指标")
        return []
    rows = []
    with open(ROLLING_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    rows.sort(key=lambda r: r.get("date") or "")
    return rows

# ── A. 2-gram 路径信号（三周期） ──────────────────────────────────────────────

def compute_gram2(rows: list[dict]) -> list[dict]:
    groups: dict[tuple[str,str], dict[str, list[float]]] = defaultdict(lambda: {p:[] for p in PERIODS})
    for i in range(1, len(rows)):
        from_s, to_s = state_key(rows[i-1]), state_key(rows[i])
        for p, col in PERIOD_COLS.items():
            v = safe_float(rows[i].get(col))
            if v is not None:
                groups[(from_s, to_s)][p].append(v)

    result = []
    for (from_s, to_s), pdata in groups.items():
        n1 = len(pdata["1d"])
        if n1 < 3: continue
        entry = {
            "fromState": from_s, "fromLabel": state_label(from_s),
            "toState":   to_s,   "toLabel":   state_label(to_s),
        }
        for p in PERIODS:
            entry[p] = stat_block(pdata[p])
        result.append(entry)

    result.sort(key=lambda x: abs(x["1d"]["avg"]), reverse=True)
    return result

# ── B. 信号 Delta（三周期） ───────────────────────────────────────────────────

def compute_signal_delta(rows: list[dict]) -> list[dict]:
    new_g:  dict[str, dict[str, list[float]]] = defaultdict(lambda: {p:[] for p in PERIODS})
    cont_g: dict[str, dict[str, list[float]]] = defaultdict(lambda: {p:[] for p in PERIODS})
    gone_g: dict[str, dict[str, list[float]]] = defaultdict(lambda: {p:[] for p in PERIODS})

    for i in range(1, len(rows)):
        today_s     = parse_signals(rows[i].get("signal_labels"))
        yesterday_s = parse_signals(rows[i-1].get("signal_labels"))
        for p, col in PERIOD_COLS.items():
            t = safe_float(rows[i].get(col))
            if t is None: continue
            for s in today_s - yesterday_s: new_g[s][p].append(t)
            for s in today_s & yesterday_s: cont_g[s][p].append(t)
            for s in yesterday_s - today_s: gone_g[s][p].append(t)

    all_sigs = set(new_g) | set(cont_g) | set(gone_g)
    result = []
    for sig in sorted(all_sigs):
        entry: dict = {"signal": sig}
        for role, g in [("new", new_g), ("continued", cont_g), ("gone", gone_g)]:
            entry[role] = {}
            for p in PERIODS:
                entry[role][p] = stat_block(g[sig][p]) if sig in g else {"count":0,"avg":0,"wr":0,"p50":0}
        # 新增 vs 持续 差值（T+1）
        n_avg = entry["new"]["1d"]["avg"]  if entry["new"]["1d"]["count"]  >= 5 else None
        c_avg = entry["continued"]["1d"]["avg"] if entry["continued"]["1d"]["count"] >= 5 else None
        entry["newVsContinued1d"] = round(n_avg - c_avg, 4) if (n_avg is not None and c_avg is not None) else None
        result.append(entry)

    result.sort(
        key=lambda x: abs(x["newVsContinued1d"]) if x["newVsContinued1d"] is not None else 0,
        reverse=True,
    )
    return result

# ── C. 象限 Streak（三周期） ─────────────────────────────────────────────────

def compute_streak(rows: list[dict]) -> dict[str, dict]:
    if not rows: return {}
    cur_state, cur_streak = state_key(rows[0]), 1
    streaks: list[tuple[str, int, dict[str, float | None]]] = []

    for i in range(1, len(rows)):
        s = state_key(rows[i])
        cur_streak = cur_streak + 1 if s == cur_state else 1
        cur_state = s
        returns = {p: safe_float(rows[i].get(col)) for p, col in PERIOD_COLS.items()}
        streaks.append((s, cur_streak, returns))

    groups: dict[str, dict[str, dict[str, list[float]]]] = {}
    for state, streak, returns in streaks:
        bucket = str(streak) if streak <= 4 else "5+"
        if state not in groups: groups[state] = {}
        if bucket not in groups[state]: groups[state][bucket] = {p:[] for p in PERIODS}
        for p in PERIODS:
            if returns[p] is not None:
                groups[state][bucket][p].append(returns[p])

    out: dict[str, dict] = {}
    for state, buckets in groups.items():
        total = sum(len(v["1d"]) for v in buckets.values())
        if total < 8: continue
        out[state] = {"label": state_label(state), "byStreak": {}}
        for bucket, pdata in sorted(buckets.items(), key=lambda x:(len(x[0]),x[0])):
            if not pdata["1d"]: continue
            out[state]["byStreak"][bucket] = {p: stat_block(pdata[p]) for p in PERIODS}
    return out

# ── D. 综合信号分（三周期） ───────────────────────────────────────────────────

def compute_composite(rows: list[dict], lift_map: dict[str, float]) -> dict:
    data: dict[str, list] = {p: [] for p in PERIODS}  # list of (score, return)

    for row in rows:
        sigs = parse_signals(row.get("signal_labels"))
        sig_lifts = [lift_map[s] for s in sigs if s in lift_map]
        if not sig_lifts: continue
        score = sum(sig_lifts) / len(sig_lifts)
        for p, col in PERIOD_COLS.items():
            v = safe_float(row.get(col))
            if v is not None:
                data[p].append((score, v))

    result: dict = {}
    for p in PERIODS:
        pairs = data[p]
        xs, ys = [x for x,_ in pairs], [y for _,y in pairs]
        corr = pearson(xs, ys)
        # 十等分
        n = len(pairs)
        combined = sorted(pairs, key=lambda x: x[0])
        dsz = max(1, n // 10)
        deciles = []
        for d in range(10):
            s, e = d*dsz, (d+1)*dsz if d < 9 else n
            chunk = combined[s:e]
            chunk_ys = [y for _, y in chunk]
            deciles.append({
                "decile": d+1,
                "scoreRange": [round(chunk[0][0],3), round(chunk[-1][0],3)],
                **stat_block(chunk_ys),
            })
        result[p] = {"corrWithReturn": round(corr,4) if corr else None,
                     "sampleCount": n, "byDecile": deciles}
    return result

# ── E. 相似度加权 kNN 预测信号 ────────────────────────────────────────────────
# [WARNING] kNN预测方向命中率48.5%，低于随机基准（50%），不建议作为信号使用。
# 复合得分（r=0.222）和二元路径标签的预测效力优于kNN，应优先使用。

def compute_knn_signal(dashboard: dict, rows: list[dict]) -> dict:
    """
    对每个历史日期，从 dateIndex 读取已计算的 similarCases（top-12）。
    用 similarity 为权重，加权平均 next_1d/3d/5d_return。
    评估加权预测 vs 实际 return 的 Pearson r。
    同时评估"方向命中率"（预测正确涨跌方向的比例）。
    """
    date_index = dashboard.get("dateIndex", {})
    rows_by_date = {str(r.get("date")): r for r in rows}

    pred_vs_actual: dict[str, list[tuple[float,float]]] = {p:[] for p in PERIODS}
    daily_knn: list[dict] = []

    period_fields = {
        "1d": "next1dReturn",
        "3d": "next3dReturn",
        "5d": "next5dReturn",
    }

    for date_str, entry in sorted(date_index.items()):
        similar_cases = entry.get("similarCases", [])
        if not similar_cases:
            continue

        # 加权预测
        knn_pred: dict[str, float | None] = {}
        for p, field in period_fields.items():
            total_sim, total_weighted = 0.0, 0.0
            for case in similar_cases:
                sim = safe_float(case.get("similarity"))
                ret = safe_float(case.get(field))
                if sim is None or ret is None: continue
                total_sim += sim
                total_weighted += sim * ret
            knn_pred[p] = total_weighted / total_sim if total_sim > 0 else None

        # 实际值
        actual_row = rows_by_date.get(date_str)
        if not actual_row:
            continue

        daily_entry: dict = {"date": date_str, "knnPred": {}, "actual": {}, "correct": {}}
        for p, col in PERIOD_COLS.items():
            actual = safe_float(actual_row.get(col))
            pred = knn_pred.get(p)
            daily_entry["knnPred"][p] = round(pred, 4) if pred is not None else None
            daily_entry["actual"][p] = round(actual, 4) if actual is not None else None
            if pred is not None and actual is not None:
                pred_vs_actual[p].append((pred, actual))
                daily_entry["correct"][p] = (pred > 0) == (actual > 0)

        daily_knn.append(daily_entry)

    # 统计
    stats: dict[str, dict] = {}
    for p in PERIODS:
        pairs = pred_vs_actual[p]
        if not pairs:
            stats[p] = {}
            continue
        xs, ys = [x for x,_ in pairs], [y for _,y in pairs]
        corr = pearson(xs, ys)
        direction_hits = sum(1 for x,y in pairs if (x>0)==(y>0))
        direction_rate = direction_hits / len(pairs) if pairs else None
        # 按预测分五档看命中率
        sorted_pairs = sorted(pairs, key=lambda p: p[0])
        n = len(sorted_pairs)
        quintiles = []
        qsz = max(1, n//5)
        for q in range(5):
            s, e = q*qsz, (q+1)*qsz if q < 4 else n
            chunk = sorted_pairs[s:e]
            chunk_ys = [y for _,y in chunk]
            q_hit = sum(1 for x,y in chunk if (x>0)==(y>0))
            quintiles.append({
                "quintile": q+1,
                "predRange": [round(chunk[0][0],3), round(chunk[-1][0],3)],
                **stat_block(chunk_ys),
                "directionHit": round(q_hit/len(chunk),3) if chunk else None,
            })
        stats[p] = {
            "pearsonR": round(corr,4) if corr else None,
            "directionAccuracy": round(direction_rate,4) if direction_rate else None,
            "sampleCount": len(pairs),
            "byPredQuintile": quintiles,
        }

    return {"stats": stats, "daily": daily_knn}

# ── F. 三周期一致性信号 ───────────────────────────────────────────────────────

def compute_multi_period_consistency(rows: list[dict], lift_map: dict[str, float]) -> list[dict]:
    """
    对每个信号：看它激活时 T+1/T+3/T+5 方向是否一致（同正或同负）。
    一致性高 = 更可信的信号；方向翻转 = 短线弹后回落。
    """
    sig_groups: dict[str, dict[str, list[float]]] = defaultdict(lambda: {p:[] for p in PERIODS})

    for row in rows:
        sigs = parse_signals(row.get("signal_labels"))
        for s in sigs:
            for p, col in PERIOD_COLS.items():
                v = safe_float(row.get(col))
                if v is not None:
                    sig_groups[s][p].append(v)

    result = []
    for sig, pdata in sig_groups.items():
        n = len(pdata["1d"])
        if n < 8: continue

        avgs = {p: safe_avg(pdata[p]) for p in PERIODS}
        wrs  = {p: safe_wr(pdata[p])  for p in PERIODS}

        # 方向是否一致
        signs = [1 if (avgs[p] or 0) > 0 else -1 for p in PERIODS]
        all_same = len(set(signs)) == 1

        # 方向翻转点
        flip = None
        if signs[0] != signs[1]: flip = "T1→T3"
        elif signs[1] != signs[2]: flip = "T3→T5"

        result.append({
            "signal": sig,
            "lift1d": avgs.get("1d"),
            "lift3d": avgs.get("3d"),
            "lift5d": avgs.get("5d"),
            "wr1d": wrs.get("1d"),
            "wr3d": wrs.get("3d"),
            "wr5d": wrs.get("5d"),
            "count": n,
            "consistent": all_same,
            "flip": flip,
            "pattern": (
                "持续向上" if all_same and (avgs["1d"] or 0) > 0.3 else
                "持续向下" if all_same and (avgs["1d"] or 0) < -0.3 else
                "短线弹后回落" if (avgs.get("1d") or 0) > 0 and flip == "T1→T3" else
                "短线跌后回升" if (avgs.get("1d") or 0) < 0 and flip == "T1→T3" else
                "中性" if all_same else "方向不稳定"
            ),
        })

    result.sort(key=lambda x: abs(x.get("lift5d") or 0), reverse=True)
    return result

# ── G. 相对强度位置信号（Relative Strength Quintile）─────────────────────────
# 核心假设：铂力特 vs 产业链相对强度处于极端高位 → 均值回归；极端低位 → 反弹修复

def compute_rs_quintile(rows: list[dict]) -> dict:
    """
    把 relative_strength_vs_industry_chain 按历史五分位分档，
    计算每档下一期 T+1 绝对收益 + 超额收益。
    也分析 relative_strength_vs_direct（更纯粹的个股 Alpha 指标）。
    """
    rs_data_chain  = []  # (rs_value, abs_1d, excess_1d, abs_3d, excess_3d, abs_5d, excess_5d)
    rs_data_direct = []

    for row in rows:
        rs_chain  = safe_float(row.get("relative_strength_vs_industry_chain"))
        rs_direct = safe_float(row.get("relative_strength_vs_direct"))
        abs1  = safe_float(row.get("next_1d_return"))
        exc1  = safe_float(row.get("next_1d_excess_vs_chain"))
        abs3  = safe_float(row.get("next_3d_return"))
        exc3  = safe_float(row.get("next_3d_excess_vs_chain"))
        abs5  = safe_float(row.get("next_5d_return"))
        exc5  = safe_float(row.get("next_5d_excess_vs_chain"))

        if rs_chain is not None and abs1 is not None:
            rs_data_chain.append((rs_chain, abs1, exc1, abs3, exc3, abs5, exc5))
        if rs_direct is not None and abs1 is not None:
            rs_data_direct.append((rs_direct, abs1, exc1, abs3, exc3, abs5, exc5))

    def quintile_stats(data: list[tuple]) -> list[dict]:
        if not data:
            return []
        sorted_data = sorted(data, key=lambda x: x[0])
        n = len(sorted_data)
        qsz = max(1, n // 5)
        result = []
        for q in range(5):
            s, e = q * qsz, (q + 1) * qsz if q < 4 else n
            chunk = sorted_data[s:e]
            rs_vals  = [x[0] for x in chunk]
            abs1_v   = [x[1] for x in chunk]
            exc1_v   = [x[2] for x in chunk if x[2] is not None]
            abs3_v   = [x[3] for x in chunk if x[3] is not None]
            exc3_v   = [x[4] for x in chunk if x[4] is not None]
            abs5_v   = [x[5] for x in chunk if x[5] is not None]
            exc5_v   = [x[6] for x in chunk if x[6] is not None]
            result.append({
                "quintile": q + 1,
                "label": ["极弱（Q1）", "偏弱（Q2）", "中性（Q3）", "偏强（Q4）", "极强（Q5）"][q],
                "rsRange": [round(rs_vals[0], 2), round(rs_vals[-1], 2)],
                "n": len(chunk),
                "abs1d":  stat_block(abs1_v),
                "exc1d":  stat_block(exc1_v),
                "abs3d":  stat_block(abs3_v) if abs3_v else {},
                "exc3d":  stat_block(exc3_v) if exc3_v else {},
                "abs5d":  stat_block(abs5_v) if abs5_v else {},
                "exc5d":  stat_block(exc5_v) if exc5_v else {},
            })
        return result

    # Pearson r：rs vs 下一期 excess
    xs_chain  = [x[0] for x in rs_data_chain]
    exc1_chain = [x[2] for x in rs_data_chain if x[2] is not None]
    xs_chain_paired = [x[0] for x in rs_data_chain if x[2] is not None]

    return {
        "vsChain": {
            "quintiles": quintile_stats(rs_data_chain),
            "corrWithExcess1d": round(pearson(xs_chain_paired, exc1_chain) or 0, 4),
        },
        "vsDirect": {
            "quintiles": quintile_stats(rs_data_direct),
        },
    }


# ── H. 量价背离信号（Volume-Price Divergence）────────────────────────────────
# 经典量化逻辑：价格方向与资金流向/量能不一致时往往是反转信号

def compute_vol_price_divergence(rows: list[dict]) -> list[dict]:
    """
    构造 6 种量价背离信号（2 资金流向 + 4 量能组合），
    计算 T+1 绝对收益 + 超额收益。
    """
    # 信号定义：(name, filter_func)
    signals = [
        ("涨但资金背离",  lambda r: (safe_float(r.get("anchor_return")) or 0) > 0.5
                                   and (safe_float(r.get("moneyflow_positive_ratio")) or 0.5) < 0.4),
        ("跌但资金支撑",  lambda r: (safe_float(r.get("anchor_return")) or 0) < -0.5
                                   and (safe_float(r.get("moneyflow_positive_ratio")) or 0.5) > 0.6),
        ("放量大涨",     lambda r: (safe_float(r.get("anchor_return")) or 0) > 1.0
                                   and (safe_float(r.get("amount_expansion_ratio")) or 1.0) > 1.3),
        ("放量大跌",     lambda r: (safe_float(r.get("anchor_return")) or 0) < -1.0
                                   and (safe_float(r.get("amount_expansion_ratio")) or 1.0) > 1.3),
        ("缩量阴跌",     lambda r: (safe_float(r.get("anchor_return")) or 0) < -0.5
                                   and (safe_float(r.get("amount_expansion_ratio")) or 1.0) < 0.85),
        ("缩量滞涨",     lambda r: (safe_float(r.get("anchor_return")) or 0) > 0
                                   and (safe_float(r.get("amount_expansion_ratio")) or 1.0) < 0.75),
    ]

    result = []
    for name, filt in signals:
        abs1_v, exc1_v, abs3_v, exc3_v, abs5_v, exc5_v = [], [], [], [], [], []
        for row in rows:
            try:
                if not filt(row):
                    continue
            except Exception:
                continue
            a1 = safe_float(row.get("next_1d_return"))
            e1 = safe_float(row.get("next_1d_excess_vs_chain"))
            a3 = safe_float(row.get("next_3d_return"))
            e3 = safe_float(row.get("next_3d_excess_vs_chain"))
            a5 = safe_float(row.get("next_5d_return"))
            e5 = safe_float(row.get("next_5d_excess_vs_chain"))
            if a1 is not None: abs1_v.append(a1)
            if e1 is not None: exc1_v.append(e1)
            if a3 is not None: abs3_v.append(a3)
            if e3 is not None: exc3_v.append(e3)
            if a5 is not None: abs5_v.append(a5)
            if e5 is not None: exc5_v.append(e5)
        result.append({
            "signal": name,
            "n": len(abs1_v),
            "abs1d": stat_block(abs1_v),
            "exc1d": stat_block(exc1_v),
            "abs3d": stat_block(abs3_v) if abs3_v else {},
            "exc3d": stat_block(exc3_v) if exc3_v else {},
            "abs5d": stat_block(abs5_v) if abs5_v else {},
            "exc5d": stat_block(exc5_v) if exc5_v else {},
        })
    return result


# ── I. 板块扩散背离（Breadth Divergence）────────────────────────────────────
# 扩散指标捕捉"行业共振"vs"个股独秀"的差异，指导方向判断

def compute_breadth_divergence(rows: list[dict]) -> list[dict]:
    """
    构造 5 种板块扩散信号，分析 T+1/T+3/T+5 的绝对和超额收益。
    """
    signals = [
        ("个股独强(同业分化)",  lambda r:
            (safe_float(r.get("anchor_return")) or 0) > 0.5
            and (safe_float(r.get("direct_up_ratio")) or 0.5) < 0.4),
        ("个股跑输(同业强势)",  lambda r:
            (safe_float(r.get("anchor_return")) or 0) < -0.5
            and (safe_float(r.get("direct_up_ratio")) or 0.5) > 0.6),
        ("全面扩散(共振向上)",  lambda r:
            (safe_float(r.get("direct_up_ratio")) or 0) > 0.7
            and (safe_float(r.get("chain_up_ratio")) or 0) > 0.7),
        ("扩散失败(产业链不跟)",lambda r:
            (safe_float(r.get("anchor_return")) or 0) > 0.5
            and (safe_float(r.get("chain_up_ratio")) or 0.5) < 0.3),
        ("全面下跌(共振向下)",  lambda r:
            (safe_float(r.get("direct_up_ratio")) or 1) < 0.3
            and (safe_float(r.get("chain_up_ratio")) or 1) < 0.3),
    ]

    result = []
    for name, filt in signals:
        abs1_v, exc1_v, abs3_v, exc3_v, abs5_v, exc5_v = [], [], [], [], [], []
        for row in rows:
            try:
                if not filt(row):
                    continue
            except Exception:
                continue
            if safe_float(row.get("direct_up_ratio")) is None:
                continue
            a1 = safe_float(row.get("next_1d_return"))
            e1 = safe_float(row.get("next_1d_excess_vs_chain"))
            a3 = safe_float(row.get("next_3d_return"))
            e3 = safe_float(row.get("next_3d_excess_vs_chain"))
            a5 = safe_float(row.get("next_5d_return"))
            e5 = safe_float(row.get("next_5d_excess_vs_chain"))
            if a1 is not None: abs1_v.append(a1)
            if e1 is not None: exc1_v.append(e1)
            if a3 is not None: abs3_v.append(a3)
            if e3 is not None: exc3_v.append(e3)
            if a5 is not None: abs5_v.append(a5)
            if e5 is not None: exc5_v.append(e5)
        result.append({
            "signal": name,
            "n": len(abs1_v),
            "abs1d": stat_block(abs1_v),
            "exc1d": stat_block(exc1_v),
            "abs3d": stat_block(abs3_v) if abs3_v else {},
            "exc3d": stat_block(exc3_v) if exc3_v else {},
            "abs5d": stat_block(abs5_v) if abs5_v else {},
            "exc5d": stat_block(exc5_v) if exc5_v else {},
        })
    return result


# ── J. 连续跑赢/跑输区间信号（Outperform Streak）────────────────────────────
# outperform_streak > 0 = 连续跑赢产业链，< 0 = 连续跑输；测试均值回归特性

def compute_streak_return(rows: list[dict], rolling: list[dict]) -> dict:
    """
    把 outperform_streak 和 beta_streak 按分组，
    计算每组的 T+1 绝对 + 超额收益。
    """
    rolling_by_date = {str(r.get("date")): r for r in rolling}
    rows_by_date    = {str(r.get("date")): r for r in rows}

    outperform_groups: dict[str, list[tuple[float,float]]] = defaultdict(list)  # (abs1, exc1)
    beta_groups:       dict[str, list[tuple[float,float]]] = defaultdict(list)

    for date, roll in rolling_by_date.items():
        row = rows_by_date.get(date)
        if not row:
            continue
        abs1 = safe_float(row.get("next_1d_return"))
        exc1 = safe_float(row.get("next_1d_excess_vs_chain"))
        abs3 = safe_float(row.get("next_3d_return"))
        exc3 = safe_float(row.get("next_3d_excess_vs_chain"))

        out_streak = safe_float(roll.get("outperform_streak"))
        beta_streak_v = safe_float(roll.get("beta_streak"))

        def bucket(v: float | None) -> str | None:
            if v is None: return None
            if v <= -3: return "≤-3(连续跑输)"
            if v == -2: return "-2"
            if v == -1: return "-1"
            if v == 0:  return "0"
            if v == 1:  return "+1"
            if v == 2:  return "+2"
            return "≥+3(连续跑赢)"

        ob = bucket(out_streak)
        if ob and abs1 is not None:
            outperform_groups[ob].append((abs1, exc1 if exc1 is not None else 0.0, abs3 or 0.0, exc3 or 0.0))

        bb = bucket(beta_streak_v)
        if bb and abs1 is not None:
            beta_groups[bb].append((abs1, exc1 if exc1 is not None else 0.0, abs3 or 0.0, exc3 or 0.0))

    def bucket_summary(groups: dict) -> list[dict]:
        order = ["≤-3(连续跑输)", "-2", "-1", "0", "+1", "+2", "≥+3(连续跑赢)"]
        out = []
        for key in order:
            vals = groups.get(key, [])
            abs1_v = [v[0] for v in vals]
            exc1_v = [v[1] for v in vals]
            abs3_v = [v[2] for v in vals]
            exc3_v = [v[3] for v in vals]
            out.append({
                "bucket": key,
                "n": len(vals),
                "abs1d": stat_block(abs1_v),
                "exc1d": stat_block(exc1_v),
                "abs3d": stat_block(abs3_v),
                "exc3d": stat_block(exc3_v),
            })
        return out

    return {
        "outperformStreak": bucket_summary(outperform_groups),
        "betaStreak":       bucket_summary(beta_groups),
    }


# ── K. 超额收益目标下的信号重排（Alpha Signal Rank）──────────────────────────
# 关键洞察：某些信号预测绝对收益（追行业 Beta），某些预测超额（纯 Alpha）
# 只有超额 lift 有效的信号，才是真正的 Alpha 来源

def compute_alpha_signal_rank(rows: list[dict]) -> list[dict]:
    """
    对 31 个信号，同时计算：
    - abs_lift1d: 激活时 T+1 绝对收益 - 全样本均值
    - exc_lift1d: 激活时 T+1 excess_vs_chain - 全样本均值
    分类：pure_alpha / beta_riding / mixed / reverse_alpha
    """
    # 全样本基线
    all_abs1 = [safe_float(r.get("next_1d_return")) for r in rows if safe_float(r.get("next_1d_return")) is not None]
    all_exc1 = [safe_float(r.get("next_1d_excess_vs_chain")) for r in rows if safe_float(r.get("next_1d_excess_vs_chain")) is not None]
    baseline_abs  = sum(all_abs1) / len(all_abs1) if all_abs1 else 0
    baseline_exc  = sum(all_exc1) / len(all_exc1) if all_exc1 else 0

    # 按信号归组
    sig_data: dict[str, dict[str, list[float]]] = defaultdict(lambda: {
        "abs1": [], "exc1": [], "abs3": [], "exc3": [], "abs5": [], "exc5": []
    })
    for row in rows:
        sigs = parse_signals(row.get("signal_labels"))
        for s in sigs:
            for col, key in [
                ("next_1d_return", "abs1"), ("next_1d_excess_vs_chain", "exc1"),
                ("next_3d_return", "abs3"), ("next_3d_excess_vs_chain", "exc3"),
                ("next_5d_return", "abs5"), ("next_5d_excess_vs_chain", "exc5"),
            ]:
                v = safe_float(row.get(col))
                if v is not None:
                    sig_data[s][key].append(v)

    result = []
    for sig, data in sig_data.items():
        n = len(data["abs1"])
        if n < 8:
            continue
        avg_abs1 = safe_avg(data["abs1"]) or 0
        avg_exc1 = safe_avg(data["exc1"]) or 0
        avg_abs3 = safe_avg(data["abs3"]) or 0
        avg_exc3 = safe_avg(data["exc3"]) or 0
        avg_abs5 = safe_avg(data["abs5"]) or 0
        avg_exc5 = safe_avg(data["exc5"]) or 0

        abs_lift = avg_abs1 - baseline_abs
        exc_lift = avg_exc1 - baseline_exc

        # 分类
        threshold = 0.3  # pp
        if exc_lift > threshold and abs_lift > threshold:
            signal_type = "纯Alpha（绝对+超额均正）"
        elif exc_lift > threshold and abs_lift <= threshold:
            signal_type = "隐藏Alpha（超额正但绝对弱）"
        elif exc_lift < -threshold and abs_lift > threshold:
            signal_type = "Beta骑乘（绝对正但超额负）"
        elif exc_lift < -threshold and abs_lift < -threshold:
            signal_type = "负向信号（绝对+超额均负）"
        else:
            signal_type = "中性"

        result.append({
            "signal": sig,
            "n": n,
            "avgAbs1d": round(avg_abs1, 4),
            "avgExc1d": round(avg_exc1, 4),
            "absLift":  round(abs_lift, 4),
            "excLift":  round(exc_lift, 4),
            "avgAbs3d": round(avg_abs3, 4),
            "avgExc3d": round(avg_exc3, 4),
            "avgAbs5d": round(avg_abs5, 4),
            "avgExc5d": round(avg_exc5, 4),
            "wr1d": round(safe_wr(data["abs1"]) or 0, 4),
            "wrExc1d": round(safe_wr(data["exc1"]) or 0, 4),
            "signalType": signal_type,
        })

    # 按 excLift 排序（超额能力优先）
    result.sort(key=lambda x: x["excLift"], reverse=True)
    return result


# ── L. 多条件交叉矩阵（Compound Condition Matrix）────────────────────────────
# 象限 × 超额位置 × 连续跑赢/跑输 三维交叉，找出实际操作优势最大的情景

def compute_compound_matrix(rows: list[dict], rolling: list[dict]) -> list[dict]:
    """
    每个日期打上三个标签：
      - quadrant：9象限 key
      - excess5d_level：low(≤P30) / mid / high(≥P70)
      - streak_sign：正(连续跑赢) / 负(连续跑输) / 中性
    找出样本量≥6 的交叉格，计算 T+1 绝对 + 超额收益。
    """
    rolling_by_date = {str(r.get("date")): r for r in rolling}

    # 先算 excess_5d 的 P30/P70 分位点
    excess5d_vals = [safe_float(r.get("excess_5d")) for r in rolling if safe_float(r.get("excess_5d")) is not None]
    if len(excess5d_vals) >= 10:
        excess5d_vals_s = sorted(excess5d_vals)
        p30 = excess5d_vals_s[int(len(excess5d_vals_s) * 0.30)]
        p70 = excess5d_vals_s[int(len(excess5d_vals_s) * 0.70)]
    else:
        p30, p70 = -3.0, 3.0

    groups: dict[tuple, dict[str, list[float]]] = defaultdict(lambda: {"abs1": [], "exc1": [], "abs3": [], "exc3": []})

    for row in rows:
        date = str(row.get("date"))
        roll = rolling_by_date.get(date)
        if not roll:
            continue

        quad = state_key(row)
        out_streak = safe_float(roll.get("outperform_streak"))
        exc5d_v    = safe_float(roll.get("excess_5d"))

        if exc5d_v is None or out_streak is None:
            continue

        # 超额位置标签
        if exc5d_v <= p30:
            exc_level = "冷（≤P30）"
        elif exc5d_v >= p70:
            exc_level = "热（≥P70）"
        else:
            exc_level = "中性"

        # Streak 标签
        if out_streak >= 2:
            streak_sign = "连续跑赢"
        elif out_streak <= -2:
            streak_sign = "连续跑输"
        else:
            streak_sign = "中性"

        key = (quad, exc_level, streak_sign)

        abs1 = safe_float(row.get("next_1d_return"))
        exc1 = safe_float(row.get("next_1d_excess_vs_chain"))
        abs3 = safe_float(row.get("next_3d_return"))
        exc3 = safe_float(row.get("next_3d_excess_vs_chain"))

        if abs1 is not None: groups[key]["abs1"].append(abs1)
        if exc1 is not None: groups[key]["exc1"].append(exc1)
        if abs3 is not None: groups[key]["abs3"].append(abs3)
        if exc3 is not None: groups[key]["exc3"].append(exc3)

    result = []
    for (quad, exc_level, streak_sign), data in groups.items():
        n = len(data["abs1"])
        if n < 6:
            continue
        result.append({
            "quadrant": quad,
            "quadrantLabel": state_label(quad),
            "excessLevel": exc_level,
            "streakSign": streak_sign,
            "n": n,
            "abs1d": stat_block(data["abs1"]),
            "exc1d": stat_block(data["exc1"]),
            "abs3d": stat_block(data["abs3"]) if data["abs3"] else {},
            "exc3d": stat_block(data["exc3"]) if data["exc3"] else {},
        })

    # 按超额 lift 排序
    result.sort(key=lambda x: x["exc1d"].get("avg", 0), reverse=True)
    return result


# ── 打印工具 ──────────────────────────────────────────────────────────────────

def print_section(title: str) -> None:
    print(f"\n{'='*65}\n  {title}\n{'='*65}")

def print_gram2(gram2: list[dict]) -> None:
    print_section("A. 2-gram 路径信号（n≥4）")
    hdr = f"{'路径':<36} {'n':>3}  {'T+1':>7}  {'T+3':>7}  {'T+5':>7}  {'胜率1d':>5}"
    print(hdr); print("-"*75)
    for r in [x for x in gram2 if x["1d"]["count"] >= 4][:15]:
        path = f"{r['fromLabel']} → {r['toLabel']}"
        print(f"{path:<36} {r['1d']['count']:>3}  "
              f"{fmt_pct(r['1d']['avg']):>8}  {fmt_pct(r['3d']['avg']):>8}  "
              f"{fmt_pct(r['5d']['avg']):>8}  {fmt_wr(r['1d']['wr']):>5}")

def print_delta(delta: list[dict]) -> None:
    print_section("B. 信号 Delta — 新出现 vs 持续（T+1/T+3/T+5）")
    shown = [r for r in delta
             if r["newVsContinued1d"] is not None
             and r["new"]["1d"]["count"] >= 5
             and r["continued"]["1d"]["count"] >= 5][:12]
    print(f"{'信号':<18} {'新T1':>7} {'新T3':>7} {'新T5':>7}   {'续T1':>7} {'续T3':>7} {'续T5':>7}  {'Δ(1d)':>7}")
    print("-"*78)
    for r in shown:
        n, c = r["new"], r["continued"]
        print(f"{r['signal']:<18} "
              f"{fmt_pct(n['1d']['avg']):>8}{fmt_pct(n['3d']['avg']):>8}{fmt_pct(n['5d']['avg']):>8}  "
              f"{fmt_pct(c['1d']['avg']):>8}{fmt_pct(c['3d']['avg']):>8}{fmt_pct(c['5d']['avg']):>8}  "
              f"{fmt_pct(r['newVsContinued1d']):>8}")

def print_streak(streak: dict) -> None:
    print_section("C. 象限 Streak（停留天数 vs 均值回归）")
    for state, info in sorted(streak.items()):
        buckets = info.get("byStreak", {})
        total = sum(b["1d"]["count"] for b in buckets.values())
        if total < 8: continue
        print(f"\n  {info['label']} (共 {total} 样本)")
        print(f"  {'Streak':>6} {'n':>4}  {'T+1':>7}  {'T+3':>7}  {'T+5':>7}  胜率1d")
        print(f"  {'-'*50}")
        for k, b in sorted(buckets.items(), key=lambda x:(len(x[0]),x[0])):
            if b["1d"]["count"] < 1: continue
            print(f"  {'第'+k+'天':>6} {b['1d']['count']:>4}  "
                  f"{fmt_pct(b['1d']['avg']):>8}  {fmt_pct(b['3d']['avg']):>8}  "
                  f"{fmt_pct(b['5d']['avg']):>8}  {fmt_wr(b['1d']['wr']):>5}")

def print_composite(comp: dict) -> None:
    print_section("D. 综合信号分 vs 三周期相关性")
    for p in PERIODS:
        d = comp.get(p, {})
        corr = d.get("corrWithReturn")
        n = d.get("sampleCount", 0)
        print(f"  T+{p}: r={corr:.4f}  (n={n})" if corr else f"  T+{p}: 无数据")

def print_knn(knn: dict) -> None:
    print_section("E. kNN 相似度加权预测 — 方向命中率")
    stats = knn.get("stats", {})
    for p in PERIODS:
        s = stats.get(p, {})
        if not s: continue
        r = s.get("pearsonR"); acc = s.get("directionAccuracy"); n = s.get("sampleCount",0)
        print(f"  T+{p}: Pearson r={r:.4f}  方向命中率={acc*100:.1f}%  (n={n})" if (r and acc) else f"  T+{p}: 无数据")
    # 按预测分五档
    q5 = stats.get("1d", {}).get("byPredQuintile", [])
    if q5:
        print(f"\n  kNN预测分五档（T+1）：预测越高→实际越高？")
        print(f"  {'分档':>4} {'预测区间':>18} {'n':>4}  {'实际T+1':>8}  {'方向命中':>6}")
        print(f"  {'-'*48}")
        for q in q5:
            rng = f"[{q['predRange'][0]:+.2f},{q['predRange'][1]:+.2f}]"
            hit = q.get("directionHit")
            print(f"  Q{q['quintile']:>1}  {rng:>18}  {q['count']:>4}  "
                  f"{fmt_pct(q['avg']):>8}  {hit*100:.0f}%" if hit else
                  f"  Q{q['quintile']:>1}  {rng:>18}  {q['count']:>4}  {fmt_pct(q['avg']):>8}  -")

def print_consistency(cons: list[dict]) -> None:
    print_section("F. 三周期一致性信号 — T1/T3/T5 方向一致的才可信")
    print(f"  {'信号':<18} {'T+1':>7} {'T+3':>7} {'T+5':>7}  {'n':>3}  {'一致性'}")
    print(f"  {'-'*62}")
    for r in cons[:20]:
        flag = "✅" if r["consistent"] else ("🔄" if r["flip"] else "❓")
        print(f"  {r['signal']:<18} "
              f"{fmt_pct(r.get('lift1d')):>8}{fmt_pct(r.get('lift3d')):>8}{fmt_pct(r.get('lift5d')):>8}  "
              f"{r['count']:>4}  {flag} {r['pattern']}")

def print_rs_quintile(rs: dict) -> None:
    print_section("G. 相对强度位置信号（vs 产业链 五分位）")
    chain = rs.get("vsChain", {})
    corr = chain.get("corrWithExcess1d", 0)
    print(f"  rs_vs_chain 与 T+1 超额相关性 r={corr:.4f}")
    print(f"\n  {'档位':<12} {'rs区间':>14} {'n':>4}  {'T+1绝对':>8}  {'T+1超额':>8}  {'胜率':>5}  {'超额胜率':>6}")
    print(f"  {'-'*70}")
    for q in chain.get("quintiles", []):
        rng = f"[{q['rsRange'][0]:+.1f},{q['rsRange'][1]:+.1f}]"
        a1 = q.get("abs1d", {}); e1 = q.get("exc1d", {})
        print(f"  {q['label']:<12} {rng:>14} {q['n']:>4}  "
              f"{fmt_pct(a1.get('avg')):>8}  {fmt_pct(e1.get('avg')):>8}  "
              f"{fmt_wr(a1.get('wr')):>5}  {fmt_wr(e1.get('wr')):>6}")


def print_vol_price(vp: list[dict]) -> None:
    print_section("H. 量价背离信号")
    print(f"  {'信号':<16} {'n':>4}  {'T+1绝对':>8}  {'T+1超额':>8}  {'T+3绝对':>8}  {'T+3超额':>8}  {'胜率':>5}")
    print(f"  {'-'*75}")
    for r in vp:
        if r["n"] < 5:
            continue
        a1 = r.get("abs1d", {}); e1 = r.get("exc1d", {})
        a3 = r.get("abs3d", {}); e3 = r.get("exc3d", {})
        print(f"  {r['signal']:<16} {r['n']:>4}  "
              f"{fmt_pct(a1.get('avg')):>8}  {fmt_pct(e1.get('avg')):>8}  "
              f"{fmt_pct(a3.get('avg')):>8}  {fmt_pct(e3.get('avg')):>8}  "
              f"{fmt_wr(a1.get('wr')):>5}")


def print_breadth(bd: list[dict]) -> None:
    print_section("I. 板块扩散背离信号")
    print(f"  {'信号':<18} {'n':>4}  {'T+1绝对':>8}  {'T+1超额':>8}  {'T+3绝对':>8}  {'T+3超额':>8}  {'胜率':>5}")
    print(f"  {'-'*78}")
    for r in bd:
        if r["n"] < 4:
            continue
        a1 = r.get("abs1d", {}); e1 = r.get("exc1d", {})
        a3 = r.get("abs3d", {}); e3 = r.get("exc3d", {})
        print(f"  {r['signal']:<18} {r['n']:>4}  "
              f"{fmt_pct(a1.get('avg')):>8}  {fmt_pct(e1.get('avg')):>8}  "
              f"{fmt_pct(a3.get('avg')):>8}  {fmt_pct(e3.get('avg')):>8}  "
              f"{fmt_wr(a1.get('wr')):>5}")


def print_streak_return(sr: dict) -> None:
    print_section("J. 连续跑赢/跑输区间信号（outperform_streak）")
    print(f"  {'区间':>14} {'n':>4}  {'T+1绝对':>8}  {'T+1超额':>8}  {'T+3绝对':>8}  {'T+3超额':>8}  {'胜率':>5}")
    print(f"  {'-'*75}")
    for row in sr.get("outperformStreak", []):
        if row["n"] < 3:
            continue
        a1 = row.get("abs1d", {}); e1 = row.get("exc1d", {})
        a3 = row.get("abs3d", {}); e3 = row.get("exc3d", {})
        print(f"  {row['bucket']:>14} {row['n']:>4}  "
              f"{fmt_pct(a1.get('avg')):>8}  {fmt_pct(e1.get('avg')):>8}  "
              f"{fmt_pct(a3.get('avg')):>8}  {fmt_pct(e3.get('avg')):>8}  "
              f"{fmt_wr(a1.get('wr')):>5}")


def print_alpha_rank(ar: list[dict]) -> None:
    print_section("K. 信号 Alpha 排行（超额收益目标 next_1d_excess_vs_chain）")
    print(f"  {'信号':<18} {'n':>4}  {'绝对T+1':>8}  {'超额T+1':>8}  {'绝对lift':>8}  {'超额lift':>8}  类型")
    print(f"  {'-'*82}")
    for r in ar:
        if r["n"] < 8:
            continue
        marker = (
            "🟢" if "纯Alpha" in r["signalType"] else
            "💡" if "隐藏" in r["signalType"] else
            "⚠️" if "Beta骑乘" in r["signalType"] else
            "🔴" if "负向" in r["signalType"] else "⬜"
        )
        print(f"  {r['signal']:<18} {r['n']:>4}  "
              f"{fmt_pct(r.get('avgAbs1d')):>8}  {fmt_pct(r.get('avgExc1d')):>8}  "
              f"{fmt_pct(r.get('absLift')):>8}  {fmt_pct(r.get('excLift')):>8}  "
              f"{marker} {r['signalType']}")


def print_compound_matrix(cm: list[dict]) -> None:
    print_section("L. 多条件交叉矩阵 Top/Bottom（象限 × 超额位置 × 连续Streak）")
    print(f"  显示 T+1 超额最强/最弱的 10 个情景（n≥6）\n")
    print(f"  {'象限':<14} {'超额位置':<10} {'Streak':>10}  {'n':>4}  {'T+1绝对':>8}  {'T+1超额':>8}  {'T+3超额':>8}  胜率")
    print(f"  {'-'*85}")
    shown = [r for r in cm if r["n"] >= 6]
    top5    = shown[:5]
    bottom5 = shown[-5:] if len(shown) > 5 else []
    for r in top5:
        e1 = r.get("exc1d", {}); a1 = r.get("abs1d", {}); e3 = r.get("exc3d", {})
        print(f"  {r['quadrantLabel']:<14} {r['excessLevel']:<10} {r['streakSign']:>10}  "
              f"{r['n']:>4}  {fmt_pct(a1.get('avg')):>8}  {fmt_pct(e1.get('avg')):>8}  "
              f"{fmt_pct(e3.get('avg')):>8}  {fmt_wr(e1.get('wr'))}")
    if bottom5:
        print(f"  ...(最弱)")
        for r in bottom5:
            e1 = r.get("exc1d", {}); a1 = r.get("abs1d", {}); e3 = r.get("exc3d", {})
            print(f"  {r['quadrantLabel']:<14} {r['excessLevel']:<10} {r['streakSign']:>10}  "
                  f"{r['n']:>4}  {fmt_pct(a1.get('avg')):>8}  {fmt_pct(e1.get('avg')):>8}  "
                  f"{fmt_pct(e3.get('avg')):>8}  {fmt_wr(e1.get('wr'))}")


def print_today(rows: list[dict], gram2: list[dict], delta: list[dict],
                streak: dict, knn: dict, cons: list[dict],
                lift_map: dict[str, float]) -> None:
    if len(rows) < 2: return
    today, yesterday = rows[-1], rows[-2]
    today_state, yesterday_state = state_key(today), state_key(yesterday)
    today_sigs = parse_signals(today.get("signal_labels"))
    yesterday_sigs = parse_signals(yesterday.get("signal_labels"))
    new_sigs  = today_sigs - yesterday_sigs
    gone_sigs = yesterday_sigs - today_sigs
    cont_sigs = today_sigs & yesterday_sigs

    # streak
    cur_streak = 1
    for i in range(len(rows)-2, -1, -1):
        if state_key(rows[i]) == today_state: cur_streak += 1
        else: break

    # 综合分
    sl = [lift_map[s] for s in today_sigs if s in lift_map]
    composite = sum(sl)/len(sl) if sl else None

    # kNN 今日预测
    daily = knn.get("daily", [])
    today_knn = next((d for d in daily if d["date"] == str(today.get("date"))), None)

    print_section(f"今日二阶信号摘要（{today.get('date')}）")
    print(f"  象限路径：{state_label(yesterday_state)} → {state_label(today_state)}")

    path_match = next((r for r in gram2
                       if r["fromState"]==yesterday_state and r["toState"]==today_state), None)
    if path_match and path_match["1d"]["count"] >= 3:
        p = path_match
        print(f"  路径历史：T+1={fmt_pct(p['1d']['avg'])} 胜率={fmt_wr(p['1d']['wr'])}  "
              f"T+3={fmt_pct(p['3d']['avg'])}  T+5={fmt_pct(p['5d']['avg'])}  n={p['1d']['count']}")
    else:
        print(f"  路径历史：样本不足（n<3）")

    print(f"\n  当前象限 Streak：连续第 {cur_streak} 天在「{state_label(today_state)}」")
    if today_state in streak:
        bucket = str(cur_streak) if cur_streak <= 4 else "5+"
        b = streak[today_state]["byStreak"].get(bucket)
        if b:
            print(f"  历史同 Streak：T+1={fmt_pct(b['1d']['avg'])} 胜率={fmt_wr(b['1d']['wr'])}  "
                  f"T+3={fmt_pct(b['3d']['avg'])}  T+5={fmt_pct(b['5d']['avg'])}  n={b['1d']['count']}")

    if today_knn:
        pred = today_knn.get("knnPred", {})
        print(f"\n  kNN 相似度加权预测：T+1={fmt_pct(pred.get('1d'))}  "
              f"T+3={fmt_pct(pred.get('3d'))}  T+5={fmt_pct(pred.get('5d'))}")
        acc = knn["stats"].get("1d", {}).get("directionAccuracy")
        print(f"  （历史方向命中率 {acc*100:.1f}%）" if acc else "")

    print(f"\n  综合信号分：{composite:+.3f}" if composite else "\n  综合信号分：无数据")

    print(f"\n  信号变化：")
    if new_sigs:
        print(f"    🆕 新出现（{len(new_sigs)}）：{', '.join(sorted(new_sigs))}")
    if gone_sigs:
        print(f"    ❌ 消失（{len(gone_sigs)}）：{', '.join(sorted(gone_sigs))}")
    if cont_sigs:
        print(f"    ♻️  持续（{len(cont_sigs)}）：{', '.join(sorted(cont_sigs))}")

    # 新增信号的多周期一致性
    cons_map = {r["signal"]: r for r in cons}
    notable = [cons_map[s] for s in new_sigs if s in cons_map and not cons_map[s]["consistent"]]
    if notable:
        print(f"\n  ⚡ 新出现信号中方向不稳定的（需谨慎）：")
        for r in notable:
            print(f"    「{r['signal']}」{r['pattern']}  "
                  f"T+1={fmt_pct(r.get('lift1d'))} T+3={fmt_pct(r.get('lift3d'))} T+5={fmt_pct(r.get('lift5d'))}")


def print_today_extended(rows: list[dict], rolling: list[dict],
                         rs: dict, sr: dict, ar: list[dict], cm: list[dict]) -> None:
    """打印今日 G-L 维度的当日状态摘要"""
    if len(rows) < 2:
        return
    today = rows[-1]
    today_date = str(today.get("date"))
    rolling_by_date = {str(r.get("date")): r for r in rolling}
    roll_today = rolling_by_date.get(today_date)

    print_section(f"今日 G-L 维度摘要（{today_date}）")

    # G: 当前 rs 位置
    rs_chain = safe_float(today.get("relative_strength_vs_industry_chain"))
    if rs_chain is not None:
        chain_qs = rs.get("vsChain", {}).get("quintiles", [])
        cur_q = None
        for q in chain_qs:
            lo, hi = q["rsRange"]
            if lo <= rs_chain <= hi:
                cur_q = q; break
        if cur_q:
            e1 = cur_q.get("exc1d", {})
            print(f"  G. 相对强度 vs 产业链：{rs_chain:+.2f}%  → {cur_q['label']}")
            print(f"     历史该档：T+1超额={fmt_pct(e1.get('avg'))}  超额胜率={fmt_wr(e1.get('wr'))}  n={cur_q['n']}")

    # J: 当前 streak 位置
    if roll_today:
        out_streak = safe_float(roll_today.get("outperform_streak"))
        exc5d = safe_float(roll_today.get("excess_5d"))
        if out_streak is not None:
            print(f"\n  J. outperform_streak = {int(out_streak):+d}  ({'连续跑赢' if out_streak>0 else '连续跑输' if out_streak<0 else '持平'})")
            # 找对应 bucket
            def bucket(v: float) -> str:
                if v <= -3: return "≤-3(连续跑输)"
                if v == -2: return "-2"
                if v == -1: return "-1"
                if v == 0:  return "0"
                if v == 1:  return "+1"
                if v == 2:  return "+2"
                return "≥+3(连续跑赢)"
            b = bucket(out_streak)
            for row_s in sr.get("outperformStreak", []):
                if row_s["bucket"] == b:
                    e1 = row_s.get("exc1d", {}); a1 = row_s.get("abs1d", {})
                    print(f"     历史该Streak：T+1绝对={fmt_pct(a1.get('avg'))}  T+1超额={fmt_pct(e1.get('avg'))}  胜率={fmt_wr(a1.get('wr'))}  n={row_s['n']}")
        if exc5d is not None:
            print(f"\n  excess_5d = {exc5d:+.2f}%")

    # K: 今日信号中哪些是 Alpha 信号
    today_sigs = parse_signals(today.get("signal_labels"))
    ar_map = {r["signal"]: r for r in ar}
    print(f"\n  K. 今日信号 Alpha/Beta 分类：")
    for s in sorted(today_sigs):
        info = ar_map.get(s)
        if info:
            marker = (
                "🟢纯Alpha" if "纯Alpha" in info["signalType"] else
                "💡隐藏Alpha" if "隐藏" in info["signalType"] else
                "⚠️Beta骑乘" if "Beta骑乘" in info["signalType"] else
                "🔴负向" if "负向" in info["signalType"] else "⬜中性"
            )
            print(f"     「{s}」{marker}  超额lift={fmt_pct(info.get('excLift'))}")
        else:
            print(f"     「{s}」样本不足")

# ── 主函数 ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("="*65)
    print("  深度量化信号挖掘（A-F 二阶 + G-L Alpha/量价/扩散/Streak）")
    print("="*65)

    rows      = load_history()
    lift_map  = load_lift_map()
    dashboard = load_dashboard()
    rolling   = load_rolling()

    print("\n[INFO] 计算 A. 2-gram 路径信号...")
    gram2 = compute_gram2(rows)

    print("[INFO] 计算 B. 信号 Delta...")
    delta = compute_signal_delta(rows)

    print("[INFO] 计算 C. 象限 Streak...")
    streak = compute_streak(rows)

    print("[INFO] 计算 D. 综合信号分...")
    comp = compute_composite(rows, lift_map)

    print("[INFO] 计算 E. kNN 相似度加权预测...")
    knn = compute_knn_signal(dashboard, rows)

    print("[INFO] 计算 F. 三周期一致性信号...")
    cons = compute_multi_period_consistency(rows, lift_map)

    print("[INFO] 计算 G. 相对强度位置信号...")
    rs = compute_rs_quintile(rows)

    print("[INFO] 计算 H. 量价背离信号...")
    vp = compute_vol_price_divergence(rows)

    print("[INFO] 计算 I. 板块扩散背离信号...")
    bd = compute_breadth_divergence(rows)

    print("[INFO] 计算 J. 连续跑赢/跑输区间信号...")
    sr = compute_streak_return(rows, rolling)

    print("[INFO] 计算 K. 信号 Alpha 排行...")
    ar = compute_alpha_signal_rank(rows)

    print("[INFO] 计算 L. 多条件交叉矩阵...")
    cm = compute_compound_matrix(rows, rolling)

    # ── 打印 A-F ──
    print_gram2(gram2)
    print_delta(delta)
    print_streak(streak)
    print_composite(comp)
    print_knn(knn)
    print_consistency(cons)

    # ── 打印 G-L ──
    print_rs_quintile(rs)
    print_vol_price(vp)
    print_breadth(bd)
    print_streak_return(sr)
    print_alpha_rank(ar)
    print_compound_matrix(cm)

    # ── 今日摘要 ──
    print_today(rows, gram2, delta, streak, knn, cons, lift_map)
    print_today_extended(rows, rolling, rs, sr, ar, cm)

    output = {
        "generatedAt": rows[-1].get("date") if rows else "",
        # A-F（已有）
        "gram2":       gram2,
        "signalDelta": delta,
        "streakStats": streak,
        "compositeScore": comp,
        "knnSignal":   {"stats": knn["stats"]},
        "multiPeriodConsistency": cons,
        # G-L（新增）
        "rsQuintile":         rs,
        "volumePriceDivergence": vp,
        "breadthDivergence":  bd,
        "streakReturn":       sr,
        "alphaSignalRank":    ar,
        "compoundMatrix":     cm,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    sz = os.path.getsize(OUTPUT_JSON)/1024
    print(f"\n[OK] 结果写入：{OUTPUT_JSON}  ({sz:.1f} KB)")

if __name__ == "__main__":
    main()
