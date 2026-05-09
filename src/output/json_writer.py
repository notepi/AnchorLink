"""
JSON 输出模块

职责：
  - 构建 IndustrySnapshot 数据结构
  - 将各模块输出聚合为完整 JSON
  - 写入 industry_snapshot.json 文件

按 PRD 第13节定义的 JSON 结构
"""

import json
from pathlib import Path
from typing import Optional

from src.output.models import (
    IndustrySnapshot,
    AnchorInfo,
    DataQuality,
    IndustryState,
    AnchorPositionOutput,
    GroupRotationOutput,
    SignalOutput,
)
from src.output.conclusion_builder import build_conclusion
from src.config.loader import PoolRegistry, Instrument
from src.pool_state.models import PoolState
from src.anchor_position.relative_strength import RelativeStrength
from src.group_rotation.models import GroupRotation
from src.signal.models import SignalResult, Signal, Evidence
from src.linkage.models import LinkageAnalysis, PoolLinkage, LinkageMember


# ============================================================
# IndustrySnapshot 构建
# ============================================================

def build_anchor_info(registry: PoolRegistry) -> AnchorInfo:
    """
    构建锚定标的信息

    Args:
        registry: 配置注册表

    Returns:
        AnchorInfo 结构
    """
    anchor = registry.get_anchor()
    instrument = registry.get_instrument(anchor.symbol)

    themes = instrument.fact_tags if instrument else []

    return AnchorInfo(
        symbol=anchor.symbol,
        name=anchor.name,
        themes=themes,
    )


def build_data_quality(signal_result: SignalResult) -> DataQuality:
    """
    构建数据质量信息

    Args:
        signal_result: 信号结果

    Returns:
        DataQuality 结构
    """
    # 从 missing_data 提取 insufficient_universes
    insufficient_universes = []
    for missing in signal_result.missing_data:
        if "pool_state" in missing or "position" in missing:
            universe_id = missing.split(" ")[0]
            insufficient_universes.append(universe_id)

    return DataQuality(
        status=signal_result.data_status,
        missing_fields=signal_result.missing_data,
        insufficient_universes=insufficient_universes,
    )


def build_industry_state(pool_states: dict[str, PoolState]) -> IndustryState:
    """
    构建行业状态指标

    Args:
        pool_states: 各池子状态

    Returns:
        IndustryState 结构
    """
    direct_peers = pool_states.get("direct_peers")
    industry_chain = pool_states.get("industry_chain")
    theme_pool = pool_states.get("theme_pool")

    return IndustryState(
        direct_peers_return_median=direct_peers.median_return if direct_peers else None,
        industry_chain_return_median=industry_chain.median_return if industry_chain else None,
        theme_pool_return_median=theme_pool.median_return if theme_pool else None,
        up_ratio=direct_peers.up_ratio if direct_peers else None,
        amount_expansion_ratio=direct_peers.volume_multiplier if direct_peers else None,
        moneyflow_positive_ratio=direct_peers.fund_positive_ratio if direct_peers else None,
    )


def build_anchor_position(
    anchor_positions: dict[str, RelativeStrength],
) -> AnchorPositionOutput:
    """
    构建锚定标的相对位置

    Args:
        anchor_positions: 相对位置数据

    Returns:
        AnchorPositionOutput 结构
    """
    direct_peers = anchor_positions.get("direct_peers")
    industry_chain = anchor_positions.get("industry_chain")
    theme_pool = anchor_positions.get("theme_pool")

    if direct_peers:
        return AnchorPositionOutput(
            anchor_return=direct_peers.anchor_return,
            relative_strength_vs_direct_peers=direct_peers.relative_strength,
            relative_strength_vs_industry_chain=industry_chain.relative_strength if industry_chain else None,
            relative_strength_vs_theme_pool=theme_pool.relative_strength if theme_pool else None,
            return_rank=direct_peers.rank_return,
            amount_rank=direct_peers.rank_volume,
            turnover_rank=direct_peers.rank_turnover,
            moneyflow_rank=direct_peers.rank_fund,
            total_count=direct_peers.total_count,
            valuation_percentile=direct_peers.valuation_percentile,
        )
    else:
        return AnchorPositionOutput(
            anchor_return=0.0,
        )


def build_group_rotation_output(group_rotation: GroupRotation) -> GroupRotationOutput:
    """
    构建组间轮动输出

    Args:
        group_rotation: 组间轮动数据

    Returns:
        GroupRotationOutput 结构
    """
    return GroupRotationOutput(
        strongest_group=group_rotation.strongest_group,
        weakest_group=group_rotation.weakest_group,
        core_pool_id=group_rotation.core_pool_id,
        group_ranking=group_rotation.group_ranking,
        core_vs_theme_spread=group_rotation.core_vs_theme_spread,
        core_vs_chain_spread=group_rotation.core_vs_chain_spread,
        core_vs_trading_spread=group_rotation.core_vs_trading_spread,
        group_medians=group_rotation.group_medians,
    )


