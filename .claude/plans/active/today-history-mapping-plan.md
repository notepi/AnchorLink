# 今日历史映射 - 从当前状态到历史相似路径

## Summary

新增一个独立于“历史信号画像”的历史分析模块：**今日历史映射**。

它回答的问题是：

> 当前这组整体状态，在历史上更像哪些情景？类似情景之后，T+1 / T+3 / T+5 通常怎么走？

它不是预测器，也不输出买卖建议。它只展示历史条件分布和相似路径参考。

---

## 模块定位

### 和“历史信号画像”的分工

| 模块 | 回答的问题 | 粒度 |
|---|---|---|
| 历史信号画像 | 单个信号历史上是什么性格？ | 单信号 |
| 今日历史映射 | 当前整组状态历史上像什么？后续路径怎样？ | 多状态组合 |

### 本模块回答

- 当前状态在历史上属于什么类型？
- 有多少个历史相似样本？
- 相似样本之后 T+1 / T+3 / T+5 的平均收益、胜率、超额表现怎样？
- 最相似的历史日期有哪些？
- 主要相似原因是什么？

### 本模块不回答

- 今天要不要买？
- 今天是否应该卖？
- 是否可以进场、追高、抄底？
- 是否构成确定预测？

---

## 数据方案

v1 不改后端 schema，直接复用 `history_summary.csv` 对应的 `HistorySummaryRow[]`。

### 目标日

“今日”在历史页中定义为：

> 当前筛选区间内的最新有效日期。

这样既能表达今天，也能支持回看任意历史日期。

目标日要求：

- `data_quality_status !== 'insufficient_data'`
- 有基本状态字段：`industry_beta`、`anchor_alpha`、`risk_level`
- 可解析 `signal_pairs` 或至少有 `signal_labels`

### 候选样本

候选样本为目标日之前的历史行：

- 日期早于目标日
- `data_quality_status !== 'insufficient_data'`
- 至少有一个前瞻收益：`next_1d_return` / `next_3d_return` / `next_5d_return`

不使用目标日之后的数据，避免未来函数。

---

## 相似匹配方法

采用“状态 + 信号相似”的 v1 口径。

### 状态底座

参与匹配的状态字段：

- `industry_beta`
- `anchor_alpha`
- `risk_level`
- `strongest_group`
- `weakest_group`

状态匹配分占总相似度 60%。

### 信号相似

从 `signal_pairs` 解析信号集合，计算目标日和候选日的 Jaccard 相似度：

```text
matchedSignals / unionSignals
```

集合元素使用 `category + label` 对，而不是只使用 label。这样与现有 `history-analysis.ts` 中的 `parseSignalPairs()` / `extractLabelCategoryPairs()` 口径一致，也避免不同 category 下同名 label 被误算成同一信号。

当 `signal_pairs` 为空或解析失败时，回退到 `signal_labels`。回退时集合元素只能使用 label。

信号相似分占总相似度 40%。

### 状态相似评分

状态匹配分 `stateScore` 为五个状态字段的加权平均。只比较目标日和候选日都有值的字段；双方任一方为 `null` / 空字符串时，该字段不参与分母。若所有状态字段都不可比，则 `stateScore = 0`。

| 字段 | 权重 | 规则 |
|---|---:|---|
| `industry_beta` | 25% | `positive/neutral/negative` 有序评分：相同 1；`positive` vs `neutral` 或 `negative` vs `neutral` 为 0.5；`positive` vs `negative` 为 0 |
| `anchor_alpha` | 25% | 同 `industry_beta` |
| `risk_level` | 20% | `low/medium/high` 有序评分：相同 1；相邻为 0.5；`low` vs `high` 为 0 |
| `strongest_group` | 15% | 字符串完全相同为 1，否则 0；v1 不做语义映射 |
| `weakest_group` | 15% | 字符串完全相同为 1，否则 0；v1 不做语义映射 |

字段值比较前做 `trim()` 和小写化。未知枚举值按无序分类处理：完全相同为 1，否则 0。

### 总分

```text
similarity = stateScore * 0.6 + signalJaccard * 0.4
```

