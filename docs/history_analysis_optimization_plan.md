# 历史分析页面优化计划

## Context

当前 `/history` 页面已经能读取 `data/output/history_*.csv` 并展示趋势、象限、信号、极端背离、滚动指标和状态转移，但页面仍像“数据堆叠”，不够适合复盘使用。

需要优化的不是把它包装成交易终端，而是把它做成一个**清晰、克制、可验证的历史研究面板**：

1. 先展示样本内最重要的结论，再展示支撑数据。
2. 所有结论必须能追溯到 CSV 字段，不硬编码不可验证数字。
3. 明确样本限制：当前只有 96 个交易日、1 个锚定标的，结论只代表样本内表现。
4. 页面提供历史统计提示和风险提示，不输出直接买卖建议。

## Design Principles

1. **结论前置，但不过度承诺**
   - 首屏展示“样本内观察结论”，不写“买入/卖出/抄底”等指令式用语。
   - 文案使用“历史上表现较好/较差”“需继续验证”“样本有限”。

2. **口径清楚**
   - 指标旁边标明样本数、统计窗口和对比基准。
   - 当日超额收益使用 `relative_strength_vs_industry_chain` 或 `anchor_return - industry_chain_median`。
   - 次日前瞻超额使用 `next_1d_excess_vs_chain`，不得和当日超额混用。

3. **减少信息噪音**
   - 首屏只放核心结论、核心指标和主要趋势。
   - 辅助分析放在下方，不把所有表格同时堆到首屏。

4. **颜色服务于识别，不制造确定性**
   - 绿色表示样本内正收益/相对较好。
   - 红色表示样本内负收益/相对较差。
   - 灰色表示中性、基准或样本不足。

5. **交互先做必要项**
   - 优先做日期范围筛选、信号类别过滤。
   - 缩放拖拽、导出报告、折叠面板放到后续阶段。

## Scope

### In Scope

- 优化 `/history` 页面信息结构。
- 修复收益趋势图口径和展示问题。
- 新增核心结论区和核心指标区。
- 优化信号 lift 排行、四象限统计、极端背离列表、滚动指标说明。
- 增加日期范围筛选和信号类别过滤。

### Out of Scope

- 不做标的切换。当前系统 MVP 只有 `688333.SH 铂力特`。
- 不做直接交易建议。
- 不新增后端统计口径，除非页面明确需要且 CSV 当前无法支持。
- 不把页面宣传成 Bloomberg/Wind 级别终端。
- 不硬编码年化收益、最大回撤、波动率等当前 CSV 不提供的指标。

## Data Sources

页面只能依赖以下已生成数据：

| 文件 | 用途 |
|------|------|
| `history_summary.csv` | 日度收益、池子中位数、相对强弱、前瞻收益 |
| `history_quadrant_stats.csv` | 象限表现、胜率、前瞻收益 |
| `history_signal_lift.csv` | 信号出现次数、前瞻收益、胜率、lift |
| `history_extreme_divergences.csv` | 极端背离事件 |
| `history_event_study.csv` | 极端背离 T-5 到 T+5 路径 |
| `history_rolling_metrics.csv` | 5 日 / 10 日滚动超额和连续性指标 |
| `history_state_transitions.csv` | 状态转移概率 |

如果页面需要新增指标，优先在前端从现有 CSV 派生；无法可靠派生时，必须先扩展历史分析生成逻辑，而不是在页面硬写。

## Technical Architecture

### 筛选方案

采用**客户端容器组件 + 本地派生数据**方案。

原因：

- 当前 `/history` 页面一次性读取的 CSV 数据量很小（96 行级别），不需要为日期范围和信号类型过滤新增 API 查询。
- 日期范围筛选、信号类别过滤需要即时联动图表，用客户端状态实现最简单。
- 保留服务端读取 CSV 的优势：页面首次渲染仍由服务端读取文件，避免把文件读取逻辑放进浏览器。

