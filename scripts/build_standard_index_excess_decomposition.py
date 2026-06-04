"""
Q5 极热负超额来源拆解 — 入口脚本
==================================
从已有画像产物读取 signal_daily.csv + forward_labels.csv，
拆解负超额来源桶，输出 decomposition daily + profile。

输入（只读）：
  - data/price/analytics/index_excess_profiles/constant_universe_2026-05-06/

输出（同目录新增）：
  - excess_decomposition_daily.csv
  - excess_decomposition_profile.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.index_products.excess_decomposition import build_excess_decomposition

DATA_DIR = ROOT / "data/price/analytics/index_excess_profiles/constant_universe_2026-05-06"


def main():
    print("=" * 60)
    print("Q5 极热负超额来源拆解")
    print(f"  输入/输出: {DATA_DIR}")
    print("=" * 60)

    summary = build_excess_decomposition(DATA_DIR, DATA_DIR)

    print("\n" + "=" * 60)
    print("验收摘要")
    print("=" * 60)
    print(f"  daily 行数: {summary.get('daily_rows', 'N/A')}")
    print(f"  profile 行数: {summary.get('profile_rows', 'N/A')}")

    print("\n[OK] 构建完成")


if __name__ == "__main__":
    main()
