# 项目目录结构

## 概览

```
space-intel/
├── config/                    # 配置文件
├── data/                      # 共享存储层
├── src/                       # 源代码
├── docs/                      # 文档
├── reports/                   # 生成的报告
└── scripts/                   # 脚本
```

## 详细结构

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
│   │   ├── analyzer.py       # 核心指标计算 v3.1
│   │   ├── rolling_analyzer.py # 连续观察指标 v2.7
│   │   ├── diagnosis_layer.py # 诊断层 v1.1
│   │   ├── score_layer.py    # 多标签评分
│   │   ├── rebound_watch_layer.py # 反抽观察
│   │   ├── data_product.py   # 数据产品接口
│   │   └── run.py            # 模块入口（8步流程）
│   │
│   ├── news/                 # 新闻数据线
│   │   ├── news_sources.py   # 新闻源管理
│   │   ├── ai_filter.py      # AI 智能筛选
│   │   ├── event_layer.py    # 事件提取 v2.0
│   │   ├── data_product.py   # 数据产品接口
│   │   └── run.py            # 模块入口
│   │
│   ├── dailyreport/          # 日报模块
│   │   ├── reporter.py       # 生成 Markdown 报告 v2.7
│   │   ├── review_stock_pool.py # 股票池复审提醒
│   │   ├── data_product.py   # 数据产品接口
│   │   └and run.py            # 模块入口
│   │
│   ├── shared/               # 共享工具
│   │   ├── config.py         # 配置加载
│   │   ├── storage.py        # 统一存储层访问
│   │   └── paths.py          # 路径常量定义
│   │
│   ├── backfill.py           # 历史数据回填
│   ├── evaluate_stock.py     # 股票池评估
│   ├── validate_signals.py   # 信号验证
│   └and explain_signal_state.py # 状态解释
│
├── docs/                     # 文档
│   ├── file_structure.md    # 本文档
│   ├── field_glossary.md    # 数据线指标字典（v3.1）
│   └and pool_governance.md   # 股票池治理规范
│
├── reports/                  # 生成的报告
│   └and scripts/run_all.py        # 统一入口
```

## 核心模块

### 行情数据线 (src/price/)

8 步流程，产出 85 个指标：

| 步骤 | 模块 | 功能 |
|------|------|------|
| 1 | fetcher.py | 从 Tushare 获取股票数据 |
| 2 | normalizer.py | 数据标准化 |
| 3 | data_product.py | 构建价格数据产品 |
| 4 | analyzer.py | 核心指标计算（涨跌幅、相对强弱、资金流向、估值） |
| 5 | rolling_analyzer.py | 连续观察指标（近5日价格/量能/资金连续性） |
| 6 | score_layer.py | 多标签评分 |
| 7 | diagnosis_layer.py | 诊断层（综合诊断、信号拆解、观察清单） |
| 8 | rebound_watch_layer.py | 反抽观察信号 |

### 新闻数据线 (src/news/)

配置驱动模式，唯一数据源是 `config/news_sources.yaml`：

| 模块 | 功能 |
|------|------|
| run.py | 模块入口 |
| news_sources.py | 新闻源注册表（自动识别来源等级、类型、抓取模式） |
| event_layer.py | 事件提取 v2.0（适配器框架） |
| ai_filter.py | AI 智能筛选（可选） |

**适配器类型**（待实现）：
- `browser_session` - 需要浏览器会话
- `rss` - RSS 订阅
- `html_list` - HTML 列表抓取
- `json_api` - JSON API

### 日报模块 (src/dailyreport/)

v2.7 瘦身版：reporter 只做格式化输出，不做计算。

### 共享模块 (src/shared/)

| 模块 | 功能 |
|------|------|
| config.py | 配置加载工具 |
| storage.py | 统一存储层访问 |
| paths.py | 路径常量定义 |

## 技术栈

- Python 3.13+
- Tushare (股票数据源)
- pandas (数据处理)
- Dashscope (新闻 AI 筛选，可选)

## 开发规范

- 使用函数式编程，保持模块独立
- 配置与代码分离
- 每个模块可独立测试
- **reporter 只做格式化输出，不做计算**（v2.7 架构原则）
- 通过数据产品接口解耦模块间依赖
- 使用 `src.shared.storage.Storage` 类访问数据目录