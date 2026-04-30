"""
新闻数据线 v2.0

重构要点：
  1. 移除 Playwright 依赖
  2. 使用 event_layer 的独立数据源（Akshare/巨潮）
  3. AI 筛选作为可选增强

用法：
    uv run python -m src.news.run
"""

import sys
from datetime import datetime

from src.news.event_layer import collect_events
from src.news.ai_filter import filter_news_with_ai, check_ai_filter_available
from src.shared.config import load_config, get_catalyst_rules


def main():
    """运行新闻数据线完整流程"""
    print("=" * 60)
    print("新闻数据线 v2.0 - 开始运行")
    print("=" * 60)

    # Step 1: 配置加载
    print("\n[Step 1/4] 加载配置...")
    try:
        config = load_config()  # 默认加载 stocks.yaml
        rules = get_catalyst_rules()
        anchor = config.get("anchor", {})
        anchor_code = anchor.get("code", "688333.SH")
        anchor_name = anchor.get("name", "铂力特")
        trade_date = datetime.now().strftime("%Y%m%d")
        print(f"  交易日期: {trade_date}")
        print(f"  锚定标的: {anchor_name} ({anchor_code})")
    except Exception as e:
        print(f"[ERROR] 配置加载失败: {e}")
        return 1

    # Step 2: 事件采集（核心，无 Playwright 依赖）
    print("\n[Step 2/4] 事件采集...")
    try:
        result = collect_events(trade_date, anchor_code, anchor_name)
        events_list = result.get("events_list", [])
        print(f"  整体状态: {result.get('overall_status')}")
        print(f"  事件数量: {len(events_list)}")
        print(f"  信号标签: {result.get('event_signal_label')}")
    except Exception as e:
        print(f"[ERROR] 事件采集失败: {e}")
        return 1

    # Step 3: AI 筛选（可选）
    print("\n[Step 3/4] AI 筛选...")
    if check_ai_filter_available():
        try:
            if events_list:
                # 转换 events_list 为 ai_filter 需要的格式
                news_items = [
                    {
                        "title": e.get("title", ""),
                        "summary": "",
                        "source_name": e.get("source_name", ""),
                    }
                    for e in events_list
                ]
                filtered = filter_news_with_ai(news_items, rules)
                print(f"  AI 筛选后保留: {len(filtered)}/{len(events_list)} 条")
            else:
                print("  无事件需要筛选")
        except Exception as e:
            print(f"[WARN] AI 筛选失败: {e}")
    else:
        print("  跳过 (未配置 DASHSCOPE_API_KEY)")

    # Step 4: 完成
    print("\n[Step 4/4] 数据产品输出")
    print(f"  daily_events.json: 已生成")
    print(f"  事件摘要: {result.get('event_summary', 'N/A')}")

    print("\n" + "=" * 60)
    print("新闻数据线 - 运行完成")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())