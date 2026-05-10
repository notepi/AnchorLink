# 历史画像 V2：锚定个股的历史性格档案

## 背景

当前 `/history` 已经能展示信号 lift、象限统计、反直觉信号、条件效果、状态转移和极端背离路径。但这些内容仍然容易被理解成"今天触发了什么信号"或"今天该怎么判断"。

历史画像的定位需要重新收窄：它不负责判断今天，而是负责回答这只锚定个股过去是什么样。

更准确地说，历史画像应该像一份个股性格档案：

- 它过去喜欢什么样的行业环境。
- 它过去讨厌什么样的产业结构。
- 它过去什么时候容易跟随产业链，什么时候容易背离产业链。
- 它过去哪些信号经常有效，哪些信号经常误导。
- 它过去出现极端状态后，通常是修复、延续，还是反转。

今日状态、今日触发、今日操作倾向，后续由单独的"今日慢面板"承接。今日慢面板可以引用历史画像，但历史画像本身不做今日判断。

## 外部研究启发

### 因子画像

Alphalens 这类因子分析工具会把一个 signal/factor 拆成收益、信息系数、换手、分组表现等维度。它的启发是：一个信号不能只看平均收益，还要看它是否稳定、是否分组有效、是否只是少数样本或异常值贡献。

对 AnchorLink 来说，不需要照搬完整因子研究框架，但应该借鉴它的"信号体检"思路：

- 信号出现后的 1/3/5 日表现。
- 相对基线提升。
- 胜率。
- 样本数。
- 在不同状态下是否仍然有效。
- 是否有反直觉或陷阱属性。

参考：

- <https://quantopian.github.io/alphalens/>
- <https://www.quantrocket.com/codeload/quant-finance-lectures/quant_finance_lectures/Lecture38-Factor-Analysis-with-Alphalens.ipynb.html>

### 事件研究

事件研究关注事件发生前后的异常收益路径，例如 AR、CAR、AAR、CAAR。它的启发是：不要只看 T+1 均值，要看事件窗口里收益如何展开。

对 AnchorLink 来说，极端背离、放量上涨、放量下跌、资金价格背离、行业强但个股弱，都可以看作事件。历史画像应该展示这些事件过去出现后的路径习惯：

- T+1 是否修复。
- T+3 是否延续。
- T+5 是否回吐。
- 事件前是否已经提前异动。
- 事件后最大不利路径和最大有利路径。

参考：

- <https://www.eventstudytools.com/introduction-event-study-methodology>
- <https://eventstudy.de/docs/statistics-introduction>

### 相对轮动

RRG（Relative Rotation Graph）把资产放在相对强弱和相对动量两个维度上，看其处在 leading、weakening、lagging、improving 哪个阶段。它的启发是：真正有用的不是"涨跌本身"，而是"相对谁强、强势是否加速、弱势是否修复"。

对 AnchorLink 来说，锚定个股需要放在产业链、主题池、主线池、交易观察池之间看：

- 它过去是跟随产业链，还是领先产业链。
- 它在产业链强时是否能跑赢。
- 它在产业链弱时是否容易逆势修复。
- 主题情绪强时它是受益，还是被主题抽血。
- 主线池强时它是同步，还是掉队。

参考：

- <https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-types/relative-rotation-graphs-rrg-charts>

### 主观操盘指标

MarketSmith、IBD、Deepvue 等成长股/主观交易工具会重点看相对强度、行业组强度、量价需求、资金吸筹/派发。它的启发是：操盘手不是只看信号是否触发，而是看这只股票过去是否具备"被资金偏好"的行为。

对 AnchorLink 来说，需要把资金类信号从普通标签升级为历史性格的一部分：

- 它过去放量上涨后是否容易延续。
- 它过去放量下跌后是否容易恐慌或修复。
- 它过去资金价格背离是否真是风险，还是反直觉机会。
- 它过去主力资金拖累时是否反而容易低吸修复。

参考：

- <https://www.marketsmith.hk/overview/details-tab/>
- <https://deepvue.com/knowledge-base/accumulation-distribution-rating-and-rank/>