实现方式：

1. `page.tsx` 保持服务端组件，负责读取全部历史数据。
2. 新增 `history-dashboard.tsx` 作为客户端组件，接收全部数据 props。
3. `history-dashboard.tsx` 内部用 `useState` 管理：
   - `startDate`
   - `endDate`
   - `signalCategory`
4. 所有图表和表格都使用筛选后的派生数据。

数据流：

```text
page.tsx (server)
  -> getHistorySummary / getQuadrantStats / getSignalLifts / ...
  -> <HistoryDashboard initialData={...} />

history-dashboard.tsx (client)
  -> filterHistoryData(...)
  -> deriveCoreMetrics(...)
  -> deriveConclusion(...)
  -> 子组件渲染
```

### 派生逻辑放置

为避免把计算逻辑塞进展示组件，新增：

- `web/src/lib/history-analysis.ts`

该文件只做纯函数派生：

- `filterSummaryByDateRange`
- `filterSignalsByCategory`
- `deriveSignalLiftsFromSummary`
- `deriveQuadrantsFromSummary`
- `deriveTransitionsFromSummary`
- `deriveCoreMetrics`
- `deriveConclusion`
- `deriveQuadrantHighlights`
- `deriveTransitionSummary`
- `deriveDivergenceFollowThrough`

展示组件只接收已经算好的 view model，不在组件里写复杂统计逻辑。

### 当前代码复用判断

现有组件不是推倒重来：

| 组件 | 当前状态 | 处理方式 |
|------|----------|----------|
| `history-trend-chart.tsx` | 已有趋势图，但当日超额/前瞻超额口径混在上下两图 | 修改为主图三线展示当日口径 |
| `signal-lift-table.tsx` | 已按 `avg_next_1d_delta_pp` 排序，已有样本不足标记 | 保留排序逻辑，新增类别过滤、Top/Bottom 高亮和字段收敛 |
| `quadrant-grid.tsx` | 已有 3x3 网格 | 增加最佳/最差象限高亮、5日均值和样本不足标记 |
| `divergence-timeline.tsx` | 已支持展开 T-5 到 T+5 | 增加 T+1/T+3 派生表现和倒序展示 |
| `rolling-metrics-chart.tsx` | 已展示 5/10 日滚动指标 | 增加指标解释，不改成 7/30 日 |
| `transition-heatmap.tsx` | 已有热力矩阵 | 增加自动摘要 |

## Page Structure

### 1. 顶部筛选区

位置：页面顶部。

功能：

- 日期范围筛选。
- 信号类别过滤：全部 / beta / alpha / volume / rotation / abnormal。
- 显示当前样本数量，例如“样本：96 个交易日，2025-12-09 ~ 2026-05-07”。

暂不做：

- 标的切换。
- 导出报告。

### 2. 样本内结论区

位置：首屏顶部，通栏。

内容：

- 一句话总结当前样本内最明显规律。
- 展示最佳场景和最差场景，但必须带样本数。
- 明确风险提示：样本有限、单标的、只代表历史样本内统计。

示例文案：

> 样本内观察：铂力特在当前 96 个交易日中呈现较强均值回归特征。`行业弱+个股弱` 场景样本 14 天，次日均值 +1.70%，胜率 64.3%；`行业强+个股弱` 场景样本 19 天，次日均值 -0.50%，胜率 42.1%。该结论仅用于复盘观察，需随样本扩展持续验证。

### 3. 核心指标区

位置：结论区下方，4 张指标卡。

指标卡建议：

1. **样本收益**
   - 日均收益
   - 中位数收益
   - 正收益天数占比

2. **相对行业**
   - 行业链日均中位数
   - 日均当日超额
   - 跑赢行业天数占比

3. **场景质量**
   - 最佳象限及样本数
   - 最差象限及样本数
   - 有效象限数量

