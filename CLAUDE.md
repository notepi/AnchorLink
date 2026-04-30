# AnchorLink - 锚定联动分析系统

锚定一家公司，与板块联动对比分析。当前标的：铂力特 (688333.SH)。

## 协作流程

严格按以下顺序执行：
1. 用户定任务
2. Claude 做 plan → 写入 `.claude/plans/active/`
3. 用户确认 plan
4. Claude 执行
5. 测试验证
6. **用户确认测试通过后**，Claude 才能修改 CLAUDE.md
7. plan 归档到 `.claude/plans/archive/`


## 操作指令

### 每日更新

```bash
uv run python scripts/run_all.py
```

### 独立模块

```bash
uv run python -m src.price.run       # 行情数据线
uv run python -m src.news.run        # 新闻数据线
uv run python -m src.dailyreport.run # 日报生成
```

## 数据说明

### 文件位置

| 目录 | 内容 |
|------|------|
| data/price/ | 行情数据（raw/normalized/processed/analytics） |
| data/news/ | 新闻数据 |
| archive/metrics/ | 指标归档（近5日连续性计算） |
| archive/events/ | 事件归档 |
| reports/ | 生成的日报 |

### 数据接口

统一使用 Tushare，配置 `.env`:

```
TUSHARE_TOKEN=xxx
```

## 文档索引

| 文档 | 内容 |
|------|------|
| docs/usage.md | 使用说明（快速上手） |
| docs/prd.md | 产品需求文档（开发视角） |
| docs/prd_business_review.md | 业务方案评审（业务视角） |
| docs/file_structure.md | 项目目录结构 |
| docs/field_glossary.md | 指标字典（85个字段） |
| docs/pool_governance.md | 股票池治理规范 |