# 标准指数超额画像分析 — 返工修复

## Context

首轮实现已完成并通过 15 项测试，但用户抽查发现 5 个影响解释的问题，需要返工修复。

## 修复项

### 1. sample_count 高估（最关键）
未来标签为空的行仍进入 profile 统计的 sample_count。修复：`compute_forward_labels` 中，超出数据范围的行 `label_quality_status` 设为 `no_future_label`；`_quality_scope` 和所有统计函数将 `no_future_label` 视同 `insufficient_data` 排除。

文件：`src/index_products/excess_profile.py`
- `compute_forward_labels`：超出范围的行设 `label_quality_status = "no_future_label"`
- `_quality_scope`：`no_future_label` → excluded
- `compute_label_quality`：已有 `no_future_label` 的行不覆盖
- **`no_future_label` 不进入 usable，也不进入 strict_ok_only。** quality_sensitivity、benchmark_comparison、grade_profile、non_overlapping_profile 都统一排除。
- **报告里的样本数必须使用"有效 future_excess 非空样本数"**，不能使用分档行数。例如 industry_chain_index / asof / 5d信号 / 10d持有 / Q5 原先是 30，修复后应接近 22。

### 2. signal_quality_status 窗口少算一天
N 日收益 = close(t)/close(t-N)，质量区间应为 [t-N, t]（含两端）。当前代码 `start_pos = max(0, pos - sw + 1)` 只覆盖了 [t-N+1, t]。

修复：`start_pos = max(0, pos - sw)`

文件：`src/index_products/excess_profile.py` → `compute_signal_quality`

### 3. 报告措辞修正
修复后重新检查报告中所有"动量延续"字样。除非是在解释"过去信号继续升温"，否则涉及 Q5 后未来超额为负的地方，一律改成：
- 极热后相对回落
- 过热降温
- 偏空/减仓信号

并明确不是绝对收益做空信号。这是相对超额的回落，不等于单票绝对做空一定赚钱。

文件：`docs/excess_backtest/standard_index_excess_profile.md`

### 4. 路径表分开展示
3.1 节自身路径和相对路径混在一起。分别展示两张表。

文件：`docs/excess_backtest/standard_index_excess_profile.md`

### 5. 测试强化
- 去掉 `or True`（Test 2 和 Test 5）
- non-overlapping 测试增加间隔断言
- Test 15 的 1d 质量测试改为验证 [t-N, t] 区间
- 新增：profile 中 sample_count 应等于有效 future_excess 的行数
- **quality_scope 命名保持和现有输出一致：`usable` / `strict_ok_only`，不要在代码或文档里混写 `usable_stats` / `strict_ok_only_stats`**

文件：`tests/test_standard_index_excess_profile.py`

## 修复后预期结论

```
极热 Q5：相对指数后续更容易回落，偏空/减仓信号较稳健。
极冷 Q1：短期有弱反弹，但不稳定。
注意：这是相对超额，不等于单票绝对做空一定赚钱。
```

## 验证

```bash
uv run python scripts/build_standard_index_excess_profile.py
uv run pytest tests/test_standard_index_excess_profile.py -v
```

关键验证：sample_count 不再高估

```bash
python3 - <<'PY'
import pandas as pd
base = 'data/price/analytics/index_excess_profiles/constant_universe_2026-05-06'
gp = pd.read_csv(f'{base}/grade_profile.csv')
print(gp[
    (gp.index_id=='industry_chain_index') &
    (gp.grade_mode=='asof') &
    (gp.quality_scope=='usable') &
    (gp.signal_window==5) &
    (gp.holding_window==10) &
    (gp.grade==5)
][['sample_count','future_excess_median','future_excess_positive_rate']])
PY
```

如果 `sample_count` 还显示 30，说明空标签仍混入统计；如果变成 22 左右，关键问题才算真修掉。
