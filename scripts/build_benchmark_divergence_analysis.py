#!/usr/bin/env python3
"""
构建 4 ETF 基准分歧分析

用法：
    python scripts/build_benchmark_divergence_analysis.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.index_products.benchmark_divergence import (
    INDEX_IDS,
    SIGNAL_WINDOWS,
    HOLDING_WINDOWS,
    load_anchor_excess,
    load_signal_daily,
    load_forward_labels,
    build_divergence_daily,
    pivot_forward_labels,
    build_divergence_forward,
    compute_divergence_profile,
    build_divergence_cases,
    compute_divergence_summary,
    build_manifest,
    compute_file_checksum,
)

PRODUCTS_DIR = PROJECT_ROOT / "data" / "price" / "analytics" / "index_products" / "constant_universe_2026-05-06"
PROFILES_DIR = PROJECT_ROOT / "data" / "price" / "analytics" / "index_excess_profiles" / "constant_universe_2026-05-06"
OUTPUT_DIR = PROJECT_ROOT / "data" / "price" / "analytics" / "index_benchmark_divergence" / "constant_universe_2026-05-06"


def main() -> None:
    print("=" * 60)
    print("4 ETF 基准分歧分析")
    print("=" * 60)

    # 验证输入
    if not PRODUCTS_DIR.exists():
        raise FileNotFoundError(f"index_products 目录不存在: {PRODUCTS_DIR}")
    if not PROFILES_DIR.exists():
        raise FileNotFoundError(f"index_excess_profiles 目录不存在: {PROFILES_DIR}")

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] 输出目录: {OUTPUT_DIR}")

    # 记录旧文件 checksum
    old_checksums: dict[str, str] = {}
    for old_dir in [
        PROJECT_ROOT / "data" / "price" / "analytics" / "index_products",
        PROJECT_ROOT / "data" / "price" / "analytics" / "index_excess_profiles",
        PROJECT_ROOT / "data" / "price" / "analytics" / "index_excess_qg_profiles",
    ]:
        if old_dir.exists():
            for f in old_dir.rglob("*.csv"):
                sha = hashlib.sha256()
                with open(f, "rb") as fh:
                    for chunk in iter(lambda: fh.read(4096), b""):
                        sha.update(chunk)
                old_checksums[str(f)] = sha.hexdigest()

    # ── Step 1: 加载数据 ──
    print("\n[Step 1/7] 加载输入数据...")
    excess_df = load_anchor_excess(PRODUCTS_DIR)
    signal_df = load_signal_daily(PROFILES_DIR)
    forward_df = load_forward_labels(PROFILES_DIR)

    # ── Step 2: 构建逐日分歧明细 ──
    print("\n[Step 2/7] 构建逐日分歧明细...")
    daily_df = build_divergence_daily(excess_df, signal_df)

    usable_count = (daily_df["quality_scope"] != "unusable").sum()
    strict_count = (daily_df["quality_scope"] == "strict_ok_only").sum()
    print(f"[INFO] daily: {len(daily_df)} 行, usable: {usable_count}, strict_ok_only: {strict_count}")

    # 统计分歧率
    usable = daily_df[daily_df["quality_scope"] != "unusable"]
    for sw in SIGNAL_WINDOWS:
        sw_df = usable[usable["signal_window"] == sw]
        total = len(sw_df)
        aligned = len(sw_df[sw_df["divergence_type"].isin(["all_aligned_positive", "all_aligned_negative"])])
        diverged = len(sw_df[sw_df["main_aux_divergence"] == True])
        print(f"  {sw}D: 总计 {total} 天, 一致 {aligned} ({aligned/total*100:.0f}%), "
              f"主辅分歧 {diverged} ({diverged/total*100:.0f}%)")

    daily_path = OUTPUT_DIR / "benchmark_divergence_daily.csv"
    daily_df.to_csv(daily_path, index=False)
    print(f"[OK] benchmark_divergence_daily.csv 写入: {len(daily_df)} 行")

    # ── Step 3: 透视 forward labels ──
    print("\n[Step 3/7] 透视 forward labels...")
    forward_wide = pivot_forward_labels(forward_df)
    print(f"[INFO] forward_wide: {len(forward_wide)} 行")

    # ── Step 4: 构建 forward joined ──
    print("\n[Step 4/7] 构建 forward joined...")
    forward_joined = build_divergence_forward(daily_df, forward_wide, signal_df)
    print(f"[INFO] forward_joined: {len(forward_joined)} 行")
    if len(forward_joined) > 0:
        usable_fwd = (forward_joined["quality_scope"] == "usable").sum()
        strict_fwd = (forward_joined["quality_scope"] == "strict_ok_only").sum()
        print(f"  usable: {usable_fwd}, strict_ok_only: {strict_fwd}")

    forward_path = OUTPUT_DIR / "benchmark_divergence_forward.csv"
    forward_joined.to_csv(forward_path, index=False)
    print(f"[OK] benchmark_divergence_forward.csv 写入: {len(forward_joined)} 行")

    # ── Step 5: 计算 profile ──
    print("\n[Step 5/7] 计算分歧画像...")
    profile_df = compute_divergence_profile(forward_joined)
    print(f"[INFO] profile: {len(profile_df)} 行")

    profile_path = OUTPUT_DIR / "benchmark_divergence_profile.csv"
    profile_df.to_csv(profile_path, index=False)
    print(f"[OK] benchmark_divergence_profile.csv 写入: {len(profile_df)} 行")

    # ── Step 6: 分歧 cases + summary ──
    print("\n[Step 6/7] 分歧 cases + summary...")
    cases_df = build_divergence_cases(daily_df, forward_wide)
    print(f"[INFO] cases: {len(cases_df)} 行")

    cases_path = OUTPUT_DIR / "benchmark_divergence_cases.csv"
    cases_df.to_csv(cases_path, index=False)
    print(f"[OK] benchmark_divergence_cases.csv 写入: {len(cases_df)} 行")

    summary = compute_divergence_summary(daily_df, profile_df)
    summary_path = OUTPUT_DIR / "benchmark_divergence_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[OK] benchmark_divergence_summary.json 写入完成")

    # ── Step 7: Build Manifest ──
    print("\n[Step 7/7] 构建 Manifest...")
    output_counts = {
        "benchmark_divergence_daily": len(daily_df),
        "benchmark_divergence_forward": len(forward_joined),
        "benchmark_divergence_profile": len(profile_df),
        "benchmark_divergence_cases": len(cases_df),
    }
    manifest = build_manifest(PRODUCTS_DIR, PROFILES_DIR, OUTPUT_DIR, output_counts)
    manifest_path = OUTPUT_DIR / "build_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[OK] build_manifest.json 写入完成")

    # ── 验证旧文件 ──
    print("\n[验证] 检查旧数据未被修改...")
    all_ok = True
    for fpath, old_sha in old_checksums.items():
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

    for sw in SIGNAL_WINDOWS:
        sw_key = f"signal_window_{sw}"
        if sw_key in summary:
            s = summary[sw_key]
            print(f"\n--- {sw}D ---")
            print(f"  一致率: {s['aligned_rate']}% ({s['aligned_count']}/{s['total_days']})")
            print(f"  主辅分歧率: {s['divergence_rate']}% ({s['diverged_count']}/{s['total_days']})")
            print(f"  main_negative_aux_positive: {s['main_negative_aux_positive_count']} 天")
            print(f"  main_positive_aux_negative: {s['main_positive_aux_negative_count']} 天")

    # 分歧关键类型未来表现
    print("\n--- 分歧关键类型 (5D T+5) ---")
    for div_type in ["main_negative_aux_positive", "main_positive_aux_negative"]:
        key = f"{div_type}_future"
        if key in summary:
            s = summary[key]
            print(f"  {div_type}: n={s['sample_count']}, "
                  f"Anchor中位={s['future_anchor_return_median']:.2f}%, "
                  f"主基准超额中位={s['future_excess_main_median']:.2f}%, "
                  f"辅助超额中位={s['future_excess_aux_median_median']:.2f}%")

    print("\n" + "=" * 60)
    print("4 ETF 基准分歧分析完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