4. **事件风险**
   - 极端背离次数
   - 最大正背离
   - 最大负背离

注意：

- 只展示能从 CSV 直接计算或稳定派生的指标。
- 不展示当前数据源没有的“最大回撤、波动率、年化收益”，除非先补充计算口径。

### 4. 收益趋势区

当前问题：

- 主图只显示两条线。
- 下方单独展示 `next_1d_excess_vs_chain`，容易让用户误以为是当日超额。

目标：

- 同一张主图展示三条线：
  - 铂力特当日收益：`anchor_return`
  - 行业链中位数：`industry_chain_median`
  - 当日超额：`relative_strength_vs_industry_chain`
- 图例明确区分“当日收益”和“前瞻收益”。
- tooltip 展示日期、三条线数值。

后续可选：

- 单独增加“前瞻收益”小图，展示 `next_1d_return` 和 `next_1d_excess_vs_chain`。

### 5. 信号 Lift 区

当前问题：

- 表格字段偏多，用户不容易看出排序依据。
- `lift_next_1d` 在 baseline 接近 0 时容易放大，单看 ratio lift 会误导。

目标：

- 默认只展示 `min_count_passed=true` 的信号。
- 排序默认使用 `avg_next_1d_delta_pp`，比 ratio lift 更直观。
- 保留字段：
  - 信号名称
  - 样本数
  - 次日均值
  - 相对基线差值 `delta_pp`
  - 胜率
- Top 3 正向信号轻微绿色高亮。
- Bottom 3 负向信号轻微红色高亮。
- 样本不足的信号放到折叠或二级视图，不参与默认排序。

文案限制：

- 不写“买入信号/卖出信号”。
- 使用“样本内正向信号/样本内风险信号”。

### 6. 四象限统计区

目标：

- 使用 3x3 网格展示 `industry_beta × anchor_alpha`。
- 每格展示：
  - 样本天数
  - 次日均值
  - 5 日均值
  - 胜率
  - 次日超额
- 自动识别最佳和最差象限：
  - 最佳：优先按 `avg_next_1d_delta_pp` 或 `avg_next_1d_excess`，其次看胜率和样本数。
  - 最差：同理反向。
- 样本数低于 5 的格子标记“样本少”。

### 7. 极端背离区

目标：

- 按事件日期倒序展示。
- 区分正向背离和负向背离。
- 每个事件展示：
  - 日期
  - 当日铂力特收益
  - 行业链中位数
  - 背离幅度
  - T+1 / T+3 后续表现
- 点击展开 T-5 到 T+5 路径。

注意：

- 不在页面上写“出货”“资金提前布局”等强因果词。
- 可写“后续回吐”“后续延续弱势”等可由数据直接支持的描述。

### 8. 滚动指标区

当前数据：

- `excess_5d`
- `excess_10d`
- `outperform_streak`
- `beta_streak`
- `theme_vs_core_streak`
- `risk_high_streak`

目标：

- 先按现有 5 日 / 10 日展示，不强行改成 7 日 / 30 日。
- 每个指标增加 tooltip 解释：
  - 5 日超额：过去 5 个交易日铂力特收益减行业链中位数的累计值。
  - 10 日超额：过去 10 个交易日累计超额。
  - 跑赢连续性：正数为连续跑赢，负数为连续跑输。
  - 高风险连续性：连续 risk=high 的天数。
- 异常值可按固定阈值提示，后续再做均值 ± 2 倍标准差。

### 9. 状态转移区

目标：

- 保留热力矩阵。
- 高概率转移格子高亮。
- tooltip 展示 `from_state -> to_state`、次数、概率。
- 在矩阵上方给出 2-3 条自动摘要，例如：
  - `行业弱+个股弱` 次日改善概率较高。
  - `行业强+个股弱` 次日继续弱势或恶化概率较高。

摘要必须由 `history_state_transitions.csv` 计算，不硬编码。

