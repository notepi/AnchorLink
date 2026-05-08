# 信号指标设计文档

> 本文档说明 AnchorLink 信号体系的设计来源、判断逻辑和投研师使用方式

---

## 1. 设计理念

### 1.1 核心思想

AnchorLink 信号体系借鉴**量化因子投资**和**技术分析**的双重理念：

1. **因子投资视角**：用可量化的因子（Beta、Alpha、成交量）描述市场状态
2. **相对强度视角**：锚定标的不是孤立的，而是相对于池子（peer group）的位置
3. **证据驱动**：每个信号都有明确的数值支撑，而非主观判断

### 1.2 行业参考来源

| 信号类别 | 行业参考 | 来源 |
|---------|---------|------|
| **Beta类** | 行业指数Beta、相对强度指标 | 经典CAPM模型、Fama-French三因子 |
| **Alpha类** | 相对收益、排名分位 | 量化因子投资、相对强度排名策略 |
| **Volume类** | 量价关系、资金流向 | 技术分析（OBV、MFI）、Level-2资金分析 |
| **Rotation类** | 板块轮动、强弱切换 | 美林时钟、行业轮动策略 |
| **Abnormal类** | 异常联动、背离预警 | 统计套利、配对交易逻辑 |

---

## 2. Beta类信号（行业环境）

### 2.1 设计来源

**Beta概念来自CAPM模型**：
```
Beta = 股票收益相对市场收益的敏感度

行业Beta = 锚定标的所属行业整体走势强度
```

行业实践中，基金经理常用**行业指数涨跌幅**判断行业环境：

| 涨跌幅度 | 强度判断 | 应用场景 |
|---------|---------|----------|
| ±0.5%以内 | 震荡/无明显方向 | 日内波动，趋势不明 |
| ±0.5%-1% | 温和强度 | 短期趋势初现 |
| ±1%-2% | 中等强度 | 明确的行业趋势信号 |

