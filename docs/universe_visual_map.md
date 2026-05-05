# AnchorLink Universe 可视化理解图

> 用途：用图理解股票池配置、计算口径、当前实现状态和目标方案。
> 配套阅读：[universe_core_logic.md](universe_core_logic.md)

---

## 1. 一张图看懂 AnchorLink 在做什么

```mermaid
flowchart TD
    A["Anchor<br/>688333.SH 铂力特"] --> U["四类 Universe<br/>四个观察视角"]

    U --> D["direct_peers<br/>核心同类池<br/>业务可比"]
    U --> C["industry_chain<br/>产业链池<br/>上下游/需求传导"]
    U --> T["theme_pool<br/>主题情绪池<br/>主题热度/扩散"]
    U --> W["trading_watchlist<br/>交易观察池<br/>短期资金切换"]

    D --> S["PoolState<br/>这个池子今天强不强"]
    C --> S
    T --> S
    W --> S

    S --> P["AnchorPosition<br/>铂力特相对每个池子强不强"]
    S --> R["GroupRotation<br/>四类池子谁最强谁最弱"]
    P --> G["Signals<br/>带证据的标签"]
    R --> G
    G --> O["Outputs<br/>JSON / CSV / Markdown / Web"]
```

这张图的核心意思：

```text
四类池子都要先有自己的状态，后面才谈得上相对位置和组间轮动。
```

---

## 2. 配置到底在哪里

配置文件只有一个主入口：

```text
config/pools.yaml
```

它分四层：

```mermaid
flowchart TB
    F["config/pools.yaml"] --> A["anchor<br/>当前锚定标的"]
    F --> I["instruments<br/>证券主数据"]
    F --> U["universes<br/>四类股票池定义"]
    F --> M["memberships<br/>股票进入池子的身份和口径"]

    I --> I1["一只股票是什么<br/>代码/名称/标签"]
    U --> U1["这个池子解决什么问题<br/>direct / chain / theme / trading"]
    M --> M1["这只股票为什么进这个池<br/>role / relevance / reason / scope flags"]
```

具体例子：

```yaml
anchor:
  symbol: 688333.SH
  name: 铂力特

universes:
  - universe_id: direct_peers
    display_name: 核心同类池

memberships:
  - universe_id: direct_peers
    symbol: 688433.SH
    role: direct_comparable
    include_in_benchmark: true
    include_in_ranking: true
    include_in_report: true
```

---

## 3. Universe 和 Scope 的区别

`Universe` 是股票池资产，`Scope` 是某次计算取哪些成员。

```mermaid
flowchart LR
    U["Universe<br/>分析视角/股票池"] --> M["Memberships<br/>池子里的成员身份"]
    M --> SS["state_scope<br/>算池子自身状态"]
    M --> BS["benchmark_scope<br/>算行业基准"]
    M --> RS["ranking_scope<br/>算 Anchor 排名"]
    M --> PS["report_scope<br/>输出展示"]
    M --> GS["rotation_scope<br/>组间轮动"]
```

最重要的区别：

| 概念 | 意思 | 例子 |
| --- | --- | --- |
| Universe | 这是哪个股票池 | `theme_pool` |
| Membership | 哪只股票以什么身份进入池子 | `中国卫通` 作为 `theme_heat_proxy` |
| Scope | 这次计算要不要用它 | 参与 ranking，不参与 benchmark |

---

## 4. Benchmark 到底是什么

Benchmark 是“基准 / 对照组”。

```mermaid
flowchart LR
    A["Anchor<br/>铂力特涨跌幅"] --> Compare["相对强弱<br/>Anchor - Benchmark"]
    B["Benchmark<br/>公平对照组中位数"] --> Compare
    Compare --> Result["跑赢 / 跑输 / 中性"]
```

不是所有池子都适合当 Benchmark：

| 池子 | 是否适合当 Benchmark | 但是否要计算自身状态 |
| --- | --- | --- |
| `direct_peers` | 是 | 是 |
| `industry_chain` | 是 | 是 |
| `theme_pool` | 否 | 是 |
| `trading_watchlist` | 否 | 是 |

核心规则：

```text
不当 Benchmark，不等于不重要。
不参与 Benchmark，不等于不计算状态。
```

---

## 5. 当前实现和目标实现的差异

### 当前实现

```mermaid
flowchart TD
    M["Memberships"] --> B["benchmark_scope"]
    B --> S["PoolState"]
    S --> R["GroupRotation"]

    T["theme_pool<br/>include_in_benchmark=false"] -.-> X["PoolState 为空"]
    W["trading_watchlist<br/>include_in_benchmark=false"] -.-> Y["PoolState 为空"]

    classDef problem fill:#3b1515,stroke:#ef4444,color:#f5f5f5
    class X,Y problem
```

