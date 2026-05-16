# AnchorLink

锚定联动分析系统。锚定一家公司，与板块联动对比分析，自动生成每日复盘报告。

当前标的：铂力特 (688333.SH)

## 快速开始

### 1. 环境配置

```bash
git clone <repo-url> && cd AnchorLink
cp .env.example .env
# 编辑 .env 填入 API Token
uv sync
```

需要的 Token：

| Token | 用途 |
|-------|------|
| `TUSHARE_TOKEN` | 股票数据源（https://tushare.citydata.club） |
| `DASHSCOPE_API_KEY` | AI 筛选（可选，https://bailian.console.aliyun.com/） |

### 2. 启动前端

```bash
cd web && npm install && npm run dev
# 访问 http://localhost:3000
```

### 3. 更新数据

```bash
# 每日更新（默认回溯60天）
uv run python scripts/run_all.py

# 扩展历史天数
uv run python scripts/run_all.py --days 365
```

## 核心概念

### 数据管道

四步管道，必须按顺序执行：

```
行情拉取 → 日报生成 → 历史分析 → 前端数据构建
```

每一步依赖上一步的输出，最终生成 `dashboard_view.json` 供前端消费。

### 四类股票池

| 股票池 | 回答的问题 |
|--------|-----------|
| direct_peers（核心同类） | 业务可比公司今天强不强？ |
| industry_chain（产业链） | 上下游有没有同向变化？ |
| theme_pool（主题情绪） | 市场是不是在炒主题？ |
| trading_watchlist（交易观察） | 短期资金有没有切换？ |

### 信号系统

五类 35+ 信号（Beta / Alpha / Volume / Rotation / Abnormal），每个信号带证据链，支持反直觉识别和象限条件效果分析。

## 目录结构

```
AnchorLink/
├── config/                    # 配置文件
│   ├── pools.yaml            # 股票池定义（四类 Universe + Membership）
│   └── catalyst_rules.yaml   # 催化筛选规则
├── data/                      # 数据存储
│   ├── price/                # 行情数据（raw/normalized/processed/analytics）
│   └── output/               # 前端数据产品（dashboard_view.json）
├── src/                       # 源代码
│   ├── price/                # 行情数据线（获取、标准化、数据产品）
│   ├── dailyreport/          # 日报生成
│   ├── pool_state/           # 池状态计算
│   ├── anchor_position/      # 锚定标的相对位置
│   ├── group_rotation/       # 组间轮动分析
│   ├── signal/               # 信号生成与标签
│   ├── history_analysis/     # 历史时序分析
│   ├── output/               # 输出层（JSON/CSV/Markdown）
│   ├── config/               # 配置加载（PoolRegistry）
│   └── shared/               # 共享工具（config/storage/paths）
├── web/                       # 前端（Next.js 15 + React 19）
├── reports/                   # 生成的 Markdown 日报
├── scripts/                   # 运维脚本
└── docs/                      # 文档
```

## 技术栈

- Python 3.11+ / Tushare / pandas
- Next.js 15 / React 19 / Tailwind CSS / ECharts

## 常见问题

**报告显示"数据不足"？** 运行 `uv run python scripts/run_all.py --days 365` 积累足够历史数据。

**如何修改股票池？** 编辑 `config/pools.yaml`（记得更新 version 和 changelog），然后运行 `uv run python scripts/run_all.py`。

**Tushare 超时导致部分数据缺失？** 重新运行即可，系统有增量补缺和超时重试机制。

**前端显示数据异常？** 运行 `python3 scripts/validate_data.py` 校验，检查 `data/output/dashboard_view.json` 是否完整。

**定时任务不执行？** `chmod +x scripts/cron_update_data.sh`，检查路径配置和 cron 服务状态。

## 文档

| 文档 | 内容 |
|------|------|
| [CLAUDE.md](CLAUDE.md) | 协作流程、代码规范、禁止事项 |
| [docs/学习指南.md](docs/学习指南.md) | 概念学习路径 |
| [docs/产品架构设计.md](docs/产品架构设计.md) | 八层架构与数据流向 |
| [docs/技术实现.md](docs/技术实现.md) | 技术栈与模块目录 |
| [docs/核心逻辑.md](docs/核心逻辑.md) | 股票池模型与计算口径 |
| [docs/信号指标设计.md](docs/信号指标设计.md) | 五类 35+ 信号设计 |
| [docs/铂力特重定义.md](docs/铂力特重定义.md) | BLT 股票池配置方案 |
| [docs/历史分析设计.md](docs/历史分析设计.md) | 历史分析模块架构 |
| [docs/操盘工作台方案.md](docs/操盘工作台方案.md) | 前端工作台方案 |
| [docs/数据契约.md](docs/数据契约.md) | 数据规范与字段映射 |
