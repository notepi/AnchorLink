# 虚拟 ETF / 自定义指数 基础数据产品

## Context

当前系统的多日超额收益（excess_5d / excess_10d）通过累加每日 `anchor_return - industry_chain_median` 得到。这只能定义为"中位数累计位移"，不等于相对一个连续可投资基准组合的收益——因为每天的中位数可能由不同股票贡献。

本次实现独立的 ETF-like NAV 指数产品，为超额收益提供可投资基准。不修改 Q×G 逻辑，不覆盖旧输出。

**重要声明**：本产品使用当前 pools.yaml 配置回算历史，无法证明历史时点就使用这些成员和权重。输出和文档中必须标注 `universe_mode = constant_universe_research_view`，不得声称是 point-in-time 实盘指数回放。

## 文件清单

### 新建

| 文件 | 职责 |
|------|------|
| `src/index_products/__init__.py` | 包入口 |
| `src/index_products/models.py` | frozen dataclass 数据结构 |
| `src/index_products/builder.py` | NAV 构建、再平衡、成员权重、超额计算 |
| `src/index_products/quality.py` | 数据质量校验（唯一键、覆盖率、陈旧报价溯源） |
| `scripts/build_custom_indexes.py` | 入口脚本：读取 → 构建 → 写入 → 打印摘要 |
| `tests/test_index_products.py` | 23 项单元测试 |
| `docs/excess_backtest/index_excess_methodology.md` | 方法论文档 |

### 不修改

- `src/price/fetcher.py`（已有其他改动，必须保留）
- `src/price/normalizer.py`（不增加字段，builder 端解决溯源）
- `src/v2_scorer/`、`scripts/excess_grade_backtest.py`（Q×G 逻辑不动）
- `docs/excess_backtest/` 下已有文件
- `data/output/history_summary.csv`、`data/output/history_rolling_metrics.csv`（只读引用）

## 关键依赖

- **配置**: `config/pools.yaml` → `src/config/loader.py` → `PoolRegistry`
- **行情 (normalized)**: `data/price/normalized/market_data_normalized.parquet`（前复权 close，6561 行 × 27 股，2025-06-03 ~ 2026-06-02，含补齐行）
- **行情 (raw)**: `data/price/raw/market_data.parquet`（6540 行，用于判断报价是否为补齐，见 §陈旧报价溯源）
- **旧口径**: `data/output/history_summary.csv`（`relative_strength_vs_industry_chain` 列）+ `data/output/history_rolling_metrics.csv`（`excess_5d`, `excess_10d` 列）
- **存储层**: `src/shared/storage.py` → `Storage("price").analytics_dir` → `data/price/analytics/`

## 陈旧报价溯源（修改 #1）

normalizer 会对缺失日 forward-fill OHLCV 并设 `vol=0`、`amount=0`，但 normalized 层无标记列。

**方案**：builder 同时读取 raw 和 normalized，通过 `(ts_code, trade_date)` 是否存在于 raw 判断报价是否补齐。不修改 normalizer。

报价状态三分类（`quote_status`）：

| `quote_status` | 含义 | 判定条件 |
|----------------|------|---------|
| `fresh` | 当日真实成交报价 | raw 中存在该 (ts_code, trade_date) 且 vol > 0 |
| `carried_forward` | 补齐报价（normalizer forward-fill） | raw 中不存在该 (ts_code, trade_date) |
| `zero_volume_raw` | raw 中有记录但零成交 | raw 中存在该 (ts_code, trade_date) 且 vol == 0 |

`price_is_stale` 定义：`quote_status in ("carried_forward", "zero_volume_raw")`。

```python
def _build_stale_matrix(normalized_df, raw_df, trading_days, symbols):
    """
    返回矩阵: {symbol: {date: (quote_status, source_trade_date, stale_days)}}
    """
    raw_keys = set(zip(raw_df["ts_code"], raw_df["trade_date"].dt.strftime("%Y%m%d")))
    raw_zero_vol = set(zip(
        raw_df.loc[raw_df["vol"] == 0, "ts_code"],
        raw_df.loc[raw_df["vol"] == 0, "trade_date"].dt.strftime("%Y%m%d")
    ))
    # 逐 cell 判定...
```

