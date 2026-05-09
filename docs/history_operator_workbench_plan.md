# 历史验证工作台改版 Plan

参考样式图：

`/Users/pan/.codex/generated_images/019e0aa2-7f39-7e71-b555-0e1dc17798d3/ig_08183907f9d269050169fecd09dc4481918ecc1b5d4e60d0ca.png`

## 合并结论

这版合并两个方向：

- **操盘工作台框架**：第一屏先给决策摘要、稳定性、交易观察建议，前端不再让用户读原始列表。
- **信号洞察 edge**：后端识别反直觉信号、信号陷阱、象限条件效果，把“为什么值得看”提炼出来。

最终目标：`/history` 不再是统计表集合，而是回答操盘手的四个问题：

1. 当前历史规律还能不能信？
2. 现在出现什么信号值得重点看？
3. 这些信号在什么条件下有效？
4. 出现什么情况要降级或失效？

## 当前问题

- `信号业务分组` 只是分类，不是结论。操盘手不关心它属于哪类，关心它能不能用。
- `信号组合效应` 暴力枚举过多，很多组合只是共现，不是可操作确认。
- `信号表现排行` 是明细表，适合诊断，不适合作为主内容。
- `交易建议` 不能只列高价值信号，需要触发条件、确认条件、反证条件和样本约束。
- `滚动指标` 和 `当日收益与超额` 有价值，应上移并保留原图。

## 产品原则

1. **先决策，后证据，最后明细**
   - 第一屏：可信度、操作倾向、失效点。
   - 第二屏：滚动稳定性、交易观察建议。
   - 第三屏：反直觉信号、信号陷阱、象限条件效果。
   - 明细表和完整组合默认折叠。

2. **后端产出操盘视图模型**
   - 信号角色、反直觉识别、条件效果、交易建议都属于业务规则。
   - 前端只展示后端产出的 `OperatorHistoryView`。

3. **保留有效图表**
   - 保留 `RollingMetricsChart`，标题「滚动指标」。
   - 保留 `HistoryTrendChart`，标题「当日收益与超额」。
   - 两张图并列进入稳定性监控，不删除、不折叠、不重做。

4. **用条件效果替代暴力组合**
   - 主区不展示完整组合列表。
   - 组合只作为“确认条件”存在，且必须证明比单信号有增量。
   - 更重要的是展示：某个信号在哪个象限/状态下有效。

## 页面结构

```text
/history
├── 筛选栏
├── 操盘决策摘要
│   ├── 历史规律可信度
│   ├── 当前操作倾向
│   └── 主要失效点
├── 稳定性监控
│   ├── 滚动指标
│   └── 当日收益与超额
├── 交易观察建议
│   ├── 看什么
│   ├── 用什么确认
│   ├── 什么会失效
│   └── 样本约束
├── 信号洞察
│   ├── 反直觉机会
│   ├── 信号陷阱
│   └── 主触发 / 确认 / 反证
├── 象限条件效果
│   ├── 当前象限高亮
│   └── 每个象限 TOP 有效 / TOP 风险信号
├── 组合确认
│   └── 最多 3 个有效确认；无增量则显示空状态
└── 折叠明细
    ├── 完整信号排行
    ├── 完整组合列表
    └── 业务分组调试视图
```

## 后端视图模型

新增输出：

`data/output/history_operator_playbook.json`

顶层结构：

```typescript
interface OperatorHistoryView {
  asOfDate: string;
  dateRange: { start: string; end: string };
  sampleDays: number;
  regime: HistoryRegime;
  playbook: OperatorPlaybook;
  signalRoles: OperatorSignalRole[];
  counterIntuitiveSignals: CounterIntuitiveSignal[];
  signalTraps: CounterIntuitiveSignal[];
  conditionalEffects: ConditionalSignalEffect[];
  confirmationPairs: OperatorConfirmationPair[];
  debugRefs: {
    signalLiftCsv: string;
    combinationDebug?: string;
  };
}
```

## 操盘逻辑

### 1. 历史规律可信度

