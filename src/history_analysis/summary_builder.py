"""
历史汇总表构建模块

从 data/output/{YYYYMMDD}/industry_snapshot.json 读取所有快照，
拉平为 HistoryRow 列表，含前瞻收益和前瞻超额。
"""

import json
from pathlib import Path
from typing import Optional

from src.history_analysis.models import HistoryRow, SignalPair
from src.history_analysis.forward_returns import (
    build_trading_day_closes,
    compute_forward_returns,
    compute_forward_excess,
    build_chain_forward_returns,
)

ANCHOR_SYMBOL = "688333.SH"
FORWARD_WINDOWS = [1, 3, 5]


def load_all_snapshots(output_root: Path) -> list[dict]:
    """
    扫描 data/output/ 下所有日期目录，读取 industry_snapshot.json。

    Returns:
        按 as_of_date 排序的 JSON dict 列表
    """
    snapshots: list[dict] = []

    for date_dir in sorted(output_root.iterdir()):
        if not date_dir.is_dir():
            continue
        json_path = date_dir / "industry_snapshot.json"
        if not json_path.exists():
            continue

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        snapshots.append(data)

    snapshots.sort(key=lambda s: s.get("as_of_date", ""))
    return snapshots


def _extract_signal_labels(signals: list[dict]) -> str:
    """提取信号标签，逗号分隔"""
    return ",".join(s.get("label", "") for s in signals if s.get("label"))


def _extract_signal_categories(signals: list[dict]) -> str:
    """提取信号类别，去重，逗号分隔"""
    categories = list(dict.fromkeys(s.get("category", "") for s in signals if s.get("category")))
    return ",".join(categories)


def _extract_signal_pairs(signals: list[dict]) -> str:
    """提取信号标签-类别对，返回 JSON 字符串"""
    pairs = [
        {"label": s.get("label", ""), "category": s.get("category", "")}
        for s in signals
        if s.get("label")
    ]
    return json.dumps(pairs, ensure_ascii=False)


def _as_of_date_to_yyyymmdd(as_of_date: str) -> str:
    """将 YYYY-MM-DD 转换为 YYYYMMDD"""
    return as_of_date.replace("-", "")


def flatten_snapshot(
    snapshot: dict,
    anchor_closes: dict[str, float],
    close_dates: list[str],
    chain_forward: dict[str, dict[str, Optional[float]]],
) -> Optional[HistoryRow]:
    """
    单条 JSON snapshot → HistoryRow。

    Args:
        snapshot: 单日 JSON dict
        anchor_closes: {YYYYMMDD: close_price}
        close_dates: 按排序的交易日日期列表
        chain_forward: {YYYYMMDD: {next_1d_return: ..., ...}} 产业链前瞻收益

    Returns:
        HistoryRow，如果日期在 close 序列中找不到则返回 None
    """
    as_of_date = snapshot.get("as_of_date", "")
    date_key = _as_of_date_to_yyyymmdd(as_of_date)

    if date_key not in anchor_closes:
        return None

    industry_state = snapshot.get("industry_state", {})
    anchor_position = snapshot.get("anchor_position", {})
    group_rotation = snapshot.get("group_rotation", {})
    conclusion = snapshot.get("conclusion", {})
    signals = snapshot.get("signals", [])
    data_quality = snapshot.get("data_quality", {})

    group_medians = group_rotation.get("group_medians", {})

    # 前瞻收益：从 close 序列按交易日位置计算
    date_idx = close_dates.index(date_key)
    anchor_forwards = compute_forward_returns(date_idx, list(anchor_closes[d] for d in close_dates), FORWARD_WINDOWS)

    # 前瞻超额
    chain_fw = chain_forward.get(date_key, {})
    excess = compute_forward_excess(anchor_forwards, chain_fw, FORWARD_WINDOWS)

    return HistoryRow(
        date=date_key,
        anchor_return=anchor_position.get("anchor_return"),
        direct_peers_median=industry_state.get("direct_peers_return_median"),
        industry_chain_median=industry_state.get("industry_chain_return_median"),
        theme_pool_median=industry_state.get("theme_pool_return_median"),
        trading_watchlist_median=group_medians.get("trading_watchlist"),
        relative_strength_vs_direct=anchor_position.get("relative_strength_vs_direct_peers"),
        relative_strength_vs_industry_chain=anchor_position.get("relative_strength_vs_industry_chain"),
        relative_strength_vs_theme=anchor_position.get("relative_strength_vs_theme_pool"),
        direct_up_ratio=industry_state.get("up_ratio"),
        chain_up_ratio=industry_state.get("chain_up_ratio"),
        amount_expansion_ratio=industry_state.get("amount_expansion_ratio"),
        moneyflow_positive_ratio=industry_state.get("moneyflow_positive_ratio"),
        strongest_group=group_rotation.get("strongest_group", ""),
        weakest_group=group_rotation.get("weakest_group", ""),
        industry_beta=conclusion.get("industry_beta", "neutral"),
        anchor_alpha=conclusion.get("anchor_alpha", "neutral"),
        risk_level=conclusion.get("risk_level", "medium"),
        signal_labels=_extract_signal_labels(signals),
        signal_categories=_extract_signal_categories(signals),
        signal_pairs=_extract_signal_pairs(signals),
        data_quality_status=data_quality.get("status", "unknown"),
        next_1d_return=anchor_forwards.get("next_1d_return"),
        next_3d_return=anchor_forwards.get("next_3d_return"),
        next_5d_return=anchor_forwards.get("next_5d_return"),
        next_1d_excess_vs_chain=excess.get("next_1d_excess_vs_chain"),
        next_3d_excess_vs_chain=excess.get("next_3d_excess_vs_chain"),
        next_5d_excess_vs_chain=excess.get("next_5d_excess_vs_chain"),
    )


def build_history_rows(
    output_root: Path,
    market_data_path: Path,
    anchor_symbol: str = ANCHOR_SYMBOL,
) -> list[HistoryRow]:
    """
    主入口：读取所有快照 + 行情数据，构建汇总表。

    Args:
        output_root: data/output/ 目录
        market_data_path: data/price/ 目录（含 raw/ 和 normalized/）
        anchor_symbol: 锚定标的代码

    Returns:
        HistoryRow 列表，按日期排序
    """
    snapshots = load_all_snapshots(output_root)
    if not snapshots:
        return []

    close_dates, closes = build_trading_day_closes(market_data_path, anchor_symbol)
    anchor_closes = dict(zip(close_dates, closes))

    # 构建产业链中位数前瞻收益
    chain_medians: list[Optional[float]] = []
    date_to_chain: dict[str, Optional[float]] = {}
    for snap in snapshots:
        as_of_date = _as_of_date_to_yyyymmdd(snap.get("as_of_date", ""))
        median = snap.get("industry_state", {}).get("industry_chain_return_median")
        chain_medians.append(median)
        date_to_chain[as_of_date] = median

    chain_forwards_list = build_chain_forward_returns(chain_medians, FORWARD_WINDOWS)
    chain_forward: dict[str, dict[str, Optional[float]]] = {}
    for i, snap in enumerate(snapshots):
        as_of_date = _as_of_date_to_yyyymmdd(snap.get("as_of_date", ""))
        chain_forward[as_of_date] = chain_forwards_list[i]

    rows: list[HistoryRow] = []
    for snapshot in snapshots:
        row = flatten_snapshot(snapshot, anchor_closes, close_dates, chain_forward)
        if row is not None:
            rows.append(row)

    return rows