## 产品定位

历史画像不是"今天状态页"，而是"锚定个股历史性格页"。

它回答的问题是：

1. 这只股过去总体是什么性格？
2. 它过去在什么环境下更容易表现？
3. 它过去在什么环境下更容易失效？
4. 哪些信号对它是真 edge？
5. 哪些信号对它是陷阱？
6. 它过去和产业链、主题池、主线池之间是什么关系？
7. 它过去发生极端背离后，通常怎么走？

它不回答的问题是：

- 今天是否触发。
- 今天应该买、卖、等。
- 今天属于哪个具体历史状态。
- 今天的操作倾向。

这些由后续今日慢面板处理。

## 和现有系统的边界

现有 `history_operator_playbook.json` 和 `OperatorHistoryView` **不废弃**，继续作为"今日慢面板"候选数据源，包含 `stance`、`watch_for`、`confirmations`、`invalidations` 等偏今日判断的字段。

边界定义：

- `OperatorHistoryView`：保留为"操盘视图/今日慢面板"候选数据源。
- `HistoryPersonalityProfile`：新增为纯历史画像数据源，只描述过去习惯，不输出今日操作倾向。
- `CounterIntuitiveSignal`、`ConditionalSignalEffect`：继续复用，不重复造同类分类逻辑。
- `OperatorSignalRole`：继续复用，不重复造。`PersonalityPattern` 和 `OperatorSignalRole` 字段虽有重叠，但语义不同——前者面向"过去习惯"（habit_type、significance、source、best/worst_condition），后者面向"今日判断"（role、insight_type、priority、conclusion、reason）。保留两个模型，不合并。
- `/history` 首屏改为读取 `history_personality_profile.json`；现有 `OperatorDecisionPanel`、`OperatorPlaybookPanel` 等今日判断组件移入折叠的 legacy/debug 区，后续迁到今日慢面板。

#### 避免 `PersonalityPattern` 与 `OperatorSignalRole` 重复实现

**输出模型分离**：
- `PersonalityPattern`: 面向过去习惯（habit_type、significance、source、best/worst_condition）
- `OperatorSignalRole`: 面向今日判断（role、insight_type、priority、conclusion、reason）

**底层计算复用**：
- 反直觉判断：复用 `src/history_analysis/counter_intuitive_analyzer.py`
- 陷阱信号判断：复用 `counter_intuitive_analyzer.py`（负向反直觉即陷阱）
- 条件效果：复用 `src/history_analysis/conditional_effect_analyzer.py`
- 统计显著性：复用 permutation 检验和 BH FDR

**禁止事项**：
- 不得复制实现相同的统计判断逻辑
- 不得在不同模块中维护相同的分类规则
- 不得出现同一信号在画像页和操盘页结论不一致的情况

新增工作只补三个现有系统没有的能力：

1. `PersonalitySummary`：高层性格摘要。
2. `RelationshipProfile`：锚定股与产业链/主题池/主线池/交易池的关系判断。
3. `PathPattern`：按事件类型聚合 T-5 到 T+5 路径。

## 页面结构

### 1. 历史性格摘要

第一屏只讲长期历史画像，不讲今天。

建议展示：

- 样本区间和有效样本数。
- 个股历史性格一句话总结。
- 历史上最有利的环境。
- 历史上最不利的环境。
- 最强反直觉机会。
- 最大信号陷阱。
- 样本置信度提示。

示例表达：

> 过去样本显示，锚定个股并不是单纯的行业 beta 跟随者。它在"行业强但个股弱"时容易继续承压，但在"行业弱+个股弱"时反而存在修复倾向。资金价格背离过去并非纯风险，放量上涨反而容易成为追涨陷阱。

### 2. 它喜欢什么

展示历史上对锚定个股最友好的环境和信号。

每条至少包含：

- 标签或环境。
- 样本数。
- 次日均值。
- 3 日均值。
- 5 日均值。
- 胜率。
- 相对产业链超额。
- 置信度。

候选来源：

- `history_signal_lift.csv`
- `history_quadrant_stats.csv`
- `history_conditional_signal_effects.csv`

