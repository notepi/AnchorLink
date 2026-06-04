"""
标准指数超额画像分析
====================
以虚拟指数产物为只读输入，构建信号→分档→Forward Label→画像统计的完整流水线。

核心职责：
  - 信号提取（从 anchor_index_excess.csv 直接读取标准超额）
  - 区间质量检查（信号区间 + 标签区间分别质检）
  - Anchor 自身行情检查
  - 分档（static_full_sample + asof expanding window）
  - Forward Label 计算（长表，每行一个 holding_window）
  - MFE/MAE 路径指标（股票自身 + 相对指数）
  - Profile 统计（all_signals + non_overlapping）
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.index_products.builder import INDEX_IDS, EXCESS_WINDOWS

# ── 常量 ──

SIGNAL_WINDOWS = [1, 3, 5, 10]
HOLDING_WINDOWS = [1, 3, 5, 10]
GRADE_DEFS = [
    (1, "极冷"),
    (2, "偏冷"),
    (3, "中性"),
    (4, "偏热"),
    (5, "极热"),
]
ASOF_MIN_SAMPLES = 60
STATUS_ORDER = {"ok": 0, "partial": 1, "insufficient_data": 2, "no_future_label": 3}
LABEL_TYPE = "close_to_close_research_label"


# ── 数据读取 ──


def load_input_data(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """读取上游指数产物，返回 (excess_df, nav_df, manifest)。"""
    excess_df = pd.read_csv(input_dir / "anchor_index_excess.csv")
    nav_df = pd.read_csv(input_dir / "custom_index_nav.csv")
    with open(input_dir / "build_manifest.json") as f:
        manifest = json.load(f)
    return excess_df, nav_df, manifest


def check_anchor_continuity(excess_df: pd.DataFrame) -> pd.Series:
    """检查 Anchor 是否有缺失报价或停牌补值，返回 bool Series（True=停牌日）。"""
    dates = excess_df["date"].values
    closes = excess_df["anchor_close"].values
    suspended = pd.Series(False, index=excess_df.index)
    for i in range(1, len(closes)):
        if pd.isna(closes[i]) or closes[i] == closes[i - 1]:
            suspended.iloc[i] = True
    return suspended


# ── 信号提取 ──


def extract_signals(excess_df: pd.DataFrame) -> pd.DataFrame:
    """从 anchor_index_excess.csv 提取 4 指数 × 4 窗口 = 16 条信号序列，输出长表。"""
    rows = []
    for _, row in excess_df.iterrows():
        date = row["date"]
        anchor_close = row["anchor_close"]
        for idx_id in INDEX_IDS:
            for sw in SIGNAL_WINDOWS:
                col = f"excess_vs_{idx_id}_{sw}d"
                val = row.get(col)
                rows.append({
                    "date": date,
                    "anchor_close": anchor_close,
                    "index_id": idx_id,
                    "signal_window": sw,
                    "standard_excess": val if pd.notna(val) else None,
                })
    return pd.DataFrame(rows)


# ── 区间质量 ──


def _worst_status(statuses: list[str]) -> str:
    """取最差 data_status：insufficient_data > partial > ok。"""
    if not statuses:
        return "insufficient_data"
    max_rank = max(STATUS_ORDER.get(s, 2) for s in statuses)
    for s, rank in STATUS_ORDER.items():
        if rank == max_rank:
            return s
    return "insufficient_data"


def compute_signal_quality(
    signals_df: pd.DataFrame,
    nav_df: pd.DataFrame,
) -> pd.DataFrame:
    """为每条信号计算 signal_quality_status。

    N 日信号依赖 [t-N, t] 区间的 data_status。
    """
    # 构建 (index_id, trade_date) → data_status 查找表
    nav_lookup = {}
    for _, row in nav_df.iterrows():
        key = (row["index_id"], row["trade_date"])
        nav_lookup[key] = row["data_status"]

    # 构建 (index_id) → 排序后的日期列表
    date_lists = {}
    for idx_id in INDEX_IDS:
        dates = nav_df[nav_df["index_id"] == idx_id]["trade_date"].sort_values().tolist()
        date_lists[idx_id] = dates

    results = {}
    for i, row in signals_df.iterrows():
        idx_id = row["index_id"]
        sw = row["signal_window"]
        date = row["date"]
        dates = date_lists.get(idx_id, [])
        if date not in dates:
            results[i] = "insufficient_data"
            continue
        pos = dates.index(date)
        start_pos = max(0, pos - sw)
        statuses = []
        for k in range(start_pos, pos + 1):
            key = (idx_id, dates[k])
            if key in nav_lookup:
                statuses.append(nav_lookup[key])
        results[i] = _worst_status(statuses)

    signals_df = signals_df.copy()
    signals_df["signal_quality_status"] = signals_df.index.map(results)
    return signals_df


def compute_label_quality(
    forward_labels_df: pd.DataFrame,
    nav_df: pd.DataFrame,
) -> pd.DataFrame:
    """为每个 forward label 计算 label_quality_status。

    H 日标签依赖 [t, t+H] 区间的 data_status。
    """
    nav_lookup = {}
    for _, row in nav_df.iterrows():
        key = (row["index_id"], row["trade_date"])
        nav_lookup[key] = row["data_status"]

    date_lists = {}
    for idx_id in INDEX_IDS:
        dates = nav_df[nav_df["index_id"] == idx_id]["trade_date"].sort_values().tolist()
        date_lists[idx_id] = dates

    results = []
    for _, row in forward_labels_df.iterrows():
        # no_future_label 已由 compute_forward_labels 设置，不覆盖
        if row.get("label_quality_status") == "no_future_label":
            results.append("no_future_label")
            continue

        idx_id = row["index_id"]
        hw = row["holding_window"]
        date = row["date"]
        dates = date_lists.get(idx_id, [])
        if date not in dates:
            results.append("insufficient_data")
            continue
        pos = dates.index(date)
        end_pos = min(len(dates) - 1, pos + hw)
        statuses = []
        for k in range(pos, end_pos + 1):
            key = (idx_id, dates[k])
            if key in nav_lookup:
                statuses.append(nav_lookup[key])
        results.append(_worst_status(statuses))

    forward_labels_df = forward_labels_df.copy()
    forward_labels_df["label_quality_status"] = results
    return forward_labels_df


# ── 分档 ──


def _percentile_thresholds(values: np.ndarray, percentiles: list[int]) -> dict[str, float]:
    """计算百分位阈值。"""
    result = {}
    for p in percentiles:
        if len(values) == 0:
            result[f"P{p}"] = float("nan")
        else:
            result[f"P{p}"] = float(np.percentile(values, p))
    return result


def _assign_grade(value: float, thresholds: dict[str, float]) -> tuple[int, str]:
    """根据阈值分档。

    Q1: x <= P20
    Q2: P20 < x <= P40
    Q3: P40 < x <= P60
    Q4: P60 < x <= P80
    Q5: x > P80
    """
    p20 = thresholds.get("P20", float("nan"))
    p40 = thresholds.get("P40", float("nan"))
    p60 = thresholds.get("P60", float("nan"))
    p80 = thresholds.get("P80", float("nan"))

    if np.isnan(p20):
        return 0, "insufficient_grade_history"

    if value <= p20:
        return 1, "极冷"
    elif value <= p40:
        return 2, "偏冷"
    elif value <= p60:
        return 3, "中性"
    elif value <= p80:
        return 4, "偏热"
    else:
        return 5, "极热"


def compute_static_grades(signals_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """全样本百分位分档。返回更新后的 signals_df 和 thresholds dict。"""
    signals_df = signals_df.copy()
    thresholds = {}

    for idx_id in INDEX_IDS:
        thresholds[idx_id] = {}
        for sw in SIGNAL_WINDOWS:
            mask = (
                (signals_df["index_id"] == idx_id)
                & (signals_df["signal_window"] == sw)
                & signals_df["standard_excess"].notna()
                & (signals_df["signal_quality_status"] != "insufficient_data")
            )
            values = signals_df.loc[mask, "standard_excess"].values.astype(float)
            th = _percentile_thresholds(values, [20, 40, 60, 80])
            thresholds[idx_id][f"{sw}d"] = th

            # 分档
            sub_mask = (
                (signals_df["index_id"] == idx_id)
                & (signals_df["signal_window"] == sw)
            )
            for i in signals_df.index[sub_mask]:
                val = signals_df.at[i, "standard_excess"]
                if pd.isna(val) or signals_df.at[i, "signal_quality_status"] == "insufficient_data":
                    signals_df.at[i, "static_grade"] = 0
                    signals_df.at[i, "static_grade_label"] = "insufficient_data"
                else:
                    g, label = _assign_grade(val, th)
                    signals_df.at[i, "static_grade"] = g
                    signals_df.at[i, "static_grade_label"] = label

    return signals_df, thresholds


def compute_asof_grades(signals_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Expanding window 分档。返回更新后的 signals_df 和 asof_grade_daily DataFrame。"""
    signals_df = signals_df.copy()
    asof_rows = []

    for idx_id in INDEX_IDS:
        for sw in SIGNAL_WINDOWS:
            sub_mask = (
                (signals_df["index_id"] == idx_id)
                & (signals_df["signal_window"] == sw)
            )
            sub_idx = signals_df.index[sub_mask]
            sub = signals_df.loc[sub_idx].sort_values("date")

            # 只用非空且非 insufficient 的样本做阈值
            valid_mask = (
                sub["standard_excess"].notna()
                & (sub["signal_quality_status"] != "insufficient_data")
            )
            valid_sub = sub[valid_mask]

            for i, (idx, row) in enumerate(sub.iterrows()):
                val = row["standard_excess"]
                if pd.isna(val) or row["signal_quality_status"] == "insufficient_data":
                    signals_df.at[idx, "asof_grade"] = 0
                    signals_df.at[idx, "asof_grade_label"] = "insufficient_data"
                    asof_rows.append({
                        "date": row["date"],
                        "index_id": idx_id,
                        "signal_window": sw,
                        "standard_excess": val,
                        "asof_grade": 0,
                        "asof_grade_label": "insufficient_data",
                        "asof_p20": None,
                        "asof_p40": None,
                        "asof_p60": None,
                        "asof_p80": None,
                        "asof_sample_count": 0,
                    })
                    continue

                # expanding window: 只用 [0:t) 的有效样本
                valid_before = valid_sub[valid_sub["date"] < row["date"]]
                n_valid = len(valid_before)

                if n_valid < ASOF_MIN_SAMPLES:
                    signals_df.at[idx, "asof_grade"] = 0
                    signals_df.at[idx, "asof_grade_label"] = "insufficient_grade_history"
                    th = {"P20": float("nan"), "P40": float("nan"), "P60": float("nan"), "P80": float("nan")}
                else:
                    past_values = valid_before["standard_excess"].values.astype(float)
                    th = _percentile_thresholds(past_values, [20, 40, 60, 80])
                    g, label = _assign_grade(val, th)
                    signals_df.at[idx, "asof_grade"] = g
                    signals_df.at[idx, "asof_grade_label"] = label

                asof_rows.append({
                    "date": row["date"],
                    "index_id": idx_id,
                    "signal_window": sw,
                    "standard_excess": val,
                    "asof_grade": signals_df.at[idx, "asof_grade"],
                    "asof_grade_label": signals_df.at[idx, "asof_grade_label"],
                    "asof_p20": th.get("P20"),
                    "asof_p40": th.get("P40"),
                    "asof_p60": th.get("P60"),
                    "asof_p80": th.get("P80"),
                    "asof_sample_count": n_valid,
                })

    asof_df = pd.DataFrame(asof_rows)
    return signals_df, asof_df


