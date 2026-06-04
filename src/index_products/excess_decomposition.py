"""
Q5 极热负超额来源拆解
======================
将负超额拆解为具体来源桶：Anchor 跌+指数涨、双跌 Anchor 跌更多、双涨 Anchor 涨更少、
Anchor 横盘+指数涨 等。回答"负超额到底来自哪里"的交易含义问题。

只读输入：已有画像产物（signal_daily.csv + forward_labels.csv），不重新计算信号/分档/标签。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.index_products.excess_profile import (
    SIGNAL_WINDOWS,
    HOLDING_WINDOWS,
    GRADE_DEFS,
    STATUS_ORDER,
)

# ── 常量 ──

FLAT_THRESHOLD = 0.5  # % — |anchor_ret| ≤ 此值视为横盘

TARGET_INDEX_ID = "industry_chain_index"

NEGATIVE_BUCKETS = [
    "anchor_down_index_up",
    "anchor_down_index_down_less",
    "anchor_up_index_up_less",
    "anchor_flat_index_up",
    "other_negative_excess",
]

POSITIVE_BUCKETS = [
    "anchor_up_outperform",
    "anchor_down_index_down_more",
    "anchor_flat_index_down",
    "other_positive_excess",
]

ALL_BUCKETS = NEGATIVE_BUCKETS + POSITIVE_BUCKETS

EXCLUDED_STATUSES = {"insufficient_data", "no_future_label"}


# ── 桶分类 ──


def classify_decomposition_bucket(
    anchor_ret: float,
    index_ret: float,
    excess: float,
    flat_threshold: float = FLAT_THRESHOLD,
) -> str:
    """根据 anchor_ret / index_ret / excess 将样本分入分解桶。

    flat 判断优先（|anchor_ret| ≤ flat_threshold 先匹配），
    然后按 sign 组合分类，最后兜底。
    """
    anchor_flat = abs(anchor_ret) <= flat_threshold

    if excess < 0:
        # ── 负超额 ──
        if anchor_flat and index_ret > 0:
            return "anchor_flat_index_up"
        if anchor_ret < -flat_threshold and index_ret > 0:
            return "anchor_down_index_up"
        if anchor_ret < -flat_threshold and index_ret < -flat_threshold and anchor_ret < index_ret:
            return "anchor_down_index_down_less"
        if anchor_ret > flat_threshold and index_ret > flat_threshold and anchor_ret < index_ret:
            return "anchor_up_index_up_less"
        return "other_negative_excess"
    else:
        # ── 正超额（含 0） ──
        if anchor_flat and index_ret < 0:
            return "anchor_flat_index_down"
        if anchor_ret > flat_threshold and index_ret > flat_threshold and anchor_ret > index_ret:
            return "anchor_up_outperform"
        if anchor_ret < -flat_threshold and index_ret < -flat_threshold and anchor_ret > index_ret:
            return "anchor_down_index_down_more"
        return "other_positive_excess"


# ── Daily 分解 ──


def compute_decomposition_daily(
    signal_df: pd.DataFrame,
    label_df: pd.DataFrame,
    index_id: str = TARGET_INDEX_ID,
    flat_threshold: float = FLAT_THRESHOLD,
) -> pd.DataFrame:
    """合并 signal + label → 逐行分类 → excess_decomposition_daily.csv。

    筛选条件：
      - index_id = industry_chain_index
      - asof_grade > 0
      - usable 口径（signal/label status ∉ excluded）
      - future_excess 非空
    """
    # 只取目标指数
    sig = signal_df[signal_df["index_id"] == index_id].copy()
    lab = label_df[label_df["index_id"] == index_id].copy()

    # 合并：signal 是每个 (date, signal_window) 一行，label 是每个 (date, holding_window) 一行
    # 合并键：date + index_id（signal_window 和 holding_window 独立维度，做 cross）
    # 实际：每条 signal 行对应多个 holding_window 的 label 行
    # 合并方式：先在 signal 侧展开，每行一个 signal_window；label 侧每行一个 holding_window
    # 合并键 = date（同一天的所有 signal_window × holding_window 组合）
    merged = lab.merge(
        sig[["date", "signal_window", "standard_excess",
             "signal_quality_status", "asof_grade", "asof_grade_label"]],
        on=["date"],
        how="inner",
    )

    # 筛选
    mask = (
        (merged["asof_grade"] > 0)
        & (~merged["signal_quality_status"].isin(EXCLUDED_STATUSES))
        & (~merged["label_quality_status"].isin(EXCLUDED_STATUSES))
        & merged["future_excess"].notna()
    )
    merged = merged[mask].copy()

    if merged.empty:
        return pd.DataFrame()

    # 逐行分类
    merged["excess_sign"] = np.where(merged["future_excess"] < 0, "negative", "positive")
    merged["decomposition_bucket"] = merged.apply(
        lambda r: classify_decomposition_bucket(
            r["future_anchor_return"],
            r["future_index_return"],
            r["future_excess"],
            flat_threshold,
        ),
        axis=1,
    )

    # 添加 grade 列（_mark_non_overlapping 需要用）
    merged["grade"] = merged["asof_grade"].astype(int)
    merged["grade_label"] = merged["asof_grade_label"]

    # non-overlapping 标记
    merged["is_non_overlapping"] = False
    merged = _mark_non_overlapping(merged)

    # 输出列
    out_cols = [
        "date", "index_id", "signal_window", "holding_window",
        "grade_mode", "grade", "grade_label",
        "future_anchor_return", "future_index_return", "future_excess",
        "excess_sign",
        "decomposition_bucket",
        "signal_quality_status", "label_quality_status",
        "is_non_overlapping",
    ]
    merged["grade_mode"] = "asof"

    return merged[out_cols].reset_index(drop=True)


def _mark_non_overlapping(df: pd.DataFrame) -> pd.DataFrame:
    """标记 is_non_overlapping：按 (signal_window, grade, holding_window) 分组，
    组内按时间排序，相邻样本间隔 ≥ H 个交易日。
    """
    all_dates = np.sort(df["date"].unique())

    for (sw, grade, hw), idx in df.groupby(["signal_window", "grade", "holding_window"]).groups.items():
        group = df.loc[idx].sort_values("date")
        selected = []
        last_date = None
        for row_idx, row in group.iterrows():
            if last_date is None:
                selected.append(row_idx)
                last_date = row["date"]
            else:
                diff = _trading_day_diff(last_date, row["date"], all_dates)
                if diff >= hw:
                    selected.append(row_idx)
                    last_date = row["date"]
        for i in selected:
            df.at[i, "is_non_overlapping"] = True

    return df


def _trading_day_diff(date1: str, date2: str, all_dates: np.ndarray) -> int:
    """计算两个日期之间的交易日数量。"""
    d1_idx = np.searchsorted(all_dates, date1)
    d2_idx = np.searchsorted(all_dates, date2)
    return d2_idx - d1_idx


# ── Profile 汇总 ──


def compute_decomposition_profile(daily_df: pd.DataFrame) -> pd.DataFrame:
    """按 (signal_window, holding_window, grade, evaluation_mode) 汇总 → 宽表一行一组。

    包含：
      - sample_count
      - negative/positive excess count + rate
      - 每个 bucket 的 count + rate_in_all + rate_in_negative/positive
    """
    if daily_df.empty:
        return pd.DataFrame()

    rows = []
    for (sw, hw, grade), group in daily_df.groupby(["signal_window", "holding_window", "grade"]):
        grade_label = group["grade_label"].iloc[0]

        for eval_mode, sub in [
            ("all_signals", group),
            ("non_overlapping", group[group["is_non_overlapping"]]),
        ]:
            n = len(sub)
            if n == 0:
                continue

            neg_sub = sub[sub["excess_sign"] == "negative"]
            pos_sub = sub[sub["excess_sign"] == "positive"]
            neg_count = len(neg_sub)
            pos_count = len(pos_sub)

            row = {
                "index_id": TARGET_INDEX_ID,
                "signal_window": sw,
                "holding_window": hw,
                "grade_mode": "asof",
                "grade": grade,
                "grade_label": grade_label,
                "evaluation_mode": eval_mode,
                "sample_count": n,
                "negative_excess_count": neg_count,
                "negative_excess_rate": neg_count / n,
                "positive_excess_count": pos_count,
                "positive_excess_rate": pos_count / n,
            }

            # 负超额桶
            for bucket in NEGATIVE_BUCKETS:
                bc = (neg_sub["decomposition_bucket"] == bucket).sum()
                row[f"{bucket}_count"] = bc
                row[f"{bucket}_rate_in_all"] = bc / n
                row[f"{bucket}_rate_in_negative"] = bc / neg_count if neg_count > 0 else 0.0

            # 正超额桶
            for bucket in POSITIVE_BUCKETS:
                bc = (pos_sub["decomposition_bucket"] == bucket).sum()
                row[f"{bucket}_count"] = bc
                row[f"{bucket}_rate_in_all"] = bc / n
                row[f"{bucket}_rate_in_positive"] = bc / pos_count if pos_count > 0 else 0.0

            rows.append(row)

    return pd.DataFrame(rows)


# ── 文件校验和 ──


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── 主流程 ──


def build_excess_decomposition(input_dir: Path, output_dir: Path) -> dict:
    """构建超额来源拆解，返回摘要 dict。

    输入：已有画像产物目录（含 signal_daily.csv + forward_labels.csv）
    输出：同目录下新增 excess_decomposition_daily.csv + excess_decomposition_profile.csv
    """
    print("[INFO] 读取已有画像产物...")
    signal_df = pd.read_csv(input_dir / "signal_daily.csv")
    label_df = pd.read_csv(input_dir / "forward_labels.csv")

    print("[INFO] 计算逐日分解...")
    daily_df = compute_decomposition_daily(signal_df, label_df)

    print("[INFO] 计算分档汇总 profile...")
    profile_df = compute_decomposition_profile(daily_df)

    # 输出
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] 写入输出目录: {output_dir}")

    daily_df.to_csv(output_dir / "excess_decomposition_daily.csv", index=False)
    profile_df.to_csv(output_dir / "excess_decomposition_profile.csv", index=False)

    # build_manifest 追加
    manifest_path = output_dir / "build_manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)
    else:
        manifest = {}

    manifest["decomposition_output"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "excess_decomposition_daily_rows": len(daily_df),
        "excess_decomposition_profile_rows": len(profile_df),
        "signal_daily_csv_sha256": _sha256_file(input_dir / "signal_daily.csv"),
        "forward_labels_csv_sha256": _sha256_file(input_dir / "forward_labels.csv"),
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("[OK] 分解构建完成")

    return {
        "daily_rows": len(daily_df),
        "profile_rows": len(profile_df),
    }
