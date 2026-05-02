"""
信号标签生成模块

职责：
  - 聚合 PoolState、RelativeStrength、GroupRotation 数据
  - 按 5 类规则生成标签
  - 计算置信度
  - 返回 SignalResult

按 implementation.md Phase 5 设计
"""

from typing import Optional

from src.signal.models import Signal, SignalResult, Evidence
from src.signal.rules import (
    BETA_POSITIVE_THRESHOLD,
    BETA_NEGATIVE_THRESHOLD,
    DIFFUSION_ENHANCE_THRESHOLD,
    DIFFUSION_INSUFFICIENT_THRESHOLD,
    DIVERGENCE_STRONG_THRESHOLD,
    DIVERGENCE_WEAK_THRESHOLD,
    ALPHA_POSITIVE_THRESHOLD,
    ALPHA_NEGATIVE_THRESHOLD,
    OUTPERFORM_RANK_THRESHOLD,
    UNDERPERFORM_RANK_THRESHOLD,
    VOLUME_HIGH_THRESHOLD,
    VOLUME_LOW_THRESHOLD,
    FUND_LEAD_THRESHOLD,
    FUND_DRAG_THRESHOLD,
    ROTATION_SPREAD_THRESHOLD,
    TRADING_POOL_HEAT_THRESHOLD,
    ABNORMAL_SPREAD_THRESHOLD,
    MIN_VALID_GROUPS,
)
from src.signal.confidence import (
    calculate_confidence,
    calculate_confidence_from_rank,
    calculate_confidence_from_spread,
)
from src.pool_state.models import PoolState
from src.anchor_position.relative_strength import RelativeStrength
from src.group_rotation.models import GroupRotation
from src.config.loader import PoolRegistry


# ============================================================
# 主入口函数
# ============================================================

def generate_signals(
    pool_states: dict[str, PoolState],
    anchor_positions: dict[str, RelativeStrength],
    group_rotation: GroupRotation,
    registry: Optional[PoolRegistry] = None,
) -> SignalResult:
    """
    生成所有信号标签

    Args:
        pool_states: 各池子状态（universe_id -> PoolState）
        anchor_positions: Anchor 相对各池子的位置（universe_id -> RelativeStrength）
        group_rotation: 组间轮动分析结果
        registry: 配置注册表（可选）

    Returns:
        SignalResult 完整结构

    Workflow:
        1. 数据质量检查
        2. 逐类生成标签（beta → alpha → volume → rotation → abnormal）
        3. 过滤激活标签
        4. 统计分类数量
        5. 返回结果
    """
    trade_date = _extract_trade_date(pool_states, anchor_positions, group_rotation)
    anchor_symbol = registry.anchor.symbol if registry else "unknown"

    # 数据质量检查
    data_status, missing_data, partial_reason = _check_signal_data_quality(
        pool_states, anchor_positions, group_rotation
    )

    if data_status == "insufficient_data":
        return _empty_signal_result(trade_date, anchor_symbol, missing_data, partial_reason)

    # 逐类生成标签
    all_signals = []

    # Beta 类
    beta_signals = generate_beta_signals(pool_states, trade_date)
    all_signals.extend(beta_signals)

    # Alpha 类
    alpha_signals = generate_alpha_signals(anchor_positions, pool_states, trade_date)
    all_signals.extend(alpha_signals)

    # Volume 类
    volume_signals = generate_volume_signals(pool_states, anchor_positions, trade_date)
    all_signals.extend(volume_signals)

    # Rotation 类
    rotation_signals = generate_rotation_signals(group_rotation, pool_states, trade_date)
    all_signals.extend(rotation_signals)

    # Abnormal 类
    abnormal_signals = generate_abnormal_signals(pool_states, anchor_positions, group_rotation, trade_date)
    all_signals.extend(abnormal_signals)

    # 过滤激活标签
    active_signals = [s for s in all_signals if s.is_active]

    # 统计分类数量
    beta_count = len([s for s in active_signals if s.category == "beta"])
    alpha_count = len([s for s in active_signals if s.category == "alpha"])
    volume_count = len([s for s in active_signals if s.category == "volume"])
    rotation_count = len([s for s in active_signals if s.category == "rotation"])
    abnormal_count = len([s for s in active_signals if s.category == "abnormal"])

    return SignalResult(
        trade_date=trade_date,
        anchor_symbol=anchor_symbol,
        signals=active_signals,
        beta_count=beta_count,
        alpha_count=alpha_count,
        volume_count=volume_count,
        rotation_count=rotation_count,
        abnormal_count=abnormal_count,
        data_status=data_status,
        missing_data=missing_data,
        partial_reason=partial_reason,
    )