# ── Forward Labels ──


def compute_forward_labels(
    signals_df: pd.DataFrame,
    excess_df: pd.DataFrame,
    nav_df: pd.DataFrame,
) -> pd.DataFrame:
    """计算 Forward Labels（长表格式，每行一个 holding_window）。

    包含 MFE/MAE 自身路径和相对指数路径。
    """
    # 准备查找表
    anchor_dates = excess_df["date"].values
    anchor_closes = excess_df.set_index("date")["anchor_close"]

    nav_lookup = {}
    for idx_id in INDEX_IDS:
        sub = nav_df[nav_df["index_id"] == idx_id].sort_values("trade_date")
        nav_lookup[idx_id] = {
            "dates": sub["trade_date"].values,
            "navs": sub.set_index("trade_date")["nav"],
        }

    # 对每个 (date, index_id) 预计算 anchor_close 序列
    anchor_series = excess_df.set_index("date")["anchor_close"]

    rows = []
    # 遍历信号表中的唯一 (date, index_id) 对
    pairs = signals_df[["date", "index_id"]].drop_duplicates()

    for _, pair in pairs.iterrows():
        date = pair["date"]
        idx_id = pair["index_id"]

        # Anchor 当前价格
        if date not in anchor_closes.index:
            continue
        anchor_close_t = anchor_closes[date]
        if pd.isna(anchor_close_t):
            continue

        # Anchor 日期位置
        anchor_date_list = list(anchor_closes.index)
        if date not in anchor_date_list:
            continue
        anchor_pos = anchor_date_list.index(date)

        # Index NAV 位置
        idx_dates = nav_lookup[idx_id]["dates"].tolist()
        idx_navs = nav_lookup[idx_id]["navs"]
        if date not in idx_dates:
            continue
        idx_pos = idx_dates.index(date)
        idx_nav_t = idx_navs[date]

        for hw in HOLDING_WINDOWS:
            row = {
                "date": date,
                "index_id": idx_id,
                "holding_window": hw,
            }

            # 未来 H 日位置
            future_anchor_pos = anchor_pos + hw
            future_idx_pos = idx_pos + hw

            if future_anchor_pos >= len(anchor_date_list) or future_idx_pos >= len(idx_dates):
                # 超出数据范围 — 标记为 no_future_label，从统计中排除
                row.update({
                    "future_anchor_return": None,
                    "future_index_return": None,
                    "future_excess": None,
                    "long_mfe": None,
                    "long_mae": None,
                    "short_mfe": None,
                    "short_mae": None,
                    "relative_long_mfe": None,
                    "relative_long_mae": None,
                    "relative_short_mfe": None,
                    "relative_short_mae": None,
                    "label_quality_status": "no_future_label",
                    "label_type": LABEL_TYPE,
                })
                rows.append(row)
                continue

            # Future returns
            future_anchor_close = anchor_closes[anchor_date_list[future_anchor_pos]]
            future_idx_nav = idx_navs[idx_dates[future_idx_pos]]

            future_anchor_return = (future_anchor_close / anchor_close_t - 1) * 100
            future_index_return = (future_idx_nav / idx_nav_t - 1) * 100
            future_excess = future_anchor_return - future_index_return

            # MFE/MAE 自身路径
            long_mfe = -float("inf")
            long_mae = float("inf")
            relative_path_vals = []

            for k in range(1, hw + 1):
                kp = anchor_pos + k
                kip = idx_pos + k
                if kp >= len(anchor_date_list) or kip >= len(idx_dates):
                    break

                anchor_close_k = anchor_closes[anchor_date_list[kp]]
                idx_nav_k = idx_navs[idx_dates[kip]]

                anchor_ret_k = (anchor_close_k / anchor_close_t - 1) * 100
                idx_ret_k = (idx_nav_k / idx_nav_t - 1) * 100

                long_mfe = max(long_mfe, anchor_ret_k)
                long_mae = min(long_mae, anchor_ret_k)

                relative_path_k = anchor_ret_k - idx_ret_k
                relative_path_vals.append(relative_path_k)

            short_mfe = -long_mae
            short_mae = -long_mfe

            # 相对指数路径
            if relative_path_vals:
                relative_long_mfe = max(relative_path_vals)
                relative_long_mae = min(relative_path_vals)
            else:
                relative_long_mfe = None
                relative_long_mae = None
            relative_short_mfe = -relative_long_mae if relative_long_mae is not None else None
            relative_short_mae = -relative_long_mfe if relative_long_mfe is not None else None

            row.update({
                "future_anchor_return": future_anchor_return,
                "future_index_return": future_index_return,
                "future_excess": future_excess,
                "long_mfe": long_mfe,
                "long_mae": long_mae,
                "short_mfe": short_mfe,
                "short_mae": short_mae,
                "relative_long_mfe": relative_long_mfe,
                "relative_long_mae": relative_long_mae,
                "relative_short_mfe": relative_short_mfe,
                "relative_short_mae": relative_short_mae,
                "label_type": LABEL_TYPE,
            })
            rows.append(row)

    return pd.DataFrame(rows)


