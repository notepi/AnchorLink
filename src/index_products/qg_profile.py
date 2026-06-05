"""
标准指数超额 Q×G 网格画像
========================

Q 维度：标准超额的冷热位置（使用 asof_grade，不用 static_grade 做预测）
G 维度：标准超额的变化方向（delta 的 as-of expanding window 分档）

核心问题：
"铂力特相对产业链指数处于冷/热位置时，如果标准超额正在上升或下降，
未来 T+1 / T+3 / T+5 / T+10 更倾向均值回归、继续强化，还是无信号？"
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# ── 常量 ──

TARGET_INDEX_ID = "industry_chain_index"
TARGET_SIGNAL_WINDOWS = [5, 10]
TARGET_HOLDING_WINDOWS = [1, 3, 5, 10]
MIN_G_HISTORY = 60

G_GRADE_LABELS = {
    1: "大降",
    2: "小降",
    3: "稳定",
    4: "小升",
    5: "大升",
    0: "insufficient_g_history",
}

Q_ZONE_MAP = {1: "冷端", 2: "冷端", 3: "中性", 4: "热端", 5: "热端"}
G_ZONE_MAP = {1: "下降", 2: "下降", 3: "稳定", 4: "上升", 5: "上升"}


# ── 数据读取 ──


def load_signal_daily(input_dir: Path) -> pd.DataFrame:
    """加载 signal_daily.csv，只保留 TARGET_INDEX_ID 和 TARGET_SIGNAL_WINDOWS。"""
    path = input_dir / "signal_daily.csv"
    if not path.exists():
        raise FileNotFoundError(f"signal_daily.csv 不存在: {path}")

    df = pd.read_csv(path)
    df = df[
        (df["index_id"] == TARGET_INDEX_ID)
        & (df["signal_window"].isin(TARGET_SIGNAL_WINDOWS))
    ].copy()
    print(f"[INFO] signal_daily 加载完成: {len(df)} 行 (index_id={TARGET_INDEX_ID}, signal_window={TARGET_SIGNAL_WINDOWS})")
    return df


def load_forward_labels(input_dir: Path) -> pd.DataFrame:
    """加载 forward_labels.csv，只保留 TARGET_INDEX_ID 和 TARGET_HOLDING_WINDOWS。"""
    path = input_dir / "forward_labels.csv"
    if not path.exists():
        raise FileNotFoundError(f"forward_labels.csv 不存在: {path}")

    df = pd.read_csv(path)
    df = df[
        (df["index_id"] == TARGET_INDEX_ID)
        & (df["holding_window"].isin(TARGET_HOLDING_WINDOWS))
    ].copy()
    print(f"[INFO] forward_labels 加载完成: {len(df)} 行")
    return df


# ── Delta 计算 ──


def compute_standard_excess_delta(signal_df: pd.DataFrame) -> pd.DataFrame:
    """
    计算 standard_excess_delta。

    规则：
    - 只在同一个 index_id、同一个 signal_window 内计算 delta，不跨窗口
    - 第一条有效 delta 为空
    - 如果 t 或 t-1 的 standard_excess 为空 → delta 为空
    - 如果 t 或 t-1 的 signal_quality_status == insufficient_data → delta 为空
    """
    df = signal_df.copy()
    df = df.sort_values(["index_id", "signal_window", "date"]).reset_index(drop=True)
    df["standard_excess_delta"] = np.nan

    for (_idx_id, sw), group in df.groupby(["index_id", "signal_window"]):
        indices = group.index.tolist()
        for i, idx in enumerate(indices):
            if i == 0:
                continue
            prev_idx = indices[i - 1]
            curr = df.loc[idx]
            prev = df.loc[prev_idx]

            if pd.isna(curr["standard_excess"]) or pd.isna(prev["standard_excess"]):
                continue
            if curr["signal_quality_status"] == "insufficient_data":
                continue
            if prev["signal_quality_status"] == "insufficient_data":
                continue

            df.loc[idx, "standard_excess_delta"] = (
                curr["standard_excess"] - prev["standard_excess"]
            )

    return df


# ── G 分档 ──


def compute_g_grade_asof(signal_df: pd.DataFrame) -> pd.DataFrame:
    """
    计算 G 分档（as-of expanding window）。

    规则：
    - 在日期 t 给 delta 分 G 档时，只能使用 t-1 及以前的 delta 历史
    - 最少需要 60 个非空且非 insufficient_data 的历史 delta
    - G1: x <= P20, G2: P20 < x <= P40, G3: P40 < x <= P60, G4: P60 < x <= P80, G5: x > P80
    - 历史不足 → g_grade=0, g_grade_label=insufficient_g_history
    """
    df = signal_df.copy()
    df = df.sort_values(["index_id", "signal_window", "date"]).reset_index(drop=True)
    df["g_grade"] = 0
    df["g_grade_label"] = G_GRADE_LABELS[0]

    for (_idx_id, sw), group in df.groupby(["index_id", "signal_window"]):
        indices = group.index.tolist()
        history_deltas: list[float] = []

        for i, idx in enumerate(indices):
            row = df.loc[idx]
            delta = row["standard_excess_delta"]

            is_valid = (
                pd.notna(delta)
                and row["signal_quality_status"] != "insufficient_data"
            )

            # 分档使用历史（不包含当前）
            if len(history_deltas) >= MIN_G_HISTORY and is_valid:
                hist_arr = np.array(history_deltas)
                p20 = np.percentile(hist_arr, 20)
                p40 = np.percentile(hist_arr, 40)
                p60 = np.percentile(hist_arr, 60)
                p80 = np.percentile(hist_arr, 80)

                if delta <= p20:
                    g = 1
                elif delta <= p40:
                    g = 2
                elif delta <= p60:
                    g = 3
                elif delta <= p80:
                    g = 4
                else:
                    g = 5

                df.loc[idx, "g_grade"] = g
                df.loc[idx, "g_grade_label"] = G_GRADE_LABELS[g]

            # 当前 delta 有效则加入历史
            if is_valid:
                history_deltas.append(delta)

    return df


# ── Q×G 信号明细 ──


def build_qg_signal_daily(signal_df: pd.DataFrame) -> pd.DataFrame:
    """构建 qg_signal_daily：包含 Q 和 G 分档的信号明细。"""
    df = compute_standard_excess_delta(signal_df)
    df = compute_g_grade_asof(df)

    # Q 分档使用 asof_grade
    df = df.rename(columns={
        "asof_grade": "q_grade",
        "asof_grade_label": "q_grade_label",
    })

    # insufficient_data / insufficient_grade_history 的 Q 标记为 0
    mask_insuff = df["q_grade_label"].isin([
        "insufficient_data",
        "insufficient_grade_history",
    ])
    df.loc[mask_insuff, "q_grade"] = 0

    output_cols = [
        "date", "index_id", "signal_window", "standard_excess",
        "standard_excess_delta", "q_grade", "q_grade_label",
        "g_grade", "g_grade_label", "signal_quality_status",
        "anchor_suspended", "fresh_quote_ratio",
        "universe_inclusion_ratio", "stale_symbols",
    ]
    return df[output_cols].copy()


# ── Forward Joined ──


def build_qg_forward_joined(
    qg_signal_df: pd.DataFrame,
    forward_labels_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    构建 qg_forward_joined：信号与未来标签连接。

    同时满足 usable 和 strict_ok_only 的样本输出两行，
    分别对应 quality_scope = strict_ok_only / usable。
    """
    signal_cols = [
        "date", "index_id", "signal_window", "standard_excess",
        "standard_excess_delta", "q_grade", "q_grade_label",
        "g_grade", "g_grade_label", "signal_quality_status",
    ]
    label_cols = [
        "date", "index_id", "holding_window",
        "future_anchor_return", "future_index_return", "future_excess",
        "long_mfe", "long_mae", "short_mfe", "short_mae",
        "relative_long_mfe", "relative_long_mae",
        "relative_short_mfe", "relative_short_mae",
        "label_quality_status",
    ]

    signal_df = qg_signal_df[signal_cols].copy()
    label_df = forward_labels_df[label_cols].copy()

    joined = pd.merge(signal_df, label_df, on=["date", "index_id"], how="inner")

    # 判断质量口径
    def _is_usable(row):
        return (
            row["signal_quality_status"] != "insufficient_data"
            and row["label_quality_status"] not in ["insufficient_data", "no_future_label"]
            and pd.notna(row["future_excess"])
        )

    def _is_strict_ok(row):
        return (
            row["signal_quality_status"] == "ok"
            and row["label_quality_status"] == "ok"
            and pd.notna(row["future_excess"])
        )

    # 展开为两行：strict_ok_only 和 usable
    rows = []
    for _, row in joined.iterrows():
        is_strict = _is_strict_ok(row)
        is_usable = _is_usable(row)

        if is_strict:
            r1 = row.copy()
            r1["quality_scope"] = "strict_ok_only"
            rows.append(r1)
            r2 = row.copy()
            r2["quality_scope"] = "usable"
            rows.append(r2)
        elif is_usable:
            r1 = row.copy()
            r1["quality_scope"] = "usable"
            rows.append(r1)

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows).reset_index(drop=True)
    return result