当前结果：

```text
direct_peers 有状态
industry_chain 有状态
theme_pool 显示为空
trading_watchlist 显示为空
```

这就是为什么现在报告里会出现：

```text
主题扩散 | - | - | - | 0/5
交易观察 | - | - | - | 0/6
```

### 目标实现

```mermaid
flowchart TD
    M["Memberships"] --> SCOPE1["state_scope"]
    M --> SCOPE2["benchmark_scope"]
    M --> SCOPE3["ranking_scope"]
    M --> SCOPE4["report_scope"]
    M --> SCOPE5["rotation_scope"]

    SCOPE1 --> PS["PoolState<br/>四类池子都有状态"]
    SCOPE2 --> BM["BenchmarkSummary<br/>只用于公平对照"]
    SCOPE3 --> AP["AnchorPosition<br/>Anchor 在四类池子中的位置"]
    SCOPE5 --> GR["GroupRotation<br/>四类池子强弱比较"]

    PS --> OUT["industry_snapshot.json"]
    BM --> OUT
    AP --> OUT
    GR --> OUT
```

目标结果：

```text
direct_peers 有状态，也可做 Benchmark
industry_chain 有状态，也可做 Benchmark
theme_pool 有状态，但不做 Benchmark
trading_watchlist 有状态，但不做 Benchmark
```

---

## 6. 每日分析从配置到输出

```mermaid
sequenceDiagram
    participant YAML as config/pools.yaml
    participant Registry as PoolRegistry
    participant Price as Market Data
    participant State as PoolStateCalculator
    participant Rank as RankingCalculator
    participant Rotation as GroupRotation
    participant Signal as SignalGenerator
    participant Output as Output Writers

    YAML->>Registry: 读取 anchor / instruments / universes / memberships
    Registry->>Price: 提供所有需要获取行情的 symbols
    Price->>State: 提供当日行情/换手率/资金
    Registry->>State: 提供 state_scope
    State->>Rank: 提供每个池子的状态
    Registry->>Rank: 提供 ranking_scope + Anchor
    State->>Rotation: 提供四类 PoolState
    Rank->>Signal: 提供 AnchorPosition
    Rotation->>Signal: 提供组间强弱
    Signal->>Output: 提供带 evidence 的标签
    Output->>Output: 写 JSON / CSV / Markdown
```

---

## 7. 现在可以看的可视化页面

前端目录：

```text
web/
```

本地启动：

```bash
cd web
npm run dev
```

主要页面：

| 页面 | 看什么 |
| --- | --- |
| `/` | 仪表盘：池子强弱图、组间轮动图、信号、结论、矩阵 |
| `/pools` | 股票池配置：四类 Universe、membership、benchmark/ranking/report |
| `/layers` | 分层视图入口 |
| `/layers/pool-state` | 池状态层 |
| `/layers/group-rotation` | 组间轮动层 |
| `/reports` | 报告列表 |

注意：

```text
这些页面展示的是当前实现状态。
因此 theme_pool / trading_watchlist 现在会显示成缺状态。
这是代码口径问题，不是配置没有这两个池子。
```

---

## 8. 看代码时按这个顺序

```mermaid
flowchart TD
    C["config/pools.yaml<br/>先看配置"] --> L["src/config/loader.py<br/>看 PoolRegistry 如何解析"]
    L --> P["src/pool_state/calculator.py<br/>看 PoolState 当前怎么取成员"]
    P --> A["src/anchor_position/relative_strength.py<br/>看 Anchor 相对位置"]
    A --> G["src/group_rotation/rotation_analyzer.py<br/>看组间轮动"]
    G --> S["src/signal/label_generator.py<br/>看标签如何生成"]
    S --> O["src/output/*<br/>看 JSON/CSV/Markdown 输出"]
```

最关键的三个文件：

| 文件 | 你看它是为了理解什么 |
| --- | --- |
| `config/pools.yaml` | 股票池到底怎么配 |
| `src/config/loader.py` | 配置如何变成代码对象 |
| `src/pool_state/calculator.py` | 当前为什么 theme/trading 没有状态 |

---

## 9. 最短理解路径

如果只想先理解，不想钻代码，就按这个顺序看：

```text
1. docs/universe_visual_map.md
2. docs/universe_core_logic.md
3. config/pools.yaml
4. http://localhost:3000/pools
5. http://localhost:3000/
```

你只要抓住一句话：

```text
Universe 是问题视角，Scope 是计算口径，Benchmark 只是公平对照组。
```