# ============================================================
# Beta 类信号生成（行业 Beta）
# ============================================================

def generate_beta_signals(
    pool_states: dict[str, PoolState],
    trade_date: str,
) -> list[Signal]:
    """
    生成 Beta 类信号标签

    基于 direct_peers 池子状态：
      - 行业Beta为正/中性/负
      - 行业扩散增强/不足
      - 行业分化

    Args:
        pool_states: 各池子状态
        trade_date: 交易日期

    Returns:
        Beta 类信号列表（7 个标签）
    """
    signals = []

    # 获取核心同类池状态
    direct_peers = pool_states.get("direct_peers")
    if direct_peers is None or direct_peers.data_status == "insufficient_data":
        return signals

    # 1. 行业Beta为正/中性/负
    median_return = direct_peers.median_return
    if median_return is not None:
        if median_return > BETA_POSITIVE_THRESHOLD:
            signals.append(_create_signal(
                label="行业Beta为正",
                category="beta",
                value=median_return,
                threshold=BETA_POSITIVE_THRESHOLD,
                trade_date=trade_date,
                source_pool="direct_peers",
                source_field="median_return",
            ))
        elif median_return < BETA_NEGATIVE_THRESHOLD:
            signals.append(_create_signal(
                label="行业Beta为负",
                category="beta",
                value=median_return,
                threshold=BETA_NEGATIVE_THRESHOLD,
                trade_date=trade_date,
                source_pool="direct_peers",
                source_field="median_return",
                is_direction_positive=False,
            ))
        else:
            signals.append(_create_signal(
                label="行业Beta为中性",
                category="beta",
                value=median_return,
                threshold=0.0,
                trade_date=trade_date,
                source_pool="direct_peers",
                source_field="median_return",
                confidence="medium",
            ))

    # 2. 行业扩散增强/不足
    up_ratio = direct_peers.up_ratio
    if up_ratio is not None:
        if up_ratio > DIFFUSION_ENHANCE_THRESHOLD:
            signals.append(_create_signal(
                label="行业扩散增强",
                category="beta",
                value=up_ratio,
                threshold=DIFFUSION_ENHANCE_THRESHOLD,
                trade_date=trade_date,
                source_pool="direct_peers",
                source_field="up_ratio",
            ))
        elif up_ratio < DIFFUSION_INSUFFICIENT_THRESHOLD:
            signals.append(_create_signal(
                label="行业扩散不足",
                category="beta",
                value=up_ratio,
                threshold=DIFFUSION_INSUFFICIENT_THRESHOLD,
                trade_date=trade_date,
                source_pool="direct_peers",
                source_field="up_ratio",
                is_direction_positive=False,
            ))

    # 3. 行业分化
    strong_count = direct_peers.strong_count
    weak_count = direct_peers.weak_count
    if strong_count >= DIVERGENCE_STRONG_THRESHOLD or weak_count >= DIVERGENCE_WEAK_THRESHOLD:
        signals.append(_create_signal(
            label="行业分化",
            category="beta",
            value=max(strong_count, weak_count),
            threshold=DIVERGENCE_STRONG_THRESHOLD,
            trade_date=trade_date,
            source_pool="direct_peers",
            source_field="strong_count/weak_count",
            additional_evidence={"strong_count": strong_count, "weak_count": weak_count},
        ))

    return signals


# ============================================================
# Alpha 类信号生成（个股 Alpha）
# ============================================================

