# 标准指数超额画像分析

## Context

项目已生成四条 ETF-like 指数 NAV 数据（`data/price/analytics/index_products/constant_universe_2026-05-06/`）。本阶段以这些产物为只读输入，回答核心问题："当铂力特相对产业链指数明显偏热或偏冷时，未来更倾向继续强化，还是均值回归？"

不修改旧版超额数据、旧 Q×G 分析结果、旧指数构建产物。

## 只读输入

- `anchor_index_excess.csv`：243 行，date + anchor_close + anchor_return_Nd + 4 指数 × 4 窗口超额
- `custom_index_nav.csv`：972 行（4 指数 × 243 天），含 index_return_1d/3d/5d/10d + data_status + fresh_quote_ratio + universe_inclusion_ratio
- `build_manifest.json`：版本元数据

关键列名（来自实际 CSV header）：
- NAV: `index_id`, `trade_date`, `nav`, `index_return_1d`, `index_return_3d`, `index_return_5d`, `index_return_10d`, `data_status`, `fresh_quote_ratio`, `universe_inclusion_ratio`, `stale_symbols`
- Excess: `date`, `anchor_close`, `anchor_return_1d/3d/5d/10d`, `excess_vs_industry_chain_index_1d/3d/5d/10d`, 同理 direct_peers/theme_pool/trading_watchlist

## 输出目录

```
data/price/analytics/index_excess_profiles/constant_universe_2026-05-06/
```

## 新建文件

| 文件 | 职责 |
|------|------|
| `src/index_products/excess_profile.py` | 画像分析核心：信号提取、分档、forward label、profile 统计 |
| `scripts/build_standard_index_excess_profile.py` | 入口脚本 |
| `tests/test_standard_index_excess_profile.py` | 11 项单元测试 |
| `docs/excess_backtest/standard_index_excess_profile.md` | 分析报告 |
| `docs/excess_backtest/standard_index_excess_profile_methodology.md` | 方法论文档 |

## 核心算法

### 1. 标准超额信号

从 `anchor_index_excess.csv` 直接读取 `excess_vs_{index_id}_{N}d`，**不重新计算**。这些值已经满足 `anchor_return_Nd - index_return_Nd` 公式。

信号维度：4 指数 × 4 信号窗口 = 16 条信号序列。

### 2. Forward Labels

对每个信号日 t 和持有期 H ∈ {1, 3, 5, 10}：

```
future_anchor_return_Hd(t) = anchor_close(t+H) / anchor_close(t) - 1
future_index_return_Hd(t)  = index_nav(t+H) / index_nav(t) - 1
future_excess_Hd(t)        = future_anchor_return_Hd(t) - future_index_return_Hd(t)
```

数据来源：`anchor_index_excess.csv` 的 `anchor_close` 和 `custom_index_nav.csv` 的 `nav`。

最后 H 个交易日没有 future label → 标记为 `None`。

标注：`close_to_close_research_label`

### 3. 路径指标（MFE/MAE）

#### 3a. 股票自身路径

持有期 [t+1, t+H] 内：

```
long_MFE = max(anchor_close(t+k) / anchor_close(t) - 1) for k in [1..H]
long_MAE = min(anchor_close(t+k) / anchor_close(t) - 1) for k in [1..H]
short_MFE = -long_MAE
short_MAE = -long_MFE
```

回答"能否交易"。

#### 3b. 相对指数路径（均值回归路径）

```
relative_path(k) = anchor_return(t, t+k) - index_return(t, t+k)
relative_long_mfe = max(relative_path(k)) for k in [1..H]
relative_long_mae = min(relative_path(k)) for k in [1..H]
relative_short_mfe = -relative_long_mae
relative_short_mae = -relative_long_mfe
```

回答"超额是否均值回归"。统一百分比口径。只使用持有期内的数据，不超出 H。

### 4. 分档逻辑

对每条 (index_id, signal_window) 独立分档，4 个信号窗口的阈值互不影响。

5 档（Q1-Q5），基于超额值的百分位：

| 档位 | 标签 | 百分位范围 |
|------|------|-----------|
| Q1 | 极冷 | P0-P20 |
| Q2 | 偏冷 | P20-P40 |
| Q3 | 中性 | P40-P60 |
| Q4 | 偏热 | P60-P80 |
| Q5 | 极热 | P80-P100 |

两套分档：

**A. static_full_sample_grade**：全样本百分位，标注 `descriptive_only`。只使用 `standard_excess` 非空且 `signal_quality_status ≠ insufficient_data` 的样本计算阈值。