# ── Profile 统计 ──


def _quality_scope(
    signal_qs: str,
    label_qs: str,
) -> str:
    """判断统计口径。no_future_label 视同 insufficient_data 排除。"""
    if signal_qs in ("insufficient_data", "no_future_label") or label_qs in ("insufficient_data", "no_future_label"):
        return "excluded"
    if signal_qs == "ok" and label_qs == "ok":
        return "strict_ok_only"
    return "usable"


def _compute_profile_stats(
    group: pd.DataFrame,
) -> dict:
    """对一组 (index_id, signal_window, grade, holding_window, quality_scope) 计算统计量。

    sample_count 使用有效 future_excess 非空的行数，而非分档行数。
    """
    # 只统计有效 future_excess 的行
    valid = group[group["future_excess"].notna()]
    n = len(valid)
    if n == 0:
        return {}

    anchor_rets = valid["future_anchor_return"].dropna()
    excess_rets = valid["future_excess"].dropna()
    partial_count = valid[
        (valid["signal_quality_status"] == "partial") | (valid["label_quality_status"] == "partial")
    ].shape[0]

    stats = {
        "sample_count": n,
        "future_anchor_return_mean": anchor_rets.mean() if len(anchor_rets) > 0 else None,
        "future_anchor_return_median": anchor_rets.median() if len(anchor_rets) > 0 else None,
        "future_anchor_positive_rate": (anchor_rets > 0).mean() if len(anchor_rets) > 0 else None,
        "future_anchor_negative_rate": (anchor_rets < 0).mean() if len(anchor_rets) > 0 else None,
        "future_excess_mean": excess_rets.mean() if len(excess_rets) > 0 else None,
        "future_excess_median": excess_rets.median() if len(excess_rets) > 0 else None,
        "future_excess_positive_rate": (excess_rets > 0).mean() if len(excess_rets) > 0 else None,
        "future_excess_negative_rate": (excess_rets < 0).mean() if len(excess_rets) > 0 else None,
        "partial_sample_count": partial_count,
        "partial_sample_ratio": partial_count / n if n > 0 else None,
    }

    for col in ["long_mfe", "long_mae", "short_mfe", "short_mae",
                "relative_long_mfe", "relative_long_mae",
                "relative_short_mfe", "relative_short_mae"]:
        vals = group[col].dropna()
        stats[f"{col}_mean"] = vals.mean() if len(vals) > 0 else None

    return stats