# ── Non-overlapping 选择 ──


def select_non_overlapping_samples(
    df: pd.DataFrame,
    holding_window: int,
    all_dates: list[str],
) -> pd.DataFrame:
    """
    选择非重叠样本。

    规则：
    - 按 date 排序
    - 相邻样本间隔至少为 holding_window 个交易日
    - 交易日间隔必须基于完整 signal_daily.csv 的日期序列
    """
    if len(df) == 0:
        return df

    date_to_idx = {d: i for i, d in enumerate(sorted(all_dates))}
    df = df.sort_values("date").reset_index(drop=True)

    selected = []
    last_date_idx = -holding_window - 1

    for i, row in df.iterrows():
        d = row["date"]
        if d not in date_to_idx:
            continue
        curr_idx = date_to_idx[d]
        if curr_idx - last_date_idx >= holding_window:
            selected.append(i)
            last_date_idx = curr_idx

    return df.loc[selected].copy()


# ── 统计计算 ──


def _compute_stats(df: pd.DataFrame) -> dict:
    """计算一组样本的统计指标。"""
    n = len(df)
    empty = {
        "sample_count": 0,
        "future_anchor_return_mean": None,
        "future_anchor_return_median": None,
        "future_anchor_positive_rate": None,
        "future_anchor_negative_rate": None,
        "future_excess_mean": None,
        "future_excess_median": None,
        "future_excess_positive_rate": None,
        "future_excess_negative_rate": None,
        "long_mfe_mean": None,
        "long_mae_mean": None,
        "short_mfe_mean": None,
        "short_mae_mean": None,
        "relative_long_mfe_mean": None,
        "relative_long_mae_mean": None,
        "relative_short_mfe_mean": None,
        "relative_short_mae_mean": None,
        "partial_sample_count": None,
        "partial_sample_ratio": None,
    }

    if n == 0:
        return empty

    def _safe_mean(col):
        vals = df[col].dropna()
        return float(vals.mean()) if len(vals) > 0 else None

    def _safe_median(col):
        vals = df[col].dropna()
        return float(vals.median()) if len(vals) > 0 else None

    def _safe_pos_rate(col):
        vals = df[col].dropna()
        return float((vals > 0).mean() * 100) if len(vals) > 0 else None

    def _safe_neg_rate(col):
        vals = df[col].dropna()
        return float((vals < 0).mean() * 100) if len(vals) > 0 else None

    partial_count = len(df[
        (df["signal_quality_status"] == "partial")
        | (df["label_quality_status"] == "partial")
    ])

    return {
        "sample_count": n,
        "future_anchor_return_mean": _safe_mean("future_anchor_return"),
        "future_anchor_return_median": _safe_median("future_anchor_return"),
        "future_anchor_positive_rate": _safe_pos_rate("future_anchor_return"),
        "future_anchor_negative_rate": _safe_neg_rate("future_anchor_return"),
        "future_excess_mean": _safe_mean("future_excess"),
        "future_excess_median": _safe_median("future_excess"),
        "future_excess_positive_rate": _safe_pos_rate("future_excess"),
        "future_excess_negative_rate": _safe_neg_rate("future_excess"),
        "long_mfe_mean": _safe_mean("long_mfe"),
        "long_mae_mean": _safe_mean("long_mae"),
        "short_mfe_mean": _safe_mean("short_mfe"),
        "short_mae_mean": _safe_mean("short_mae"),
        "relative_long_mfe_mean": _safe_mean("relative_long_mfe"),
        "relative_long_mae_mean": _safe_mean("relative_long_mae"),
        "relative_short_mfe_mean": _safe_mean("relative_short_mfe"),
        "relative_short_mae_mean": _safe_mean("relative_short_mae"),
        "partial_sample_count": partial_count,
        "partial_sample_ratio": float(partial_count / n * 100) if n > 0 else None,
    }