**B. asof_grade**：expanding window，只用 `[0:t)` 数据。最少 60 个非空且非 insufficient_data 的历史信号（不是简单取前 60 行）。不足时标记 `insufficient_grade_history`。只使用 `standard_excess` 非空且 `signal_quality_status ≠ insufficient_data` 的样本计算阈值。

分位边界定义：

```
Q1: x <= P20
Q2: P20 < x <= P40
Q3: P40 < x <= P60
Q4: P60 < x <= P80
Q5: x > P80
```

as-of 模式下当天数值可能超过历史最大值，Q5 定义为 `x > P80`（无上界）。当多个阈值相同时，按上述顺序依次匹配，确保结果确定。

**报告正文只能使用 `asof` 分档得出预测结论。`static_full_sample` 只能放在回顾性附录。**

### 5. 数据质量处理

从 `custom_index_nav.csv` 的 `data_status` 字段读取。

#### 5a. 信号区间与标签区间分别质检

N 日信号依赖 [t-N, t] 的行情，未来 H 日标签依赖 [t, t+H] 的行情。任一区间存在 stale 报价都会影响结果。

```
signal_quality_status = worst(data_status over [t-N, t])
label_quality_status  = worst(data_status over [t, t+H])
```

worst 定义：`insufficient_data` > `partial` > `ok`（即只要有一个 insufficient_data 就整段 insufficient_data）。

#### 5b. 统计口径

| 统计口径 | 条件 |
|----------|------|
| `strict_ok_only_stats` | signal_quality_status = ok 且 label_quality_status = ok |
| `usable_stats` | signal_quality_status ≠ insufficient_data 且 label_quality_status ≠ insufficient_data |
| 排除 | signal_quality_status = insufficient_data 或 label_quality_status = insufficient_data |

`label_quality_status` 只能用于事后筛选标签，不能参与信号生成和分档。

每份报告同时输出两个口径的统计。

#### 5c. Anchor 自身行情检查

当前质量字段主要覆盖指数成员，还没有覆盖 Anchor 自身。构建前需检查：

- 铂力特历史区间没有缺失报价或重复日期
- 如有停牌补值（forward-filled close），需要在报告中标记
- 检查方式：对比 `anchor_index_excess.csv` 中 anchor_close 是否连续非空，如有缺日或停牌补值，在 `signal_daily.csv` 中标记 `anchor_suspended = true`

### 6. Profile 统计

对每组 (index_id, signal_window, grade, holding_window, quality_scope) 输出：

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

## 输出文件

### `signal_daily.csv`
```
date, index_id, signal_window, standard_excess, data_status,
fresh_quote_ratio, universe_inclusion_ratio, stale_symbols,
signal_quality_status, anchor_suspended,
static_grade, static_grade_label, asof_grade, asof_grade_label
```

### `forward_labels.csv`（长表，每行一个 holding_window）
```
date, index_id, holding_window,
future_anchor_return, future_index_return, future_excess,
long_mfe, long_mae, short_mfe, short_mae,
relative_long_mfe, relative_long_mae,
relative_short_mfe, relative_short_mae,
label_quality_status, label_type
```

`signal_quality_status` 只保留在 `signal_daily.csv`。画像统计时按 `date + index_id` 关联两张表。`label_quality_status` 随 holding_window 不同而不同（1D/3D/5D/10D 对应的未来区间长度不同）。

### `asof_grade_daily.csv`
```
date, index_id, signal_window, standard_excess, asof_grade, asof_grade_label,
asof_p20, asof_p40, asof_p60, asof_p80, asof_sample_count
```

### `grade_profile.csv`
```
index_id, signal_window, grade_mode, grade, grade_label, holding_window, quality_scope, evaluation_mode,
sample_count, future_anchor_return_mean, future_anchor_return_median,
future_anchor_positive_rate, future_anchor_negative_rate,
future_excess_mean, future_excess_median,
future_excess_positive_rate, future_excess_negative_rate,
partial_sample_count, partial_sample_ratio,
long_mfe_mean, long_mae_mean, short_mfe_mean, short_mae_mean,
relative_long_mfe_mean, relative_long_mae_mean, relative_short_mfe_mean, relative_short_mae_mean
```

`grade_mode` = `static_full_sample` | `asof`。`evaluation_mode` = `all_signals`。报告正文只能使用 `asof` 得出预测结论。

### `benchmark_comparison.csv`
```
index_id, signal_window, grade_mode, grade, holding_window, quality_scope,
anchor_return_mean, anchor_return_median, anchor_positive_rate,
excess_mean, excess_median, excess_positive_rate,
sample_count
```

