#!/usr/bin/env python
"""
铂力特 Backtrader 回测脚本
测试多种策略的回测效果
"""

import pandas as pd
import numpy as np
import backtrader as bt
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 数据加载
# ============================================================

def load_blt_data():
    """加载铂力特数据"""
    price_df = pd.read_parquet('data/price/normalized/market_data_normalized.parquet')
    price_df['trade_date'] = pd.to_datetime(price_df['trade_date'])
    blt = price_df[price_df['ts_code'] == '688333.SH'].copy()
    blt = blt.sort_values('trade_date').reset_index(drop=True)

    # 设置索引
    blt.set_index('trade_date', inplace=True)

    return blt


class PandasData(bt.feeds.PandasData):
    """自定义 Pandas 数据源"""
    params = (
        ('datetime', None),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'vol'),
        ('openinterest', None),
    )

# ============================================================
# 策略定义
# ============================================================

class BaselineStrategy(bt.Strategy):
    """基线策略：买入持有"""
    params = ()

    def __init__(self):
        self.buy_price = None
        self.buy_comm = None

    def next(self):
        if not self.position:
            self.buy()


class RSIStrategy(bt.Strategy):
    """RSI 策略"""
    params = (
        ('rsi_period', 14),
        ('rsi_oversold', 30),
        ('rsi_overbought', 70),
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_period)

    def next(self):
        if not self.position:
            if self.rsi < self.p.rsi_oversold:
                self.buy()
        else:
            if self.rsi > self.p.rsi_overbought:
                self.sell()


class MACDStrategy(bt.Strategy):
    """MACD 策略"""
    params = (
        ('fast_period', 12),
        ('slow_period', 26),
        ('signal_period', 9),
    )

    def __init__(self):
        self.macd = bt.indicators.MACD(
            self.data.close,
            period_me1=self.p.fast_period,
            period_me2=self.p.slow_period,
            period_signal=self.p.signal_period
        )
        self.crossover = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)

    def next(self):
        if not self.position:
            if self.crossover > 0:  # 金叉
                self.buy()
        else:
            if self.crossover < 0:  # 死叉
                self.sell()


class BollingerStrategy(bt.Strategy):
    """布林带策略"""
    params = (
        ('period', 20),
        ('devfactor', 2.0),
    )

    def __init__(self):
        self.boll = bt.indicators.BollingerBands(
            self.data.close,
            period=self.p.period,
            devfactor=self.p.devfactor
        )

    def next(self):
        if not self.position:
            if self.data.close < self.boll.lines.bot:
                self.buy()  # 价格跌破下轨买入
        else:
            if self.data.close > self.boll.lines.top:
                self.sell()  # 价格突破上轨卖出


class MeanReversionStrategy(bt.Strategy):
    """均值回归策略"""
    params = (
        ('period', 20),
        ('buy_threshold', -0.05),  # 低于均线5%买入
        ('sell_threshold', 0.05),  # 高于均线5%卖出
        ('stop_loss', 0.05),       # 5%止损
        ('take_profit', 0.10),     # 10%止盈
    )

    def __init__(self):
        self.sma = bt.indicators.SMA(self.data.close, period=self.p.period)
        self.deviation = (self.data.close - self.sma) / self.sma
        self.buy_price = None

    def next(self):
        if not self.position:
            if self.deviation < self.p.buy_threshold:
                self.buy()
                self.buy_price = self.data.close[0]
        else:
            # 止损
            if self.data.close[0] < self.buy_price * (1 - self.p.stop_loss):
                self.sell()
            # 止盈
            elif self.data.close[0] > self.buy_price * (1 + self.p.take_profit):
                self.sell()
            # 信号反转
            elif self.deviation > self.p.sell_threshold:
                self.sell()


class CombinedSignalStrategy(bt.Strategy):
    """组合信号策略"""
    params = (
        ('rsi_oversold', 35),
        ('rsi_overbought', 65),
        ('buy_score_threshold', 2),
        ('sell_score_threshold', -2),
        ('stop_loss', 0.05),
        ('take_profit', 0.10),
    )

    def __init__(self):
        # 技术指标
        self.rsi = bt.indicators.RSI(self.data.close, period=14)
        self.macd = bt.indicators.MACD(self.data.close)
        self.boll = bt.indicators.BollingerBands(self.data.close, period=20)

        # 信号
        self.macd_cross = bt.indicators.CrossOver(self.macd.macd, self.macd.signal)
        self.buy_price = None

    def next(self):
        # 计算信号得分
        score = 0

        # RSI 信号
        if self.rsi < self.p.rsi_oversold:
            score += 1
        elif self.rsi > self.p.rsi_overbought:
            score -= 1

        # MACD 信号
        if self.macd_cross > 0:
            score += 1
        elif self.macd_cross < 0:
            score -= 1

        # 布林带信号
        if self.data.close < self.boll.lines.bot:
            score += 1
        elif self.data.close > self.boll.lines.top:
            score -= 1

        # 交易逻辑
        if not self.position:
            if score >= self.p.buy_score_threshold:
                self.buy()
                self.buy_price = self.data.close[0]
        else:
            # 止损
            if self.data.close[0] < self.buy_price * (1 - self.p.stop_loss):
                self.sell()
            # 止盈
            elif self.data.close[0] > self.buy_price * (1 + self.p.take_profit):
                self.sell()
            # 信号反转
            elif score <= self.p.sell_score_threshold:
                self.sell()


