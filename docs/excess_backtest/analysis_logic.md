# 分析逻辑

> 对应脚本：`scripts/excess_grid_profile.py`（v3: 中位数价格收益 + 四层指标）

## 一、目标

对每个超额指标，用**二维网格**画像：

- **Q 维度（位置）**：超额收益在历史百分位的哪个位置（冷/热）
- **G 维度（方向）**：超额收益在上升还是下降

对每个 Q×G 网格回答：

1. **做多空间多大？做空空间多大？**
2. **空间偏多还是偏空？常态表现为正还是为负？**
3. **路径是否友好？**
4. **结论有多可靠？**

参考：股东人数分析用 G（变化率）× Q（百分位）二维网格。

## 二、方法论基础

### 2.1 核心思路：Fama-French 分档法

本分析沿用 Fama-French 因子检验的标准方法：

1. 按信号值（超额收益）排序分档
2. 对每档计算前向收益的统计量
3. **关键指标是跨档的趋势（spread），不是单档的绝对值**

类比：Fama-French 的 HML 因子不是看"价值股能赚多少"，而是看"价值股比成长股多赚多少"。同理，我们要看的是"冷端比热端多赚多少"，而不是"某个档位能赚多少"。

### 2.2 Oracle 退出 vs 中位数价格收益

本分析使用两种度量方式，分别对应不同用途：

**Oracle 退出**（20天最高/最低价）：
- 含义：理论上的最大可行空间（MFE/MAE）
- 用途：空间层指标，描述"最好/最差能到哪"
- 局限：几乎所有触发日都有正空间，PF/VaR/WinRate 无区分度

**中位数价格收益**（20天收盘价的中位数）：
- 含义：未来 20 日收盘价中位数相对当日收盘的涨跌幅
- 用途：常态/风险层指标，描述典型价格水平
- 局限：该指标比 Oracle 上下沿更接近常态，但仍不是可交易退出收益
- 优势：有正有负，PF/VaR/WinRate 有真实区分度

**核心原则**：空间层用 Oracle，常态/风险层用中位数价格收益。两者互补。

### 2.3 重叠窗口问题

连续触发日的前向 20 天收益有 19 天重叠。250 个观察值的有效独立样本量约为 250/20 ≈ 12，t-stat 会被高估。

处理方式：用描述性置信度，不直接做假设检验。

## 三、四层指标架构

```
excess_grade_daily.csv
  │
  ├─ 1. 空间层（Oracle MFE/MAE/RR）──→ 理论边界
  │
  ├─ 2. 常态表现层（中位数价格收益/天数/留存率）──→ 典型价格表现
  │
  ├─ 3. 路径层（达峰/达谷天数）──→ 时序特征
  │
  ├─ 4. 风险层（WinRate/PF/VaR，基于中位数价格收益）──→ 稳定性
  │
  ├─ 5. 跨档趋势分析 ──→ Q 和 G 两个维度各自的 spread 和单调性
  │
  ├─ 6. 综合画像 ──→ 每格的空间偏向 + 常态表现 + 置信度 + 一句话
  │
  └─ 7. 输出
```

### 3.1 空间层

基于 Oracle 做多/做空空间（long_upside / short_upside），描述理论上界。

做多空间 = 20天内最高价相对收盘的涨幅
做空空间 = 20天内最低价相对收盘的跌幅取反

| 指标 | 计算 | 含义 |
|------|------|------|
| upsideMean | mean(空间序列) | 理论上行空间均值 |
| upsideMedian | median(空间序列) | 抗极值干扰 |
| adverseMean | mean(不利波动序列) | 理论不利空间均值 |
| upsideAdverseRatio | upsideMean / abs(adverseMean) | 空间风险比 |
| std | 标准差 | 空间波动 |
| p25 / p75 | 百分位 | 空间集中区间 |
| skew | 偏度 | 尾部方向 |
| maxUpside / maxAdverse | 极值 | 最极端情况 |

