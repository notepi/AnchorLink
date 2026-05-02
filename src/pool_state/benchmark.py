"""
池子指标计算函数

职责：
  - 计算 median_return, mean_return, up_ratio
  - 计算 volume_multiplier（相对历史均值）
  - 计算 fund_positive_ratio
  - 计算 strong_count, weak_count

所有函数只做计算，不做数据加载
"""

from typing import Optional
import pandas as pd

from src.pool_state.models import MemberData


def calculate_median_return(member_data: list[MemberData]) -> Optional[float]:
    """
    计算中位数涨跌幅

    Args:
        member_data: 有效成员数据列表

    Returns:
        中位数涨跌幅（%），无有效数据时返回 None
    """
    returns = [m.pct_chg for m in member_data if m.pct_chg is not None]

    if not returns:
        return None

    # 使用 pandas 中位数计算（处理偶数个数的中间值）
    return float(pd.Series(returns).median())


def calculate_mean_return(member_data: list[MemberData]) -> Optional[float]:
    """
    计算平均涨跌幅

    Args:
        member_data: 有效成员数据列表

    Returns:
        平均涨跌幅（%），无有效数据时返回 None
    """
    returns = [m.pct_chg for m in member_data if m.pct_chg is not None]

    if not returns:
        return None

    return sum(returns) / len(returns)


def calculate_up_ratio(member_data: list[MemberData]) -> Optional[float]:
    """
    计算上涨比例

    Args:
        member_data: 有效成员数据列表

    Returns:
        上涨比例（0-1），无有效数据时返回 None

    Note:
        涨跌幅 > 0 视为上涨，涨跌幅 = 0 视为平盘（不计入上涨）
    """
    returns = [m.pct_chg for m in member_data if m.pct_chg is not None]

    if not returns:
        return None

    up_count = len([r for r in returns if r > 0])
    return up_count / len(returns)


def calculate_volume_multiplier(
    member_data: list[MemberData],
    market_data: pd.DataFrame,
    lookback_days: int = 20,
) -> Optional[float]:
    """
    计算成交额放大倍数（相对历史均值）

    Args:
        member_data: 有效成员数据列表
        market_data: 行情数据（用于计算历史均值）
        lookback_days: 回溯天数

    Returns:
        放大倍数，无有效数据时返回 None

    Note:
        计算口径：当日总成交额 / 成员历史平均成交额之和
        返回值 > 1 表示放量，< 1 表示缩量
    """
    # 获取当日有成交额的成员
    valid_members = [m for m in member_data if m.amount is not None and m.amount > 0]

    if not valid_members:
        return None

    # 计算当日总成交额
    today_amount = sum(m.amount for m in valid_members)

    if today_amount == 0:
        return None

    # 计算历史平均成交额
    trade_date_dt = pd.to_datetime(valid_members[0].trade_date, format="%Y%m%d")
    start_date_dt = trade_date_dt - pd.Timedelta(days=lookback_days)

    # 过滤历史数据（不含当日）
    history_data = market_data[
        (market_data["trade_date"] >= start_date_dt) &
        (market_data["trade_date"] < trade_date_dt)
    ]

    if history_data.empty:
        return None

    # 计算每个成员的历史平均，再汇总
    member_symbols = [m.symbol for m in valid_members]

    history_amounts = []
    for symbol in member_symbols:
        symbol_history = history_data[history_data["ts_code"] == symbol]
        if not symbol_history.empty and "amount" in symbol_history.columns:
            avg_amount = symbol_history["amount"].mean()
            if avg_amount > 0:
                history_amounts.append(avg_amount)

    if not history_amounts:
        return None

    history_avg = sum(history_amounts)

    if history_avg == 0:
        return None

    return today_amount / history_avg


def calculate_fund_positive_ratio(member_data: list[MemberData]) -> Optional[float]:
    """
    计算资金净流入为正比例

    Args:
        member_data: 有效成员数据列表

    Returns:
        资金净流入为正比例（0-1），无资金数据时返回 None

    Note:
        只统计有资金数据的成员，net_mf_amount > 0 视为正向
    """
    fund_data = [m for m in member_data if m.net_mf_amount is not None]

    if not fund_data:
        return None

    positive_count = len([m for m in fund_data if m.net_mf_amount > 0])
    return positive_count / len(fund_data)


def calculate_strong_weak_count(
    member_data: list[MemberData],
    strong_threshold: float = 3.0,
    weak_threshold: float = -3.0,
) -> tuple[int, int]:
    """
    计算强势股和弱势股数量

    Args:
        member_data: 有效成员数据列表
        strong_threshold: 强势阈值（涨幅 > 此值为强势）
        weak_threshold: 弱势阈值（涨幅 < 此值为弱势）

    Returns:
        (强势股数量, 弱势股数量)

    Note:
        默认阈值：涨跌幅 > 3% 为强势，涨跌幅 < -3% 为弱势
    """
    returns = [m.pct_chg for m in member_data if m.pct_chg is not None]

    strong_count = len([r for r in returns if r > strong_threshold])
    weak_count = len([r for r in returns if r < weak_threshold])

    return strong_count, weak_count