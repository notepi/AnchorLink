#!/usr/bin/env python3
"""
统一入口脚本
运行完整的数据处理和报告生成流程

用法：
    uv run python scripts/run_all.py              # 每日更新（默认）
    uv run python scripts/run_all.py --days 365   # 新增股票或补历史
    uv run python scripts/run_all.py --only-report  # 只生成日报
    uv run python scripts/run_all.py --skip-research  # 跳过B链
    uv run python scripts/run_all.py --force-research  # 强制重跑B链（规则变了但日期没变时用）
    uv run python scripts/run_all.py --allow-noncritical-fail  # 漂移/校准失败不阻断

--days 说明：
    这是最低覆盖窗口，不是每天重拉N天。fetcher 会增量补缺：
    已有数据到 max_date → 只拉 max_date 之后的新数据。
    默认 60 天够日常增量，新增股票或补历史用 365。
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
    parser.add_argument("--days", type=int, default=60, help="行情数据最低覆盖天数（默认60，增量补缺）")
    parser.add_argument("--only-report", action="store_true", help="只生成日报")
    parser.add_argument("--skip-research", action="store_true", help="跳过标准超额研究链（B链）")
    parser.add_argument("--force-research", action="store_true", help="强制重跑B链（即使日期没落后）")
    parser.add_argument("--allow-noncritical-fail", action="store_true", help="漂移检测/校准失败时不阻断管道")
    args = parser.parse_args()

    if args.skip_research and args.force_research:
        print("[ERROR] --skip-research 和 --force-research 不可同时使用")
        return 1

    print("=" * 60)
    print("AnchorLink - 统一入口")
    print("=" * 60)

    success = True

    if args.only_report:
        success = run_module("src.dailyreport.run", "日报生成")
    else:
        # ===== A 链：日报 / V2 主链 =====

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

        # 3.10. 旧超额分级回测（legacy median displacement）
        if success:
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "excess_grade_backtest.py")],
                cwd=PROJECT_ROOT,
            )
            if result.returncode != 0:
                print("[ERROR] 旧超额分级回测失败")
                success = False

        # ===== B 链：标准超额研究链（依赖 A 链行情数据）=====
        # 必须在 dashboard 之前跑，因为 dashboard 可能依赖 B 链输出
        # A 链失败时禁止跑 B 链：数据无效就不应写下游产物
        if not args.skip_research:
            if success:
                research_cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "run_research_chain.py")]
                if args.force_research:
                    research_cmd.append("--force")
                result = subprocess.run(research_cmd, cwd=PROJECT_ROOT)
                if result.returncode != 0:
                    print("[ERROR] 标准超额研究链失败")
                    success = False
            else:
                print("[INFO] A 链失败，跳过标准超额研究链")
        else:
            print("[INFO] 跳过标准超额研究链（--skip-research）")

        # 4. 前端数据构建（依赖 A 链 + B 链输出）
        if success:
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "build_dashboard_view.py")],
                cwd=PROJECT_ROOT,
            )
            if result.returncode != 0:
                print("[ERROR] 前端数据构建失败")
                success = False

        # 5. 参数漂移检测
        if success:
            if not run_module("scripts.param_drift_check", "参数漂移检测"):
                if args.allow_noncritical_fail:
                    print("[WARN] 漂移检测失败（--allow-noncritical-fail，不阻断）")
                else:
                    print("[ERROR] 漂移检测失败")
                    success = False

        # 6. 参数自动校准（仅漂移时运行）
        if success:
            drift_report_path = PROJECT_ROOT / "data" / "output" / "param_drift_report.json"
            try:
                import json as _json
                with open(drift_report_path) as _f:
                    _drift = _json.load(_f)
                if _drift.get("driftDetected"):
                    if not run_module("scripts.auto_calibrate_v2", "参数自动校准（漂移已检测）"):
                        if args.allow_noncritical_fail:
                            print("[WARN] 校准失败（--allow-noncritical-fail，不阻断）")
                        else:
                            print("[ERROR] 校准失败")
                            success = False
                else:
                    print("[INFO] 无漂移，跳过校准")
            except Exception as e:
                if args.allow_noncritical_fail:
                    print(f"[WARN] 无法读取漂移报告: {e}（--allow-noncritical-fail，不阻断）")
                else:
                    print(f"[ERROR] 无法读取漂移报告: {e}")
                    success = False

    print("\n" + "=" * 60)
    if success:
        print("所有任务完成")
    else:
        print("部分任务失败")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
