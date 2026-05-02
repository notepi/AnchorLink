"""
日报模块 - MVP 流程入口

职责：
  - 整合六层模块调用
  - 生成三类输出文件（JSON/CSV/Markdown）

Usage:
    from src.dailyreport import run_daily_analysis
    result = run_daily_analysis("20260502")

    # 或 CLI:
    uv run python -m src.dailyreport.run --date 20260502
"""

from src.dailyreport.run import run_daily_analysis, main

__all__ = ["run_daily_analysis", "main"]