def generate_alpha_signals(
    anchor_positions: dict[str, RelativeStrength],
    pool_states: dict[str, PoolState],
    trade_date: str,
) -> list[Signal]:
    """
    生成 Alpha 类信号标签

    基于 Anchor 相对 direct_peers 的位置：
      - 个股Alpha为正/中性/负
      - 跑赢/跑输核心同类
      - 处于行业前排/后排

    Args:
        anchor_positions: Anchor 相对位置
        pool_states: 各池子状态
        trade_date: 交易日期

    Returns:
        Alpha 类信号列表
    """
    signals = []

    # 获取相对核心同类池的位置
    direct_peers_position = anchor_positions.get("direct_peers")
    if direct_peers_position is None or direct_peers_position.data_status == "insufficient_data":
        return signals

    # 1. 个股Alpha为正/中性/负
    relative_strength = direct_peers_position.relative_strength
    if relative_strength > ALPHA_POSITIVE_THRESHOLD:
        signals.append(_create_signal(
            label="个股Alpha为正",
            category="alpha",
            value=relative_strength,
            threshold=ALPHA_POSITIVE_THRESHOLD,
            trade_date=trade_date,
            source_pool="direct_peers",
            source_field="relative_strength",
        ))
    elif relative_strength < ALPHA_NEGATIVE_THRESHOLD:
        signals.append(_create_signal(
            label="个股Alpha为负",
            category="alpha",
            value=relative_strength,
            threshold=ALPHA_NEGATIVE_THRESHOLD,
            trade_date=trade_date,
            source_pool="direct_peers",
            source_field="relative_strength",
            is_direction_positive=False,
        ))
    else:
        signals.append(_create_signal(
            label="个股Alpha为中性",
            category="alpha",
            value=relative_strength,
            threshold=0.0,
            trade_date=trade_date,
            source_pool="direct_peers",
            source_field="relative_strength",
            confidence="medium",
        ))

    # 2. 跑赢/跑输核心同类（基于 position 字段）
    position = direct_peers_position.position
    if position == "outperform" and relative_strength > ALPHA_POSITIVE_THRESHOLD:
        signals.append(_create_signal(
            label="跑赢核心同类",
            category="alpha",
            value=relative_strength,
            threshold=ALPHA_POSITIVE_THRESHOLD,
            trade_date=trade_date,
            source_pool="direct_peers",
            source_field="position",
        ))
    elif position == "underperform" and relative_strength < ALPHA_NEGATIVE_THRESHOLD:
        signals.append(_create_signal(
            label="跑输核心同类",
            category="alpha",
            value=relative_strength,
            threshold=ALPHA_NEGATIVE_THRESHOLD,
            trade_date=trade_date,
            source_pool="direct_peers",
            source_field="position",
            is_direction_positive=False,
        ))

    # 3. 处于行业前排/后排（基于排名）
    rank_return = direct_peers_position.rank_return
    total_count = direct_peers_position.total_count
    if total_count > 0 and rank_return > 0:
        rank_percentile = rank_return / total_count
        if rank_percentile <= OUTPERFORM_RANK_THRESHOLD:
            confidence = calculate_confidence_from_rank(rank_return, total_count, OUTPERFORM_RANK_THRESHOLD)
            signals.append(_create_signal(
                label="处于行业前排",
                category="alpha",
                value=rank_percentile,
                threshold=OUTPERFORM_RANK_THRESHOLD,
                trade_date=trade_date,
                source_pool="direct_peers",
                source_field="rank_return",
                percentile=rank_percentile * 100,
                confidence=confidence,
            ))
        elif rank_percentile >= UNDERPERFORM_RANK_THRESHOLD:
            confidence = calculate_confidence_from_rank(rank_return, total_count, UNDERPERFORM_RANK_THRESHOLD)
            signals.append(_create_signal(
                label="处于行业后排",
                category="alpha",
                value=rank_percentile,
                threshold=UNDERPERFORM_RANK_THRESHOLD,
                trade_date=trade_date,
                source_pool="direct_peers",
                source_field="rank_return",
                percentile=rank_percentile * 100,
                confidence=confidence,
                is_direction_positive=False,
            ))

    return signals