空间风险比的意义：
- 比值高 → 有利空间远大于不利空间 → 方向有利
- 比值接近 1 → 有利和不利空间差不多 → 多空拉扯
- 比值 < 1 → 不利空间大于有利 → 不宜做

### 3.2 常态表现层

基于中位数价格收益（fwd_20d_median_return），描述典型价格水平。

做多侧：中位数价格收益 = 20天内所有收盘价的中位数相对当日收盘的涨跌幅
做空侧：做空中位数价格收益 = -做多侧中位数价格收益

| 指标 | 计算 | 含义 |
|------|------|------|
| retMean | mean(中位数价格收益序列) | 典型价格表现均值 |
| retMedian | median(中位数价格收益序列) | 典型价格表现中位数 |
| retentionMean | mean(retention序列) | 利润留存率均值 |
| retentionMedian | median(retention序列) | 利润留存率中位数 |

留存率 = 中位数价格收益 / 最大收益（Oracle），截尾到 [-2, 2]，分母 < 1% 时置 None
- 留存率高（接近1）→ 持仓过程平稳，较少过山车
- 留存率低或为负 → 持仓过程中大幅回吐利润

**注意**：报告优先展示 `retentionMedian`（中位数），避免 `retentionMean` 被极端值拉偏。

### 3.3 路径层

衡量触发后持仓过程中的体验。

| 指标 | 做多 | 做空 |
|------|------|------|
| peakDayMedian | fwd_20d_peak_day 中位数 | fwd_20d_trough_day 中位数 |
| peakDayMean | fwd_20d_peak_day 均值 | fwd_20d_trough_day 均值 |
| medianDayMean | fwd_20d_median_day 均值 | fwd_20d_median_day 均值 |
| medianDayMedian | fwd_20d_median_day 中位数 | fwd_20d_median_day 中位数 |
| favorableFirstRate | peak_day < trough_day 的比例 | trough_day < peak_day 的比例 |

### 3.4 风险层

基于中位数价格收益计算，有真实区分度。

做多侧：直接用中位数价格收益序列
做空侧：用做空中位数价格收益序列（= -做多侧）

| 指标 | 计算 | 含义 |
|------|------|------|
| winRate | count(收益 > 0) / n | 中位数价格收益胜率 |
| profitFactor | sum(正收益) / abs(sum(负收益)), cap=9.9 | 盈利因子 |
| var95 | percentile(收益序列, 5%) | VaR_95：5%最差情况的损失 |

**重要**：PF/VaR/WinRate 基于中位数价格收益计算，不是 Oracle 空间。Oracle 空间几乎全为正，这三个指标无区分度。

## 四、跨档趋势分析

这是整个分析的核心。不看单格绝对值，看趋势。

### 4.1 分组定义

```
Q_cold = Q1-Q2（极冷、偏冷）
Q_mid  = Q3（中性）
Q_hot  = Q4-Q5（偏热、极热）

G_down = G1-G2（大降、小降）
G_stable = G3（稳定）
G_up  = G4-G5（小升、大升）
```

### 4.2 Q 维度 Spread

对每个指标，算冷端 vs 热端的差异（固定 G 或对全部 G 聚合）：

```
long_cold_hot_spread = mean(Q_cold 做多空间) - mean(Q_hot 做多空间)
short_hot_cold_spread = mean(Q_hot 做空空间) - mean(Q_cold 做空空间)
ret_q_spread = mean(Q_cold 中位数价格收益) - mean(Q_hot 中位数价格收益)
```

- long_cold_hot_spread > 0 → 冷端做多空间更大，信号偏多
- short_hot_cold_spread > 0 → 热端做空空间更大，信号偏空
- ret_q_spread > 0 → 冷端中位数价格收益更高
- 三者都 > 0 且显著 → Q 维度有预测力

百分比变化：

