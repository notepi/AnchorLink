# 4 ETF 基准分歧分析

## Context

项目已有四条 ETF-like 指数及标准超额画像。本次分析四条基准对铂力特强弱方向的一致与分歧，回答"主辅分歧时该信谁"，不修改已有产物。

核心问题：
1. 四条 ETF 对铂力特强弱方向什么时候一致？
2. 什么时候 industry_chain_index 与其他三个辅助指数方向相反？
3. 分歧日里，未来 T+1/T+3/T+5/T+10 相对哪个基准的超额更稳定？
4. 这种分歧应该怎么解释？
5. 未来报告中是否应该把"主基准判断"和"辅助基准确认"分开显示？

---

## 目标过滤

**四条指数全部处理：**
- industry_chain_index
- direct_peers_index
- theme_pool_index
- trading_watchlist_index

**信号窗口：** 1D, 3D, 5D, 10D

**持有期：** T+1, T+3, T+5, T+10

---

## 输入文件

主要读取：
- `data/price/analytics/index_products/constant_universe_2026-05-06/anchor_index_excess.csv`
  - 包含 date, anchor_return_1d/3d/5d/10d, excess_vs_{index_id}_{window}d
- `data/price/analytics/index_excess_profiles/constant_universe_2026-05-06/forward_labels.csv`
  - 用于未来标签验证
- `data/price/analytics/index_excess_profiles/constant_universe_2026-05-06/signal_daily.csv`
  - 可选，用于 signal_quality_status / asof_grade 辅助解释

---

## 核心定义

### 1. 单指数方向

对每个 date、signal_window、index_id：

```
excess_signal = excess_vs_{index_id}_{signal_window}d

direction =
  positive if excess_signal > +0.5
  negative if excess_signal < -0.5
  neutral  if -0.5 <= excess_signal <= +0.5 且 excess_signal 非空
  missing  if excess_signal 为空（NaN/None）
```

阈值 ±0.5 使用百分点，避免微小噪音导致方向频繁翻转。

**NaN 规则（写死）：**
- excess_signal 为 NaN/None → direction = missing
- missing 不计入 positive/negative/neutral 计数
- 同时记录 `valid_index_count`（非 missing 的指数数量）
- `valid_index_count < 4` 时标记 `incomplete_signal = true`

同时保留 raw_sign = sign(excess_signal)（missing 时 raw_sign = 0）

### 2. 四指数信号质量过滤

分歧判断是四条 ETF 一起参与，不能只看主基准质量。

从 signal_daily.csv 读取每条指数的 signal_quality_status，连接到每日四指数方向。

**质量口径（写死）：**

```
usable：
  四条指数的 signal_quality_status 都不是 insufficient_data
  且 valid_index_count == 4

strict_ok_only：
  四条指数的 signal_quality_status 都为 ok
  且 valid_index_count == 4
```

**不满足 usable 的日期：**
- 不参与分歧判断
- 不参与 profile 统计
- 在 daily.csv 中保留但标记 `quality_scope = unusable`

**forward 质量口径：**
- usable：四条指数 signal != insufficient_data 且 label != insufficient_data/no_future_label 且 future_excess 非空
- strict_ok_only：四条指数 signal == ok 且 label == ok 且 future_excess 非空

### 3. 四指数一致性

对每个 date、signal_window（仅 usable 日期）：

```
positive_count / negative_count / neutral_count 只统计非 missing

分类优先级（写死，从高到低）：
1. all_aligned_positive  — positive_count == 4（优先于 majority）
2. all_aligned_negative  — negative_count == 4（优先于 majority）
3. majority_positive     — positive_count >= 3 且不满足 all_aligned
4. majority_negative     — negative_count >= 3 且不满足 all_aligned
5. mixed_no_majority     — 其他情况
```

**注意：** all_aligned 必须优先于 majority，否则全一致会被 majority 吃掉。

### 3. 主辅分歧

主基准：industry_chain_index
辅助基准：direct_peers_index + theme_pool_index + trading_watchlist_index

```
aux_majority_direction =
  positive if aux_positive_count >= 2
  negative if aux_negative_count >= 2
  neutral otherwise
```

主辅分歧：
```
main_aux_divergence = 
  main_direction in {positive, negative}
  and aux_majority_direction in {positive, negative}
  and main_direction != aux_majority_direction
```

### 4. 分歧类型

分类优先级（写死，从高到低）：

