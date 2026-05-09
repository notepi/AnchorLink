#!/usr/bin/env python3
"""
历史分析 CLI 入口

用法：
    uv run python scripts/build_history_analysis.py
    uv run python scripts/build_history_analysis.py --divergence-threshold 6.0 --signal-min-count 3
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
OUTPUT_ROOT = PROJECT_ROOT / "data" / "output"
MARKET_DATA_PATH = PROJECT_ROOT / "data" / "price"


def main():
    parser = argparse.ArgumentParser(description="构建历史时间序列分析")
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--market-data-path", type=Path, default=MARKET_DATA_PATH)
    parser.add_argument("--divergence-threshold", type=float, default=8.0)
    parser.add_argument("--signal-min-count", type=int, default=5)
    parser.add_argument("--days", type=int, default=60, help="行情数据回溯天数（默认60）")
    args = parser.parse_args()

    from src.history_analysis.orchestrator import build_history_analysis

    print("[INFO] 开始历史分析...")
    results = build_history_analysis(
        output_root=args.output_root,
        market_data_path=args.market_data_path,
        divergence_threshold=args.divergence_threshold,
        signal_min_count=args.signal_min_count,
    )

    output_root = args.output_root
    for name, count in results.items():
        print(f"[OK] {name}: {count} 行")

    print("[OK] 历史分析完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
