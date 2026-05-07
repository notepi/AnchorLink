# AnchorLink Universe（股票池资产层）设计文档

> 版本：v1.0
> 日期：2026-05-05
> 状态：正式版
> 关联 PRD：docs/prd.md 第 8 节

> 阅读顺序建议：如果要理解“为什么这么分池、各类口径到底怎么计算”，先读
> [universe_core_logic.md](universe_core_logic.md)。本文更偏向 Universe 资产层明细和当前配置说明。

---

## 1. 设计背景与问题

### 1.1 核心问题

不同类型的股票池混在一起计算会导致误判：

| 问题 | 说明 |
|------|------|
| 主题股当核心用 | 把炒作主题的股票纳入核心同类池，拉低/抬高板块均值 |
| 产业链混入情绪 | 把业务关联弱的股票算入产业链均值 |
| 交易观察池参与基准 | 短期资金异动的股票不应参与行业基准计算 |

### 1.2 设计目标

- **可区分**：核心业务可比 vs 产业链联动 vs 主题炒作 vs 交易观察
- **可解释**：每只股票进入池子必须有 reason、relevance、role
- **可配置**：是否参与 benchmark/ranking/report 显式开关
- **可追溯**：added_at、reviewed_at、changelog 全量记录

---

## 2. 三层架构

```
┌─────────────────────────────────────────────────────────┐
│                    Anchor（锚定标的）                    │
│                    688333.SH 铂力特                      │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│              Instruments（证券主数据层）                  │
│  16 只股票全局唯一下，定义事实信息（代码、名称、标签）      │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│              Universes（股票池定义层）                    │
│  4 类池子：direct_peers / industry_chain /              │
│            theme_pool / trading_watchlist               │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│              Memberships（成员关系层）                    │
│  多对多关系，一只股票可进入多个池子                        │
│  每个关系独立：role、relevance、reason、weight           │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 四类 Universe

| Universe ID | 中文名 | 用途 | 参与 Benchmark | 参与 Ranking | 参与 Report |
|------------|--------|------|---------------|-------------|------------|
| `direct_peers` | 核心业务可比池 | 真正同类公司比较 | ✅ | ✅ | ✅ |
| `industry_chain` | 产业链池 | 上下游联动传导 | ✅ | ✅ | ✅ |
| `theme_pool` | 主题情绪池 | 主题炒作热度 | ❌ | ✅ | ✅ |
| `trading_watchlist` | 交易观察池 | 短期资金异动 | ❌ | ✅ | ✅ |

### 3.1 设计说明

**direct_peers（核心同类池）**
- 业务直接可比公司
- 用途：判断 Anchor 相对核心业务的强弱
- 要求：min_size=1，宁少勿滥
- relevance 参考值：0.8~1.0

**industry_chain（产业链池）**
- 上下游和需求传导
- 用途：判断产业链联动和主题传导
- 要求：min_size=3
- relevance 参考值：0.7~0.9

**theme_pool（主题情绪池）**
- 主题热度和扩散
- 用途：观察市场主题热度
- 不参与 benchmark：主题炒作不代表业务确认
- relevance 参考值：0.4~0.7

**trading_watchlist（交易观察池）**
- 短期资金切换和异动
- 用途：捕捉交易机会
- 不参与 benchmark：资金异动不代表基本面
- relevance 参考值：0.5~0.9

---

## 4. 数据模型

### 4.1 Instrument（证券主数据）

```python
@dataclass(frozen=True)
class Instrument:
    symbol: str           # 股票代码，全局唯一
    name: str             # 股票名称
    market: str           # 市场：A-share
    exchange: str         # 交易所：SH / SZ
    fact_tags: list[str]  # 事实标签：增材制造、商业航天 等
