"""
虚拟 ETF / 自定义指数 — 数据质量校验

职责：
  - 唯一键校验
  - 已纳入成员 close 非空非零
  - anchor 覆盖最新交易日
  - raw 与 normalized 最新日同步
"""

import pandas as pd


def check_price_uniqueness(price_df: pd.DataFrame) -> None:
    """校验 (ts_code, trade_date) 唯一性"""
    dup = price_df.duplicated(subset=["ts_code", "trade_date"])
    if dup.any():
        dup_count = dup.sum()
        sample = price_df[dup][["ts_code", "trade_date"]].head(5).to_string()
        raise ValueError(
            f"行情数据存在 {dup_count} 条重复键 (ts_code, trade_date):\n{sample}"
        )


def check_no_null_zero_close(price_df: pd.DataFrame) -> None:
    """校验已纳入成员的估值 close 不为空且 > 0

    注意：未纳入成员（included=false）允许 close 为空，
    此函数只检查 close 列中实际存在的值。
    """
    null_count = price_df["close"].isna().sum()
    zero_count = (price_df["close"] <= 0).sum()
    issues = []
    if null_count > 0:
        issues.append(f"{null_count} 条 close 为 null")
    if zero_count > 0:
        issues.append(f"{zero_count} 条 close <= 0")
    if issues:
        raise ValueError("行情数据 close 异常: " + "; ".join(issues))


def check_anchor_covers_latest(
    price_df: pd.DataFrame,
    anchor_symbol: str,
    allow_stale: bool = False,
) -> str | None:
    """校验 anchor 覆盖最新交易日

    Args:
        price_df: normalized 行情数据
        anchor_symbol: anchor 代码
        allow_stale: 为 True 时仅输出警告，否则 raise ValueError

    Returns:
        警告字符串或 None
    """
    latest_date = price_df["trade_date"].max()
    anchor_latest = price_df[price_df["ts_code"] == anchor_symbol]["trade_date"].max()

    if pd.isna(anchor_latest) or anchor_latest < latest_date:
        msg = (
            f"Anchor {anchor_symbol} 未覆盖最新交易日: "
            f"anchor_latest={anchor_latest}, data_latest={latest_date}"
        )
        if allow_stale:
            print(f"[WARN] {msg}")
            return msg
        raise ValueError(msg)
    return None


def check_raw_normalized_sync(
    raw_df: pd.DataFrame,
    normalized_df: pd.DataFrame,
) -> str | None:
    """校验 raw 与 normalized 最新交易日同步"""
    if raw_df.empty or normalized_df.empty:
        return None

    raw_latest = raw_df["trade_date"].max()
    norm_latest = normalized_df["trade_date"].max()

    if raw_latest != norm_latest:
        msg = (
            f"raw 与 normalized 最新交易日不同步: "
            f"raw={raw_latest}, normalized={norm_latest}"
        )
        print(f"[WARN] {msg}")
        return msg
    return None


def run_all_quality_checks(
    normalized_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    anchor_symbol: str,
    allow_stale_anchor: bool = False,
) -> list[str]:
    """运行全部质量检查，返回警告列表

    Raises:
        ValueError: 严重问题（重复键、close 异常、anchor 缺失）
    """
    warnings: list[str] = []

    check_price_uniqueness(normalized_df)
    check_no_null_zero_close(normalized_df)

    w = check_anchor_covers_latest(normalized_df, anchor_symbol, allow_stale=allow_stale_anchor)
    if w:
        warnings.append(w)

    w = check_raw_normalized_sync(raw_df, normalized_df)
    if w:
        warnings.append(w)

    return warnings