后端根据有效样本和滚动指标生成：

- `confidence`: `high | medium | low`
- `status`: `stable | weakening | invalid`
- `headline`
- `reasons`
- `riskPoints`

规则：

- `sampleDays < 20`：`confidence = low`，`status = invalid`
- `20 <= sampleDays < 40`：最高只能 `medium`
- 滚动恶化满足任一条件：
  - 最新 `excess_5d < 0 && excess_10d < 0`
  - 最新 `excess_10d` 从前一条 `>= 0` 转为 `< 0`
  - 最新 `risk_high_streak >= 3`
  - 最新 `outperform_streak <= -3`
- 滚动稳定满足全部条件：
  - 最新 `excess_10d >= 0`
  - 最近 3 条中 `excess_5d < 0` 的数量不超过 1
  - 最新 `risk_high_streak < 3`

### 2. 反直觉信号

反直觉信号是核心 edge。后端识别“直觉方向”和“历史实际方向”不一致的信号。

示例：

- “资金价格背离”：直觉偏风险，但历史表现强，可能是反直觉机会。
- “放量上涨”：直觉偏追涨，但历史表现弱，可能是信号陷阱。
- “行业Beta为正”：直觉偏好，但历史未必有正向收益。

模型：

```typescript
interface CounterIntuitiveSignal {
  label: string;
  displayLabel: string;
  category: string;
  appearanceCount: number;
  avgNext1d: number | null;
  winRate1d: number | null;
  avgNext1dDeltaPp: number | null;
  intuitiveDirection: 'positive' | 'negative' | 'neutral';
  actualDirection: 'positive' | 'negative' | 'neutral';
  degree: number;
  verdict: 'counter_intuitive_opportunity' | 'signal_trap';
  explanation: string;
}
```

识别规则：

- 先定义信号语义直觉方向：
  - positive：行业Beta为正、个股Alpha为正、跑赢核心池、放量上涨、资金价格共振、主力资金领先
  - negative：行业Beta为负、个股Alpha为负、放量下跌、资金价格背离、行业强但个股弱
  - neutral：中性/分化/背景类信号
- 实际方向：
  - `avg_next_1d_delta_pp > 0.1` 或 `avg_next_1d > 0.1`：positive
  - `< -0.1`：negative
  - 其他：neutral
- 直觉 positive 但实际 negative：`signal_trap`
- 直觉 negative 但实际 positive：`counter_intuitive_opportunity`
- `degree = abs(avg_next_1d_delta_pp) * severityMultiplier`

### 3. 信号角色

业务分组不再作为主概念。后端给每个信号打操盘角色：

- `primary_trigger`：主触发信号，出现时值得重点关注
- `confirmation`：确认信号，增强主触发可信度
- `risk_invalidator`：反证信号，出现时降级或回避
- `context_only`：背景信号，只解释环境
- `ignore`：样本不足或无稳定边际

模型：

```typescript
interface OperatorSignalRole {
  label: string;
  displayLabel: string;
  category: string;
  businessTag: string;
  role: 'primary_trigger' | 'confirmation' | 'risk_invalidator' | 'context_only' | 'ignore';
  insightType: 'counter_intuitive' | 'trap' | 'normal';
  priority: number;
  count: number;
  avgNext1d: number | null;
  deltaPp: number | null;
  winRate: number | null;
  trend: TrendStatus;
  bestCondition?: ConditionalSignalEffect;
  conclusion: string;
  reason: string;
}
```

主触发规则：

- `appearance_count >= 10`
- `avg_next_1d_delta_pp > 0.5`
- `win_rate_1d >= 0.5`
- 趋势不是 `trend_deteriorating`

反证规则：

- `avg_next_1d_delta_pp < 0`
- 或 `win_rate_1d < 0.5`
- 或属于 `signal_trap`
- 或业务标签为异常/风险且历史表现偏弱

### 4. 象限条件效果

用象限条件效果替代主区的暴力组合列表。

模型：

