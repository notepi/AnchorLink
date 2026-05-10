# 四次审计：history_personality_profile_impl.md

## 总体结论

最新版 `history_personality_profile_impl.md` 已经回到最初目标：

> 把 `/history` 从“历史统计 + 今日判断混合工作台”，改造成一份 **锚定个股的历史性格档案**。

它现在同时钉住了三件事：

```text
产品目标 = 历史性格档案
呈现目标 = 接近 history-personality-profile-mockup.png 的结构、密度和阅读路径
视觉皮肤 = 当前 Web 暗色 anchor-* 体系
```

这版已经可以作为实施计划推进。相比上一版，关键方向都已修正：

- 标题不再被“复刻”牵着走。
- 明确只描述过去，不判断今天。
- 明确 mockup 是结构和呈现目标。
- 明确今日判断组件进入底部折叠区。
- 后端补齐 `summary_metrics`、完整 `RelationshipProfile`、多事件类型 `PathPattern`。
- 前端从 2x2 卡片网格改为顶部摘要、横排指标、左右两列、底部明细。
- `RelationshipProfile.evidence` 和 `PathPattern.summary` 都要求可读中文结论。

剩余问题主要是实现口径细节。建议在开工前补下面几项，避免实施时出现参数不够、验收误判或指标语义不清。

## 已通过项

### 1. 产品目标清楚

第一部分已经明确：

- `/history` 是历史性格档案。
- 只描述过去。
- 不判断今天。
- 最终结构接近 mockup。
- 暗色皮肤保持全站一致。

这正是当前目标。

### 2. 今日判断隔离已写入计划

文档明确把：

- `operator-decision-panel`
- `operator-playbook-panel`
- `today-history-mapping-panel`
- 今日结论
- 交易建议
- 确认/失效条件

移出主叙事，放入底部折叠区。这能避免 `/history` 再次变成“历史统计 + 今日判断混合工作台”。

### 3. 后端补齐方向正确

当前三块后端工作是必要的：

- `PersonalitySummaryMetrics` 解决顶部指标空缺。
- 完整 `RelationshipProfile` 解决四池关系重复和解释力不足。
- 多事件类型 `PathPattern` 解决路径画像全 null 和事件覆盖窄的问题。

### 4. 前端呈现目标正确

当前前端结构已经对齐 mockup 的核心阅读路径：

1. 顶部通栏档案摘要。
2. 横排关键指标。
3. 左列：喜欢、讨厌、产业联动。
4. 右列：反直觉、陷阱、路径。
5. 底部完整统计明细。

这比原先 2x2 dashboard 卡片网格正确很多。

## 仍需补准的点

### P0：PathPattern 的输入参数还不够明确

文档写：

```text
build_personality_profile 签名增加 event_paths: list[EventPath]
```

但后面又写事件来源包括：

```text
极强正向背离：ExtremeDivergence 中 divergence > threshold 的日期
极强负向背离：ExtremeDivergence 中 divergence < -threshold 的日期
```

这里有一个实现冲突：如果 `build_personality_profile` 只接收 `event_paths`，它拿不到 `ExtremeDivergence.divergence`，也就无法区分正向/负向背离。`event_paths` 里只有 `event_date`、`offset`、`anchor_return`、`chain_median`、`excess`，没有原始 divergence 分类。

建议二选一：

1. `build_personality_profile` 增加参数：

```python
extreme_divergences: list[ExtremeDivergence]
event_paths: list[EventPath]
```

2. 或不传 `ExtremeDivergence`，直接从 `HistoryRow` 计算：

```python
divergence = anchor_return - industry_chain_median
```

然后用 `divergence_threshold` 参数筛正/负极端背离。

更推荐方案 1，因为已有 `find_extreme_divergences` 的产物，避免重复口径。

### P0：`median_adverse_3d_proxy` 计算描述仍有歧义

文档写：

