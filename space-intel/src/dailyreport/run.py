"""
日报入口
生成每日复盘报告

用法：
    python -m src.dailyreport.run
"""

import sys

from src.dailyreport.reporter import generate_daily_report


def main():
    """生成日报"""
    print("=" * 60)
    print("日报生成 - 开始运行")
    print("=" * 60)

    try:
        report_path = generate_daily_report()
        print(f"\n[OK] 报告已生成: {report_path}")
    except Exception as e:
        print(f"[ERROR] 报告生成失败: {e}")
        return 1

    print("\n" + "=" * 60)
    print("日报生成 - 完成")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())