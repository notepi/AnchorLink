# 虚拟指数超额方法论

## 1. 为什么每日中位数累计不能作为严格的多日超额

旧口径定义：

```
daily_excess(t) = anchor_return(t) - industry_chain 当日涨跌幅中位数
excess_5d / excess_10d = daily_excess 的简单累计
```

问题：每天的中位数可能由不同股票贡献。连续累加每日中位数差值，不等于相对一个连续可投资基准组合的收益。例如：

- 第 1 天中位数由 A 股贡献，第 2 天由 B 股贡献
- 累加 A 的收益差 + B 的收益差，不等于相对任何固定组合的超额
- 这种累加只能定义为"中位数累计位移"，不具备组合可投资性

## 2. 为什么保留旧指标作为中位数位移温度计

旧指标有信号价值：它反映了 Anchor 相对板块中位数的日度偏离方向和幅度。

保留方式：
- 旧字段 `daily_excess` / `excess_5d` / `excess_10d` 保持只读
- 在新旧对照文件中重命名为 `median_displacement_1d` / `median_displacement_5d` / `median_displacement_10d`
- 它们是辅助温度计，不是正式指数超额

## 3. 四条指数各自职责

| 指数 ID | 职责 | 角色 |
|---------|------|------|
| `industry_chain_index` | 商业航天硬科技产业链主基准 | **正式主基准** |
| `direct_peers_index` | 增材制造本业确认辅助指数 | 同业确认 |
| `theme_pool_index` | 商业航天主题情绪温度指数 | 情绪解释 |
| `trading_watchlist_index` | 短线交易风向指数 | 交易解释 |

四条指数独立构造，不合并为一个总指数。每条指数反映不同的分析维度。

## 4. 主基准为什么是 industry_chain_index

`industry_chain_index` 是正式主基准，原因：

1. 它覆盖 Anchor 所在的完整产业链（商业航天硬科技），而非仅同业
2. 该池 `can_be_benchmark=True`，经过专门设计
3. 成员数量充足（industry_chain 池共 11 只，其中 10 只纳入 benchmark，600343.SH 仅用于 ranking，不进入指数），具备统计意义
4. 与 Anchor 的业务关联度最高

`direct_peers_index` 用于确认同业相对位置，`theme_pool_index` 和 `trading_watchlist_index` 用于解释市场情绪和交易行为。

## 5. 虚拟指数成员、权重、再平衡、停牌估值规则

### 5.1 成员选择

| 指数 | 筛选条件 |
|------|---------|
| `industry_chain_index` | universe_id=industry_chain, enabled=True, include_in_benchmark=True |
| `direct_peers_index` | universe_id=direct_peers, enabled=True, include_in_benchmark=True |
| `theme_pool_index` | universe_id=theme_pool, enabled=True, include_in_ranking=True |
| `trading_watchlist_index` | universe_id=trading_watchlist, enabled=True, include_in_ranking=True |

### 5.2 权重

三种权重：
- `raw_config_weight`：pools.yaml 中的原始配置权重（如 0.8）
- `normalized_target_weight`：归一化后目标权重 = raw_config_weight / sum(成员 raw_config_weight)
- `actual_weight`：每日实际权重 = units × close / NAV（随价格漂移）

调仓时只对已纳入成员重新归一化：`effective_target_weight = raw_config_weight / sum(已纳入成员 raw_config_weight)`

### 5.3 NAV 计算

```
base_level = 1000
units_i(base_date) = 1000 × effective_target_weight_i / close_i(base_date)
NAV(t) = sum(units_i × close_i(t))
```

每条指数独立确定 base_date：首个满足 `included_member_count >= min_size` 且 `universe_inclusion_ratio >= 0.8` 的交易日。

### 5.4 再平衡

月频再平衡（可参数化为 quarterly 或 none）：

- 再平衡日：每月第一个交易日
- 生效时点：`rebalance_at = close`，`effective_from = next_trading_day`
- 再平衡日当天 NAV 用旧 units 计算，收盘后更新 units
- NAV 连续性保证：`sum(new_units_i × close_i) = NAV`

迟到成员纳入时执行全量连续再平衡：对所有已纳入成员（含新成员）统一重算 units。如果迟到成员加入日恰好也是月初，只执行一次全量再平衡。

### 5.5 停牌估值

报价状态三分类：
- `fresh`：当日真实成交报价
- `carried_forward`：normalizer forward-fill 的补齐报价
- `zero_volume_raw`：raw 中有记录但零成交

非 fresh 报价视为 stale，使用上一有效 close 估值。NAV 不会因停牌变成 NaN。

再平衡日遇到 stale 成员时仍使用其 forward-filled close 参与计算，但标记 `rebalance_uses_stale_price = true`。本产品是估值型研究指数，不代表该组合能够按 stale 价格真实成交。

## 6. 标准 1D / 3D / 5D / 10D 超额公式

```
anchor_return_Nd = anchor_close(t) / anchor_close(t-N) - 1
index_return_Nd  = index_nav(t)    / index_nav(t-N)    - 1
excess_vs_index_Nd = anchor_return_Nd - index_return_Nd
```

输出统一使用百分比口径（× 100）。前 N-1 天 `excess_Nd` 为空。

## 7. 数据质量规则

| 检查 | 失败行为 |
|------|---------|
| (ts_code, trade_date) 唯一 | raise ValueError |
| 已纳入成员 close 无 null/≤0 | raise ValueError |
| anchor 覆盖最新交易日 | raise ValueError（可 allow_stale_anchor=True 降级为警告） |
| fresh_quote_ratio + universe_inclusion_ratio | data_status 降级 |
| raw 与 normalized 最新日同步 | 警告 |

覆盖率降级：
- `fresh_quote_ratio >= 0.8` 且 `universe_inclusion_ratio >= 0.8` → ok
- `fresh_quote_ratio >= 0.5` 且 `universe_inclusion_ratio >= 0.5` → partial
- 其他 → insufficient_data

## 8. 新旧口径如何并行

- 旧 `daily_excess` / `excess_5d` / `excess_10d` 保持只读，不覆盖
- 新指数超额写入独立目录 `data/price/analytics/index_products/`
- 新旧对照文件 `legacy_vs_index_excess_comparison.csv` 按日期 inner join，报告共同区间
- 旧指标在新对照中重命名为 `median_displacement_1d/5d/10d`
- 新指标为 `index_excess_1d/3d/5d/10d`

## 9. 固定股票池研究视图声明

**本产品不是 point-in-time 实盘回放。本产品是 constant-universe research view。**

使用当前 pools.yaml 配置回算历史，无法证明历史时点就使用这些成员和权重。输出中所有文件包含以下元数据：

- `universe_mode = constant_universe_research_view`
- `pool_config_version`：配置版本
- `price_adjustment_mode = qfq`：前复权
- `source_data_as_of`：行情数据截止日
- `build_mode = full_rebuild`：每次完整重建
- `generated_at`：生成时刻

前复权行情在公司行为发生后历史价格可能重算，因此每次生成必须完整重建，不能只追加最新 NAV。
