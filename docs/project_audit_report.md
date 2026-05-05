# AnchorLink 项目审计问题报告

> 审计日期：2026-05-05  
> 审计范围：Python 数据管线、`config/pools.yaml` 股票池配置、每日输出、Next.js Web 展示与配置编辑器、项目文档与质量门禁。  
> 审计目标：判断当前实现是否支撑“核心股票池 / Universe 配置、状态计算、轮动比较、报告展示、可视化动态配置”的产品目标。

## 结论摘要

项目已经有可运行的 MVP：Python 测试通过、日报可生成、Web build 通过、`/pools` 配置工作台可读写 `config/pools.yaml`。

但当前离“股票池体系闭环”还有明显差距。最高优先级的问题集中在三点：

1. `state`、`benchmark`、`rotation` 三种口径没有真正拆开，导致主题池和交易观察池虽然在配置里存在，但核心计算里基本被排除。
2. 输出层把部分数据异常隐藏成 `ok`，页面和报告容易给出过度确定的结论。
3. Web 动态配置已经暴露了新字段，但 Python 后端尚未消费这些字段，用户保存配置后可能以为生效，实际计算不变。

## 验证结果

| 检查项 | 结果 | 说明 |
|---|---:|---|
| Python 测试 | 通过 | `uv run pytest -q`，197 passed |
| Web 构建 | 通过 | `npm run build` 成功 |
| TypeScript | 通过 | `npx tsc --noEmit` 成功 |
| 日报生成 | 通过但有业务异常 | `uv run python -m src.dailyreport.run --date 20260430` 成功，但池子状态为 `partial` |
| Web lint | 失败 | `npm run lint` 进入 Next ESLint 初始化交互，无法作为 CI 门禁 |
| Python lint | 未配置 | `uv run ruff check .` 失败：未安装 `ruff` |
| npm audit | 未完成 | `npm audit --omit=dev` 因网络/TLS 连接失败，结果不确定 |
| 明文密钥扫描 | 未发现真实密钥 | 只发现 `TUSHARE_TOKEN=xxx` 等占位示例和环境变量读取 |

## 问题清单

| ID | 优先级 | 模块 | 问题 |
|---|---|---|---|
| A-01 | P1 | 核心计算 | PoolState 用 benchmark 口径计算所有池子状态，主题池/交易池状态为空 |
| A-02 | P1 | 组间轮动 | GroupRotation 只比较 `can_be_benchmark=true` 的池子，主题/交易轮动缺失 |
| A-03 | P1 | 输出质量 | 日报管线为 `partial`，JSON 却输出 `data_quality.status=ok` |
| A-04 | P1 | 配置闭环 | Web 已写 `include_in_state/include_in_rotation`，Python 后端完全忽略 |
| A-05 | P2 | CSV 输出 | `peer_matrix.csv` 给每个成员重复写入 Anchor 的排名，容易误导 |
| A-06 | P2 | Web/API | `/api/config` 无认证直接改本地 YAML，若部署会变成配置写入风险 |
| A-07 | P2 | Web 展示 | 报告页读取 `reports/<date>`，但日报实际写到 `data/output/<date>` |
| A-08 | P2 | 工程质量 | ESLint 未配置，`npm run lint` 不能在 CI/审计中使用 |
| A-09 | P2 | 工程结构 | 根目录和 `web/` 双 package/lockfile 导致 Next workspace root 警告 |
| A-10 | P2 | 旧配置残留 | `stocks.yaml/news_sources` 等旧结构仍在 README 和部分代码中出现 |
| A-11 | P3 | 数据获取 | `tushare_proxy.py` 放在根目录，`src/price/fetcher.py` 通过 `sys.path` 引入 |
| A-12 | P3 | 测试覆盖 | 测试覆盖“能跑”，但缺少核心业务口径回归断言 |

## 详细问题

### A-01 PoolState 用 Benchmark 口径计算所有池子状态

**优先级：P1**

证据：

