# AnchorLink 股票池核心逻辑与计算口径设计

> 文档类型：核心设计说明
> 适用范围：Universe / 股票池资产层 / 池状态计算 / 组间轮动 / 输出口径
> 当前结论：`Universe` 是 AnchorLink 的核心资产；`Benchmark` 只是其中一种计算口径，不能等同于股票池状态。

---

## 0. 一句话结论

AnchorLink 的核心不是“维护几组股票列表”，而是维护一套围绕锚定标的的行业关系资产：

```text
Anchor
  -> 四类 Universe
  -> 每只股票在每个 Universe 里的 Membership 身份
  -> 不同分析任务使用不同 Scope
  -> 输出行业状态、锚定位置、组间轮动和结构化结论
```

最关键的规则是：

```text
不参与 Benchmark，不等于不计算状态。
```

`theme_pool` 和 `trading_watchlist` 不能作为行业基准，但它们必须有自己的状态，否则系统就无法回答“主题热不热”“交易观察池有没有升温”。

---

## 1. AnchorLink 要回答什么问题

每天只围绕一个锚定标的，例如：

```text
Anchor = 688333.SH 铂力特
```

系统要回答四个问题：

| 问题 | 需要的数据 |
| --- | --- |
| 铂力特今天强还是弱？ | Anchor 自身涨跌、成交、资金、排名 |
| 它是跟随行业，还是独立走强/走弱？ | Anchor vs 核心同类、产业链、主题池、交易观察池 |
| 今天强的是业务同类、产业链，还是主题情绪？ | 四类 Universe 的自身状态和组间比较 |
| 上层系统应该如何使用这个结论？ | 稳定的 `industry_snapshot.json`、`peer_matrix.csv`、`industry_report.md` |

因此，股票池不是附属配置，而是所有判断的底座。

---

## 2. 六个核心概念

### 2.1 Anchor

锚定标的，本次分析的中心股票。

规则：

- Anchor 是被分析对象。
- Anchor 默认不进入自身 Benchmark。
- Anchor 可以进入 Ranking，用来判断它在各个池子中的位置。
- MVP 只支持单 Anchor。

### 2.2 Instrument

证券主数据，一只股票只维护一份事实信息。

示例字段：

```yaml
symbol: 688433.SH
name: 华曙高科
market: A-share
exchange: SH
fact_tags: [增材制造, 3D打印设备, 工业级打印]
```

Instrument 不表达“为什么要比较”，只表达“这只股票是什么”。

### 2.3 Universe

Universe 是分析视角，也就是产品意义上的股票池。

AnchorLink MVP 有四类 Universe：

| Universe | 中文名 | 它回答的问题 |
| --- | --- | --- |
| `direct_peers` | 核心同类池 | 真正业务可比公司今天强不强？ |
| `industry_chain` | 产业链池 | 上下游和需求端有没有传导？ |
| `theme_pool` | 主题情绪池 | 市场是不是在炒主题？ |
| `trading_watchlist` | 交易观察池 | 短期资金有没有切换或异动？ |

Universe 不是互斥分类。一只股票可以出现在多个 Universe，因为它在不同问题中扮演不同角色。

### 2.4 Membership

Membership 是“某只股票进入某个 Universe 的理由和身份”。

例如华曙高科可以同时出现两次：

| Symbol | Universe | Role | 含义 |
| --- | --- | --- | --- |
| `688433.SH` | `direct_peers` | `direct_comparable` | 作为核心同类参与业务可比 |
| `688433.SH` | `theme_pool` | `theme_heat_proxy` | 作为 3D 打印主题热度代理 |

这不是重复数据，而是同一只股票的两种分析身份。

### 2.5 Scope

Scope 是某次计算到底取哪些 membership。

这是最容易混乱的地方。AnchorLink 至少需要五种 Scope：

| Scope | 用途 | 是否应该覆盖四类 Universe |
| --- | --- | --- |
| `state_scope` | 计算每个池子的自身状态 | 是 |
| `benchmark_scope` | 计算可作为行业基准的池子 | 只限可做基准的池子 |
| `ranking_scope` | 计算 Anchor 在池子里的排名 | 是 |
| `report_scope` | 输出到 CSV/Markdown | 是 |
| `rotation_scope` | 比较组间强弱 | 是，但可配置排除 |

