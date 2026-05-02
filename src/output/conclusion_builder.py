"""
结论生成模块

职责：
  - 从 SignalResult 计算 industry_beta 判断
  - 从 SignalResult 计算 anchor_alpha 判断
  - 综合计算 risk_level
  - 生成 summary 模板文本
  - 生成 next_watch 观察点列表

按 PRD 第13节 conclusion 字段定义
"""

from typing import Optional

from src.output.models import (
    Conclusion,
    BetaLevel,
    AlphaLevel,
    RiskLevel,
)
from src.signal.models import SignalResult, Signal
from src.pool_state.models import PoolState
from src.anchor_position.relative_strength import RelativeStrength
from src.group_rotation.models import GroupRotation


# ============================================================
# industry_beta 计算
# ============================================================

def determine_industry_beta(signal_result: SignalResult) -> BetaLevel:
    """
    从 beta 类信号判断行业 Beta

    Args:
        signal_result: 信号结果

    Returns:
        "positive" | "neutral" | "negative"

    规则：
        - 有 "行业Beta为正" 标签 → positive
        - 有 "行业Beta为负" 标签 → negative
        - 其他（中性或无标签） → neutral
    """
    beta_signals = [s for s in signal_result.signals if s.category == "beta"]

    for signal in beta_signals:
        if signal.label == "行业Beta为正":
            return "positive"
        elif signal.label == "行业Beta为负":
            return "negative"

    return "neutral"


# ============================================================
# anchor_alpha 计算
# ============================================================

def determine_anchor_alpha(signal_result: SignalResult) -> AlphaLevel:
    """
    从 alpha 类信号判断个股 Alpha

    Args:
        signal_result: 信号结果

    Returns:
        "positive" | "neutral" | "negative"

    规则：
        - 有 "个股Alpha为正" 或 "跑赢核心同类" → positive
        - 有 "个股Alpha为负" 或 "跑输核心同类" → negative
        - 其他 → neutral
    """
    alpha_signals = [s for s in signal_result.signals if s.category == "alpha"]

    positive_labels = ["个股Alpha为正", "跑赢核心同类"]
    negative_labels = ["个股Alpha为负", "跑输核心同类"]

    for signal in alpha_signals:
        if signal.label in positive_labels:
            return "positive"
        elif signal.label in negative_labels:
            return "negative"

    return "neutral"


# ============================================================
# risk_level 计算
# ============================================================

def determine_risk_level(
    signal_result: SignalResult,
    pool_states: dict[str, PoolState],
) -> RiskLevel:
    """
    综合计算风险等级

    Args:
        signal_result: 信号结果
        pool_states: 各池子状态

    Returns:
        "low" | "medium" | "high"

    规则：
        - high: 数据不足(insufficient_data) 或 有异常联动标签(abnormal类)
        - medium: 数据部分缺失(partial) 或 行业分化
        - low: 数据完整(ok) 且 无异常信号
    """
    # 数据不足 → high
    if signal_result.data_status == "insufficient_data":
        return "high"

    # 有异常联动标签 → high
    abnormal_signals = [s for s in signal_result.signals if s.category == "abnormal"]
    if len(abnormal_signals) > 0:
        return "high"

    # 数据部分缺失 → medium
    if signal_result.data_status == "partial":
        return "medium"

    # 行业分化 → medium
    for pool_state in pool_states.values():
        if pool_state.strong_count >= 3 or pool_state.weak_count >= 3:
            return "medium"

    # 数据完整且无异常 → low
    return "low"


# ============================================================
# summary 生成
# ============================================================

