"""
置信度计算模块

职责：
  - 根据阈值距离计算置信度
  - 支持不同类型的置信度计算

按 implementation.md Phase 5 设计
"""

from typing import Literal

from src.signal.rules import (
    CONFIDENCE_HIGH_MULTIPLIER,
    CONFIDENCE_MEDIUM_MULTIPLIER,
)

ConfidenceLevel = Literal["high", "medium", "low"]


def calculate_confidence(
    value: float,
    threshold: float,
    is_direction_positive: bool = True,
) -> ConfidenceLevel:
    """
    计算置信度

    Args:
        value: 实际值
        threshold: 判断阈值
        is_direction_positive: 方向是否为正向（> threshold 激活）

    Returns:
        "high" | "medium" | "low"

    Logic:
        - 计算值超过阈值的程度
        - high:   超过阈值 2 倍以上
        - medium: 超过阈值 1-2 倍
        - low:    超过阈值 0-1 倍

    Example:
        value=3.0, threshold=1.0 → margin=2.0 → ratio=2.0 → medium
        value=5.0, threshold=1.0 → margin=4.0 → ratio=4.0 → high
        value=1.2, threshold=1.0 → margin=0.2 → ratio=0.2 → low
    """
    if threshold == 0:
        # 零阈值特殊处理
        if abs(value) > 2.0:
            return "high"
        elif abs(value) > 1.0:
            return "medium"
        else:
            return "low"

    # 计算超过阈值的程度
    if is_direction_positive:
        margin = value - threshold
    else:
        margin = threshold - value

    margin_ratio = margin / abs(threshold)

    if margin_ratio >= CONFIDENCE_HIGH_MULTIPLIER:
        return "high"
    elif margin_ratio >= CONFIDENCE_MEDIUM_MULTIPLIER:
        return "medium"
    else:
        return "low"


def calculate_confidence_from_rank(
    rank: int,
    total_count: int,
    threshold_percentile: float,
) -> ConfidenceLevel:
    """
    基于排名计算置信度

    Args:
        rank: 排名位置（1 = 最高）
        total_count: 总成员数
        threshold_percentile: 阈值分位

    Returns:
        置信度等级

    Example:
        rank=1, total=10, threshold=0.3 → percentile=0.1 → high
        rank=3, total=10, threshold=0.3 → percentile=0.3 → medium
    """
    if total_count == 0:
        return "low"

    percentile = rank / total_count

    # 排名越靠前，置信度越高
    if percentile <= threshold_percentile / 2:
        return "high"
    elif percentile <= threshold_percentile:
        return "medium"
    else:
        return "low"


def calculate_confidence_from_spread(
    spread: float,
    threshold: float,
) -> ConfidenceLevel:
    """
    基于差值计算置信度

    Args:
        spread: 差值绝对值
        threshold: 阈值

    Returns:
        置信度等级

    Example:
        spread=3.0, threshold=1.0 → ratio=3.0 → high
        spread=1.5, threshold=1.0 → ratio=1.5 → medium
    """
    if threshold == 0:
        return "medium"

    ratio = spread / abs(threshold)

    if ratio >= CONFIDENCE_HIGH_MULTIPLIER:
        return "high"
    elif ratio >= CONFIDENCE_MEDIUM_MULTIPLIER:
        return "medium"
    else:
        return "low"