核心区分：

```text
Universe = 资产和视角
Scope = 这次计算用哪些成员
```

### 2.6 Output

输出不是自然语言报告的副产品，而是固定协议。

| 输出 | 用途 |
| --- | --- |
| `industry_snapshot.json` | 给上层系统读取 |
| `peer_matrix.csv` | 给人检查每个 membership 的数据和口径 |
| `industry_report.md` | 给人阅读每日结论 |

---

## 3. 四类 Universe 的产品语义

### 3.1 direct_peers

核心业务可比池。

它回答：

```text
真正和 Anchor 业务可比的公司今天强不强？
Anchor 是跑赢核心同类，还是跑输核心同类？
```

规则：

- 可以参与 Benchmark。
- 必须计算自身状态。
- 必须参与 Ranking。
- 宁少勿滥，样本少也可以，但报告必须标记样本数量。

### 3.2 industry_chain

产业链池。

它回答：

```text
上下游、需求端、供应链有没有同向变化？
产业链强弱是否支持 Anchor 的走势？
```

规则：

- 可以参与 Benchmark。
- 必须计算自身状态。
- 必须参与 Ranking。
- 个别成员可以只观察，不参与 Benchmark，但仍可参与 State/Ranking/Report。

### 3.3 theme_pool

主题情绪池。

它回答：

```text
市场是否在炒商业航天、3D 打印、军工等主题？
主题热度有没有传导到核心同类？
```

规则：

- 默认不参与 Benchmark。
- 必须计算自身状态。
- 必须参与 Ranking。
- 必须参与组间轮动，否则无法识别“主题强于核心同类”。

### 3.4 trading_watchlist

交易观察池。

它回答：

```text
短期资金是否在相关军工、材料、元器件方向切换？
Anchor 是不是落后于交易资金热区？
```

规则：

- 不参与 Benchmark。
- 必须计算自身状态。
- 必须参与 Ranking。
- 可以参与组间轮动，但结论应表述为“交易热度”，不能表述为“行业基本面确认”。

---

## 4. 五种 Scope 的标准定义

### 4.1 State Scope

State Scope 用于计算一个 Universe 自己今天强不强。

目标配置字段：

```yaml
include_in_state: true
```

目标接口：

```python
registry.get_state_scope(universe_id) -> list[Membership]
```

过滤规则：

```text
enabled == true
and include_in_state == true
```

计算指标：

- 平均涨跌幅
- 中位数涨跌幅
- 上涨比例
- 下跌比例
- 成交额放大倍数
- 资金净流入为正比例
- 强势股数量
- 弱势股数量
- 缺失数据成员
- 数据质量状态

关键规则：

```text
四类 Universe 都必须有 State。
```

### 4.2 Benchmark Scope

Benchmark Scope 用于计算“可以当行业基准”的成员。

目标接口：

```python
registry.get_benchmark_scope(universe_id) -> list[Membership]
```

过滤规则：

```text
enabled == true
and include_in_benchmark == true
```

适用：

| Universe | 是否可作为 Benchmark |
| --- | --- |
| `direct_peers` | 是 |
| `industry_chain` | 是 |
| `theme_pool` | 否 |
| `trading_watchlist` | 否 |

关键规则：

```text
Benchmark 是 State 的子集或独立口径，不是 State 本身。
```

### 4.3 Ranking Scope

Ranking Scope 用于判断 Anchor 在某个 Universe 中的位置。

目标接口：

```python
registry.get_ranking_scope(universe_id, include_anchor=True) -> list[str]
```

过滤规则：

```text
membership.enabled == true
and membership.include_in_ranking == true
plus anchor when include_anchor == true
```

计算指标：

- 涨幅排名
- 成交额排名
- 换手率排名
- 资金净流入排名
- 估值分位，仅 `direct_peers` 有意义

关键规则：

```text
Anchor 不需要是 Membership，但 Ranking 里必须显式加入 Anchor。
```

