# Space-Intel 项目记忆

此文件用于存储跨会话的项目记忆，跟着项目版本控制走。

## 核心约定

### 运行命令
```bash
uv run python scripts/run_all.py        # 完整运行
uv run python -m src.price.run          # 行情数据线
uv run python -m src.news.run           # 新闻数据线
uv run python -m src.dailyreport.run    # 日报生成
```

### 数据流向
```
raw → normalized → processed → analytics → archive
```

### 模块版本
- analyzer: v2.1.1
- rolling_analyzer: v2.4
- event_layer: v1.0
- reporter: v2.5

## 股票池配置

| 分组 | 用途 |
|------|------|
| anchor | 铂力特 (688333.SH) - 核心标的 |
| core_universe | 核心观察池 (3只) |
| extended_universe | 扩展观察池 |
| research_core | 研究层对比基准 |

## 注意事项

- 使用 `Storage` 类访问数据目录
- 配置文件在 `config/` 目录
- 报告输出到 `reports/` 目录