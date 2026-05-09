"""
前瞻收益计算模块

从 parquet 文件读取锚定标的 close 价格，
按交易日位置计算 next_1d/3d/5d_return 和 next_Nd_excess_vs_chain。

关键：使用交易日位置偏移，不是自然日偏移。
"""

from pathlib import Path
from typing import Optional

import pandas as pd


def build_trading_day_closes(
    parquet_path: Path,
    anchor_symbol: str,
) -> tuple[list[str], list[float]]:
    """
    从 parquet 读取锚定标的的交易日序列和 close 价格。

    优先读取 normalized parquet，不存在则 fallback 到 raw parquet。

    Returns:
        (dates, closes) — 两个等长列表，dates 为 YYYYMMDD 字符串，按日期排序
    """
    normalized_path = parquet_path / "normalized" / "market_data_normalized.parquet"
    raw_path = parquet_path / "raw" / "market_data.parquet"

    if normalized_path.exists():
        df = pd.read_parquet(normalized_path)
    elif raw_path.exists():
        df = pd.read_parquet(raw_path)
    else:
        raise FileNotFoundError(f"No market data parquet found in {parquet_path}")

    anchor_df = df[df["ts_code"] == anchor_symbol].copy()
    anchor_df = anchor_df.sort_values("trade_date")

    dates = anchor_df["trade_date"].dt.strftime("%Y%m%d").tolist()
    closes = anchor_df["close"].tolist()

    return dates, closes


def compute_forward_returns(
    idx: int,
    closes: list[float],
    windows: list[int],
) -> dict[str, Optional[float]]:
    """
    按交易日位置计算前瞻收益。

    Args:
        idx: 当前日期在 closes 列表中的位置
        closes: 按交易日排序的 close 价格列表
        windows: 前瞻窗口列表，如 [1, 3, 5]

    Returns:
        {"next_1d_return": ..., "next_3d_return": ..., "next_5d_return": ...}
        末尾无法计算的设为 None
    """
    result: dict[str, Optional[float]] = {}

    for w in windows:
        key = f"next_{w}d_return"
        if idx + w >= len(closes) or closes[idx] == 0:
            result[key] = None
        else:
            result[key] = closes[idx + w] / closes[idx] - 1.0
            # 转为百分点口径以匹配 snapshot 中的 anchor_return
            result[key] = round(result[key] * 100, 6)

    return result


def compute_forward_excess(
    anchor_forwards: dict[str, Optional[float]],
    chain_forwards: dict[str, Optional[float]],
    windows: list[int],
) -> dict[str, Optional[float]]:
    """
    计算前瞻超额收益 = 锚定前瞻收益 - 产业链前瞻收益。

    产业链前瞻收益从 HistoryRow 的 industry_chain_median 按交易日位置 shift 得到。

    Args:
        anchor_forwards: 锚定标的的前瞻收益
        chain_forwards: 产业链中位数的前瞻收益
        windows: 前瞻窗口列表

    Returns:
        {"next_1d_excess_vs_chain": ..., "next_3d_excess_vs_chain": ..., ...}
    """
    result: dict[str, Optional[float]] = {}

    for w in windows:
        key = f"next_{w}d_excess_vs_chain"
        anchor_val = anchor_forwards.get(f"next_{w}d_return")
        chain_val = chain_forwards.get(f"next_{w}d_return")

        if anchor_val is not None and chain_val is not None:
            result[key] = round(anchor_val - chain_val, 6)
        else:
            result[key] = None

    return result


def build_chain_forward_returns(
    chain_medians: list[Optional[float]],
    windows: list[int],
) -> list[dict[str, Optional[float]]]:
    """
    计算产业链中位数的前瞻收益。

    口径说明：产业链前瞻收益取"未来第 N 天的 industry_chain_median"，
    不是复利累计。1 日窗口精确，3/5 日窗口是近似——
    假设产业链 daily median 可简单取未来某一天值而非累计复合。
    这是因为产业链 median 不是一个可交易指数，没有 close 可算复合收益。

    产业链中位数本身是百分点口径（如 0.99 表示 0.99%），
    但前瞻收益需要从 level 变化计算。由于中位数已经是百分比变化，
    前瞻收益 = chain_median[T+N]（近似，因为中位数不可复合）。

    这个近似在 1-5 天窗口内误差可接受。

    Args:
        chain_medians: 按交易日排序的产业链中位数列表
        windows: 前瞻窗口列表

    Returns:
        每个日期一个 dict，格式同 compute_forward_returns
    """
    results: list[dict[str, Optional[float]]] = []

    for idx in range(len(chain_medians)):
        forwards: dict[str, Optional[float]] = {}
        for w in windows:
            key = f"next_{w}d_return"
            future_idx = idx + w
            if future_idx >= len(chain_medians):
                forwards[key] = None
            else:
                forwards[key] = chain_medians[future_idx]
        results.append(forwards)

    return results