当前已有数据示例：

- `资金价格背离`：样本 7，次日均值约 +3.21%，相对基线约 +2.98pp。
- `情绪池强于产业链`：样本 16，次日均值约 +1.26%。
- `主力资金拖累`：样本 26，次日均值约 +1.13%。
- `行业弱+个股弱`：样本 14，次日均值约 +1.70%，胜率约 64%。

这些不是直接买入信号，而是历史偏好。

### 3. 它讨厌什么

展示历史上对锚定个股最不友好的环境和信号。

当前已有数据示例：

- `放量下跌`：样本 5，次日均值约 -1.62%。
- `放量上涨`：样本 7，次日均值约 -1.55%。
- `主线池强但主题情绪弱`：样本 12，次日均值约 -1.09%。
- `行业强+个股弱`：样本 19，次日均值约 -0.50%，相对产业链约 -1.32pp。

这一栏的意义是识别"过去容易翻车的样子"。

### 4. 反直觉习惯

展示"看起来危险，但过去反而容易修复"的模式。

候选规则：

- 信号直觉方向为负面。
- 历史实际方向为正面。
- 样本数达到最低阈值。
- 相对基线提升为正。

当前已有数据示例：

- `资金价格背离`：直觉偏风险，但历史表现偏强。
- `个股Alpha为负` / `跑输主线池`：直觉偏弱，但过去样本里并不一定差。
- `行业Beta为负`：直觉偏风险，但历史次日均值为正。

这一栏应该强调"可研究"，而不是"可直接交易"。

### 5. 信号陷阱

展示"看起来漂亮，但过去表现差"的模式。

候选规则：

- 信号直觉方向为正面。
- 历史实际方向为负面。
- 相对基线提升为负。

当前已有数据示例：

- `放量上涨`：直觉偏正面，但历史次日均值偏弱。
- `资金价格共振`：直觉偏正面，但历史表现低于基线。
- `行业Beta为正`：行业看似强，但锚定股过去并不一定跟随。
- `主线池强于主题情绪`：看似主线强，但对锚定股未必友好。

这一栏是历史画像最有价值的部分之一，因为它防止操盘手被直觉带偏。

### 6. 产业联动画像

展示锚定个股和产业链、主题池、主线池、交易观察池的历史关系。

需要回答：

- 它过去更跟产业链，还是更跟主题情绪。
- 它过去跑赢产业链后容易延续还是均值回归。
- 它过去跑输产业链后容易继续弱还是修复。
- 产业链强时，它是否经常跟不上。
- 产业链弱时，它是否经常先修复。

建议指标：

- 平均相对产业链强弱。
- 跑赢产业链天数占比。
- 跑输产业链后 T+1/T+3 修复概率。
- 极端跑赢/跑输后的事件路径。
- 主线池、主题池、交易池相对强弱对锚定股后续收益的条件效果。

### 7. 路径画像

路径画像不只展示结果，还展示过程。

对于每类重要事件，展示：

- T-5 到 T+5 的锚定股收益路径。
- 产业链中位数路径。
- 相对超额路径。
- 平均路径。
- 最好/最差路径。
- 最大不利路径。
- 最大有利路径。

优先事件：

- 极端正背离。
- 极端负背离。
- 放量上涨。
- 放量下跌。
- 资金价格背离。
- 行业强但个股弱。
- 行业弱但个股强。

> **与 `today-history-mapping-panel` 的区别**：路径画像是按事件类型聚合的历史路径（"所有极端正背离事件过去怎么走"），而 `today-history-mapping` 是找和今天相似的历史状态。两者服务不同场景，不重复。

如果后续能拿到日内高低价，可以进一步计算类似 MAE/MFE 的风险路径：

- 最大不利波动：类似 MAE。
- 最大有利波动：类似 MFE。
- 这类指标能帮助今日慢面板判断"历史上类似状态通常要忍受多大波动"。

参考：

- <https://www.tradesviz.com/glossary/maximum-adverse-excursion/>
- <https://www.tradesviz.com/glossary/maximum-favorable-excursion/>

## 后端数据设计

