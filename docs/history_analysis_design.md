# 历史时间序列分析模块

## Context

AnchorLink 目前只有单日快照，96 个 `data/output/{YYYYMMDD}/industry_snapshot.json` 互相孤立。Codex 的初步扫描发现了一些有价值的模式（如"行业强个股弱"象限次日平均收益为负，极端背离日期可追溯个股事件），但这些发现停留在内存临时计算，没有落地为可复用的代码和数据。

**核心问题**：缺一张把 96 天 JSON 串成时间序列的汇总表，以及基于这张表的多层分析。没有这些，每日报告只能解释当天，无法回答"铂力特是跟板块还是独立""哪些信号真的有用""今天这个状态历史上之后怎么走"。

**目标定位**：不只是"生成几个统计 CSV"，而是建成一个**历史规律验证层**——从"解释今天"走向"验证历史规律，指导当前判断"。

## 目标

1. 汇总表：96 天 JSON → 单一 CSV，含次日/3日/5日前瞻收益及前瞻超额收益
2. 四象限分析：按 industry_beta × anchor_alpha 分组，统计前瞻收益和胜率
3. 极端背离复盘：|锚定-产业链| > 阈值的日期 + T-5 到 T+5 事件路径
4. 滚动指标：5d/10d 累计超额、连续跑赢/跑输、风险高位连续天数等
5. 信号 lift：每个标签出现后的前瞻收益、胜率、相对 baseline 的 lift
6. 状态转移矩阵：今天这个象限明天转成什么，概率多少

## 架构位置

放在 `src/history_analysis/`，不在 `src/output/history/`。

原因：架构文档第 10 节明确 "Output 层不新增业务判断，只格式化输出"（见 `docs/architecture.md` L125）。历史分析会做象限分类、胜率判断、背离筛选、lift 计算，属于新增业务判断，应在 Output 层之外。

CSV 写入归 `src/output/history_csv_writer.py`，因为写入文件是 Output 层的职责。

## 关键约束

- `industry_state` 缺 `trading_watchlist_return_median`，需从 `group_rotation.group_medians` 取
- `industry_state.up_ratio` 来自 `direct_peers`（代码见 `json_writer.py` L98），不是 `industry_chain`。历史表字段名改为 `direct_up_ratio` 以明确口径
- `chain_up_ratio` 当前快照未输出，需要在 `json_writer.py` 补充后历史表才能包含，暂时标注为可选字段
- 首日 20251209 的 `group_medians` 为空，所有 industry_state 字段为 None
- 前瞻收益必须按交易日位置对齐（不是自然日偏移），从 parquet close 价格计算
- 所有百分比统一用"百分点"口径（snapshot 里 `anchor_return` = `2.71` 表示 2.71%，不是 0.0271）
- 优先读取 `data/price/normalized/market_data_normalized.parquet`，不存在再 fallback 到 `data/price/raw/market_data.parquet`
- **产业链前瞻口径**：取"未来第 N 天的 industry_chain_median"，不是复利累计。1 日窗口精确，3/5 日窗口是近似（产业链 median 不是可交易指数，没有 close 可算复合收益）
- **使用时点**：所有指标依赖当天收盘后数据，只能回答"收盘后看到今天状态，历史上次日怎么走"，不能用于盘中或开盘前
- **9 象限固定输出**：四象限 CSV 固定输出 9 行（3 beta × 3 alpha），未出现的象限 count=0 其余字段 None

## 新增文件

### `src/history_analysis/models.py` (~140行)

Frozen dataclasses：

