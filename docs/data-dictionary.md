# 数据字典

本文档记录 AnchorLink 系统产生的所有数据文件、字段含义及用途。

---

## 一、数据目录结构

```
data/
├── price/                          # 行情数据
│   ├── raw/                        # 原始数据（Tushare 拉取）
│   │   └── market_data.parquet
│   └── normalized/                 # 标准化数据
│       └── market_data_normalized.parquet
│
├── output/                         # 分析输出
│   ├── YYYYMMDD/                   # 每日快照目录（如 20260518/）
│   │   ├── industry_snapshot.json  # 当日完整快照
│   │   ├── peer_matrix.csv         # 池成员矩阵
│   │   └── industry_report.md      # 文字报告
│   │
│   ├── history_summary.csv         # 【主表】每日状态汇总
│   ├── history_rolling_metrics.csv # 滚动指标
│   ├── history_quadrant_stats.csv  # 九象限统计
│   ├── history_signal_lift.csv     # 信号效果
│   ├── history_state_transitions.csv # 状态转移
│   ├── history_extreme_divergences.csv # 极端背离事件
│   ├── history_event_study.csv     # 事件路径
│   ├── history_counter_intuitive_signals.csv # 反直觉信号
│   ├── history_conditional_signal_effects.csv # 条件信号效果
│   │
│   ├── history_personality_profile.json # 性格画像
│   ├── history_operator_playbook.json   # 操盘手册
│   ├── history_prediction_backtest.json # 预测回测
│   └── dashboard_view.json          # 前端视图（聚合数据）
```

---

## 二、数据生产流程

```
src.price.run              # 拉取行情数据 → data/price/
    ↓
src.dailyreport.run        # 生成每日快照 → data/output/YYYYMMDD/
    ↓
build_history_analysis.py  # 汇总历史分析 → data/output/history_*.csv
    ↓
build_dashboard_view.py    # 聚合前端数据 → data/output/dashboard_view.json
```

统一入口：
```bash
uv run python scripts/run_all.py
```

---

## 三、每日快照（data/output/YYYYMMDD/）

### 3.1 industry_snapshot.json

**说明**：当日的完整分析快照，包含所有池的状态、联动数据、信号。

**关键字段**：
```json
{
  "date": "20260518",
  "anchor": {
    "symbol": "688333.SH",
    "name": "铂力特",
    "return": -0.2
  },
  "pools": {
    "direct_peers": { "median": 1.5, "up_ratio": 0.7 },
    "industry_chain": { "median": 0.8, "up_ratio": 0.6 },
    "theme_pool": { "median": 0.5, "up_ratio": 0.5 },
    "trading_watchlist": { "median": 1.2, "up_ratio": 0.8 }
  },
  "beta_alpha": {
    "industry_beta": "positive",
    "anchor_alpha": "neutral",
    "risk_level": "low"
  },
  "signals": ["行业Beta为正", "交易池升温"],
  "linkage": {
    "corr_5d": 0.72,
    "beta_5d": 1.3
  }
}
```

### 3.2 peer_matrix.csv

**说明**：所有池成员的详细数据，包括涨跌、排名、联动指标。

**字段**：
| 字段 | 说明 |
|------|------|
| symbol | 股票代码 |
| name | 股票名称 |
| pool | 所属池子 |
| return | 当日收益(%) |
| amount | 成交额(亿) |
| turnover | 换手率(%) |
| corr_5d | 5日相关性 |
| beta_5d | 5日Beta |
| direction_consistency_5d | 5日方向一致性 |

---

## 四、历史汇总表

### 4.1 history_summary.csv【主表】

**说明**：最重要的表，每日一行，记录当天的完整状态 + 前瞻收益。

**位置**：`data/output/history_summary.csv`

**字段说明**：

