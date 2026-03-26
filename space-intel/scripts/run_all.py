#!/usr/bin/env python3
"""
统一入口脚本
运行完整的数据处理和报告生成流程

用法：
    python scripts/run_all.py
    python scripts/run_all.py --skip-news  # 跳过新闻数据线
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def run_module(module_path: str, description: str) -> bool:
    """运行指定模块"""
    print(f"\n{'=' * 60}")
    print(f"运行: {description}")
    print(f"{'=' * 60}")

    result = subprocess.run(
        [sys.executable, "-m", module_path],
        cwd=PROJECT_ROOT,
    )
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="运行完整的数据处理流程")
    parser.add_argument("--skip-news", action="store_true", help="跳过新闻数据线")
    parser.add_argument("--only-report", action="store_true", help="只生成日报")
    args = parser.parse_args()

    print("=" * 60)
    print("商业航天情报系统 - 统一入口")
    print("=" * 60)

    success = True

    if args.only_report:
        # 只生成日报
        success = run_module("src.dailyreport.run", "日报生成")
    else:
        # 完整流程
        # 1. 行情数据线
        if not run_module("src.price.run", "行情数据线"):
            print("[ERROR] 行情数据线运行失败")
            success = False

        # 2. 新闻数据线（可选）
        if not args.skip_news:
            if not run_module("src.news.run", "新闻数据线"):
                print("[WARN] 新闻数据线运行失败（不影响日报生成）")

        # 3. 日报生成
        if success:
            if not run_module("src.dailyreport.run", "日报生成"):
                print("[ERROR] 日报生成失败")
                success = False

    print("\n" + "=" * 60)
    if success:
        print("所有任务完成 ✓")
    else:
        print("部分任务失败 ✗")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())