```
1. all_aligned_positive     — 四指数全部 positive
2. all_aligned_negative    — 四指数全部 negative
3. main_positive_aux_negative — main=positive, aux多数=negative
4. main_negative_aux_positive — main=negative, aux多数=positive
5. main_positive_aux_neutral   — main=positive, aux多数=neutral
6. main_negative_aux_neutral   — main=negative, aux多数=neutral
7. main_neutral_aux_positive   — main=neutral, aux多数=positive
8. main_neutral_aux_negative   — main=neutral, aux多数=negative
9. mixed_no_majority          — 其他情况
```

all_aligned 必须优先于 main_aux 分歧。

### 5. 分歧强度

```
main_excess = industry_chain 标准超额
aux_mean_excess = 三个辅助指数标准超额均值
aux_median_excess = 三个辅助指数标准超额中位数
main_aux_spread = main_excess - aux_median_excess
```

注意：只做解释，不把辅助指数合成新基准。

---

## 未来标签验证

用 forward_labels.csv 计算不同分歧类型下的未来表现。

如果 forward_labels.csv 是长表，需要按 index_id 透视成宽表，保证每个未来窗口都有四条指数对应的 future_excess。

统计维度：signal_window × holding_window × divergence_type

输出指标：
- sample_count
- future_anchor_return_mean / median
- future_anchor_positive_rate
- future_excess_main_mean / median / positive_rate
- future_excess_aux_median_mean / median / positive_rate
- future_excess_consensus_direction_rate

其中：
```
future_excess_aux_median = median(
  future_excess_direct_peers,
  future_excess_theme_pool,
  future_excess_trading_watchlist
)
```

**方向正确率定义（写死）：**

```
future_main_direction_correct =
  (main_direction == positive 且 future_excess_industry_chain > 0)
  或 (main_direction == negative 且 future_excess_industry_chain < 0)

future_aux_direction_correct =
  (aux_majority_direction == positive 且 future_excess_aux_median > 0)
  或 (aux_majority_direction == negative 且 future_excess_aux_median < 0)
```

- main_direction 或 aux_majority_direction 为 neutral/missing 时不参与 correct 统计
- future_excess 为空时也不参与 correct 统计
- correct 率 = correct_count / valid_count（只统计有明确方向且有未来数据的样本）

---

## 输出目录

新建：`data/price/analytics/index_benchmark_divergence/constant_universe_2026-05-06/`

---

## 输出文件

### 1. benchmark_divergence_daily.csv

逐日明细字段：
- date, signal_window
- anchor_return_{window}
- excess_industry_chain, excess_direct_peers, excess_theme_pool, excess_trading_watchlist
- direction_industry_chain, direction_direct_peers, direction_theme_pool, direction_trading_watchlist
- positive_count, negative_count, neutral_count, missing_count
- valid_index_count, incomplete_signal
- main_direction, aux_majority_direction
- main_aux_divergence, divergence_type
- main_excess, aux_mean_excess, aux_median_excess, main_aux_spread
- signal_quality_status_industry_chain, signal_quality_status_direct_peers, signal_quality_status_theme_pool, signal_quality_status_trading_watchlist
- quality_scope

### 2. benchmark_divergence_forward.csv

连接未来标签后明细字段：
- date, signal_window, holding_window, divergence_type
- future_anchor_return
- future_excess_industry_chain, future_excess_direct_peers, future_excess_theme_pool, future_excess_trading_watchlist
- future_excess_aux_median
- future_main_direction_correct, future_aux_direction_correct
- signal_quality_status_industry_chain, signal_quality_status_direct_peers, signal_quality_status_theme_pool, signal_quality_status_trading_watchlist
- label_quality_status_industry_chain, label_quality_status_direct_peers, label_quality_status_theme_pool, label_quality_status_trading_watchlist
- quality_scope

### 3. benchmark_divergence_profile.csv

维度：signal_window, holding_window, divergence_type
输出第六节所有统计指标。

### 4. benchmark_divergence_cases.csv

只输出 main_aux_divergence == true 的日期，字段包括：
- date, signal_window, divergence_type
- main_excess, aux_median_excess, main_aux_spread
- 四指数方向, 四指数超额
- future_anchor_return_1d/3d/5d/10d
- future_excess_main_1d/3d/5d/10d
- future_excess_aux_median_1d/3d/5d/10d

### 5. benchmark_divergence_summary.json

记录：
- 各 signal_window 的一致率
- 各 signal_window 的主辅分歧率
- 最常见的 divergence_type
- main_negative_aux_positive 的样本数和未来表现
- main_positive_aux_negative 的样本数和未来表现