```
long_q_spread_pct = long_cold_hot_spread / mean(Q_cold 做多空间)
short_q_spread_pct = short_hot_cold_spread / mean(Q_cold 做空空间)
ret_q_spread_pct = ret_q_spread / abs(mean(Q_cold 中位数价格收益))
```

- spread_pct >= 0.2 → 趋势有经济意义
- spread_pct < 0.1 → 差异太小，噪音区间

### 4.3 G 维度 Spread

对每个指标，算下降 vs 上升的差异（固定 Q 或对全部 Q 聚合）：

```
long_down_up_spread = mean(G_down 做多空间) - mean(G_up 做多空间)
short_up_down_spread = mean(G_up 做空空间) - mean(G_down 做空空间)
ret_g_spread = mean(G_down 中位数价格收益) - mean(G_up 中位数价格收益)
```

### 4.4 做空竞争力比

对每个网格：

```
shortCompetitiveness = short_upside_mean / long_upside_mean
```

- 比值低 → 做多优势明显
- 比值高 → 做空竞争力强
- 这是判断每个网格空间偏向的核心指标

### 4.5 单调性检验

Spearman 秩相关，对 Q 和 G 两个维度各算：

```
q_rho = spearmanr([1,2,3,4,5], [各Q档做多空间均值])  # 固定G=G3
g_rho = spearmanr([1,2,3,4,5], [各G档做多空间均值])  # 固定Q=Q3
q_rho_ret = spearmanr([1,2,3,4,5], [各Q档中位数价格收益均值])  # 固定G=G3
g_rho_ret = spearmanr([1,2,3,4,5], [各G档中位数价格收益均值])  # 固定Q=Q3
```

- |rho| > 0.8 → 强单调趋势，信号可靠
- |rho| < 0.5 → 趋势不明显，信号弱

### 4.6 统计显著性

第一版用描述性置信度，不用 Newey-West（单标的样本量有限，HAC 估计不稳定）：

综合判断 spread 是否有意义：
- spread 方向符合预期
- spread_pct >= 0.2
- |rho| >= 0.7

三者全满足 → 趋势显著；满足部分 → 趋势存在但不强；都不满足 → 趋势不可靠。

## 五、路径画像

衡量触发后持仓过程中的体验。

### 路径标签

| favorableFirstRate | 标签 | 含义 |
|--------------------|------|------|
| > 60% | 先有利 | 大部分触发日先浮盈再回调 |
| 40%-60% | 路径拉锯 | 涨跌先后各半 |
| < 40% | 先不利 | 大部分触发日先浮亏再反转 |

## 六、综合画像

对每个网格输出四个维度的标签 + 一句话总结。

### 6.1 样本量门槛

| n | spaceBias | confidence | 说明 |
|---|-----------|------------|------|
| 0 | 无样本 | 无效 | 无触发样本，不生成画像 |
| < 5 | 样本不足 | 无效 | 样本太少，结论不可靠 |
| 5-9 | 正常生成 | 至少"低" | 样本有限，置信度受限 |
| >= 10 | 正常生成 | 按规则判断 | 正常流程 |

### 6.2 空间偏向标签（spaceBias）

基于做空竞争力比（Oracle 空间），描述理论空间关系，不是可执行交易建议。

```
if shortCompetitiveness < 0.4:
    spaceBias = "偏多"
elif shortCompetitiveness < 0.7:
    spaceBias = "多空拉扯"
elif shortCompetitiveness < 0.9:
    spaceBias = "多空拉扯偏空"
else:
    spaceBias = "偏空"
```

**趋势修正**（跨档趋势可提升 spaceBias 下限）：

```
if q_rho 表明热端偏空 且 q_grade >= 4: spaceBias 至少为 "多空拉扯偏空"
if q_rho 表明冷端偏多 且 q_grade <= 2: spaceBias 至少为 "偏多"
```

### 6.3 常态表现标签（normalPerformance）