```python
@dataclass(frozen=True)
class HistoryRow:
    date: str                                          # YYYYMMDD
    anchor_return: Optional[float]
    direct_peers_median: Optional[float]
    industry_chain_median: Optional[float]
    theme_pool_median: Optional[float]
    trading_watchlist_median: Optional[float]
    relative_strength_vs_direct: Optional[float]
    relative_strength_vs_industry_chain: Optional[float]
    relative_strength_vs_theme: Optional[float]
    direct_up_ratio: Optional[float]                   # 来自 direct_peers
    chain_up_ratio: Optional[float]                    # 可选，需快照补充
    amount_expansion_ratio: Optional[float]
    moneyflow_positive_ratio: Optional[float]
    strongest_group: str
    weakest_group: str
    industry_beta: str                                 # positive/neutral/negative
    anchor_alpha: str                                  # positive/neutral/negative
    risk_level: str                                    # low/medium/high
    signal_labels: str                                 # 逗号分隔
    signal_categories: str                             # 逗号分隔，去重
    data_quality_status: str                           # ok/partial/insufficient_data
    next_1d_return: Optional[float]                    # 锚定前瞻绝对收益
    next_3d_return: Optional[float]
    next_5d_return: Optional[float]
    next_1d_excess_vs_chain: Optional[float]           # 锚定前瞻 - 产业链前瞻
    next_3d_excess_vs_chain: Optional[float]
    next_5d_excess_vs_chain: Optional[float]

@dataclass(frozen=True)
class RollingMetrics:
    date: str
    excess_5d: Optional[float]                         # 5d 累计超额 (anchor - chain)
    excess_10d: Optional[float]
    outperform_streak: int                             # 正=跑赢，负=跑输
    beta_streak: int                                   # 正=beta 连续正，负=连续负
    theme_vs_core_streak: int                          # 正=theme>core，负=core>theme
    risk_high_streak: int                              # risk=high 连续天数

@dataclass(frozen=True)
class QuadrantStats:
    quadrant: str                                      # 如 "行业强+个股强"
    count: int
    avg_next_1d: Optional[float]
    avg_next_3d: Optional[float]
    avg_next_5d: Optional[float]
    avg_next_1d_excess: Optional[float]                # 相对产业链的前瞻超额
    win_rate_1d: Optional[float]
    avg_relative_strength: Optional[float]

@dataclass(frozen=True)
class ExtremeDivergence:
    date: str
    anchor_return: float
    industry_chain_median: float
    divergence: float                                  # anchor - chain
    industry_beta: str
    anchor_alpha: str
    risk_level: str
    signal_labels: str

@dataclass(frozen=True)
class EventPath:
    """极端背离事件的 T-5 到 T+5 路径"""
    event_date: str
    anchor_returns: dict[str, Optional[float]]         # T-5..T+5 → anchor return
    chain_medians: dict[str, Optional[float]]          # T-5..T+5 → chain median
    excesses: dict[str, Optional[float]]               # T-5..T+5 → relative strength

@dataclass(frozen=True)
class SignalLift:
    label: str
    appearance_count: int
    avg_next_1d: Optional[float]
    avg_next_3d: Optional[float]
    avg_next_5d: Optional[float]
    avg_next_1d_excess: Optional[float]
    win_rate_1d: Optional[float]
    baseline_avg_next_1d: Optional[float]              # 全样本基准
    baseline_win_rate_1d: Optional[float]
    lift_next_1d: Optional[float]                      # (signal_avg - baseline) / |baseline|
    lift_win_rate: Optional[float]                     # signal_win_rate - baseline_win_rate
    min_count_passed: bool                             # appearance_count >= min_count

@dataclass(frozen=True)
class StateTransition:
    from_state: str                                    # 如 "行业强+个股弱"
    to_state: str
    count: int
    probability: float                                 # count / from_state 总数
```

### `src/history_analysis/summary_builder.py` (~250行)

核心平铺表构建：

- `load_all_snapshots(output_root: Path) -> list[dict]` — 扫描日期目录，读 JSON，按日期排序
- `load_anchor_closes(market_data_path: Path, anchor_symbol: str) -> dict[str, float]` — 读 parquet，返回 {YYYYMMDD: close}
- `flatten_snapshot(snapshot: dict, anchor_closes: dict, chain_closes: dict, trading_dates: list[str], date_idx: int) -> HistoryRow` — 单条 JSON → HistoryRow
- `compute_forward_returns(date_idx: int, closes: list[float], windows: list[int]) -> dict[str, Optional[float]]` — 按交易日位置算前瞻收益
- `build_history_rows(output_root: Path, market_data_path: Path, anchor_symbol: str) -> list[HistoryRow]` — 主入口

