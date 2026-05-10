# /history 历史性格档案改造计划

## 目标定义

把 `/history` 从"历史统计 + 今日判断混合工作台"改造成一份**锚定个股的历史性格档案**。只描述过去，不判断今天。

- **产品结构**：顶部档案摘要 → 横排关键指标 → 左右两列主体 → 底部完整统计明细入口
- **呈现目标**：`docs/assets/history-personality-profile-mockup.png` 的结构、密度和阅读路径
- **视觉皮肤**：当前 Web 暗色 `anchor-*` token，保持全站一致

---

## 阶段一：后端数据模型扩展

**目标**：在 `HistoryPersonalityProfile` 中新增 `summary_metrics` 字段，定义数据模型。

**修改文件**：
- `src/history_analysis/models.py`

**具体步骤**：

1. 新增 `PersonalitySummaryMetrics` dataclass：
   ```python
   @dataclass(frozen=True)
   class PersonalitySummaryMetrics:
       baseline_win_rate_1d: float | None
       median_excess_3d: float | None
       median_adverse_3d_proxy: float | None
       payoff_ratio: float | None
       sharpe_like_ratio: float | None
       signal_coverage_ratio: float | None
   ```

2. 在 `HistoryPersonalityProfile` 中新增字段：
   ```python
   summary_metrics: PersonalitySummaryMetrics
   ```

**验收**：
- `models.py` 能导入，无语法错误
- `PersonalitySummaryMetrics` 和 `HistoryPersonalityProfile` 定义完整

---

## 阶段二：后端 PersonalitySummaryMetrics 计算实现

**目标**：实现 6 个指标的计算逻辑。

**修改文件**：
- `src/history_analysis/personality_profile.py`

**具体步骤**：

1. 新增 `_build_summary_metrics(rows: list[HistoryRow]) -> PersonalitySummaryMetrics` 函数

2. 逐个实现 6 个指标：
   - `baseline_win_rate_1d`：valid rows 中 `next_1d_return > 0` 的比例
   - `median_excess_3d`：`next_3d_excess_vs_chain` 中位数
   - `median_adverse_3d_proxy`：负向 `next_3d_return` 的中位数；负样本为空返回 `None`
   - `payoff_ratio`：正收益平均 / |负收益平均|；无负样本返回 `None`
   - `sharpe_like_ratio`：平均日收益 / 日收益标准差 × √252；标准差为 0 返回 `None`
   - `signal_coverage_ratio`：`signal_labels` 非空非 `"[]"` 的天数 / valid rows 总数

3. 在 `build_personality_profile` 中调用 `_build_summary_metrics`，赋值给返回的 `HistoryPersonalityProfile`

**验收**：
- 运行 `python -c "from src.history_analysis.personality_profile import _build_summary_metrics; print('OK')"` 无报错

---

## 阶段三：后端 RelationshipProfile 字段映射修复 + 完整实现

**目标**：修复 4 个池子读同一字段的 bug，补全 corr/修复率/延续率计算，relation 分类用明确阈值。

**修改文件**：
- `src/history_analysis/personality_profile.py`

**具体步骤**：

1. 修改 `_build_simple_relationship_pattern` 签名，增加 `rs_field: str` 参数

2. 循环中取 `rs = getattr(r, rs_field, None)`，替代硬编码的 `r.relative_strength_vs_industry_chain`

3. 新增 corr 计算（需要 pool median 字段）：
   - `same_day_corr`：anchor_return 与 pool median 的皮尔逊相关系数
   - `anchor_leads_corr`：anchor_return(t) 与 pool median(t+1)
   - `anchor_lags_corr`：anchor_return(t) 与 pool median(t-1)

4. 新增修复率/延续率计算：
   - `repair_after_underperform_ratio`：rs < 0 后 3 日内 rs > 0 的比例
   - `continuation_after_outperform_ratio`：rs > 0 后 3 日内 rs > 0 的比例

5. 按阈值规则判定 `relation`（见 2.2 节阈值表）

6. `evidence` 改为可读中文短句，包含 relation、avg_rs、修复率信息

7. `_build_relationship_profile` 中 4 次调用分别传：
   - chain → `relative_strength_vs_industry_chain`, pool=`industry_chain_median`
   - theme → `relative_strength_vs_theme`, pool=`theme_pool_median`
   - core → `relative_strength_vs_direct`, pool=`direct_peers_median`
   - trading → 计算 `anchor_return - trading_watchlist_median`, pool=`trading_watchlist_median`

**验收**：
- 运行脚本生成 JSON，检查 4 池子 `avg_relative_strength` 不全部相同
- `same_day_corr` 非 null
- `evidence` 是可读中文短句

---

## 阶段四：后端 PathPattern 多事件类型实现

**目标**：修复全 null 问题，支持多事件类型，路径为累计收益。

**修改文件**：
- `src/history_analysis/personality_profile.py`
- `src/history_analysis/orchestrator.py`

**具体步骤**：