```

**当前数据（16 只）**：

| Symbol | Name | Exchange | Fact Tags |
|--------|------|----------|-----------|
| 688333.SH | 铂力特 | SH | 金属3D打印, 增材制造, 商业航天制造链 |
| 688433.SH | 华曙高科 | SH | 增材制造, 3D打印设备, 工业级打印 |
| 600343.SH | 航天动力 | SH | 航天发动机, 推进系统, 商业航天, 国企 |
| 600879.SH | 航天电子 | SH | 航天电子, 航天供应链, 国企 |
| 600118.SH | 中国卫星 | SH | 卫星制造, 商业航天, 国企 |
| 003009.SZ | 中天火箭 | SZ | 固体火箭, 商业航天, 火箭发动机 |
| 688102.SH | 斯瑞新材 | SH | 高性能铜合金, 难熔金属, 航空航天材料 |
| 601698.SH | 中国卫通 | SH | 卫星通信, 卫星互联网, 商业航天, 国企 |
| 300762.SZ | 上海瀚讯 | SZ | 卫星通信终端, 宽带卫星通信, 商业航天 |
| 688062.SH | 航天宏图 | SH | 遥感卫星, 商业航天, 数据服务 |
| 688568.SH | 中科星图 | SH | GIS应用, 卫星数据, 商业航天 |
| 002179.SZ | 中航光电 | SZ | 连接器, 军工, 航空航天 |
| 603678.SH | 火炬电子 | SH | 军工电子, MLCC, 被动元器件 |
| 000733.SZ | 振华科技 | SZ | 军工电子, MLCC, 钽电容 |
| 603267.SH | 鸿远电子 | SH | MLCC, 被动元器件, 军工 |
| 600151.SH | 航天工程 | SH | 煤化工工程, 国企 |

### 4.2 Universe（股票池定义）

```python
@dataclass(frozen=True)
class Universe:
    universe_id: str           # 池子ID：direct_peers / industry_chain 等
    display_name: str         # 显示名称
    purpose: str              # 用途说明
    can_be_benchmark: bool    # 能否作为基准
    min_size: int             # 最小成员数
    description: Optional[str] # 详细描述
```

**池子定义**：

| Universe ID | Display Name | Can Be Benchmark | Min Size |
|------------|--------------|------------------|----------|
| direct_peers | 核心同类池 | ✅ | 1 |
| industry_chain | 产业链池 | ✅ | 3 |
| theme_pool | 主题情绪池 | ❌ | 3 |
| trading_watchlist | 交易观察池 | ❌ | 1 |

### 4.3 Membership（成员关系）

```python
@dataclass(frozen=True)
class Membership:
    universe_id: str          # 池子ID
    symbol: str               # 股票代码
    role: str                 # 角色：direct_comparable / downstream_demand 等
    relevance: float          # 相关性 0~1
    weight: float             # 权重
    enabled: bool             # 是否启用
    include_in_benchmark: bool  # 参与基准计算
    include_in_ranking: bool    # 参与排名计算
    include_in_report: bool      # 出现在报告
    reason: str               # 进入池子的理由
    added_at: str             # 加入日期
    reviewed_at: Optional[str] # 复核日期
```

**Role 类型定义**：

| Role | 适用池子 | 说明 |
|------|---------|------|
| `direct_comparable` | direct_peers | 直接可比公司 |
| `upstream_supplier` | industry_chain | 上游供应商 |
| `downstream_demand` | industry_chain | 下游需求方 |
| `theme_heat_proxy` | theme_pool | 主题热度代理 |
| `trading_signal` | trading_watchlist | 交易信号 |
| `inactive_watch` | trading_watchlist | 观察中（已禁用） |

### 4.4 Anchor（锚定标的）

```python
@dataclass(frozen=True)
class Anchor:
    symbol: str       # 股票代码：688333.SH
    name: str        # 名称：铂力特
    reason: str      # 为什么选择这个标的
    added_date: str  # 加入日期
```

---

## 5. 三种计算口径

PoolRegistry 提供三种口径，用于不同计算场景：

### 5.1 Benchmark Scope

```python
def get_benchmark_scope(self, universe_id: str) -> list[Membership]:
    """参与基准计算"""
    return [
        m for m in self._config.memberships
        if m.universe_id == universe_id
        and m.enabled
        and m.include_in_benchmark
    ]