基于中位数价格收益均值，描述典型价格水平。

```
if retMean > 1.0:
    normalPerformance = "正向"
elif retMean >= -1.0:
    normalPerformance = "中性"
else:
    normalPerformance = "负向"
```

阈值 1% 为启发式规则，后续可校准。

### 6.4 路径标签（pathTag）

按空间偏向选择展示哪一侧的路径：

- 偏多 → 用 long favorableFirstRate
- 偏空 / 多空拉扯偏空 → 用 short favorableFirstRate
- 多空拉扯 → 同时展示两侧

判定规则（见第五节）：

| favorableFirstRate | 标签 |
|--------------------|------|
| > 60% | 先有利 |
| 40%-60% | 路径拉锯 |
| < 40% | 先不利 |

### 6.5 置信度标签（confidence）

综合样本量、单调性、spread 幅度，基于中位数价格收益趋势：

```
grade_n_ok = n >= 20
trend_ok = abs(retRho) >= 0.7
spread_ok = abs(retSpreadPct) >= 0.2

if grade_n_ok and trend_ok and spread_ok:
    confidence = "高"
elif n >= 10 and (trend_ok or spread_ok):
    confidence = "中"
else:
    confidence = "低"

# 5 ≤ n < 10 时至少"低"
if n < 10:
    confidence = "低"
```

### 6.6 一句话总结（summary）

根据 spaceBias + normalPerformance + pathTag 组合生成。

## 七、月度分布

按月度（YYYYMM）统计每个指标下所有触发日的做多/做空空间均值 + 中位数价格收益均值。

用途：看信号是否有时效性——某些月信号强、某些月信号弱甚至反转。

## 八、Q×G 交互分析

Q 和 G 不是独立维度。每天同时有 Q 档和 G 档，两个维度有交互：G 方向在冷端和热端的效果可能不同。

### 8.1 条件趋势

**G 趋势随 Q 变化**：对每个 Q 档，分别计算 G 维度的 spread 和 Spearman rho。

```
for q in [1,2,3,4,5]:
    g_spread_within_q = mean(G_down & Q=q 做多空间) - mean(G_up & Q=q 做多空间)
    g_rho_within_q = spearmanr([1,2,3,4,5], [各G档做多空间均值 | Q=q])
    ret_spread_within_q = mean(G_down & Q=q 中位数价格收益) - mean(G_up & Q=q 中位数价格收益)
    ret_rho_within_q = spearmanr([1,2,3,4,5], [各G档中位数价格收益均值 | Q=q])
```

**Q 趋势随 G 变化**：对每个 G 档，分别计算 Q 维度的 spread 和 Spearman rho。

### 8.2 四象限分析

将 Q 和 G 各分为两端，形成 2×2 四象限：

```
Q_cold = Q1-Q2, Q_hot = Q4-Q5
G_down = G1-G2, G_up = G4-G5
```

| 象限 | 含义 |
|------|------|
| Q冷×G降 | 超额低且在恶化 — 双冷叠加 |
| Q冷×G升 | 超额低但在改善 — 位置冷+方向升 |
| Q热×G降 | 超额高但在恶化 — 位置热+方向降 |
| Q热×G升 | 超额高且在改善 — 双热叠加 |

每个象限统计：n、做多空间均值、做空空间均值、shortCompetitiveness、中位数价格收益均值。

### 8.3 交互效应

交互项衡量 Q 和 G 是否独立：

```
long_interaction = (Q_cold×G_down - Q_cold×G_up) - (Q_hot×G_down - Q_hot×G_up)
short_interaction = (Q_cold×G_down - Q_cold×G_up) - (Q_hot×G_down - Q_hot×G_up) [做空侧]
ret_interaction = (Q_cold×G_down - Q_cold×G_up) - (Q_hot×G_down - Q_hot×G_up) [中位数价格收益侧]
```

