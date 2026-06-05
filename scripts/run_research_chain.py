#!/usr/bin/env python3
"""
标准超额研究链（B 链）编排器
=============================
检测 B 链输出是否滞后于行情数据，按顺序重跑，验证完成。

用法：
    python scripts/run_research_chain.py              # 检测+执行+验证
    python scripts/run_research_chain.py --check-only # 只检测是否滞后
    python scripts/run_research_chain.py --force      # 跳过检测，强制全量重跑

B 链步骤（严格顺序）：
    1. build_custom_indexes.py                  → 类ETF指数构建
    2. build_standard_index_excess_profile.py   → 标准超额画像
    3. build_standard_index_excess_decomposition.py → 超额分解
    4. build_standard_index_qg_profile.py       → Q×G 网格画像
    5. build_benchmark_divergence_analysis.py    → 基准分歧分析
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "pools.yaml"
NORMALIZED_PATH = PROJECT_ROOT / "data" / "price" / "normalized" / "market_data_normalized.parquet"
ANALYTICS_BASE = PROJECT_ROOT / "data" / "price" / "analytics"

# B 链步骤定义：(脚本文件名, 描述, 额外CLI参数)
B_CHAIN: list[tuple[str, str, list[str]]] = [
    ("build_custom_indexes.py", "类ETF指数构建", ["--allow-stale-anchor"]),
    ("build_standard_index_excess_profile.py", "标准超额画像", []),
    ("build_standard_index_excess_decomposition.py", "超额分解", []),
    ("build_standard_index_qg_profile.py", "Q×G 网格画像", []),
    ("build_benchmark_divergence_analysis.py", "基准分歧分析", []),
]

# 各步骤的输出目录（相对于 ANALYTICS_BASE）和用于检测日期的 CSV 文件
# (输出子目录后缀, 日期检测 CSV 文件名, 日期列名)
STEP_OUTPUTS: list[tuple[str, str, str]] = [
    ("index_products", "anchor_index_excess.csv", "date"),
    ("index_excess_profiles", "signal_daily.csv", "date"),
    ("index_excess_profiles", "excess_decomposition_daily.csv", "date"),
    ("index_excess_qg_profiles", "qg_signal_daily.csv", "date"),
    ("index_benchmark_divergence", "benchmark_divergence_daily.csv", "date"),
]


def _read_pool_config_version() -> str:
    """从 config/pools.yaml 读取 version 字段"""
    import yaml

    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    version = cfg.get("version")
    if not version:
        raise ValueError("config/pools.yaml 缺少 version 字段")
    return str(version)


def _get_normalized_latest() -> str:
    """读取标准化行情数据的最新交易日期，返回 YYYYMMDD 字符串"""
    import pandas as pd

    df = pd.read_parquet(NORMALIZED_PATH, columns=["trade_date"])
    latest = df["trade_date"].max()
    # 处理 pandas Timestamp 或字符串
    if hasattr(latest, "strftime"):
        return latest.strftime("%Y%m%d")
    return str(latest).replace("-", "")[:8]


def _get_step_latest(step_idx: int, version: str) -> str | None:
    """
    读取 B 链第 step_idx 步输出的最新日期。
    优先读 build_manifest.json 的 source_data_as_of，
    回退读 CSV 尾行日期。
    返回 YYYYMMDD 字符串，不存在返回 None。
    """
    subdir, csv_name, date_col = STEP_OUTPUTS[step_idx]
    out_dir = ANALYTICS_BASE / subdir / f"constant_universe_{version}"

    # 优先读 manifest
    manifest_path = out_dir / "build_manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            as_of = manifest.get("source_data_as_of")
            if as_of:
                # 可能是 "20260602" 或 "2026-06-02"
                return str(as_of).replace("-", "")[:8]
        except (json.JSONDecodeError, OSError):
            pass

    # 回退读 CSV 尾行
    csv_path = out_dir / csv_name
    if csv_path.exists():
        try:
            import pandas as pd

            df = pd.read_csv(csv_path, usecols=[date_col], nrows=1)
            if date_col not in df.columns:
                return None
            full = pd.read_csv(csv_path, usecols=[date_col])
            last = str(full[date_col].iloc[-1])
            return last.replace("-", "")[:8]
        except Exception:
            pass

    return None


def check_staleness(version: str, norm_latest: str) -> list[tuple[int, str, str | None, bool]]:
    """
    检测 B 链各步骤是否滞后。
    返回 [(step_idx, 描述, step_latest, is_stale), ...]
    """
    results = []
    for i, (_, desc, _) in enumerate(B_CHAIN):
        step_latest = _get_step_latest(i, version)
        is_stale = step_latest is None or step_latest < norm_latest
        results.append((i, desc, step_latest, is_stale))
    return results


def run_b_chain(force: bool = False) -> bool:
    """执行 B 链。返回 True 表示全部成功。"""
    version = _read_pool_config_version()
    norm_latest = _get_normalized_latest()

    print(f"[INFO] 行情最新日期: {norm_latest}")
    print(f"[INFO] pools.yaml 版本: {version}")

    # 检测滞后
    staleness = check_staleness(version, norm_latest)
    any_stale = any(s[3] for s in staleness)

    print("\n--- B 链状态检测 ---")
    for idx, desc, step_latest, is_stale in staleness:
        status = "⬆ 需更新" if is_stale else "✓ 最新"
        latest_str = step_latest or "不存在"
        print(f"  步骤 {idx + 1} {desc}: {latest_str} {status}")

    if not any_stale and not force:
        print("\n[OK] B 链全部最新，无需重跑")
        return True

    if force:
        print("\n[INFO] --force 模式，跳过检测，强制全量重跑")
    else:
        print("\n[INFO] B 链滞后，开始重跑...")

    # 按顺序执行
    success = True
    for idx, (script_name, desc, extra_args) in enumerate(B_CHAIN):
        print(f"\n{'=' * 60}")
        print(f"[INFO] 步骤 {idx + 1}/{len(B_CHAIN)}: {desc}")
        print(f"{'=' * 60}")

        script_path = PROJECT_ROOT / "scripts" / script_name
        cmd = [sys.executable, str(script_path)] + extra_args

        result = subprocess.run(cmd, cwd=PROJECT_ROOT)
        if result.returncode != 0:
            print(f"[ERROR] 步骤 {idx + 1} {desc} 失败 (exit {result.returncode})")
            success = False
            break
        else:
            print(f"[OK] 步骤 {idx + 1} {desc} 完成")

    if not success:
        return False

    # 验证
    print(f"\n{'=' * 60}")
    print("[INFO] 验证 B 链输出...")
    print(f"{'=' * 60}")

    staleness_after = check_staleness(version, norm_latest)
    all_ok = True
    for idx, desc, step_latest, is_stale in staleness_after:
        if is_stale:
            print(f"  [ERROR] 步骤 {idx + 1} {desc}: 仍滞后 (最新={step_latest}, 期望={norm_latest})")
            all_ok = False
        else:
            print(f"  [OK] 步骤 {idx + 1} {desc}: {step_latest}")

    if all_ok:
        print(f"\n[OK] B 链全部更新至 {norm_latest}")
    else:
        print(f"\n[ERROR] B 链验证失败，部分步骤仍滞后")

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="标准超额研究链（B 链）编排器")
    parser.add_argument("--check-only", action="store_true", help="只检测是否滞后，不执行")
    parser.add_argument("--force", action="store_true", help="跳过检测，强制全量重跑")
    args = parser.parse_args()

    if args.check_only and args.force:
        print("[ERROR] --check-only 和 --force 不可同时使用")
        return 1

    try:
        version = _read_pool_config_version()
        norm_latest = _get_normalized_latest()
    except Exception as e:
        print(f"[ERROR] 无法读取行情数据或配置: {e}")
        return 1

    if args.check_only:
        staleness = check_staleness(version, norm_latest)
        any_stale = any(s[3] for s in staleness)

        print(f"行情最新日期: {norm_latest}")
        print(f"pools.yaml 版本: {version}")
        print()
        for idx, desc, step_latest, is_stale in staleness:
            status = "滞后" if is_stale else "最新"
            latest_str = step_latest or "不存在"
            print(f"  步骤 {idx + 1} {desc}: {latest_str} [{status}]")

        return 1 if any_stale else 0

    success = run_b_chain(force=args.force)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