新增主产物：

```text
data/output/history_personality_profile.json
```

建议结构：

```typescript
interface HistoryPersonalityProfile {
  as_of_date: string;
  date_range_start: string;
  date_range_end: string;
  sample_days: number;
  valid_sample_days: number;
  personality_summary: PersonalitySummary;
  habit_patterns: PersonalityPattern[];
  counter_intuitive_patterns: PersonalityPattern[];
  trap_patterns: PersonalityPattern[];
  relationship_profile: RelationshipProfile;
  path_patterns: PathPattern[];
  stability: PersonalityStability;
  sample_warnings: string[];
}
```

核心模型：

```typescript
interface PersonalitySummary {
  headline: string;
  traits: string[];
  strongest_pattern_label: string | null;
  weakest_pattern_label: string | null;
  confidence: 'high' | 'medium' | 'low';
  generation_method: 'rule_template_v1';
}

interface PersonalityPattern {
  label: string;
  display_label: string;
  category: string;
  pattern_kind: 'environment' | 'signal' | 'quadrant' | 'relationship' | 'event';
  habit_type: 'likes' | 'dislikes' | 'counter_intuitive' | 'trap' | 'context';
  count: number;
  avg_next_1d: number | null;
  avg_next_3d: number | null;
  avg_next_5d: number | null;
  avg_next_1d_excess: number | null;
  avg_next_1d_delta_pp: number | null;
  win_rate_1d: number | null;
  effect_score: number | null;
  significance: 'strong' | 'suggestive' | 'weak' | 'insufficient';
  confidence: 'high' | 'medium' | 'low';
  best_condition: ConditionEffect | null;
  worst_condition: ConditionEffect | null;
  explanation: string;
  source: 'signal_lift' | 'quadrant_stats' | 'conditional_effect' | 'counter_intuitive' | 'event_study';
}

interface RelationshipProfile {
  anchor_vs_chain: RelationshipPattern;
  anchor_vs_theme: RelationshipPattern;
  anchor_vs_core: RelationshipPattern;
  anchor_vs_trading_watchlist: RelationshipPattern;
}

interface RelationshipPattern {
  relation: 'follows' | 'leads' | 'lags' | 'mean_reverts' | 'diverges' | 'unstable';
  confidence: 'high' | 'medium' | 'low';
  sample_count: number;
  evidence: string[];
  same_day_corr: number | null;
  anchor_leads_corr: number | null;
  anchor_lags_corr: number | null;
  avg_relative_strength: number | null;
  outperform_ratio: number | null;
  repair_after_underperform_ratio: number | null;
  continuation_after_outperform_ratio: number | null;
  stability: 'stable' | 'changed' | 'unstable' | 'insufficient';
}

interface PathPattern {
  event_label: string;
  count: number;
  avg_path: Array<{
    offset: number;
    anchor_return: number | null;
    chain_median: number | null;
    excess: number | null;
  }>;
  summary: string;
  confidence: 'high' | 'medium' | 'low';
}

interface ConditionEffect {
  quadrant: string;
  count: number;
  avg_next_1d: number | null;
  win_rate_1d: number | null;
  delta_pp_vs_quadrant: number | null;
}

interface PersonalityStability {
  status: 'stable' | 'changed' | 'insufficient';
  recent_window_days: number;
  early_vs_recent_notes: string[];
}
```

## 生成逻辑

新增后端模块建议：

```text
src/history_analysis/personality_profile.py
```

核心职责：

- 从现有 `HistoryRow`、`SignalLift`、`QuadrantStats`、`ConditionalSignalEffect`、`EventPath` 生成历史性格画像。
- 复用现有 `CounterIntuitiveSignal`、`OperatorSignalRole`、`ConditionalSignalEffect`，不要重复实现同类分类逻辑。
- 不读取今日快照做当日判断。
- 不输出今日状态。
- 所有结论必须附带样本数和置信度。

集成位置：