def generate_summary(
    industry_beta: BetaLevel,
    anchor_alpha: AlphaLevel,
    risk_level: RiskLevel,
    pool_states: dict[str, PoolState],
    anchor_positions: dict[str, RelativeStrength],
    group_rotation: GroupRotation,
) -> str:
    """
    生成综合判断文本（3-5句话）

    Args:
        industry_beta: 行业 Beta 判断
        anchor_alpha: 个股 Alpha 判断
        risk_level: 风险等级
        pool_states: 各池子状态
        anchor_positions: 相对位置
        group_rotation: 组间轮动

    Returns:
        summary 文本

    模板结构：
        1. 行业环境：{industry_beta}，核心同类池中位数涨跌幅 {direct_peers_median}%
        2. 锚定标的表现：{anchor_alpha}，涨跌幅 {anchor_return}%，相对核心池 {relative_strength}%
        3. 组间轮动：{strongest_group}最强，{weakest_group}最弱
        4. 需关注点：风险等级 {risk_level}
    """
    sentences = []

    # 1. 行业环境
    direct_peers = pool_states.get("direct_peers")
    if direct_peers and direct_peers.median_return is not None:
        beta_desc = {"positive": "偏正面", "neutral": "中性", "negative": "偏负面"}
        sentences.append(
            f"行业环境{beta_desc[industry_beta]}，核心同类池中位数涨跌幅{direct_peers.median_return:.2f}%。"
        )
    else:
        beta_desc = {"positive": "偏正面", "neutral": "中性", "negative": "偏负面"}
        sentences.append(f"行业环境{beta_desc[industry_beta]}。")

    # 2. 锚定标的表现
    direct_peers_position = anchor_positions.get("direct_peers")
    if direct_peers_position:
        alpha_desc = {"positive": "跑赢行业", "neutral": "跟随行业", "negative": "跑输行业"}
        anchor_return = direct_peers_position.anchor_return
        relative_strength = direct_peers_position.relative_strength
        sentences.append(
            f"锚定标的{alpha_desc[anchor_alpha]}，涨跌幅{anchor_return:.2f}%，相对核心池{relative_strength:.2f}%。"
        )
    else:
        alpha_desc = {"positive": "跑赢行业", "neutral": "跟随行业", "negative": "跑输行业"}
        sentences.append(f"锚定标的{alpha_desc[anchor_alpha]}。")

    # 3. 组间轮动
    if group_rotation.strongest_group and group_rotation.weakest_group:
        strongest = group_rotation.strongest_group
        weakest = group_rotation.weakest_group
        strongest_median = group_rotation.group_medians.get(strongest)
        weakest_median = group_rotation.group_medians.get(weakest)

        if strongest_median is not None and weakest_median is not None:
            sentences.append(
                f"{strongest}池最强（中位数{strongest_median:.2f}%），{weakest}池最弱（{weakest_median:.2f}%）。"
            )
        else:
            sentences.append(f"{strongest}池最强，{weakest}池最弱。")

    # 4. 需关注点
    risk_desc = {"low": "风险较低", "medium": "需关注", "high": "需警惕"}
    sentences.append(f"整体风险等级：{risk_desc[risk_level]}。")

    return "".join(sentences)


# ============================================================
# next_watch 生成
# ============================================================

def generate_next_watch(
    signal_result: SignalResult,
    anchor_positions: dict[str, RelativeStrength],
    pool_states: dict[str, PoolState],
) -> list[str]:
    """
    生成次日观察点

    Args:
        signal_result: 信号结果
        anchor_positions: 相对位置
        pool_states: 各池子状态

    Returns:
        观察点列表

    规则：
        - 跑赢核心同类 → "是否连续跑赢核心同类"
        - 放量 → "成交额是否维持放大"
        - 主题池强于核心 → "主题池热度是否传导到核心同类"
        - 行业分化 → "分化是否继续扩大"
    """
    watch_points = []

    # 1. 跑赢核心同类 → 连续性观察
    alpha_signals = [s for s in signal_result.signals if s.category == "alpha"]
    if any(s.label in ["跑赢核心同类", "个股Alpha为正"] for s in alpha_signals):
        watch_points.append("是否连续跑赢核心同类")

    # 2. 放量 → 成交额观察
    volume_signals = [s for s in signal_result.signals if s.category == "volume"]
    if any(s.label in ["放量上涨", "放量下跌", "主力资金领先"] for s in volume_signals):
        watch_points.append("成交额是否维持放大")

    # 3. 主题池相关 → 传导观察
    rotation_signals = [s for s in signal_result.signals if s.category == "rotation"]
    if any(s.label in ["主题扩散强于核心同类", "交易观察池升温"] for s in rotation_signals):
        watch_points.append("主题池热度是否传导到核心同类")

    # 4. 行业分化 → 分化观察
    beta_signals = [s for s in signal_result.signals if s.category == "beta"]
    if any(s.label == "行业分化" for s in beta_signals):
        watch_points.append("分化是否继续扩大")

    # 5. 异常联动 → 异常观察
    abnormal_signals = [s for s in signal_result.signals if s.category == "abnormal"]
    if len(abnormal_signals) > 0:
        watch_points.append("异常联动是否持续")

    # 默认观察点（如果没有生成任何观察点）
    if len(watch_points) == 0:
        watch_points.append("核心同类池整体表现")
        watch_points.append("锚定标的相对位置变化")

    return watch_points[:5]  # 最多返回5个观察点


# ============================================================
# Conclusion 主入口
# ============================================================

def build_conclusion(
    signal_result: SignalResult,
    pool_states: dict[str, PoolState],
    anchor_positions: dict[str, RelativeStrength],
    group_rotation: GroupRotation,
) -> Conclusion:
    """
    构建综合结论

    Args:
        signal_result: 信号结果
        pool_states: 各池子状态
        anchor_positions: 相对位置
        group_rotation: 组间轮动

    Returns:
        Conclusion 完整结构
    """
    # 计算各字段
    industry_beta = determine_industry_beta(signal_result)
    anchor_alpha = determine_anchor_alpha(signal_result)
    risk_level = determine_risk_level(signal_result, pool_states)
    summary = generate_summary(
        industry_beta, anchor_alpha, risk_level,
        pool_states, anchor_positions, group_rotation
    )
    next_watch = generate_next_watch(signal_result, anchor_positions, pool_states)

    return Conclusion(
        industry_beta=industry_beta,
        anchor_alpha=anchor_alpha,
        risk_level=risk_level,
        summary=summary,
        next_watch=next_watch,
    )