前瞻收益计算：
- 绝对收益：`close[i+N]/close[i] - 1`
- 超额收益：`anchor_next_Nd_return - chain_next_Nd_return`
- chain 前瞻收益需要从 `group_rotation.group_medians` 取每日 chain_median 再按交易日位置 shift
- 末尾几天无法计算的设为 None

trading_watchlist_median 取值：`snapshot["group_rotation"]["group_medians"].get("trading_watchlist")`

### `src/history_analysis/forward_returns.py` (~150行)

前瞻收益计算独立模块：

- `build_trading_day_closes(parquet_path: Path, anchor_symbol: str) -> tuple[list[str], list[float]]` — 返回 (日期列表, close列表)，优先 normalized parquet
- `compute_forward_returns(idx: int, closes: list[float], windows: list[int]) -> dict[str, Optional[float]]` — 核心计算
- `compute_chain_forward_returns(rows: list[HistoryRow], date_index: dict[str, int], windows: list[int]) -> dict[str, dict[str, Optional[float]]]` — 产业链前瞻收益

### `src/history_analysis/rolling_metrics.py` (~200行)

- `compute_rolling_excess(rows, window)` — 累计超额
- `compute_outperform_streak(rows)` — 连续跑赢/跑输（正=跑赢，负=跑输）
- `compute_beta_streak(rows)` — beta 连续性（neutral 断裂）
- `compute_theme_vs_core_streak(rows)` — 主题池 > 核心池连续性
- `compute_risk_high_streak(rows)` — risk=high 连续天数
- `build_rolling_metrics(rows)` — 主入口

None 值断裂所有 streak，重置为 0。

### `src/history_analysis/quadrant_analyzer.py` (~150行)

- `classify_quadrant(industry_beta, anchor_alpha) -> str` — 9 种组合的中文标签
- `build_quadrant_stats(rows) -> list[QuadrantStats]` — 按象限分组统计

4 个"干净"象限为主，5 个含 neutral 的象限单独报告。每个象限同时统计绝对前瞻收益和相对产业链的前瞻超额。

### `src/history_analysis/divergence_analyzer.py` (~100行)

- `compute_divergence(row) -> Optional[float]` — anchor_return - industry_chain_median
- `find_extreme_divergences(rows, threshold=8.0) -> list[ExtremeDivergence]` — 筛选极端日期

### `src/history_analysis/event_study.py` (~150行)

- `build_event_path(event_date: str, rows: list[HistoryRow], date_index: dict[str, int], window: int = 5) -> EventPath` — 取 T-N 到 T+N 的路径
- `build_all_event_paths(divergences: list[ExtremeDivergence], rows: list[HistoryRow], window: int = 5) -> list[EventPath]`

输出每个极端背离日期的 anchor_return / chain_median / excess 的 T-5..T+5 路径，看背离后是修复、延续还是反转。

### `src/history_analysis/signal_analyzer.py` (~200行)

- `explode_signals(rows) -> list[tuple[str, int]]` — 展开 signal_labels
- `build_signal_lifts(rows, min_count: int = 5) -> list[SignalLift]` — 每个标签的胜率和 lift

胜率表必须带：`count`、`baseline_avg`、`baseline_win_rate`、`lift_next_1d`、`lift_win_rate`、`min_count_passed`。

lift 定义：
- `lift_next_1d = (signal_avg - baseline_avg) / abs(baseline_avg)` 如果 baseline != 0，否则直接用差值
- `lift_win_rate = signal_win_rate - baseline_win_rate`

min_count 低于阈值的标签仍输出，但 `min_count_passed = False`。

### `src/history_analysis/transition_analyzer.py` (~150行)

- `build_state_transitions(rows: list[HistoryRow]) -> list[StateTransition]` — 状态转移矩阵
- `build_transition_matrix(transitions: list[StateTransition]) -> dict[str, dict[str, float]]` — from_state → {to_state → probability}

核心问题：今天"行业强个股弱"，明天转成"行业强个股强"的概率是多少？是修复还是恶化？

### `src/history_analysis/orchestrator.py` (~80行)

- `build_history_analysis(output_root: Path, market_data_path: Path, anchor_symbol: str, divergence_threshold: float = 8.0, signal_min_count: int = 5) -> dict` — 编排全部分析阶段，返回各分析结果