相似样本按 `similarity` 降序排序。

v1 参与路径统计的样本数采用自适应规则：

```text
sampleSize = clamp(round(candidateCount * 0.15), 5, 12)
```

即候选较少时不强行固定 12 个，候选充足时最多取 Top 12，避免过度稀释相似性。组件 v1 先不暴露调节控件。

最低有效样本数为 5 个；少于 5 个时不生成路径参考。

---

## 输出内容

### 当前状态摘要

展示目标日整体状态：

- 日期
- Beta / Alpha 象限
- 风险等级
- 最强组 / 最弱组
- 核心信号 Top N

示例：

```text
当前状态：行业中性 + 个股偏弱 + 中风险
强弱结构：主题池强，产业链弱
核心信号：行业 Beta 为中性、个股 Alpha 为负、主力资金拖累
```

### 历史路径统计

对相似样本计算：

| 窗口 | 指标 |
|---|---|
| T+1 | 平均收益、胜率、平均超额 |
| T+3 | 平均收益、胜率、平均超额 |
| T+5 | 平均收益、胜率、平均超额 |

不做 T+10。当前 `HistoryRow` 只有 T+1 / T+3 / T+5。

平均超额字段明确使用：

- T+1：`next_1d_excess_vs_chain`
- T+3：`next_3d_excess_vs_chain`
- T+5：`next_5d_excess_vs_chain`

### 路径标签

根据相似样本路径生成一个解释标签：

- **强势延续**：T+1、T+3、T+5 平均收益均 `> 0`，且三个窗口胜率均 `>= 55%`
- **弱势修复**：T+1 或 T+3 平均收益 `> 0.3%`，但 T+5 平均收益 `<= 0` 或 T+5 胜率 `< 50%`
- **冲高回落**：T+1 平均收益 `> 0.5%`，且 T+5 平均收益较 T+1 回落至少 `0.7%`
- **继续走弱**：至少两个窗口平均收益 `< -0.3%`
- **分化震荡**：三个窗口平均收益绝对值均 `< 0.2%`，且胜率均在 `45% ~ 55%`
- **样本分歧**：不满足以上规则时使用的兜底标签

标签只描述历史路径，不写成预测。

### 相似历史案例

展示 Top 5 相似日期：

- 日期
- 相似度
- 匹配状态
- 匹配信号
- 后续 T+1 / T+3 / T+5 收益

---

## 前端实现方案

### 新增派生函数

新增独立文件，避免继续膨胀已有 1000+ 行的 `history-analysis.ts`：

```text
web/src/lib/today-history-mapping.ts
```

导出：

```typescript
deriveTodayHistoryMapping(
  summary: HistorySummaryRow[],
  targetDate?: string
): TodayHistoryMapping | null
```

默认 `targetDate` 为传入 summary 中最新有效日期。

实现要求：

- 不修改输入数组和行对象。
- 只做前端派生，不改后端 schema。
- 复用或迁移现有信号解析 helper 时，保持单一来源，避免复制两套解析逻辑。

### 新增类型

建议作为 `web/src/lib/today-history-mapping.ts` 的导出类型；若后续多个模块复用，再迁移到 `web/src/types/index.ts`。

```typescript
interface HistoricalPathStat {
  window: '1d' | '3d' | '5d';
  avgReturn: number | null;
  winRate: number | null;
  avgExcess: number | null;
}

interface SimilarHistoryCase {
  date: string;
  similarity: number;
  matchedSignals: Array<{ category: string | null; label: string }>;
  matchedStateFields: string[];
  next1d: number | null;
  next3d: number | null;
  next5d: number | null;
}

interface TodayHistoryMapping {
  targetDate: string;
  sampleCount: number;
  pathLabel: string;
  stateSummary: string;
  coreSignals: string[];
  pathStats: HistoricalPathStat[];
  similarCases: SimilarHistoryCase[];
  notes: string[];
}
```

### 新增组件

建议新增：

```text
TodayHistoryMappingPanel
```

展示位置：