### 4.4 Report Scope

Report Scope 用于控制哪些 membership 出现在输出文件里。

目标接口：

```python
registry.get_report_scope(universe_id) -> list[Membership]
```

过滤规则：

```text
enabled == true
and include_in_report == true
```

输出位置：

- `peer_matrix.csv`
- `industry_report.md`
- 前端股票池展示

关键规则：

```text
Report 不是计算口径，只是展示口径。
```

### 4.5 Rotation Scope

Rotation Scope 用于比较组间强弱。

目标配置字段：

```yaml
include_in_rotation: true
```

MVP 可先默认：

```text
所有有有效 State 的 Universe 都参与 rotation
```

比较项：

- `direct_peers` vs `industry_chain`
- `direct_peers` vs `theme_pool`
- `direct_peers` vs `trading_watchlist`
- `industry_chain` vs `theme_pool`
- `industry_chain` vs `trading_watchlist`

关键规则：

```text
Rotation 比的是各池子的状态，不是 Benchmark 资格。
```

---

## 5. 目标配置结构

当前 `config/pools.yaml` 已经有大部分字段，但建议补齐两个字段：

```yaml
memberships:
  - universe_id: theme_pool
    symbol: 601698.SH
    role: theme_heat_proxy
    relevance: 0.60
    weight: 0.5
    enabled: true

    include_in_state: true
    include_in_benchmark: false
    include_in_ranking: true
    include_in_report: true
    include_in_rotation: true

    reason: "卫星通信运营商，商业航天主线标的..."
    added_at: "2026-03-17"
    reviewed_at: "2026-05-02"
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| `include_in_state` | 这只股票是否参与该池自身状态计算 |
| `include_in_benchmark` | 这只股票是否参与行业基准计算 |
| `include_in_ranking` | 这只股票是否参与 Anchor 排名比较 |
| `include_in_report` | 这只股票是否出现在输出文件 |
| `include_in_rotation` | 这个 membership 是否用于组间轮动 |

兼容规则：

```text
如果历史配置没有 include_in_state，则默认等于 enabled。
如果历史配置没有 include_in_rotation，则默认等于 include_in_state。
```

这样不会破坏旧配置。

---

## 6. 每日分析主流程

目标流程：

```text
1. 加载 PoolRegistry
2. 校验 Anchor / Instrument / Universe / Membership
3. 获取所有需要的行情数据
4. 对每个 Universe 计算 PoolState，使用 state_scope
5. 对每个 Universe 计算 AnchorPosition，使用 ranking_scope + pool_state
6. 计算 BenchmarkSummary，使用 benchmark_scope
7. 计算 GroupRotation，使用 rotation_scope + pool_state
8. 生成 Signals，每个标签必须带 evidence
9. 构建 IndustrySnapshot
10. 输出 JSON / CSV / Markdown
```

数据流：

```text
config/pools.yaml
  -> PoolRegistry
  -> state_scope / benchmark_scope / ranking_scope / report_scope / rotation_scope
  -> PoolState / AnchorPosition / GroupRotation / Signals
  -> industry_snapshot.json / peer_matrix.csv / industry_report.md
