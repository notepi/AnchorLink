"""
Signal Layer - 信号标签生成模块

职责：
  - 将 PoolState、AnchorPosition、GroupRotation 数据转化为可读信号标签
  - 按 PRD 定义生成 5 类 35+ 个标签
  - 每个标签携带 evidence 支撑数据

模块结构：
  - models.py: Evidence, Signal, SignalResult 数据结构
  - rules.py: 阈值常量定义
  - confidence.py: 置信度计算
  - label_generator.py: 标签生成主入口

使用示例：
    from src.signal import generate_signals, SignalResult

    result = generate_signals(pool_states, anchor_positions, group_rotation)
    for signal in result.signals:
        print(f"{signal.label}: {signal.evidence.value}")
"""

from src.signal.models import (
    Evidence,
    Signal,
    SignalResult,
    SignalCategory,
    ConfidenceLevel,
)
from src.signal.rules import (
    BETA_POSITIVE_THRESHOLD,
    BETA_NEGATIVE_THRESHOLD,
    ALPHA_POSITIVE_THRESHOLD,
    ALPHA_NEGATIVE_THRESHOLD,
    VOLUME_HIGH_THRESHOLD,
    VOLUME_LOW_THRESHOLD,
    ROTATION_SPREAD_THRESHOLD,
    ABNORMAL_SPREAD_THRESHOLD,
)
from src.signal.confidence import (
    calculate_confidence,
    calculate_confidence_from_rank,
    calculate_confidence_from_spread,
)
from src.signal.label_generator import (
    generate_signals,
    generate_beta_signals,
    generate_alpha_signals,
    generate_volume_signals,
    generate_rotation_signals,
    generate_abnormal_signals,
)


__all__ = [
    # 数据结构
    "Evidence",
    "Signal",
    "SignalResult",
    "SignalCategory",
    "ConfidenceLevel",
    # 阈值常量
    "BETA_POSITIVE_THRESHOLD",
    "BETA_NEGATIVE_THRESHOLD",
    "ALPHA_POSITIVE_THRESHOLD",
    "ALPHA_NEGATIVE_THRESHOLD",
    "VOLUME_HIGH_THRESHOLD",
    "VOLUME_LOW_THRESHOLD",
    "ROTATION_SPREAD_THRESHOLD",
    "ABNORMAL_SPREAD_THRESHOLD",
    # 置信度计算
    "calculate_confidence",
    "calculate_confidence_from_rank",
    "calculate_confidence_from_spread",
    # 标签生成
    "generate_signals",
    "generate_beta_signals",
    "generate_alpha_signals",
    "generate_volume_signals",
    "generate_rotation_signals",
    "generate_abnormal_signals",
]