```text
OperatorPlaybookPanel
TodayHistoryMappingPanel
OperatorSignalInsights
QuadrantSignalBreakdown
OperatorCombinationSummary
```

也就是插入在 `OperatorPlaybookPanel` 之后、`OperatorSignalInsights` 之前。

组件内使用 `useMemo` 包裹派生计算：

```typescript
const mapping = useMemo(
  () => deriveTodayHistoryMapping(summary, targetDate),
  [summary, targetDate]
);
```

标题：

```text
今日历史映射
```

副标题：

```text
把选定日期的整体状态放回历史样本中，观察相似状态后的路径分布，不代表预测。
```

### 空状态

样本不足时显示：

```text
相似历史样本不足，暂不生成路径参考。
```

不要回退到全样本平均，避免制造虚假的参考价值。

空状态容器需要保留标题和说明，避免筛选后整块 UI 突然消失。

### 可访问性

- 路径统计表使用语义化表格或明确的 `aria-label`。
- 相似案例列表中的相似度、收益、胜率不只依赖颜色表达。
- 所有可交互控件支持键盘聚焦；v1 如无交互控件，则不增加额外 tab stop。

---

## 文案边界

允许使用：

- 历史相似
- 路径参考
- 样本分布
- 后续表现
- 类似状态
- 平均收益
- 胜率
- 超额表现

禁止使用：

- 预测
- 买入
- 卖出
- 进场
- 下单
- 抄底
- 追高
- 确定上涨
- 确定下跌

---

## 验收标准

- 用户能看懂：这是把当前状态映射回历史，而不是生成交易指令。
- 页面清楚展示相似样本数，样本不足时不强行给结论。
- 输出包含 T+1 / T+3 / T+5 的平均收益、胜率、平均超额。
- 能展示最相似历史日期及匹配信号。
- 不引入未来函数：目标日之后的数据不能参与相似样本。
- 不修改后端 schema，v1 只做前端派生和展示。
- 页面不出现“预测 / 买入 / 卖出 / 进场 / 下单”等操作性文案。
- 相似匹配逻辑不继续塞进 `history-analysis.ts`，新增逻辑保持在独立模块内。
- 路径统计表和相似案例不只依赖颜色表达正负或强弱。

---

## 测试计划

### 纯函数测试

- 相似度排序：状态相同且信号重合更高的样本排在前面。
- 样本过滤：目标日之后的数据不会进入候选样本。
- 样本不足：有效相似样本少于 5 时返回 `null` 或空状态。
- 路径统计：T+1 / T+3 / T+5 均值、胜率、超额计算正确。
- 信号解析：优先解析 `signal_pairs`，解析失败时回退 `signal_labels`。
- 状态评分：有序枚举相邻得 0.5，相反得 0，null 字段不进入分母。
- 样本数量：候选样本数分别覆盖少于 5、5-80、80 以上时的自适应 Top N。
- 路径标签：覆盖强势延续、弱势修复、冲高回落、继续走弱、分化震荡、样本分歧。

### 页面验证

- 历史页能正常渲染 `TodayHistoryMappingPanel`。
- 调整日期筛选后，目标日随筛选区间最新有效日期变化。
- 样本不足时展示空状态。
- 深色 UI 下数字颜色和标签可读。
- 筛选变更时组件通过 `useMemo` 派生，不在 render 中重复执行裸计算。

---

## 改动文件预估

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `web/src/lib/today-history-mapping.ts` | 新增 | 相似匹配、路径统计、导出类型 |
| `web/src/lib/history-analysis.ts` | 可选小改 | 只在需要复用/导出信号解析 helper 时调整，不新增主逻辑 |
| `web/src/types/index.ts` | 可选小改 | 仅当类型需要跨模块复用时集中定义 |
| `web/src/components/history/today-history-mapping-panel.tsx` | 新增组件 | 展示今日历史映射 |
| `web/src/components/history/history-dashboard.tsx` | 小改 | 接入新组件 |

v1 不修改：

- Python 历史分析后端
- `HistoryRow` / `history_summary.csv` schema
- 当前 dashboard snapshot 数据流