```

---

## 7. 指标应该怎么解释

### 7.1 PoolState

PoolState 是“某个池子今天怎么样”。

四类 Universe 都应该有 PoolState。

示例：

```json
{
  "universe_id": "theme_pool",
  "median_return": 3.71,
  "mean_return": 5.03,
  "up_ratio": 1.0,
  "valid_count": 5,
  "data_status": "partial"
}
```

### 7.2 BenchmarkSummary

BenchmarkSummary 是“能不能作为行业基准”。

只有 `direct_peers` 和 `industry_chain` 默认有 BenchmarkSummary。

示例：

```json
{
  "direct_peers_benchmark_median": 1.29,
  "industry_chain_benchmark_median": 3.90
}
```

### 7.3 AnchorPosition

AnchorPosition 是“Anchor 相对某个池子的位置”。

四类 Universe 都应该有 AnchorPosition。

示例：

```json
{
  "universe_id": "theme_pool",
  "anchor_return": 4.67,
  "pool_median": 3.71,
  "relative_strength": 0.96,
  "return_rank": 2,
  "total_count": 6
}
```

### 7.4 GroupRotation

GroupRotation 是“四类池子之间谁强谁弱”。

示例：

```json
{
  "strongest_group": "trading_watchlist",
  "weakest_group": "direct_peers",
  "core_vs_theme_spread": -2.42,
  "core_vs_trading_spread": -1.80
}
```

### 7.5 Signals

Signals 是带证据的标签。

每个标签必须能追溯到数据：

```json
{
  "label": "主题扩散强于核心同类",
  "category": "rotation",
  "confidence": "medium",
  "evidence": {
    "source_pool": "theme_pool",
    "source_field": "median_return",
    "value": 3.71,
    "secondary_value": 1.29,
    "threshold": 1.0
  }
}
```

---

## 8. 与当前代码的差异

当前代码已经完成了资产模型，但计算口径还需要调整。

### 8.1 已经对齐的部分

| 目标 | 当前代码状态 |
| --- | --- |
| `Instrument` | 已在 `src/config/loader.py` 实现 |
| `Universe` | 已在 `src/config/loader.py` 实现 |
| `Membership` | 已在 `src/config/loader.py` 实现 |
| `get_benchmark_scope` | 已实现 |
| `get_ranking_scope` | 已实现 |
| `get_report_scope` | 已实现 |
| 四类 Universe 配置 | 已在 `config/pools.yaml` 实现 |

### 8.2 当前不对齐的部分

| 问题 | 当前表现 | 应调整为 |
| --- | --- | --- |
| PoolState 使用 `benchmark_scope` | `theme_pool`、`trading_watchlist` 状态为空 | PoolState 使用 `state_scope` |
| GroupRotation 过滤 `can_be_benchmark=false` | 组间轮动只比较 direct/chain | Rotation 基于有效 PoolState |
| JSON 状态缺少完整四池状态 | `theme_pool_return_median` 可能为 `null`，无 trading median | 输出四类池状态 |
| CSV 排名只套 Anchor 排名 | 非 Anchor 行显示同一排名 | 每个 membership 都应有自身排名或留空 |
| DataQuality 只看 signal_result | 可能显示 `ok` 但 pool_result 是 `partial` | 汇总 pool / position / rotation / signal 状态 |

### 8.3 当前最核心的修正

第一优先级：

```text
新增 state_scope，并让 PoolStateCalculator 使用 state_scope。
```

这一步修完，`theme_pool` 和 `trading_watchlist` 才会真正成为可分析的池子。

第二优先级：

```text
让 GroupRotation 比较四类 Universe 的 PoolState。
```

这一步修完，系统才能输出“主题强于核心同类”“交易观察池升温”等结论。

第三优先级：

```text
修正输出协议，把四类池状态和数据质量完整写入 JSON。
```

这一步修完，上层系统才能稳定读取。

---

## 9. 目标代码接口

### 9.1 PoolRegistry

建议最终接口：

```python
class PoolRegistry:
    def get_members(self, universe_id: str, enabled_only: bool = True) -> list[Membership]:
        ...

    def get_state_scope(self, universe_id: str) -> list[Membership]:
        ...

    def get_benchmark_scope(self, universe_id: str) -> list[Membership]:
        ...

    def get_ranking_scope(self, universe_id: str, include_anchor: bool = True) -> list[str]:
        ...

    def get_report_scope(self, universe_id: str) -> list[Membership]:
        ...

    def get_rotation_scope(self, universe_id: str) -> list[Membership]:
        ...