1. `build_personality_profile` 签名增加：
   ```python
   extreme_divergences: list[ExtremeDivergence]
   event_paths: list[EventPath]
   ```

2. `orchestrator.py` 第 117 行调用处传入 `extreme_divergences` 和 `event_paths`

3. 重写 `_build_path_patterns`：
   - 接收 `rows`、`extreme_divergences`、`event_paths`
   - 从 `extreme_divergences` 筛正/负背离日期
   - 从 `rows` 筛放量上涨/下跌/资金价格背离日期
   - 对每类事件日期，用 `rows` 构建 T-5~T+5 路径（复用 `build_event_paths` 逻辑）
   - 对每个事件，以 T0 为基准计算累计收益路径
   - 按 offset 求平均 `anchor_return`、`chain_median`、`excess`
   - 生成多条 `PathPattern`，`event_label` 和 `summary` 为中文

**验收**：
- 生成 JSON 后，`path_patterns` 至少 3 类事件
- 每类至少 8 个有效点（非 null）
- `summary` 是可读中文结论

---

## 阶段五：后端 JSON 输出兼容

**目标**：确保新增字段正确写入 JSON。

**修改文件**：
- `src/output/history_csv_writer.py`（验证是否需要修改）

**具体步骤**：

1. 检查 `write_personality_profile_json` 是否通过 dataclass 字段自动序列化
2. 如需要，确认 `PersonalitySummaryMetrics` 被正确包含在 `HistoryPersonalityProfile` 的序列化中

**验收**：
- 运行 `uv run python scripts/build_history_analysis.py`
- 检查 `data/output/history_personality_profile.json` 包含 `summary_metrics`、`relationship_profile`（4 池子不同）、`path_patterns`（非 null）

---

## 阶段六：前端 PersonalitySummaryCard 重写

**目标**：顶部横幅档案摘要，环形图 + headline + traits + 档案标签。

**修改文件**：
- `web/src/components/history/personality-summary-card.tsx`

**具体步骤**：

1. 移除 PieChart、图例、置信度进度条
2. 手写 SVG donut 环形图：
   - 用 `<svg>` + `<circle>` 画环形，innerRadius 中心放性格类型文字
   - 颜色分段映射 likes/dislikes/counter_intuitive/trap 比例
3. 右侧布局：headline + traits 胶囊标签行
4. 右上档案标签区：样本天数、置信度、基线胜率大数字
5. 新增 props：`baselineWinRate`（来自 `summary_metrics.baseline_win_rate_1d`）

**验收**：
- 环形图中心显示性格类型（如「产业链跟随型」）
- traits 标签正常渲染
- 档案标签区显示样本/置信度/胜率

---

## 阶段七：前端 MetricsBar 新增

**目标**：横排 6 个关键指标，紧凑展示。

**新增文件**：
- `web/src/components/history/metrics-bar.tsx`

**具体步骤**：

1. 定义 props 接口，接收 `summary_metrics` 和 `sampleDays`
2. 6 个指标横向排列，每个：标签 + 大数字 + 单位
   - 胜率 → `baseline_win_rate_1d` × 100 + "%"
   - T+3 超额 → `median_excess_3d` + "pp"
   - T+3 不利回报 → `median_adverse_3d_proxy` + "pp"
   - 盈亏比 → `payoff_ratio` + "x"
   - 夏普 → `sharpe_like_ratio`
   - 信号覆盖 → `signal_coverage_ratio` × 100 + "%"
3. 负值用绿色，正值用红色（A股惯例）
4. 无卡片背景，用细边框或分隔线分割

**验收**：
- 6 个指标横排可见
- 数字格式化正确
- 颜色按正负正确显示

---

## 阶段八：前端 HabitPatternList 重写

**目标**：卡片堆叠 → 紧凑行式表格，加星级和迷你方向条。

**修改文件**：
- `web/src/components/history/habit-pattern-list.tsx`

**具体步骤**：

1. 从卡片堆叠改为 `div` 行式布局（类似 table row）
2. 每行元素：
   - 左侧彩色竖线（likes=红、dislikes=绿、counter_intuitive=紫、trap=橙）
   - 标签名
   - significance badge（strong→「强」、suggestive→「提示」、weak→「弱」）
   - `n=xx`
   - 次日收益（正负色）
   - 星级：strong=5星、suggestive=3-4星、weak=1-2星
   - 迷你方向条：宽度按 `|avg_next_1d| / 10` 比例（封顶），正红负绿
3. 悬停/点击展开：超额、胜率、3日/5日均值、最佳象限
4. 移除 CombinedHabitPatternCard 和 CombinedSignalPatternCard 的卡片外壳，改为直接在 dashboard 中按区域渲染

**验收**：
- 行式布局，不是卡片
- 星级和方向条正常显示
- 悬停展开显示详细信息

---

## 阶段九：前端 RelationshipProfilePanel 重写

**目标**：4 张独立卡片 → 紧凑行式列表。

**修改文件**：
- `web/src/components/history/relationship-profile-panel.tsx`

**具体步骤**：