def build_signal_outputs(signal_result: SignalResult) -> list[SignalOutput]:
    """
    构建信号标签输出

    Args:
        signal_result: 信号结果

    Returns:
        SignalOutput 列表
    """
    outputs = []

    for signal in signal_result.signals:
        # Evidence 转 dict
        evidence_dict = _evidence_to_dict(signal.evidence)

        # 合并 additional_evidence
        if signal.additional_evidence:
            evidence_dict.update(signal.additional_evidence)

        outputs.append(SignalOutput(
            label=signal.label,
            category=signal.category,
            confidence=signal.confidence,
            evidence=evidence_dict,
        ))

    return outputs


def _evidence_to_dict(evidence: Evidence) -> dict:
    """
    将 Evidence dataclass 转换为 dict

    Args:
        evidence: Evidence 结构

    Returns:
        dict 格式
    """
    result = {
        "value": evidence.value,
        "threshold": evidence.threshold,
    }

    if evidence.source_pool:
        result["source_pool"] = evidence.source_pool
    if evidence.source_field:
        result["source_field"] = evidence.source_field
    if evidence.secondary_value is not None:
        result["secondary_value"] = evidence.secondary_value
    if evidence.percentile is not None:
        result["percentile"] = evidence.percentile

    return result


def _format_date(trade_date: str) -> str:
    """
    将 YYYYMMDD 格式转换为 YYYY-MM-DD

    Args:
        trade_date: YYYYMMDD 格式日期

    Returns:
        YYYY-MM-DD 格式日期
    """
    if len(trade_date) == 8:
        return f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
    return trade_date


# ============================================================
# 主入口函数
# ============================================================

def build_industry_snapshot(
    registry: PoolRegistry,
    pool_states: dict[str, PoolState],
    anchor_positions: dict[str, RelativeStrength],
    group_rotation: GroupRotation,
    signal_result: SignalResult,
    linkage_analysis: Optional[LinkageAnalysis] = None,
) -> IndustrySnapshot:
    """
    构建完整的 IndustrySnapshot

    Args:
        registry: 配置注册表
        pool_states: 各池子状态
        anchor_positions: 相对位置数据
        group_rotation: 组间轮动数据
        signal_result: 信号结果

    Returns:
        IndustrySnapshot 完整结构
    """
    # 构建各部分
    anchor_info = build_anchor_info(registry)
    data_quality = build_data_quality(signal_result)
    industry_state = build_industry_state(pool_states)
    anchor_position = build_anchor_position(anchor_positions)
    group_rotation_output = build_group_rotation_output(group_rotation)
    signal_outputs = build_signal_outputs(signal_result)

    # 构建 conclusion
    conclusion = build_conclusion(
        signal_result, pool_states, anchor_positions, group_rotation, linkage_analysis
    )

    # 格式化日期
    as_of_date = _format_date(signal_result.trade_date)

    return IndustrySnapshot(
        anchor=anchor_info,
        as_of_date=as_of_date,
        data_quality=data_quality,
        industry_state=industry_state,
        anchor_position=anchor_position,
        group_rotation=group_rotation_output,
        signals=signal_outputs,
        conclusion=conclusion,
        linkage_analysis=linkage_analysis,
    )


# ============================================================
# JSON 写入
# ============================================================