def compute_grade_profile(
    signals_df: pd.DataFrame,
    forward_labels_df: pd.DataFrame,
) -> pd.DataFrame:
    """计算 grade_profile.csv（evaluation_mode = all_signals）。"""
    # 合并信号和标签
    merged = forward_labels_df.merge(
        signals_df[["date", "index_id", "signal_window", "standard_excess",
                     "signal_quality_status", "anchor_suspended",
                     "static_grade", "static_grade_label",
                     "asof_grade", "asof_grade_label"]],
        on=["date", "index_id"],
        how="left",
    )

    rows = []
    for grade_mode, grade_col, label_col in [
        ("static_full_sample", "static_grade", "static_grade_label"),
        ("asof", "asof_grade", "asof_grade_label"),
    ]:
        for idx_id in INDEX_IDS:
            for sw in SIGNAL_WINDOWS:
                for hw in HOLDING_WINDOWS:
                    for g_num, g_label in GRADE_DEFS:
                        for scope in ["strict_ok_only", "usable"]:
                            mask = (
                                (merged["index_id"] == idx_id)
                                & (merged["signal_window"] == sw)
                                & (merged["holding_window"] == hw)
                                & (merged[grade_col] == g_num)
                            )
                            sub = merged[mask]
                            if sub.empty:
                                continue

                            # 质量过滤
                            if scope == "strict_ok_only":
                                sub = sub[
                                    (sub["signal_quality_status"] == "ok")
                                    & (sub["label_quality_status"] == "ok")
                                ]
                            else:
                                sub = sub[
                                    (~sub["signal_quality_status"].isin(["insufficient_data", "no_future_label"]))
                                    & (~sub["label_quality_status"].isin(["insufficient_data", "no_future_label"]))
                                ]

                            if sub.empty:
                                continue

                            stats = _compute_profile_stats(sub)
                            if stats:
                                rows.append({
                                    "index_id": idx_id,
                                    "signal_window": sw,
                                    "grade_mode": grade_mode,
                                    "grade": g_num,
                                    "grade_label": g_label,
                                    "holding_window": hw,
                                    "quality_scope": scope,
                                    "evaluation_mode": "all_signals",
                                    **stats,
                                })

    return pd.DataFrame(rows)


