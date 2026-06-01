# 分析逻辑审计报告

> 审计对象：`docs/excess_backtest/analysis_logic.md`
>
> 审计结论：当前分析方案已经从“交易推荐”校准为“网格画像”，方向正确；但若要交给代码实现，还需要补齐若干关键定义，尤其是 spread 时间序列、置信度规则、路径标签与方向绑定。

## 一、总体结论

新版 `analysis_logic.md` 已经解决了旧版的核心问题：它不再把单档 Oracle 均值当作交易推荐依据，而是把目标明确改成：

- 判断指标是否有预测力
- 观察做多/做空空间是否随档位变化
- 给冷端、热端和中间档建立画像
- 用路径与置信度辅助解释

这与当前第一阶段目标一致：**先做网格画像，不做实盘策略推荐**。

但目前文档仍有几处规格不够明确。它适合作为 v2 方案骨架，但还不是完全 decision-complete 的实现说明。

## 二、做得对的地方

### 1. 目标口径正确

文档明确写道：

```text
不是给交易推荐，是给每个网格画一张像。
```

这是关键校准。它避免把 Oracle 20 日最高/最低误解释成可执行收益。

### 2. 核心从单档绝对值转向跨档趋势

文档强调：

```text
关键指标是跨档的趋势（spread），不是单档的绝对值。
```

这是正确方向。对于当前 Oracle 数据，单档绝对空间会被系统性抬高，而冷端与热端之间的相对差异更接近信号本身。

### 3. 指标身份更准确

文档已将“收益”改为“空间”，并区分：

- `upside`
- `adverse`
- `upsideAdverseRatio`
- `upsidePositiveRate`

这比旧版 `profit/loss/winRate` 更贴合网格画像目标。

### 4. 移除不合适指标

文档明确不再使用：

- Sortino
- pnlRatio
- winRate
- kurtosis

这是合理的。Oracle 空间层不适合用 Sortino，`upsideAdverseRatio` 也比传统盈亏比语义更清楚。

### 5. `10_最热` 的反直觉问题已被框架修正

新版报告格式中，`10_最热` 不再被简单写成“做多”，而是通过：

- 做多空间
- 做空空间
- 空/多比
- 空间风险比
- 路径
- 偏向

综合描述为“偏空”或“多空拉扯偏空”。这比旧版推荐标签更合理。

## 三、仍需修正的问题

### 1. Oracle spread 的有效性表述过强

文档写道：

```text
绝对值不可信，但跨档的相对差异仍然有效。
因为 Oracle 偏差对所有档位方向相同、量级接近，所以档位之间的差值（spread）受影响很小。
```

这个判断方向上可以接受，但表述过强。

问题在于：Oracle 偏差未必对所有档位量级接近。高波动档位天然更容易在 20 天内出现更高高点或更低低点，因此 Oracle 空间可能混入“波动率差异”，不只是方向信号。

建议改成：

```text
绝对值不能解释为可实现收益；跨档 spread 比单档绝对值更适合做画像，但仍可能受到不同档位波动率差异影响。第二阶段需用固定持有期收益验证。
```

### 2. `spread_series` 没有定义清楚

文档提出 Newey-West：

```text
模型 = OLS(spread_series ~ 1), cov_type='HAC', maxlags=19
```

但没有定义 `spread_series` 如何构造。

这会导致实现分叉。至少有三种可能：

1. 每个交易日构造冷端组合收益与热端组合收益之差。
2. 将冷端触发日和热端触发日各自组成事件序列，再按日期对齐后相减。
3. 直接对冷端样本和热端样本做均值差检验。

建议在文档中指定第一版实现：

```text
v2 暂不实现 Newey-West；先输出 cold_hot_spread 描述值和 Spearman rho。
```

或者明确：

```text
spread_series 以交易日为索引。若当日属于冷端，则取该日空间；若属于热端，则取负的该日空间；其他档位为空。对该序列均值做 HAC t-test。
```

二选一，不应留空。

### 3. `bias` 阈值需要标注为启发式规则

当前规则：

```text
if shortCompetitiveness < 0.4:
    bias = "偏多"
elif shortCompetitiveness > 0.7:
    bias = "偏空"
else:
    bias = "多空拉扯"
```

这个规则直观，但阈值 0.4 / 0.7 没有统计来源。

建议标注为：

```text
v2 heuristic，后续根据样本外结果校准。
```

同时建议扩展标签，避免把临界热端粗暴判成“偏空”：

| shortCompetitiveness | 建议标签 |
| --- | --- |
| < 0.4 | 偏多 |
| 0.4-0.7 | 多空拉扯 |
| 0.7-0.9 | 多空拉扯偏空 |
| > 0.9 | 偏空 |

这样 `10_最热` 这类做空竞争力高、但多头尾部空间仍在的档位，表达会更准确。

### 4. 路径标签必须绑定方向

`favorableFirstRate` 有两个版本：

- 做多：`peak_day < trough_day`
- 做空：`trough_day < peak_day`

综合画像不能只写一个“先有利”。它必须跟 bias 绑定：

```text
if bias 偏多:
    pathTag 使用 long_favorable_first_rate
elif bias 偏空:
    pathTag 使用 short_favorable_first_rate
else:
    同时展示 long_path_tag 和 short_path_tag
```