def snapshot_to_dict(snapshot: IndustrySnapshot) -> dict:
    """
    将 IndustrySnapshot 转换为 dict（用于 JSON 序列化）

    Args:
        snapshot: IndustrySnapshot 结构

    Returns:
        dict 格式
    """
    return {
        "anchor": {
            "symbol": snapshot.anchor.symbol,
            "name": snapshot.anchor.name,
            "themes": snapshot.anchor.themes,
        },
        "as_of_date": snapshot.as_of_date,
        "data_quality": {
            "status": snapshot.data_quality.status,
            "missing_fields": snapshot.data_quality.missing_fields,
            "insufficient_universes": snapshot.data_quality.insufficient_universes,
        },
        "industry_state": {
            "direct_peers_return_median": snapshot.industry_state.direct_peers_return_median,
            "industry_chain_return_median": snapshot.industry_state.industry_chain_return_median,
            "theme_pool_return_median": snapshot.industry_state.theme_pool_return_median,
            "up_ratio": snapshot.industry_state.up_ratio,
            "amount_expansion_ratio": snapshot.industry_state.amount_expansion_ratio,
            "moneyflow_positive_ratio": snapshot.industry_state.moneyflow_positive_ratio,
        },
        "anchor_position": {
            "anchor_return": snapshot.anchor_position.anchor_return,
            "relative_strength_vs_direct_peers": snapshot.anchor_position.relative_strength_vs_direct_peers,
            "relative_strength_vs_industry_chain": snapshot.anchor_position.relative_strength_vs_industry_chain,
            "relative_strength_vs_theme_pool": snapshot.anchor_position.relative_strength_vs_theme_pool,
            "return_rank": snapshot.anchor_position.return_rank,
            "amount_rank": snapshot.anchor_position.amount_rank,
            "turnover_rank": snapshot.anchor_position.turnover_rank,
            "moneyflow_rank": snapshot.anchor_position.moneyflow_rank,
            "total_count": snapshot.anchor_position.total_count,
            "valuation_percentile": snapshot.anchor_position.valuation_percentile,
        },
        "group_rotation": {
            "strongest_group": snapshot.group_rotation.strongest_group,
            "weakest_group": snapshot.group_rotation.weakest_group,
            "core_pool_id": snapshot.group_rotation.core_pool_id,
            "group_ranking": snapshot.group_rotation.group_ranking,
            "core_vs_theme_spread": snapshot.group_rotation.core_vs_theme_spread,
            "core_vs_chain_spread": snapshot.group_rotation.core_vs_chain_spread,
            "core_vs_trading_spread": snapshot.group_rotation.core_vs_trading_spread,
            "group_medians": snapshot.group_rotation.group_medians,
        },
        "signals": [
            {
                "label": s.label,
                "category": s.category,
                "confidence": s.confidence,
                "evidence": s.evidence,
            }
            for s in snapshot.signals
        ],
        "conclusion": {
            "industry_beta": snapshot.conclusion.industry_beta,
            "anchor_alpha": snapshot.conclusion.anchor_alpha,
            "risk_level": snapshot.conclusion.risk_level,
            "summary": snapshot.conclusion.summary,
            "next_watch": snapshot.conclusion.next_watch,
        },
        "linkage_analysis": _linkage_analysis_to_dict(snapshot.linkage_analysis),
    }


def _linkage_analysis_to_dict(linkage: Optional[LinkageAnalysis]) -> Optional[dict]:
    if linkage is None:
        return None

    return {
        "trade_date": linkage.trade_date,
        "anchor_symbol": linkage.anchor_symbol,
        "status": linkage.status,
        "windows": linkage.windows,
        "partial_reason": linkage.partial_reason,
        "pools": {
            universe_id: _pool_linkage_to_dict(pool)
            for universe_id, pool in linkage.pools.items()
        },
    }


def _pool_linkage_to_dict(pool: PoolLinkage) -> dict:
    return {
        "universe_id": pool.universe_id,
        "status": pool.status,
        "avg_corr_20d": pool.avg_corr_20d,
        "avg_beta_20d": pool.avg_beta_20d,
        "avg_direction_consistency_20d": pool.avg_direction_consistency_20d,
        "partial_reason": pool.partial_reason,
        "top_members": [_linkage_member_to_dict(member) for member in pool.top_members],
        "members": [_linkage_member_to_dict(member) for member in pool.members],
    }


def _linkage_member_to_dict(member: LinkageMember) -> dict:
    return {
        "universe_id": member.universe_id,
        "symbol": member.symbol,
        "name": member.name,
        "role": member.role,
        "relevance": member.relevance,
        "weight": member.weight,
        "corr_5d": member.corr_5d,
        "corr_10d": member.corr_10d,
        "corr_20d": member.corr_20d,
        "beta_5d": member.beta_5d,
        "beta_10d": member.beta_10d,
        "beta_20d": member.beta_20d,
        "direction_consistency_5d": member.direction_consistency_5d,
        "direction_consistency_10d": member.direction_consistency_10d,
        "direction_consistency_20d": member.direction_consistency_20d,
        "observations": member.observations,
        "data_status": member.data_status,
        "partial_reason": member.partial_reason,
    }


def write_json(snapshot: IndustrySnapshot, path: str | Path) -> None:
    """
    写入 industry_snapshot.json 文件

    Args:
        snapshot: IndustrySnapshot 结构
        path: 输出路径
    """
    path = Path(path)

    # 确保目录存在
    path.parent.mkdir(parents=True, exist_ok=True)

    # 转换为 dict 并写入
    data = snapshot_to_dict(snapshot)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