- 在 `src/history_analysis/orchestrator.py` 中，现有 signal lift、counter intuitive、conditional effects、event study 都生成之后（stage 9 之后），调用 `build_personality_profile(...)`。
- 输出独立 JSON：`data/output/history_personality_profile.json`。
- 不合入 `history_operator_playbook.json`，避免历史画像和今日判断耦合。
- CSV 产物不删除，继续作为 profile 的证据来源和调试明细。

### PersonalitySummary 生成规则

V1 使用规则模板，不使用 LLM。

输入：

- Top 1 `likes` pattern。
- Top 1 `dislikes` pattern。
- Top 1 `counter_intuitive` pattern。
- Top 1 `trap` pattern。
- `RelationshipProfile.anchor_vs_chain.relation`。
- 样本量和稳定性。

模板：

```text
过去样本显示，锚定个股更像「{primary_trait}」。它较喜欢「{top_like}」，不太喜欢「{top_dislike}」；「{top_counter_intuitive}」属于反直觉机会线索，「{top_trap}」容易形成信号陷阱。和产业链关系上，它更偏「{chain_relation}」。{confidence_note}
```

`primary_trait` 规则：

- `anchor_vs_chain.relation == follows` 且同日相关高：`产业链跟随型`
- `anchor_vs_chain.relation == leads`：`产业链领先型`
- `anchor_vs_chain.relation == mean_reverts`：`背离修复型`
- `trap_patterns` 强于 `likes` 且稳定性差：`高误判型`
- 无明确关系或样本不足：`样本观察型`

### RelationshipProfile 判断算法

对每个参照池分别计算关系：产业链、主题池、主线池、交易观察池。

#### 数据来源

| 参照对象 | 池子 ID | 数据来源 | 日收益字段 | 样本过滤 |
|----------|----------|----------|------------|----------|
| 产业链 | `industry_chain` | `PoolRegistry.get_benchmark_scope()` | `industry_chain_median` | 和锚定股同日有效 |
| 主题池 | `theme_pool` | `PoolRegistry.get_ranking_scope_members()` | `theme_pool_median` | 和锚定股同日有效 |
| 主线池 | `direct_peers` | `PoolRegistry.get_benchmark_scope()` | `direct_peers_median` | 和锚定股同日有效 |
| 交易观察池 | `trading_watchlist` | `PoolRegistry.get_ranking_scope_members()` | `trading_watchlist_median` | 和锚定股同日有效 |

**缺失数据降级策略**：如果某个参照池当前没有足够历史序列，应输出：
```typescript
{
  relation: "unstable",
  confidence: "low",
  stability: "insufficient",
  evidence: ["样本或参照池历史序列不足"]
}
```

#### 基础序列

- `anchor_return[t]`
- `group_median[t]`
- `relative_strength[t] = anchor_return[t] - group_median[t]`
- `next_1d_excess[t]`、`next_3d_excess[t]`

相关性：

- `same_day_corr = corr(anchor_return[t], group_median[t])`
- `anchor_leads_corr = corr(anchor_return[t], group_median[t+1])`
- `anchor_lags_corr = corr(anchor_return[t], group_median[t-1])`

关系分类：

- `follows`：`same_day_corr >= 0.35`，且领先/滞后相关都没有比同日相关高出 `0.10`。
- `leads`：`anchor_leads_corr >= 0.30`，且比 `same_day_corr` 至少高 `0.10`。
- `lags`：`anchor_lags_corr >= 0.30`，且比 `same_day_corr` 至少高 `0.10`。
- `mean_reverts`：极端跑输后 3 日修复率 `>= 55%`，且极端跑赢后 3 日延续率 `< 45%`。
- `diverges`：`same_day_corr < 0.15`，且 `abs(avg_relative_strength) >= 1.0pp` 或极端背离样本占比 `>= 15%`。
- `unstable`：有效样本 `< 20`，或早期/近期关系分类不一致且差异无法由样本量解释。

极端阈值：

- 跑赢：`relative_strength >= +3pp`
- 跑输：`relative_strength <= -3pp`
- 修复：跑输后 `next_3d_excess > 0`
- 延续：跑赢后 `next_3d_excess > 0`

关系置信度：