```typescript
interface ConditionalSignalEffect {
  label: string;
  displayLabel: string;
  category: string;
  quadrant: string;
  quadrantCount: number;
  signalInQuadrantCount: number;
  avgNext1dInQuadrant: number | null;
  winRateInQuadrant: number | null;
  deltaPpVsQuadrant: number | null;
  overallAvgNext1d: number | null;
  verdict: 'works_in_condition' | 'fails_in_condition' | 'insufficient';
}
```

计算规则：

- 按 9 象限分组。
- 每个象限先计算象限基线 `avg_next_1d`。
- 再统计信号在该象限内的 `avg_next_1d`、`win_rate`。
- `deltaPpVsQuadrant = 信号象限内均值 - 象限基线`。
- 前端高亮当前象限，并展示该象限下 TOP3 有效信号 / TOP3 风险信号。

### 5. 组合确认

组合只回答：是否比单信号更有解释力。

规则：

- 样本数 `>= 8`
- 组合次日均值不为空
- `synergy = combination.avgNext1d - max(single.avg_next_1d) > 0`
- 胜率不低于 50%，或协同增量足够明显
- 最多输出 3 个

没有合格组合时，显示：

> 当前没有比单信号更有解释力的组合

完整组合列表只进入折叠明细。

### 6. 交易观察建议

模型：

```typescript
interface OperatorPlaybook {
  stance: 'active_watch' | 'cautious_watch' | 'wait';
  headline: string;
  watchFor: string[];
  confirmations: string[];
  invalidations: string[];
  sampleNote: string;
}
```

生成规则：

- `regime.status = invalid`：`stance = wait`
- 有反证信号且无强主触发：`stance = wait`
- 有主触发但 `regime.status = weakening`：`stance = cautious_watch`
- 有主触发且 `regime.status = stable`：`stance = active_watch`
- `watchFor` = TOP3 `primary_trigger`
- `confirmations` = TOP 条件效果 + TOP 组合确认
- `invalidations` = TOP3 `risk_invalidator` + 滚动恶化条件

## 后端改动

### 新增 `src/history_analysis/counter_intuitive_analyzer.py`

核心函数：

```python
def identify_counter_intuitive_signals(
    rows: list[HistoryRow],
    signal_lifts: list[SignalLift],
    min_count: int = 5,
) -> list[CounterIntuitiveSignal]:
    ...
```

职责：

- 定义信号直觉方向映射。
- 对比直觉方向和实际收益方向。
- 输出反直觉机会和信号陷阱。

### 新增 `src/history_analysis/conditional_signal_analyzer.py`

核心函数：

```python
def build_conditional_signal_effects(
    rows: list[HistoryRow],
    signal_lifts: list[SignalLift],
    min_count: int = 3,
) -> list[ConditionalSignalEffect]:
    ...
```

职责：

- 按 9 象限统计信号效果。
- 输出每个信号在不同市场状态下的有效性。

### 新增 `src/history_analysis/operator_playbook.py`

核心函数：

```python
def build_operator_playbook(
    rows: list[HistoryRow],
    rolling: list[RollingMetrics],
    signal_lifts: list[SignalLift],
    counter_intuitive: list[CounterIntuitiveSignal],
    conditional_effects: list[ConditionalSignalEffect],
    min_signal_count: int = 5,
    min_combo_count: int = 8,
) -> OperatorHistoryView:
    ...
```

职责：

- 生成 `HistoryRegime`。
- 给信号打操盘角色。
- 整合反直觉机会、信号陷阱、象限条件效果。
- 生成交易观察建议。
- 输出可测试的 `OperatorHistoryView`。

### 修改 `src/history_analysis/models.py`

新增 dataclass：

- `CounterIntuitiveSignal`
- `ConditionalSignalEffect`
- `HistoryRegime`
- `OperatorSignalRole`
- `OperatorConfirmationPair`
- `OperatorPlaybook`
- `OperatorHistoryView`

### 修改 `src/output/history_csv_writer.py`

新增：

- `write_counter_intuitive_csv()`
- `write_conditional_signal_csv()`