# ============================================================
# 回测引擎
# ============================================================

def run_backtest(data_feed, strategy_class, strategy_name, cash=100000):
    """运行单个策略回测"""
    cerebro = bt.Cerebro()
    cerebro.addstrategy(strategy_class)
    cerebro.adddata(data_feed)
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=0.001)  # 0.1% 手续费

    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

    # 运行
    initial_value = cerebro.broker.getvalue()
    results = cerebro.run()
    strat = results[0]
    final_value = cerebro.broker.getvalue()

    # 提取结果
    sharpe = strat.analyzers.sharpe.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    returns = strat.analyzers.returns.get_analysis()
    trades = strat.analyzers.trades.get_analysis()

    return {
        'strategy': strategy_name,
        'initial_value': initial_value,
        'final_value': final_value,
        'total_return': (final_value - initial_value) / initial_value * 100,
        'sharpe_ratio': sharpe.get('sharperatio', 0),
        'max_drawdown': drawdown.get('max', {}).get('drawdown', 0),
        'total_trades': trades.get('total', {}).get('total', 0),
        'won_trades': trades.get('won', {}).get('total', 0),
        'lost_trades': trades.get('lost', {}).get('total', 0),
    }


def run_all_strategies():
    """运行所有策略对比"""
    # 加载数据
    df = load_blt_data()

    # 创建数据源
    data = PandasData(dataname=df)

    # 策略列表
    strategies = [
        (BaselineStrategy, '买入持有'),
        (RSIStrategy, 'RSI策略'),
        (MACDStrategy, 'MACD策略'),
        (BollingerStrategy, '布林带策略'),
        (MeanReversionStrategy, '均值回归策略'),
        (CombinedSignalStrategy, '组合信号策略'),
    ]

    # 运行所有策略
    results = []
    for strategy_class, strategy_name in strategies:
        print(f"[INFO] 回测: {strategy_name}...")
        try:
            result = run_backtest(data, strategy_class, strategy_name)
            results.append(result)
        except Exception as e:
            print(f"[WARN] {strategy_name} 回测失败: {e}")
            continue

    # 整理结果
    results_df = pd.DataFrame(results)

    return results_df


# ============================================================
# 主函数
# ============================================================

def main():
    print("[INFO] 开始 Backtrader 回测...")

    # 运行所有策略
    results_df = run_all_strategies()

    # 打印结果
    print("\n" + "="*60)
    print("回测结果对比")
    print("="*60)

    if len(results_df) > 0:
        # 格式化输出
        display_cols = ['strategy', 'total_return', 'sharpe_ratio', 'max_drawdown', 'total_trades', 'won_trades', 'lost_trades']
        print(results_df[display_cols].to_string(index=False))

        # 计算胜率
        results_df['win_rate'] = results_df['won_trades'] / (results_df['won_trades'] + results_df['lost_trades']) * 100
        results_df['win_rate'] = results_df['win_rate'].fillna(0)

        print("\n" + "="*60)
        print("胜率对比")
        print("="*60)
        print(results_df[['strategy', 'win_rate', 'total_trades']].to_string(index=False))

        # 保存结果
        results_df.to_csv('data/output/backtest_strategy_comparison.csv', index=False)
        print("\n[OK] 结果已保存到 data/output/backtest_strategy_comparison.csv")

        # 生成报告
        best_strategy = results_df.loc[results_df['total_return'].idxmax()]
        best_sharpe = results_df.loc[results_df['sharpe_ratio'].idxmax()] if results_df['sharpe_ratio'].notna().any() else None

        # 格式化 sharpe
        best_sharpe_name = best_sharpe['strategy'] if best_sharpe is not None else 'N/A'
        best_sharpe_value = f"{best_sharpe['sharpe_ratio']:.2f}" if best_sharpe is not None and best_sharpe['sharpe_ratio'] is not None else 'N/A'

        report = f"""# Backtrader 回测报告

## 策略对比

{results_df.to_string(index=False)}

## 最佳策略

- **收益最高**: {best_strategy['strategy']} ({best_strategy['total_return']:.2f}%)
- **Sharpe最高**: {best_sharpe_name} ({best_sharpe_value})

## 结论

1. 买入持有策略作为基线
2. 均值回归策略适合铂力特的反转特性
3. 组合信号策略可以综合多个指标的优势

## 下一步

1. 参数优化
2. 风险管理优化
3. 加入更多因子
"""

        with open('docs/backtest-report.md', 'w') as f:
            f.write(report)

        print("[OK] 报告已保存到 docs/backtest-report.md")

    else:
        print("[WARN] 没有成功运行的策略")


if __name__ == '__main__':
    main()
