"""
滚动指标计算模块

计算 5d/10d 累计超额、连续跑赢/跑输、beta 连续性等。
"""

from typing import Optional

from src.history_analysis.models import HistoryRow, RollingMetrics


def compute_rolling_excess(
    rows: list[HistoryRow],
    window: int,
) -> list[Optional[float]]:
    """
    累计超额收益：过去 window 天 anchor_return - industry_chain_median 的求和。

    不足 window 天的前期行返回 None。
    """
    result: list[Optional[float]] = []

    for i in range(len(rows)):
        if i < window - 1:
            result.append(None)
            continue

        total = 0.0
        valid = True
        for j in range(i - window + 1, i + 1):
            anchor_ret = rows[j].anchor_return
            chain_med = rows[j].industry_chain_median
            if anchor_ret is None or chain_med is None:
                valid = False
                break
            total += anchor_ret - chain_med

        result.append(round(total, 6) if valid else None)

    return result


def compute_outperform_streak(rows: list[HistoryRow]) -> list[int]:
    """
    连续跑赢/跑输 streak。

    正数 = 连续跑赢（anchor_return > industry_chain_median）
    负数 = 连续跑输
    0 = 刚断裂或首日
    """
    result: list[int] = []

    for i in range(len(rows)):
        anchor_ret = rows[i].anchor_return
        chain_med = rows[i].industry_chain_median

        if anchor_ret is None or chain_med is None:
            result.append(0)
            continue

        if i == 0:
            result.append(1 if anchor_ret > chain_med else -1)
            continue

        prev = result[i - 1]
        if anchor_ret > chain_med:
            result.append(prev + 1 if prev > 0 else 1)
        elif anchor_ret < chain_med:
            result.append(prev - 1 if prev < 0 else -1)
        else:
            result.append(0)

    return result


def compute_beta_streak(rows: list[HistoryRow]) -> list[int]:
    """
    industry_beta 连续性 streak。

    正数 = 连续 positive，负数 = 连续 negative，0 = 刚断裂或 neutral。
    neutral 断裂 streak。
    """
    result: list[int] = []

    for i in range(len(rows)):
        beta = rows[i].industry_beta

        if beta == "neutral":
            result.append(0)
            continue

        if i == 0:
            result.append(1 if beta == "positive" else -1)
            continue

        prev = result[i - 1]
        if beta == "positive":
            result.append(prev + 1 if prev > 0 else 1)
        else:
            result.append(prev - 1 if prev < 0 else -1)

    return result


def compute_theme_vs_core_streak(rows: list[HistoryRow]) -> list[int]:
    """
    主题池 vs 核心池连续性 streak。

    正数 = theme_pool_median > direct_peers_median 连续天数
    负数 = 反之
    """
    result: list[int] = []

    for i in range(len(rows)):
        theme_med = rows[i].theme_pool_median
        direct_med = rows[i].direct_peers_median

        if theme_med is None or direct_med is None:
            result.append(0)
            continue

        if i == 0:
            result.append(1 if theme_med > direct_med else -1)
            continue

        prev = result[i - 1]
        if theme_med > direct_med:
            result.append(prev + 1 if prev > 0 else 1)
        elif theme_med < direct_med:
            result.append(prev - 1 if prev < 0 else -1)
        else:
            result.append(0)

    return result


def compute_risk_high_streak(rows: list[HistoryRow]) -> list[int]:
    """risk_level=high 连续天数"""
    result: list[int] = []

    for i in range(len(rows)):
        if rows[i].risk_level == "high":
            if i == 0:
                result.append(1)
            else:
                result.append(result[i - 1] + 1 if result[i - 1] > 0 else 1)
        else:
            result.append(0)

    return result


def build_rolling_metrics(rows: list[HistoryRow]) -> list[RollingMetrics]:
    """主入口：计算所有滚动指标"""
    if not rows:
        return []

    excess_5d = compute_rolling_excess(rows, 5)
    excess_10d = compute_rolling_excess(rows, 10)
    outperform_streak = compute_outperform_streak(rows)
    beta_streak = compute_beta_streak(rows)
    theme_vs_core_streak = compute_theme_vs_core_streak(rows)
    risk_high_streak = compute_risk_high_streak(rows)

    return [
        RollingMetrics(
            date=rows[i].date,
            excess_5d=excess_5d[i],
            excess_10d=excess_10d[i],
            outperform_streak=outperform_streak[i],
            beta_streak=beta_streak[i],
            theme_vs_core_streak=theme_vs_core_streak[i],
            risk_high_streak=risk_high_streak[i],
        )
        for i in range(len(rows))
    ]