# ============================================================
# Volume 类信号生成（资金成交）
# ============================================================

def generate_volume_signals(
    pool_states: dict[str, PoolState],
    anchor_positions: dict[str, RelativeStrength],
    trade_date: str,
) -> list[Signal]:
    """
    生成 Volume 类信号标签

    基于成交额放大倍数和资金流向：
      - 放量上涨/下跌
      - 缩量调整
      - 放量滞涨
      - 资金价格共振/背离
      - 主力资金领先/拖累

    Args:
        pool_states: 各池子状态
        anchor_positions: Anchor 相对位置
        trade_date: 交易日期

    Returns:
        Volume 类信号列表
    """
    signals = []

    direct_peers = pool_states.get("direct_peers")
    direct_peers_position = anchor_positions.get("direct_peers")

    if direct_peers is None or direct_peers_position is None:
        return signals

    # 获取关键数据
    volume_multiplier = direct_peers.volume_multiplier
    anchor_return = direct_peers_position.anchor_return
    fund_positive_ratio = direct_peers.fund_positive_ratio

    # 1. 放量上涨/下跌
    if volume_multiplier is not None and volume_multiplier > VOLUME_HIGH_THRESHOLD:
        if anchor_return > 0:
            signals.append(_create_signal(
                label="放量上涨",
                category="volume",
                value=volume_multiplier,
                threshold=VOLUME_HIGH_THRESHOLD,
                trade_date=trade_date,
                source_pool="direct_peers",
                source_field="volume_multiplier",
                secondary_value=anchor_return,
                additional_evidence={"anchor_return": anchor_return},
            ))
        elif anchor_return < 0:
            signals.append(_create_signal(
                label="放量下跌",
                category="volume",
                value=volume_multiplier,
                threshold=VOLUME_HIGH_THRESHOLD,
                trade_date=trade_date,
                source_pool="direct_peers",
                source_field="volume_multiplier",
                secondary_value=anchor_return,
                additional_evidence={"anchor_return": anchor_return},
            ))

    # 2. 缩量调整
    if volume_multiplier is not None and volume_multiplier < VOLUME_LOW_THRESHOLD:
        signals.append(_create_signal(
            label="缩量调整",
            category="volume",
            value=volume_multiplier,
            threshold=VOLUME_LOW_THRESHOLD,
            trade_date=trade_date,
            source_pool="direct_peers",
            source_field="volume_multiplier",
            is_direction_positive=False,
        ))

    # 3. 放量滞涨（放量但涨幅小）
    if volume_multiplier is not None and volume_multiplier > VOLUME_HIGH_THRESHOLD:
        if anchor_return > 0 and anchor_return < 0.5:
            signals.append(_create_signal(
                label="放量滞涨",
                category="volume",
                value=volume_multiplier,
                threshold=VOLUME_HIGH_THRESHOLD,
                trade_date=trade_date,
                source_pool="direct_peers",
                source_field="volume_multiplier",
                secondary_value=anchor_return,
                additional_evidence={"anchor_return": anchor_return},
            ))

    # 4. 资金价格共振/背离
    if fund_positive_ratio is not None:
        if fund_positive_ratio > FUND_LEAD_THRESHOLD and anchor_return > 0:
            signals.append(_create_signal(
                label="资金价格共振",
                category="volume",
                value=fund_positive_ratio,
                threshold=FUND_LEAD_THRESHOLD,
                trade_date=trade_date,
                source_pool="direct_peers",
                source_field="fund_positive_ratio",
                secondary_value=anchor_return,
                additional_evidence={"anchor_return": anchor_return},
            ))
        elif fund_positive_ratio < FUND_DRAG_THRESHOLD and anchor_return > 0:
            signals.append(_create_signal(
                label="资金价格背离",
                category="volume",
                value=fund_positive_ratio,
                threshold=FUND_DRAG_THRESHOLD,
                trade_date=trade_date,
                source_pool="direct_peers",
                source_field="fund_positive_ratio",
                secondary_value=anchor_return,
                additional_evidence={"anchor_return": anchor_return},
                is_direction_positive=False,
            ))

    # 5. 主力资金领先/拖累
    if fund_positive_ratio is not None:
        if fund_positive_ratio > FUND_LEAD_THRESHOLD:
            signals.append(_create_signal(
                label="主力资金领先",
                category="volume",
                value=fund_positive_ratio,
                threshold=FUND_LEAD_THRESHOLD,
                trade_date=trade_date,
                source_pool="direct_peers",
                source_field="fund_positive_ratio",
            ))
        elif fund_positive_ratio < FUND_DRAG_THRESHOLD:
            signals.append(_create_signal(
                label="主力资金拖累",
                category="volume",
                value=fund_positive_ratio,
                threshold=FUND_DRAG_THRESHOLD,
                trade_date=trade_date,
                source_pool="direct_peers",
                source_field="fund_positive_ratio",
                is_direction_positive=False,
            ))

    return signals


