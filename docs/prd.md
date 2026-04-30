# 商业航天情报系统 PRD

> 版本：v1.0 | 最后更新：2026-04-01
> 本文档是系统开发的核心参考，定义产品需求和技术规格。

---

## 1. 产品概述

### 1.1 背景

铂力特（688333.SH）是国内金属增材制造（3D打印）龙头，科创板上市。投资者需要一个自动化工具来：

1. **每日复盘**：了解铂力特在商业航天板块中的相对表现
2. **资金监控**：跟踪主力资金动向和市场情绪
3. **信号识别**：发现异常信号和潜在机会

### 1.2 目标

| 目标 | 指标 |
|------|------|
| 自动化数据获取 | 每日自动抓取 14 只股票数据 |
| 结构化分析 | 产出 85 个标准化指标 |
| 可读报告 | 生成 Markdown 格式日报 |

### 1.3 用户画像

- **个人投资者**：关注铂力特在商业航天板块的相对强弱
- **开发维护者**：需要清晰的模块接口和配置说明

---

## 2. 业务需求

### 2.1 核心需求

| 需求 | 优先级 | 状态 |
|------|--------|------|
| 每日行情数据抓取 | P0 | 已实现 |
| 板块相对强弱计算 | P0 | 已实现 |
| 资金流向分析 | P0 | 已实现 |
| 近5日连续性分析 | P0 | 已实现 |
| 日报生成 | P0 | 已实现 |

### 2.2 次要需求

| 需求 | 优先级 | 状态 |
|------|--------|------|
| 新闻事件抓取 | P1 | 框架已实现，适配器待开发 |
| AI 智能筛选 | P2 | 可选功能 |
| 历史回测 | P2 | 待开发 |

### 2.3 未来规划

- 多标的扩展：支持多个锚定标的
- 实时监控：盘中实时数据更新
- 可视化界面：Web Dashboard

---

## 3. 功能规格

### 3.1 行情数据线 (src/price/)

#### 3.1.1 流程概览

```
数据获取 → 标准化 → 数据产品 → 指标计算 → 连续观察 → 评分 → 诊断 → 反抽观察
```

#### 3.1.2 模块规格

| 步骤 | 模块 | 输入 | 输出 | 说明 |
|------|------|------|------|------|
| 1 | fetcher.py | stocks.yaml | data/price/raw/ | 从 Tushare 获取数据 |
| 2 | normalizer.py | raw/ | data/price/normalized/ | 统一字段格式 |
| 3 | data_product.py | normalized/ | price_data_product.json | 构建数据产品 |
| 4 | analyzer.py | data_product | daily_metrics.parquet | 核心指标计算 |
| 5 | rolling_analyzer.py | archive/metrics/ | rolling_metrics.parquet | 近5日连续性 |
| 6 | score_layer.py | archive/metrics/ | scored_metrics.parquet | 多标签评分 |
| 7 | diagnosis_layer.py | daily_metrics + rolling | 诊断结果 | 综合诊断 |
| 8 | rebound_watch_layer.py | 诊断结果 | 反抽信号 | 反抽观察 |

#### 3.1.3 指标产出

**基础行情（12个）**：
- trade_date, anchor_symbol, anchor_return
- sector_avg_return, relative_strength
- anchor_amount, amount_20d_high, amount_vs_5d_avg
- return_rank_in_sector, amount_rank_in_sector
- core_universe_count, sector_total_count

**基本面（8个）**：
- pe_ttm, pb, ps_ttm
- total_mv, circ_mv
- turnover_rate, turnover_rate_f

**资金流向（14个）**：
- net_mf_amount
- buy_elg_vol, sell_elg_vol
- buy_lg_vol, sell_lg_vol
- buy_elg_amount, sell_elg_amount
- buy_lg_amount, sell_lg_amount
- buy_md_amount, sell_md_amount
- buy_sm_amount, sell_sm_amount

**状态标签（9个）**：
- price_strength_label, volume_strength_label
- overall_signal_label, abnormal_signals
- valuation_label, capital_flow_label
- activity_label, capital_structure_label
- price_capital_relation_label

**连续观察（24个）**：
- rs_outperform_days_5d, rs_consecutive_outperform
- rs_consecutive_underperform, rs_5d_mean, rs_5d_series
- volume_expand_days_5d, amount_20d_high_days_5d
- volume_consecutive_shrink, volume_consecutive_expand
- amount_vs_5d_avg_series
- price_trend_label, volume_trend_label, momentum_label
- mf_inflow_days_5d, mf_consecutive_inflow
- mf_consecutive_outflow, mf_5d_mean
- capital_flow_trend_label
- trend_summary, rolling_summary_text

**诊断层（11个）**：
- diagnosis_label, diagnosis_reason
- signal_breakdown, observation_list
- capital_text, rolling_summary_text
- 等

### 3.2 新闻数据线 (src/news/)

#### 3.2.1 设计原则

**配置驱动**：唯一数据源是 `config/news_sources.yaml`，不硬编码任何新闻源。

#### 3.2.2 模块规格

| 模块 | 功能 |
|------|------|
| news_sources.py | 新闻源注册表，自动识别来源等级、类型、抓取模式 |
| event_layer.py | 事件提取，适配器框架 |
| ai_filter.py | AI 智能筛选（可选，需 Dashscope Token） |