否则会出现“偏空但使用做多路径”或“多空拉扯但只看一边路径”的误读。

### 5. confidence 规则还不够可实现

文档写：

```text
if 样本量 >= 20 且 单调性显著:
    confidence = "高"
elif 样本量 >= 10:
    confidence = "中"
else:
    confidence = "低"
```

但“单调性显著”没有定义。

建议改为明确规则：

```text
monotonicStrong = abs(spearman_rho) >= 0.7
spreadStrong = abs(cold_hot_spread_pct) >= 20%

if n >= 20 and monotonicStrong and spreadStrong:
    confidence = "高"
elif n >= 10 and (monotonicStrong or spreadStrong):
    confidence = "中"
else:
    confidence = "低"
```

如果后续实现 Newey-West，再加入：

```text
spreadSignificant = abs(nw_tstat) >= 2
```

### 6. 月度分布粒度需要更明确

文档写：

```text
按月度（YYYYMM）统计每个指标下所有触发日的做多/做空空间均值。
```

如果“所有触发日”把 1-10 档混在一起，会看不出网格效果。

建议至少输出：

```text
indicator × month × side(cold/mid/hot)
```

其中：

- cold = 档位 1-3
- mid = 档位 4-7
- hot = 档位 8-10

更完整则输出：

```text
indicator × month × grade
```

### 7. `upsidePositiveRate` 在 Oracle 层区分度有限

因为 20 日窗口内最高价/最低价极容易产生正空间，`upsidePositiveRate` 往往接近 1。

建议保留但降权，不作为主判断指标。主判断应优先使用：

- `upsideMean`
- `upsideMedian`
- `adverseMean`
- `upsideAdverseRatio`
- `shortCompetitiveness`
- `favorableFirstRate`
- `cold_hot_spread`
- `spearman_rho`

## 四、建议补充到文档的实现定义

### 1. 极端档定义

```text
cold = grades 1-3
mid = grades 4-7
hot = grades 8-10
```

### 2. Spread 定义

```text
long_cold_hot_spread = mean(long_upside_20d | cold) - mean(long_upside_20d | hot)
short_hot_cold_spread = mean(short_upside_20d | hot) - mean(short_upside_20d | cold)
```

可同时输出百分比变化：

```text
long_spread_pct = long_cold_hot_spread / mean(long_upside_20d | cold)
short_spread_pct = short_hot_cold_spread / mean(short_upside_20d | cold)
```

### 3. 单调性定义

```text
long_rho = spearmanr(grade, long_upside_mean_by_grade)
short_rho = spearmanr(grade, short_upside_mean_by_grade)
```

解释：

- `long_rho < 0`：越冷，做多空间越大。
- `short_rho > 0`：越热，做空空间越大。

### 4. Bias 定义

建议 v2 使用四档：

```text
if shortCompetitiveness < 0.4:
    bias = "偏多"
elif shortCompetitiveness < 0.7:
    bias = "多空拉扯"
elif shortCompetitiveness < 0.9:
    bias = "多空拉扯偏空"
else:
    bias = "偏空"
```

并保留趋势修正：

```text
如果当前指标 short_rho > 0.7 且档位 >= 8，则 bias 至少为 "多空拉扯偏空"。
如果当前指标 long_rho < -0.7 且档位 <= 3，则 bias 至少为 "偏多"。
```

### 5. Path Tag 定义

```text
if rate > 0.6:
    pathTag = "先有利"
elif rate >= 0.4:
    pathTag = "路径拉锯"
else:
    pathTag = "先不利"
```

方向选择：

```text
bias 偏多 → 使用 long path
bias 偏空 / 多空拉扯偏空 → 使用 short path
bias 多空拉扯 → 同时展示 longPathTag 和 shortPathTag
```

### 6. Confidence 定义

第一版建议不强行实现 Newey-West，先用可稳定实现的描述性置信度：

```text
grade_n_ok = n_triggers >= 20
trend_ok = abs(relevant_rho) >= 0.7
spread_ok = abs(relevant_spread_pct) >= 0.2

if grade_n_ok and trend_ok and spread_ok:
    confidence = "高"
elif n_triggers >= 10 and (trend_ok or spread_ok):
    confidence = "中"
else:
    confidence = "低"
```

其中：

- 偏多档使用 `long_rho` 和 `long_spread_pct`
- 偏空档使用 `short_rho` 和 `short_spread_pct`
- 多空拉扯同时参考两侧

## 五、最终判断

新版 `analysis_logic.md` 已经完成最重要的方向修正：

- 不再以单档 Oracle 均值直接给交易推荐
- 改为用跨档趋势判断指标预测力
- 用空间、风险、路径、置信度给网格画像

但它还需要补齐实现细节：

1. spread 与 spread_series 的准确定义
2. bias 阈值的分层和说明
3. pathTag 与 bias 的绑定关系
4. confidence 的可执行规则
5. 月度分布的分组粒度
6. Oracle spread 仍需固定持有期验证的免责声明

补齐这些之后，这份文档就可以作为 `excess_grid_profile.py` v2 重构的实现规格。