# ============================================================
# Rotation 类信号生成（组间轮动）
# ============================================================

def generate_rotation_signals(
    group_rotation: GroupRotation,
    pool_states: dict[str, PoolState],
    trade_date: str,
) -> list[Signal]:
    """
    生成 Rotation 类信号标签

    基于组间轮动分析：
      - 核心同类强于主题扩散
      - 主题扩散强于核心同类
      - 产业链强于情绪池
      - 情绪池强于产业链
      - 交易观察池升温/降温

    Args:
        group_rotation: 组间轮动分析结果
        pool_states: 各池子状态
        trade_date: 交易日期

    Returns:
        Rotation 类信号列表
    """
    signals = []

    if group_rotation.data_status == "insufficient_data":
        return signals

    # 1. 核心同类 vs 主题扩散
    core_vs_theme = group_rotation.core_vs_theme_spread
    if core_vs_theme is not None:
        if core_vs_theme > ROTATION_SPREAD_THRESHOLD:
            signals.append(_create_signal(
                label="核心同类强于主题扩散",
                category="rotation",
                value=core_vs_theme,
                threshold=ROTATION_SPREAD_THRESHOLD,
                trade_date=trade_date,
                source_pool="direct_peers vs theme_pool",
                source_field="core_vs_theme_spread",
            ))
        elif core_vs_theme < -ROTATION_SPREAD_THRESHOLD:
            signals.append(_create_signal(
                label="主题扩散强于核心同类",
                category="rotation",
                value=abs(core_vs_theme),
                threshold=ROTATION_SPREAD_THRESHOLD,
                trade_date=trade_date,
                source_pool="theme_pool vs direct_peers",
                source_field="core_vs_theme_spread",
            ))

    # 2. 产业链 vs 情绪池（trading_watchlist）
    core_vs_trading = group_rotation.core_vs_trading_spread
    if core_vs_trading is not None:
        if core_vs_trading > ROTATION_SPREAD_THRESHOLD:
            signals.append(_create_signal(
                label="产业链强于情绪池",
                category="rotation",
                value=core_vs_trading,
                threshold=ROTATION_SPREAD_THRESHOLD,
                trade_date=trade_date,
                source_pool="industry_chain vs trading_watchlist",
                source_field="core_vs_trading_spread",
            ))
        elif core_vs_trading < -ROTATION_SPREAD_THRESHOLD:
            signals.append(_create_signal(
                label="情绪池强于产业链",
                category="rotation",
                value=abs(core_vs_trading),
                threshold=ROTATION_SPREAD_THRESHOLD,
                trade_date=trade_date,
                source_pool="trading_watchlist vs industry_chain",
                source_field="core_vs_trading_spread",
            ))

    # 3. 交易观察池升温/降温
    trading_pool = pool_states.get("trading_watchlist")
    if trading_pool and trading_pool.median_return is not None:
        if trading_pool.median_return > TRADING_POOL_HEAT_THRESHOLD:
            signals.append(_create_signal(
                label="交易观察池升温",
                category="rotation",
                value=trading_pool.median_return,
                threshold=TRADING_POOL_HEAT_THRESHOLD,
                trade_date=trade_date,
                source_pool="trading_watchlist",
                source_field="median_return",
            ))
        elif trading_pool.median_return < -TRADING_POOL_HEAT_THRESHOLD:
            signals.append(_create_signal(
                label="交易观察池降温",
                category="rotation",
                value=abs(trading_pool.median_return),
                threshold=TRADING_POOL_HEAT_THRESHOLD,
                trade_date=trade_date,
                source_pool="trading_watchlist",
                source_field="median_return",
            ))

    return signals


