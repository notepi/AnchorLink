# Space Intel

商业航天板块每日复盘工具。自动获取市场数据、计算技术指标、生成 Markdown 格式的日报。

## 架构

系统分为三个独立模块：

- **src/price/** - 行情数据线（获取、标准化、分析）
- **src/news/** - 新闻数据线（采集、筛选、事件提取）
- **src/dailyreport/** - 日报（股票复盘报告生成）

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 环境配置

```bash
cp .env.example .env
# 编辑 .env 填入实际的 API 密钥
```

### 运行分析

```bash
# 完整运行（推荐）
python scripts/run_all.py

# 跳过新闻数据线
python scripts/run_all.py --skip-news

# 只生成日报
python scripts/run_all.py --only-report
```

### 独立运行各模块

```bash
# 行情数据线
python -m src.price.run

# 新闻数据线
python -m src.news.run

# 日报生成
python -m src.dailyreport.run
```

## 目录结构

```
space-intel/
├── config/                    # 配置文件
│   ├── stocks.yaml           # 股票池定义
│   ├── news_sources.yaml     # 新闻源配置
│   └── catalyst_rules.yaml   # 催化筛选规则
│
├── data/                      # 共享存储层
│   ├── price/                # 行情数据
│   │   ├── raw/              # 原始数据
│   │   ├── normalized/       # 标准化数据
│   │   ├── processed/        # 处理后数据
│   │   └── archive/          # 归档数据
│   └── news/                 # 新闻数据
│       ├── raw/              # 原始数据
│       ├── processed/        # 处理后数据
│       └── archive/          # 归档数据
│
├── src/                       # 源代码
│   ├── price/                # 行情数据线
│   │   ├── fetcher.py        # 数据获取
│   │   ├── normalizer.py     # 数据标准化
│   │   ├── analyzer.py       # 指标计算
│   │   ├── rolling_analyzer.py  # 连续观察
│   │   ├── score_layer.py    # 评分层
│   │   ├── rebound_watch_layer.py  # 反抽观察
│   │   ├── data_product.py   # 数据产品接口
│   │   └── run.py            # 入口
│   │
│   ├── news/                 # 新闻数据线
│   │   ├── news_sources.py   # 新闻源管理
│   │   ├── news_source_fetcher.py  # 新闻抓取
│   │   ├── catalyst_collector.py  # 催化收集
│   │   ├── ai_filter.py      # AI 筛选
│   │   ├── event_layer.py    # 事件层
│   │   ├── data_product.py   # 数据产品接口
│   │   └── run.py            # 入口
│   │
│   ├── dailyreport/          # 日报模块
│   │   ├── reporter.py       # 报告生成
│   │   ├── review_stock_pool.py  # 股票池复审
│   │   └── run.py            # 入口
│   │
│   └── shared/               # 共享工具
│       ├── config.py         # 配置加载
│       └── storage.py        # 存储层访问
│
├── reports/                  # 生成的报告
├── scripts/                  # 脚本
│   └── run_all.py            # 统一入口
├── tests/                    # 测试文件
├── ARCHITECTURE.md           # 架构文档
└── README.md                 # 本文件
```

## 测试

```bash
python -m pytest -q
```

## 技术栈

- Python 3.11+
- Tushare (股票数据源)
- pandas (数据处理)
- OpenAI API (新闻 AI 筛选)