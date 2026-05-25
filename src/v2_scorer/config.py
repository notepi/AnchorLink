"""
V2 评分信号权重与 Regime 乘数配置

来源：composite_signal_backtest_v2.py + analysis_framework.md 4.1 节
"""

from __future__ import annotations

# V1 买入信号（原有）
V1_BUY: dict[str, int] = {
    "excess_5d_P15-": +3,
    "excess_10d_P15-": +3,
    "outperform_streak_≤-3": +3,
    "跌但资金支撑": +2,
    "delta_excess_5d_温和回调": +2,
    "alpha_signal_count_≥3": +2,
    "path_弱+弱→中或强": +2,
    "缩量阴跌": +1,
    "trading_corr_快速上升": +1,
    "rs_vs_chain_Q2": +1,
}

# V1 卖出信号（原有）
V1_SELL: dict[str, int] = {
    "excess_5d_P85+": -3,
    "放量大涨_veto": -3,
    "outperform_streak_≥+3": -2,
    "delta_excess_5d_最快上升": -2,
    "rs_vs_chain_Q5": -2,
    "Beta骑乘组合": -2,
    "信号_放量上涨": -2,
    "excess_10d_P70-P85": -1,
    "放量大跌": -1,
    "path_强+强→强+弱": -1,
}

# V2 新增买入信号（P0 验证通过）
V2_NEW_BUY: dict[str, int] = {
    "mean_reverting+streak≤-3": +5,
    "mean_reverting+streak≤-2": +3,
    "transition+streak≤-2": +3,
    "MACD柱状图负": +1,
    "周三效应": +1,
    "LiqSweep高(假突破)": +1,
}

# V2 新增卖出信号（P0 验证通过）
V2_NEW_SELL: dict[str, int] = {
    "transition+streak≥+2": -4,
    "周五+ADX<25": -3,
    "周五效应": -2,
    "RSI超买(>70)": -2,
    "Stoch超买(K>80)": -2,
    "BB上轨触及": -2,
    "看跌FVG日": -2,
    "BOS创20日新高": -1,
}

# Regime 自适应乘数
REGIME_MULTIPLIER: dict[str, dict[str, float]] = {
    "mean_reverting": {
        "streak_buy": 1.5,
        "streak_sell": 1.3,
        "reversion_buy": 1.3,
        "trend_buy": 0.7,
    },
    "trending": {
        "streak_buy": 0.8,
        "streak_sell": 1.0,
        "reversion_buy": 0.8,
        "trend_buy": 1.2,
    },
    "transition": {
        "streak_buy": 1.3,
        "streak_sell": 1.3,
        "reversion_buy": 1.0,
        "trend_buy": 1.0,
    },
}

# Alpha 信号集合
ALPHA_SIGNALS: set[str] = {
    "资金价格背离", "主力资金拖累", "行业扩散不足", "交易观察池降温",
    "行业Beta为中性", "主题情绪强但主线池弱", "行业Beta为负",
    "情绪池强于产业链", "放量下跌",
}