- 高：有效样本 `>= 60`，关系分类满足阈值，且早期/近期分类一致。
- 中：有效样本 `>= 30`，关系分类满足阈值，但早期/近期有轻微差异。
- 低：有效样本 `< 30`，或只满足弱阈值。

#### 关系分类优先级

多个条件同时满足时，按以下优先级裁决（从高到低）：

1. **insufficient sample → unstable**
   - 条件：有效样本 < 20

2. **early/recent strong conflict → unstable 或 changed**
   - 条件：
     - early 和 recent 样本都 >= 10
     - 两者 relation 分类不同
     - 且差异不能仅由样本量波动解释（如 strong vs strong）
   - 输出：
     - 如果任一窗口样本 < 5 → unstable, stability = insufficient
     - 如果任一窗口样本 < 10 → changed, confidence = low
     - 否则 → changed, confidence = medium

3. **lead/lag 显著优势 → leads / lags**
   - 条件：
     - anchor_leads_corr >= 0.30 且比 same_day_corr 高 >= 0.10 → leads
     - anchor_lags_corr >= 0.30 且比 same_day_corr 高 >= 0.10 → lags

4. **mean reversion 条件显著 → mean_reverts**
   - 条件：
     - 极端跑输后 3 日修复率 >= 55%
     - 且极端跑赢后 3 日延续率 < 45%

5. **same-day corr 显著 → follows**
   - 条件：same_day_corr >= 0.35

6. **low corr + persistent excess/divergence → diverges**
   - 条件：same_day_corr < 0.15 且 (abs(avg_relative_strength) >= 1.0pp 或 极端背离占比 >= 15%)

7. **otherwise → unstable**
   - 说明：以上都不满足时

#### relation 与 stability 的关系

- `relation` 描述全样本主关系
  - 只有样本不足或关系完全不可判定时，relation = unstable
  - 否则 relation 为主关系类型（follows/leads/lags/mean_reverts/diverges）

- `stability` 描述该关系是否跨时间稳定
  - stable: 早期和近期分类一致
  - changed: 早期和近期分类不一致
  - unstable: 样本不足或关系不可判定
  - insufficient: 任一窗口样本 < 5

### 统计口径定义

| 字段 | 定义 | 计算公式 |
|------|------|----------|
| `baseline_avg_next_1d` | 全体有效历史日的锚定股次日均值 | `avg(all_valid_rows.next_1d_return)` |
| `avg_next_1d_delta_pp` | 信号出现日次日均值与基线的百分点差 | `pattern_avg_next_1d - baseline_avg_next_1d` |
| `avg_next_1d_excess` | 信号出现日锚定股次日相对产业链的超额 | `pattern_avg_next_1d - pattern_industry_chain_median_next_1d` |
| `group_median` | 某个参照池的成员涨跌幅中位数 | `median(pool_members.return)` |

**参照池口径说明**：
- `group_median` 对不同参照池分别计算
- 不能混用不同池子的 median
- 产业链：`industry_chain_median`
- 主题池：`theme_pool_median`
- 主线池：`direct_peers_median`
- 交易观察池：`trading_watchlist_median`

### 样本量和过拟合约束

置信度建议：

- `count < 5`：不进入主画像，只进入折叠明细。
- `5 <= count < 10`：低置信度，只能标记为"观察线索"。
- `10 <= count < 20`：中置信度，可以进入列表，但不能进入 headline。
- `count >= 20`：高置信度，可以进入 headline 候选。

多重比较控制：

- 对所有候选信号/环境计算 `effect = avg_next_1d - baseline_avg_next_1d`。
- 使用固定随机种子 `0` 做 1000 次标签置换，估计每个 pattern 的双侧 permutation p-value。
- 对同一批候选 pattern 用 Benjamini-Hochberg 控制 FDR，`q <= 0.20` 标记为 `strong`。
- 未通过 FDR 但 `count >= 10` 且 `abs(effect) >= 0.8pp` 标记为 `suggestive`。
- 其余为 `weak` 或 `insufficient`。
- Headline 只能使用 `strong` 或高样本 `suggestive` 结论。

