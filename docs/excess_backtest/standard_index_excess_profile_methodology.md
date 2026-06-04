# 标准指数超额画像分析方法论

## 1. 目标

以虚拟指数 NAV 产物为只读输入，构建"信号 → 分档 → Forward Label → 画像统计"的完整流水线，回答：当 Anchor 相对产业链指数明显偏热或偏冷时，未来超额收益更倾向动量延续还是均值回归。

## 2. 数据来源

只读输入，不修改任何上游产物：

| 文件 | 内容 | 行数 |
|------|------|------|
| `anchor_index_excess.csv` | 243 天 × 4 指数 × 4 窗口超额 | 243 |
| `custom_index_nav.csv` | 4 指数 × 243 天 NAV + data_status | 972 |
| `build_manifest.json` | 上游版本元数据 | 1 |

输出目录：`data/price/analytics/index_excess_profiles/constant_universe_2026-05-06/`

## 3. 信号定义

标准超额信号直接从 `anchor_index_excess.csv` 读取 `excess_vs_{index_id}_{N}d`，不重新计算。

信号维度：4 指数（industry_chain / direct_peers / theme_pool / trading_watchlist）× 4 窗口（1d / 3d / 5d / 10d）= 16 条信号序列。

## 4. Forward Labels

对每个信号日 t 和持有期 H ∈ {1, 3, 5, 10}：

```
future_anchor_return_Hd(t) = anchor_close(t+H) / anchor_close(t) - 1
future_index_return_Hd(t)  = index_nav(t+H) / index_nav(t) - 1
future_excess_Hd(t)        = future_anchor_return_Hd(t) - future_index_return_Hd(t)
```

输出为长表格式（每行一个 holding_window），而非宽表。最后 H 个交易日无 future label，标记为 `None`。

标注类型：`close_to_close_research_label`。

## 5. 路径指标

### 5a. 股票自身路径

持有期 [t+1, t+H] 内：

```
long_MFE = max(anchor_close(t+k) / anchor_close(t) - 1) for k in [1..H]
long_MAE = min(anchor_close(t+k) / anchor_close(t) - 1) for k in [1..H]
short_MFE = -long_MAE
short_MAE = -long_MFE
```

回答"能否交易"。

### 5b. 相对指数路径（均值回归路径）

```
relative_path(k) = anchor_return(t, t+k) - index_return(t, t+k)
relative_long_mfe = max(relative_path(k)) for k in [1..H]
relative_long_mae = min(relative_path(k)) for k in [1..H]
relative_short_mfe = -relative_long_mae
relative_short_mae = -relative_long_mfe
```

回答"超额是否均值回归"。统一百分比口径。只使用持有期内数据，不超出 H。

## 6. 分档

### 6.1 分档方式

对每条 (index_id, signal_window) 独立分档，4 个信号窗口的阈值互不影响。

5 档（Q1-Q5），基于超额值的百分位：

| 档位 | 标签 | 条件 |
|------|------|------|
| Q1 | 极冷 | x ≤ P20 |
| Q2 | 偏冷 | P20 < x ≤ P40 |
| Q3 | 中性 | P40 < x ≤ P60 |
| Q4 | 偏热 | P60 < x ≤ P80 |
| Q5 | 极热 | x > P80 |

as-of 模式下当天数值可能超过历史最大值，Q5 定义为 `x > P80`（无上界）。当多个阈值相同时，按上述顺序依次匹配，确保结果确定。

### 6.2 两套分档

**A. static_full_sample_grade**：全样本百分位，标注 `descriptive_only`。只使用 `standard_excess` 非空且 `signal_quality_status ≠ insufficient_data` 的样本计算阈值。不可用于预测结论。

**B. asof_grade**：expanding window，只用 `[0:t)` 数据。最少 60 个非空且非 insufficient_data 的历史信号（不是简单取前 60 行）。不足时标记 `insufficient_grade_history`。只使用 `standard_excess` 非空且 `signal_quality_status ≠ insufficient_data` 的样本计算阈值。

**报告正文只能使用 `asof` 分档得出预测结论。`static_full_sample` 只能放在回顾性附录。**

## 7. 数据质量处理

### 7a. 信号区间与标签区间分别质检

N 日信号依赖 [t-N, t] 的行情，未来 H 日标签依赖 [t, t+H] 的行情。

```
signal_quality_status = worst(data_status over [t-N, t])
label_quality_status  = worst(data_status over [t, t+H])
```

worst 定义：`insufficient_data` > `partial` > `ok`。

### 7b. 统计口径

| 统计口径 | 条件 |
|----------|------|
| `strict_ok_only_stats` | signal_quality_status = ok 且 label_quality_status = ok |
| `usable_stats` | signal_quality_status ≠ insufficient_data 且 label_quality_status ≠ insufficient_data |
| 排除 | 任一为 insufficient_data |

`label_quality_status` 只能用于事后筛选标签，不能参与信号生成和分档。

### 7c. Anchor 自身行情检查

检查铂力特历史区间是否有缺失报价或停牌补值。如有停牌补值，在 `signal_daily.csv` 中标记 `anchor_suspended = true`。

## 8. Profile 统计

### 8a. 评估模式

- `all_signals`：所有符合条件的信号日均纳入
- `non_overlapping`：按时间顺序，每组内相邻样本间隔 ≥ H 个交易日，避免未来标签高度重叠导致样本数虚增

### 8b. 统计指标

对每组 (index_id, signal_window, grade_mode, grade, holding_window, quality_scope, evaluation_mode) 输出：

- sample_count
- future_anchor_return_mean / median
- future_anchor_positive_rate / negative_rate
- future_excess_mean / median
- future_excess_positive_rate / negative_rate
- partial_sample_count / partial_sample_ratio
- long_mfe_mean / long_mae_mean
- short_mfe_mean / short_mae_mean
- relative_long_mfe_mean / relative_long_mae_mean
- relative_short_mfe_mean / relative_short_mae_mean

四条指数分别输出，不混合。`direct_peers_index` 只做辅助确认，不写为主基准。

## 9. 输出文件

| 文件 | 格式 | 关键字段 |
|------|------|---------|
| `signal_daily.csv` | 长表 | date, index_id, signal_window, standard_excess, signal_quality_status, anchor_suspended, static_grade, asof_grade |
| `forward_labels.csv` | 长表（每行一个 holding_window） | date, index_id, holding_window, future_excess, MFE/MAE, relative MFE/MAE, label_quality_status |
| `asof_grade_daily.csv` | 长表 | date, index_id, signal_window, asof_grade, asof_p20/p40/p60/p80 |
| `grade_profile.csv` | 汇总 | grade_mode, grade, evaluation_mode=all_signals |
| `non_overlapping_profile.csv` | 汇总 | evaluation_mode=non_overlapping |
| `benchmark_comparison.csv` | 汇总 | grade_mode, grade |
| `quality_sensitivity.csv` | 汇总 | grade_mode, usable/strict 对比 |
| `static_thresholds.json` | JSON | 分档阈值 |
| `build_manifest.json` | JSON | 元数据 + 上游 SHA256 + 输入校验和 |

## 10. 声明

本产品使用 as-of 分档消除了阈值未来函数，但固定股票池和前复权数据仍然属于 `constant_universe_research_view`，不是严格 PIT 实盘回测。具体限制：

- 使用当前 pools.yaml 配置回算历史，无法证明历史时点就使用这些成员和权重
- 前复权行情在公司行为发生后历史价格可能重算
- 243 个交易日的样本量有限，画像结论可能随时间变化
- non_overlapping 样本量更小，稳健性检查的统计功效有限
