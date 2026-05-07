# AnchorLink 产品架构设计文档

> 版本：v0.3
> 文档类型：产品架构设计
> 对应 PRD：`docs/prd.md` v0.3
> 目标系统：TradingTS / AnchorLink
> 最后更新：2026-05-01

---

## 0. 一句话架构

AnchorLink 是一个 **围绕锚定标的的行业位置判断模块**。

它的架构不是从“代码模块”开始，而是从一个投研问题开始：

```text
锚定标的今天涨跌了
        |
        v
这是它自己的问题，还是行业、产业链、主题情绪、交易资金的问题？
```

AnchorLink 的架构就是为了稳定回答这个问题。

---

## 1. 产品架构总览

```text
                         +----------------------+
                         |      锚定标的 Anchor  |
                         |   例如：688333.SH 铂力特 |
                         +----------+-----------+
                                    |
                                    v
          +------------------------------------------------+
          |              四个并列股票池 / Universe          |
          |                                                |
          |  +------------------+    +------------------+  |
          |  | 核心同类池        |    | 产业链池          |  |
          |  | Direct Peers     |    | Industry Chain   |  |
          |  | 真正可比公司      |    | 上下游/需求传导   |  |
          |  +------------------+    +------------------+  |
          |                                                |
          |  +------------------+    +------------------+  |
          |  | 主题情绪池        |    | 交易观察池        |  |
          |  | Theme Pool       |    | Trading Watchlist |  |
          |  | 主题热度/扩散     |    | 短期异动/资金切换 |  |
          |  +------------------+    +------------------+  |
          +---------------------+--------------------------+
                                |
                                v
              +--------------+--------------+
              |     分别计算每个池子的状态     |
              | 按 membership 口径计算状态     |
              | benchmark / ranking / report  |
              +--------------+--------------+
                             |
                             v
              +--------------+--------------+
              |     判断锚定标的相对位置       |
              | 跑赢/跑输/前排/掉队/独立异动   |
              +--------------+--------------+
                             |
                             v
              +--------------+--------------+
              |      生成结构化行业结论        |
              | 行业 Beta / 个股 Alpha / 轮动  |
              +--------------+--------------+
                             |
                             v
        +--------------------+--------------------+
        |                    |                    |
        v                    v                    v
+---------------+    +---------------+    +----------------+
| snapshot.json |    | peer_matrix   |    | report.md      |
| 给系统读       |    | 给人检查       |    | 给人阅读        |
+---------------+    +---------------+    +----------------+
```

四个池是围绕 Anchor 的并列观察视角，不是递进链路。它们统一进入池子状态计算，再统一进入锚定相对位置判断。

---

## 2. 架构要回答的核心问题

AnchorLink 每天只围绕一个 Anchor 工作。它要回答 5 个问题。

| 问题 | 架构中的回答方式 |
| --- | --- |
| 今天是行业整体问题，还是个股问题？ | 比较 Anchor 与核心同类池、产业链池的相对强弱。 |
| 主题热度有没有传导到核心同类？ | 比较主题情绪池与核心同类池的强弱差。 |
| Anchor 在行业里是前排还是掉队？ | 计算 Anchor 在各池子中的涨幅、成交、资金排名。 |
| 资金和成交是否支持这个走势？ | 比较成交额放大、换手率、主力净流入和资金扩散。 |
| 上层系统该如何使用这个结论？ | 输出稳定的 `industry_snapshot.json`。 |

---

## 3. 第一层：锚定标的

### 3.1 Anchor 是什么

Anchor 是本次分析的中心股票。

例如：

```text
Anchor = 铂力特 688333.SH
```

所有分析都围绕它展开：

- 它相对核心同类强不强？
- 它相对产业链强不强？
- 它有没有跟上主题情绪？
- 它的成交和资金是否异常？

### 3.2 Anchor 不是什么

Anchor 不是股票池的一员用来算平均值。

架构规则：

```text
Anchor 可以参与排名
Anchor 默认不参与自身 benchmark
```

原因很简单：不能把“被分析对象”放进“对照组均值”里，否则相对强弱会被污染。

---

## 4. 第二层：四类股票池

股票池是 AnchorLink 最核心的产品资产。

架构上必须把四类池子分开，因为它们回答的问题不同。

### 4.1 四类股票池

