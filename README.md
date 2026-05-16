# AnchorLink

锚定联动分析系统 — 锚定一家公司，与板块联动对比分析，自动生成每日复盘报告。

当前标的：铂力特 (688333.SH)

## 预览

> [在线体验完整 Demo](docs/demo.html) — 暗色主题，信号面板 + 历史分析 + 性格档案 + 时间轴

<!-- 截图占位：浏览器打开 docs/demo.html 截图后取消注释
<p align="center">
  <img src="docs/assets/demo-preview.png" width="80%">
</p>
-->

## 数据管道

四步管道，按顺序执行，每步依赖上一步输出：

```mermaid
flowchart LR
    A["行情拉取"] --> B["日报生成"]
    B --> C["历史分析"]
    C --> D["前端数据构建"]
```

统一入口：`uv run python scripts/run_all.py`

## 四类股票池

| 股票池 | 回答的问题 |
|--------|-----------|
| 核心同类 `direct_peers` | 业务可比公司今天强不强？ |
| 产业链 `industry_chain` | 上下游有没有同向变化？ |
| 主题情绪 `theme_pool` | 市场是不是在炒主题？ |
| 交易观察 `trading_watchlist` | 短期资金有没有切换？ |

五类 35+ 信号（Beta / Alpha / Volume / Rotation / Abnormal），每个信号带证据链，支持反直觉识别和象限条件效果分析。

## 快速开始

```bash
git clone <repo-url> && cd AnchorLink
cp .env.example .env
# 编辑 .env 填入 TUSHARE_TOKEN
uv sync

# 启动前端
cd web && npm install && npm run dev
# 访问 http://localhost:3000

# 更新数据
uv run python scripts/run_all.py
```

| Token | 用途 |
|-------|------|
| `TUSHARE_TOKEN` | 股票数据源（https://tushare.citydata.club） |
| `DASHSCOPE_API_KEY` | AI 筛选（可选） |

## 技术栈

Python 3.11+ / Tushare / pandas · Next.js 15 / React 19 / Tailwind CSS

## 文档

| 文档 | 内容 |
|------|------|
| [CLAUDE.md](CLAUDE.md) | 协作流程、代码规范、禁止事项 |
| [产品 Demo](docs/demo.html) | 在线体验完整界面 |
| [学习指南](docs/学习指南.md) | 概念学习路径 |
| [产品架构设计](docs/产品架构设计.md) | 八层架构与数据流向 |
| [技术实现](docs/技术实现.md) | 技术栈与模块目录 |
| [核心逻辑](docs/核心逻辑.md) | 股票池模型与计算口径 |
| [信号指标设计](docs/信号指标设计.md) | 五类 35+ 信号设计 |
| [铂力特重定义](docs/铂力特重定义.md) | BLT 股票池配置方案 |
| [历史分析设计](docs/历史分析设计.md) | 历史分析模块架构 |
| [操盘工作台方案](docs/操盘工作台方案.md) | 前端工作台方案 |
| [数据契约](docs/数据契约.md) | 数据规范与字段映射 |

## 常见问题

**报告显示"数据不足"？** 运行 `uv run python scripts/run_all.py --days 365` 积累足够历史数据。

**如何修改股票池？** 编辑 `config/pools.yaml`（记得更新 version 和 changelog），然后运行 `uv run python scripts/run_all.py`。

**Tushare 超时导致部分数据缺失？** 重新运行即可，系统有增量补缺和超时重试机制。

**前端显示数据异常？** 运行 `python3 scripts/validate_data.py` 校验，检查 `data/output/dashboard_view.json` 是否完整。