每个 member 每日额外输出：
- `quote_status: str` — `"fresh"` / `"carried_forward"` / `"zero_volume_raw"`
- `price_is_stale: bool` — 是否非 fresh 报价
- `source_trade_date: str` — 实际报价来源日（forward-fill 来源的原始交易日）
- `stale_days: int` — 连续使用补齐报价的天数

## 版本化输出目录（修改 #2）

输出路径使用 `Storage("price").analytics_dir`：

```
data/price/analytics/index_products/constant_universe_{pool_config_version}/
```

例如当前配置版本 `2026-05-06`：

```
data/price/analytics/index_products/constant_universe_2026-05-06/
  build_manifest.json                     # 版本元数据（人工可读）
  custom_index_nav.csv                    # 检查用
  custom_index_nav.parquet                # 正式数据产品
  custom_index_members.csv
  custom_index_members.parquet
  anchor_index_excess.csv
  anchor_index_excess.parquet
  legacy_vs_index_excess_comparison.csv
  legacy_vs_index_excess_comparison.parquet
```

每次生成不覆盖历史版本。如果配置版本相同则覆盖同目录（幂等）。

## 固定股票池研究视图元数据（修改 #3）

所有输出文件（CSV 和 parquet）必须包含以下元数据字段/列：

| 字段 | 值 | 说明 |
|------|-----|------|
| `universe_mode` | `constant_universe_research_view` | 固定股票池研究视图 |
| `pool_config_version` | 来自 pools.yaml `version` | 当前 `2026-05-06` |
| `price_adjustment_mode` | `qfq` | 前复权 |
| `source_data_as_of` | normalized 数据最新交易日 | 行情数据截止日 |
| `build_mode` | `full_rebuild` | 每次完整重建，不追加 |
| `generated_at` | ISO 8601 时间戳 | 生成时刻 |

parquet 文件元数据通过 `pyarrow.Table.replace_schema_metadata()` 写入。同时输出 `build_manifest.json`（人工可读，包含上述全部元数据字段 + overlap 信息 + 各指数摘要），方便检查版本信息而无需解析 parquet schema。

文档中必须明确声明："本产品不是 point-in-time 实盘回放。本产品是 constant-universe research view。"不得声称是 point-in-time 实盘回放，但"point-in-time"一词本身可用于对比说明。

## 数据模型 (`models.py`)