| 股票池 | 中文名 | 解决的问题 | 能不能当核心基准 |
| --- | --- | --- | --- |
| `direct_peers` | 核心同类池 | 真正业务可比公司今天强不强？ | 能 |
| `industry_chain` | 产业链池 | 上下游有没有联动或传导？ | 能 |
| `theme_pool` | 主题情绪池 | 市场是不是在炒主题？ | 默认不能 |
| `trading_watchlist` | 交易观察池 | 短期资金有没有切换或异动？ | 不能 |

### 4.2 为什么不能混在一起

如果把四类股票混在一起算平均，会得到一个看似精确但实际没意义的结果。

例如：

```text
核心同类弱
主题情绪强
交易观察池暴涨
```

如果混算，可能显示“板块中性偏强”。

但真实结论应该是：

```text
主题热，但核心同类没有确认。
Anchor 如果上涨，可能更多是情绪带动，而不是核心业务同频。
```

这就是 Universe 必须是一等资产的原因。

### 4.3 每只股票进入池子必须有身份

一只股票进入某个池子，不只是写一个代码，还必须说明：

| 字段 | 作用 |
| --- | --- |
| `symbol` | 股票代码。 |
| `role` | 它在这个池子里扮演什么角色。 |
| `relevance` | 它和 Anchor 或主题的相关度。 |
| `reason` | 为什么它应该进入这个池子。 |
| `include_in_benchmark` | 是否参与池子均值/中位数。 |
| `include_in_ranking` | 是否参与排名。 |
| `include_in_report` | 是否展示在报告里。 |

核心规则：

```text
一只股票可以出现在多个池子里
但每次出现都代表不同身份
```

### 4.4 底层配置设计

底层配置不要把四个池子做成互斥列表。正确做法是两层结构：

```text
证券主数据 Instrument
    一只股票只维护一份事实信息

股票池成员关系 Membership
    一只股票可以在多个池子里出现多次
    每次出现都有独立 role / reason / relevance / 计算口径
```

也就是说，底层是一个多对多关系：

```text
Instrument 1  <---->  N Universe Membership  N  <---->  1 Universe
```

推荐配置结构：

```yaml
version: "2026-05-01"

anchor:
  symbol: 688333.SH
  name: 铂力特

instruments:
  - symbol: 688333.SH
    name: 铂力特
    market: A-share
    exchange: SH
    fact_tags: [金属3D打印, 增材制造, 商业航天制造链]

  - symbol: 688433.SH
    name: 华曙高科
    market: A-share
    exchange: SH
    fact_tags: [增材制造, 3D打印设备]

universes:
  - universe_id: direct_peers
    display_name: 核心同类池
    purpose: 真正业务可比公司
    can_be_benchmark: true
    min_size: 3

  - universe_id: industry_chain
    display_name: 产业链池
    purpose: 上下游和需求传导
    can_be_benchmark: true
    min_size: 3

  - universe_id: theme_pool
    display_name: 主题情绪池
    purpose: 主题热度和扩散
    can_be_benchmark: false
    min_size: 3

  - universe_id: trading_watchlist
    display_name: 交易观察池
    purpose: 短期资金切换和异动
    can_be_benchmark: false
    min_size: 1

memberships:
  - universe_id: direct_peers
    symbol: 688433.SH
    role: direct_comparable
    relevance: 0.90
    weight: 1.0
    enabled: true
    include_in_benchmark: true
    include_in_ranking: true
    include_in_report: true
    reason: 同属增材制造赛道，业务可比。
    added_at: "2026-05-01"
    reviewed_at: "2026-05-01"

  - universe_id: theme_pool
    symbol: 688433.SH
    role: theme_heat_proxy
    relevance: 0.65
    weight: 0.5
    enabled: true
    include_in_benchmark: false
    include_in_ranking: true
    include_in_report: true
    reason: 同属 3D 打印主题，可观察主题情绪传导。
    added_at: "2026-05-01"
    reviewed_at: "2026-05-01"
```

这个例子里，`688433.SH 华曙高科` 同时出现在 `direct_peers` 和 `theme_pool`，但它不是重复股票，而是两个不同的 membership：

| symbol | universe | role | benchmark | 含义 |
| --- | --- | --- | --- | --- |
| `688433.SH` | `direct_peers` | `direct_comparable` | 是 | 作为核心同类参与对比。 |
| `688433.SH` | `theme_pool` | `theme_heat_proxy` | 否 | 作为主题热度观察对象。 |