# ── Grid Profile ──


def compute_grid_profile(
    joined_df: pd.DataFrame,
    all_dates: list[str],
) -> pd.DataFrame:
    """计算 Q×G 网格画像。"""
    profiles = []

    for quality_scope in ["usable", "strict_ok_only"]:
        scope_df = joined_df[joined_df["quality_scope"] == quality_scope]
        if len(scope_df) == 0:
            continue

        group_cols = [
            "index_id", "signal_window", "holding_window",
            "q_grade", "q_grade_label", "g_grade", "g_grade_label",
        ]

        for group_key, group_df in scope_df.groupby(group_cols):
            idx_id, sw, hw, q_grade, q_label, g_grade, g_label = group_key

            # 只统计有效 Q/G 分档
            if q_grade not in {1, 2, 3, 4, 5} or g_grade not in {1, 2, 3, 4, 5}:
                continue

            # all_signals
            stats_all = _compute_stats(group_df)
            profiles.append({
                "index_id": idx_id,
                "signal_window": sw,
                "holding_window": hw,
                "q_grade": q_grade,
                "q_grade_label": q_label,
                "g_grade": g_grade,
                "g_grade_label": g_label,
                "quality_scope": quality_scope,
                "evaluation_mode": "all_signals",
                **stats_all,
            })

            # non_overlapping
            non_overlap = select_non_overlapping_samples(group_df, hw, all_dates)
            stats_no = _compute_stats(non_overlap)
            profiles.append({
                "index_id": idx_id,
                "signal_window": sw,
                "holding_window": hw,
                "q_grade": q_grade,
                "q_grade_label": q_label,
                "g_grade": g_grade,
                "g_grade_label": g_label,
                "quality_scope": quality_scope,
                "evaluation_mode": "non_overlapping",
                **stats_no,
            })

    return pd.DataFrame(profiles)


