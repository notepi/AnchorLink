# Daily Signal Review：标准超额 Q×G + 基准分歧每日信号解释层

## 背景

当前项目已经完成三块分析：

1. 标准 ETF 类基准超额
2. 标准超额 Q×G 画像（`index_excess_qg_profiles/`）
3. 四 ETF 基准分歧分析（`index_benchmark_divergence/`）

本次新增"每日信号解释层"，把 Q×G 网格画像和基准分歧分析合并成每天可读、可展示、可接入前端/日报的信号解释文件。

## 目标

回答每天三个问题：

1. 今天锚定股相对主基准处于什么状态？（Q档 + G档 + Q×G历史画像）
2. 今天基准之间是否分歧？（主辅分歧 + 四ETF一致）
3. 今天应该如何解释？（signal_label + action_hint + explanation）

**不是交易系统，不输出买/卖指令，只输出画像解释和动作倾向。**

---

## 输入文件

只读取，不修改：

- `data/price/analytics/index_excess_qg_profiles/constant_universe_2026-05-06/qg_signal_daily.csv`
- `data/price/analytics/index_excess_qg_profiles/constant_universe_2026-05-06/qg_grid_profile.csv`
- `data/price/analytics/index_excess_qg_profiles/constant_universe_2026-05-06/qg_quadrant_profile.csv`
- `data/price/analytics/index_excess_qg_profiles/constant_universe_2026-05-06/build_manifest.json`
- `data/price/analytics/index_benchmark_divergence/constant_universe_2026-05-06/benchmark_divergence_daily.csv`
- `data/price/analytics/index_benchmark_divergence/constant_universe_2026-05-06/benchmark_divergence_profile.csv`
- `data/price/analytics/index_benchmark_divergence/constant_universe_2026-05-06/build_manifest.json`

---

## 核心逻辑

### 1. 每日信号粒度

以 `qg_signal_daily.csv` 为主表，每行 = 一个 date + signal_window 组合。

按 `date + signal_window` 连接 `benchmark_divergence_daily.csv`。

### 2. 信号窗口范围

CSV 保留 `qg_signal_daily.csv` 中实际存在的 signal_window，目前是 **[5, 10]**。

`benchmark_divergence_daily` 虽然有 [1,3,5,10]，但这里只按 Q×G 的 signal_window 左连接，1D 和 3D 的分歧数据不会进入结果。

日报和 latest JSON 默认重点看：
- `signal_window = 5`（主视图）
- `signal_window = 10`（确认视图）
- `holding_window = 5` 和 `holding_window = 10`

原因：5D 标准超额更接近当前主线 Q 口径；5D/10D 是 Q×G 区分度较高的未来观察窗口。

### 3. 从 qg_grid_profile 提取历史画像

对每个 `date + signal_window + q_grade + g_grade`，从 `qg_grid_profile.csv` 找到 `quality_scope=usable, evaluation_mode=all_signals` 的对应行。

提取：
- `sample_count_5d`（hw=5 的 sample_count）
- `sample_count_10d`（hw=10 的 sample_count）
- `sample_count = min(sample_count_5d, sample_count_10d)`
- `future_excess_median`（hw=5 → `future_excess_5d_median`，hw=10 → `future_excess_10d_median`）
- `future_anchor_return_median`（同理）

**样本不足规则（写死）：**
```
sample_count < 5 → sample_quality = low_sample
sample_count >= 5 → sample_quality = ok
```

分别保留两个 holding_window 的样本数，避免看不清是 T+5 还是 T+10 样本不足。

### 4. 从 benchmark_divergence_daily 提取分歧状态

提取：
- `divergence_type`
- `main_aux_divergence`
- `positive_count / negative_count / neutral_count`
- `valid_index_count`
- `incomplete_signal`
- `quality_scope`（重命名为 `divergence_quality_scope`）

**连接时保留全部 quality_scope，不过滤 unusable。** 如果过滤掉，早期日期会连不上，反而丢失"为什么不可用"的解释。unusable 行会触发 confidence_level = low。

### 5. confidence_level 规则（写死）

```
confidence_level = low（任一满足）：
  - sample_quality = low_sample
  - main_aux_divergence = true
  - incomplete_signal = true
  - divergence_quality_scope = unusable

confidence_level = high（全部满足）：
  - sample_quality = ok
  - main_aux_divergence = false
  - incomplete_signal = false
  - divergence_type in {all_aligned_positive, all_aligned_negative}

confidence_level = medium（其他）
```

**优先级：low > high > medium**（多条件冲突时 low 优先）

### 6. signal_label 规则（写死）

#### 热端（Q >= 4）
- G >= 4 → `热端上升：不追高`
- 未来5D和10D超额中位数均负 → `热端回落：相对走弱`
- G <= 2 → `热端下行：偏观察`
- 其他 → `热端平稳：偏观察`

#### 冷端（Q <= 2）
- G >= 4 且未来超额任一为正 → `冷端回升：弱均值回归候选`
- G >= 4 → `冷端回升：偏观察`
- G <= 2 → `冷端下行：接飞刀风险`
- 其他 → `冷端平稳：偏观察`

#### 中性
- `中性状态：观察`

#### 数据不足
- Q/G 不在 1-5 → `数据不足：观察`

### 7. action_hint 规则（写死）

允许值及优先级（高→低）：
1. `downgraded_explanatory` — main_aux_divergence=true
2. `avoid_chasing` — Q>=4 + 未来5D/10D超额均负
3. `risk_warning` — Q<=2 + G<=2
4. `mean_reversion_candidate` — Q<=2 + G>=4 + 未来超额任一为正
5. `watch` — 其他