### `quality_sensitivity.csv`
```
index_id, signal_window, grade_mode, grade, holding_window,
usable_anchor_return_mean, strict_anchor_return_mean,
usable_anchor_return_median, strict_anchor_return_median,
usable_anchor_positive_rate, strict_anchor_positive_rate,
usable_excess_mean, strict_excess_mean,
usable_excess_median, strict_excess_median,
usable_excess_positive_rate, strict_excess_positive_rate,
usable_sample_count, strict_sample_count, partial_count, partial_ratio
```

### `non_overlapping_profile.csv`
```
index_id, signal_window, grade_mode, grade, grade_label, holding_window, quality_scope, evaluation_mode,
sample_count, future_anchor_return_mean, future_anchor_return_median,
future_anchor_positive_rate, future_anchor_negative_rate,
future_excess_mean, future_excess_median,
future_excess_positive_rate, future_excess_negative_rate,
relative_long_mfe_mean, relative_long_mae_mean, relative_short_mfe_mean, relative_short_mae_mean
```

`evaluation_mode = non_overlapping`：按时间顺序，每组 (index_id, signal_window, grade_mode, grade, holding_window) 内，相邻样本间隔至少为 H 个交易日。用作稳健性检查，避免连续日期的未来标签高度重叠导致样本数虚增。

`grade_profile.csv` 的 `evaluation_mode = all_signals`。

### `static_thresholds.json`
```json
{
  "generated_at": "...",
  "pool_config_version": "2026-05-06",
  "universe_mode": "constant_universe_research_view",
  "descriptive_only": true,
  "thresholds": {
    "industry_chain_index": {
      "1d": {"P20": ..., "P40": ..., "P60": ..., "P80": ...},
      "3d": {...}, "5d": {...}, "10d": {...}
    },
    ...
  }
}
```

### `build_manifest.json`
包含元数据 + 各输出文件行数 + 上游溯源：

```json
{
  "generated_at": "...",
  "pool_config_version": "2026-05-06",
  "universe_mode": "constant_universe_research_view",
  "price_adjustment_mode": "qfq",
  "source_data_as_of": "...",
  "upstream_build_manifest_sha256": "...",
  "input_checksums": {
    "anchor_index_excess_csv_sha256": "...",
    "custom_index_nav_csv_sha256": "...",
    "build_manifest_json_sha256": "..."
  },
  "output_record_counts": {
    "signal_daily": ...,
    "forward_labels": ...,
    "asof_grade_daily": ...,
    "grade_profile": ...,
    "non_overlapping_profile": ...,
    "benchmark_comparison": ...,
    "quality_sensitivity": ...
  }
}
```

## 脚本入口

`scripts/build_standard_index_excess_profile.py`

- `sys.path.insert(0, ROOT)` 确保直接运行
- 默认从 `data/price/analytics/index_products/constant_universe_2026-05-06/` 读取
- 输出到 `data/price/analytics/index_excess_profiles/constant_universe_2026-05-06/`

## 测试（15 项）

1. 标准超额公式：从 anchor_index_excess.csv 读取的值 = anchor_return_Nd - index_return_Nd
2. 5D/10D 超额不是 daily_excess 简单求和
3. Forward label 公式正确：future_anchor_return_5d = anchor_close(t+5)/anchor_close(t) - 1
4. 最后 H 个交易日没有 future label
5. 四个信号窗口分别独立分档（阈值不同）
6. asof_grade 只使用 t-1 及以前数据
7. insufficient_data 行被排除
8. partial 行只进入 usable_stats，不进入 strict_ok_only_stats
9. 四条指数分别输出，不允许混合
10. 旧数据文件未被修改（检查 mtime 或 checksum）
11. 脚本可从项目根目录直接运行
12. grade_profile.csv 包含 grade_mode 列，asof 和 static 行数一致
13. 重复值导致分位阈值相等时，分档仍正确（按顺序匹配）
14. non_overlapping_profile 相邻样本间隔 ≥ H
15. signal_quality_status 和 label_quality_status 各自覆盖正确区间

## 报告要求

`standard_index_excess_profile.md` 必须回答 7 个问题（见需求 §九），优先展示：
- 样本量
- 中位数
- 胜率
- 均值是否被极端值拉动
- 严格口径是否仍然成立
- MFE/MAE 路径特征（自身路径 + 相对路径）
- non_overlapping 稳健性检查结论

报告必须声明：as-of 分档消除了阈值未来函数，但固定股票池和前复权数据仍然属于 `constant_universe_research_view`，不是严格 PIT 实盘回测。

## 验证

```bash
uv run python scripts/build_standard_index_excess_profile.py
uv run pytest tests/test_standard_index_excess_profile.py -v
git diff --stat -- docs/excess_backtest/excess_grade_* data/price/analytics/index_products/
```