### 新增 JSON 写入

建议新增：

```python
def write_operator_playbook_json(view: OperatorHistoryView, path: Path) -> None:
    ...
```

### 修改 `src/history_analysis/orchestrator.py`

在现有产物之后新增：

- `history_counter_intuitive_signals.csv`
- `history_conditional_signal_effects.csv`
- `history_operator_playbook.json`

现有 CSV 不删除，继续作为折叠明细和调试数据源。

## 前端改动

### 数据读取

新增：

- `getCounterIntuitiveSignals()`
- `getConditionalSignalEffects()`
- `getHistoryOperatorPlaybook()`

新增类型：

- `CounterIntuitiveSignal`
- `ConditionalSignalEffect`
- `HistoryRegime`
- `OperatorSignalRole`
- `OperatorConfirmationPair`
- `OperatorPlaybook`
- `OperatorHistoryView`

### 新组件

- `OperatorDecisionPanel`
- `StabilityMonitor`
- `OperatorPlaybookPanel`
- `CounterIntuitiveSignalPanel`
- `SignalTrapAlert`
- `SignalRoleSummary`
- `QuadrantSignalBreakdown`
- `CombinationConfirmationSummary`
- `HistoryDetailsDisclosure`

### 降级旧组件

- `SignalBusinessGroups`：只作为折叠调试区。
- `SignalCombinations`：只作为折叠调试区。
- `SignalLiftTable`：默认折叠。
- `generateTradingRules`：不再驱动主交易建议。

### 稳定性监控

保留两张现有图：

```tsx
<StabilityMonitor>
  <RollingMetricsChart data={rollingMetrics} />
  <HistoryTrendChart data={trendData} title="当日收益与超额" />
</StabilityMonitor>
```

补充状态文案：

- “近期超额收益走弱，历史结论降级使用”
- “10 日超额仍为正，历史规律可继续参考”
- “样本不足，历史统计仅作观察”

## 页面展示重点

### 第一屏

- 操盘决策摘要
- 滚动指标
- 当日收益与超额

### 第二屏

- 交易观察建议
- 反直觉机会
- 信号陷阱

### 第三屏

- 信号角色摘要
- 象限条件效果
- 组合确认

### 折叠明细

- 完整信号排行
- 完整组合列表
- 业务分组调试视图

## 验证

### 后端测试

- 样本不足时 `regime.status = invalid`
- 滚动恶化时 `regime.status = weakening` 或 `invalid`
- 直觉 positive 但实际 negative 的信号进入 `signal_trap`
- 直觉 negative 但实际 positive 的信号进入 `counter_intuitive_opportunity`
- 高价值信号标为 `primary_trigger`
- 负向信号或陷阱信号标为 `risk_invalidator`
- 象限内信号效果能正确计算 `deltaPpVsQuadrant`
- 无协同组合时 `confirmationPairs = []`
- 低样本组合不会进入 `confirmationPairs`
- `playbook.invalidations` 必须包含可检查条件

### 前端验证

- 第一屏先看到操盘决策摘要。
- 「滚动指标」和「当日收益与超额」并列显示，且保留原图。
- 交易观察建议包含“看什么 / 用什么确认 / 什么会失效 / 样本约束”。
- 反直觉机会和信号陷阱有明确视觉区分。
- 信号按角色展示，不按业务分组列表展示。
- 象限条件效果能高亮当前象限。
- 组合确认最多 3 条，无有效组合时显示空状态。
- 完整信号排行、组合明细、业务分组调试视图均默认折叠。

## 验收标准

- 操盘手不用读完整信号表，就知道当前重点看哪些信号。
- 操盘手能看到反直觉机会和信号陷阱，而不是只看常规排行。
- 操盘手能知道信号在哪个象限/状态下有效。
- 操盘手不用读组合列表，就知道组合有没有增量。
- 页面能明确说明何时观察、何时等待、何时失效。
- 后端产物能被单元测试覆盖。
- 前端不承载核心业务判断，只呈现后端视图模型。