**来源依据**：
- [Sector Rotation Strategies - ETFdb](https://etfdb.com/etfs/investment-style/)
- [Fidelity Sector Rotation Guide](https://www.fidelity.com/learning-center/trading-investing/sectors)

**AnchorLink采用±0.5%阈值**，原因：
- A股日均波动约1%，0.5%是"明显涨跌"的下限
- 超过此值视为有方向性，而非随机波动

**AnchorLink的替代方案**：
- 不使用外部行业指数（如申万行业指数）
- 使用**内部池子中位数**作为行业基准
- 优势：更贴合锚定标的的实际对标股票

### 2.2 判断逻辑

| 信号 | 判断条件 | 阈值依据 |
|------|---------|---------|
| **行业Beta为正** | 池子中位数涨跌幅 > 0.5% | 0.5%是A股日均波动的典型值，超过此值视为"明显上涨" |
| **行业Beta为负** | 池子中位数涨跌幅 < -0.5% | 同上，负方向 |
| **行业扩散增强** | 池子中上涨股票比例 > 70% | 70%是"普涨"的标准阈值，超过视为趋势扩散 |
| **行业扩散不足** | 池子中上涨股票比例 < 30% | 30%是"普跌"的标准阈值 |
| **行业分化** | 强势股或弱势股数量 >= 3 | 分化度判断，超过3只视为分化明显 |

### 2.3 数据计算

```
median_return = 池子成员涨跌幅排序后取中位数
               = sort(member_returns)[len/2]

up_ratio = 池子中上涨股票数 / 池子总成员数
         = count(return > 0) / total_count

strong_count = 池子中涨幅前3名的股票数（涨幅 > median + threshold）
weak_count = 池子中跌幅前3名的股票数（跌幅 < median - threshold）
```

### 2.4 投研师使用方式

| 信号组合 | 行业判断 | 操作建议 |
|---------|---------|---------|
| Beta为正 + 扩散增强 | 行业趋势明确，普涨 | 顺势操作，可加仓 |
| Beta为正 + 扩散不足 | 行业上涨但分化 | 精选个股，不宜盲目跟涨 |
| Beta为负 + 扩散不足 | 行业普跌 | 谨慎操作，规避风险 |
| Beta为负 + 扩散增强 | 行业下跌但有分化 | 关注抗跌个股，可能有机会 |

**置信度解读**：
- high（超阈值2倍以上）→ 行业信号强烈可信
- medium（超阈值1-2倍）→ 行业信号可信度中等
- low（刚超阈值）→ 行业信号可信度低，需结合其他信号

---

## 3. Alpha类信号（个股相对强弱）

### 3.1 设计来源

**Alpha概念来自主动投资**：
```
Alpha = 股票收益超出基准收益的部分
      = 个股收益 - 基准收益

AnchorLink中：
Alpha = 锚定标的涨跌幅 - 池子中位数涨跌幅
     = relative_strength
```

行业实践中，量化基金常用**相对强度排名**：

| 阈值设置 | 来源 | 收益表现 |
|---------|------|---------|
| **前10% vs 后10%** | Jegadeesh & Titman (1993) 经典动量研究 | 年化超额收益~12% |
| **前20%** | IBD RS ≥ 80（Investor's Business Daily） | 历史回测优异 |
| **前30%** | 中信证券、华泰证券多因子选股常用 | 券商策略标准 |

**经典相对强度策略**：
- [Jegadeesh & Titman (1993) - Returns to Buying Winners and Selling Losers](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x)
  - 方法：按过去3-12个月收益率排序，分成10个十分位数组合
  - 买入前10%赢家，卖出后10%输家
  - 年化超额收益约10-12%
- [Moskowitz & Grinblatt (1999) - Do Industries Explain Momentum?](https://www.jstor.org/stable/117432)
  - 行业动量：前3-4个行业（约前30%）vs 后3-4个行业
- [IBD CAN SLIM - RS Rating Methodology](https://www.investors.com/)
  - RS评分 ≥ 80（即前20%）作为选股标准

**AnchorLink采用前30%阈值**，原因：
- 平衡信号敏感度和样本量（池子成员通常较少）
- 与券商策略标准一致

### 3.2 判断逻辑

| 信号 | 判断条件 | 阈值依据 |
|------|---------|---------|
| **个股Alpha为正** | relative_strength > 0.5% | 超过池子平均0.5%视为有独立Alpha |
| **个股Alpha为负** | relative_strength < -0.5% | 跑输池子平均0.5%视为弱势 |
| **跑赢主线池** | relative_strength > 0.5% 且 position="outperform" | 同上，额外标注跑赢主线池 |
| **处于行业前排** | rank_percentile < 30% | 前30%视为前排，经典排名阈值 |
| **处于行业后排** | rank_percentile > 70% | 后70%视为后排 |

### 3.3 数据计算

```
relative_strength = anchor_return - pool_median_return
                  = 锚定标的涨跌幅 - 池子中位数涨跌幅

rank_percentile = return_rank / total_count
                = 涨幅排名 / 池子成员总数

anchor_return = 锚定标的当日涨跌幅
pool_median_return = 池子成员涨跌幅中位数
```

**示例计算**（2026-05-07）：
```
铂力特涨跌幅: +2.72%
产业链池中位数: +0.99%

relative_strength = 2.72% - 0.99% = +1.72%
                  → 个股Alpha为正，跑赢1.72%

涨幅排名: 第2名
池子成员总数: 4只
rank_percentile = 2/4 = 50%（前端显示25%分位）
```

### 3.4 投研师使用方式

| 信号组合 | 个股判断 | 操作建议 |
|---------|---------|---------|
| Alpha为正 + 前排位置 | 个股强势明确，有独立Alpha | 可考虑加仓 |
| Alpha为正 + 后排位置 | 有Alpha但相对落后 | 观察持续性，谨慎加仓 |
| Alpha为负 + 后排位置 | 个股弱势明显 | 警惕风险，考虑减仓 |
| Alpha为正 + Beta为正 | 行业个股共振 | 顺势操作，可加仓 |
| Alpha为正 + Beta为负 | 个股逆势上涨 | 警惕补跌风险 |

---

## 4. Volume类信号（资金成交）

### 4.1 设计来源

**量价关系是技术分析经典指标**：

| 经典指标 | 含义 |
|---------|------|
| OBV（能量潮） | 成交量累计，判断资金流向 |
| MFI（资金流量指标） | 价量结合，判断买卖强度 |
| VWAP（成交量加权均价） | 机构交易基准价 |

行业实践中，**放量判断**有明确阈值：

| 放量程度 | 成交量倍数 | 市场含义 |
|---------|-----------|----------|
| **温和放量** | 1.5-2倍均量 | 主力资金逐步进场，趋势启动 |
| **明显放量** | 2-3倍均量 | 强势确认，机构积极参与 |
| **巨量** | 3倍以上 | 警惕短期见顶或底部反转 |

**来源依据**：
- [Technical Analysis - Volume Confirmation (Investopedia)](https://www.investopedia.com/terms/v/volume.asp)
- [Breakout Trading Volume Requirements (Investopedia)](https://www.investopedia.com/terms/b/breakout.asp)
  - 有效突破：价格突破关键阻力位时，需成交量放大至少1.5-2倍确认
  - 量价背离：价格上涨但成交量萎缩（低于均量），警惕假突破

**资金流向判断**（Level-2数据常用）：
- 大单净流入占比 > 60% → 主力资金积极买入
- 连续多日流入（3天以上） → 持续性主力行为

**来源依据**：
- [主力资金流向指标详解 - 格隆汇](https://www.gelonghui.com/p/653051)
- [东方财富主力资金流向](https://www.eastmoney.com/)
- [同花顺资金流向](https://www.10jqka.com.cn/)

**AnchorLink采用1.5倍阈值**，原因：
- 与技术分析经典标准一致（温和放量）
- 平衡信号敏感度（过高的2倍阈值可能漏掉温和放量信号）

### 4.2 判断逻辑

| 信号 | 判断条件 | 阈值依据 |
|------|---------|---------|
| **放量上涨** | volume_multiplier > 1.5 且 anchor_return > 0 | 1.5倍成交量视为明显放量，配合上涨视为资金认可 |
| **缩量下跌** | volume_multiplier < 0.7 且 anchor_return < 0 | 缩量下跌可能是洗盘，需结合其他信号 |
| **资金价格共振** | fund_positive_ratio > 60% 且 anchor_return > 0 | 60%资金正向配合上涨，视为共振 |
| **主力资金领先** | fund_positive_ratio > 60% | 资金正向比例超60%，视为主力看好 |
| **主力资金拖累** | fund_positive_ratio < 40% | 资金正向比例低于40%，视为资金撤离 |

### 4.3 数据计算

```
volume_multiplier = 锚定标的成交量 / 平均成交量
                  = 当日成交额 / 近20日平均成交额

fund_positive_ratio = 池子中资金流向为正的股票数 / 池子总成员数
                    = count(fund_flow > 0) / total_count

anchor_return = 锚定标的当日涨跌幅
```

### 4.4 投研师使用方式

| 信号组合 | 资金判断 | 操作建议 |
|---------|---------|---------|
| 放量上涨 + Alpha为正 | 资金确认个股强势 | 可跟随主力资金 |
| 资金价格共振 + Beta为正 | 资金确认行业强势 | 顺势操作 |
| 缩量下跌 + Alpha为正 | 洗盘可能 | 观察后续放量情况 |
| 资金价格背离 | 资金流出但股价涨 | 警惕资金撤离风险 |
| 主力资金领先 | 资金看好 | 关注后续走势 |

---

## 5. Rotation类信号（板块轮动）

### 5.1 设计来源

**板块轮动是行业配置经典策略**：

| 经典模型 | 含义 |
|---------|------|
| 美林时钟 | 经济周期 → 行业轮动 |
| 行业相对强度 | 哪个行业近期更强 → 配置哪个 |
| 动量轮动 | 做多强势行业，做空弱势行业 |

行业实践中，**板块轮动差值**判断资金流向：

| 轮动信号 | 阈值标准 | 说明 |
|---------|---------|------|
| **轻度轮动** | 行业间涨跌幅差 1-2% | 正常轮动节奏 |
| **中度轮动** | 行业间涨跌幅差 3-5% | 明显的资金迁移信号 |
| **强势轮动** | 行业间涨跌幅差 >5% | 大规模行业切换 |

**来源依据**：
- [Sector Rotation Strategies - ETFdb](https://etfdb.com/etfs/investment-style/)
- [Sector Momentum Strategy - New Trader U](https://newtraderu.com/sector-momentum-strategy-a-comprehensive-guide/)
  - 行业动量：前3-4个行业（约前30%）vs 后3-4个行业
  - Moskowitz, Ooi, Pedersen (2012) 时序动量：正收益 vs 负收益

**AnchorLink采用±0.5%阈值**，原因：
- 与Beta类阈值一致（±0.5%是"明显涨跌"的下限）
- 适用于池子间对比（池子成员数较少，差值通常更小）

### 5.2 判断逻辑

| 信号 | 判断条件 | 阈值依据 |
|------|---------|---------|
| **主线池强于主题情绪** | core_vs_theme_spread > 0.5% | 主线池涨幅超主题池0.5%，视为主线清晰 |
| **主题情绪强于主线池** | core_vs_theme_spread < -0.5% | 主题池涨幅超主线池0.5%，视为情绪炒作 |
| **交易观察池升温** | trading_pool.median_return > 0.5% | 交易池涨超0.5%，视为短线资金活跃 |

### 5.3 数据计算

```
core_vs_theme_spread = core_pool_median - theme_pool_median
                     = 产业链池中位数 - 主题情绪池中位数

> 0: 主线池更强（主线逻辑清晰）
< 0: 主题池更强（情绪炒作升温）
```

### 5.4 投研师使用方式

| 信号组合 | 轮动判断 | 操作建议 |
|---------|---------|---------|
| 主线池强 + Beta为正 | 主线逻辑清晰 | 坚守主线，可加仓 |
| 主题池强 + Beta为正 | 资金转向情绪炒作 | 警惕主线松动 |
| 交易池升温 | 短线资金活跃 | 关注短线机会，但需谨慎 |
| 主线池弱 + 交易池升温 | 资金撤离主线转向短线 | 警惕主线风险 |

---

## 6. Abnormal类信号（异常联动）

### 6.1 设计来源

**异常联动来自统计套利和配对交易逻辑**：

```
配对交易假设：
  相关股票应该保持稳定价差关系
  价差偏离 → 做多弱势股 + 做空强势股 → 等待回归

AnchorLink应用：
  锚定标的 vs 池子平均
  偏离过大 → 异常信号 → 警惕风险或机会
```

行业实践中，量化基金常用**协整检验**和**价差监控**：
- 价差偏离超过2倍标准差 → 异常信号

**统计套利经典方法**：
- [Gatev et al. (2006) -_pairs Trading](https://www.mit.edu/people/gatev/)
  - 配对交易：选择历史价差稳定的股票对
  - 当价差偏离超过2倍标准差时，触发交易信号

**AnchorLink采用±2%阈值**，原因：
- 2%偏离超过A股日均波动（~1%）的2倍
- 与统计套利"2倍标准差"标准一致

### 6.2 判断逻辑

| 信号 | 判断条件 | 阈值依据 |
|------|---------|---------|
| **行业强但个股弱** | median_return > 0.5% 且 relative_strength < -0.5% 且 spread > 2% | 行业涨但个股跌超2%，视为异常背离 |
| **行业弱但个股强** | median_return < -0.5% 且 relative_strength > 0.5% 且 spread > 2% | 行业跌但个股涨超2%，视为逆势异常 |
| **主题池强但主线池弱** | core_vs_theme_spread < -2% | 主题池涨超主线池2%，视为资金大幅转向 |

### 6.3 数据计算

```
spread = abs(median_return - anchor_return) 或 abs(core_pool_median - theme_pool_median)

异常判断：
  spread > 2% → 明显背离（超过A股日均波动2倍）
```

### 6.4 投研师使用方式

| 信号组合 | 异常判断 | 操作建议 |
|---------|---------|---------|
| 行业强但个股弱 | 个股可能有问题 | 立即检查个股基本面，警惕风险 |
| 行业弱但个股强 | 个股逆势上涨 | 警惕补跌风险，检查上涨原因 |
| 主题池强但主线池弱 | 资金转向情绪炒作 | 警惕主线松动，检查轮动原因 |
| 多个异常信号 | 风险高 | 立即关注，可能需要调整仓位 |

---

## 7. 置信度计算逻辑

### 7.1 设计来源

**置信度量化来自信号强度判断**：

```
行业实践中：
  强信号 vs 弱信号 → 决策权重不同
  超过阈值越多 → 信号越可信

AnchorLink量化：
  margin_ratio = (value - threshold) / abs(threshold)
```

### 7.2 计算公式

**数值类信号**（median_return、relative_strength、volume_multiplier）：
```
margin_ratio = (value - threshold) / abs(threshold)

置信度分级：
  margin_ratio >= 2.0 → high（超过阈值2倍以上）
  margin_ratio >= 1.0 → medium（超过阈值1-2倍）
  margin_ratio < 1.0  → low（刚超过阈值）
```

**排名类信号**（rank_percentile）：
```
percentile = rank / total_count

置信度分级：
  percentile <= 15% → high（排名前15%）
  percentile <= 30% → medium（排名前30%）
  percentile > 30%  → low（排名后70%，但符合前排阈值）
```

### 7.3 投研师解读

| 置信度 | 含义 | 决策权重 |
|--------|------|---------|
| high | 信号强烈可信 | 可作为主要决策依据 |
| medium | 信号可信度中等 | 需结合其他信号确认 |
| low | 信号刚满足阈值 | 仅供参考，谨慎决策 |

---

## 8. 信号组合解读

### 8.1 共振组合（利好）

| 组合条件 | 组合名称 | 投研师建议 |
|---------|---------|-----------|
| Beta为正 + Alpha为正 + 资金共振 | 强势共振 | 行业个股资金三重共振，可考虑加仓 |
| Beta为正 + 扩散增强 + 前排位置 | 趋势确认 | 行业趋势明确+个股前排，顺势操作 |
| Alpha为正 + 资金领先 | 资金确认 | 个股强势+资金认可，可跟随 |

### 8.2 背离组合（风险）

| 组合条件 | 组合名称 | 投研师建议 |
|---------|---------|-----------|
| Beta为正 + Alpha为负 | 个股背离 | 行业上涨但个股跑输，警惕个股风险 |
| Beta为负 + Alpha为正 | 逆势上涨 | 行业下跌但个股上涨，警惕补跌风险 |
| 资金价格背离 + Alpha为负 | 双重背离 | 资金流出+个股弱势，高风险 |

### 8.3 风险等级判断

| 条件 | 风险等级 | 建议 |
|------|---------|------|
| abnormal信号 >= 2 | 高风险 | 立即关注，检查基本面 |
| abnormal信号 = 1 或 背离组合 | 中风险 | 关注风险，谨慎操作 |
| 无异常信号 | 低风险 | 正常决策 |

---

## 9. 阈值合理性说明

### 9.1 阈值来源

| 阈值 | 设置值 | 学术/行业依据 |
|------|--------|--------------|
| BETA_POSITIVE_THRESHOLD | 0.5% | A股日均波动~1%，±0.5%是"明显涨跌"下限（[Sector Rotation](https://etfdb.com/)） |
| DIFFUSION_ENHANCE_THRESHOLD | 70% | 70%上涨视为"普涨"，符合行业惯例 |
| ALPHA_POSITIVE_THRESHOLD | 0.5% | 超池子平均0.5%视为有Alpha |
| OUTPERFORM_RANK_THRESHOLD | 30% | 前30%视为前排，[Jegadeesh & Titman (1993)](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x)经典方法使用前10%/后10%，券商策略常用前30% |
| VOLUME_HIGH_THRESHOLD | 1.5倍 | 温和放量标准，[Investopedia Volume Confirmation](https://www.investopedia.com/terms/v/volume.asp) |
| FUND_LEAD_THRESHOLD | 60% | Level-2资金分析常用，[主力资金流向 - 格隆汇](https://www.gelonghui.com/p/653051) |
| ABNORMAL_SPREAD_THRESHOLD | 2% | 统计套利"2倍标准差"标准，[Gatev配对交易](https://www.mit.edu/people/gatev/) |

**Fama-French因子模型阈值参考**：
- [Fama-French Data Library - Dartmouth](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
  - 价值因子（HML）：30%/70%分位数分成价值(30%)/中性(40%)/成长(30%)
  - 盈利因子（RMW）、投资因子（CMA）：同样使用30%/70%分位数 |

### 9.2 阈值可调整性

阈值定义在 `src/signal/rules.py`，可根据实际市场波动调整：

```python
# 当前阈值（基于A股市场特性）
BETA_POSITIVE_THRESHOLD = 0.5      # 可调整：0.3 ~ 0.8
DIFFUSION_ENHANCE_THRESHOLD = 0.70 # 可调整：60% ~ 80%
ALPHA_POSITIVE_THRESHOLD = 0.5     # 可调整：0.3 ~ 0.8
```

---

## 10. 数据质量保障

### 10.1 数据质量门控

| 状态 | 条件 | 信号生成 |
|------|------|---------|
| ok | 核心数据完整 | 正常生成信号 |
| partial | 缺失1-2个数据 | 生成信号但置信度抑制 |
| insufficient_data | 缺失 >= 3个核心数据 | 不生成信号 |

### 10.2 数据来源池子优先级

```
Beta/Alpha信号：
  优先使用 industry_chain（主线池）
  缺失时回退 direct_peers（本业池）

Volume信号：
  使用 direct_peers（资金流向在本业池有意义）

Rotation信号：
  使用所有池子对比
```

---

## 11. 参考文献

### 学术论文

| 论文 | 阈值方法 | 链接 |
|------|---------|------|
| Jegadeesh & Titman (1993) | 前10% vs 后10%动量组合 | [Returns to Buying Winners and Selling Losers](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x) |
| Moskowitz & Grinblatt (1999) | 前3-4行业（约30%）vs 后3-4行业 | [Do Industries Explain Momentum?](https://www.jstor.org/stable/117432) |
| Moskowitz, Ooi, Pedersen (2012) | 正收益 vs 负收益（时序动量） | [Time Series Momentum](https://www.aqr.com/insights/working-papers/time-series-momentum) |
| Gatev et al. (2006) | 价差偏离2倍标准差 | [Pairs Trading](https://www.mit.edu/people/gatev/) |
| Fama & French (1992) | 30%/70%分位数因子构建 | [The Cross-Section of Expected Stock Returns](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) |

### 行业实践

| 来源 | 阈值应用 | 链接 |
|------|---------|------|
| Investor's Business Daily | RS ≥ 80（前20%） | [IBD CAN SLIM Methodology](https://www.investors.com/) |
| Investopedia | 放量1.5-2倍确认突破 | [Volume Confirmation](https://www.investopedia.com/terms/v/volume.asp) |
| ETFdb | 行业轮动差值1-2%/3-5% | [Sector Rotation Strategies](https://etfdb.com/etfs/investment-style/) |
| 格隆汇 | 大单净流入>60%主力看好 | [主力资金流向指标详解](https://www.gelonghui.com/p/653051) |
| 东方财富 | Level-2资金流向分析 | [东方财富主力资金](https://www.eastmoney.com/) |

### 经典书籍

| 书籍 | 内容 |
|------|------|
| Murphy《技术分析》 | 量价关系、成交量确认 |
| Pring《市场技术分析》 | OBV、MFI等指标 |
| Grinblatt《金融市场微观结构》 | 资金流向、订单流分析 |

---

## 12. 总结

AnchorLink 信号体系的核心特点：

1. **可量化**：每个信号都有明确数值支撑，而非主观判断
2. **相对强度**：锚定标的相对于池子的位置，而非孤立判断
3. **证据驱动**：每个信号都有 evidence（数值、阈值、来源）
4. **置信度分级**：信号可信度量化，而非二元判断
5. **组合解读**：信号组合共振/背离判断，支撑决策

**投研师使用建议**：
- 不要孤立看单个信号，要看信号组合
- 高置信度信号权重更高，低置信度信号仅供参考
- 异常信号优先关注，代表风险
- 结合行业/个股基本面，信号只是量化辅助