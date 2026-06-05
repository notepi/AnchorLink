# AnchorLink

锚定联动分析系统。锚定一家公司，与板块联动对比分析。当前标的：铂力特 (688333.SH)。

当前阶段：V2 评分系统已固化（src/technical_indicators + src/regime_detector + src/v2_scorer → build_v2_scoring.py → /v2 页面）。历史数据已扩展到 365 天。

## 协作流程

1. 用户定任务
2. Claude 做 plan → 写入 `.claude/plans/active/`
3. 用户确认 plan
4. Claude 执行
5. 测试验证
6. **用户确认测试通过后**，Claude 才能修改 CLAUDE.md
7. plan 归档到 `.claude/plans/archive/`

## 数据管道

### 执行顺序

```
A链: price → dailyreport → history → v2 → daily_report → 二阶 → composite → deep_quant → excess_grade
B链: custom_indexes → standard_excess_profile → decomposition → qg_profile → divergence
汇合: A+B → dashboard_view → 漂移检测 → 自动校准
```

任何步骤失败则管道失败（退出码 1），不可静默当成功。

### 入口与参数

```bash
uv run python scripts/run_all.py                        # 轻量手动运行（--days 60）
uv run python scripts/run_all.py --days 120             # 人工日更/cron 推荐
uv run python scripts/run_all.py --days 365             # 新增股票或补历史
uv run python scripts/run_all.py --skip-research        # 跳过B链
uv run python scripts/run_all.py --force-research       # 强制重跑B链（规则变了但日期没变时用，A链必须成功）
uv run python scripts/run_research_chain.py             # 仅B链
uv run python scripts/run_research_chain.py --force     # 强制重跑B链
uv run python scripts/run_research_chain.py --check-only # 只检测是否滞后
```

`--days` 是最低覆盖窗口，不是每天重拉 N 天。fetcher 增量补缺：已有数据到 max_date → 只拉之后的新数据。

- `--days 60`（默认）：轻量手动运行
- `--days 120`：人工日更 / cron 推荐
- `--days 365`：新增股票或补历史

`--allow-noncritical-fail`：漂移检测/校准失败不阻断管道。**仅开发调试用，生产日更禁止使用。**

V2 评分脚本需用 `-m` 运行：`uv run python -m scripts.build_v2_scoring`

### 定时任务

`scripts/cron_update_data.sh` 调用 `run_all.py`，失败即停，校验通过才备份。不可自建管道绕过 `run_all.py`。

## 代码规范

- Python：snake_case 变量/函数，PascalCase 类，绝对导入 `from src.module import ...`
- TypeScript：camelCase 变量/函数，PascalCase 类型/组件，`@/` 路径别名
- JSON 字段：camelCase（Python 端在 build_dashboard_view.py 转换）
- 日期格式：内部 `YYYYMMDD` 字符串，显示 `YYYY-MM-DD`，禁止 Date 对象入 JSON
- 错误处理：`raise ValueError()` / `raise FileNotFoundError()` + `from e` 链式
- 日志：`print()` 加 `[INFO]`/`[OK]`/`[WARN]`/`[ERROR]` 前缀，不用 logging 模块
- 数据类：`@dataclass(frozen=True)`，不可变

## 术语管理

所有池名称、状态标签、路径标签的展示文本以 `docs/glossary.md` 为唯一口径，代码常量在 `web/src/lib/glossary.ts`。

- 修改展示术语前，先更新 `docs/glossary.md`，再同步到 `glossary.ts`
- 不可在组件中硬编码池名称或状态标签的展示文本，必须从 `glossary.ts` 引用

## 前端开发

- 修改前端代码后，必须清 `.next` 缓存再重启 dev server：`rm -rf web/.next && npx next dev`
- `npm run build` 通过不代表 dev server 没问题，改模块结构（新增/删除文件、改 import）后 webpack 缓存可能损坏导致 Internal Server Error
- 重启后用 `curl` 验证页面不返回错误，再告知用户去浏览器验证

## 禁止事项

- 不可直接读取 `data/price/raw/`，必须走 normalizer → normalized
- 不可跳过 PoolRegistry.validate()，配置变更后必须校验
- 不可修改 `config/pools.yaml` 不更新 version 和 changelog
- 不可把 theme_pool / trading_watchlist 用于 benchmark 计算
- 不可跳步执行数据管道（信号依赖池状态，池状态依赖行情数据）
- 不可删除 `data/output/` 下的历史日报目录（回测依赖）
- 不可用 Python 相对导入，必须绝对导入