| 字段 | 类型 | 说明 | 用途 |
|------|------|------|------|
| `date` | string | 日期 YYYYMMDD | 主键 |
| `anchor_return` | float | 铂力特当日收益(%) | 看个股表现 |
| `direct_peers_median` | float | 直接同业池中位数(%) | 看同业表现 |
| `industry_chain_median` | float | 产业链池中位数(%) | 看板块表现 |
| `theme_pool_median` | float | 主题池中位数(%) | 看情绪 |
| `trading_watchlist_median` | float | 交易观察池中位数(%) | 看联动 |
| `relative_strength_vs_direct` | float | 相对同业超额(%) | 看 Alpha |
| `relative_strength_vs_industry_chain` | float | 相对产业链超额(%) | 看 Alpha |
| `relative_strength_vs_theme` | float | 相对主题超额(%) | 看 Alpha |
| `direct_up_ratio` | float | 同业上涨家数比 | 看板块广度 |
| `chain_up_ratio` | float | 产业链上涨家数比 | 看板块广度 |
| `amount_expansion_ratio` | float | 量能扩张比 | 看放量 |
| `moneyflow_positive_ratio` | float | 主力资金净流入比 | 看资金 |
| `strongest_group` | string | 最强池名称 | 看轮动 |
| `weakest_group` | string | 最弱池名称 | 看轮动 |
| `industry_beta` | string | 行业Beta状态 | positive/neutral/negative |
| `anchor_alpha` | string | 个股Alpha状态 | positive/neutral/negative |
| `risk_level` | string | 风险等级 | low/medium/high |
| `signal_labels` | string | 信号标签（逗号分隔） | 看当天信号 |
| `signal_categories` | string | 信号类别（逗号分隔） | beta/alpha/volume/rotation/abnormal |
| `signal_pairs` | string | 信号详情（JSON） | 含 category 和 label |
| `data_quality_status` | string | 数据质量状态 | ok/insufficient_data |
| `next_1d_return` | float | 次日收益(%) | 回测用 |
| `next_3d_return` | float | 3日后收益(%) | 回测用 |
| `next_5d_return` | float | 5日后收益(%) | 回测用 |
| `next_1d_excess_vs_chain` | float | 次日相对板块超额(%) | 回测用 |
| `next_3d_excess_vs_chain` | float | 3日后相对板块超额(%) | 回测用 |
| `next_5d_excess_vs_chain` | float | 5日后相对板块超额(%) | 回测用 |

**示例数据**：
```csv
date,anchor_return,industry_chain_median,relative_strength_vs_industry_chain,industry_beta,anchor_alpha,risk_level,signal_labels,next_1d_return
20260518,-0.2,1.5,-1.7,positive,neutral,low,"行业Beta为正,交易池升温",-0.95
```

---

### 4.2 history_rolling_metrics.csv

**说明**：滚动窗口指标，累计超额、连续天数。

**位置**：`data/output/history_rolling_metrics.csv`

**字段**：

| 字段 | 说明 |
|------|------|
| `date` | 日期 |
| `excess_5d` | 5日累计超额(%) |
| `excess_10d` | 10日累计超额(%) |
| `outperform_streak` | 跑赢连胜天数（负数为跑输连败） |
| `beta_streak` | Beta状态连续天数 |
| `theme_vs_core_streak` | 主题强于核心连续天数 |
| `risk_high_streak` | 高风险连续天数 |

---

### 4.3 history_quadrant_stats.csv

**说明**：九象限统计，按 industry_beta × anchor_alpha 分组。

**位置**：`data/output/history_quadrant_stats.csv`

**字段**：

| 字段 | 说明 |
|------|------|
| `quadrant` | 象限名称（如"行业强+个股弱"） |
| `count` | 样本天数 |
| `avg_next_1d` | 次日平均收益(%) |
| `avg_next_3d` | 3日平均收益(%) |
| `avg_next_5d` | 5日平均收益(%) |
| `avg_next_1d_excess` | 次日平均超额(%) |
| `win_rate_1d` | 次日胜率 |
| `avg_relative_strength` | 平均相对强度 |

**用途**：回答"历史上行业强但个股弱时，后来怎样？"

---

### 4.4 history_signal_lift.csv

**说明**：信号效果分析，每个信号的历史表现。

**位置**：`data/output/history_signal_lift.csv`

**字段**：

| 字段 | 说明 |
|------|------|
| `label` | 信号标签 |
| `category` | 信号类别 |
| `count` | 出现次数 |
| `avg_next_1d` | 次日平均收益(%) |
| `avg_next_3d` | 3日平均收益(%) |
| `avg_next_5d` | 5日平均收益(%) |
| `win_rate_1d` | 次日胜率 |
| `baseline_avg_next_1d` | 基线收益(%) |
| `avg_next_1d_delta_pp` | 相对基线增量(百分点) |
| `lift_next_1d` | 收益提升率 |