- `src/pool_state/calculator.py:104-120`：单个 universe 状态计算直接使用 `registry.get_benchmark_scope(universe_id)`。
- `config/pools.yaml` 中 `theme_pool` 和 `trading_watchlist` 的成员均为 `include_in_benchmark: false`。
- 实测 `20260430` 输出：`theme_pool_return_median: null`。

影响：

- 主题情绪池、交易观察池虽然存在于配置和页面中，但不参与池子状态计算。
- 用户会看到“有股票池、有成员”，但行业状态只来自核心同类池/产业链池。
- 这与当前核心设计“Benchmark 只是对照口径，不等于状态口径”不一致。

建议：

- 在 Python `Membership` 中增加 `include_in_state`。
- 新增 `PoolRegistry.get_state_scope()`。
- `PoolStateCalculator` 改用 state scope，而不是 benchmark scope。
- Benchmark 只用于“铂力特相对谁跑赢/跑输”的对照，不应决定池子是否有状态。

### A-02 GroupRotation 排除了主题池和交易观察池

**优先级：P1**

证据：

- `src/group_rotation/rotation_analyzer.py:145-149`：如果 universe `can_be_benchmark=false`，直接跳过。
- 当前配置里 `theme_pool`、`trading_watchlist` 都是 `can_be_benchmark: false`。
- 实测 group rotation 只输出：`['industry_chain', 'direct_peers']`。

影响：

- “产业链强、主题强、交易观察强”这种轮动图景无法出现。
- 交易观察池的短线强弱、主题情绪池的热度变化无法进入组间比较。
- 当前 rotation 名义上比较四类池子，实际只比较两个 benchmark 池。

建议：

- 引入独立 `include_in_rotation` 口径。
- GroupRotation 使用 rotation scope，而不是 `can_be_benchmark`。
- `can_be_benchmark` 只表示能否作为 Anchor 对照基准。

### A-03 输出层隐藏了 `partial` 数据状态

**优先级：P1**

证据：

- 日报运行日志显示：`池子状态计算完成: 4 个池子, 状态=partial`。
- 但 `data/output/20260430/industry_snapshot.json` 中 `data_quality.status` 为 `ok`。
- `src/output/json_writer.py:59-80` 的 `build_data_quality()` 只从 `SignalResult` 生成质量状态，没有聚合 `PoolStateResult` 或 `GroupRotation` 的状态。

影响：

- 用户看到 JSON/Web 可能认为数据完整，但实际主题池状态为空、资金流为空、轮动不完整。
- 后续信号和报告会在缺数据情况下显得过于确定。

建议：

- `IndustrySnapshot.data_quality` 应聚合：
  - `pool_result.overall_status`
  - 每个 `PoolState.data_status`
  - `RelativeStrength.data_status`
  - `GroupRotation.data_status`
  - `SignalResult.data_status`
- 只要任一核心层为 `partial`，总状态至少应为 `partial`。

### A-04 Web 配置写入的新字段后端不生效

**优先级：P1**

证据：

- Web API 会写入 `include_in_state`、`include_in_rotation`：`web/src/app/api/config/route.ts:20-35`。
- Web 类型也定义了这两个字段：`web/src/types/index.ts:154-168`。
- 但 Python `Membership` dataclass 没有这两个字段：`src/config/loader.py:42-56`。
- Python 解析 membership 时也没有读取这两个字段：`src/config/loader.py:159-175`。

影响：

- 用户在 `/pools` 勾选 state/rotation 并保存后，会以为配置已生效。
- 实际 Python 计算仍只看 `include_in_benchmark/include_in_ranking/include_in_report`。
- 这是典型的“配置 UI 领先于业务引擎”的断层。

建议：

- 同步 Python schema、TS schema、YAML schema。
- 增加配置加载测试，断言 `include_in_state`、`include_in_rotation` 被解析并用于对应 scope。
- 在字段未接入前，UI 应标注“尚未进入计算”或暂时隐藏。

### A-05 `peer_matrix.csv` 成员排名字段误导

**优先级：P2**

证据：