#### 3.2.3 适配器类型

| 类型 | 用途 | 状态 |
|------|------|------|
| browser_session | 需要浏览器会话的页面 | 待实现 |
| rss | RSS 订阅 | 待实现 |
| html_list | HTML 列表抓取 | 待实现 |
| json_api | JSON API | 待实现 |

### 3.3 日报模块 (src/dailyreport/)

#### 3.3.1 设计原则

**reporter 只做格式化输出，不做计算**（v2.7 架构原则）

#### 3.3.2 报告结构

```markdown
# 铂力特每日复盘 - YYYY-MM-DD

## 📊 状态面板
## 一、今日结论
## 二、证据板
## 三、资金流向
## 四、近5日结构
## 五、估值与位置
## 六、今日关键信号
## 七、明日观察清单
## 八、研究层对比
## 九、股票池快照
## 十、股票池复审提醒
```

---

## 4. 数据设计

### 4.1 数据流向

```
Tushare API
    ↓
data/price/raw/           # 原始数据
    ↓
data/price/normalized/    # 标准化数据
    ↓
data/price/processed/     # 处理后数据
    ↓
data/price/analytics/     # 分析数据
    ↓
archive/metrics/          # 归档数据（按日期）
```

### 4.2 存储规范

| 目录 | 格式 | 保留期限 |
|------|------|----------|
| data/price/raw/ | Parquet | 永久 |
| data/price/processed/ | Parquet | 永久 |
| archive/metrics/ | Parquet (YYYYMMDD.parquet) | 永久 |
| reports/ | Markdown | 永久 |

### 4.3 指标字典

详见 [docs/field_glossary.md](field_glossary.md)

---

## 5. 接口规格

### 5.1 数据产品接口

每个模块通过 `data_product.py` 暴露统一接口：

```python
# src/price/data_product.py
def build_price_data_product() -> dict:
    """构建价格数据产品"""
    return {
        "overall_status": "ok" | "degraded" | "error",
        "trade_date": "YYYY-MM-DD",
        "anchor_symbol": "688333.SH",
        # ...
    }
```

### 5.2 配置文件接口

#### stocks.yaml

```yaml
version: "YYYY-MM-DD"
anchor:
  code: 688333.SH
  name: 铂力特
  layer: anchor
  active: true
  benchmark_included: false

core_universe:
  - code: 600343.SH
    name: 航天动力
    layer: core
    active: true
    benchmark_included: true

research_core:
  # 研究层对标

extended_universe:
  # 扩展观察池
```

#### news_sources.yaml

```yaml
sources:
  - https://tushare.pro/news/cls
  - https://tushare.pro/news/eastmoney
```

---

## 6. 技术架构

### 6.1 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    scripts/run_all.py                    │
│                      （统一入口）                          │
└─────────────────────────────────────────────────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  src/price/  │    │  src/news/   │    │src/dailyreport│
│  行情数据线   │    │  新闻数据线   │    │   日报模块    │
└──────────────┘    └──────────────┘    └──────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────┐
│                    data/ (共享存储)                       │
└─────────────────────────────────────────────────────────┘
```

### 6.2 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| 语言 | Python | 3.13+ |
| 数据源 | Tushare | - |
| 数据处理 | pandas | 2.0+ |
| 存储 | Parquet | - |
| AI 筛选 | Dashscope | 1.14+ (可选) |
| 包管理 | uv | - |

### 6.3 开发规范

1. **函数式编程**：保持模块独立
2. **配置分离**：配置与代码分离
3. **可测试性**：每个模块可独立测试
4. **reporter 只做格式化**：不做计算
5. **数据产品解耦**：通过数据产品接口解耦模块间依赖
6. **统一存储访问**：使用 `src.shared.storage.Storage` 类

---

## 7. 开发规划

### 7.1 当前版本 (v1.0)

| 功能 | 状态 |
|------|------|
| 行情数据线 | ✅ 已完成 |
| 日报模块 | ✅ 已完成 |
| 连续观察层 | ✅ 已完成 |
| 诊断层 | ✅ 已完成 |
| 反抽观察层 | ✅ 已完成 |

### 7.2 待开发功能

| 功能 | 优先级 | 预计工作量 |
|------|--------|------------|
| 新闻适配器实现 | P1 | 3-5 天 |
| AI 智能筛选 | P2 | 2-3 天 |
| 历史回测 | P2 | 5-7 天 |
| Web Dashboard | P3 | 10-15 天 |

### 7.3 已知问题

| 问题 | 影响 | 状态 |
|------|------|------|
| 新闻适配器未实现 | 新闻数据线无实际产出 | 待开发 |
| archive 数据不足5日 | 近5日结构显示"数据不足" | 需积累数据 |

---

## 附录

### A. 文档索引

| 文档 | 内容 |
|------|------|
| CLAUDE.md | 项目操作指南 |
| docs/file_structure.md | 项目目录结构 |
| docs/field_glossary.md | 指标字典（85个字段） |
| docs/pool_governance.md | 股票池治理规范 |

### B. 变更日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-04-01 | v1.0 | 初始版本 |