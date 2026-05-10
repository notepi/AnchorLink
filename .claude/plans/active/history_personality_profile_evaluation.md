# 历史性格画像前端复刻：数据评估与实施方案

## Context

用户要求根据 `docs/assets/history-personality-profile-mockup.png` 复刻档案式历史性格画像页面。当前实现（`personality-summary-card.tsx` + `habit-pattern-list.tsx` + `relationship-profile-panel.tsx` + `path-pattern-panel.tsx`）是2x2卡片网格布局，与mockup的三列紧凑档案式设计差距很大。

## 数据支撑评估

### 数据已存在（无需新增后端）

| 元素 | 数据来源 | 状态 |
|------|---------|------|
| 头部性格摘要 | `personality_summary` | 完整 |
| 喜欢/讨厌/反直觉/陷阱列表 | `habit_patterns` + `counter_intuitive_patterns` + `trap_patterns` | 完整 |
| 路径折线图 | `history_event_study.csv` 已有 T-5~T+5 数据 | **有数据但未聚合** |

### 数据有Bug（需修复）

| 元素 | 问题 | 修复方式 |
|------|------|---------|
| 产业联动4个池子 | `_build_relationship_profile` 中4个池子都读 `relative_strength_vs_industry_chain` | 改为各自读对应字段 |

### 数据不存在（用替代方案）

| Mockup 元素 | 缺口 | 替代方案 |
|------------|------|---------|
| 列表右侧迷你走势条 | 无逐日序列 | CSS方向条（正绿/负红） |
| 右侧面板胜率走势面积图 | 无滚动窗口时序 | 基线胜率大数字 |
| 右侧面板信号强弱分布 | 无分组聚合 | `effect_score` 静态分布条 |

## 实施计划

### 后端修改

#### 1. 修复 RelationshipProfile 字段映射

**文件**: `src/history_analysis/personality_profile.py`

修改 `_build_simple_relationship_pattern` 增加 `rs_field` 参数，`_build_relationship_profile` 改为：
- anchor_vs_chain → `relative_strength_vs_industry_chain`
- anchor_vs_theme → `relative_strength_vs_theme`
- anchor_vs_core → `relative_strength_vs_direct`
- anchor_vs_trading_watchlist → 通过 `trading_watchlist_median` 与 `anchor_return` 计算

#### 2. 重写 _build_path_patterns 聚合真实路径

**文件**: `src/history_analysis/personality_profile.py`

当前 `_build_path_patterns` 生成全null的placeholder。改为：
- 从已有 `event_paths` 数据（极端背离事件）聚合
- 按事件类型分：极强正向背离 / 极强负向背离 / 全量极端事件
- 每个类型计算各offset的平均 `anchor_return`, `chain_median`, `excess`
- 输出到 `path_patterns`

**需要修改 orchestrator 签名**: `build_personality_profile` 需要接收 `event_paths` 参数。

### 前端改造

#### 3. 重写 Dashboard 布局（三列档案式）

**文件**: `web/src/components/history/history-dashboard.tsx`

从 2x2 网格改为：
```
grid grid-cols-1 xl:grid-cols-12 gap-4
├── xl:col-span-5 (左列：喜欢 + 讨厌 + 产业联动)
├── xl:col-span-4 (中列：反直觉 + 陷阱 + 路径图)
└── xl:col-span-3 (右列：胜率数字 + 信号分布条)
```

#### 4. 重写 PersonalitySummaryCard（环形头部）

**文件**: `web/src/components/history/personality-summary-card.tsx`

- 左侧：SVG 环形图（中心显示性格类型，如"产业链跟随型"）
- 右侧：headline + traits标签 + 样本信息
- 右上：档案标签区（样本天数、置信度、胜率大数字）
- 移除饼图、置信度条

#### 5. 重写 HabitPatternList（紧凑行式 + 星级）

**文件**: `web/src/components/history/habit-pattern-list.tsx`

从卡片堆叠改为表格行式：
- 每行：彩色竖线 + 标签 + significance badge + n=xx + 次日收益 + 星级
- 星级规则：strong=5星, suggestive=3-4星, weak=1-2星
- 右侧迷你方向条：正收益=绿色短条，负收益=红色短条
- 悬停/展开显示超额、胜率、3日/5日均值

#### 6. 重写 RelationshipProfilePanel（紧凑展示）

**文件**: `web/src/components/history/relationship-profile-panel.tsx`

- 从4个独立卡片改为紧凑列表
- 每个池子一行：池名 + relation标签 + 相对强弱数字
- 更小的字号和间距

#### 7. 重写 PathPatternPanel

**文件**: `web/src/components/history/path-pattern-panel.tsx`

- 保持折线图（Recharts）
- 接入真实聚合路径数据
- 空数据时降级显示

#### 8. 新增右侧辅助组件

**文件**: 
- `web/src/components/history/personality-side-panel.tsx`
  - 大胜率数字（基线胜率）
  - 信号强弱分布条（用 habit_patterns 的 effect_score）

### 依赖与复用

- **Recharts**: 已有依赖，用于路径折线图
- **Tailwind anchor 主题**: 已有 `bg-anchor-bgSecondary`, `border-anchor-border` 等
- **数据读取**: `web/src/lib/data-reader.ts` 已有 `getHistoryPersonalityProfile()`

## 验证步骤

1. 后端修复后运行 `uv run python scripts/build_history_analysis.py`
2. 检查 `data/output/history_personality_profile.json`:
   - 4个池子的 `avg_relative_strength` 各不相同
   - `path_patterns` 包含非null的路径数据
3. 前端 `cd web && pnpm dev`
4. 访问 `/history` 验证三列布局、环形图、星级、紧凑列表