- `src/output/csv_writer.py:145-174` 的 `_get_ranking_data(symbol, universe_id, anchor_positions)` 并没有使用 `symbol`。
- 只要该 universe 有 AnchorPosition，就把 Anchor 的 `rank_return` 返回给每个成员。
- 实测 `peer_matrix.csv` 中主题池和交易观察池多行都显示相同 `return_rank=2`。

影响：

- 用户可能误以为每个成员自己的收益排名都是 2。
- CSV 作为“数据检查”文件会误导人工复核。

建议：

- 如果当前只支持 Anchor 排名，则字段名改为 `anchor_return_rank`，并只在 Anchor 行输出。
- 更好的方案是计算每个 symbol 在对应 universe 的真实排名。

### A-06 `/api/config` 缺少认证和部署保护

**优先级：P2**

证据：

- `web/src/app/api/config/route.ts:231-239` 允许任意 PATCH 修改 `config/pools.yaml`。
- 当前没有鉴权、CSRF、防部署环境保护。

影响：

- 本地开发可接受。
- 如果 Web 被部署或暴露到内网/公网，会变成配置篡改入口。

建议：

- 明确该接口只允许 `NODE_ENV=development` 或本地回环地址。
- 若需要生产使用，加入认证、CSRF、防并发写、审计日志和版本备份。

### A-07 报告页和日报输出目录不一致

**优先级：P2**

证据：

- Python 输出：`src/output/__init__.py:97-120` 写入 `data/output/<date>/industry_report.md`。
- Web 报告读取：`web/src/lib/data-reader.ts:172-219` 读取 `reports/<date>/*.md`。
- 当前 `reports/` 目录为空，历史报告文件在 git 状态里大量删除。

影响：

- 日报生成成功后，`/industry-report` 和 `/reports` 不一定能看到最新报告。
- 用户会以为“没有报告数据”，但实际报告在 `data/output`。

建议：

- Web 报告页改读 `data/output/<date>/industry_report.md`。
- 或者日报生成后同步一份到 Web 读取的 `reports/<date>/`。
- 推荐统一为 `data/output`，减少双目录心智负担。

### A-08 Lint 门禁不可用

**优先级：P2**

证据：

- `npm run lint` 执行 `next lint`。
- 当前 Next 15 下该命令进入交互式 ESLint 初始化，退出码为 1。

影响：

- CI 无法稳定执行 lint。
- 代码风格、潜在 React/Next 问题无法被门禁捕捉。

建议：

- 增加 ESLint 配置。
- 把脚本改为 `eslint .`。
- 同步迁移 Next 官方推荐配置。

### A-09 Node 工作区结构混乱

**优先级：P2**

证据：

- 根目录有 `package.json/package-lock.json`，只包含 `autoprefixer`。
- `web/` 内也有完整 `package.json/package-lock.json`。
- Next build 多次警告 workspace root 推断不正确。

影响：

- Next 的 output tracing root 不稳定。
- 开发态 `.next` CSS 曾出现 404，和 dev/build 混写、root 推断异常高度相关。
- 新开发者会困惑到底应该在根目录还是 `web/` 安装依赖。

建议：

- 如果 Web 是独立应用，移除根目录 Node package 或改成明确 workspace。
- 在 `web/next.config.ts` 设置 `outputFileTracingRoot`。
- 将 `.next`、`out`、`node_modules` 明确加入 `.gitignore`。

### A-10 旧配置和旧文档残留

**优先级：P2**

证据：

- `README.md:52-56` 仍提到 `src.news.run`。
- `README.md:63-97` 仍描述 `stocks.yaml/news_sources.yaml/src/news`。
- `src/shared/config.py:127-145` 仍提供 `get_news_sources()` 和 `get_catalyst_rules()`。
- `src/dailyreport/review_stock_pool.py` 仍读取 `config/stocks.yaml` 和旧分层字段。

影响：

- 用户会在 `pools.yaml`、`stocks.yaml`、文档里的 news/catalyst 之间来回迷路。
- 老代码和新核心逻辑并存，后续修改容易改错地方。

建议：

- 明确宣布 `pools.yaml` 是唯一核心股票池配置。
- 删除或迁移旧 `stocks.yaml` 相关入口。
- README 改成当前真实结构。

