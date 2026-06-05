#!/usr/bin/env python3
"""
构建标准指数超额 Q×G 网格画像

用法：
    python scripts/build_standard_index_qg_profile.py

输入：
    data/price/analytics/index_excess_profiles/constant_universe_2026-05-06/

输出：
    data/price/analytics/index_excess_qg_profiles/constant_universe_2026-05-06/
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.index_products.qg_profile import (
    TARGET_INDEX_ID,
    TARGET_SIGNAL_WINDOWS,
    Q_ZONE_MAP,
    G_ZONE_MAP,
    load_signal_daily,
    load_forward_labels,
    build_qg_signal_daily,
    build_qg_forward_joined,
    compute_grid_profile,
    compute_quadrant_profile,
    compute_g_thresholds,
    build_manifest,
)


INPUT_DIR = PROJECT_ROOT / "data" / "price" / "analytics" / "index_excess_profiles" / "constant_universe_2026-05-06"
OUTPUT_DIR = PROJECT_ROOT / "data" / "price" / "analytics" / "index_excess_qg_profiles" / "constant_universe_2026-05-06"


def main() -> None:
    print("=" * 60)
    print("标准指数超额 Q×G 网格画像")
    print("=" * 60)

    # 验证输入目录
    if not INPUT_DIR.exists():
        raise FileNotFoundError(f"输入目录不存在: {INPUT_DIR}")

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] 输出目录: {OUTPUT_DIR}")

    # 记录旧文件 checksum（用于验证不被修改）
    old_files_checksums: dict[str, str] = {}
    for old_dir in [
        PROJECT_ROOT / "data" / "price" / "analytics" / "index_products",
        PROJECT_ROOT / "data" / "price" / "analytics" / "index_excess_profiles",
    ]:
        if old_dir.exists():
            for f in old_dir.rglob("*.csv"):
                import hashlib
                sha = hashlib.sha256()
                with open(f, "rb") as fh:
                    for chunk in iter(lambda: fh.read(4096), b""):
                        sha.update(chunk)
                old_files_checksums[str(f)] = sha.hexdigest()

    # ── Step 1: 加载数据 ──
    print("\n[Step 1/6] 加载输入数据...")
    signal_df = load_signal_daily(INPUT_DIR)
    forward_df = load_forward_labels(INPUT_DIR)

    # 获取完整交易日历（用于 non-overlapping）
    all_dates = sorted(signal_df["date"].unique().tolist())
    print(f"[INFO] 完整交易日历: {len(all_dates)} 天")

    # ── Step 2: 构建 Q×G 信号明细 ──
    print("\n[Step 2/6] 构建 Q×G 信号明细...")
    qg_signal_df = build_qg_signal_daily(signal_df)

    # 输出统计
    valid_qg = qg_signal_df[
        (qg_signal_df["q_grade"].isin([1, 2, 3, 4, 5]))
        & (qg_signal_df["g_grade"].isin([1, 2, 3, 4, 5]))
    ]
    print(f"[INFO] qg_signal_daily: {len(qg_signal_df)} 行, 有效 Q×G: {len(valid_qg)} 行")
    for sw in TARGET_SIGNAL_WINDOWS:
        sub = qg_signal_df[qg_signal_df["signal_window"] == sw]
        g_insuff = (sub["g_grade"] == 0).sum()
        print(f"  signal_window={sw}: {len(sub)} 行, insufficient_g_history: {g_insuff}")

    # 保存
    qg_signal_path = OUTPUT_DIR / "qg_signal_daily.csv"
    qg_signal_df.to_csv(qg_signal_path, index=False)
    print(f"[OK] qg_signal_daily.csv 写入: {len(qg_signal_df)} 行")

    # ── Step 3: 构建 Forward Joined ──
    print("\n[Step 3/6] 构建 Q×G Forward Joined...")
    joined_df = build_qg_forward_joined(qg_signal_df, forward_df)

    usable_count = (joined_df["quality_scope"] == "usable").sum()
    strict_count = (joined_df["quality_scope"] == "strict_ok_only").sum()
    print(f"[INFO] qg_forward_joined: {len(joined_df)} 行")
    print(f"  usable: {usable_count}, strict_ok_only: {strict_count}")

    # 保存
    joined_path = OUTPUT_DIR / "qg_forward_joined.csv"
    joined_df.to_csv(joined_path, index=False)
    print(f"[OK] qg_forward_joined.csv 写入: {len(joined_df)} 行")

    # ── Step 4: 计算 Grid Profile ──
    print("\n[Step 4/6] 计算 Q×G 网格画像...")
    grid_df = compute_grid_profile(joined_df, all_dates)

    # 统计样本不足的格子
    low_sample = grid_df[
        (grid_df["evaluation_mode"] == "all_signals")
        & (grid_df["quality_scope"] == "usable")
        & (grid_df["sample_count"] < 5)
    ]
    print(f"[INFO] qg_grid_profile: {len(grid_df)} 行")
    print(f"  样本不足(<5)的格子: {len(low_sample)}")

    # 保存
    grid_path = OUTPUT_DIR / "qg_grid_profile.csv"
    grid_df.to_csv(grid_path, index=False)
    print(f"[OK] qg_grid_profile.csv 写入: {len(grid_df)} 行")

    # ── Step 5: 计算 Quadrant Profile + G 阈值 ──
    print("\n[Step 5/6] 计算四象限画像 + G 阈值...")
    quadrant_df = compute_quadrant_profile(joined_df, all_dates)
    print(f"[INFO] qg_quadrant_profile: {len(quadrant_df)} 行")

    quadrant_path = OUTPUT_DIR / "qg_quadrant_profile.csv"
    quadrant_df.to_csv(quadrant_path, index=False)
    print(f"[OK] qg_quadrant_profile.csv 写入: {len(quadrant_df)} 行")

    # G 阈值
    import json
    thresholds = compute_g_thresholds(qg_signal_df)
    thresholds_path = OUTPUT_DIR / "qg_thresholds.json"
    with open(thresholds_path, "w", encoding="utf-8") as f:
        json.dump(thresholds, f, ensure_ascii=False, indent=2)
    print(f"[OK] qg_thresholds.json 写入: {len(thresholds)} 个窗口")
    for t in thresholds:
        print(f"  signal_window={t['signal_window']}: P20={t['latest_p20']:.4f}, "
              f"P40={t['latest_p40']:.4f}, P60={t['latest_p60']:.4f}, "
              f"P80={t['latest_p80']:.4f} (n={t['latest_sample_count']})")

    # ── Step 6: Build Manifest ──
    print("\n[Step 6/6] 构建 Manifest...")
    output_counts = {
        "qg_signal_daily": len(qg_signal_df),
        "qg_forward_joined": len(joined_df),
        "qg_grid_profile": len(grid_df),
        "qg_quadrant_profile": len(quadrant_df),
    }
    manifest = build_manifest(INPUT_DIR, OUTPUT_DIR, output_counts)
    manifest_path = OUTPUT_DIR / "build_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[OK] build_manifest.json 写入完成")

    # ── 验证旧文件未被修改 ──
    print("\n[验证] 检查旧数据未被修改...")
    import hashlib
    all_ok = True
    for fpath, old_sha in old_files_checksums.items():
        sha = hashlib.sha256()
        with open(fpath, "rb") as fh:
            for chunk in iter(lambda: fh.read(4096), b""):
                sha.update(chunk)
        if sha.hexdigest() != old_sha:
            print(f"[ERROR] 文件被修改: {fpath}")
            all_ok = False
    if all_ok:
        print("[OK] 旧数据未被修改")

    # ── 核心结论摘要 ──
    print("\n" + "=" * 60)
    print("核心结论摘要")
    print("=" * 60)

    for sw in TARGET_SIGNAL_WINDOWS:
        print(f"\n--- signal_window = {sw}D ---")
        usable_grid = grid_df[
            (grid_df["signal_window"] == sw)
            & (grid_df["evaluation_mode"] == "all_signals")
            & (grid_df["quality_scope"] == "usable")
        ]

        # Q5 极热分析
        q5 = usable_grid[usable_grid["q_grade"] == 5]
        for _, row in q5.iterrows():
            hw = row["holding_window"]
            g = row["g_grade"]
            excess_med = row["future_excess_median"]
            anchor_med = row["future_anchor_return_median"]
            excess_pos = row["future_excess_positive_rate"]
            n = row["sample_count"]
            if pd.notna(excess_med):
                direction = "正超额" if excess_med > 0 else "负超额"
                print(f"  Q5-G{g} T+{hw}: n={n}, 超额中位数={excess_med:+.2f}%, "
                      f"Anchor中位数={anchor_med:+.2f}%, 超额胜率={excess_pos:.0f}% [{direction}]")

        # Q1 极冷分析
        q1 = usable_grid[usable_grid["q_grade"] == 1]
        for _, row in q1.iterrows():
            hw = row["holding_window"]
            g = row["g_grade"]
            excess_med = row["future_excess_median"]
            anchor_med = row["future_anchor_return_median"]
            excess_pos = row["future_excess_positive_rate"]
            n = row["sample_count"]
            if pd.notna(excess_med):
                direction = "正超额" if excess_med > 0 else "负超额"
                print(f"  Q1-G{g} T+{hw}: n={n}, 超额中位数={excess_med:+.2f}%, "
                      f"Anchor中位数={anchor_med:+.2f}%, 超额胜率={excess_pos:.0f}% [{direction}]")

    print("\n" + "=" * 60)
    print("Q×G 网格画像构建完成")
    print("=" * 60)


if __name__ == "__main__":
    from pandas import notna as pd_notna  # noqa: E402 — for summary section
    import pandas as pd  # noqa: E402
    main()
