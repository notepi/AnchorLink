# Claude Code 操作规约

本文件只写 Claude Code 执行红线。项目说明见 `README.md`，方法论和分析报告见 `docs/`。

## 统一入口

每日更新：

```bash
uv run python scripts/run_all.py --days 120
```

数据一致性失败：

```bash
uv run python scripts/run_all.py --days 120 --force-normalize
```

仅重跑 B 链：

```bash
uv run python scripts/run_research_chain.py --force
```

不要手工串脚本替代 `run_all.py`，除非用户明确要求单步调试。

## B 链不可跳步

固定顺序：

1. `build_custom_indexes.py`
2. `build_standard_index_excess_profile.py`
3. `build_standard_index_excess_decomposition.py`
4. `build_standard_index_qg_profile.py`
5. `build_benchmark_divergence_analysis.py`

任一步失败必须 fail-fast，不可静默当成功。

## 数据红线

- B 链开始前必须校验 anchor raw / normalized / dashboard 日期和 close。
- 校验失败必须停止；只有 `--force-normalize` 可先重跑 normalizer 再继续。
- 业务分析和指标计算只用 normalized。
- raw 只允许用于数据一致性校验。
- 不得仅凭 close 等于前一日 close 判断停牌。
- 有真实行情且 vol > 0 时，`anchor_suspended=False`。

## 主基准红线

- `industry_chain_index` 是主基准。
- `theme_pool` / `trading_watchlist` 只能用于辅助解释和分歧分析。
- Q×G 是画像，不是可交易回测。
- Oracle 空间指标不能写成实盘收益。

## 修改规则

- 修改 `config/pools.yaml` 必须更新 version 和 changelog。
- 修改展示术语先改 `docs/glossary.md`，再同步 `web/src/lib/glossary.ts`。
- 不可删除 `data/output/` 历史日报目录。
- 不可绕过 `PoolRegistry.validate()`。
- Python 必须绝对导入，不可用相对导入。

## 前端规则

改前端后清 `.next`，重启 dev server，并验证页面不报错。

## 验收

- 数据链修改后检查最新日期。
- B 链重跑后确认 `anchor_index_excess` / `qg_signal_daily` / `benchmark_divergence` / `dashboard_view` 同步到最新。
- 前端修改后必须 build 或启动验证。