```

### 9.2 PoolStateCalculator

目标规则：

```python
members = registry.get_state_scope(universe_id)
```

不能再用：

```python
members = registry.get_benchmark_scope(universe_id)
```

除非明确是在计算 BenchmarkSummary。

### 9.3 GroupRotation

目标规则：

```text
输入：所有 data_status != insufficient_data 的 PoolState
输出：四类 Universe 的 group_ranking / spreads
```

不能再用：

```text
can_be_benchmark == true
```

来决定是否参与组间轮动。

### 9.4 Output

目标 JSON 应至少包含：

```json
{
  "pool_states": {
    "direct_peers": {},
    "industry_chain": {},
    "theme_pool": {},
    "trading_watchlist": {}
  },
  "benchmark_summary": {
    "direct_peers": {},
    "industry_chain": {}
  },
  "anchor_positions": {
    "direct_peers": {},
    "industry_chain": {},
    "theme_pool": {},
    "trading_watchlist": {}
  },
  "group_rotation": {},
  "signals": [],
  "conclusion": {}
}
```

---

## 10. 验收标准

### 10.1 配置验收

- `config/pools.yaml` 中所有 enabled membership 必须有 `reason`、`role`、`relevance`、`added_at`、`reviewed_at`。
- 每个 Universe 至少有一个 state member。
- `direct_peers` 和 `industry_chain` 的 benchmark 成员数必须满足 `min_size`。
- `theme_pool` 和 `trading_watchlist` 可以没有 benchmark 成员，但不能没有 state member。

### 10.2 计算验收

每日输出中必须满足：

- `direct_peers` 有 PoolState。
- `industry_chain` 有 PoolState。
- `theme_pool` 有 PoolState。
- `trading_watchlist` 有 PoolState。
- Anchor 对四类 Universe 都有相对位置。
- GroupRotation 至少能比较三个以上有效 Universe。
- `data_quality.status` 能反映 partial / insufficient_data。

### 10.3 输出验收

`industry_snapshot.json` 必须能回答：

- 今天核心同类池强不强？
- 今天产业链强不强？
- 今天主题池热不热？
- 今天交易观察池有没有升温？
- Anchor 相对四类池分别是强还是弱？
- 最强池和最弱池是谁？
- 结论对应哪些 evidence？

`peer_matrix.csv` 必须能检查：

- 每个 membership 属于哪个 Universe。
- 每个 membership 的 role / relevance / reason。
- 每个 membership 是否参与 state / benchmark / ranking / report / rotation。
- 每个 membership 当日行情数据是否缺失。

`industry_report.md` 必须能读出：

- 四类池子状态，而不是只有 direct/chain。
- 主题和交易池不作为基本面确认，但作为热度和资金观察。
- 数据不足时不输出强结论。

---

## 11. 推荐实施顺序

### Phase 1：修正口径

目标：让概念先正确。

任务：

- `Membership` 增加 `include_in_state`、`include_in_rotation`。
- `PoolRegistry` 增加 `get_state_scope()`、`get_rotation_scope()`。
- `PoolStateCalculator` 改用 `state_scope`。
- 保持 `benchmark_scope` 只用于基准计算。

### Phase 2：修正组间轮动

目标：让四类池子真正参与强弱比较。

任务：

- `GroupRotation` 使用有效 PoolState。
- 不再用 `can_be_benchmark` 排除 theme/trading。
- 输出 `core_vs_theme_spread`、`core_vs_trading_spread`。

### Phase 3：修正输出协议

目标：让上层系统稳定读取。

任务：

- JSON 增加完整 `pool_states`。
- JSON 增加 `benchmark_summary`。
- JSON 增加四类 `anchor_positions`。
- DataQuality 汇总 pool / position / rotation / signal。

### Phase 4：修正 CSV 与报告

目标：让人能检查每个 membership。

任务：

- `peer_matrix.csv` 增加 `include_in_state`、`include_in_rotation`。
- 修正每行排名，不能把 Anchor 排名套给所有股票。
- 报告展示四类池子的状态。

---

## 12. 最终心智模型

读 AnchorLink 股票池时，只记住这张图：

```text
一只股票是什么？
  -> Instrument

它为什么进入这个分析体系？
  -> Membership.reason

它在哪个问题里被观察？
  -> Universe

这次计算要不要用它？
  -> Scope

它贡献了什么证据？
  -> PoolState / AnchorPosition / Signal Evidence
```

Universe 是资产，Scope 是口径，Output 是协议。

只要这三者分清，整个 AnchorLink 就不会乱。
