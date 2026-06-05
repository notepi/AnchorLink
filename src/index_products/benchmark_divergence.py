"""
4 ETF 基准分歧分析
==================

分析四条 ETF 标准超额之间的一致与分歧，回答：
- 四指数对铂力特强弱方向什么时候一致？
- 什么时候 industry_chain 与辅助指数方向相反？
- 分歧日里，相对哪个基准的超额更稳定？
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

INDEX_IDS = [
    "industry_chain_index",
    "direct_peers_index",
    "theme_pool_index",
    "trading_watchlist_index",
]

AUX_INDEX_IDS = [
    "direct_peers_index",
    "theme_pool_index",
    "trading_watchlist_index",
]

MAIN_INDEX_ID = "industry_chain_index"

SIGNAL_WINDOWS = [1, 3, 5, 10]
HOLDING_WINDOWS = [1, 3, 5, 10]

DIRECTION_THRESHOLD = 0.5  # 百分点

INDEX_SHORT = {
    "industry_chain_index": "industry_chain",
    "direct_peers_index": "direct_peers",
    "theme_pool_index": "theme_pool",
    "trading_watchlist_index": "trading_watchlist",
}


# ── 数据读取 ──


def load_anchor_excess(input_dir: Path) -> pd.DataFrame:
    """加载 anchor_index_excess.csv。"""
    path = input_dir / "anchor_index_excess.csv"
    if not path.exists():
        raise FileNotFoundError(f"anchor_index_excess.csv 不存在: {path}")
    df = pd.read_csv(path)
    print(f"[INFO] anchor_index_excess 加载完成: {len(df)} 行")
    return df


def load_signal_daily(profiles_dir: Path) -> pd.DataFrame:
    """加载 signal_daily.csv 用于质量状态。"""
    path = profiles_dir / "signal_daily.csv"
    if not path.exists():
        raise FileNotFoundError(f"signal_daily.csv 不存在: {path}")
    df = pd.read_csv(path)
    print(f"[INFO] signal_daily 加载完成: {len(df)} 行")
    return df


def load_forward_labels(profiles_dir: Path) -> pd.DataFrame:
    """加载 forward_labels.csv。"""
    path = profiles_dir / "forward_labels.csv"
    if not path.exists():
        raise FileNotFoundError(f"forward_labels.csv 不存在: {path}")
    df = pd.read_csv(path)
    print(f"[INFO] forward_labels 加载完成: {len(df)} 行")
    return df


# ── 方向计算 ──


def compute_direction(excess: Optional[float]) -> str:
    """
    计算单指数方向。

    规则：
    - positive if excess > +0.5
    - negative if excess < -0.5
    - neutral if -0.5 <= excess <= +0.5 且非空
    - missing if excess 为空
    """
    if pd.isna(excess):
        return "missing"
    if excess > DIRECTION_THRESHOLD:
        return "positive"
    if excess < -DIRECTION_THRESHOLD:
        return "negative"
    return "neutral"


# ── 每日分歧判断 ──


def build_divergence_daily(
    excess_df: pd.DataFrame,
    signal_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    构建逐日分歧明细。

    步骤：
    1. 从 anchor_index_excess.csv 提取四指数超额（宽表 → 长表 → 宽表按 signal_window）
    2. 从 signal_daily.csv 获取质量状态
    3. 计算方向、一致性、分歧类型
    """
    rows = []

    for sw in SIGNAL_WINDOWS:
        for _, excess_row in excess_df.iterrows():
            date = excess_row["date"]
            anchor_return = excess_row.get(f"anchor_return_{sw}d")

            # 提取四指数超额
            excesses = {}
            for idx_id in INDEX_IDS:
                col = f"excess_vs_{idx_id}_{sw}d"
                excesses[idx_id] = excess_row.get(col)

            # 计算方向
            directions = {idx_id: compute_direction(excesses[idx_id]) for idx_id in INDEX_IDS}

            # 计数（missing 不计入 positive/negative/neutral）
            positive_count = sum(1 for d in directions.values() if d == "positive")
            negative_count = sum(1 for d in directions.values() if d == "negative")
            neutral_count = sum(1 for d in directions.values() if d == "neutral")
            missing_count = sum(1 for d in directions.values() if d == "missing")
            valid_index_count = positive_count + negative_count + neutral_count
            incomplete_signal = valid_index_count < 4

            # 主基准方向
            main_direction = directions[MAIN_INDEX_ID]

            # 辅助基准多数方向
            aux_directions = [directions[idx_id] for idx_id in AUX_INDEX_IDS]
            aux_positive_count = sum(1 for d in aux_directions if d == "positive")
            aux_negative_count = sum(1 for d in aux_directions if d == "negative")
            aux_neutral_count = sum(1 for d in aux_directions if d == "neutral")

            if aux_positive_count >= 2:
                aux_majority_direction = "positive"
            elif aux_negative_count >= 2:
                aux_majority_direction = "negative"
            else:
                aux_majority_direction = "neutral"

            # 分歧判定
            main_aux_divergence = (
                main_direction in {"positive", "negative"}
                and aux_majority_direction in {"positive", "negative"}
                and main_direction != aux_majority_direction
            )

            # 分歧类型（优先级从高到低）
            divergence_type = _classify_divergence(
                positive_count, negative_count,
                main_direction, aux_majority_direction
            )

            # 分歧强度
            main_excess = excesses[MAIN_INDEX_ID]
            aux_excess_vals = [excesses[idx_id] for idx_id in AUX_INDEX_IDS if pd.notna(excesses[idx_id])]
            aux_mean_excess = float(np.mean(aux_excess_vals)) if aux_excess_vals else None
            aux_median_excess = float(np.median(aux_excess_vals)) if aux_excess_vals else None
            main_aux_spread = None
            if pd.notna(main_excess) and aux_median_excess is not None:
                main_aux_spread = main_excess - aux_median_excess

            # 质量状态（从 signal_daily 获取）
            quality_statuses = {}
            for idx_id in INDEX_IDS:
                match = signal_df[
                    (signal_df["date"] == date)
                    & (signal_df["index_id"] == idx_id)
                    & (signal_df["signal_window"] == sw)
                ]
                if len(match) > 0:
                    quality_statuses[idx_id] = match.iloc[0]["signal_quality_status"]
                else:
                    quality_statuses[idx_id] = "insufficient_data"

            # 质量口径
            all_not_insuff = all(
                quality_statuses[idx_id] != "insufficient_data"
                for idx_id in INDEX_IDS
            )
            all_ok = all(
                quality_statuses[idx_id] == "ok"
                for idx_id in INDEX_IDS
            )

            if all_ok and not incomplete_signal:
                quality_scope = "strict_ok_only"
            elif all_not_insuff and not incomplete_signal:
                quality_scope = "usable"
            else:
                quality_scope = "unusable"

            rows.append({
                "date": date,
                "signal_window": sw,
                f"anchor_return_{sw}d": anchor_return,
                "excess_industry_chain": excesses["industry_chain_index"],
                "excess_direct_peers": excesses["direct_peers_index"],
                "excess_theme_pool": excesses["theme_pool_index"],
                "excess_trading_watchlist": excesses["trading_watchlist_index"],
                "direction_industry_chain": directions["industry_chain_index"],
                "direction_direct_peers": directions["direct_peers_index"],
                "direction_theme_pool": directions["theme_pool_index"],
                "direction_trading_watchlist": directions["trading_watchlist_index"],
                "positive_count": positive_count,
                "negative_count": negative_count,
                "neutral_count": neutral_count,
                "missing_count": missing_count,
                "valid_index_count": valid_index_count,
                "incomplete_signal": incomplete_signal,
                "main_direction": main_direction,
                "aux_majority_direction": aux_majority_direction,
                "main_aux_divergence": main_aux_divergence,
                "divergence_type": divergence_type,
                "main_excess": main_excess,
                "aux_mean_excess": aux_mean_excess,
                "aux_median_excess": aux_median_excess,
                "main_aux_spread": main_aux_spread,
                "signal_quality_status_industry_chain": quality_statuses["industry_chain_index"],
                "signal_quality_status_direct_peers": quality_statuses["direct_peers_index"],
                "signal_quality_status_theme_pool": quality_statuses["theme_pool_index"],
                "signal_quality_status_trading_watchlist": quality_statuses["trading_watchlist_index"],
                "quality_scope": quality_scope,
            })

    return pd.DataFrame(rows)


