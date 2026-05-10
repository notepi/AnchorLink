# 二次审计：历史画像 V2 — 锚定个股的历史性格档案

## 一、总体结论

`history_personality_profile_plan.md` 已经吸收了上一版审计中的大部分关键意见。当前方案不再只是概念描述，而是接近可实施的规格文档。

结论：

- **产品定位成立**：历史画像负责描述过去，今日判断交给后续今日慢面板。
- **三个新增能力成立**：`PersonalitySummary`、`RelationshipProfile`、`PathPattern` 仍然是最有价值的新增模块。
- **P0 问题大多已补齐**：性格摘要生成、关系画像算法、与 `operator_playbook` 的边界、后端集成位置都已有明确方案。
- **仍需实施前小修订**：主要集中在关系分类优先级、统计口径、模型复用方式和前端落地节奏。

当前状态建议定为：**可以进入实现准备，但先补齐少量工程细节**。

## 二、已解决的问题

### 1. 与现有系统边界已清晰

原审计指出方案和 `OperatorHistoryView` / `history_operator_playbook.json` 大面积重叠，且没有说明废弃、迁移还是并存。

当前 plan 已明确：

- `history_operator_playbook.json` 和 `OperatorHistoryView` **不废弃**。
- 它们继续作为"今日慢面板"候选数据源。
- 新增 `HistoryPersonalityProfile`，作为纯历史画像数据源。
- `/history` 首屏读取 `history_personality_profile.json`。
- 今日判断类组件移入折叠的 legacy/debug 区，后续迁到今日慢面板。

评价：这个边界定义是合理的。历史画像和今日判断终于分开，不再互相抢职责。

### 2. `PersonalitySummary` 生成逻辑已补齐

原审计指出一句话性格总结是门面功能，但生成方式缺失。

当前 plan 已定义：

- V1 使用 `rule_template_v1`。
- 不使用 LLM。
- 输入包括 top like、top dislike、top counter-intuitive、top trap、产业链关系、样本量和稳定性。
- `primary_trait` 有明确规则，如产业链跟随型、产业链领先型、背离修复型、高误判型、样本观察型。

评价：V1 用规则模板是正确选择。它可复现、可测试，也避免过早引入 LLM 的解释漂移。

### 3. `RelationshipProfile` 算法已从概念变成规则

原审计指出 `follows/leads/lags/mean_reverts/diverges/unstable` 没有判断标准。

当前 plan 已补充：

- `same_day_corr`
- `anchor_leads_corr`
- `anchor_lags_corr`
- `avg_relative_strength`
- 跑赢/跑输极端阈值
- 修复率和延续率
- 每种 relation 的初始阈值
- 高/中/低置信度规则

评价：方向正确，已具备实现基础。但仍需补一个分类优先级，见后文阻塞项。

### 4. 样本量和过拟合约束已明显加强

原审计指出 90 天数据、20+ 信号、多象限拆分会带来严重多重比较风险。

当前 plan 已补充：

- `count < 5` 不进入主画像。
- `5 <= count < 10` 只能作为观察线索。
- `10 <= count < 20` 不能进入 headline。
- `count >= 20` 才能作为 headline 候选。
- permutation p-value。
- Benjamini-Hochberg FDR。
- `effect_score = avg_next_1d_delta_pp * min(1, sqrt(count / 20))` 做小样本收缩。

评价：这已经能显著降低小样本误导。后续可以再升级 block permutation，但 V1 不必一开始做满。

### 5. 时间稳定性已补上

原审计指出方案把历史区间当作均匀样本，忽略个股性格变化。

当前 plan 已补充：

- early / recent 切分。
- recent 默认最近 30 个有效交易日。
- 对主要 pattern 分别计算早期和近期 effect。
- 方向相反或差异过大标记为 `changed`。
- headline 必须提示近期行为变化。

评价：作为 V1 足够。突变点识别可以留到 V2。

### 6. 前端改造范围已具体化

原审计指出 `/history` 下组件多，方案没有说明保留、删除、重写。

当前 plan 已列出：

- 哪些今日判断组件移入折叠区。
- 哪些纯统计组件保留到明细区。
- 哪些新增画像组件。
- 首屏展示顺序。
- 前端文案禁用词和推荐表达。

评价：范围已经明确。不过实际实施建议拆阶段，避免一次性重构过大。

## 三、仍需修订的阻塞项

### P0：补充 `RelationshipProfile` 分类优先级

当前 plan 定义了各 relation 的阈值，但没有说明多个条件同时满足时如何裁决。

例如：

- 同时满足 `same_day_corr >= 0.35` 和极端跑输后修复率高，是 `follows` 还是 `mean_reverts`？
- 有效样本 `< 20` 时，`unstable` 是否直接覆盖所有关系？
- early/recent 分类不一致时，是输出 `unstable`，还是输出主关系并标记 `stability: changed`？

建议补充固定优先级：

```text
insufficient sample -> unstable
early/recent strong conflict -> unstable 或 changed
lead/lag 显著优势 -> leads/lags
mean reversion 条件显著 -> mean_reverts
same-day corr 显著 -> follows
low corr + persistent excess/divergence -> diverges
otherwise -> unstable
```

并明确 `relation` 和 `stability` 的关系：

- `relation` 描述全样本主关系。
- `stability` 描述该关系是否跨时间稳定。
- 只有样本不足或关系完全不可判定时，`relation = unstable`。

### P0：明确 baseline 和 excess 的统计口径

当前 plan 多处使用：

- `avg_next_1d_delta_pp`
- `avg_next_1d_excess`
- `baseline_avg_next_1d`
- `group_median`

但需要明确口径，否则实现时会产生不一致。

