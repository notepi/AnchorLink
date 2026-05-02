"""
Signal Layer 数据模型

定义 Signal 层的核心数据结构：
  - Evidence: 信号支撑数据
  - Signal: 单个信号标签
  - SignalResult: 信号计算结果容器

按 implementation.md Phase 5 设计
"""

from dataclasses import dataclass, field
from typing import Optional, Literal


# 类型定义
SignalCategory = Literal["beta", "alpha", "volume", "rotation", "abnormal"]
ConfidenceLevel = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class Evidence:
    """
    信号支撑数据

    标准化的 evidence 结构，包含：
      - 数值指标（用于判断的数据）
      - 来源标识（数据来自哪个池子/维度）
      - 状态标记（数据是否有效）
    """

    # 核心数值（必需）
    value: float                    # 核心判断值
    threshold: float                # 判断阈值

    # 来源信息（可选）
    source_pool: Optional[str] = None   # 数据来源池子ID
    source_field: Optional[str] = None  # 数据字段名

    # 辅助数值（可选）
    secondary_value: Optional[float] = None  # 辅助判断值
    percentile: Optional[float] = None       # 分位位置（0-100）

    # 状态标记
    is_valid: bool = True
    invalid_reason: Optional[str] = None


@dataclass(frozen=True)
class Signal:
    """
    信号标签

    按 PRD 定义的 35+ 个标签结构
    """

    # 基础标识
    label: str                      # 标签文本（如"行业Beta为正"）
    category: SignalCategory        # 标签类别
    confidence: ConfidenceLevel     # "high" | "medium" | "low"

    # 支撑数据
    evidence: Evidence              # 单个 evidence（大多数标签只需一个）
    trade_date: str                 # 交易日期 YYYYMMDD

    # 可选字段（带默认值）
    additional_evidence: dict = field(default_factory=dict)  # 多维度 evidence
    is_active: bool = True          # 标签是否激活（满足条件）
    inactive_reason: Optional[str] = None  # 未激活原因


@dataclass(frozen=True)
class SignalResult:
    """
    信号计算结果容器

    包含所有激活的信号标签
    """

    trade_date: str
    anchor_symbol: str
    signals: list[Signal] = field(default_factory=list)

    # 分类统计
    beta_count: int = 0
    alpha_count: int = 0
    volume_count: int = 0
    rotation_count: int = 0
    abnormal_count: int = 0

    # 数据质量
    data_status: str = "ok"  # "ok" | "partial" | "insufficient_data"
    missing_data: list[str] = field(default_factory=list)
    partial_reason: Optional[str] = None