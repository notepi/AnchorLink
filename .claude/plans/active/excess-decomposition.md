# Q5 极热负超额来源拆解分析

## Context

标准指数超额画像已完成，核心发现：Q5 极热后未来超额倾向于为负（相对回落）。但"负超额"的来源未拆解——是 Anchor 跌了？Anchor 涨了但涨得少？指数涨了而 Anchor 横盘？本分析拆解负超额的构成，回答交易含义。

## 输入（只读）

已有画像产物，不重新计算信号/分档/标签：

| 文件 | 关键列 |
|------|--------|
| `signal_daily.csv` | date, index_id, signal_window, standard_excess, signal_quality_status, asof_grade, asof_grade_label |
| `forward_labels.csv` | date, index_id, holding_window, future_anchor_return, future_index_return, future_excess, label_quality_status |

输入目录：`data/price/analytics/index_excess_profiles/constant_universe_2026-05-06/`

## 输出

同一目录下新增两个文件：

| 文件 | 格式 | 说明 |
|------|------|------|
| `excess_decomposition_daily.csv` | 长表 | 每行 = (date, index_id, signal_window, holding_window)，含分解桶标签 + is_non_overlapping 标记 |
| `excess_decomposition_profile.csv` | 宽表 | 每行 = 完整分组，含所有桶的 count/rate，含 evaluation_mode |

## 分解桶定义

### flat 阈值

`FLAT_THRESHOLD = 0.5`（%）。|future_anchor_return| ≤ 0.5% 视为"横盘"。

### 负超额（future_excess < 0）

| 桶 | 条件 | 含义 |
|----|------|------|
| `anchor_down_index_up` | anchor_ret < -0.5 且 index_ret > 0 | Anchor 跌 + 指数涨，最痛 |
| `anchor_down_index_down_less` | anchor_ret < -0.5 且 index_ret < -0.5 且 anchor_ret < index_ret | 双跌但 Anchor 跌更多 |
| `anchor_up_index_up_less` | anchor_ret > 0.5 且 index_ret > 0.5 且 anchor_ret < index_ret | 双涨但 Anchor 涨更少 |
| `anchor_flat_index_up` | \|anchor_ret\| ≤ 0.5 且 index_ret > 0 | Anchor 横盘 + 指数涨 |
| `other_negative_excess` | 其余 future_excess < 0 | 兜底 |

### 正超额（future_excess ≥ 0）

| 桶 | 条件 | 含义 |
|----|------|------|
| `anchor_up_outperform` | anchor_ret > 0.5 且 index_ret > 0.5 且 anchor_ret > index_ret | 双涨 Anchor 涨更多 |
| `anchor_down_index_down_more` | anchor_ret < -0.5 且 index_ret < -0.5 且 anchor_ret > index_ret | 双跌但指数跌更多 |
| `anchor_flat_index_down` | \|anchor_ret\| ≤ 0.5 且 index_ret < 0 | Anchor 横盘 + 指数跌 |
| `other_positive_excess` | 其余 future_excess ≥ 0 | 兜底 |

### 分类优先级

flat 判断优先（|anchor_ret| ≤ 0.5% 先匹配），然后按 sign 组合分类，最后兜底。

## 筛选条件

- `index_id = industry_chain_index`（主基准）
- `grade_mode = asof`
- `quality_scope = usable`：`signal_quality_status ∉ [insufficient_data, no_future_label]` 且 `label_quality_status ∉ [insufficient_data, no_future_label]`
- `asof_grade > 0`（排除 insufficient_grade_history）
- `future_excess` 非空
- 重点分析 grade=5（极热），grade=1（极冷）作对照

## evaluation_mode

`all_signals`：所有符合条件的信号日均纳入。

`non_overlapping`：按时间顺序，每组内相邻样本间隔 ≥ H 个交易日（复用 `excess_profile.py` 的 non-overlapping 逻辑）。两组分别输出到 profile。

报告必须分别展示：
- Q5 5d×5d all_signals
- Q5 5d×5d non_overlapping
- Q5 5d×10d all_signals
- Q5 5d×10d non_overlapping

## 桶占比：双口径分母

每个桶输出两个比率：

```
bucket_rate_in_all_samples = bucket_count / sample_count
bucket_rate_in_negative_excess = bucket_count / negative_excess_count（负超额桶）
bucket_rate_in_positive_excess = bucket_count / positive_excess_count（正超额桶）
```

报告引用时需注明分母是"全部样本"还是"负/正超额样本"。

## 输出文件字段

### `excess_decomposition_daily.csv`

```
date, index_id, signal_window, holding_window,
grade_mode, grade, grade_label,
future_anchor_return, future_index_return, future_excess,
excess_sign,
decomposition_bucket,
signal_quality_status, label_quality_status,
is_non_overlapping
```

### `excess_decomposition_profile.csv`

```
index_id, signal_window, holding_window, grade_mode, grade, grade_label, evaluation_mode,
sample_count,
negative_excess_count, negative_excess_rate,
positive_excess_count, positive_excess_rate,
anchor_down_index_up_count, anchor_down_index_up_rate_in_all, anchor_down_index_up_rate_in_negative,
anchor_down_index_down_less_count, anchor_down_index_down_less_rate_in_all, anchor_down_index_down_less_rate_in_negative,
anchor_up_index_up_less_count, anchor_up_index_up_less_rate_in_all, anchor_up_index_up_less_rate_in_negative,
anchor_flat_index_up_count, anchor_flat_index_up_rate_in_all, anchor_flat_index_up_rate_in_negative,
other_negative_excess_count, other_negative_excess_rate_in_all, other_negative_excess_rate_in_negative,
anchor_up_outperform_count, anchor_up_outperform_rate_in_all, anchor_up_outperform_rate_in_positive,
anchor_down_index_down_more_count, anchor_down_index_down_more_rate_in_all, anchor_down_index_down_more_rate_in_positive,
anchor_flat_index_down_count, anchor_flat_index_down_rate_in_all, anchor_flat_index_down_rate_in_positive,
other_positive_excess_count, other_positive_excess_rate_in_all, other_positive_excess_rate_in_positive
```