def _classify_divergence(
    positive_count: int,
    negative_count: int,
    main_direction: str,
    aux_majority_direction: str,
) -> str:
    """分歧类型分类（优先级从高到低）。"""
    # 1. 全一致
    if positive_count == 4:
        return "all_aligned_positive"
    if negative_count == 4:
        return "all_aligned_negative"
    # 2. 主辅分歧
    if main_direction == "positive" and aux_majority_direction == "negative":
        return "main_positive_aux_negative"
    if main_direction == "negative" and aux_majority_direction == "positive":
        return "main_negative_aux_positive"
    # 3. 主辅一侧中性
    if main_direction == "positive" and aux_majority_direction == "neutral":
        return "main_positive_aux_neutral"
    if main_direction == "negative" and aux_majority_direction == "neutral":
        return "main_negative_aux_neutral"
    if main_direction == "neutral" and aux_majority_direction == "positive":
        return "main_neutral_aux_positive"
    if main_direction == "neutral" and aux_majority_direction == "negative":
        return "main_neutral_aux_negative"
    # 4. 混合
    return "mixed_no_majority"


# ── Forward 标签透视 ──


def pivot_forward_labels(forward_df: pd.DataFrame) -> pd.DataFrame:
    """
    将 forward_labels 长表透视为宽表。

    每个 (date, holding_window) 一行，包含四条指数的 future_excess。
    """
    # 只保留需要的列
    keep_cols = ["date", "index_id", "holding_window",
                 "future_anchor_return", "future_index_return", "future_excess",
                 "label_quality_status"]
    df = forward_df[keep_cols].copy()

    # 透视：每个 index_id 的 future_excess 变成一列
    pivoted = df.pivot_table(
        index=["date", "holding_window", "future_anchor_return"],
        columns="index_id",
        values="future_excess",
        aggfunc="first",
    ).reset_index()

    # 重命名列
    rename_map = {idx_id: f"future_excess_{INDEX_SHORT[idx_id]}" for idx_id in INDEX_IDS if idx_id in pivoted.columns}
    pivoted = pivoted.rename(columns=rename_map)

    # 透视 label_quality_status
    label_pivot = df.pivot_table(
        index=["date", "holding_window"],
        columns="index_id",
        values="label_quality_status",
        aggfunc="first",
    ).reset_index()

    label_rename = {idx_id: f"label_quality_status_{INDEX_SHORT[idx_id]}" for idx_id in INDEX_IDS if idx_id in label_pivot.columns}
    label_pivot = label_pivot.rename(columns=label_rename)

    # 合并
    result = pd.merge(pivoted, label_pivot, on=["date", "holding_window"], how="left")

    # 计算 future_excess_aux_median
    aux_cols = [f"future_excess_{INDEX_SHORT[idx_id]}" for idx_id in AUX_INDEX_IDS]
    available_aux = [c for c in aux_cols if c in result.columns]
    if available_aux:
        result["future_excess_aux_median"] = result[available_aux].median(axis=1)
    else:
        result["future_excess_aux_median"] = None

    # 去掉 pivot 产生的列名层级
    result.columns.name = None

    return result