**用途**：回答"交易池升温时，胜率多少？"

---

### 4.5 history_state_transitions.csv

**说明**：状态转移矩阵，从一个状态转向另一个状态的概率。

**位置**：`data/output/history_state_transitions.csv`

**字段**：

| 字段 | 说明 |
|------|------|
| `from_state` | 来源状态（如"positive+neutral"） |
| `to_state` | 目标状态 |
| `count` | 出现次数 |
| `probability` | 转移概率 |

**用途**：回答"行业强+个股中 最可能转向哪个状态？"

---

### 4.6 history_extreme_divergences.csv

**说明**：极端背离事件，个股与板块走势严重偏离。

**位置**：`data/output/history_extreme_divergences.csv`

**字段**：

| 字段 | 说明 |
|------|------|
| `date` | 日期 |
| `anchor_return` | 个股收益(%) |
| `industry_chain_median` | 板块中位数(%) |
| `divergence` | 背离幅度(%) |
| `industry_beta` | 当日行业状态 |
| `anchor_alpha` | 当日个股状态 |
| `signal_labels` | 当日信号 |

**用途**：识别异常事件，研究极端情况的后续表现。

---

### 4.7 history_event_study.csv

**说明**：事件研究路径，极端背离事件前后的走势。

**位置**：`data/output/history_event_study.csv`

**字段**：

| 字段 | 说明 |
|------|------|
| `event_date` | 事件日期 |
| `offset` | 偏移天数（-5 到 +5） |
| `date` | 具体日期 |
| `anchor_return` | 个股收益(%) |
| `chain_median` | 板块中位数(%) |
| `excess` | 超额收益(%) |

**用途**：看极端事件后的典型路径。

---

### 4.8 history_counter_intuitive_signals.csv

**说明**：反直觉信号，直觉预期与实际相反的信号。

**位置**：`data/output/history_counter_intuitive_signals.csv`

**字段**：

| 字段 | 说明 |
|------|------|
| `label` | 信号标签 |
| `intuitive_direction` | 直觉预期方向 |
| `actual_direction` | 实际方向 |
| `degree` | 偏差程度 |
| `explanation` | 解释说明 |

---

### 4.9 history_conditional_signal_effects.csv

**说明**：条件信号效果，某个信号在特定象限内的表现。

**位置**：`data/output/history_conditional_signal_effects.csv`

**字段**：

| 字段 | 说明 |
|------|------|
| `label` | 信号标签 |
| `quadrant` | 象限 |
| `count` | 出现次数 |
| `avg_next_1d` | 次日平均收益(%) |
| `win_rate_1d` | 次日胜率 |
| `avg_next_1d_delta_pp_vs_quadrant` | 相对象限增量 |

---

## 五、派生分析（JSON）

### 5.1 history_personality_profile.json

**说明**：铂力特的历史性格画像，总结其行为模式。

**位置**：`data/output/history_personality_profile.json`

**核心内容**：
- `summary_metrics`：摘要指标（基线胜率、盈亏比、夏普比）
- `habit_patterns`：习惯模式（喜欢什么、讨厌什么）
- `counter_intuitive_patterns`：反直觉模式
- `trap_patterns`：陷阱模式
- `relationship_profile`：与各板块的关系画像
- `path_patterns`：极端事件的典型路径
- `stability`：稳定性评估

---

### 5.2 history_operator_playbook.json

**说明**：操盘手册，面向交易员的建议。

**位置**：`data/output/history_operator_playbook.json`

**核心内容**：
- `regime`：当前市场制度判断
- `playbook`：操作建议（观察什么、确认什么、什么情况失效）
- `signal_roles`：信号角色分类
- `confirmation_pairs`：可作为确认条件的信号组合

---

### 5.3 history_prediction_backtest.json

**说明**：历史相似案例预测的回测验证结果。

**位置**：`data/output/history_prediction_backtest.json`

**核心内容**：
- `metrics_by_period`：分时段指标（30/60/90天）
  - `ic`：IC（Spearman 相关系数）
  - `direction_accuracy`：方向准确率
  - `rmse`：预测误差