```python
from typing import Optional

@dataclass(frozen=True)
class IndexMember:
    symbol: str
    raw_config_weight: float           # pools.yaml 中的原始 weight（如 0.8）
    normalized_target_weight: float    # 归一化后的目标权重（如 0.1111）
    role: str
    membership_scope: str              # "benchmark" | "ranking"

@dataclass(frozen=True)
class IndexDefinition:
    index_id: str               # "{universe_id}_index"，如 "industry_chain_index"
    display_name: str
    can_be_benchmark: bool
    pool_config_version: str
    members: tuple[IndexMember, ...]

@dataclass(frozen=True)
class IndexNAVRecord:
    index_id: str
    trade_date: str             # YYYYMMDD
    nav: float
    index_return_1d: Optional[float]   # 百分比，首日为 None
    index_return_3d: Optional[float]   # 百分比，前 2 日为 None
    index_return_5d: Optional[float]   # 百分比，前 4 日为 None
    index_return_10d: Optional[float]  # 百分比，前 9 日为 None
    is_rebalance_day: bool
    rebalance_uses_stale_price: bool   # 当日再平衡是否有成员使用了 stale 报价
    included_member_count: int         # 当日实际纳入的成员数
    configured_member_count: int       # 配置中的成员总数
    fresh_price_count: int             # fresh 报价成员数
    stale_price_count: int             # 非 fresh 报价成员数
    stale_days_max: int                # 当日最大连续非 fresh 天数
    stale_symbols: str                 # 逗号分隔
    fresh_quote_ratio: float           # fresh_price_count / included_member_count
    universe_inclusion_ratio: float    # included_member_count / configured_member_count
    data_status: str                   # "ok" | "partial" | "insufficient_data"
    rebalance_flag: str                # "" | "monthly"
    rebalance_reason: str              # "monthly_rebalance" | "late_member_join" | "none"
    pool_config_version: str
    price_adjustment_mode: str         # "qfq"
    universe_mode: str                 # "constant_universe_research_view"
    source_data_as_of: str             # 行情数据截止日，YYYYMMDD
    build_mode: str                    # "full_rebuild"
    generated_at: str                  # ISO 8601

@dataclass(frozen=True)
class MemberDayRecord:
    index_id: str
    trade_date: str
    symbol: str
    raw_config_weight: float                         # pools.yaml 原始 weight
    normalized_target_weight: float                  # 归一化后目标权重
    actual_weight: Optional[float]                   # units * close / nav；included=false 时为 None
    close: Optional[float]                           # included=false 时为 None
    quote_status: str                                # "fresh" | "carried_forward" | "zero_volume_raw"；included=false 时为 ""
    price_is_stale: bool
    source_trade_date: Optional[str]                 # 报价实际来源日；included=false 时为 None
    stale_days: int                                  # 连续非 fresh 天数
    included: bool
    membership_role: str
    membership_event: str                            # "base_init" | "late_member_join" | "none"
    pool_config_version: str
    price_adjustment_mode: str
    universe_mode: str
    source_data_as_of: str
    build_mode: str
    generated_at: str

@dataclass(frozen=True)
class AnchorExcessRecord:
    date: str                          # YYYYMMDD
    anchor_symbol: str
    anchor_close: float
    # Anchor 多周期收益（百分比）
    anchor_return_1d: Optional[float]
    anchor_return_3d: Optional[float]
    anchor_return_5d: Optional[float]
    anchor_return_10d: Optional[float]
    # 4 指数 × 4 窗口，前 N-1 天为 None
    excess_vs_industry_chain_index_1d: Optional[float]
    excess_vs_industry_chain_index_3d: Optional[float]
    excess_vs_industry_chain_index_5d: Optional[float]
    excess_vs_industry_chain_index_10d: Optional[float]
    excess_vs_direct_peers_index_1d: Optional[float]
    excess_vs_direct_peers_index_3d: Optional[float]
    excess_vs_direct_peers_index_5d: Optional[float]
    excess_vs_direct_peers_index_10d: Optional[float]
    excess_vs_theme_pool_index_1d: Optional[float]
    excess_vs_theme_pool_index_3d: Optional[float]
    excess_vs_theme_pool_index_5d: Optional[float]
    excess_vs_theme_pool_index_10d: Optional[float]
    excess_vs_trading_watchlist_index_1d: Optional[float]
    excess_vs_trading_watchlist_index_3d: Optional[float]
    excess_vs_trading_watchlist_index_5d: Optional[float]
    excess_vs_trading_watchlist_index_10d: Optional[float]
    pool_config_version: str
    price_adjustment_mode: str
    universe_mode: str
    source_data_as_of: str
    build_mode: str
    generated_at: str
```

## 成员筛选规则

严格按需求，每个池子用自己的规则：

| 指数 ID | 筛选条件 | 对应 PoolRegistry 方法 |
|---------|---------|----------------------|
| `industry_chain_index` | `enabled=True, include_in_benchmark=True` | `get_benchmark_scope("industry_chain")` |
| `direct_peers_index` | `enabled=True, include_in_benchmark=True` | `get_benchmark_scope("direct_peers")` |
| `theme_pool_index` | `enabled=True, include_in_ranking=True` | `get_ranking_scope_members("theme_pool")` |
| `trading_watchlist_index` | `enabled=True, include_in_ranking=True` | `get_ranking_scope_members("trading_watchlist")` |

## NAV 构建算法 (`builder.py`)

### 核心流程

```
build_all_indexes()
  → load PoolRegistry + normalized parquet + raw parquet
  → run quality checks (quality.py)
  → build_index_definitions(registry)           # 4 条 IndexDefinition
  → build_stale_matrix(normalized, raw, ...)    # 陈旧报价溯源矩阵
  → for each definition:
      build_nav_series(def, price_df, stale_matrix, ...)
  → compute_anchor_excess(all_nav, anchor_closes)
  → build_legacy_comparison(anchor_excess, history_summary)
  → write CSVs + parquets to versioned output dir
```