def compute_non_overlapping_profile(
    signals_df: pd.DataFrame,
    forward_labels_df: pd.DataFrame,
) -> pd.DataFrame:
    """计算 non_overlapping_profile.csv（相邻样本间隔 ≥ H）。"""
    merged = forward_labels_df.merge(
        signals_df[["date", "index_id", "signal_window", "standard_excess",
                     "signal_quality_status", "anchor_suspended",
                     "static_grade", "static_grade_label",
                     "asof_grade", "asof_grade_label"]],
        on=["date", "index_id"],
        how="left",
    )

    rows = []
    for grade_mode, grade_col, label_col in [
        ("static_full_sample", "static_grade", "static_grade_label"),
        ("asof", "asof_grade", "asof_grade_label"),
    ]:
        for idx_id in INDEX_IDS:
            for sw in SIGNAL_WINDOWS:
                for hw in HOLDING_WINDOWS:
                    for g_num, g_label in GRADE_DEFS:
                        for scope in ["strict_ok_only", "usable"]:
                            mask = (
                                (merged["index_id"] == idx_id)
                                & (merged["signal_window"] == sw)
                                & (merged["holding_window"] == hw)
                                & (merged[grade_col] == g_num)
                            )
                            sub = merged[mask].sort_values("date")

                            if scope == "strict_ok_only":
                                sub = sub[
                                    (sub["signal_quality_status"] == "ok")
                                    & (sub["label_quality_status"] == "ok")
                                ]
                            else:
                                sub = sub[
                                    (~sub["signal_quality_status"].isin(["insufficient_data", "no_future_label"]))
                                    & (~sub["label_quality_status"].isin(["insufficient_data", "no_future_label"]))
                                ]
                            sub = sub.sort_values("date")
                            selected_indices = []
                            last_date = None
                            for idx, row in sub.iterrows():
                                if last_date is None:
                                    selected_indices.append(idx)
                                    last_date = row["date"]
                                else:
                                    # 计算交易日间隔
                                    date_diff = _trading_day_diff(last_date, row["date"],
                                                                   merged[merged["index_id"] == idx_id]["date"].sort_values().unique())
                                    if date_diff >= hw:
                                        selected_indices.append(idx)
                                        last_date = row["date"]

                            sub = sub.loc[selected_indices]
                            if sub.empty:
                                continue

                            stats = _compute_profile_stats(sub)
                            if stats:
                                rows.append({
                                    "index_id": idx_id,
                                    "signal_window": sw,
                                    "grade_mode": grade_mode,
                                    "grade": g_num,
                                    "grade_label": g_label,
                                    "holding_window": hw,
                                    "quality_scope": scope,
                                    "evaluation_mode": "non_overlapping",
                                    **stats,
                                })

    return pd.DataFrame(rows)