- `stability_metrics`：稳定性指标
- `quintile_returns`：分组测试结果（Q1-Q5）
- `confidence_intervals`：置信区间

---

### 5.4 dashboard_view.json

**说明**：前端视图数据，聚合所有分析结果，供 `/history-v2` 页面直接使用。

**位置**：`data/output/dashboard_view.json`

**核心结构**：
- `meta`：页面元数据
- `summary`：摘要信息（当前映射、路径标签）
- `cards`：指标卡片
- `mapData`：热力图数据
- `trends`：趋势数据
- `tableData`：表格数据
- `personality`：性格画像
- `operator`：操盘手册
- `predictionEvaluation`：预测评估
- `dateIndex`：按日期索引的映射数据

---

## 六、四池定义

| 池子 | 英文标识 | 说明 | 成员来源 |
|------|----------|------|----------|
| 增材制造本业池 | `direct_peers` | 直接竞争对手 | 同行业公司 |
| 商业航天产业链池 | `industry_chain` | 上下游产业链 | 产业链相关公司 |
| 商业航天主题池 | `theme_pool` | 主题情绪股 | 概念相关公司 |
| 交易联动观察池 | `trading_watchlist` | 高频联动股 | 与铂力特联动紧密的股票 |

配置文件：`config/pools.yaml`

---

## 七、信号分类

| 类别 | 英文标识 | 说明 | 示例信号 |
|------|----------|------|----------|
| Beta | `beta` | 行业相关 | 行业Beta为正、行业扩散增强 |
| Alpha | `alpha` | 个股相关 | 个股Alpha为正、跑赢主线池 |
| Volume | `volume` | 量能相关 | 放量上涨、缩量调整 |
| Rotation | `rotation` | 轮动相关 | 主题池强于核心池、交易池升温 |
| Abnormal | `abnormal` | 异常情况 | 行业强但个股弱、行业弱但个股强 |

---

## 八、数据时间范围

| 数据 | 时间范围 | 说明 |
|------|----------|------|
| 历史汇总表 | 约 1 年（243 个交易日） | 2025-05-16 ~ 2026-05-18 |
| 每日快照 | 同上 | 每日一个目录 |
| 前瞻收益 | 排除最近 5 天 | T+5 需要未来数据 |

---

## 九、常见查询示例

### 查询个股和板块的联动关系
```sql
SELECT date, anchor_return, industry_chain_median, relative_strength_vs_industry_chain
FROM history_summary
ORDER BY date
```

### 查询"行业强+个股弱"的历史表现
```sql
SELECT * FROM history_quadrant_stats 
WHERE quadrant = '行业强+个股弱'
```

### 查询"交易池升温"信号的胜率
```sql
SELECT * FROM history_signal_lift 
WHERE label LIKE '%交易池%'
```

### 查询极端背离事件
```sql
SELECT * FROM history_extreme_divergences 
ORDER BY ABS(divergence) DESC
```

---

# 第二部分：前后端数据契约（DashboardView）

> 本部分定义 DashboardView 数据层的标准规范和字段映射，是前后端数据交互的唯一依据。
> TypeScript 类型定义：`web/src/types/dashboard-view.ts`｜JSON Schema：`data/schema/dashboard_view.schema.json`

## 十、命名规范

所有标识符使用小驼峰（camelCase）。

| 类型 | 规则 | 示例 |
|------|------|------|
| 普通字段 | 描述性名词/名词短语 | `tradingDate`, `signalName` |
| 布尔字段 | `is`/`has`/`should`/`can`前缀 | `isValid`, `hasSignal` |
| 数组字段 | 复数形式 | `similarCases`, `signals` |
| 日期字段 | `Date`后缀，格式 `YYYY-MM-DD` | `tradingDate` |

枚举类型用 PascalCase + Enum 后缀，枚举值用 UPPER_SNAKE_CASE。

---

## 十一、数据类型约定

| 类型 | 说明 | 示例 |
|------|------|------|
| `string` | 文本、日期、枚举值 | `"2026-05-11"`, `"dominantLeader"` |
| `number` | 整数、浮点数、百分比 | `0.85`, `120`, `3.14` |
| `boolean` | 逻辑值 | `true`, `false` |
| `null` | 数据缺失 | `null`，前端显示为 `--` |
| 数组 | 同类型元素集合 | `SimilarCaseRecord[]` |
| 枚举 | 有限取值字符串集合 | `QuadrantEnum` |