# ── Forward Joined ──


def build_divergence_forward(
    daily_df: pd.DataFrame,
    forward_wide: pd.DataFrame,
    signal_df: pd.DataFrame,
) -> pd.DataFrame:
    """连接分歧判断与未来标签。"""
    # daily 只保留 usable 和 strict_ok_only
    daily_valid = daily_df[daily_df["quality_scope"] != "unusable"].copy()

    # 连接
    joined = pd.merge(
        daily_valid,
        forward_wide,
        on=["date"],
        how="inner",
    )

    # 过滤 holding_window
    joined = joined[joined["holding_window"].isin(HOLDING_WINDOWS)].copy()

    # 计算 future_main_direction_correct
    joined["future_main_direction_correct"] = _compute_direction_correct(
        joined, "main_direction", "future_excess_industry_chain"
    )

    # 计算 future_aux_direction_correct
    joined["future_aux_direction_correct"] = _compute_direction_correct(
        joined, "aux_majority_direction", "future_excess_aux_median"
    )

    # 质量口径判断（需要四条指数 forward label 质量）
    def _forward_quality_scope(row):
        sig_ok = all(
            row.get(f"signal_quality_status_{INDEX_SHORT[idx_id]}") != "insufficient_data"
            for idx_id in INDEX_IDS
        )
        lbl_ok = all(
            row.get(f"label_quality_status_{INDEX_SHORT[idx_id]}") not in ["insufficient_data", "no_future_label"]
            for idx_id in INDEX_IDS
        )
        excess_ok = all(
            pd.notna(row.get(f"future_excess_{INDEX_SHORT[idx_id]}"))
            for idx_id in INDEX_IDS
        )
        sig_all_ok = all(
            row.get(f"signal_quality_status_{INDEX_SHORT[idx_id]}") == "ok"
            for idx_id in INDEX_IDS
        )
        lbl_all_ok = all(
            row.get(f"label_quality_status_{INDEX_SHORT[idx_id]}") == "ok"
            for idx_id in INDEX_IDS
        )

        if sig_all_ok and lbl_all_ok and excess_ok:
            return "strict_ok_only"
        elif sig_ok and lbl_ok and excess_ok:
            return "usable"
        return "unusable"

    # 同时满足两个口径的展开为两行
    rows = []
    for _, row in joined.iterrows():
        scope = _forward_quality_scope(row)
        if scope == "strict_ok_only":
            r1 = row.copy()
            r1["quality_scope"] = "strict_ok_only"
            rows.append(r1)
            r2 = row.copy()
            r2["quality_scope"] = "usable"
            rows.append(r2)
        elif scope == "usable":
            r1 = row.copy()
            r1["quality_scope"] = "usable"
            rows.append(r1)

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows).reset_index(drop=True)
    return result


