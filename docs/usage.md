# AnchorLink - 使用说明

> 快速上手指南 | 最后更新：2026-04-30

---

## 一、系统概述

**名称**：AnchorLink（锚定联动）

**用途**：锚定一家公司，与板块联动对比分析，自动生成每日复盘报告。

**当前标的**：铂力特（688333.SH）

**核心能力**：
- 锚定标的与板块联动分析
- 计算相对强弱、资金流向对比
- 计算 85 个标准化指标
- 生成 Markdown 格式日报

---

## 二、快速开始

### 1. 环境配置

```bash
# 1. 安装依赖
uv sync

# 2. 配置已完成（.env 已设置）
# - CITYDATA_TOKEN: CityData 代理（无积分限制）
# - DASHSCOPE_API_KEY: AI筛选（GLM-5）
```

**Token 配置说明**：

| Token | 用途 | 备注 |
|-------|------|------|
| CITYDATA_TOKEN | 行情数据获取 | CityData 代理，无积分限制 |
| DASHSCOPE_API_KEY | AI 新闻筛选 | 阿里百炼 GLM-5 |

### 2. 每日运行

```bash
# 一键运行全部流程
uv run python scripts/run_all.py
```

**输出**：
- `reports/YYYYMMDD_blt_review.md` - 当日复盘报告
- `archive/metrics/YYYYMMDD.parquet` - 指标归档

### 3. 独立模块运行

```bash
# 仅运行行情数据线
uv run python -m src.price.run

# 仅运行日报生成
uv run python -m src.dailyreport.run
```

---

## 三、系统架构

### 数据流向

```
Tushare API
    ↓ fetcher.py
data/price/raw/           # 原始数据
    ↓ normalizer.py
data/price/normalized/    # 标准化数据
    ↓ data_product.py
data/price/processed/     # 数据产品
    ↓ analyzer.py
data/price/analytics/     # 分析结果
    ↓ rolling_analyzer.py
archive/metrics/          # 近5日连续性
    ↓ diagnosis_layer.py
诊断结果
    ↓ reporter.py
reports/                  # 最终报告
```

### 三条数据线

| 数据线 | 状态 | 输出 |
|--------|------|------|
| 行情数据线 (src/price/) | ✅ 已完成 | 85个指标 + 诊断结论 |
| 新闻数据线 (src/news/) | ⚠️ 框架完成，适配器待开发 | 事件列表 |
| 日报模块 (src/dailyreport/) | ✅ 已完成 | Markdown报告 |

---

## 四、报告结构

生成的日报包含 10 个章节：

| 章节 | 内容 | 用途 |
|------|------|------|
| 状态面板 | 8个状态标签 | 快速定位 |
| 今日结论 | 诊断标签+原因+下一步 | 决策依据 |
| 证据板 | 关键指标数值 | 验证结论 |
| 资金流向 | 主力行为分析 | 资金判断 |
| 近5日结构 | 连续性分析 | 趋势判断 |
| 估值与位置 | PE/PB、板块排名 | 估值参考 |
| 关键信号 | 异常/积极/风险 | 信号识别 |
| 明日观察 | 观察清单 | 下一步行动 |
| 研究层对比 | 产业链对标 | 中期位次 |
| 股票池复审 | 治理提醒 | 池维护 |

---

## 五、核心指标说明

### 关键概念

**相对强弱**：剔除板块影响后的真实表现
```
relative_strength = 铂力特涨跌幅 - 板块均值涨跌幅
```

**双层股票池**：

| 层级 | 用途 | 股票数 |
|------|------|--------|
| core_universe | 交易层对标（参与均值计算） | 4只 |
| research_core | 研究层对标（产业链对比） | 4只 |
| extended_universe | 扩展观察 | 9只 |

**状态标签规则**：

| 标签 | 触发条件 |
|------|----------|
| 价格强度-强 | 涨幅>2% 或 相对强弱>1%且排名前半 |
| 价格强度-弱 | 跌幅>2% 或 相对强弱<-1%且排名后半 |
| 成交额强度-强 | 创20日新高 或 成交额>1.5倍均值 |

---

## 六、配置文件

### 股票池配置

位置：`config/stocks.yaml`

```yaml
anchor:
  code: 688333.SH
  name: 铂力特

core_universe:
  - code: 600343.SH
    name: 航天动力
  - code: 000901.SZ
    name: 航天科技
```

### 新闻源配置

位置：`config/news_sources.yaml`（待实现适配器）

---

## 七、数据目录

| 目录 | 内容 | 格式 |
|------|------|------|
| data/price/raw/ | Tushare原始数据 | Parquet |
| data/price/normalized/ | 标准化数据 | Parquet |
| archive/metrics/ | 指标归档（按日期） | Parquet |
| reports/ | 日报 | Markdown |

---

## 八、常见问题

### Q: 报告显示"数据不足"？

**原因**：archive/metrics/ 目录下数据不足5日

**解决**：连续运行5天，积累足够数据后自动显示完整近5日结构

### Q: 如何修改股票池？

**步骤**：
1. 编辑 `config/stocks.yaml`
2. 运行 `uv run python scripts/run_all.py`
3. 新股票池立即生效

### Q: 新闻功能何时可用？

**状态**：框架已完成，适配器待开发

**预计**：实现浏览器适配器后可用（P1优先级）

---

## 九、文档索引

| 文档 | 内容 |
|------|------|
| [CLAUDE.md](CLAUDE.md) | 项目操作指南 |
| [docs/prd.md](docs/prd.md) | 产品需求文档（开发视角） |
| [docs/prd_business_review.md](docs/prd_business_review.md) | 业务方案评审（业务视角） |
| [docs/field_glossary.md](docs/field_glossary.md) | 指标字典（85个字段） |
| [docs/file_structure.md](docs/file_structure.md) | 项目目录结构 |
| [docs/pool_governance.md](docs/pool_governance.md) | 股票池治理规范 |

---

## 十、下一步规划

| 功能 | 优先级 | 状态 |
|------|--------|------|
| 新闻适配器实现 | P1 | 待开发 |
| AI智能筛选 | P2 | 可选 |
| 历史回测 | P2 | 待开发 |
| Web Dashboard | P3 | 待开发 |