1. 移除外层 section 卡片背景
2. 4 个池子改为 4 个紧凑 div 行
3. 每行：池名（text-xs font-medium）+ relation 胶囊标签 + avg_relative_strength 数字 + same_day_corr 数字
4. relation 标签颜色：follows=蓝、leads=紫、lags=黄、mean_reverts=绿、diverges=橙、unstable=灰
5. 展开/悬停显示 `evidence` 可读描述

**验收**：
- 4 行紧凑展示
- relation 标签颜色正确
- evidence 中文描述可读

---

## 阶段十：前端 PathPatternPanel 修改

**目标**：接入真实路径数据，多条路径用标签切换。

**修改文件**：
- `web/src/components/history/path-pattern-panel.tsx`

**具体步骤**：

1. 接入真实 `path_patterns` 数据（不再全 null）
2. 多条路径用横向标签切换展示
3. 每条路径下方显示 `summary` 可读结论
4. LineChart 保持 Recharts，tooltip 明确标注"累计收益"
5. 空数据降级显示提示

**验收**：
- 折线图显示真实数据
- 标签切换正常
- summary 结论可读

---

## 阶段十一：前端 history-dashboard.tsx 布局重写

**目标**：2×2 卡片网格 → 档案式布局。

**修改文件**：
- `web/src/components/history/history-dashboard.tsx`

**具体步骤**：

1. 主标题从「历史分析」改为「历史性格档案」
2. 筛选器弱化/下沉（可以保留但不做第一视觉主角）
3. 整体布局改为：
   ```
   [全宽] PersonalitySummaryCard
   [全宽] MetricsBar
   [左右两列] grid grid-cols-1 xl:grid-cols-2 gap-4
     ├── 左列
     │   ├── HabitPatternList likes
     │   ├── HabitPatternList dislikes
     │   └── RelationshipProfilePanel
     └── 右列
         ├── HabitPatternList counter_intuitive
         ├── HabitPatternList trap
         └── PathPatternPanel
   [全宽] 折叠区 —— 完整统计明细 / 今日判断数据源
   ```
4. 今日判断组件（operator-decision-panel、operator-playbook-panel、today-history-mapping-panel 等）移入底部折叠区
5. likes/dislikes/counter_intuitive/trap 不再用 CombinedHabitPatternCard 卡片外壳包裹

**验收**：
- 顶部摘要是第一视觉主角
- 横排指标可见
- 左右两列布局
- 今日判断不在主叙事区

---

## 阶段十二：前端类型定义更新

**目标**：TypeScript 类型与后端新增字段对齐。

**修改文件**：
- `web/src/types/index.ts`

**具体步骤**：

1. 新增 `PersonalitySummaryMetrics` 接口
2. `HistoryPersonalityProfile` 接口新增 `summary_metrics` 字段
3. 如有 PathPattern 字段名变更（如改为 cum_return），同步更新

**验收**：
- `npm run type-check` 或 `npx tsc --noEmit` 无类型错误

---

## 阶段十三：联调与验证

**目标**：前后端联调，确认数据流正确，页面呈现符合目标。

**步骤**：

1. 后端：`uv run python scripts/build_history_analysis.py`
2. 检查 JSON：
   - `summary_metrics` 字段存在，可计算字段非 null
   - 4 池子 `avg_relative_strength` / corr / evidence 不全部重复
   - `path_patterns` 至少 3 类事件，路径点非 null
3. 前端：`cd web && npm run dev`
4. 访问 `/history` 验证：
   - 第一屏主标题为「历史性格档案」
   - 顶部档案摘要横幅感
   - 横排 6 指标可见
   - 左右两列，表格行式
   - 产业联动和路径画像有真实数据
   - 暗色主题，密度高
   - 今日判断在底部折叠区

---

## 文件总清单

| 阶段 | 文件 | 操作 |
|------|------|------|
| 一 | `src/history_analysis/models.py` | 新增 `PersonalitySummaryMetrics`，修改 `HistoryPersonalityProfile` |
| 二~四 | `src/history_analysis/personality_profile.py` | 新增 `_build_summary_metrics`，修复 `_build_simple_relationship_pattern`，重写 `_build_path_patterns`，修改 `build_personality_profile` 签名 |
| 四 | `src/history_analysis/orchestrator.py` | 修改 `build_personality_profile` 调用，传入新参数 |
| 五 | `src/output/history_csv_writer.py` | 验证序列化兼容性 |
| 六 | `web/src/components/history/personality-summary-card.tsx` | 重写 |
| 七 | `web/src/components/history/metrics-bar.tsx` | 新增 |
| 八 | `web/src/components/history/habit-pattern-list.tsx` | 重写 |
| 九 | `web/src/components/history/relationship-profile-panel.tsx` | 重写 |
| 十 | `web/src/components/history/path-pattern-panel.tsx` | 修改 |
| 十一 | `web/src/components/history/history-dashboard.tsx` | 重写布局 |
| 十二 | `web/src/types/index.ts` | 新增/修改类型定义 |
