# Space-Intel 系统架构

## 概述

Space-Intel 是一个投资决策支持平台，专注于商业航天板块的每日行情分析。

系统采用模块化架构，分为三条独立数据线：

- **行情数据线** (src/price/) - 股票行情数据的获取、标准化和分析
- **新闻数据线** (src/news/) - 新闻数据的采集、筛选和事件提取
- **日报模块** (src/dailyreport/) - 复盘报告生成

---

## 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         scripts/run_all.py                           │
│                         （统一入口）                                   │
└─────────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
   ┌───────────────┐    ┌───────────────┐    ┌───────────────┐
   │  src/price/   │    │  src/news/    │    │src/dailyreport│
   │  行情数据线    │    │  新闻数据线    │    │    日报模块    │
   └───────────────┘    └───────────────┘    └───────────────┘
           │                    │                    │
           ▼                    ▼                    │
   ┌───────────────┐    ┌───────────────┐           │
   │data/price/    │    │ data/news/    │           │
   │  存储层       │    │   存储层       │           │
   └───────────────┘    └───────────────┘           │
           │                    │                    │
           └────────────────────┴────────────────────┘
                               │
                               ▼
                    ┌───────────────────┐
                    │  reports/*.md     │
                    │  日报输出          │
                    └───────────────────┘
```

---

## 模块职责

### 行情数据线 (src/price/)

| 模块 | 职责 | 输入 | 输出 |
|------|------|------|------|
| `fetcher.py` | 从 Tushare 获取股票数据 | API 请求 | `data/price/raw/*.parquet` |
| `normalizer.py` | 数据标准化 | 原始 parquet | `data/price/normalized/*.parquet` |
| `analyzer.py` | 计算核心指标 | 标准化数据 | `data/price/processed/daily_metrics.parquet` |
| `rolling_analyzer.py` | 连续观察指标 | 日指标 | `data/analytics/rolling_metrics.parquet` |
| `score_layer.py` | 多标签评分 | 滚动指标 | `data/analytics/scored_metrics.parquet` |
| `rebound_watch_layer.py` | 反抽观察信号 | 日指标 | 反抽信号 |
| `data_product.py` | 数据产品接口 | - | PriceDataProduct 类 |

### 新闻数据线 (src/news/)

| 模块 | 职责 | 输入 | 输出 |
|------|------|------|------|
| `news_sources.py` | 新闻源管理 | YAML 配置 | `data/news/processed/registry.json` |
| `news_source_fetcher.py` | 新闻抓取 | Registry | `data/news/raw/*.json` |
| `ai_filter.py` | AI 智能筛选 | 新闻列表 | 筛选后新闻 |
| `event_layer.py` | 事件提取 | 筛选后新闻 | `data/news/processed/daily_events.json` |
| `data_product.py` | 数据产品接口 | - | NewsDataProduct 类 |

### 日报模块 (src/dailyreport/)

| 模块 | 职责 | 输入 | 输出 |
|------|------|------|------|
| `reporter.py` | 生成 Markdown 报告 | 价格数据产品 | `reports/*.md` |
| `review_stock_pool.py` | 股票池复审提醒 | stocks.yaml | 复审建议 |

---

## 共享模块 (src/shared/)

### Storage 类

统一存储层访问接口：

```python
from src.shared.storage import Storage

# 行情存储
price_storage = Storage("price")
price_storage.raw_dir           # data/price/raw/
price_storage.normalized_dir    # data/price/normalized/
price_storage.processed_dir     # data/price/processed/

# 新闻存储
news_storage = Storage("news")
news_storage.raw_dir            # data/news/raw/
news_storage.processed_dir      # data/news/processed/
```

### 配置加载

```python
from src.shared.config import (
    load_config,
    get_stock_pool,
    get_all_stock_codes,
    get_benchmark_codes,
    get_news_sources,
    get_catalyst_rules,
)
```

---

## 数据产品接口

### PriceDataProduct

```python
from src.price.data_product import PriceDataProduct

# 获取最新交易日
trade_date = PriceDataProduct.get_latest_trade_date()

# 加载价格输入数据
inputs = PriceDataProduct.load_price_inputs()
```

### NewsDataProduct

```python
from src.news.data_product import NewsDataProduct

# 获取事件数据
events = NewsDataProduct.get_daily_events()

# 按相关度筛选
strong_events = NewsDataProduct.get_events_by_relevance(level="strong")
```

---

## 配置文件

| 文件 | 用途 |
|------|------|
| `config/stocks.yaml` | 股票池定义（anchor, core_universe, extended_universe） |
| `config/news_sources.yaml` | 新闻源 URL 列表 |
| `config/catalyst_rules.yaml` | 催化筛选规则（关键词、投资主题） |

---

## 环境变量

复制 `.env.example` 为 `.env` 并填入实际值：

| 变量 | 用途 | 获取方式 |
|------|------|----------|
| `TUSHARE_TOKEN` | Tushare API 访问令牌 | 注册 https://tushare.pro 后获取 |
| `DASHSCOPE_API_KEY` | 阿里百炼 API Key | 用于新闻 AI 筛选（可选） |