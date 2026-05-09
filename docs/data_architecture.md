# 数据架构层级说明

> 本文档说明 AnchorLink 各数据模块的设计来源、架构位置和数据流向

---

## 架构层级总览

AnchorLink 采用**八层架构**设计：

```
L1. Config 层        → 池子配置加载
L2. Price 层         → 行情数据获取
L3. Pool State 层    → 池子状态计算
L4. Anchor Position 层 → 相对位置计算
L5. Group Rotation 层 → 组间轮动计算
L6. Linkage 层       → 联动分析计算（独立模块）
L7. Signal 层        → 信号标签生成
L8. Output 层        → 结论聚合 + 文件输出
```

---

## 各模块详细说明

### 1. 信号面板（Signal Panel）

**架构层级**：**L7 Signal 层**

**数据来源**：
- Pool State 层：median_return, up_ratio, volume_multiplier, fund_positive_ratio
- Anchor Position 层：relative_strength, position, rank_percentile
- Group Rotation 层：core_vs_theme_spread, core_vs_trading_spread

**计算逻辑**：
- 入口函数：`src/signal/label_generator.py` - `generate_signals()`
- 5类35+标签：
  - **Beta类**（行业环境）：行业Beta为正/负、行业扩散增强、行业分化
  - **Alpha类**（个股Alpha）：个股Alpha为正/负、跑赢主线池、处于行业前排
  - **Volume类**（资金成交）：放量上涨、资金价格共振、主力资金领先
  - **Rotation类**（板块轮动）：核心池强于主题情绪、交易观察池升温
  - **Abnormal类**（联动背离）：行业强但个股弱、主题池强但核心池弱

**阈值定义**：`src/signal/rules.py`
- BETA_POSITIVE_THRESHOLD = 0.5%
- VOLUME_HIGH_THRESHOLD = 1.5x
- ABNORMAL_SPREAD_THRESHOLD = 2%

**存储位置**：
- JSON字段：`industry_snapshot.signals[]`
- 每个信号包含：label, category, confidence, evidence

**前端组件**：`web/src/components/dashboard/signal-panel/index.tsx`

---

### 2. 综合结论（Conclusion Panel）

**架构层级**：**L8 Output 层**

**数据来源**：
- Signal 层：signal_result（所有信号标签）
- Pool State 层：pool_states（池子统计）
- Anchor Position 层：anchor_positions（相对位置）
- Group Rotation 层：group_rotation（轮动对比）
- Linkage 层：linkage_analysis（联动解释力）

**计算逻辑**：
- 入口函数：`src/output/conclusion_builder.py` - `build_conclusion()`

**结论字段**：
| 字段 | 类型 | 含义 |
|------|------|------|
| industry_beta | positive/neutral/negative | 行业环境判断 |
| anchor_alpha | positive/neutral/negative | 个股Alpha判断 |
| risk_level | low/medium/high | 风险等级 |
| summary | string | 综合判断文本（3-5句话） |
| next_watch | list[str] | 次日观察点（最多5条） |

**判定规则**：
- **industry_beta**：有"行业Beta为正"信号 → positive
- **anchor_alpha**：有"个股Alpha为正"信号 → positive
- **risk_level**：
  1. data_status == "insufficient_data" → high
  2. 有 abnormal 类信号 → high
  3. data_status == "partial" → medium
  4. strong_count/weak_count >= 3 → medium
  5. 默认 → low

**存储位置**：
- JSON字段：`industry_snapshot.conclusion`

**前端组件**：`web/src/components/dashboard/conclusion-panel/index.tsx`

---

### 3. 联动分析（Linkage Panel）

**架构层级**：**L6 Linkage 层**（独立模块，与其他层平级）

**数据来源**：
- 直接从 Price 层获取历史行情数据（不依赖其他中间层）

**计算逻辑**：
- 入口函数：`src/linkage/calculator.py` - `calculate_daily_linkage()`
- 计算锚定标的与池子成员的联动关系

**联动指标**：
| 指标 | 含义 | 计算方式 |
|------|------|---------|
| corr_5d/10d/20d | 相关性 | Pearson相关系数 `corr(anchor_return, member_return)` |
| beta_5d/10d/20d | 弹性系数 | `cov(member, anchor) / var(anchor)` |
| direction_consistency_Nd | 方向一致性 | 同向天数 / N（0-1，0.7+表示高度同向） |

**指标解读**：
- **corr > 0.6**：强联动，成员股与锚定标的涨跌高度相关
- **beta > 1**：高弹性，成员股波动幅度超过锚定标的
- **direction_consistency > 70%**：方向高度一致