### A-11 Tushare proxy 结构需要收敛

**优先级：P3**

证据：

- `src/price/fetcher.py:23-26` 通过 `sys.path.insert()` 从项目根目录导入 `tushare_proxy.py`。
- `tushare_proxy.py` 在根目录，不在 `src/` 包内。

影响：

- 包结构不标准，部署、测试、打包时容易受工作目录影响。

建议：

- 将 `tushare_proxy.py` 移入 `src/price/tushare_proxy.py` 或 `src/integrations/tushare_proxy.py`。
- 删除 `sys.path.insert()`。

### A-12 测试通过但没有覆盖核心业务断言

**优先级：P3**

证据：

- 测试 197 条通过。
- 但当前实际输出仍存在：
  - `pool_result.overall_status=partial`
  - `snapshot.data_quality.status=ok`
  - `theme_pool_return_median=null`
  - rotation 只剩 direct/chain
  - CSV 每行重复 Anchor 排名

影响：

- 测试证明“代码可运行”，但不能证明“产品目标成立”。

建议：

- 增加基于 `config/pools.yaml` 的业务回归测试：
  - 主题池开启 state 后必须有 median。
  - 交易观察池开启 rotation 后必须进入 group_rotation。
  - pool partial 必须传递到 snapshot data_quality。
  - peer_matrix 非 Anchor 成员不得复用 Anchor rank。

## 建议整改路线

### 第一阶段：核心口径闭环

目标：让 `pools.yaml` 的配置真正驱动计算。

1. Python `Membership` 增加 `include_in_state`、`include_in_rotation`。
2. `PoolRegistry` 增加 `get_state_scope()`、`get_rotation_scope()`。
3. `PoolStateCalculator` 改用 state scope。
4. `GroupRotation` 改用 rotation scope。
5. 新增核心口径回归测试。

### 第二阶段：输出可信度修复

目标：报告和页面不要隐藏不完整数据。

1. `DataQuality` 聚合所有层状态。
2. `peer_matrix.csv` 修正排名字段。
3. `industry_report.md` 标出 partial 原因。
4. Web Dashboard 明确显示数据质量。

### 第三阶段：Web 与后端配置一致

目标：用户在 `/pools` 保存的东西必须改变计算结果。

1. 同步 TS/Python/YAML schema。
2. `/api/config` 增加 dev-only/认证保护。
3. 配置保存后支持“一键重新生成日报”或提示运行命令。
4. 报告页改读 `data/output`。

### 第四阶段：工程收敛

目标：减少新开发者和未来自己的心智负担。

1. 修复 ESLint。
2. 配置 Python lint。
3. 整理 Node workspace。
4. 删除旧 news/stocks 文档和入口，或明确标记为 legacy。
5. 增加 `.gitignore` 和产物清理策略。

## 当前可用程度判断

| 能力 | 当前状态 |
|---|---|
| Python 日报生成 | 可用，但业务口径不完整 |
| Web Dashboard | 可用，依赖已有 `data/output` |
| `/pools` 可视化配置 | 可用，但部分字段后端未接入 |
| 核心股票池状态 | 部分可用，仅 direct/chain 较可靠 |
| 主题池/交易池状态 | 不可靠，核心状态被 benchmark 口径排空 |
| 组间轮动 | 部分可用，仅比较 direct/chain |
| 报告展示 | 目录未统一，Web 报告页看不到日报生成物 |
| 生产部署 | 不建议，需先处理配置写入安全和质量门禁 |

## 审计结论

AnchorLink 已经不是空架子，数据管线、配置模型、输出文件、Web 展示都已经有基础形态。

但当前最核心的问题是：**项目已经开始用 Universe/Scope 的方式表达股票池，却没有把 scope 彻底贯彻到 Python 计算层和输出层。**

下一步不建议继续堆页面功能，应该先修核心口径：

1. state scope
2. benchmark scope
3. ranking scope
4. report scope
5. rotation scope

这五个口径闭环后，`pools.yaml` 才真正成为项目的核心股票池配置中心。
