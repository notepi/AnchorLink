"""
Group Rotation 模块

职责：
  - 比较四类池子之间谁强谁弱
  - 找出最强和最弱池子
  - 计算组间差值（spread）

核心组件：
  - GroupRotation: 组间轮动结果数据类
  - analyze_group_rotation: 组间强弱分析
  - SpreadCalculator: Spread 差值计算
"""

from src.group_rotation.models import GroupRotation
from src.group_rotation.rotation_analyzer import (
    analyze_group_rotation,
    determine_strongest_weakest,
)
from src.group_rotation.spread_calculator import (
    SpreadCalculator,
    calculate_single_spread,
    analyze_rotation_with_spreads,
)

__all__ = [
    "GroupRotation",
    "analyze_group_rotation",
    "determine_strongest_weakest",
    "SpreadCalculator",
    "calculate_single_spread",
    "analyze_rotation_with_spreads",
]