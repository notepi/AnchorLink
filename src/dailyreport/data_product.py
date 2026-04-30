"""
日报数据产品模块
封装对 price 模块的调用，实现 dailyreport 与 price 的解耦

设计原则：
  - reporter.py 只导入此模块，不直接导入 src.price.*
  - 所有价格相关的数据获取都通过此接口
"""

from typing import Any, Dict, Optional

import pandas as pd

from src.price.data_product import load_price_data_product
from src.price.rolling_analyzer import load_rolling_metrics
from src.price.score_layer import calc_score
from src.price.rebound_watch_layer import calc_rebound_watch, format_rebound_section


def get_price_context() -> Dict[str, Any]:
    """
    获取报告所需的行情上下文

    Returns:
        {
            "price_product": dict,  # 价格数据产品
            "rolling": dict | None,  # 连续观察层数据
        }
    """
    price_product = load_price_data_product()

    rolling = None
    try:
        rolling = load_rolling_metrics()
    except Exception:
        pass  # 连续观察层不可用时静默降级

    return {
        "price_product": price_product,
        "rolling": rolling,
    }


def get_score_snapshot(
    overall_signal_label: str,
    price_strength_label: str,
    volume_strength_label: str,
    momentum_label: str,
    capital_flow_trend_label: str,
    capital_flow_label: Optional[str],
    rolling: Optional[Dict[str, Any]],
    relative_strength: Optional[float],
    return_rank_in_sector: Optional[int],
) -> str:
    """
    获取评分层快照（Markdown 格式）

    Returns:
        评分层快照 Markdown 字符串，失败时返回空字符串
    """
    try:
        score_row = pd.Series({
            "overall_signal_label": overall_signal_label,
            "price_strength_label": price_strength_label,
            "volume_strength_label": volume_strength_label,
            "momentum_label": momentum_label,
            "capital_flow_trend_label": capital_flow_trend_label or "",
        })
        score_result = calc_score(score_row)

        drag_items = []
        support_items = []

        if price_strength_label == "弱":
            drag_items.append("价格表现偏弱")
        if capital_flow_label == "主力偏空":
            drag_items.append("主力资金偏空")
        if rolling and "流出" in str(rolling.get("capital_flow_trend_label", "")):
            drag_items.append("近5日资金持续流出")
        if volume_strength_label == "弱":
            drag_items.append("量能偏弱")

        if momentum_label in {"价强量稳", "量价齐升"}:
            support_items.append("近5日结构尚未明显破坏")
        if relative_strength is not None and relative_strength > -0.005:
            support_items.append("相对板块并未明显失真")
        if return_rank_in_sector is not None and return_rank_in_sector <= 2:
            support_items.append("板块内位置仍处前列")

        drag_text = "；".join(drag_items[:2]) if drag_items else "暂无明显拖累项"
        support_text = "；".join(support_items[:2]) if support_items else "暂未见明显缓冲项"

        return (
            f"\n\n### 评分层快照\n"
            f"- **整体判断**：{score_result['signal_rating']}\n"
            f"- **主要拖累项**：{drag_text}\n"
            f"- **主要缓冲项**：{support_text}\n"
        )
    except Exception:
        return ""


def get_rebound_section(
    overall_signal_label: str,
    price_strength_label: str,
    volume_strength_label: str,
    capital_flow_trend_label: str,
    relative_strength: Optional[float],
    anchor_return: Optional[float],
    momentum_label: str,
    price_trend_label: str,
) -> str:
    """
    获取反抽观察部分（Markdown 格式）

    Returns:
        反抽观察 Markdown 字符串
    """
    try:
        rebound_data = {
            "signal_score": 0,
            "signal_rating": "",
            "overall_signal_label": overall_signal_label,
            "price_strength_label": price_strength_label,
            "volume_strength_label": volume_strength_label,
            "capital_flow_trend_label": capital_flow_trend_label or "",
            "relative_strength": relative_strength,
            "anchor_return": anchor_return,
            "momentum_label": momentum_label,
            "price_trend_label": price_trend_label,
        }

        score_result = calc_score(pd.Series(rebound_data))
        rebound_data.update(score_result)

        rebound_result = calc_rebound_watch(rebound_data)

        if rebound_result["rebound_watch_flag"]:
            return f"\n\n{format_rebound_section(rebound_result)}\n"
        else:
            return "\n\n当前未触发反抽观察。\n"
    except Exception:
        return "\n\n当前未触发反抽观察。\n"