def _trading_day_diff(date1: str, date2: str, all_dates: np.ndarray) -> int:
    """计算两个日期之间的交易日数量。"""
    d1_idx = np.searchsorted(all_dates, date1)
    d2_idx = np.searchsorted(all_dates, date2)
    return d2_idx - d1_idx


def compute_benchmark_comparison(
    signals_df: pd.DataFrame,
    forward_labels_df: pd.DataFrame,
) -> pd.DataFrame:
    """计算 benchmark_comparison.csv。"""
    merged = forward_labels_df.merge(
        signals_df[["date", "index_id", "signal_window", "standard_excess",
                     "signal_quality_status",
                     "static_grade", "static_grade_label",
                     "asof_grade", "asof_grade_label"]],
        on=["date", "index_id"],
        how="left",
    )

    rows = []
    for grade_mode, grade_col, label_col in [
        ("static_full_sample", "static_grade", "static_grade_label"),
        ("asof", "asof_grade", "asof_grade_label"),
    ]:
        for idx_id in INDEX_IDS:
            for sw in SIGNAL_WINDOWS:
                for hw in HOLDING_WINDOWS:
                    for g_num, g_label in GRADE_DEFS:
                        for scope in ["strict_ok_only", "usable"]:
                            mask = (
                                (merged["index_id"] == idx_id)
                                & (merged["signal_window"] == sw)
                                & (merged["holding_window"] == hw)
                                & (merged[grade_col] == g_num)
                            )
                            sub = merged[mask]
                            if scope == "strict_ok_only":
                                sub = sub[
                                    (sub["signal_quality_status"] == "ok")
                                    & (sub["label_quality_status"] == "ok")
                                ]
                            else:
                                sub = sub[
                                    (~sub["signal_quality_status"].isin(["insufficient_data", "no_future_label"]))
                                    & (~sub["label_quality_status"].isin(["insufficient_data", "no_future_label"]))
                                ]

                            if sub.empty:
                                continue

                            # 只用有效 future_excess 的行
                            sub_valid = sub[sub["future_excess"].notna()]
                            if sub_valid.empty:
                                continue

                            anchor_rets = sub_valid["future_anchor_return"].dropna()
                            excess_rets = sub_valid["future_excess"].dropna()

                            rows.append({
                                "index_id": idx_id,
                                "signal_window": sw,
                                "grade_mode": grade_mode,
                                "grade": g_num,
                                "holding_window": hw,
                                "quality_scope": scope,
                                "anchor_return_mean": anchor_rets.mean() if len(anchor_rets) > 0 else None,
                                "anchor_return_median": anchor_rets.median() if len(anchor_rets) > 0 else None,
                                "anchor_positive_rate": (anchor_rets > 0).mean() if len(anchor_rets) > 0 else None,
                                "excess_mean": excess_rets.mean() if len(excess_rets) > 0 else None,
                                "excess_median": excess_rets.median() if len(excess_rets) > 0 else None,
                                "excess_positive_rate": (excess_rets > 0).mean() if len(excess_rets) > 0 else None,
                                "sample_count": len(sub_valid),
                            })

    return pd.DataFrame(rows)