```

**用途**：计算池子均值、中位数、广度

**当前 Benchmark 成员**：

| Universe | Symbol | Name | Role |
|----------|--------|------|------|
| direct_peers | 688433.SH | 华曙高科 | direct_comparable |
| industry_chain | 600343.SH | 航天动力 | downstream_demand |
| industry_chain | 600879.SH | 航天电子 | upstream_supplier |
| industry_chain | 600118.SH | 中国卫星 | downstream_demand |
| theme_pool | 无（include_in_benchmark=false） | — | — |
| trading_watchlist | 无（include_in_benchmark=false） | — | — |

### 5.2 Ranking Scope

```python
def get_ranking_scope(self, universe_id: str, include_anchor: bool = True) -> list[str]:
    """参与排名计算"""
    symbols = [
        m.symbol for m in self._config.memberships
        if m.universe_id == universe_id
        and m.enabled
        and m.include_in_ranking
    ]
    if include_anchor:
        anchor_symbol = self._config.anchor.symbol
        if anchor_symbol not in symbols:
            symbols.append(anchor_symbol)
    return symbols
```

**用途**：涨幅排名、成交额排名、换手率排名、资金排名

**设计决策**：Anchor 不在任何 Membership 中，但 ranking 需要包含 Anchor

### 5.3 Report Scope

```python
def get_report_scope(self, universe_id: str) -> list[Membership]:
    """出现在报告中"""
    return [
        m for m in self._config.memberships
        if m.universe_id == universe_id
        and m.enabled
        and m.include_in_report
    ]