# ── Quadrant Profile ──



def compute_quadrant_profile(
    joined_df: pd.DataFrame,
    all_dates: list[str],
) -> pd.DataFrame:
    """计算四象限画像。直接从 joined 明细聚合，不从 grid 二次聚合。"""
    # 为每行添加 zone 列
    df = joined_df.copy()
    df["q_zone"] = df["q_grade"].map(Q_ZONE_MAP)
    df["g_zone"] = df["g_grade"].map(G_ZONE_MAP)

    # 过滤无效 zone
    df = df[df["q_zone"].notna() & df["g_zone"].notna()].copy()

    profiles = []

    for quality_scope in ["usable", "strict_ok_only"]:
        scope_df = df[df["quality_scope"] == quality_scope]
        if len(scope_df) == 0:
            continue

        for (sw, hw, q_zone, g_zone), group_df in scope_df.groupby(
            ["signal_window", "holding_window", "q_zone", "g_zone"]
        ):
            # all_signals
            stats_all = _compute_stats(group_df)
            profiles.append({
                "signal_window": sw,
                "holding_window": hw,
                "q_zone": q_zone,
                "g_zone": g_zone,
                "quality_scope": quality_scope,
                "evaluation_mode": "all_signals",
                **stats_all,
            })

            # non_overlapping
            non_overlap = select_non_overlapping_samples(group_df, hw, all_dates)
            stats_no = _compute_stats(non_overlap)
            profiles.append({
                "signal_window": sw,
                "holding_window": hw,
                "q_zone": q_zone,
                "g_zone": g_zone,
                "quality_scope": quality_scope,
                "evaluation_mode": "non_overlapping",
                **stats_no,
            })

    return pd.DataFrame(profiles)


