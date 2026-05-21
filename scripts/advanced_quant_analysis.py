#!/usr/bin/env python
"""
铂力特量化分析脚本
包含：TA-Lib 技术指标、因子 IC 分析、Backtrader 回测
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import spearmanr
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 1. 数据加载
# ============================================================

def load_data():
    """加载所有数据"""
    # 行情数据
    price_df = pd.read_parquet('data/price/normalized/market_data_normalized.parquet')
    price_df['trade_date'] = pd.to_datetime(price_df['trade_date'])
    price_df = price_df.sort_values('trade_date')

    # 铂力特数据
    blt = price_df[price_df['ts_code'] == '688333.SH'].copy()
    blt = blt.sort_values('trade_date').reset_index(drop=True)

    # 历史汇总数据
    history_df = pd.read_csv('data/output/history_summary.csv')
    history_df['date'] = pd.to_datetime(history_df['date'], format='%Y%m%d')

    return blt, history_df

# ============================================================
# 2. TA-Lib 技术指标计算
# ============================================================

def calculate_tech_indicators(df):
    """使用 TA-Lib 计算技术指标"""
    try:
        import talib as ta
    except ImportError:
        print("[WARN] TA-Lib 未安装，使用手动计算")
        return calculate_tech_indicators_manual(df)

    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    volume = df['vol'].values

    indicators = pd.DataFrame(index=df.index)

    # 趋势指标
    indicators['MA5'] = ta.MA(close, timeperiod=5)
    indicators['MA10'] = ta.MA(close, timeperiod=10)
    indicators['MA20'] = ta.MA(close, timeperiod=20)
    indicators['EMA12'] = ta.EMA(close, timeperiod=12)
    indicators['EMA26'] = ta.EMA(close, timeperiod=26)

    macd, macdsignal, macdhist = ta.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    indicators['MACD'] = macd
    indicators['MACD_signal'] = macdsignal
    indicators['MACD_hist'] = macdhist

    indicators['ADX'] = ta.ADX(high, low, close, timeperiod=14)

    # 动量指标
    indicators['RSI'] = ta.RSI(close, timeperiod=14)

    slowk, slowd = ta.STOCH(high, low, close, fastk_period=9, slowk_period=3, slowd_period=3)
    indicators['KDJ_K'] = slowk
    indicators['KDJ_D'] = slowd

    indicators['CCI'] = ta.CCI(high, low, close, timeperiod=14)
    indicators['MOM'] = ta.MOM(close, timeperiod=10)
    indicators['ROC'] = ta.ROC(close, timeperiod=10)

    # 波动率指标
    indicators['ATR'] = ta.ATR(high, low, close, timeperiod=14)
    indicators['NATR'] = ta.NATR(high, low, close, timeperiod=14)

    upper, middle, lower = ta.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
    indicators['BB_upper'] = upper
    indicators['BB_middle'] = middle
    indicators['BB_lower'] = lower
    indicators['BB_width'] = (upper - lower) / middle
    indicators['BB_position'] = (close - lower) / (upper - lower)  # 布林带位置

    # 成交量指标
    indicators['OBV'] = ta.OBV(close, volume)
    indicators['AD'] = ta.AD(high, low, close, volume)

    # 价格位置
    indicators['price_vs_ma5'] = close / indicators['MA5'] - 1
    indicators['price_vs_ma10'] = close / indicators['MA10'] - 1
    indicators['price_vs_ma20'] = close / indicators['MA20'] - 1

    return indicators


def calculate_tech_indicators_manual(df):
    """手动计算技术指标（不依赖 TA-Lib）"""
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['vol']

    indicators = pd.DataFrame(index=df.index)

    # 移动平均
    indicators['MA5'] = close.rolling(5).mean()
    indicators['MA10'] = close.rolling(10).mean()
    indicators['MA20'] = close.rolling(20).mean()

    # EMA
    indicators['EMA12'] = close.ewm(span=12).mean()
    indicators['EMA26'] = close.ewm(span=26).mean()

    # MACD
    indicators['MACD'] = indicators['EMA12'] - indicators['EMA26']
    indicators['MACD_signal'] = indicators['MACD'].ewm(span=9).mean()
    indicators['MACD_hist'] = indicators['MACD'] - indicators['MACD_signal']

    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    indicators['RSI'] = 100 - (100 / (1 + rs))

    # KDJ
    lowest_low = low.rolling(9).min()
    highest_high = high.rolling(9).max()
    rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
    indicators['KDJ_K'] = rsv.ewm(alpha=1/3).mean()
    indicators['KDJ_D'] = indicators['KDJ_K'].ewm(alpha=1/3).mean()

    # ATR
    tr = pd.concat([
        high - low,
        abs(high - close.shift(1)),
        abs(low - close.shift(1))
    ], axis=1).max(axis=1)
    indicators['ATR'] = tr.rolling(14).mean()

    # 布林带
    indicators['BB_middle'] = close.rolling(20).mean()
    indicators['BB_std'] = close.rolling(20).std()
    indicators['BB_upper'] = indicators['BB_middle'] + 2 * indicators['BB_std']
    indicators['BB_lower'] = indicators['BB_middle'] - 2 * indicators['BB_std']
    indicators['BB_width'] = (indicators['BB_upper'] - indicators['BB_lower']) / indicators['BB_middle']
    indicators['BB_position'] = (close - indicators['BB_lower']) / (indicators['BB_upper'] - indicators['BB_lower'])

    # OBV
    indicators['OBV'] = (np.sign(close.diff()) * volume).cumsum()

    # 动量
    indicators['MOM'] = close.diff(10)
    indicators['ROC'] = close.pct_change(10) * 100

    # 价格位置
    indicators['price_vs_ma5'] = close / indicators['MA5'] - 1
    indicators['price_vs_ma10'] = close / indicators['MA10'] - 1
    indicators['price_vs_ma20'] = close / indicators['MA20'] - 1

    return indicators


def generate_ta_signals(indicators, df):
    """生成技术指标交易信号"""
    signals = pd.DataFrame(index=indicators.index)

    # MACD 金叉死叉
    signals['MACD_cross'] = 0
    macd_cross = (indicators['MACD'] > indicators['MACD_signal']).astype(int)
    signals['MACD_cross'] = macd_cross.diff()
    signals.loc[signals['MACD_cross'] > 0, 'MACD_cross'] = 1   # 金叉
    signals.loc[signals['MACD_cross'] < 0, 'MACD_cross'] = -1  # 死叉
    signals.loc[signals['MACD_cross'] == 0, 'MACD_cross'] = 0

    # RSI 超买超卖
    signals['RSI_signal'] = 0
    signals.loc[indicators['RSI'] < 30, 'RSI_signal'] = 1   # 超卖
    signals.loc[indicators['RSI'] > 70, 'RSI_signal'] = -1  # 超买

    # KDJ 金叉死叉
    signals['KDJ_cross'] = 0
    kdj_cross = (indicators['KDJ_K'] > indicators['KDJ_D']).astype(int)
    signals['KDJ_cross'] = kdj_cross.diff()
    signals.loc[signals['KDJ_cross'] > 0, 'KDJ_cross'] = 1
    signals.loc[signals['KDJ_cross'] < 0, 'KDJ_cross'] = -1
    signals.loc[signals['KDJ_cross'] == 0, 'KDJ_cross'] = 0

    # 布林带位置
    signals['BB_signal'] = 0
    signals.loc[indicators['BB_position'] < 0.2, 'BB_signal'] = 1   # 接近下轨
    signals.loc[indicators['BB_position'] > 0.8, 'BB_signal'] = -1  # 接近上轨

    # 价格与均线关系
    signals['MA_signal'] = 0
    signals.loc[indicators['price_vs_ma20'] < -0.05, 'MA_signal'] = 1   # 低于 MA20 5%
    signals.loc[indicators['price_vs_ma20'] > 0.05, 'MA_signal'] = -1  # 高于 MA20 5%

    return signals

# ============================================================
# 3. 因子 IC 分析
# ============================================================

def calculate_ic(factor_values, return_values):
    """计算因子 IC"""
    aligned = pd.concat([factor_values, return_values], axis=1).dropna()
    if len(aligned) < 10:
        return np.nan, np.nan
    ic, p_value = spearmanr(aligned.iloc[:, 0], aligned.iloc[:, 1])
    return ic, p_value


def analyze_factor_ic(df, factor_cols, return_col='next_1d_return'):
    """分析所有因子的 IC"""
    results = []

    for col in factor_cols:
        if col not in df.columns:
            continue

        # 计算 IC
        ic, p_value = calculate_ic(df[col], df[return_col])

        # 计算 IC_IR（滚动 IC 的均值/标准差）
        rolling_ics = []
        for i in range(20, len(df)):
            ic_window, _ = calculate_ic(
                df[col].iloc[i-20:i],
                df[return_col].iloc[i-20:i]
            )
            if not np.isnan(ic_window):
                rolling_ics.append(ic_window)

        ic_mean = np.mean(rolling_ics) if rolling_ics else np.nan
        ic_std = np.std(rolling_ics) if len(rolling_ics) > 1 else np.nan
        ic_ir = ic_mean / ic_std if ic_std and ic_std > 0 else np.nan

        results.append({
            'factor': col,
            'IC': ic,
            'p_value': p_value,
            'significant': p_value < 0.05 if not np.isnan(p_value) else False,
            'IC_mean': ic_mean,
            'IC_std': ic_std,
            'IC_IR': ic_ir
        })

    return pd.DataFrame(results).sort_values('IC', key=abs, ascending=False)


def quantile_analysis(df, factor_col, return_col='next_1d_return', n_quantiles=5):
    """因子分组测试"""
    data = df[[factor_col, return_col]].dropna()

    if len(data) < n_quantiles * 3:
        return None

    # 分组
    data['quantile'] = pd.qcut(data[factor_col], n_quantiles, labels=False, duplicates='drop') + 1

    # 计算各组收益
    quantile_stats = data.groupby('quantile')[return_col].agg(['mean', 'std', 'count'])
    quantile_stats['win_rate'] = data.groupby('quantile')[return_col].apply(lambda x: (x > 0).mean())

    # t 检验
    if 5 in data['quantile'].values and 1 in data['quantile'].values:
        q5 = data[data['quantile'] == 5][return_col]
        q1 = data[data['quantile'] == 1][return_col]
        t_stat, p_value = stats.ttest_ind(q5, q1)
        spread = q5.mean() - q1.mean()
    else:
        t_stat, p_value, spread = np.nan, np.nan, np.nan

    return {
        'quantile_stats': quantile_stats,
        'spread': spread,
        't_stat': t_stat,
        'p_value': p_value
    }

# ============================================================
# 4. 自相关分析
# ============================================================

def analyze_autocorrelation(returns, max_lag=20):
    """分析收益率自相关"""
    from statsmodels.stats.diagnostic import acorr_ljungbox
    import statsmodels.api as sm

    # 清理数据
    returns = returns.dropna()

    # Ljung-Box 检验
    lb_test = acorr_ljungbox(returns, lags=max_lag, return_df=True)

    # ACF
    acf_values = sm.tsa.acf(returns, nlags=max_lag)

    # PACF
    pacf_values = sm.tsa.pacf(returns, nlags=max_lag)

    # 判断动量/反转
    effect_type = 'momentum' if acf_values[1] > 0 else 'reversal'

    return {
        'lb_test': lb_test,
        'acf': acf_values,
        'pacf': pacf_values,
        'effect_type': effect_type,
        'has_autocorr': (lb_test['lb_pvalue'] < 0.05).any()
    }

# ============================================================
# 5. 策略回测（简化版）
# ============================================================

def simple_backtest(signals, returns, initial_capital=100000):
    """简单回测"""
    capital = initial_capital
    position = 0
    trades = []
    equity_curve = []

    for i, (signal, ret) in enumerate(zip(signals, returns)):
        # 交易逻辑
        if signal == 1 and position == 0:  # 买入
            position = capital / 100  # 假设每次买入固定股数
            entry_price = 100  # 假设基准价格
            trades.append({'type': 'buy', 'idx': i})
        elif signal == -1 and position > 0:  # 卖出
            trades.append({'type': 'sell', 'idx': i})
            position = 0

        # 更新净值
        daily_pnl = position * ret / 100 * entry_price if position > 0 else 0
        capital += daily_pnl
        equity_curve.append(capital)

    equity_curve = pd.Series(equity_curve)

    # 计算指标
    returns_series = equity_curve.pct_change().dropna()
    sharpe = returns_series.mean() / returns_series.std() * np.sqrt(252) if len(returns_series) > 0 and returns_series.std() > 0 else 0
    max_dd = (equity_curve.cummax() - equity_curve).max() / equity_curve.cummax().max() if len(equity_curve) > 0 else 0

    return {
        'final_capital': capital,
        'total_return': (capital - initial_capital) / initial_capital,
        'sharpe': sharpe,
        'max_drawdown': max_dd,
        'num_trades': len(trades),
        'equity_curve': equity_curve
    }

# ============================================================
# 6. 主函数
# ============================================================

def main():
    print("[INFO] 开始量化分析...")

    # 1. 加载数据
    print("\n[1/6] 加载数据...")
    blt, history_df = load_data()
    print(f"  铂力特行情数据: {len(blt)} 天")
    print(f"  历史汇总数据: {len(history_df)} 天")

    # 2. 计算技术指标
    print("\n[2/6] 计算技术指标...")
    indicators = calculate_tech_indicators(blt)
    indicators['trade_date'] = blt['trade_date'].values
    print(f"  计算了 {len(indicators.columns) - 1} 个技术指标")

    # 3. 生成信号
    print("\n[3/6] 生成交易信号...")
    ta_signals = generate_ta_signals(indicators, blt)
    ta_signals['trade_date'] = blt['trade_date'].values
    print(f"  生成了 {len(ta_signals.columns) - 1} 种信号")

    # 4. 合并数据
    print("\n[4/6] 合并数据...")
    # 合并技术指标和历史数据
    indicators_with_date = indicators.copy()
    history_with_indicators = history_df.merge(
        indicators_with_date,
        left_on='date',
        right_on='trade_date',
        how='left'
    )
    print(f"  合并后数据: {len(history_with_indicators)} 行, {len(history_with_indicators.columns)} 列")

    # 5. 因子 IC 分析
    print("\n[5/6] 因子 IC 分析...")

    # 原始因子
    original_factors = [
        'relative_strength_vs_industry_chain',
        'relative_strength_vs_direct',
        'relative_strength_vs_theme',
        'amount_expansion_ratio',
        'moneyflow_positive_ratio',
        'direct_up_ratio',
        'chain_up_ratio'
    ]

    # 技术指标因子
    tech_factors = ['RSI', 'MACD', 'MACD_hist', 'KDJ_K', 'KDJ_D', 'BB_position', 'ATR', 'OBV']

    all_factors = [f for f in original_factors + tech_factors if f in history_with_indicators.columns]

    ic_results = analyze_factor_ic(history_with_indicators, all_factors)
    print("\n  因子 IC 排名:")
    print(ic_results[['factor', 'IC', 'p_value', 'significant', 'IC_IR']].head(10).to_string())

    # 6. 自相关分析
    print("\n[6/6] 收益率自相关分析...")
    autocorr_results = analyze_autocorrelation(history_df['anchor_return'])
    print(f"  效应类型: {autocorr_results['effect_type']}")
    print(f"  存在自相关: {autocorr_results['has_autocorr']}")
    print(f"  ACF(1): {autocorr_results['acf'][1]:.4f}")

    # 保存结果
    print("\n[INFO] 保存结果...")

    # 保存技术指标
    indicators.to_csv('data/output/analysis_tech_indicators.csv', index=False)

    # 保存 IC 分析结果
    ic_results.to_csv('data/output/analysis_factor_ic.csv', index=False)

    # 保存信号
    ta_signals.to_csv('data/output/analysis_ta_signals.csv', index=False)

    # 生成报告
    report = f"""