```text
valid rows 的 next_3d_return 中最差值的中位数
```

“最差值的中位数”语义不清。到底是：

- 所有负向 `next_3d_return` 的中位数？
- 每个样本窗口内最差路径的中位数？
- 全样本最低若干分位数？

由于当前没有逐日 forward path，建议明确为：

```text
median_adverse_3d_proxy = median([r.next_3d_return for r in valid if r.next_3d_return < 0])
```

如果负样本为空，则返回 `None`，并在 `sample_warnings` 中说明“不利样本不足”。

前端文案建议叫：

```text
T+3 不利回报
```

不要叫“最大回撤”。

### P1：验证标准“各不相同”过严

文档验证步骤写：

```text
4 池子 avg_relative_strength、same_day_corr、relation 各不相同
```

这个验收过严。真实数据里四个池子的 `relation` 有可能合理地相同，比如都偏 `follows`。我们要防的是“因为字段映射 bug 导致全部完全一样”，不是要求真实关系一定不同。

建议改成：

```text
4 池子使用各自 group_median / relative_strength 口径计算；
不得因复用同一字段导致 avg_relative_strength、corr、evidence 完全重复。
relation 可以相同，但 evidence 和底层统计应反映各自参照池。
```

### P1：`summary_metrics` 6 个字段“均非 null”也过严

验证步骤写：

```text
summary_metrics 6 个字段均非 null
```

这个也可能误伤正常情况。例如：

- 没有负收益样本时，`payoff_ratio` 或 `median_adverse_3d_proxy` 可能无法计算。
- 日收益标准差为 0 时，`sharpe_like_ratio` 应为 `None`。
- 样本不足时，某些指标应降级。

建议改成：

```text
summary_metrics 字段存在；
可计算字段非 null；
不可计算字段为 null 且 sample_warnings 给出原因。
```

### P1：PathPattern 字段语义需落在类型或注释里

文档写路径为“累计收益路径”，但现有模型字段仍是：

- `anchor_return`
- `chain_median`
- `excess`

如果实现继续使用这些字段，必须在模型注释、JSON 文档、前端 tooltip 中说明它们表示“相对 T0 的累计收益”，不是每日涨跌。

更稳的做法是改字段名：

```python
anchor_cum_return
chain_cum_return
excess_cum_return
```

这不是阻塞项，但能减少后续误用。

### P1：mockup 对齐验收可以更具体

当前验证写了：

- 顶部横幅档案感。
- 横排 6 指标可见。
- 左右两列。
- 表格行式。
- 暗色主题。

建议再补两条，避免做成“暗色但仍像 dashboard”：

- 第一屏主标题应为“历史性格档案/历史性格画像”，不再以“历史分析”为主标题。
- 筛选器不能抢占第一视觉，可以下沉、弱化或放入工具行。

这是当前真实页面最明显的问题之一。

## 建议修改摘要

建议对 `history_personality_profile_impl.md` 做以下小修：

1. `build_personality_profile` 输入明确增加 `extreme_divergences`，或明确从 `HistoryRow` 重新计算 divergence。
2. 把 `median_adverse_3d_proxy` 公式写成负向 `next_3d_return` 的中位数。
3. 验证标准从“四池关系各不相同”改为“不得因字段复用而完全重复”。
4. 验证标准从“summary_metrics 6 字段均非 null”改为“可计算字段非 null，不可计算字段有 warnings”。
5. 明确 PathPattern 字段是累计收益路径，最好改名。
6. 前端验收增加：主标题替换“历史分析”，筛选器弱化。

## 最终判断

当前 impl 已经不再走偏，可以进入实施准备。

它的合理定位是：

```text
/history 历史性格档案改造计划：
以后端完整档案数据为基础，
按 history-personality-profile-mockup.png 的结构、密度和阅读路径呈现，
并套用当前 Web 暗色视觉体系。
```

补完上述小修后，就可以按计划开工。