# ============================================================
# Abnormal 类信号生成（联动背离）
# ============================================================

def generate_abnormal_signals(
    pool_states: dict[str, PoolState],
    anchor_positions: dict[str, RelativeStrength],
    group_rotation: GroupRotation,
    trade_date: str,
) -> list[Signal]:
    """
    生成 Abnormal 类信号标签

    基于联动背离检测：
      - 行业强但个股弱
      - 行业弱但个股强
      - 主题池强但核心池弱
      - 核心池强但主题池弱

    Args:
        pool_states: 各池子状态
        anchor_positions: Anchor 相对位置
        group_rotation: 组间轮动分析结果
        trade_date: 交易日期

    Returns:
        Abnormal 类信号列表
    """
    signals = []

    # 1. 行业强但个股弱 / 行业弱但个股强
    direct_peers = pool_states.get("direct_peers")
    direct_peers_position = anchor_positions.get("direct_peers")

    if direct_peers and direct_peers_position:
        median_return = direct_peers.median_return
        relative_strength = direct_peers_position.relative_strength

        if median_return is not None and relative_strength is not None:
            # 行业涨，个股跌（相对）
            if median_return > BETA_POSITIVE_THRESHOLD and relative_strength < ALPHA_NEGATIVE_THRESHOLD:
                spread = abs(median_return - relative_strength)
                signals.append(_create_signal(
                    label="行业强但个股弱",
                    category="abnormal",
                    value=spread,
                    threshold=ABNORMAL_SPREAD_THRESHOLD,
                    trade_date=trade_date,
                    source_pool="direct_peers vs anchor",
                    source_field="median_return vs relative_strength",
                    additional_evidence={
                        "pool_median": median_return,
                        "relative_strength": relative_strength,
                    },
                ))

            # 行业跌，个股涨（相对）
            if median_return < BETA_NEGATIVE_THRESHOLD and relative_strength > ALPHA_POSITIVE_THRESHOLD:
                spread = abs(abs(median_return) + relative_strength)
                signals.append(_create_signal(
                    label="行业弱但个股强",
                    category="abnormal",
                    value=spread,
                    threshold=ABNORMAL_SPREAD_THRESHOLD,
                    trade_date=trade_date,
                    source_pool="direct_peers vs anchor",
                    source_field="median_return vs relative_strength",
                    additional_evidence={
                        "pool_median": median_return,
                        "relative_strength": relative_strength,
                    },
                ))

    # 2. 主题池强但核心池弱 / 核心池强但主题池弱
    core_vs_theme = group_rotation.core_vs_theme_spread
    if core_vs_theme is not None:
        if abs(core_vs_theme) > ABNORMAL_SPREAD_THRESHOLD:
            if core_vs_theme < 0:  # 主题池更强
                signals.append(_create_signal(
                    label="主题池强但核心池弱",
                    category="abnormal",
                    value=abs(core_vs_theme),
                    threshold=ABNORMAL_SPREAD_THRESHOLD,
                    trade_date=trade_date,
                    source_pool="theme_pool vs direct_peers",
                    source_field="core_vs_theme_spread",
                ))
            else:  # 核心池更强
                signals.append(_create_signal(
                    label="核心池强但主题池弱",
                    category="abnormal",
                    value=abs(core_vs_theme),
                    threshold=ABNORMAL_SPREAD_THRESHOLD,
                    trade_date=trade_date,
                    source_pool="direct_peers vs theme_pool",
                    source_field="core_vs_theme_spread",
                ))

    return signals