**存储位置**：
- JSON字段：`industry_snapshot.linkage_analysis`
- 结构：
```json
{
  "pools": {
    "industry_chain": {
      "avg_corr_20d": 0.72,
      "avg_beta_20d": 1.15,
      "avg_direction_consistency_20d": 0.68,
      "top_members": [
        {
          "symbol": "301005.SZ",
          "corr_20d": 0.85,
          "beta_20d": 1.32
        }
      ]
    }
  }
}
```

**前端组件**：`web/src/components/dashboard/linkage-panel/index.tsx`

---

### 4. 同类矩阵（Peer Matrix）

**架构层级**：**L3-L4 层聚合输出**

**数据来源**：
- Pool State 层：成员涨跌幅、成交额、换手率、资金流向
- Anchor Position 层：排名位次、估值分位

**计算逻辑**：
- CSV生成：`src/output/csv_writer.py` - `write_peer_matrix()`
- 每行一个成员，列包括：

| 字段 | 含义 |
|------|------|
| ts_code | 股票代码 |
| name | 股票名称 |
| role | 角色（peer/proxy等） |
| relevance | 相关度权重 |
| pct_chg | 当日涨跌幅（%） |
| amount | 成交额（千元） |
| turnover_rate | 换手率（%） |
| fund_flow | 资金流向（元） |
| return_rank | 涨幅排名 |
| valuation_percentile | 估值分位（0-100） |

**存储位置**：
- 文件：`data/output/YYYYMMDD/peer_matrix.csv`

**前端展示**：`web/src/components/dashboard/ranking-table/index.tsx`

---

## 数据流向总图

```
Price 层（raw行情）
    │
    ├──────────────────────┬──────────────────────┐
    │                      │                      │
    ▼                      ▼                      ▼
Pool State 层         Anchor Position 层     Linkage 层
（池子统计）           （相对位置）           （联动分析）
    │                      │                      │
    │                      │                      │
    ▼                      ▼                      │
Group Rotation 层           │                      │
（组间轮动）                │                      │
    │                      │                      │
    └──────────────────────┴──────────────────────┘
                           │
                           ▼
                      Signal 层
                      （信号生成）
                           │
                           ▼
                      Output 层
                      （结论聚合 + 输出）
                           │
                           ▼
                   industry_snapshot.json
                           │
                           ▼
                      前端展示
```

---

## 关键文件路径汇总

| 模块 | 后端文件 | 前端文件 |
|------|---------|---------|
| **信号面板** | `src/signal/label_generator.py` | `web/src/components/dashboard/signal-panel/` |
| **综合结论** | `src/output/conclusion_builder.py` | `web/src/components/dashboard/conclusion-panel/` |
| **联动分析** | `src/linkage/calculator.py` | `web/src/components/dashboard/linkage-panel/` |
| **同类矩阵** | `src/output/csv_writer.py` | `web/src/components/dashboard/ranking-table/` |

---

## 设计特点

1. **层级分明**：每层只依赖下层，不跨层调用
2. **数据聚合**：Output层聚合所有中间层结果
3. **单一输出**：所有数据写入一个JSON文件（industry_snapshot.json）
4. **信号驱动**：结论基于信号标签规则判定，而非模型预测
5. **置信度量化**：每个信号有evidence支撑（数值、阈值、来源）

---

## JSON输出结构

```json
{
  "anchor": {
    "symbol": "688333.SH",
    "name": "铂力特",
    "themes": [...]
  },
  "as_of_date": "20260507",
  "data_quality": {
    "status": "ok",
    "missing_fields": []
  },
  "industry_state": {
    "median_return": 0.99,
    "up_ratio": 0.9
  },
  "anchor_position": {
    "anchor_return": 2.72,
    "relative_strength": 1.72,
    "return_rank": 2
  },
  "group_rotation": {
    "strongest_group": "theme_pool",
    "weakest_group": "trading_watchlist"
  },
  "signals": [
    {
      "label": "行业Beta为正",
      "category": "beta",
      "confidence": "low",
      "evidence": {...}
    }
  ],
  "conclusion": {
    "industry_beta": "positive",
    "anchor_alpha": "positive",
    "risk_level": "low",
    "summary": "...",
    "next_watch": [...]
  },
  "linkage_analysis": {
    "pools": {...}
  }
}
```

所有模块数据聚合到一个JSON，前端按字段读取各模块数据。