**构建模式**：每次生成完整重建该版本（`build_mode = full_rebuild`），不追加最新 NAV。前复权行情在公司行为后历史价格可能重算，追加会导致不一致。`source_data_as_of` 记录行情数据截止日。

### 陈旧报价溯源

1. 读取 raw parquet，构建 `raw_keys = set((ts_code, trade_date_str))` 和 `raw_zero_vol`（vol==0 的键集合）
2. 读取 normalized parquet，逐行判定 quote_status：不在 raw_keys → `carried_forward`；在 raw_keys 且在 raw_zero_vol → `zero_volume_raw`；其余 → `fresh`
3. 对每个 symbol 的非 fresh 段，计算 `source_trade_date`（上一个 fresh 日的日期）和 `stale_days`（连续非 fresh 天数）
4. 输出 stale_matrix: `{symbol: {date: (quote_status, source_trade_date, stale_days)}}`

### NAV 构建 `build_nav_series()` 步骤

1. **准备价格矩阵**: pivot `close` 以 trade_date 为行、ts_code 为列；forward-fill NaN
2. **确定交易日历**: 排序去重 trade_date
3. **确定 base_date**: 每条指数独立确定——首个满足 `included_member_count >= universe.min_size` 且 `universe_inclusion_ratio >= 0.8` 的交易日
4. **初始化 units**: 只纳入 base_date 有有效 close 的成员
   - `units_i = 1000 * effective_target_weight_i / close_i(base_date)`
   - `effective_target_weight_i` = 对当日已纳入成员的 raw_config_weight 重新归一化
5. **检测再平衡日**: 月频 = 每月第一个交易日（`month != prev_month`）
6. **逐日迭代** (从 base_date 起):
   - a. 检查是否有迟到成员首次出现有效 close → 全量连续再平衡（见下方）
   - b. 计算当日 NAV: `nav = sum(units_i * close_i(t))`
   - c. 从 stale_matrix 查询每个成员的 is_stale / source_trade_date / stale_days
   - d. 计算 actual_weight: `units_i * close_i(t) / nav`
   - e. 计算 fresh_quote_ratio / universe_inclusion_ratio / data_status
   - f. 记录 IndexNAVRecord（含全部元数据字段）
   - g. **再平衡** (若当日为再平衡日):
     - 先用旧 units 算出 nav（已记录）
     - 更新: `units_i_new = nav * effective_target_weight_i / close_i(t)`
     - `effective_target_weight_i` = 当日已纳入成员的 raw_config_weight / sum(当日已纳入成员 raw_config_weight)
     - 验证: `sum(units_i_new * close_i(t))` ≈ nav（NAV 连续性）
     - 新 units 次日生效

### 迟到成员处理（修改 #4）

成员在 base_date 后才有首个有效 close 时，执行**全量连续再平衡**：

```
nav_pre = sum(旧 units_j * close_j(t))    # 纳入前 NAV

# 重新归一化：对所有已纳入成员（含新成员）的 raw_config_weight 求和
effective_target_weight_i = raw_config_weight_i / sum(已纳入成员 raw_config_weight)

对所有已纳入成员（含新成员）统一重算：
units_i_new = nav_pre * effective_target_weight_i / close_i(t)
```

NAV 连续性保证：`sum(units_i_new * close_i) = nav_pre * sum(effective_target_weight_i) = nav_pre`。

如果迟到成员加入日恰好也是月初再平衡日，只执行一次全量再平衡。

### 再平衡频率参数化

```python
def _find_rebalance_dates(trading_days, freq: str = "monthly") -> set:
    if freq == "none": return set()
    if freq == "monthly": # 每月首个交易日
    if freq == "quarterly": # 每季首个交易日（预留）
    raise ValueError(f"Unknown rebalance_freq: {freq}")
```

### 再平衡生效时点（修改 #5）

明确定义：

```
rebalance_at = close
effective_from = next_trading_day
```

即：再平衡日当天 NAV 用旧 units 计算，收盘后更新 units，新 units 自下一个交易日起生效。月初当天的收益仍由旧权重决定。

### 再平衡与陈旧报价

再平衡日遇到 stale 成员时，仍使用其 forward-filled close 参与再平衡计算（研究型指数估值需要），但必须记录风险标记：