**特殊约定**：
- 百分比存储为小数（85% → `0.85`），前端显示时乘100加 `%`
- 日期统一 `YYYY-MM-DD` 字符串
- 空值统一 `null`，禁止 `""`、`0`、`NaN`
- 数值精度：百分比保留2位小数，绝对数值保留2位小数，整数无小数

---

## 十二、DashboardView 结构

```typescript
interface DashboardView {
  meta: Meta                 // 元数据
  filter: Filter             // 筛选条件
  summary: SummaryInfo       // 核心摘要
  cards: CardInfo[]          // 15张指标卡片
  mapData: MapDataInfo       // 矩阵/热力图
  trends: TrendsInfo         // 趋势/时间轴
  tableData: TableDataInfo   // 表格/列表
  personality: PersonalityInfo // 历史性格档案
  operator: OperatorInfo     // 交易员视角
  aiInsight: AiInsightInfo   // AI研判/建议
}
```

---

## 十三、校验规则

三层校验确保数据100%合规：

1. **格式校验**（JSON Schema）：必填字段存在、类型正确、枚举值合法
2. **类型校验**（TypeScript）：字段访问安全、类型使用正确
3. **业务规则校验**：数值范围合理、逻辑一致、与旧页面显示一致

校验脚本：`scripts/validate_data.py`

---

## 十四、v2 页面字段映射

以下为 `/history-v2` 页面 110 个显示字段与 `dashboard_view.json` 的映射关系。

### 1. TopBar 组件

| 序号 | 页面位置 | 数据路径 | 格式 |
|------|---------|----------|------|
| 1 | 页面主标题 | 固定「历史分析」 | 直接显示 |
| 2 | 日期范围说明 | `meta.dateRange` | 「X个交易日 · YYYYMMDD ~ YYYYMMDD」 |
| 3 | 筛选-起始日期 | `filter.startDate` | YYYY-MM-DD |
| 4 | 筛选-结束日期 | `filter.endDate` | YYYY-MM-DD |
| 5 | 筛选-信号类别 | `filter.signalCategory` | 全部/偏好/规避/反直觉/陷阱 |

### 2. TradingView 组件

#### 2.1 顶部三张卡片

| 序号 | 页面位置 | 数据路径 | 格式 |
|------|---------|----------|------|
| 6 | 卡片1标题 | `cards[0].title` | 固定「历史规律可信度」 |
| 7 | 卡片1值 | `cards[0].value` | high→高(红)，medium→中(黄)，low→低(灰) |
| 8 | 卡片1badge | `cards[0].badge` | stable→稳定，deteriorating→下降，concerning→警告，insufficient→不足 |
| 9 | 卡片1描述 | `cards[0].description` | 直接显示 |
| 10 | 卡片2标题 | `cards[1].title` | 固定「当前操作倾向」 |
| 11 | 卡片2值 | `cards[1].value` | 积极观察/谨慎观察/观望 |
| 12 | 卡片2描述 | `cards[1].description` | 直接显示 |
| 13 | 卡片3标题 | `cards[2].title` | 固定「主要失效点」 |
| 14 | 卡片3值 | `cards[2].value` | 直接显示 |
| 15 | 卡片3描述 | `cards[2].description` | 直接显示 |

#### 2.2 四个建议模块

| 序号 | 页面位置 | 数据路径 | 格式 |
|------|---------|----------|------|
| 16 | 看什么 | `aiInsight.advice.watch` | 直接显示 |
| 17 | 用什么确认 | `aiInsight.advice.confirm` | 直接显示 |
| 18 | 什么会失效 | `aiInsight.advice.failure` | 直接显示 |
| 19 | 样本约束 | `aiInsight.advice.constraint` | 直接显示 |

### 3. HistoryMapping 组件

#### 3.1 头部与当前状态