def compute_quality_sensitivity(
    signals_df: pd.DataFrame,
    forward_labels_df: pd.DataFrame,
) -> pd.DataFrame:
    """计算 quality_sensitivity.csv。"""
    merged = forward_labels_df.merge(
        signals_df[["date", "index_id", "signal_window", "standard_excess",
                     "signal_quality_status",
                     "static_grade", "static_grade_label",
                     "asof_grade", "asof_grade_label"]],
        on=["date", "index_id"],
        how="left",
    )

    rows = []
    for grade_mode, grade_col, label_col in [
        ("static_full_sample", "static_grade", "static_grade_label"),
        ("asof", "asof_grade", "asof_grade_label"),
    ]:
        for idx_id in INDEX_IDS:
            for sw in SIGNAL_WINDOWS:
                for hw in HOLDING_WINDOWS:
                    for g_num, g_label in GRADE_DEFS:
                        mask = (
                            (merged["index_id"] == idx_id)
                            & (merged["signal_window"] == sw)
                            & (merged["holding_window"] == hw)
                            & (merged[grade_col] == g_num)
                        )
                        sub = merged[mask]

                        # usable
                        usable = sub[
                            (~sub["signal_quality_status"].isin(["insufficient_data", "no_future_label"]))
                            & (~sub["label_quality_status"].isin(["insufficient_data", "no_future_label"]))
                        ]
                        # strict
                        strict = sub[
                            (sub["signal_quality_status"] == "ok")
                            & (sub["label_quality_status"] == "ok")
                        ]

                        if usable.empty and strict.empty:
                            continue

                        partial_count = len(usable) - len(strict)
                        partial_ratio = partial_count / len(usable) if len(usable) > 0 else None

                        def _stats(df, prefix):
                            valid = df[df["future_excess"].notna()]
                            anchor = valid["future_anchor_return"].dropna()
                            excess = valid["future_excess"].dropna()
                            return {
                                f"{prefix}_anchor_return_mean": anchor.mean() if len(anchor) > 0 else None,
                                f"{prefix}_anchor_return_median": anchor.median() if len(anchor) > 0 else None,
                                f"{prefix}_anchor_positive_rate": (anchor > 0).mean() if len(anchor) > 0 else None,
                                f"{prefix}_excess_mean": excess.mean() if len(excess) > 0 else None,
                                f"{prefix}_excess_median": excess.median() if len(excess) > 0 else None,
                                f"{prefix}_excess_positive_rate": (excess > 0).mean() if len(excess) > 0 else None,
                                f"{prefix}_sample_count": len(valid),
                            }

                        row = {
                            "index_id": idx_id,
                            "signal_window": sw,
                            "grade_mode": grade_mode,
                            "grade": g_num,
                            "holding_window": hw,
                            **_stats(usable, "usable"),
                            **_stats(strict, "strict"),
                            "partial_count": partial_count,
                            "partial_ratio": partial_ratio,
                        }
                        rows.append(row)

    return pd.DataFrame(rows)


# ── 文件校验和 ──


