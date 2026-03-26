"""
新闻数据产品模块 v1.0

职责：
  - 统一新闻链路的数据产品入口
  - 读取 daily_events.json
  - 为 reporter 提供稳定加载接口
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.shared.storage import Storage

# 存储层
STORAGE = Storage("news")

DEFAULT_EVENTS_PATH = STORAGE.get_processed_path("daily_events.json")


class NewsDataProduct:
    """新闻数据产品接口"""

    @staticmethod
    def get_latest_trade_date() -> Optional[str]:
        """获取最新交易日 YYYYMMDD"""
        events = NewsDataProduct.get_daily_events()
        if events and "trade_date" in events:
            return events["trade_date"]
        return None

    @staticmethod
    def get_daily_events(trade_date: str = None) -> Dict[str, Any]:
        """
        获取事件数据产品

        Args:
            trade_date: 交易日期 YYYYMMDD，默认取最新

        Returns:
            事件数据字典
        """
        if trade_date:
            # 从归档读取
            archive_path = STORAGE.get_archive_path(f"{trade_date}.json")
            if archive_path.exists():
                with open(archive_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}

        # 读取最新数据
        if DEFAULT_EVENTS_PATH.exists():
            with open(DEFAULT_EVENTS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    @staticmethod
    def get_events_by_relevance(trade_date: str = None, level: str = "strong") -> List[Dict]:
        """
        按相关度筛选事件

        Args:
            trade_date: 交易日期
            level: 相关度级别 strong/weak/noise

        Returns:
            事件列表
        """
        events = NewsDataProduct.get_daily_events(trade_date)
        items = events.get("events_list", [])
        return [e for e in items if e.get("relevance") == level]

    @staticmethod
    def get_catalyst_news(trade_date: str = None) -> List[Dict]:
        """
        获取催化新闻（relevance=strong）

        Args:
            trade_date: 交易日期

        Returns:
            催化新闻列表
        """
        return NewsDataProduct.get_events_by_relevance(trade_date, "strong")


def load_news_data_product(path: str = None) -> Dict[str, Any]:
    """加载新闻数据产品"""
    product_path = Path(path) if path else DEFAULT_EVENTS_PATH
    if not product_path.exists():
        return {}
    with open(product_path, "r", encoding="utf-8") as f:
        return json.load(f)