## 核心模块

### 文件：`src/index_products/excess_decomposition.py`

```python
# 关键函数
def classify_decomposition_bucket(
    anchor_ret: float, index_ret: float, flat_threshold: float = 0.5
) -> str:
    """单行分类 → 桶名"""

def compute_decomposition_daily(
    signal_df: pd.DataFrame, label_df: pd.DataFrame,
    index_id: str = "industry_chain_index",
    flat_threshold: float = 0.5
) -> pd.DataFrame:
    """合并 signal + label → 逐行分类 + non-overlapping 标记"""

def compute_non_overlapping_flags(
    daily_df: pd.DataFrame
) -> pd.Series:
    """标记 is_non_overlapping，复用 excess_profile 的间隔逻辑"""

def compute_decomposition_profile(
    daily_df: pd.DataFrame
) -> pd.DataFrame:
    """按 (signal_window, grade, holding_window, evaluation_mode) 汇总 → 宽表一行一组"""

def build_excess_decomposition(input_dir: Path, output_dir: Path) -> dict:
    """主入口：读取 → 计算 → 写出 → 返回 manifest"""
```

### 复用

从 `src/index_products/excess_profile.py` 复用常量：`SIGNAL_WINDOWS`, `HOLDING_WINDOWS`, `GRADE_DEFS`, `STATUS_ORDER`。

non-overlapping 逻辑参考 `excess_profile.py` 的 `compute_non_overlapping_profile`，但此处只标记 `is_non_overlapping` 而非单独输出。

不修改 `excess_profile.py`。

## 脚本

### 文件：`scripts/build_standard_index_excess_decomposition.py`

- `sys.path.insert(0, str(ROOT))` 确保直接运行
- 读取已有画像产物，输出分解文件到同一目录
- 打印 manifest 摘要

## 测试

### 文件：`tests/test_standard_index_excess_decomposition.py`（10+ 项）

1. **桶互斥且穷尽**：对随机 anchor_ret/index_ret 组合，每个样本恰好落入一个桶
2. **anchor_down_index_up 条件**：anchor < -0.5, index > 0, excess < 0 → 必须是 anchor_down_index_up
3. **anchor_flat_index_up 条件**：|anchor| ≤ 0.5, index > 0, excess < 0 → 必须是 anchor_flat_index_up
4. **正超额桶正确**：anchor > 0.5, index > 0.5, anchor > index → anchor_up_outperform
5. **usable 筛选排除 insufficient_data 和 no_future_label**
6. **asof_grade=0 排除**：insufficient_grade_history 行不进入统计
7. **profile sample_count 求和 = daily 有效行数**：按 (signal_window, grade, holding_window, evaluation_mode) 检查
8. **industry_chain_index only**：输出不含其他 index_id
9. **分母一致性**：
   - negative bucket count 之和 = negative_excess_count
   - positive bucket count 之和 = positive_excess_count
   - negative_excess_count + positive_excess_count = sample_count
10. **non_overlapping 间隔**：is_non_overlapping=True 的行，同组内相邻日期间隔 ≥ H 个交易日
11. **双口径比率正确**：bucket_rate_in_all = bucket_count / sample_count；bucket_rate_in_negative = bucket_count / negative_excess_count

## 报告

### 文件：`docs/excess_backtest/standard_index_excess_decomposition.md`

回答 7 个问题：

1. **Q5 负超额最大来源桶是哪个？** 列出 Q5 × 5d信号 × 5d持有 的负超额桶占比（双口径）
2. **Q5 负超额来源随持有期变化吗？** 对比 5d vs 10d 持有
3. **Q1 正超额来源是什么？** Q1 × 5d × 5d 的正超额桶占比
4. **anchor_down_index_up 在 Q5 中占比多少？** 这是最痛的情况
5. **anchor_up_index_up_less 在 Q5 中占比多少？** "涨了但涨得少"——减仓而非做空
6. **Q5 负超额中"Anchor 涨但涨得少"vs"Anchor 跌"的比率**——决定交易含义是减仓还是做空
7. **综合交易含义**：根据分解结果，Q5 极热后的操作建议更偏减仓还是偏做空？Q1 极冷后呢？

每个问题必须同时展示 all_signals 和 non_overlapping 结果。

## 执行顺序

1. 创建 `src/index_products/excess_decomposition.py`
2. 创建 `scripts/build_standard_index_excess_decomposition.py`
3. 创建 `tests/test_standard_index_excess_decomposition.py`
4. 运行脚本 + 测试
5. 创建 `docs/excess_backtest/standard_index_excess_decomposition.md`

## 验证

```bash
uv run python scripts/build_standard_index_excess_decomposition.py
uv run pytest tests/test_standard_index_excess_decomposition.py -v
```

确认：
- `excess_decomposition_daily.csv` 和 `excess_decomposition_profile.csv` 生成
- 10+ 项测试全部通过
- 报告包含 Q5 5d×5d 负超额桶占比数值（all_signals + non_overlapping）