```

**用途**：生成 peer_matrix.csv 和 industry_report.md

---

## 6. 当前 Membership 详情

### 6.1 direct_peers（核心同类池）

| Symbol | Name | Role | Relevance | Weight | Benchmark | Ranking | Report |
|--------|------|------|-----------|--------|-----------|---------|--------|
| 688433.SH | 华曙高科 | direct_comparable | 0.90 | 1.0 | ✅ | ✅ | ✅ |

**设计说明**：
- 唯一核心同类是华曙高科（同属增材制造赛道）
- relevance 0.9（高相关）
- 近20日相关系数 +0.792

### 6.2 industry_chain（产业链池）

| Symbol | Name | Role | Relevance | Weight | Benchmark | Ranking | Report |
|--------|------|------|-----------|--------|-----------|---------|--------|
| 600343.SH | 航天动力 | downstream_demand | 0.85 | 1.0 | ✅ | ✅ | ✅ |
| 600879.SH | 航天电子 | upstream_supplier | 0.80 | 1.0 | ✅ | ✅ | ✅ |
| 600118.SH | 中国卫星 | downstream_demand | 0.75 | 1.0 | ✅ | ✅ | ✅ |
| 003009.SZ | 中天火箭 | downstream_demand | 0.70 | 0.8 | ❌ | ✅ | ✅ |

**设计说明**：
- 4 只股票，3 只参与 benchmark
- 003009.SZ 不参与 benchmark（weight=0.8）
- 上游供应商（航天电子）+ 下游需求方（航天动力、中国卫星、中天火箭）

### 6.3 theme_pool（主题情绪池）

| Symbol | Name | Role | Relevance | Weight | Benchmark | Ranking | Report |
|--------|------|------|-----------|--------|-----------|---------|--------|
| 688433.SH | 华曙高科 | theme_heat_proxy | 0.65 | 0.5 | ❌ | ✅ | ✅ |
| 601698.SH | 中国卫通 | theme_heat_proxy | 0.60 | 0.5 | ❌ | ✅ | ✅ |
| 300762.SZ | 上海瀚讯 | theme_heat_proxy | 0.55 | 0.4 | ❌ | ✅ | ✅ |
| 688062.SH | 航天宏图 | theme_heat_proxy | 0.50 | 0.3 | ❌ | ✅ | ✅ |
| 688568.SH | 中科星图 | theme_heat_proxy | 0.45 | 0.3 | ❌ | ✅ | ✅ |

**设计说明**：
- 所有成员 include_in_benchmark=false
- 688433.SH 华曙高科同时在 direct_peers 和 theme_pool（双重身份）
- relevance 逐次递减（0.65 → 0.45）

### 6.4 trading_watchlist（交易观察池）

| Symbol | Name | Role | Relevance | Weight | Benchmark | Ranking | Report |
|--------|------|------|-----------|--------|-----------|---------|--------|
| 688102.SH | 斯瑞新材 | trading_signal | 0.80 | 0.6 | ❌ | ✅ | ✅ |
| 603678.SH | 火炬电子 | trading_signal | 0.85 | 0.7 | ❌ | ✅ | ✅ |
| 000733.SZ | 振华科技 | trading_signal | 0.87 | 0.7 | ❌ | ✅ | ✅ |
| 603267.SH | 鸿远电子 | trading_signal | 0.90 | 0.8 | ❌ | ✅ | ✅ |
| 002179.SZ | 中航光电 | trading_signal | 0.53 | 0.5 | ❌ | ✅ | ✅ |
| 600151.SH | 航天工程 | inactive_watch | 0.20 | 0.1 | ❌ | ❌ | ❌ |

**设计说明**：
- 603267.SH 鸿远电子 relevance 最高（0.90）
- 600151.SH 航天工程已禁用（enabled=false，inactive_watch）
- 600151.SH 不参与 ranking 和 report

---

## 7. 双重身份股票

一只股票可以进入多个 Universe，需要独立记录每对关系：

### 7.1 华曙高科（688433.SH）

| Universe | Role | Relevance | Reason |
|----------|------|-----------|--------|
| direct_peers | direct_comparable | 0.90 | 同属增材制造赛道，业务模式互补 |
| theme_pool | theme_heat_proxy | 0.65 | 同属 3D 打印主题，近期走势分化是研究信号 |

**设计意图**：作为核心可比公司时用 direct_peers，作为主题代理时用 theme_pool

### 7.2 航天工程（600151.SH）

| Universe | Role | Relevance | Enabled |
|----------|------|-----------|---------|
| trading_watchlist | inactive_watch | 0.20 | ❌ 已禁用 |

**禁用原因**：主业为煤化工工程，与商业航天无实质关联，已降入 extended 观察

---

## 8. 配置校验规则

### 8.1 validate() 校验

```python
def validate(self) -> dict[str, Any]:
    """验证配置完整性"""
    errors = []
    warnings = []

    # 1. 验证每个 universe 的 min_size
    for universe in self._config.universes.values():
        benchmark_members = self.get_benchmark_scope(universe.universe_id)
        if len(benchmark_members) < universe.min_size:
            if universe.can_be_benchmark:
                errors.append(
                    f"{universe.display_name}({universe.universe_id}) "
                    f"benchmark成员数({len(benchmark_members)}) < min_size({universe.min_size})"
                )

    # 2. 验证 membership 中的 symbol 必须存在于 instruments
    for mem in self._config.memberships:
        if mem.symbol not in self._config.instruments:
            errors.append(
                f"Membership({mem.universe_id}/{mem.symbol}) "
                f"引用的 symbol 不存在于 instruments"
            )