配置约束：

- `instruments.symbol` 全局唯一。
- `memberships` 里允许同一 `symbol` 出现多次。
- `membership` 的唯一键是 `universe_id + symbol`。
- 同一 `symbol` 在不同池子里的 `role`、`reason`、`weight` 可以不同。
- 是否参与 benchmark、ranking、report 必须由 membership 单独决定。
- 计算时不能只按 `symbol` 去重，否则会丢失它在不同池子里的身份。

---

## 5. 第三层：市场观察

Market 层只负责提供事实数据，不负责下结论。

### 5.1 需要观察什么

每只股票每天需要这些市场观察值：

| 观察值 | 用途 |
| --- | --- |
| 涨跌幅 | 判断价格强弱。 |
| 成交额 | 判断热度和放量。 |
| 换手率 | 判断交易活跃度。 |
| 主力净流入 | 判断资金方向。 |
| PE / PB / PS | 判断估值位置。 |
| 市值 | 辅助比较规模。 |
| 停牌/缺失状态 | 控制数据质量。 |

### 5.2 Market 层的边界

Market 层只说：

```text
这只股票今天涨了多少
成交是多少
资金是多少
估值是多少
数据是否缺失
```

它不说：

```text
行业强
个股弱
可以买
风险很大
```

这些是后面几层的职责。

---

## 6. 第四层：池子状态

Pool State 层负责分别计算每个池子今天强不强。

### 6.1 池子状态的计算口径

每个池子的状态必须按 membership 上的三个开关来算：

| 口径 | 使用哪些成员 | 用途 |
| --- | --- | --- |
| `benchmark_scope` | `enabled=true` 且 `include_in_benchmark=true` 的成员。 | 计算池子均值、中位数、广度、资金扩散等核心状态。 |
| `ranking_scope` | `enabled=true` 且 `include_in_ranking=true` 的成员，必要时显式加入 Anchor。 | 计算 Anchor 在该池子里的涨幅、成交、换手、资金排名。 |
| `report_scope` | `enabled=true` 且 `include_in_report=true` 的成员。 | 展示在 `peer_matrix.csv` 和 `industry_report.md`。 |

这三个口径不能混用。

例如：

```text
theme_pool 可以参与 ranking 和 report
但默认不参与 benchmark
```

所以主题情绪池可以回答：

```text
主题热不热？
Anchor 有没有跟上主题？
```

但默认不能回答：

```text
核心同类基准涨跌是多少？
```

**特殊说明：非 benchmark 池子的状态计算**

对于 `can_be_benchmark=false` 的池子（如 theme_pool、trading_watchlist）：

```text
虽然不输出"基准"结论
但仍计算 median_return 用于组间轮动比较
计算口径使用 ranking_scope 成员
```

原因：第八层组间轮动需要比较所有池子的强弱，因此非 benchmark 池子也需要计算中位数涨跌幅。但这不代表它们可以作为"核心基准"使用。

### 6.2 有效样本口径

即使成员进入了 `benchmark_scope`，也不代表一定参与当天计算。还要看当天数据是否有效。

| 情况 | 是否进入当日 benchmark 计算 |
| --- | --- |
| 正常交易且有涨跌幅 | 是 |
| 停牌 | 否，进入数据质量说明 |
| 当日行情缺失 | 否，进入数据质量说明 |
| 资金字段缺失 | 价格类指标可算，资金类指标不算 |
| 估值字段缺失 | 价格类指标可算，估值分布不算 |

因此每个池子要区分：

```text
configured_count  配置成员数
enabled_count     启用成员数
benchmark_count   可参与 benchmark 的成员数
valid_count       当日数据有效成员数
```

如果 `valid_count < min_size`，这个池子状态必须标记为：

```text
insufficient_data
```

并且不能输出强结论。

### 6.3 每个池子怎么算

对每个池子单独计算：

| 指标 | 含义 |
| --- | --- |
| 平均涨跌幅 | 池子整体方向。 |
| 中位数涨跌幅 | 排除极端值后的真实状态。 |
| 上涨比例 | 行业广度。 |
| 成交额放大倍数 | 热度是否升温。 |
| 资金净流入为正比例 | 资金是否扩散。 |
| 强势股数量 | 前排数量。 |
| 弱势股数量 | 掉队数量。 |
| 估值分布 | 池子估值位置。 |