```
rebalance_uses_stale_price: bool  # 当日再平衡是否有成员使用了 stale 报价
```

文档中说明：这是估值型研究指数，不代表该组合能够按 stale 价格真实成交。

## 超额计算

严格按需求公式：

```
anchor_return_Nd = anchor_close(t) / anchor_close(t-N) - 1
index_return_Nd  = index_nav(t)    / index_nav(t-N)    - 1
excess_vs_index_Nd = anchor_return_Nd - index_return_Nd
```

输出统一百分比口径（× 100）。前 N-1 天 `excess_Nd` 为 None。

## 新旧对照

从 `history_summary.csv` 读取 `relative_strength_vs_industry_chain`，重命名为 `median_displacement_1d`。5d/10d 通过滚动求和计算。`excess_5d` 和 `excess_10d` 从 `history_rolling_metrics.csv` 读取，重命名为 `median_displacement_5d` / `median_displacement_10d`。

**共同区间约束**：旧快照从约 2025-05-16 开始，新 qfq 行情从 2025-06-03 开始。对照统计必须按日期 inner join，不得把共同区间写成"全历史"。构建时报告 `overlap_start` / `overlap_end` / `overlap_n`。

对照 CSV 只包含 industry_chain（旧口径只对 industry_chain 有完整的 5d/10d 数据）。

## 数据质量校验 (`quality.py`)

| 检查 | 失败行为 |
|------|---------|
| `(ts_code, trade_date)` 唯一 | `raise ValueError` |
| 已纳入成员的估值 close 无 null / ≤ 0 | `raise ValueError`；未纳入成员（included=false）允许 close 为空 |
| anchor 覆盖最新交易日 | **`raise ValueError`**（修改 #6），除非 `allow_stale_anchor=True` |
| fresh_quote_ratio 阈值 | data_status 降级 |
| raw 与 normalized 最新日同步 | `print [WARN]` |
| pool_config_version 写入输出 | 构建时强制写入 |

覆盖率降级规则（拆分为两个比率）：

```
fresh_quote_ratio = fresh_price_count / included_member_count
universe_inclusion_ratio = included_member_count / configured_member_count

data_status 判定：
  fresh_quote_ratio >= 0.8 AND universe_inclusion_ratio >= 0.8  → "ok"
  fresh_quote_ratio >= 0.5 AND universe_inclusion_ratio >= 0.5  → "partial"
  其他                                                           → "insufficient_data"
```

## 输出文件

输出目录：`data/price/analytics/index_products/constant_universe_{version}/`

每个文件同时输出 CSV（人工检查）和 parquet（正式数据产品）。

### `custom_index_nav.csv / .parquet`
```
date, index_id, index_nav, index_return_1d, index_return_3d, index_return_5d, index_return_10d,
is_rebalance_day, rebalance_uses_stale_price, rebalance_reason, included_member_count, configured_member_count,
fresh_price_count, stale_price_count, stale_days_max, stale_symbols,
fresh_quote_ratio, universe_inclusion_ratio, data_status, rebalance_flag,
pool_config_version, price_adjustment_mode, universe_mode, source_data_as_of, build_mode, generated_at
```

### `custom_index_members.csv / .parquet`
```
date, index_id, symbol, raw_config_weight, normalized_target_weight, actual_weight, close,
quote_status, price_is_stale, source_trade_date, stale_days, included, membership_role, membership_event,
pool_config_version, price_adjustment_mode, universe_mode, source_data_as_of, build_mode, generated_at
```

### `anchor_index_excess.csv / .parquet`
```
date, anchor_symbol, anchor_close, anchor_return_1d, anchor_return_3d, anchor_return_5d, anchor_return_10d,
excess_vs_industry_chain_index_1d, excess_vs_industry_chain_index_3d,
excess_vs_industry_chain_index_5d, excess_vs_industry_chain_index_10d,
excess_vs_direct_peers_index_1d, excess_vs_direct_peers_index_3d,
excess_vs_direct_peers_index_5d, excess_vs_direct_peers_index_10d,
excess_vs_theme_pool_index_1d, excess_vs_theme_pool_index_3d,
excess_vs_theme_pool_index_5d, excess_vs_theme_pool_index_10d,
excess_vs_trading_watchlist_index_1d, excess_vs_trading_watchlist_index_3d,
excess_vs_trading_watchlist_index_5d, excess_vs_trading_watchlist_index_10d,
pool_config_version, price_adjustment_mode, universe_mode, source_data_as_of, build_mode, generated_at
```

