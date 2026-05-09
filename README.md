# AnchorLink

锚定联动分析系统。锚定一家公司，与板块联动对比分析，自动生成每日复盘报告。

**核心功能**：
- 锚定标的与板块联动分析
- 计算相对强弱、资金流向对比
- 生成 Markdown 格式日报
- Web 可视化界面

## 快速开始

### 1. 克隆项目

```bash
git clone <repo-url>
cd AnchorLink
```

### 2. 环境配置

```bash
cp .env.example .env
# 编辑 .env 填入 API Token（必需）
```

需要的 Token：
- `CITYDATA_TOKEN` - 股票数据源（获取方式：https://tushare.citydata.club）
- `DASHSCOPE_API_KEY` - AI 筛选（获取方式：https://bailian.console.aliyun.com/）

### 3. 启动前端

```bash
cd web
npm install
npm run dev
# 访问 http://localhost:3000
```

### 4. 更新数据（可选）

前端依赖 `data/output/` 目录的数据文件。如需更新数据：

```bash
uv sync

# 每日更新（默认回溯60天）
uv run python scripts/run_all.py

# 扩展历史天数
uv run python scripts/run_all.py --days 365
```

## 模块说明

- **src/price/** - 行情数据线（获取、标准化、分析）
- **src/dailyreport/** - 日报（股票复盘报告生成）

## 目录结构

```
AnchorLink/
├── config/                    # 配置文件
│   ├── pools.yaml            # 股票池定义（三层结构）
│   └── catalyst_rules.yaml   # 催化筛选规则
│
├── data/                      # 共享存储层
│   ├── price/                # 行情数据
│   │   ├── raw/              # 原始数据
│   │   ├── normalized/       # 标准化数据
│   │   ├── processed/        # 处理后数据
│   │   └── archive/          # 归档数据
│   └── output/               # 前端数据产品
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
│   ├── dailyreport/          # 日报模块
│   │   ├── reporter.py       # 报告生成
│   │   ├── review_stock_pool.py  # 股票池复审
│   │   └── run.py            # 入口
│   │
│   └── shared/               # 共享工具
│       ├── config.py         # 配置加载
│       └── storage.py        # 存储层访问
│
├── web/                       # 前端
│   └── src/                  # Next.js 应用
│
├── reports/                  # 生成的报告
├── archive/                  # 指标归档
├── scripts/                  # 脚本
│   └── run_all.py            # 统一入口
├── tests/                    # 测试文件
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
- Next.js 15 (前端)
- React 19 (前端)