**注意：** 不再单独设 `high_confidence_relative_weakness/repair`。高置信通过 `confidence_level` 字段表达，不作为独立动作。action_hint 只描述动作倾向，confidence_level 描述可信程度，两者正交。

如果 Q5 + confidence=high + avoid_chasing，explanation 里会写明"高置信 + 不追高"——本质仍是"不追高"，只是更可信。

### 8. explanation 生成

拼接短中文解释，格式：
```
当前处于 Q5(极热)-G4(小升) 状态；历史画像显示 T+5 超额中位 -1.9%、T+10 超额中位 -2.5%；四 ETF 基准一致；置信度较高
```

分歧时：
```
当前处于 Q3(中性)-G2(小降) 状态；主基准与辅助基准方向分歧，信号应降级为解释型，不宜单独作为方向判断；置信度较低
```

---

## 输出目录

新建：`data/price/analytics/index_daily_signal_review/constant_universe_2026-05-06/`

## 输出文件

### 1. daily_signal_review.csv

字段：
- date, signal_window
- q_grade, g_grade, qg_grid, qg_zone
- sample_count_5d, sample_count_10d, sample_count, sample_quality
- future_excess_5d_median, future_excess_10d_median
- future_anchor_return_5d_median, future_anchor_return_10d_median
- divergence_type, main_aux_divergence
- positive_count, negative_count, neutral_count
- valid_index_count, incomplete_signal
- divergence_quality_scope
- confidence_level, signal_label, action_hint, explanation

### 2. daily_signal_review_latest.json

最新交易日重点视图，包含 5D 主视图 + 10D 确认视图：
```json
{
  "latest_date": "20260602",
  "primary_signal_window": 5,
  "primary_item": {
    "signal_window": 5,
    "q_grade": 5,
    "g_grade": 4,
    "qg_grid": "Q5-G4",
    "signal_label": "热端上升：不追高",
    "action_hint": "avoid_chasing",
    "confidence_level": "high",
    "explanation": "...",
    "future_excess_5d_median": -1.88,
    "future_excess_10d_median": -2.48,
    "divergence_type": "all_aligned_positive",
    "main_aux_divergence": false
  },
  "confirmation_item": {
    "signal_window": 10,
    "q_grade": 5,
    "g_grade": 3,
    "qg_grid": "Q5-G3",
    "signal_label": "...",
    "action_hint": "...",
    "confidence_level": "...",
    "explanation": "...",
    "future_excess_5d_median": ...,
    "future_excess_10d_median": ...,
    "divergence_type": "...",
    "main_aux_divergence": ...
  }
}
```

### 3. daily_signal_review_summary.json

统计：
- total_rows, date_range
- confidence_level_counts
- action_hint_counts
- main_aux_divergence_count
- low_sample_count
- latest_date
- latest_primary_signal

### 4. build_manifest.json

双上游溯源：
- generated_at
- source_qg_manifest_sha256
- source_divergence_manifest_sha256
- source_data_as_of_qg
- source_data_as_of_divergence
- input_files, output_files
- output_record_counts

---

## 新增文件

- `src/index_products/daily_signal_review.py`
- `scripts/build_daily_signal_review.py`
- `tests/test_daily_signal_review.py`
- `docs/excess_backtest/daily_signal_review.md`
- `data/price/analytics/index_daily_signal_review/constant_universe_2026-05-06/`

## 不修改

- index_products/
- index_excess_profiles/
- index_excess_qg_profiles/
- index_benchmark_divergence/

---

## 测试用例

| # | 测试内容 |
|---|----------|
| 1 | Q×G 和 divergence 按 date+signal_window 正确连接 |
| 2 | 只保留 qg_signal_daily 中实际存在的 signal_window（5 和 10） |
| 3 | sample_count < 5 → sample_quality = low_sample |
| 4 | sample_count_5d 和 sample_count_10d 分别保留 |
| 5 | main_aux_divergence=true → confidence_level = low |
| 6 | divergence_quality_scope=unusable → confidence_level = low（不过滤 unusable 行） |
| 7 | 四ETF全一致 + 样本足够 + 无缺失 → confidence_level = high |
| 8 | Q5 + 未来5D/10D超额中位数为负 → avoid_chasing |
| 9 | Q1 + G回升 + 未来超额中位数为正 → mean_reversion_candidate |
| 10 | latest JSON 包含 primary_item（5D）+ confirmation_item（10D） |
| 11 | manifest 包含两个上游 manifest SHA256 |
| 12 | 旧数据目录未修改 |

---

## 报告要求

`docs/excess_backtest/daily_signal_review.md` 包含：

1. 这层分析解决什么问题
2. 为什么不是交易指令，而是每日解释层
3. 输入数据来源
4. 字段口径
5. confidence_level 规则
6. action_hint 规则
7. 最新交易日信号摘要
8. 对 Q5 热端回落、Q1 冷端修复、基准分歧降级的解释
9. 局限性

---

## 执行命令

```bash
python scripts/build_daily_signal_review.py
uv run pytest tests/test_daily_signal_review.py -v
```

## 完成后汇报

1. 新增/修改文件清单
2. 测试通过数量
3. daily_signal_review.csv 行数
4. 最新交易日日期
5. 最新交易日 signal_window=5 的 Q/G 状态、signal_label、action_hint、confidence_level、explanation
6. confidence_level 分布
7. action_hint 分布
8. 确认旧数据未修改
