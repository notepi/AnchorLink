"""
标准指数超额画像分析 — 入口脚本
================================
从虚拟指数产物读取数据，构建信号→分档→Forward Label→画像统计的完整流水线。

输入（只读）：
  - data/price/analytics/index_products/constant_universe_2026-05-06/

输出：
  - data/price/analytics/index_excess_profiles/constant_universe_2026-05-06/
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.index_products.excess_profile import build_excess_profile

INPUT_DIR = ROOT / "data/price/analytics/index_products/constant_universe_2026-05-06"
OUTPUT_DIR = ROOT / "data/price/analytics/index_excess_profiles/constant_universe_2026-05-06"


def main():
    print("=" * 60)
    print("标准指数超额画像分析")
    print(f"  输入: {INPUT_DIR}")
    print(f"  输出: {OUTPUT_DIR}")
    print("=" * 60)

    summary = build_excess_profile(INPUT_DIR, OUTPUT_DIR)

    manifest = summary.get("manifest", {})
    print("\n" + "=" * 60)
    print("验收摘要")
    print("=" * 60)
    print(f"  pool_config_version: {manifest.get('pool_config_version')}")
    print(f"  source_data_as_of: {manifest.get('source_data_as_of')}")
    print(f"  anchor_suspended_days: {summary.get('anchor_suspended_days', 'N/A')}")

    counts = manifest.get("output_record_counts", {})
    print(f"\n  输出文件行数:")
    for name, count in counts.items():
        print(f"    {name}: {count}")

    print("\n[OK] 构建完成")


if __name__ == "__main__":
    main()