计算口径：

| 指标 | 计算口径 |
| --- | --- |
| 平均涨跌幅 | `benchmark_scope` 中当日有有效涨跌幅的成员。 |
| 中位数涨跌幅 | `benchmark_scope` 中当日有有效涨跌幅的成员。 |
| 上涨比例 | 有效上涨成员数 / 有效涨跌幅成员数。 |
| 成交额放大倍数 | 有成交额和历史均值的有效成员。 |
| 资金净流入为正比例 | 有资金字段的有效成员。 |
| 估值分布 | 有 PE/PB/PS 字段的有效成员。 |
| 强势股数量 | 有效涨跌幅成员中超过强势阈值的数量。 |
| 弱势股数量 | 有效涨跌幅成员中低于弱势阈值的数量。 |

### 6.4 池子状态的输出

每个池子都应该输出类似结论：

```text
direct_peers:
  configured_count：5
  benchmark_count：4
  valid_count：4
  核心同类池中位数涨幅：+0.8%
  上涨比例：60%
  成交额放大：1.2 倍
  资金正向比例：50%
  数据状态：ok
```

注意：这里还不判断 Anchor，只判断池子本身。

---

## 7. 第五层：锚定标的位置

Anchor Position 层负责把 Anchor 放回每个池子里比较。

### 7.1 相对强弱

最重要的判断是：

```text
Anchor 相对强弱 = Anchor 涨跌幅 - 池子中位数涨跌幅
```

例如：

```text
铂力特涨幅：+2.1%
核心同类池中位数：+0.8%

相对核心同类强弱 = +1.3%
```

这表示：

```text
铂力特跑赢核心同类。
```

### 7.2 排名

Anchor 不只看涨跌幅，还要看排名：

| 排名 | 说明 |
| --- | --- |
| 涨幅排名 | 今天是不是行业前排。 |
| 成交额排名 | 是否有资金关注。 |
| 换手率排名 | 交易是否活跃。 |
| 主力资金排名 | 是否有资金支持。 |
| 估值分位 | 相对核心同类贵还是便宜。 |

### 7.3 位置判断

Anchor Position 层最终回答：

```text
Anchor 是：
- 跑赢核心同类？
- 跑输核心同类？
- 处于行业前排？
- 处于行业后排？
- 行业弱但它强？
- 行业强但它弱？
```

---

## 8. 第六层：组间轮动

Group Rotation 层负责比较四类池子之间谁强谁弱。

### 8.1 为什么要看组间轮动

因为不同池子的强弱组合，代表不同市场含义。

| 组合 | 含义 |
| --- | --- |
| 核心同类强，主题池也强 | 行业和主题共振。 |
| 主题池强，核心同类弱 | 可能只是主题炒作，核心未确认。 |
| 产业链强，核心同类弱 | 可能是上下游先动，Anchor 还没跟。 |
| 交易观察池强，其他池弱 | 短期资金异动，不一定是行业趋势。 |

### 8.2 组间轮动输出

它输出：

```text
strongest_group = theme_pool
weakest_group = direct_peers
core_vs_theme_spread = -1.2%
```

解释为：

```text
主题情绪强于核心同类，需观察主题热度是否向核心业务传导。
```

---

## 9. 第七层：信号标签

Signals 层负责把指标翻译成结构化标签。

### 9.1 标签不是一句话评论

每个标签必须带证据。

错误方式：

```text
个股表现较强。
```

正确方式：

```json
{
  "label": "个股Alpha为正",
  "evidence": {
    "anchor_return": 2.1,
    "direct_peers_median": 0.8,
    "relative_strength": 1.3
  }
}
```

### 9.2 标签类型

| 类型 | 回答的问题 |
| --- | --- |
| 行业 Beta | 行业环境是正、负，还是分化？ |
| 个股 Alpha | Anchor 是否跑赢行业？ |
| 资金成交 | 量能和资金是否支持？ |
| 组间轮动 | 哪个池子最强，哪个最弱？ |
| 异常联动 | 是否出现行业强但个股弱等异常？ |

---

## 10. 第八层：输出

AnchorLink 最终输出三件套。

### 10.1 `industry_snapshot.json`

给 TradingTS 上层系统读。

它是最重要的输出。

必须包含：