解读：
- 交互项 > 0 → G 方向在冷端效果更强（冷端更依赖方向信号）
- 交互项 < 0 → G 方向在热端效果更强
- 交互项 ≈ 0 → Q 和 G 接近独立

### 8.4 报告格式

在 Q/G 独立趋势之后、网格表格之前，输出：

```
**条件趋势**：
- Q1_极冷内 G 趋势：做多空间 G降→G升 +X%（ρ=...），做空空间 ...，中位数价格收益 ...（ρ=...）
- Q5_极热内 G 趋势：做多空间 G降→G升 +Y%（ρ=...），做空空间 ...，中位数价格收益 ...（ρ=...）
- G1_大降内 Q 趋势：做多空间 Q冷→Q热 +Z%（ρ=...），做空空间 ...，中位数价格收益 ...（ρ=...）
- G5_大升内 Q 趋势：做多空间 Q冷→Q热 +W%（ρ=...），做空空间 ...，中位数价格收益 ...（ρ=...）

**四象限**：
| 象限 | n | 做多空间 | 做空空间 | 空/多比 | 中位数价格收益 |
|------|---|---------|---------|--------|---------------|
| Q冷×G降 | ... | ... | ... | ... | ... |
| Q冷×G升 | ... | ... | ... | ... | ... |
| Q热×G降 | ... | ... | ... | ... | ... |
| Q热×G升 | ... | ... | ... | ... | ... |

**交互效应**：做多交互项=+X，做空交互项=+Y，中位数价格收益交互项=+Z → 结论
```

## 九、输出

| 文件 | 内容 |
|------|------|
| excess_grade_daily.csv | 每日数据（含中位数价格收益/天数/留存率） |
| excess_grade_summary.csv | 75 行（3 指标 × 5 Q × 5 G），含四层指标 + 路径 + 画像 |
| excess_grade_backtest.json | 结构化数据：网格画像 + 月度分布 + 跨档趋势 + 阈值 |
| excess_grade_backtest.md | 可读报告：Q/G 趋势结论 + 网格表格 + 画像标签 |

## 十、报告格式

```
## 10日超额

**Q维度趋势**：做多空间从冷端到热端变化 X%（...→...），做空空间变化 Y%。
**G维度趋势**：做多空间从下降到上升变化 Z%，做空空间变化 W%。
单调性 Q_ρ=..., G_ρ=...。

**中位数价格收益趋势**：Q维度 ...%（ρ=...），G维度 ...%（ρ=...）。

**条件趋势**：...

**四象限**：
| 象限 | n | 做多空间 | 做空空间 | 空/多比 | 中位数价格收益 |
|------|---|---------|---------|--------|---------------|
| Q冷×G降 | ... | ... | ... | ... | ... |
...

**交互效应**：...

### Q1_极冷

| G档 | n | 做多空间 | 做空空间 | 空/多比 | 空间风险比 | 中位数价格收益 | 胜率 | PF | VaR_95 | 留存率中位数 | 多头达峰 | 空头达谷 | 先有利 | 空间偏向 | 常态表现 | 置信度 | 说明 |
|-----|---|---------|---------|--------|-----------|---------------|------|-----|--------|-------------|---------|---------|--------|----------|----------|--------|------|
| G1_大降 | 12 | +23.60% | +7.02% | 0.30 | 3.4 | +5.2% | 58% | 1.8 | -8.3% | -0.3 | 10d | 12d | 19% | 偏多 | 正向 | 中 | ... |
```

v3 修正要点：
- "偏向"拆分为"空间偏向"（Oracle）和"常态表现"（中位数价格收益）
- 做空侧常态收益用 -median_return 重算，不再与做多侧相同
- "中位数退出收益"→"中位数价格收益"，不再宣称"真实可获得"
- 留存率展示中位数（retentionMedian），报告列名"留存率中位数"
- 留存率截尾 [-2, 2]，分母 < 1% 时置 None
