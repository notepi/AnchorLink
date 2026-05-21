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