def _compute_direction_correct(
    df: pd.DataFrame,
    direction_col: str,
    future_excess_col: str,
) -> pd.Series:
    """计算方向正确率。"""
    results = []
    for _, row in df.iterrows():
        direction = row[direction_col]
        future_excess = row[future_excess_col]

        if direction not in {"positive", "negative"} or pd.isna(future_excess):
            results.append(None)
            continue

        if direction == "positive" and future_excess > 0:
            results.append(True)
        elif direction == "negative" and future_excess < 0:
            results.append(True)
        else:
            results.append(False)

    return pd.Series(results, index=df.index)


# ── Profile 统计 ──


def _compute_profile_stats(df: pd.DataFrame) -> dict:
    """计算一组样本的统计指标。"""
    n = len(df)
    empty = {
        "sample_count": 0,
        "future_anchor_return_mean": None,
        "future_anchor_return_median": None,
        "future_anchor_positive_rate": None,
        "future_excess_main_mean": None,
        "future_excess_main_median": None,
        "future_excess_main_positive_rate": None,
        "future_excess_aux_median_mean": None,
        "future_excess_aux_median_median": None,
        "future_excess_aux_median_positive_rate": None,
        "future_excess_consensus_direction_rate": None,
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

    # 共识方向率：main 和 aux 方向都正确
    main_correct = df["future_main_direction_correct"]
    aux_correct = df["future_aux_direction_correct"]
    both_valid = main_correct.notna() & aux_correct.notna()
    if both_valid.sum() > 0:
        both_correct = (main_correct[both_valid] == True) & (aux_correct[both_valid] == True)
        consensus_rate = float(both_correct.mean() * 100)
    else:
        consensus_rate = None

    return {
        "sample_count": n,
        "future_anchor_return_mean": _safe_mean("future_anchor_return"),
        "future_anchor_return_median": _safe_median("future_anchor_return"),
        "future_anchor_positive_rate": _safe_pos_rate("future_anchor_return"),
        "future_excess_main_mean": _safe_mean("future_excess_industry_chain"),
        "future_excess_main_median": _safe_median("future_excess_industry_chain"),
        "future_excess_main_positive_rate": _safe_pos_rate("future_excess_industry_chain"),
        "future_excess_aux_median_mean": _safe_mean("future_excess_aux_median"),
        "future_excess_aux_median_median": _safe_median("future_excess_aux_median"),
        "future_excess_aux_median_positive_rate": _safe_pos_rate("future_excess_aux_median"),
        "future_excess_consensus_direction_rate": consensus_rate,
    }


def compute_divergence_profile(forward_df: pd.DataFrame) -> pd.DataFrame:
    """计算分歧画像。"""
    if len(forward_df) == 0 or "quality_scope" not in forward_df.columns:
        return pd.DataFrame()

    profiles = []

    for quality_scope in ["usable", "strict_ok_only"]:
        scope_df = forward_df[forward_df["quality_scope"] == quality_scope]
        if len(scope_df) == 0:
            continue

        for (sw, hw, div_type), group_df in scope_df.groupby(
            ["signal_window", "holding_window", "divergence_type"]
        ):
            stats = _compute_profile_stats(group_df)
            profiles.append({
                "signal_window": sw,
                "holding_window": hw,
                "divergence_type": div_type,
                "quality_scope": quality_scope,
                **stats,
            })

    return pd.DataFrame(profiles)


# ── Cases ──


def build_divergence_cases(
    daily_df: pd.DataFrame,
    forward_wide: pd.DataFrame,
) -> pd.DataFrame:
    """构建分歧案例明细。"""
    # 只保留主辅分歧日
    cases = daily_df[daily_df["main_aux_divergence"] == True].copy()

    if len(cases) == 0:
        return pd.DataFrame()

    # 连接未来标签（每个 holding_window）
    joined = pd.merge(cases, forward_wide, on=["date"], how="left")
    joined = joined[joined["holding_window"].isin(HOLDING_WINDOWS)].copy()

    return joined


# ── Summary ──


def compute_divergence_summary(
    daily_df: pd.DataFrame,
    profile_df: pd.DataFrame,
) -> dict:
    """计算分歧摘要。"""
    usable = daily_df[daily_df["quality_scope"] != "unusable"]

    summary = {}

    for sw in SIGNAL_WINDOWS:
        sw_daily = usable[usable["signal_window"] == sw]
        total = len(sw_daily)

        if total == 0:
            continue

        aligned = len(sw_daily[
            sw_daily["divergence_type"].isin(["all_aligned_positive", "all_aligned_negative"])
        ])
        diverged = len(sw_daily[sw_daily["main_aux_divergence"] == True])

        # 最常见分歧类型
        type_counts = sw_daily["divergence_type"].value_counts()

        # main_negative_aux_positive 样本数
        main_neg_aux_pos = sw_daily[sw_daily["divergence_type"] == "main_negative_aux_positive"]
        main_pos_aux_neg = sw_daily[sw_daily["divergence_type"] == "main_positive_aux_negative"]

        summary[f"signal_window_{sw}"] = {
            "total_days": int(total),
            "aligned_count": int(aligned),
            "aligned_rate": round(aligned / total * 100, 1) if total > 0 else 0,
            "diverged_count": int(diverged),
            "divergence_rate": round(diverged / total * 100, 1) if total > 0 else 0,
            "most_common_type": str(type_counts.index[0]) if len(type_counts) > 0 else None,
            "main_negative_aux_positive_count": int(len(main_neg_aux_pos)),
            "main_positive_aux_negative_count": int(len(main_pos_aux_neg)),
        }

    # 未来表现摘要（5D, T+5）
    for div_type in ["main_negative_aux_positive", "main_positive_aux_negative"]:
        sub = profile_df[
            (profile_df["signal_window"] == 5)
            & (profile_df["holding_window"] == 5)
            & (profile_df["divergence_type"] == div_type)
            & (profile_df["quality_scope"] == "usable")
        ]
        if len(sub) > 0:
            row = sub.iloc[0]
            summary[f"{div_type}_future"] = {
                "sample_count": int(row["sample_count"]) if pd.notna(row["sample_count"]) else 0,
                "future_anchor_return_median": float(row["future_anchor_return_median"]) if pd.notna(row["future_anchor_return_median"]) else None,
                "future_excess_main_median": float(row["future_excess_main_median"]) if pd.notna(row["future_excess_main_median"]) else None,
                "future_excess_aux_median_median": float(row["future_excess_aux_median_median"]) if pd.notna(row["future_excess_aux_median_median"]) else None,
            }

    return summary


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
    products_dir: Path,
    profiles_dir: Path,
    output_dir: Path,
    output_record_counts: dict[str, int],
) -> dict:
    """构建 build_manifest.json（双上游溯源）。"""
    # index_products manifest
    products_manifest_path = products_dir / "build_manifest.json"
    products_manifest_sha256 = ""
    source_data_as_of_products = ""
    if products_manifest_path.exists():
        products_manifest_sha256 = compute_file_checksum(products_manifest_path)
        with open(products_manifest_path) as f:
            pm = json.load(f)
        source_data_as_of_products = pm.get("source_data_as_of", "")

    # index_excess_profiles manifest
    profiles_manifest_path = profiles_dir / "build_manifest.json"
    profiles_manifest_sha256 = ""
    source_data_as_of_profiles = ""
    if profiles_manifest_path.exists():
        profiles_manifest_sha256 = compute_file_checksum(profiles_manifest_path)
        with open(profiles_manifest_path) as f:
            prm = json.load(f)
        source_data_as_of_profiles = prm.get("source_data_as_of", "")

    # 输入文件 checksum
    input_checksums = {}
    for fname in ["anchor_index_excess.csv"]:
        fpath = products_dir / fname
        if fpath.exists():
            input_checksums[f"{fname}_sha256"] = compute_file_checksum(fpath)
    for fname in ["forward_labels.csv", "signal_daily.csv"]:
        fpath = profiles_dir / fname
        if fpath.exists():
            input_checksums[f"{fname}_sha256"] = compute_file_checksum(fpath)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pool_config_version": "2026-05-06",
        "universe_mode": "constant_universe_research_view",
        "price_adjustment_mode": "qfq",
        "index_products_manifest_sha256": products_manifest_sha256,
        "index_excess_profiles_manifest_sha256": profiles_manifest_sha256,
        "source_data_as_of_index_products": source_data_as_of_products,
        "source_data_as_of_profiles": source_data_as_of_profiles,
        "input_checksums": input_checksums,
        "target_index_ids": INDEX_IDS,
        "signal_windows": SIGNAL_WINDOWS,
        "holding_windows": HOLDING_WINDOWS,
        "output_record_counts": output_record_counts,
    }