### 6. build_manifest.json

记录：
- generated_at, input files, input checksums
- pool_config_version, universe_mode, price_adjustment_mode
- target_index_ids, signal_windows, holding_windows
- output_record_counts

**双上游溯源（写死）：**

```
index_products_manifest_sha256:    index_products/ build_manifest.json 文件自身 SHA256
index_excess_profiles_manifest_sha256: index_excess_profiles/ build_manifest.json 文件自身 SHA256
source_data_as_of_index_products:  从 index_products/ build_manifest.json 继承
source_data_as_of_profiles:        从 index_excess_profiles/ build_manifest.json 继承
```

不再用单一 upstream_manifest_sha256，因为输入来自两个目录。

### 7. docs/excess_backtest/benchmark_divergence_analysis.md

分析报告。

---

## 报告必须回答的问题

1. 四 ETF 是否应该投票？
2. 还是继续保留 industry_chain 为主基准、其余为辅助解释？
3. 当主辅分歧时，应该怎么标记？
4. 2025-11 到 2025-12 的分歧案例说明了什么？
5. 这是否影响此前 Q5 极热 → 相对回落 的主结论？
6. 对后续日报或前端展示有什么建议？

重点分析：
- main_negative_aux_positive：industry_chain 说弱但辅助说强
- main_positive_aux_negative：industry_chain 说强但辅助说弱
- 四指数一致极热/极冷时未来结果是否比单主基准更稳定
- 分歧日期列表及时间集中性

建议结论语言：
- 四指数一致：高置信
- 主辅分歧：降级为解释型信号
- industry_chain 弱、辅助强：产业链强度高于其他参照，不能简单说 Anchor 弱
- industry_chain 强、辅助弱：Anchor 在产业链里占优，但未必在情绪或交易池里占优

**禁止写成：** "多数投票胜出"/"主基准错误"/"辅助指数推翻主基准"，除非数据明确支持并给出样本量和未来验证。

---

## 测试用例

文件：`tests/test_benchmark_divergence.py`

| # | 测试内容 |
|---|----------|
| 1 | 四条指数标准超额字段正确读取 |
| 2 | direction 阈值 ±0.5 正确，NaN → missing |
| 3 | positive/negative/neutral/missing 计数正确，missing 不计入前三者 |
| 4 | valid_index_count 和 incomplete_signal 正确 |
| 5 | aux_majority_direction 正确 |
| 6 | main_aux_divergence 判定正确 |
| 7 | divergence_type 分类正确，all_aligned 优先于 majority |
| 8 | 四指数质量过滤：usable 需四条都不是 insufficient_data 且 valid_index_count==4 |
| 9 | strict_ok_only 需四条都是 ok |
| 10 | forward_labels 长表正确透视为四指数宽表 |
| 11 | future_excess_aux_median 计算正确 |
| 12 | future_main_direction_correct 定义正确 |
| 13 | future_aux_direction_correct 定义正确 |
| 14 | profile sample_count 与 forward 明细一致 |
| 15 | 分歧 cases 只包含 main_aux_divergence=true |
| 16 | build_manifest 包含双上游 checksum 和双 source_data_as_of |
| 17 | 旧数据未被修改 |
| 18 | 脚本可从项目根目录直接运行 |

---

## 不修改的文件

- data/price/analytics/index_products/
- data/price/analytics/index_excess_profiles/
- data/price/analytics/index_excess_qg_profiles/
- docs/excess_backtest/excess_grade_*
- docs/excess_backtest/asof_validation/

---

## 新增文件

- src/index_products/benchmark_divergence.py
- scripts/build_benchmark_divergence_analysis.py
- tests/test_benchmark_divergence.py
- docs/excess_backtest/benchmark_divergence_analysis.md
- data/price/analytics/index_benchmark_divergence/constant_universe_2026-05-06/

---

## 执行命令

```bash
python scripts/build_benchmark_divergence_analysis.py
uv run pytest tests/test_benchmark_divergence.py -v
```

---

## 完成后汇报

1. 生成文件清单
2. 测试通过数量
3. 四指数方向一致率
4. 主辅分歧率
5. main_negative_aux_positive 样本数和未来表现
6. main_positive_aux_negative 样本数和未来表现
7. 是否影响 Q5 极热主结论
8. 是否建议前端增加"基准分歧"提示
9. 旧数据未修改确认
