# Space Intel 项目指南

## 项目概述
商业航天板块每日复盘工具。自动获取市场数据、计算技术指标、生成 Markdown 格式的日报。

## 架构

系统分为三个独立模块：

```
src/
├── price/           # 行情数据线
├── news/            # 新闻数据线
├── dailyreport/     # 日报模块
└── shared/          # 共享工具
```

## 运行命令

```bash
# 完整运行
uv run python scripts/run_all.py

# 独立运行各模块
uv run python -m src.price.run       # 行情数据线
uv run python -m src.news.run        # 新闻数据线
uv run python -m src.dailyreport.run # 日报生成
```

## 目录结构

```
space-intel/
├── config/                    # 配置文件
│   ├── stocks.yaml           # 股票池定义
│   ├── news_sources.yaml     # 新闻源配置
│   ├── catalyst_rules.yaml   # 催化筛选规则
│   └── catalyst_sources.yaml # 催化源配置
│
├── data/                      # 共享存储层
│   ├── price/                # 行情数据
│   │   ├── raw/              # 原始数据 (market_data, daily_basic, moneyflow)
│   │   ├── normalized/       # 标准化数据 (market_data_normalized)
│   │   ├── processed/        # 处理后数据 (daily_metrics, price_data_product)
│   │   ├── analytics/        # 分析数据 (rolling_metrics, scored_metrics)
│   │   └── archive/          # 归档数据 (YYYYMMDD.parquet)
│   ├── news/                 # 新闻数据
│   │   ├── raw/news_sources/ # 按来源存储 (tushare_cls, tushare_eastmoney)
│   │   └── processed/        # news_sources_registry, daily_events
│   └── catalyst/             # 催化数据
│       ├── index/            # stocks.json
│       └── news/             # 催化新闻数据
│
├── src/
│   ├── price/                # 行情数据线
│   │   ├── fetcher.py        # 数据获取
│   │   ├── normalizer.py     # 数据标准化
│   │   ├── analyzer.py       # 核心指标计算
│   │   ├── rolling_analyzer.py # 连续观察指标
│   │   ├── score_layer.py    # 多标签评分
│   │   ├── rebound_watch_layer.py # 反抽观察
│   │   ├── data_product.py   # 数据产品接口
│   │   └── run.py            # 模块入口
│   │
│   ├── news/                 # 新闻数据线
│   │   ├── news_sources.py   # 新闻源管理
│   │   ├── news_source_fetcher.py # 新闻抓取
│   │   ├── ai_filter.py      # AI 智能筛选
│   │   ├── event_layer.py    # 事件提取
│   │   ├── data_product.py   # 数据产品接口
│   │   └── run.py            # 模块入口
│   │
│   ├── dailyreport/          # 日报模块
│   │   ├── reporter.py       # 生成 Markdown 报告
│   │   ├── review_stock_pool.py # 股票池复审提醒
│   │   ├── data_product.py   # 数据产品接口
│   │   └── run.py            # 模块入口
│   │
│   ├── shared/               # 共享工具
│   │   ├── config.py         # 配置加载
│   │   ├── storage.py        # 统一存储层访问
│   │   └── paths.py          # 路径常量定义
│   │
│   ├── backfill.py           # 历史数据回填
│   ├── evaluate_stock.py     # 股票池评估
│   ├── validate_signals.py   # 信号验证
│   └── explain_signal_state.py # 状态解释
│
├── reports/                  # 生成的报告
└── scripts/run_all.py        # 统一入口
```

## 核心模块

### 行情数据线 (src/price/)
- `run.py` - 模块入口，7 步流程
- `fetcher.py` - 从 Tushare 获取股票数据
- `normalizer.py` - 数据标准化
- `analyzer.py` - 核心指标计算（涨跌幅、相对强弱、成交额等）v2.1.1
- `rolling_analyzer.py` - 连续观察指标 v2.4
- `score_layer.py` - 多标签评分
- `rebound_watch_layer.py` - 反抽观察信号
- `data_product.py` - 数据产品接口

### 新闻数据线 (src/news/)
- `run.py` - 模块入口，3 步流程
- `news_sources.py` - 新闻源管理
- `news_source_fetcher.py` - 新闻抓取（Playwright CDP 浏览器会话）
- `ai_filter.py` - AI 智能筛选
- `event_layer.py` - 事件提取 v1.0
- `data_product.py` - 数据产品接口

### 日报模块 (src/dailyreport/)
- `run.py` - 模块入口
- `reporter.py` - 生成 Markdown 报告 v2.5
- `review_stock_pool.py` - 股票池复审提醒
- `data_product.py` - 数据产品接口

### 共享模块 (src/shared/)
- `config.py` - 配置加载工具
- `storage.py` - 统一存储层访问
- `paths.py` - 路径常量定义

## 技术栈
- Python 3.11+
- Tushare (股票数据源)
- pandas (数据处理)
- OpenAI API (新闻 AI 筛选，可选)

## 开发规范
- 使用函数式编程，保持模块独立
- 配置与代码分离
- 每个模块可独立测试
- 通过数据产品接口解耦模块间依赖
- 使用 `src.shared.storage.Storage` 类访问数据目录

## 项目文档
- `ARCHITECTURE.md` - 系统架构详细说明
- `.claude/memory/MEMORY.md` - 跨会话项目记忆（跟随版本控制）