#!/usr/bin/env python3
"""
批量处理历史数据
遍历所有交易日，生成每日信号和报告

用法：
    uv run python scripts/run_history.py              # 处理所有已有数据
    uv run python scripts/run_history.py --days 90    # 先获取90天数据再处理
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent


def get_available_dates() -> list[str]:
    """获取已有数据的交易日列表"""
    market_path = PROJECT_ROOT / "data/price/raw/market_data.parquet"
    if not market_path.exists():
        return []

    df = pd.read_parquet(market_path)
    dates = sorted(df["trade_date"].astype(str).unique())
    return dates


def run_price_fetch(days: int) -> bool:
    """获取行情数据"""
    import subprocess

    print(f"\n{'=' * 60}")
    print(f"获取 {days} 天行情数据")
    print(f"{'=' * 60}")

    # 修改 fetcher 获取更多天数
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import sys
sys.path.insert(0, '{PROJECT_ROOT}')
from src.price.fetcher import fetch_market_data
fetch_market_data(days={days})
""",
        ],
        cwd=PROJECT_ROOT,
    )
    return result.returncode == 0


def run_daily_analysis(trade_date: str) -> bool:
    """运行单日分析"""
    import subprocess

    print(f"\n{'=' * 60}")
    print(f"处理日期: {trade_date}")
    print(f"{'=' * 60}")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.dailyreport.run",
            "--date",
            trade_date,
        ],
        cwd=PROJECT_ROOT,
    )
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="批量处理历史数据")
    parser.add_argument("--days", type=int, default=None, help="获取最近N天数据（默认不获取）")
    parser.add_argument("--start", type=str, default=None, help="起始日期 YYYYMMDD")
    parser.add_argument("--end", type=str, default=None, help="结束日期 YYYYMMDD")
    args = parser.parse_args()

    print("=" * 60)
    print("AnchorLink - 批量历史数据处理")
    print("=" * 60)

    # Step 1: 获取数据（如果指定）
    if args.days:
        if not run_price_fetch(args.days):
            print("[ERROR] 数据获取失败")
            return 1

    # Step 2: 获取可用日期
    dates = get_available_dates()
    if not dates:
        print("[ERROR] 无可用数据，请先运行 src.price.run")
        return 1

    print(f"\n[INFO] 共有 {len(dates)} 个交易日")
    print(f"[INFO] 日期范围: {dates[0]} ~ {dates[-1]}")

    # Step 3: 过滤日期范围
    if args.start:
        dates = [d for d in dates if d >= args.start]
    if args.end:
        dates = [d for d in dates if d <= args.end]

    if not dates:
        print("[ERROR] 过滤后无可用日期")
        return 1

    print(f"[INFO] 处理 {len(dates)} 个日期: {dates}")

    # Step 4: 批量处理
    success_count = 0
    fail_count = 0

    for trade_date in dates:
        if run_daily_analysis(trade_date):
            success_count += 1
        else:
            fail_count += 1
            print(f"[WARN] {trade_date} 处理失败")

    # Step 5: 统计
    print("\n" + "=" * 60)
    print(f"处理完成: 成功 {success_count}, 失败 {fail_count}")
    print("=" * 60)

    # 输出结果目录
    output_dir = PROJECT_ROOT / "data/output"
    output_dates = sorted([d.name for d in output_dir.iterdir() if d.is_dir()])
    print(f"\n[INFO] 已生成 {len(output_dates)} 个日期的输出")
    print(f"[INFO] 输出目录: {output_dates}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())