> **小样本事件类型的自然降级**：事件类型拆分后很多类别 count < 10，置换检验功效低，这些类别会自然落入 `weak`/`insufficient`。这是正确行为——小样本不应获得高显著性标签，样本量约束本身就是防过拟合的第一道防线。

时间稳定性：

- 将历史样本分为 `early` 和 `recent`，`recent` 默认最近 30 个有效交易日。
- 对主要 pattern 分别计算早期和近期 effect。
- 如果方向一致且差异 `< 1.0pp`，标记 `stable`。
- 如果方向相反或差异 `>= 1.0pp`，标记 `changed`，headline 必须加入"近期行为已有变化"提示。
- 如果任一窗口样本 `< 5`，标记 `insufficient`。

排序建议：

- 喜欢：优先按 shrunk `effect_score`、`avg_next_1d_excess`、`win_rate_1d` 综合排序。
- 讨厌：优先按负向 shrunk `effect_score`、负向超额和低胜率排序。
- 反直觉：优先按直觉方向与实际方向的背离程度排序。
- 陷阱：优先按正面直觉但负向实际表现排序。

`effect_score` 使用收缩分数，避免小样本冲到前面：

```text
effect_score = avg_next_1d_delta_pp * min(1, sqrt(count / 20))
```

## 前端展示

`/history` 页面应改成档案式结构。

建议顺序：

1. 历史性格摘要。
2. 它喜欢什么。
3. 它讨厌什么。
4. 反直觉习惯。
5. 信号陷阱。
6. 产业联动画像。
7. 路径画像。
8. 折叠明细：完整信号 lift、象限表、状态转移、事件路径。

### 组件处置

| 组件 | 处置 | 原因 |
|------|------|------|
| `history-dashboard.tsx` | **重写首屏布局** | 首屏改为性格摘要 |
| `operator-decision-panel.tsx` | 移入折叠 | 属于今日判断 |
| `operator-playbook-panel.tsx` | 移入折叠 | 属于今日判断 |
| `operator-signal-insights.tsx` | 移入折叠 | 属于今日判断 |
| `trading-playbook.tsx` | 移入折叠 | 属于今日判断 |
| `trading-suggestions.tsx` | 移入折叠 | 属于今日判断 |
| `conclusion-card.tsx` | 移入折叠 | 今日结论性质 |
| `decision-summary.tsx` | 移入折叠 | 今日决策性质 |
| `today-history-mapping-panel.tsx` | 移入折叠 | 今日映射性质 |
| `signal-insights.tsx` | 保留，移入明细 | 纯统计 |
| `signal-lift-table.tsx` | 保留，移入明细 | 纯统计 |
| `quadrant-grid.tsx` | 保留，移入明细 | 纯统计 |
| `quadrant-signal-breakdown.tsx` | 保留，移入明细 | 纯统计 |
| `rolling-metrics-chart.tsx` | 保留，移入明细 | 纯统计 |
| `history-trend-chart.tsx` | 保留，移入明细 | 纯统计 |
| `transition-heatmap.tsx` | 保留，移入明细 | 纯统计 |
| `divergence-timeline.tsx` | 保留，移入明细 | 纯统计 |
| `stability-monitor.tsx` | 保留，移入明细 | 纯统计 |
| `signal-combinations.tsx` | 保留，移入明细 | 纯统计 |
| `operator-combination-summary.tsx` | 保留，移入明细 | 纯统计 |
| `combination-evidence-summary.tsx` | 保留，移入明细 | 纯统计 |
| `signal-evidence-summary.tsx` | 保留，移入明细 | 纯统计 |
| `signal-business-groups.tsx` | 保留，移入明细 | 纯统计 |
| `signal-trend-indicator.tsx` | 保留，移入明细 | 纯统计 |
| `core-metrics.tsx` | 保留，移入明细 | 纯统计 |
| `filter-bar.tsx` | 保留 | 筛选功能 |

### 新增组件

