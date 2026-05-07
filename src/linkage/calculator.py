"""
日线股价联动分析。

计算 Anchor 与各池成员的 5/10/20 日相关性、beta 和方向一致率。
"""

from typing import Optional

import pandas as pd

from src.config.loader import PoolRegistry, Membership
from src.linkage.models import LinkageAnalysis, LinkageMember, PoolLinkage


DEFAULT_WINDOWS = [5, 10, 20]
MIN_OBSERVATIONS = 3


def calculate_daily_linkage(
    registry: PoolRegistry,
    market_data: pd.DataFrame,
    trade_date: str,
    windows: Optional[list[int]] = None,
) -> LinkageAnalysis:
    """
    计算日线联动分析。

    Args:
        registry: 股票池配置
        market_data: 标准化日线行情，需包含 ts_code/trade_date/close
        trade_date: 分析日期 YYYYMMDD
        windows: 回看窗口，默认 [5, 10, 20]

    Returns:
        LinkageAnalysis
    """
    windows = windows or DEFAULT_WINDOWS
    anchor_symbol = registry.get_anchor().symbol

    prepared = _prepare_returns(market_data, trade_date)
    anchor_returns = prepared[prepared["ts_code"] == anchor_symbol][["trade_date", "return"]]

    if anchor_returns.empty:
        return LinkageAnalysis(
            trade_date=trade_date,
            anchor_symbol=anchor_symbol,
            status="insufficient_data",
            windows=windows,
            partial_reason=f"anchor return series missing: {anchor_symbol}",
        )

    pool_results = {}
    for universe in registry.get_all_universes():
        memberships = [
            m
            for m in registry.get_members(universe.universe_id)
            if m.include_in_report and m.symbol != anchor_symbol
        ]
        pool_results[universe.universe_id] = _calculate_pool_linkage(
            registry,
            prepared,
            anchor_returns,
            universe.universe_id,
            memberships,
            windows,
        )

    statuses = [pool.status for pool in pool_results.values()]
    if statuses and all(status == "insufficient_data" for status in statuses):
        status = "insufficient_data"
    elif any(status != "ok" for status in statuses):
        status = "partial"
    else:
        status = "ok"

    return LinkageAnalysis(
        trade_date=trade_date,
        anchor_symbol=anchor_symbol,
        status=status,
        windows=windows,
        pools=pool_results,
    )


def _prepare_returns(market_data: pd.DataFrame, trade_date: str) -> pd.DataFrame:
    df = market_data.copy()
    if "trade_date" not in df.columns or "ts_code" not in df.columns or "close" not in df.columns:
        return pd.DataFrame(columns=["ts_code", "trade_date", "return"])

    if df["trade_date"].dtype.kind != "M":
        df["trade_date"] = pd.to_datetime(df["trade_date"])

    end_date = pd.to_datetime(trade_date, format="%Y%m%d")
    df = df[df["trade_date"] <= end_date].sort_values(["ts_code", "trade_date"])
    df["return"] = df.groupby("ts_code")["close"].pct_change() * 100
    return df[["ts_code", "trade_date", "return"]].dropna(subset=["return"])


def _calculate_pool_linkage(
    registry: PoolRegistry,
    returns_df: pd.DataFrame,
    anchor_returns: pd.DataFrame,
    universe_id: str,
    memberships: list[Membership],
    windows: list[int],
) -> PoolLinkage:
    members = []

    for membership in memberships:
        instrument = registry.get_instrument(membership.symbol)
        member_returns = returns_df[returns_df["ts_code"] == membership.symbol][["trade_date", "return"]]
        joined = anchor_returns.merge(
            member_returns,
            on="trade_date",
            how="inner",
            suffixes=("_anchor", "_member"),
        ).sort_values("trade_date")

        metrics = _calculate_member_metrics(joined, windows)
        members.append(LinkageMember(
            universe_id=universe_id,
            symbol=membership.symbol,
            name=instrument.name if instrument else membership.symbol,
            role=membership.role,
            relevance=membership.relevance,
            weight=membership.weight,
            observations=len(joined),
            **metrics,
        ))

    valid_members = [m for m in members if m.data_status == "ok"]
    partial_members = [m for m in members if m.data_status == "partial"]

    if valid_members:
        status = "ok" if len(valid_members) == len(members) else "partial"
        partial_reason = None if status == "ok" else "some members have short return windows"
    elif partial_members:
        status = "partial"
        partial_reason = "only short-window linkage metrics available"
    else:
        status = "insufficient_data"
        partial_reason = "no member has enough overlapping return observations"

    top_members = sorted(
        [m for m in members if m.corr_20d is not None],
        key=lambda m: (
            m.corr_20d if m.corr_20d is not None else -2.0,
            m.direction_consistency_20d if m.direction_consistency_20d is not None else 0.0,
        ),
        reverse=True,
    )[:3]

    return PoolLinkage(
        universe_id=universe_id,
        status=status,
        members=members,
        top_members=top_members,
        avg_corr_20d=_mean([m.corr_20d for m in members]),
        avg_beta_20d=_mean([m.beta_20d for m in members]),
        avg_direction_consistency_20d=_mean([m.direction_consistency_20d for m in members]),
        partial_reason=partial_reason,
    )


def _calculate_member_metrics(joined: pd.DataFrame, windows: list[int]) -> dict:
    metrics = {}
    available_windows = 0

    for window in windows:
        subset = joined.tail(window)
        suffix = f"{window}d"

        corr = None
        beta = None
        direction_consistency = None

        if len(subset) >= max(MIN_OBSERVATIONS, window):
            corr = subset["return_anchor"].corr(subset["return_member"])
            anchor_var = subset["return_anchor"].var()
            if anchor_var and pd.notna(anchor_var):
                beta = subset["return_member"].cov(subset["return_anchor"]) / anchor_var
            direction_consistency = (
                (subset["return_anchor"] * subset["return_member"]) > 0
            ).sum() / len(subset)
            available_windows += 1

        metrics[f"corr_{suffix}"] = _clean_float(corr)
        metrics[f"beta_{suffix}"] = _clean_float(beta)
        metrics[f"direction_consistency_{suffix}"] = _clean_float(direction_consistency)

    if available_windows == len(windows):
        metrics["data_status"] = "ok"
        metrics["partial_reason"] = None
    elif available_windows > 0:
        metrics["data_status"] = "partial"
        metrics["partial_reason"] = "not enough observations for all windows"
    else:
        metrics["data_status"] = "insufficient_data"
        metrics["partial_reason"] = "not enough overlapping return observations"

    return metrics


def _mean(values: list[Optional[float]]) -> Optional[float]:
    clean_values = [v for v in values if v is not None and pd.notna(v)]
    if not clean_values:
        return None
    return float(sum(clean_values) / len(clean_values))


def _clean_float(value) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    return float(value)