| 序号 | 页面位置 | 数据路径 | 格式 |
|------|---------|----------|------|
| 20 | 模块标题 | 固定「今日历史映射」 | 直接显示 |
| 21 | 模块说明 | 固定文本 | 直接显示 |
| 22 | 相似样本数 | `summary.currentMapping.similarSampleCount` | 「相似样本 X个」 |
| 23 | 当前日期 | `summary.currentMapping.date` | YYYYMMDD，等宽 |
| 24 | 当前状态 | `summary.currentMapping.state` | 直接显示 |
| 25 | 状态标签 | `summary.currentMapping.tags` | 循环显示，带边框 |
| 26 | 路径标签 | `summary.pathLabel` | strong_rise→强势延续(红)，continue_fall→继续走弱(绿)，其他→灰色 |

#### 3.2 历史路径统计

| 序号 | 页面位置 | 数据路径 | 格式 |
|------|---------|----------|------|
| 27-29 | T+1 收益/胜率/超额 | `tableData.windowStats[0].avgReturn/winRate/avgExcess` | 收益超额：2位小数+%/pp，正红↑负绿↓；胜率：×100+%，0位小数 |
| 30-32 | T+3 收益/胜率/超额 | `tableData.windowStats[1].*` | 同上 |
| 33-35 | T+5 收益/胜率/超额 | `tableData.windowStats[2].*` | 同上 |

#### 3.3 最相似历史案例

| 序号 | 页面位置 | 数据路径 | 格式 |
|------|---------|----------|------|
| 36 | 案例日期 | `tableData.similarCases[N].date` | YYYYMMDD，等宽 |
| 37 | 相似度 | `tableData.similarCases[N].similarity` | 「相似度 X.XX」 |
| 38 | 匹配状态标签 | `tableData.similarCases[N].matchingStates` | 蓝色badge |
| 39 | 匹配信号标签 | `tableData.similarCases[N].matchingSignals` | 灰色标签 |
| 40-42 | T+1/T+3/T+5收益 | `tableData.similarCases[N].next1dReturn/next3dReturn/next5dReturn` | 2位小数，正红负绿+% |

### 4. TransitionHeatmap 组件

#### 4.1 路径判断

| 序号 | 页面位置 | 数据路径 | 格式 |
|------|---------|----------|------|
| 43 | 路径判断标题 | `summary.transitionVerdict.title` | 蓝色背景高亮 |
| 44 | 路径判断描述 | `summary.transitionVerdict.description` | 直接显示 |
| 45 | 观察要点 | `summary.transitionVerdict.watchPoints` | 橙色圆点标记 |

#### 4.2 路径排名

| 序号 | 页面位置 | 数据路径 | 格式 |
|------|---------|----------|------|
| 46 | 排名 | `tableData.rankedTransitionPaths[N].rank` | 灰色圆圈背景 |
| 47 | 路径名称 | `tableData.rankedTransitionPaths[N].path` | 「转向 {toState}」 |
| 48 | 路径说明 | 计算生成 | 「偏X修复」 |
| 49 | 样本数 | `tableData.rankedTransitionPaths[N].count` | 「n=X」 |
| 50 | 平均收益 | `tableData.rankedTransitionPaths[N].avgReturn` | 2位小数+pp，正红负绿 |
| 51 | 星级 | 根据收益和样本量计算 | 1-5星 |

#### 4.3 热力图矩阵

| 序号 | 页面位置 | 数据路径 | 格式 |
|------|---------|----------|------|
| 52 | 单元格数值 | `mapData.transitionMatrix[from][to]` | 数值越大蓝色越深 |
| 53 | 行列状态标签 | 状态名称简化 | 如「强+强」 |
| 54 | 当前状态高亮 | 比较当前状态 | 橙色边框 |
| 55 | 最高概率路径 | 最高概率单元格 | 橙色边框 |

### 5. StabilityPanel 组件

| 序号 | 页面位置 | 数据路径 | 格式 |
|------|---------|----------|------|
| 56 | 稳定性结论 | `personality.stability.earlyVsRecentNotes[0]` | 橙色背景高亮 |
| 57-58 | 5日超额 | `cards[3].value/description` | 偏弱/震荡/偏强 |
| 59-60 | 10日超额 | `cards[4].value/description` | 同上 |
| 61-62 | 今日偏离 | `cards[5].value/description` | 不强/中等/明显 |
| 63 | 跑赢主线池图表 | `trends.excessReturn` | 紫(5日)/蓝(10日)/红(连胜)曲线 |
| 64 | 跟随偏离图表 | `trends.followDeviation` | 红(个股)/蓝虚(板块)/紫(超额)曲线 |
| 65-66 | 图表说明 | 固定文本 | 直接显示 |

