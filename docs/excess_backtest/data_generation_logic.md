# 数据生成逻辑

> 对应脚本：`scripts/excess_grade_backtest.py`

## 一、目标

对每个交易日，计算三个超额指标的 Q 档（位置）和 G 档（方向），以及未来 20 天的前向空间，输出每日明细数据。

核心原则：**每日独立评估，无空窗期**。每个交易日落入某个网格，就独立计算前向空间，不做连续资金管理。

## 二、输入

| 文件 | 来源 | 用途 |
|------|------|------|
| market_data_normalized.parquet | src.price.run | 铂力特的 OHLC 行情 |
| history_rolling_metrics.csv | build_history_analysis.py | 5日超额、10日超额 |
| history_summary.csv | build_history_analysis.py | 当日超额（relative_strength_vs_industry_chain） |

## 三、流程

```
1. load_and_merge()
   行情 + 超额指标 → 合并到一张表（按日期对齐）

2. compute_forward_metrics()
   对每一天算未来 20 天的最高/最低价收益

3. assign_q_grades()
   三个指标各自按百分位分 5 档（Q 维度：位置）

4. assign_g_grades()
   三个指标各自按日间 delta 百分位分 5 档（G 维度：方向）

5. build_daily_rows()
   展开为每天 × 每指标一行

6. compute_buy_and_hold()
   计算买入持有基线

7. 输出 CSV + JSON
```

## 四、步骤详解

### 4.1 数据加载与合并

```
铂力特行情（trade_date, open, high, low, close）
  + history_rolling_metrics.csv 的 excess_5d, excess_10d
  + history_summary.csv 的 daily_excess
  → 按 date_str 对齐
```

三个超额指标的含义：

| 指标 | 含义 |
|------|------|
| excess_5d | 过去 5 天铂力特相对板块的超额收益 |
| excess_10d | 过去 10 天铂力特相对板块的超额收益 |
| daily_excess | 当天铂力特相对产业链的相对强度 |

### 4.2 前向指标计算

对每个交易日 i（最后 MAX_HOLD=20 天除外）：

| 字段 | 计算方式 | 含义 |
|------|---------|------|
| fwd_20d_max_return | (max(high[i+1..i+20]) / close[i] - 1) × 100 | 未来20天最高价相对当天收盘的涨幅(%) |
| fwd_20d_min_return | (min(low[i+1..i+20]) / close[i] - 1) × 100 | 未来20天最低价相对当天收盘的跌幅(%) |
| fwd_20d_peak_day | argmax(high[i+1..i+20]) + 1 | 最高价出现在第几天(1-20) |
| fwd_20d_trough_day | argmin(low[i+1..i+20]) + 1 | 最低价出现在第几天(1-20) |
| tradeable | 1（最后20天=0） | 是否有完整的20天前向数据 |

### 4.3 Q 维度分档（位置）

三个指标**各自独立**按百分位分 5 档：

| 档位 | 标签 | 百分位区间 | 含义 |
|------|------|-----------|------|
| 1 | 极冷 | P0-P20 | 超额极低 |
| 2 | 偏冷 | P20-P40 | |
| 3 | 中性 | P40-P60 | |
| 4 | 偏热 | P60-P80 | |
| 5 | 极热 | P80-P100 | 超额极高 |

阈值计算：`pct_threshold(series, p)` = 排序后第 p% 位置的值。

超额值为 NaN → q_grade = 空。

### 4.4 G 维度分档（方向）

对每个指标，计算日间变化：

```
delta(t) = excess(t) - excess(t-1)
```

按 delta 百分位分 5 档：

| 档位 | 标签 | 百分位区间 | 含义 |
|------|------|-----------|------|
| 1 | 大降 | P0-P20 | 超额在快速恶化 |
| 2 | 小降 | P20-P40 | 超额在缓慢恶化 |
| 3 | 稳定 | P40-P60 | 超额变化不大 |
| 4 | 小升 | P60-P80 | 超额在缓慢改善 |
| 5 | 大升 | P80-P100 | 超额在快速改善 |

注意：
- 每个指标独立算 delta 和分档阈值
- 第一天没有 delta → g_grade = 空
- G 用百分位而不用固定阈值：各指标 delta 量级不同，百分位自动适应

### 4.5 每日数据展开

原始数据是每天一行（含三个指标），展开为**每天 × 每指标一行**：

| 字段 | 说明 |
|------|------|
| date | 交易日期（YYYYMMDD） |
| indicator | 指标名（excess_5d / excess_10d / daily_excess） |
| excess_value | 当天该指标的值 |
| q_grade | Q 档位（1-5） |
| q_label | Q 档位标签 |
| g_grade | G 档位（1-5） |
| g_label | G 档位标签 |
| tradeable | 是否可回测 |
| fwd_20d_max_return | 前向最高收益 |
| fwd_20d_min_return | 前向最低收益 |
| fwd_20d_peak_day | 达峰天数 |
| fwd_20d_trough_day | 达谷天数 |
| long_upside | = fwd_20d_max_return（做多理论上行空间） |
| long_adverse | = fwd_20d_min_return（做多理论不利空间） |
| short_upside | = -fwd_20d_min_return（做空理论上行空间） |
| short_adverse | = -fwd_20d_max_return（做空理论不利空间） |

术语：**空间**（不是收益）。Oracle 退出 = 20 天内最高/最低价，是理论上界。

```
做多空间 = 20天内最高价收益
做空空间 = 20天内最低价收益取反
不利空间 = 反方向的最大波动
```

### 4.6 买入持有基线

| 指标 | 计算 |
|------|------|
| totalReturnPct | (最后收盘 / 首日收盘 - 1) × 100 |
| maxDrawdown | 峰值回撤的最大值 |
| nDays | 总交易日数 |

## 五、输出

| 文件 | 内容 |
|------|------|
| excess_grade_daily.csv | 约 N×3 行（N=可回测天数，3个指标），每日每指标一行 |
| excess_grade_thresholds.json | Q/G 分档阈值 + 档位标签 + 买入持有基线 |

## 六、已知局限

| 问题 | 说明 |
|------|------|
| Oracle 退出 | 用 20 天内最高/最低价退出，是理论上界，实际做不到 |
| 佣金=0 | 真实交易有佣金和滑点 |
| 重叠窗口 | 连续触发日的前向 20 天收益有 19 天重叠，影响 t-stat 可靠性 |
| 做空不可行 | 科创板融券困难，做空仅理论参考 |
| 样本量 | 当前约 252 天数据，5×5=25 格，极端格样本有限 |