## Implementation Plan

### P0：先定架构和派生口径

新增：

- `web/src/components/history/history-dashboard.tsx`
- `web/src/lib/history-analysis.ts`

修改：

- `web/src/app/(main)/history/page.tsx`

验收：

- `page.tsx` 保持服务端组件。
- `history-dashboard.tsx` 是唯一持有筛选状态的客户端容器。
- 日期范围筛选后，至少趋势图、核心指标、结论卡片同步更新。
- 派生函数有明确输入输出，不依赖 React 状态。

### P1：修正确性和首屏结构

新增：

- `web/src/components/history/filter-bar.tsx`
- `web/src/components/history/conclusion-card.tsx`
- `web/src/components/history/core-metrics.tsx`

修改：

- `web/src/components/history/history-trend-chart.tsx`
- `web/src/components/history/signal-lift-table.tsx`
- `web/src/components/history/quadrant-grid.tsx`
- `web/src/lib/data-reader.ts`
- `web/src/types/index.ts`

验收：

- 首屏能看到样本区间、样本数量、样本内结论和核心指标。
- 收益趋势图三条线口径正确。
- 信号表默认按 `avg_next_1d_delta_pp` 排序。
- 页面不出现直接买卖建议。

### P2：完善研究体验

新增或优化：

- 日期范围筛选联动所有组件，而不只是首屏组件。
- 信号类别过滤。
- 极端背离事件展示 T+1 / T+3 后续表现。
- 滚动指标 tooltip 解释。
- 状态转移摘要。

验收：

- 筛选后所有组件数据一致更新。
- 筛选后样本数明确显示。
- 样本不足时有提示，不强行给结论。

### P3：增强功能

可选功能：

- 月度收益热力图。
- 前瞻收益独立图。
- 折叠/展开辅助区。
- 导出当前筛选后的研究摘要。
- 图表缩放或刷选区间。

## Critical Files

### 新增文件

- `/Users/pan/Desktop/research/0workspace/AnchorLink/web/src/components/history/history-dashboard.tsx`
- `/Users/pan/Desktop/research/0workspace/AnchorLink/web/src/components/history/filter-bar.tsx`
- `/Users/pan/Desktop/research/0workspace/AnchorLink/web/src/components/history/conclusion-card.tsx`
- `/Users/pan/Desktop/research/0workspace/AnchorLink/web/src/components/history/core-metrics.tsx`
- `/Users/pan/Desktop/research/0workspace/AnchorLink/web/src/lib/history-analysis.ts`

### 修改文件

- `/Users/pan/Desktop/research/0workspace/AnchorLink/web/src/app/(main)/history/page.tsx`
- `/Users/pan/Desktop/research/0workspace/AnchorLink/web/src/components/history/history-trend-chart.tsx`
- `/Users/pan/Desktop/research/0workspace/AnchorLink/web/src/components/history/signal-lift-table.tsx`
- `/Users/pan/Desktop/research/0workspace/AnchorLink/web/src/components/history/quadrant-grid.tsx`
- `/Users/pan/Desktop/research/0workspace/AnchorLink/web/src/components/history/divergence-timeline.tsx`
- `/Users/pan/Desktop/research/0workspace/AnchorLink/web/src/components/history/rolling-metrics-chart.tsx`
- `/Users/pan/Desktop/research/0workspace/AnchorLink/web/src/components/history/transition-heatmap.tsx`
- `/Users/pan/Desktop/research/0workspace/AnchorLink/web/src/lib/data-reader.ts`
- `/Users/pan/Desktop/research/0workspace/AnchorLink/web/src/types/index.ts`

## Derivation Rules

### 筛选规则

日期范围：

```text
filteredSummary = summary.filter(date >= startDate && date <= endDate)
```

日期筛选后的聚合口径：