def _sha256_file(path: Path) -> str:
    """计算文件 SHA256。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── 主流程 ──


def build_excess_profile(input_dir: Path, output_dir: Path) -> dict:
    """构建标准指数超额画像分析，返回摘要 dict。"""
    print("[INFO] 读取输入数据...")
    excess_df, nav_df, manifest = load_input_data(input_dir)

    # Anchor 自身行情检查
    print("[INFO] 检查 Anchor 行情连续性...")
    anchor_suspended = check_anchor_continuity(excess_df)

    # 信号提取
    print("[INFO] 提取标准超额信号...")
    signals_df = extract_signals(excess_df)

    # 携带 data_status
    nav_status_map = {}
    for _, row in nav_df.iterrows():
        nav_status_map[(row["index_id"], row["trade_date"])] = {
            "data_status": row["data_status"],
            "fresh_quote_ratio": row["fresh_quote_ratio"],
            "universe_inclusion_ratio": row["universe_inclusion_ratio"],
            "stale_symbols": row.get("stale_symbols", ""),
        }

    signals_df["data_status"] = signals_df.apply(
        lambda r: nav_status_map.get((r["index_id"], r["date"]), {}).get("data_status", "insufficient_data"),
        axis=1,
    )
    signals_df["fresh_quote_ratio"] = signals_df.apply(
        lambda r: nav_status_map.get((r["index_id"], r["date"]), {}).get("fresh_quote_ratio", None),
        axis=1,
    )
    signals_df["universe_inclusion_ratio"] = signals_df.apply(
        lambda r: nav_status_map.get((r["index_id"], r["date"]), {}).get("universe_inclusion_ratio", None),
        axis=1,
    )
    signals_df["stale_symbols"] = signals_df.apply(
        lambda r: nav_status_map.get((r["index_id"], r["date"]), {}).get("stale_symbols", ""),
        axis=1,
    )

    # Anchor suspended 标记
    excess_date_to_suspended = dict(zip(excess_df["date"], anchor_suspended))
    signals_df["anchor_suspended"] = signals_df["date"].map(excess_date_to_suspended).fillna(False)

    # 区间质量
    print("[INFO] 计算信号区间质量...")
    signals_df = compute_signal_quality(signals_df, nav_df)

    # 分档
    print("[INFO] 计算 static 全样本分档...")
    signals_df, static_thresholds = compute_static_grades(signals_df)

    print("[INFO] 计算 asof 分档...")
    signals_df, asof_df = compute_asof_grades(signals_df)

    # Forward Labels
    print("[INFO] 计算 Forward Labels...")
    forward_labels_df = compute_forward_labels(signals_df, excess_df, nav_df)

    # 标签区间质量
    print("[INFO] 计算标签区间质量...")
    forward_labels_df = compute_label_quality(forward_labels_df, nav_df)

    # Profile 统计
    print("[INFO] 计算 grade_profile...")
    grade_profile_df = compute_grade_profile(signals_df, forward_labels_df)

    print("[INFO] 计算 non_overlapping_profile...")
    non_overlap_df = compute_non_overlapping_profile(signals_df, forward_labels_df)

    print("[INFO] 计算 benchmark_comparison...")
    benchmark_df = compute_benchmark_comparison(signals_df, forward_labels_df)

    print("[INFO] 计算 quality_sensitivity...")
    quality_df = compute_quality_sensitivity(signals_df, forward_labels_df)

    # 输出
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] 写入输出目录: {output_dir}")

    # signal_daily.csv
    signal_daily_cols = [
        "date", "index_id", "signal_window", "standard_excess", "data_status",
        "fresh_quote_ratio", "universe_inclusion_ratio", "stale_symbols",
        "signal_quality_status", "anchor_suspended",
        "static_grade", "static_grade_label", "asof_grade", "asof_grade_label",
    ]
    signals_df[signal_daily_cols].to_csv(output_dir / "signal_daily.csv", index=False)

    # forward_labels.csv
    label_cols = [
        "date", "index_id", "holding_window",
        "future_anchor_return", "future_index_return", "future_excess",
        "long_mfe", "long_mae", "short_mfe", "short_mae",
        "relative_long_mfe", "relative_long_mae",
        "relative_short_mfe", "relative_short_mae",
        "label_quality_status", "label_type",
    ]
    forward_labels_df[label_cols].to_csv(output_dir / "forward_labels.csv", index=False)

    # asof_grade_daily.csv
    asof_cols = [
        "date", "index_id", "signal_window", "standard_excess",
        "asof_grade", "asof_grade_label",
        "asof_p20", "asof_p40", "asof_p60", "asof_p80", "asof_sample_count",
    ]
    asof_df[asof_cols].to_csv(output_dir / "asof_grade_daily.csv", index=False)

    # grade_profile.csv
    grade_profile_df.to_csv(output_dir / "grade_profile.csv", index=False)

    # non_overlapping_profile.csv
    non_overlap_df.to_csv(output_dir / "non_overlapping_profile.csv", index=False)

    # benchmark_comparison.csv
    benchmark_df.to_csv(output_dir / "benchmark_comparison.csv", index=False)

    # quality_sensitivity.csv
    quality_df.to_csv(output_dir / "quality_sensitivity.csv", index=False)

    # static_thresholds.json
    thresholds_out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pool_config_version": manifest.get("pool_config_version", ""),
        "universe_mode": "constant_universe_research_view",
        "descriptive_only": True,
        "thresholds": static_thresholds,
    }
    with open(output_dir / "static_thresholds.json", "w") as f:
        json.dump(thresholds_out, f, indent=2, ensure_ascii=False)

    # build_manifest.json
    upstream_sha = _sha256_file(input_dir / "build_manifest.json")
    input_checksums = {
        "anchor_index_excess_csv_sha256": _sha256_file(input_dir / "anchor_index_excess.csv"),
        "custom_index_nav_csv_sha256": _sha256_file(input_dir / "custom_index_nav.csv"),
        "build_manifest_json_sha256": upstream_sha,
    }
    output_counts = {
        "signal_daily": len(signals_df),
        "forward_labels": len(forward_labels_df),
        "asof_grade_daily": len(asof_df),
        "grade_profile": len(grade_profile_df),
        "non_overlapping_profile": len(non_overlap_df),
        "benchmark_comparison": len(benchmark_df),
        "quality_sensitivity": len(quality_df),
    }
    build_manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pool_config_version": manifest.get("pool_config_version", ""),
        "universe_mode": "constant_universe_research_view",
        "price_adjustment_mode": "qfq",
        "source_data_as_of": manifest.get("source_data_as_of", ""),
        "upstream_build_manifest_sha256": upstream_sha,
        "input_checksums": input_checksums,
        "output_record_counts": output_counts,
    }
    with open(output_dir / "build_manifest.json", "w") as f:
        json.dump(build_manifest, f, indent=2, ensure_ascii=False)

    print("[OK] 构建完成")

    return {
        "manifest": build_manifest,
        "anchor_suspended_days": int(signals_df["anchor_suspended"].sum() // len(INDEX_IDS) / len(SIGNAL_WINDOWS)),
        "grade_profile_rows": len(grade_profile_df),
        "non_overlapping_rows": len(non_overlap_df),
    }