# ── G 阈值摘要 ──


def compute_g_thresholds(signal_df: pd.DataFrame) -> list[dict]:
    """计算 G 阈值历史摘要。"""
    thresholds = []

    for sw in TARGET_SIGNAL_WINDOWS:
        window_df = signal_df[
            signal_df["signal_window"] == sw
        ].sort_values("date")

        valid = window_df[
            window_df["standard_excess_delta"].notna()
            & (window_df["signal_quality_status"] != "insufficient_data")
        ]
        deltas = valid["standard_excess_delta"].values

        if len(deltas) >= MIN_G_HISTORY:
            thresholds.append({
                "signal_window": sw,
                "min_history": MIN_G_HISTORY,
                "latest_p20": round(float(np.percentile(deltas, 20)), 6),
                "latest_p40": round(float(np.percentile(deltas, 40)), 6),
                "latest_p60": round(float(np.percentile(deltas, 60)), 6),
                "latest_p80": round(float(np.percentile(deltas, 80)), 6),
                "latest_sample_count": len(deltas),
                "latest_trade_date": str(window_df["date"].iloc[-1]),
            })

    return thresholds


# ── 文件 checksum ──


def compute_file_checksum(file_path: Path) -> str:
    """计算文件 SHA256。"""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


# ── Build Manifest ──


def build_manifest(
    input_dir: Path,
    output_dir: Path,
    output_record_counts: dict[str, int],
) -> dict:
    """构建 build_manifest.json。"""
    upstream_path = input_dir / "build_manifest.json"
    upstream_manifest = {}
    upstream_manifest_sha256 = ""
    source_data_as_of = ""

    if upstream_path.exists():
        # 计算上游 manifest 文件自身的 SHA256
        upstream_manifest_sha256 = compute_file_checksum(upstream_path)
        with open(upstream_path) as f:
            upstream_manifest = json.load(f)
        # source_data_as_of 从上游继承，不用自己的生成日期
        source_data_as_of = upstream_manifest.get("source_data_as_of", "")

    input_checksums = {}
    for fname in ["signal_daily.csv", "forward_labels.csv"]:
        fpath = input_dir / fname
        if fpath.exists():
            input_checksums[f"{fname}_sha256"] = compute_file_checksum(fpath)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "pool_config_version": "2026-05-06",
        "universe_mode": "constant_universe_research_view",
        "price_adjustment_mode": "qfq",
        "source_data_as_of": source_data_as_of,
        "upstream_profile_manifest_sha256": upstream_manifest_sha256,
        "input_checksums": input_checksums,
        "output_record_counts": output_record_counts,
        "target_index_id": TARGET_INDEX_ID,
        "target_signal_windows": TARGET_SIGNAL_WINDOWS,
    }