# ============================================================
# 辅助函数
# ============================================================

def _create_signal(
    label: str,
    category: str,
    value: float,
    threshold: float,
    trade_date: str,
    source_pool: str,
    source_field: str,
    secondary_value: Optional[float] = None,
    percentile: Optional[float] = None,
    additional_evidence: Optional[dict] = None,
    confidence: Optional[str] = None,
    is_direction_positive: bool = True,
) -> Signal:
    """
    创建信号标签

    Args:
        label: 标签文本
        category: 类别
        value: 核心值
        threshold: 阈值
        trade_date: 日期
        source_pool: 来源池子
        source_field: 来源字段
        secondary_value: 辅助值
        percentile: 分位
        additional_evidence: 附加证据
        confidence: 置信度（可选，自动计算）
        is_direction_positive: 方向是否正向

    Returns:
        Signal 完整结构
    """
    evidence = Evidence(
        value=value,
        threshold=threshold,
        source_pool=source_pool,
        source_field=source_field,
        secondary_value=secondary_value,
        percentile=percentile,
        is_valid=True,
    )

    # 计算置信度
    if confidence is None:
        confidence = calculate_confidence(value, threshold, is_direction_positive)

    return Signal(
        label=label,
        category=category,
        evidence=evidence,
        additional_evidence=additional_evidence or {},
        confidence=confidence,
        trade_date=trade_date,
        is_active=True,
    )


def _extract_trade_date(
    pool_states: dict[str, PoolState],
    anchor_positions: dict[str, RelativeStrength],
    group_rotation: GroupRotation,
) -> str:
    """
    提取交易日期

    从任意数据源中提取日期
    """
    if pool_states:
        for ps in pool_states.values():
            if ps.trade_date:
                return ps.trade_date

    if anchor_positions:
        for ap in anchor_positions.values():
            if ap.trade_date:
                return ap.trade_date

    if group_rotation.trade_date:
        return group_rotation.trade_date

    return "unknown"


def _check_signal_data_quality(
    pool_states: dict[str, PoolState],
    anchor_positions: dict[str, RelativeStrength],
    group_rotation: GroupRotation,
) -> tuple[str, list[str], Optional[str]]:
    """
    检查信号数据质量

    Returns:
        (data_status, missing_data, partial_reason)
    """
    missing_data = []

    # 检查核心池数据
    direct_peers = pool_states.get("direct_peers")
    if direct_peers is None:
        missing_data.append("direct_peers pool_state")
    elif direct_peers.data_status == "insufficient_data":
        missing_data.append("direct_peers data insufficient")

    # 检查 Anchor 位置数据
    direct_peers_position = anchor_positions.get("direct_peers")
    if direct_peers_position is None:
        missing_data.append("direct_peers anchor_position")
    elif direct_peers_position.data_status == "insufficient_data":
        missing_data.append("direct_peers position insufficient")

    # 检查组间轮动数据
    if group_rotation.data_status == "insufficient_data":
        missing_data.append("group_rotation insufficient")

    # 判断状态
    if len(missing_data) >= 3:
        return "insufficient_data", missing_data, "core data missing"
    elif len(missing_data) > 0:
        return "partial", missing_data, f"partial data: {', '.join(missing_data)}"
    else:
        return "ok", [], None


def _empty_signal_result(
    trade_date: str,
    anchor_symbol: str,
    missing_data: list[str],
    partial_reason: Optional[str],
) -> SignalResult:
    """
    创建空信号结果

    用于数据不足时返回
    """
    return SignalResult(
        trade_date=trade_date,
        anchor_symbol=anchor_symbol,
        signals=[],
        beta_count=0,
        alpha_count=0,
        volume_count=0,
        rotation_count=0,
        abnormal_count=0,
        data_status="insufficient_data",
        missing_data=missing_data,
        partial_reason=partial_reason,
    )