```text
anchor
data_quality
industry_state
anchor_position
group_rotation
signals
conclusion
```

它回答：

```text
今天行业是什么状态？
Anchor 在行业中是什么位置？
有哪些有证据的标签？
上层系统应该如何理解这个行业模块结论？
```

### 10.2 `peer_matrix.csv`

给人检查。

它展示：

- 每只股票属于哪个池子。
- 在池子里是什么角色。
- 是否参与 benchmark。
- 是否参与 ranking。
- 当日涨跌、成交、资金、估值、排名。

关键点：

```text
CSV 的一行代表一次“股票在某个池子中的身份”
不是简单的一只股票一行
```

### 10.3 `industry_report.md`

给人阅读。

报告固定五章：

1. 行业状态概览。
2. 行业结构拆解。
3. 锚定标的相对位置。
4. 行业联动与异常信号。
5. 行业模块结论。

报告只解释结构化结果，不创造新结论。

---

## 11. 数据质量与降级

AnchorLink 不能在数据不足时强行输出强结论。

### 11.1 降级规则

| 情况 | 应该怎么处理 |
| --- | --- |
| Anchor 没有行情 | 本次分析失败。 |
| 某个池子样本不足 | 标记 `insufficient_data`，不输出强结论。 |
| 资金数据缺失 | 不输出资金类强标签。 |
| 估值数据缺失 | 不输出估值分位结论。 |
| 成员停牌 | 不参与当日均值，但进入数据质量说明。 |
| 主题池强但核心池样本不足 | 只能说主题热，不能说已经传导。 |

### 11.2 数据质量贯穿全链路

```text
数据缺失
  -> 池子状态降级
  -> 信号标签抑制
  -> JSON 标记 data_quality
  -> 报告解释限制
```

---

## 12. 模块边界

### 12.1 每层负责什么

| 层 | 负责 | 不负责 |
| --- | --- | --- |
| Anchor | 定义分析中心。 | 不参与自身 benchmark。 |
| Pools | 定义比较口径。 | 不抓市场数据。 |
| Market | 提供事实数据。 | 不判断强弱。 |
| Pool State | 判断每个池子强弱。 | 不判断最终交易。 |
| Anchor Position | 判断 Anchor 相对位置。 | 不写报告文案。 |
| Group Rotation | 判断池子间强弱切换。 | 不预测未来行情。 |
| Signals | 生成有证据标签。 | 不调用 LLM 编故事。 |
| Output | 输出 JSON/CSV/MD。 | 不新增业务判断。 |

### 12.2 主链路不包含什么

MVP 主链路不包含：

- 新闻抓取。
- 公告解析。
- LLM 生成观点。
- UI。
- 数据库。
- 自动推荐同类公司。
- 买卖建议。

---

## 13. 用一句例子串起来

以铂力特为例：

```text
1. Anchor = 铂力特

2. 系统读取四类池子：
   - 核心同类池：增材制造/业务可比公司
   - 产业链池：上下游和需求传导公司
   - 主题情绪池：商业航天、军工、3D 打印主题标的
   - 交易观察池：短期资金关注的相关标的

3. 系统分别计算：
   - 核心同类今天强不强
   - 产业链有没有传导
   - 主题是不是更热
   - 交易观察池有没有异动

4. 系统再看铂力特：
   - 是否跑赢核心同类
   - 是否处于行业前排
   - 成交和资金是否支持

5. 系统输出：
   - 行业 Beta
   - 个股 Alpha
   - 主题扩散
   - 组间轮动
   - 异常联动
```

---

## 14. 架构验收标准

这份架构成立的标准不是“模块很多”，而是能不能稳定避免混乱。

必须满足：

- 所有结论都能追溯到具体股票池。
- 核心同类、产业链、主题情绪、交易观察不会混算。
- Anchor 不进入自身 benchmark。
- 每个标签都有 evidence。
- 数据不足时会降级，而不是硬给结论。
- JSON 是上层系统主协议。
- Markdown 只是解释层。
- 系统不输出最终买卖建议。

---

## 15. 最终定义

AnchorLink 的架构可以压缩为：

```text
一个 Anchor
四类股票池
分别计算池子状态
再判断 Anchor 相对位置
最后输出有证据的行业结论
```

这就是 AnchorLink。不是新闻系统，不是研报系统，也不是交易系统。它是 TradingTS 的行业锚定分析模块。