```text
quadrants = deriveQuadrantsFromSummary(filteredSummary)
signals = deriveSignalLiftsFromSummary(filteredSummary, signalCategory)
transitions = deriveTransitionsFromSummary(filteredSummary)
rolling = rolling.filter(date in selected range)
divergences = divergences.filter(date in selected range)
events = events.filter(event_date in selected range)
```

原因：

- `history_quadrant_stats.csv`、`history_signal_lift.csv`、`history_state_transitions.csv` 都是全样本聚合结果。
- 用户选择日期范围后，不能简单过滤这些聚合表，否则页面会显示“筛选后的日期范围 + 全样本统计”的混合口径。
- P0/P1 实现可以先不开放日期范围筛选；一旦开放，以上聚合必须从 `filteredSummary` 重算。

信号类别：

```text
filteredSignals =
  signalCategory === "all"
    ? deriveSignalLiftsFromSummary(filteredSummary)
    : deriveSignalLiftsFromSummary(
        rows where signal_categories contains signalCategory
      )
```

说明：

- `history_signal_lift.csv` 是全样本统计结果，不能直接代表筛选后结果。
- 默认实现应重算筛选后的 signal lift，避免页面上显示的信号统计和日期范围不一致。

### 信号 Lift 重算公式

输入：`HistorySummaryRow[]`

基线：

```text
baseline_avg_next_1d = avg(next_1d_return)
baseline_win_rate_1d = count(next_1d_return > 0) / count(next_1d_return)
```

对每个 `signal_labels` 中出现的 label：

```text
appearance_count = count(rows containing label)
avg_next_1d = avg(next_1d_return for rows containing label)
avg_next_3d = avg(next_3d_return for rows containing label)
avg_next_5d = avg(next_5d_return for rows containing label)
avg_next_1d_excess = avg(next_1d_excess_vs_chain for rows containing label)
win_rate_1d = count(next_1d_return > 0) / count(valid next_1d_return)
avg_next_1d_delta_pp = avg_next_1d - baseline_avg_next_1d
lift_next_1d = avg_next_1d_delta_pp / abs(baseline_avg_next_1d)
lift_win_rate = win_rate_1d - baseline_win_rate_1d
min_count_passed = appearance_count >= 5
```

如果 `baseline_avg_next_1d` 为 0 或接近 0，页面默认展示 `avg_next_1d_delta_pp`，`lift_next_1d` 仅作为辅助字段。

### 象限重算公式

输入：`HistorySummaryRow[]`

象限：

```text
quadrant = classify(industry_beta, anchor_alpha)
```

对每个 3x3 象限固定输出：

```text
count = count(rows where next_1d_return is not null)
avg_next_1d = avg(next_1d_return)
avg_next_3d = avg(next_3d_return)
avg_next_5d = avg(next_5d_return)
avg_next_1d_excess = avg(next_1d_excess_vs_chain)
win_rate_1d = count(next_1d_return > 0) / count(valid next_1d_return)
avg_relative_strength = avg(relative_strength_vs_industry_chain)
```

筛选后仍固定输出 9 个象限，缺失象限 `count=0`，其他指标为 `null`。

### 状态转移重算公式

输入：按日期升序的 `HistorySummaryRow[]`

```text
from_state = classify(row[i].industry_beta, row[i].anchor_alpha)
to_state = classify(row[i+1].industry_beta, row[i+1].anchor_alpha)
count = transition count
probability = count / total transitions from from_state
```

如果筛选后相邻日期不是连续交易日，仍按筛选后的顺序计算转移；页面必须显示当前样本天数，避免误解。

### 核心指标公式

所有公式忽略 `null` 值。