# 铂力特量化分析报告

## 1. 数据概览
- 行情数据: {len(blt)} 天
- 历史汇总: {len(history_df)} 天
- 技术指标: {len(indicators.columns) - 1} 个

## 2. 因子 IC 分析结果

### 最有效因子 (IC > 0.03)
{ic_results[ic_results['IC'].abs() > 0.03][['factor', 'IC', 'p_value']].to_string() if len(ic_results[ic_results['IC'].abs() > 0.03]) > 0 else '无'}

### 最无效因子 (IC 接近 0)
{ic_results[ic_results['IC'].abs() < 0.01][['factor', 'IC', 'p_value']].to_string() if len(ic_results[ic_results['IC'].abs() < 0.01]) > 0 else '无'}

## 3. 收益率特征
- 效应类型: {autocorr_results['effect_type']}
- ACF(1): {autocorr_results['acf'][1]:.4f}
- 存在显著自相关: {autocorr_results['has_autocorr']}

## 4. 关键发现
"""

    with open('docs/quant-analysis-report.md', 'w') as f:
        f.write(report)

    print("[OK] 分析完成！结果已保存到 data/output/analysis_*.csv")
    print("[OK] 报告已保存到 docs/quant-analysis-report.md")

    return ic_results, autocorr_results


if __name__ == '__main__':
    main()