| 组件 | 职责 |
|------|------|
| `PersonalitySummaryCard` | 性格摘要 headline + traits + 置信度 |
| `HabitPatternList` | 喜欢什么 / 讨厌什么列表 |
| `CounterIntuitiveList` | 反直觉习惯列表 |
| `TrapPatternList` | 信号陷阱列表 |
| `RelationshipProfilePanel` | 产业联动画像 |
| `PathPatternPanel` | 路径画像（按事件类型聚合） |

前端文案要避免：

- "当前触发"。
- "今日状态"。
- "现在建议"。
- "今天应当"。

前端文案应该使用：

- "过去样本显示"。
- "历史上更容易"。
- "过去出现后"。
- "这只股过去不太喜欢"。
- "样本不足，仅作观察"。

## 审计修订说明

本 plan 已根据 `history_personality_profile_audit.md` 进行修订，补充了以下 P0+P1 工程细节：

| 优先级 | 修订项 | 修订位置 |
|--------|--------|----------|
| **P0-1** | 补充 `RelationshipProfile` 分类优先级 | "关系分类优先级" 章节 |
| **P0-2** | 明确 baseline/excess 统计口径 | "统计口径定义" 章节 |
| **P0-3** | 明确各参照池数据来源和降级策略 | "数据来源" 章节 |
| **P1-1** | 避免 `PersonalityPattern` 与 `OperatorSignalRole` 重复实现 | "边界定义" 章节 |

**已解决的原审计项**（未在此列出，已由原 plan 包含）：
- P0: `PersonalitySummary.headline` 生成算法
- P0: 和 `operator_playbook` 的边界
- P1: 样本量约束下的降级策略
- P1: 过拟合风险和多重比较校正
- P1: 后端在 orchestrator 中的集成位置
- P1: 时间维度的性格稳定性
- P2: 前端改造范围
- P2: `best_condition` / `worst_condition` 结构化数据

**后续可选的 P2 项**（本次修订暂不包含）：
- 前端实施拆成 MVP / 完整迁移两阶段
- `PathPattern` 补充最好/最差/最大不利/最大有利路径字段

## 和今日慢面板的分工

今日慢面板不是历史画像 V1 的实现依赖。历史画像必须可以独立运行、独立展示、独立验收。

历史画像：

- 描述过去。
- 输出稳定的个股性格档案。
- 不判断今天。
- 可以每天随数据刷新，但语义仍然是历史总结。

今日慢面板：

- 描述今天。
- 引用今日快照。
- 将今日状态映射到历史画像。
- 输出今日观察重点、确认条件、失效条件。

两者关系：

```text
历史画像 = 这只股过去是什么性格
今日慢面板 = 今天像不像它过去喜欢/讨厌的样子
```

## 测试计划

后端测试：

- 生成 `history_personality_profile.json`。
- 确认主产物不依赖今日状态判断。
- 确认 `history_operator_playbook.json` 仍可生成，且不被 `history_personality_profile.json` 替代。
- 样本不足的信号标记为低置信度。
- `count < 5` 的 pattern 不进入主画像。
- permutation p-value 和 BH FDR 能稳定复现。
- 反直觉信号能正确进入 `counter_intuitive_patterns`。
- 陷阱信号能正确进入 `trap_patterns`。
- 喜欢/讨厌环境能按历史表现排序。
- 产业联动画像能按明确阈值区分 follows、leads、lags、mean_reverts、diverges、unstable。
- 路径画像能输出 T-5 到 T+5 的平均路径。
- 早期/近期方向相反时，稳定性标记为 `changed`。

前端验证：

- 第一屏是历史性格摘要，不是今日结论。
- 页面不出现"今天是什么状态"的主判断。
- 每条结论都展示样本数和置信度。
- 低样本结论有明确降级提示。
- 完整统计表仍可在折叠明细中查看。

## 验收标准

- 用户能在不看今日数据的情况下，理解这只锚定股过去的行为习惯。
- 用户能知道它过去喜欢什么环境、讨厌什么环境。
- 用户能知道哪些信号对它是机会，哪些信号对它是陷阱。
- 用户能看到它和产业链/主题池/主线池的历史关系。
- 用户能看到典型事件后的历史路径，而不只是平均收益。
- 历史画像和今日慢面板边界清晰，不互相混淆。