```

### 8.2 校验规则汇总

| 规则 | 级别 | 说明 |
|------|------|------|
| benchmark 成员数 >= min_size | Error | can_be_benchmark=True 时必须满足 |
| symbol 必须在 instruments 中存在 | Error | 配置引用完整性 |
| enabled=true 的 membership 应有 reviewed_at | Warning | 未定期复核 |

---

## 9. 代码实现

### 9.1 核心文件

| 文件 | 职责 |
|------|------|
| `src/config/loader.py` | PoolRegistry，配置加载与管理 |
| `src/group_rotation/models.py` | GroupRotation 数据模型 |
| `src/output/models.py` | IndustrySnapshot 及相关模型 |
| `src/anchor_position/ranking_calculator.py` | 排名计算 |

### 9.2 PoolRegistry 核心接口

```python
class PoolRegistry:
    # 获取成员
    def get_members(self, universe_id: str, enabled_only: bool = True) -> list[Membership]

    # 三种口径
    def get_benchmark_scope(self, universe_id: str) -> list[Membership]
    def get_ranking_scope(self, universe_id: str, include_anchor: bool = True) -> list[str]
    def get_report_scope(self, universe_id: str) -> list[Membership]

    # 辅助接口
    def get_universe(self, universe_id: str) -> Optional[Universe]
    def get_instrument(self, symbol: str) -> Optional[Instrument]
    def get_all_universes(self) -> list[Universe]
    def get_all_symbols(self) -> list[str]
    def get_anchor(self) -> Anchor
    def validate(self) -> dict[str, Any]
```

### 9.3 使用示例

```python
from src.config.loader import PoolRegistry

# 初始化
registry = PoolRegistry()

# 获取产业链池 benchmark 成员
benchmark_members = registry.get_benchmark_scope("industry_chain")
# -> [Membership(600343.SH), Membership(600879.SH), Membership(600118.SH)]

# 获取产业链池 ranking 成员（含 Anchor）
ranking_symbols = registry.get_ranking_scope("industry_chain", include_anchor=True)
# -> ["600343.SH", "600879.SH", "600118.SH", "003009.SZ", "688333.SH"]

# 校验配置
validation = registry.validate()
# -> {"valid": True, "errors": [], "warnings": [], "stats": {...}}
```

---

## 10. 与旧版 stocks.yaml 的关系

### 10.1 旧版结构（stocks.yaml v2026-03-18）

| 层级 | 数量 | 说明 |
|------|------|------|
| core_universe | 3 | 参与板块均值计算 |
| research_core | 3 | 研究对标，不参与计算 |
| research_candidates | 1 | 待评估 |
| trading_candidates | 1 | 待评估 |
| extended_universe | 8 | 观察，不参与计算 |

### 10.2 新版结构（pools.yaml v2026-05-02）

| 层级 | Universe | Benchmark 成员数 |
|------|----------|------------------|
| direct_peers | 核心同类池 | 1 |
| industry_chain | 产业链池 | 3 |
| theme_pool | 主题情绪池 | 0 |
| trading_watchlist | 交易观察池 | 0 |

### 10.3 映射关系

| 旧版 (stocks.yaml) | 新版 (pools.yaml) | 变化 |
|------------------|------------------|------|
| core_universe | industry_chain | 重命名 |
| research_core | direct_peers + 部分 industry_chain | 拆分重组 |
| extended_universe | theme_pool + trading_watchlist | 合并重组 |

### 10.4 当前状态

- **pools.yaml**：新版配置，正式使用中
- **stocks.yaml**：已删除（2026-05-06 清理旧配置残留）
- 迁移已完成：所有代码已更新为使用 pools.yaml

---

## 11. 变更记录

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-05-02 | v2026-05-02 | Phase 1 配置重构：从 stocks.yaml 单层结构迁移到 pools.yaml 三层结构 |
| 2026-03-18 | v2026-03-18 | 股票池治理规则固化 |
| 2026-03-17 | v2026-03-17e | research_core 正式建立：华曙高科、中天火箭升入 research_core |
| 2026-03-10 | v2026-03-10 | 重构为双层结构（core/extended），core 3只，extended 7只 |

---

## 12. 下一步优化方向

| 优化项 | 说明 | 优先级 |
|--------|------|--------|
| 估值分位计算 | 当前 ranking_calculator 不含 pe/pb 字段，需扩展 | 高 |
| 历史相关性回测 | 基于历史数据验证 relevance 和 role | 中 |
| 自动复核提醒 | 当 reviewed_at 超过 90 天时警告 | 中 |
| Universe 变更 diff | 在报告中展示股票池变更 diff | 低 |
