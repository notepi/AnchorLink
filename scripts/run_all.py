#!/usr/bin/env python3
"""
统一入口脚本
运行完整的数据处理和报告生成流程

用法：
    python scripts/run_all.py
    python scripts/run_all.py --days 365    # 扩展历史天数
    python scripts/run_all.py --only-report # 只生成日报
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def run_module(module_path: str, description: str, extra_args: list[str] = None) -> bool:
    """运行指定模块"""
    print(f"\n{'=' * 60}")
    print(f"运行: {description}")
    print(f"{'=' * 60}")

    cmd = [sys.executable, "-m", module_path]
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="运行完整的数据处理流程")
    parser.add_argument("--days", type=int, default=60, help="行情数据回溯天数（默认60）")
    parser.add_argument("--only-report", action="store_true", help="只生成日报")
    args = parser.parse_args()

    print("=" * 60)
    print("AnchorLink - 统一入口")
    print("=" * 60)

    success = True

    if args.only_report:
        success = run_module("src.dailyreport.run", "日报生成")
    else:
        # 1. 行情数据线（透传 --days）
        price_args = ["--days", str(args.days)]
        if not run_module("src.price.run", f"行情数据线 (回溯 {args.days} 天)", price_args):
            print("[ERROR] 行情数据线运行失败")
            success = False

        # 2. 日报生成
        if success:
            if not run_module("src.dailyreport.run", "日报生成"):
                print("[ERROR] 日报生成失败")
                success = False

        # 3. 历史分析（全量重建）
        if success:
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "build_history_analysis.py")],
                cwd=PROJECT_ROOT,
            )
            if result.returncode != 0:
                print("[ERROR] 历史分析失败")
                success = False

        # 3.5. V2 评分计算（依赖 history CSVs，需用 -m 运行以支持 src 导入）
        if success:
            if not run_module("scripts.build_v2_scoring", "V2 评分计算"):
                print("[ERROR] V2 评分计算失败")
                success = False

        # 3.6. 每日分析报告生成
        if success:
            if not run_module("scripts.build_daily_report", "每日分析报告生成"):
                print("[ERROR] 报告生成失败")
                success = False

        # 3.7. 二阶信号分析（依赖 history CSVs）
        if success:
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "analyze_2nd_order_signals.py")],
                cwd=PROJECT_ROOT,
            )
            if result.returncode != 0:
                print("[ERROR] 二阶信号分析失败")
                success = False

        # 3.8. 复合信号回测（依赖 history CSVs）
        if success:
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "composite_signal_backtest.py")],
                cwd=PROJECT_ROOT,
            )
            if result.returncode != 0:
                print("[ERROR] 复合信号回测失败")
                success = False

        # 3.9. 深度量化分析（依赖 history CSVs + 二阶信号）
        if success:
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "deep_quant_analysis.py")],
                cwd=PROJECT_ROOT,
            )
            if result.returncode != 0:
                print("[ERROR] 深度量化分析失败")
                success = False

        # 4. 前端数据构建
        if success:
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "build_dashboard_view.py")],
                cwd=PROJECT_ROOT,
            )
            if result.returncode != 0:
                print("[ERROR] 前端数据构建失败")
                success = False

        # 5. 参数漂移检测（不阻断管道）
        if success:
            if not run_module("scripts.param_drift_check", "参数漂移检测"):
                print("[WARN] 漂移检测失败（不影响主流程）")

        # 6. 参数自动校准（仅漂移时运行）
        if success:
            drift_report_path = PROJECT_ROOT / "data" / "output" / "param_drift_report.json"
            try:
                import json as _json
                with open(drift_report_path) as _f:
                    _drift = _json.load(_f)
                if _drift.get("driftDetected"):
                    if not run_module("scripts.auto_calibrate_v2", "参数自动校准（漂移已检测）"):
                        print("[WARN] 校准失败（不影响主流程）")
                else:
                    print("[INFO] 无漂移，跳过校准")
            except Exception:
                print("[WARN] 无法读取漂移报告，跳过校准")

    print("\n" + "=" * 60)
    if success:
        print("所有任务完成")
    else:
        print("部分任务失败")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