| 指标 | 公式 |
|------|------|
| 日均收益 | `avg(anchor_return)` |
| 中位数收益 | `median(anchor_return)` |
| 正收益天数占比 | `count(anchor_return > 0) / count(anchor_return)` |
| 行业链日均中位数 | `avg(industry_chain_median)` |
| 日均当日超额 | `avg(relative_strength_vs_industry_chain)` |
| 跑赢行业天数占比 | `count(relative_strength_vs_industry_chain > 0) / count(relative_strength_vs_industry_chain)` |
| 极端背离次数 | `divergences.length`，日期筛选后只统计范围内事件 |
| 最大正背离 | `max(divergence)` |
| 最大负背离 | `min(divergence)` |

### 最佳/最差象限算法

输入：`QuadrantStat[]`

过滤：

```text
eligible = quadrants where count >= 5 and avg_next_1d is not null
```

排序分数：

```text
score = avg_next_1d_excess ?? avg_next_1d
```

最佳象限：

```text
max eligible by score, tie-breaker win_rate_1d, then count
```

最差象限：

```text
min eligible by score, tie-breaker lower win_rate_1d, then larger count
```

如果 `eligible` 为空：

- 不显示最佳/最差结论。
- 显示“当前筛选范围样本不足”。

### 样本内结论算法

`deriveConclusion` 输出：

```ts
{
  sampleDays: number;
  dateRange: { start: string; end: string };
  bestQuadrant: QuadrantStat | null;
  worstQuadrant: QuadrantStat | null;
  meanReversion: {
    outperformThenReverseRate: number | null;
    underperformThenReverseRate: number | null;
  };
  warning: string;
}
```

均值回归计算：

```text
跑赢后反转率 =
  count(relative_strength_vs_industry_chain > 0 and next_1d_excess_vs_chain < 0)
  / count(relative_strength_vs_industry_chain > 0 and next_1d_excess_vs_chain is not null)

跑输后反转率 =
  count(relative_strength_vs_industry_chain < 0 and next_1d_excess_vs_chain > 0)
  / count(relative_strength_vs_industry_chain < 0 and next_1d_excess_vs_chain is not null)
```

结论文案规则：

- `sampleDays < 30`：只显示“样本不足，不生成方向性结论”。
- `30 <= sampleDays < 80`：显示“样本有限，结论仅供观察”。
- `sampleDays >= 80`：允许显示样本内主要规律，但必须带样本数和“需持续验证”。

### 状态转移摘要算法

输入：`StateTransition[]`

候选摘要：

```text
对每个 from_state，找 probability 最大的 to_state。
仅保留 probability >= 0.30 且 count >= 3 的转移。
按 probability 降序取前 3 条。
```

展示文案：

```text
{from_state} 次日最常转向 {to_state}，样本 {count} 次，概率 {probability%}。
```

不写“必然”“大概率买入”等确定性表达。

### 极端背离后续表现

对每个 `ExtremeDivergence`：

```text
T+1 = event_path where event_date == date and offset == 1
T+3 = event_path where event_date == date and offset == 3
```

展示：

- `T+1 anchor_return`
- `T+3 anchor_return`
- `T+1 excess`
- `T+3 excess`

缺数据时显示 `--`。

## Verification

### 正确性

- 收益趋势图使用当日口径：
  - `anchor_return`
  - `industry_chain_median`
  - `relative_strength_vs_industry_chain`
- 次日前瞻指标只在明确标注为“前瞻”时展示。
- 核心指标均能追溯到 CSV 字段或明确派生公式。
- 样本不足时不展示强结论。

### 可读性

- 首屏能看清样本范围、核心结论和核心指标。
- 信号排行一眼能看出排序依据。
- 四象限能看出最佳/最差场景和样本数。
- 滚动指标有解释，不需要猜含义。

### 风险控制

- 页面不出现“买入、卖出、抄底、逃顶”等直接交易建议。
- 所有结论都带样本数或样本限制。
- 颜色只表达样本内表现好坏，不表达未来确定性。

### 技术验证

- `npm run lint` 通过。
- TypeScript 无类型错误。
- 页面加载无控制台报错。
- 大屏、笔记本和平板宽度下无文本遮挡或图表截断。