### 6. PersonalityProfile 组件

| 序号 | 页面位置 | 数据路径 | 格式 |
|------|---------|----------|------|
| 67 | 性格环形图 | `summary.profile.donutData` | 偏好(红)/规避(绿)/反直觉(紫)/陷阱(橙) |
| 68 | 性格标签 | `summary.profile.tags` | 三个标签 |
| 69-70 | 性格标题/描述 | `summary.profile.title/description` | 直接显示 |
| 71 | 样本数 | `cards[6].value` | 「X/Y」等宽 |
| 72 | 置信度 | `cards[7].value` | high→高(绿)，medium→中，low→低 |
| 73 | 基线胜率 | `cards[8].value` | 「X%」等宽绿 |
| 74-75 | 胜率 | `cards[9].value` | ×100，1位小数+%，红 |
| 76-77 | T+3超额 | `cards[10].value` | 2位小数+pp，绿 |
| 78-79 | T+3不利 | `cards[11].value` | 2位小数+pp，绿 |
| 80-81 | 盈亏比 | `cards[12].value` | 2位小数+x，红 |
| 82-83 | 夏普 | `cards[13].value` | 2位小数，红 |
| 84-85 | 信号覆盖 | `cards[14].value` | ×100，0位小数+%，红 |
| 86 | 偏好环境列表 | `personality.habitPatterns[likes]` | 按收益降序，红边框 |
| 87 | 规避环境列表 | `personality.habitPatterns[dislikes]` | 按收益升序，绿边框 |
| 88 | 产业联动关系 | `personality.relationshipProfile` | 跟随/领先/滞后+相关系数 |
| 89 | 反直觉机会 | `personality.counterIntuitivePatterns` | 紫边框 |
| 90 | 信号陷阱 | `personality.trapPatterns` | 橙边框 |
| 91 | 路径模式标签 | `personality.pathPatterns[*].eventLabel` | 名称+样本数 |
| 92 | 路径图表 | `personality.pathPatterns[i].avgPath` | 红(个股)/灰虚(板块)/绿虚(超额) |
| 93 | 路径总结 | `personality.pathPatterns[i].summary` | 直接显示 |

### 7. SignalTimeline 组件

| 序号 | 页面位置 | 数据路径 | 格式 |
|------|---------|----------|------|
| 94 | 价格曲线 | `trends.signalTimeline.price` | 红色实线 |
| 95 | 信号标记点 | `mapData.signalMarks` | 偏好红/规避绿/反直觉紫/陷阱橙 |
| 96 | 时间轴刻度 | `trends.signalTimeline.dates` | YYYY-MM |
| 97-100 | 信号轨道 | `mapData.signalLanes.likes/dislikes/counter_intuitive/trap` | 彩色小点 |
| 101 | 轨道样本量 | `mapData.signalLanes.*.count` | 「X次」灰色 |
| 102-107 | 信号详情面板 | `tableData.signalDetail.*` | 日期/价格/涨跌幅/命中信号 |

### 8. 底部研究明细

| 序号 | 页面位置 | 数据路径 | 格式 |
|------|---------|----------|------|
| 108 | 标题 | 固定「研究明细」 | 折叠面板 |
| 109 | 说明 | 固定文本 | 头部右侧灰色 |
| 110 | 内容 | `aiInsight.researchDetails` | 直接显示 |

---

## 十五、格式化工具函数

统一使用 `src/lib/history-v2/formatters.ts`：

| 函数 | 用途 |
|------|------|
| `formatDate(value, format)` | 日期格式化 |
| `formatPercent(value, decimals=2)` | 百分比格式化，自动正负颜色 |
| `formatPp(value, decimals=2)` | pp单位格式化 |
| `formatSignalBadge(type)` | 信号标签样式映射 |
| `formatQuadrantName(value)` | 象限状态名称映射 |
| `formatPathLabel(value)` | 路径标签映射和颜色 |