### `legacy_vs_index_excess_comparison.csv / .parquet`
```
date, median_displacement_1d, median_displacement_5d, median_displacement_10d,
index_excess_1d, index_excess_3d, index_excess_5d, index_excess_10d,
diff_1d, diff_5d, diff_10d,
overlap_start, overlap_end, overlap_n,
pool_config_version, price_adjustment_mode, universe_mode, source_data_as_of, build_mode, generated_at
```

## 测试 (`tests/test_index_products.py`)

23 项测试，使用合成行情数据（3 只股票 × 30 交易日）：

1. 权重归一化总和 ≈ 1.0
2. 初始 NAV == 1000
3. 无价格变化 → NAV 不变
4. 单只股票上涨 → NAV 按实际权重变化
5. 月初再平衡前后 NAV 连续
6. 停牌成员用上一有效 close，NAV 不变 NaN
7. stale member 被正确记录（price_is_stale=True，source_trade_date 指向原始日）
8. 同一股票在不同指数中允许不同权重
9. `excess_Nd = anchor_return_Nd - index_return_Nd`
10. 输入有重复键 → ValueError
11. anchor 缺最新日 → ValueError（默认行为）；传入 `allow_stale_anchor=True` → 仅警告
12. 覆盖率低于阈值 → data_status 正确降级
13. 迟到成员纳入时 NAV 连续（全量连续再平衡）
14. 月初再平衡生效时点：再平衡日当天收益由旧权重决定，次日起新权重生效
15. stale_days 正确累计（连续多日补齐时 stale_days 递增）
16. 固定股票池研究视图元数据完整（universe_mode / pool_config_version / price_adjustment_mode / source_data_as_of / build_mode / generated_at 均非空）
17. 新旧对照只统计日期交集（overlap_start / overlap_end / overlap_n 正确）
18. raw_config_weight / normalized_target_weight / actual_weight 三种权重正确（可追溯 0.8 → 0.1111 → 当日实际）
19. index_return_3d/5d/10d 与 NAV 点位一致（`nav(t)/nav(t-N)-1` 吻合）
20. raw 中 vol=0 时 quote_status == "zero_volume_raw"
21. stale 报价参与再平衡时 rebalance_uses_stale_price == True
22. 迟到成员加入日 effective_target_weight 正确重新归一化（权重和 == 1.0）
23. membership_event / rebalance_reason 字段正确（base_init / late_member_join / monthly_rebalance / none）

## 实施顺序

1. `models.py` — 纯数据结构
2. `quality.py` — 质量检查函数
3. `builder.py` — 核心引擎（含陈旧报价溯源）
4. `__init__.py` — 包入口
5. `build_custom_indexes.py` — 入口脚本
6. `test_index_products.py` — 测试
7. `index_excess_methodology.md` — 文档

## 验证

```bash
# 1. 运行构建
uv run python scripts/build_custom_indexes.py

# 2. 检查输出
ls -la data/price/analytics/index_products/constant_universe_2026-05-06/
head -3 data/price/analytics/index_products/constant_universe_2026-05-06/custom_index_nav.csv

# 3. 运行测试
uv run pytest tests/test_index_products.py -v

# 4. 确认旧数据未修改
git diff -- data/output/ docs/excess_backtest/

# 5. 交叉验证
# 查看 legacy_vs_index_excess_comparison.csv 中的 diff_* 列
```

验收摘要需包含：
- 四条指数各自成员数量
- 各指数起始日、结束日、最新 NAV
- 最新日期 fresh_quote_ratio / universe_inclusion_ratio、陈旧报价列表
- industry_chain_index 最新 1D/3D/5D/10D 收益
- 铂力特相对 industry_chain_index 最新标准超额
- 新旧共同区间相关系数、MAE、最大差异（报告 overlap_start / overlap_end / overlap_n）
- 测试通过数
- 修改文件清单