### `src/output/history_csv_writer.py` (~250行)

CSV 写入归 Output 层：

- `write_history_csv` → `data/output/history_summary.csv`
- `write_rolling_csv` → `data/output/history_rolling_metrics.csv`
- `write_quadrant_csv` → `data/output/history_quadrant_stats.csv`
- `write_divergence_csv` → `data/output/history_extreme_divergences.csv`
- `write_event_study_csv` → `data/output/history_event_study.csv`
- `write_signal_lift_csv` → `data/output/history_signal_lift.csv`
- `write_transition_csv` → `data/output/history_state_transitions.csv`

使用 `csv.DictWriter`，输出到 `data/output/` 根目录。

### `scripts/build_history_analysis.py` (~80行)

CLI 入口：

```bash
uv run python scripts/build_history_analysis.py
uv run python scripts/build_history_analysis.py --divergence-threshold 6.0 --signal-min-count 3
```

### `tests/test_history_analysis.py` (~600行)

合成 5-10 条 HistoryRow 覆盖：正常日、None 字段日、末尾日（无前瞻收益）、极端背离日、多标签日、risk=high 日。

前瞻收益测试：已知 close 序列 [100, 102, 101, 105, 103]，验证 `next_1d_return`、`next_3d_return`、`next_5d_return` 和 `next_Nd_excess_vs_chain`。

## 修改文件

- `src/output/json_writer.py` — 补充 `chain_up_ratio` 到 `industry_state`（从 `PoolState` 的 `industry_chain.up_ratio` 取值）
- `src/output/__init__.py` — 添加 `history_csv_writer` 引用
- `CLAUDE.md` — 添加历史分析命令文档

## 数据流

```
data/output/{YYYYMMDD}/industry_snapshot.json (96个)
    + data/price/normalized/market_data_normalized.parquet (锚定 close)
      [fallback: data/price/raw/market_data.parquet]
    │
    ▼
summary_builder.build_history_rows()
    │
    ├─→ history_csv_writer → history_summary.csv
    ├─→ rolling_metrics    → history_rolling_metrics.csv
    ├─→ quadrant_analyzer  → history_quadrant_stats.csv
    ├─→ divergence_analyzer + event_study
    │       → history_extreme_divergences.csv
    │       → history_event_study.csv
    ├─→ signal_analyzer    → history_signal_lift.csv
    └─→ transition_analyzer → history_state_transitions.csv
```

## 执行顺序

| 阶段 | 内容 | 依赖 | 可并行 |
|------|------|------|--------|
| P1 | models.py + summary_builder.py + forward_returns.py + history_csv_writer(write_history_csv) + CLI + 测试 | 无 | — |
| P2 | rolling_metrics.py + csv_writer 扩展 + 测试 | P1 | — |
| P3 | quadrant_analyzer.py + csv_writer 扩展 + 测试 | P1 | 可与 P4/P5 并行 |
| P4 | divergence_analyzer.py + event_study.py + csv_writer 扩展 + 测试 | P1 | 可与 P3/P5 并行 |
| P5 | signal_analyzer.py + csv_writer 扩展 + 测试 | P1 | 可与 P3/P4 并行 |
| P6 | transition_analyzer.py + csv_writer 扩展 + 测试 | P1 | 可与 P3/P4/P5 并行 |
| P7 | orchestrator.py + json_writer 补充 chain_up_ratio + 更新 CLAUDE.md + 端到端验证 | P1-P6 | — |

## 验证

1. `uv run python scripts/build_history_analysis.py` 生成 7 个 CSV
2. `history_summary.csv` 行数等于 `data/output/` 下日期目录数（当前 96）
3. 极端背离表包含已知日期：2026-04-20、2026-01-05、2025-12-18、2026-01-12
4. 事件研究表每个极端日期有 T-5 到 T+5 的路径
5. 象限统计表"行业强个股弱"天数和次日收益以脚本实际计算为准
6. 信号 lift 表带 `min_count_passed` 标记
7. 状态转移表行列均为 9 种象限组合
8. `pytest tests/test_history_analysis.py --cov=src/history_analysis` 覆盖率 ≥ 80%