建议补充：

- `baseline_avg_next_1d` 是全体有效历史日的锚定股次日均值。
- `avg_next_1d_delta_pp = pattern_avg_next_1d - baseline_avg_next_1d`。
- `avg_next_1d_excess = pattern_anchor_next_1d - pattern_group_median_next_1d`。
- `group_median` 对不同参照池分别计算，不能混用产业链 median。

### P0：明确各参照池数据来源

`RelationshipProfile` 要计算锚定股 vs 产业链、主题池、主线池、交易观察池，但 plan 还没有指明每个池从哪些字段或产物取值。

建议在后端设计中补一张表：

| 参照对象 | 数据来源 | 日收益字段 | 样本过滤 |
|----------|----------|------------|----------|
| 产业链 | existing history rows / chain members | group median return | 和锚定股同日有效 |
| 主题池 | theme pool history | theme median return | 同日有效 |
| 主线池 | core pool history | core median return | 同日有效 |
| 交易观察池 | watchlist history | watchlist median return | 同日有效 |

如果某个池当前没有稳定历史序列，应允许输出：

```text
relation = unstable
confidence = low
stability = insufficient
evidence = ["样本或参照池历史序列不足"]
```

## 四、仍需注意的非阻塞风险

### 1. `PersonalityPattern` 与 `OperatorSignalRole` 仍有重复风险

原审计建议合并模型。当前 plan 选择保留 `PersonalityPattern`，理由是两者语义不同：

- `PersonalityPattern` 面向过去习惯。
- `OperatorSignalRole` 面向今日判断。

这个选择可以接受，但要避免重复实现统计逻辑。

建议：

- 输出模型可以分开。
- 底层计算函数必须复用。
- 反直觉、陷阱、条件效果的判定不要复制一份新逻辑。

否则未来会出现同一信号在画像页和操盘页结论不一致的问题。

### 2. permutation 检验可能低估时间序列风险

当前 plan 使用随机标签置换 + BH FDR，这是比原方案强很多的进步。

但金融时间序列存在自相关和市场状态聚集，普通随机置换会打散时间结构，可能低估显著性风险。

建议 V1 保留当前方案，但在文档中注明：

- V1 使用普通 permutation，主要用于小样本降噪。
- V2 可升级为 block permutation 或 rolling bootstrap。

### 3. 前端一次性改造风险偏高

plan 现在包含：

- 重写 `/history` 首屏。
- 新增 6 个画像组件。
- 移动大量今日判断组件。
- 保留完整明细区。

建议实施拆成两阶段：

1. 后端先生成 `history_personality_profile.json`，前端新增画像区，但不大规模搬迁 legacy 组件。
2. 确认数据和文案稳定后，再重排 `/history` 信息架构。

这样可以先验证历史画像是否真的有解释力，再做页面大改。

### 4. `PathPattern` 还缺少路径风险字段

当前 `PathPattern` 只有 `avg_path`、`summary`、`confidence`。页面结构中提到最好/最差路径、最大不利路径、最大有利路径，但模型没有对应字段。

建议补充可选字段：

```typescript
best_path?: PathPoint[];
worst_path?: PathPoint[];
max_adverse_excess?: number | null;
max_favorable_excess?: number | null;
```

如果 V1 不做，也应明确路径画像只展示平均路径，MAE/MFE 类字段留到后续。

## 五、更新后的建议修改清单

| 优先级 | 修改项 | 状态 |
|--------|--------|------|
| **P0** | 明确 `PersonalitySummary.headline` 的生成算法 | 已解决 |
| **P0** | 定义 `RelationshipProfile` 的判断算法 | 基本解决 |
| **P0** | 补充 `RelationshipProfile` 多条件命中时的分类优先级 | 待补 |
| **P0** | 明确 baseline、delta、excess、group median 的统计口径 | 待补 |
| **P0** | 明确产业链/主题池/主线池/交易池的数据来源 | 待补 |
| **P0** | 明确和 `operator_playbook` 的边界 | 已解决 |
| **P1** | 合并 `EnvironmentPattern` 和 `SignalHabit` 为统一模型 | 已由 `PersonalityPattern` 变体解决 |
| **P1** | 补充样本量约束下的降级策略 | 已解决 |
| **P1** | 补充过拟合风险讨论和多重比较校正 | 已解决 |
| **P1** | 说明后端在 orchestrator 中的集成位置 | 已解决 |
| **P1** | 避免 `PersonalityPattern` 和 `OperatorSignalRole` 重复实现统计逻辑 | 待补 |
| **P2** | 补充时间维度：滚动窗口性格稳定性 | 已部分解决 |
| **P2** | 明确前端改造范围 | 已解决 |
| **P2** | 前端实施拆成 MVP / 完整迁移两阶段 | 建议补充 |
| **P2** | `best_condition` / `worst_condition` 改为结构化数据 | 已解决 |
| **P2** | `PathPattern` 补充最好/最差/最大不利/最大有利路径字段 | 建议补充 |

## 六、最终判断

当前 plan 已经通过主要产品审计：方向清楚、边界清楚、核心能力有价值，且多数统计风险已有约束。

但在进入编码前，建议先补齐三个 P0 工程细节：

1. `RelationshipProfile` 分类优先级。
2. baseline / excess / group median 的统一统计口径。
3. 四类参照池的数据来源和缺失降级策略。

补完这三项后，可以按后端优先的方式实施：

1. 先生成 `history_personality_profile.json`。
2. 加测试验证样本量、显著性、关系分类和稳定性。
3. 再做 `/history` 首屏画像化改造。

整体评价：**方案已经从“需要补 P0 才能实施”升级为“补少量工程口径后即可实施”**。
