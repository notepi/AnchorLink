# 多维度估值评估改进计划

## 背景

当前估值标签基于 PE_TTM 绝对阈值（>100 高估值），存在问题：
- 未考虑行业特性：科创板成长股 PE 普遍 100+
- 无历史对比：无法判断当前估值处于自身什么位置
- 单一指标：PB、PS_TTM 已获取但未使用

用户需求：
1. 行业内估值对比（板块相对位置）
2. 自身历史分位
3. 多指标综合标签（PE、PB、PS）

## 数据现状

| 项目 | 状态 |
|------|------|
| PE_TTM、PB | 已使用 |
| PS_TTM | 已获取存于 daily_basic.parquet，未提取 |
| daily_basic 数据量 | 铂力特约 6 年历史 |
| 板块股票池 | core_universe 3 只 |

**关键差距**：daily_basic 只获取 anchor，板块其他股票无估值数据。

## 实现方案

### Step 1: 扩展数据获取

**修改**: `src/price/fetcher.py`

- 新增 `_fetch_daily_basic_all()` 函数
- 获取 anchor + core_universe 共 4 只股票的 daily_basic
- 合并保存为单一 parquet 文件

### Step 2: 新增估值计算函数

**修改**: `src/price/analyzer.py`

新增三个函数：

```python
def _compute_sector_valuation(anchor_code, daily_basic_df, core_codes, latest_date):
    """板块内估值对比"""
    # 输出: sector_pe_mean, pe_vs_sector, pe_sector_position(偏高/适中/偏低)

def _compute_valuation_percentile(anchor_code, daily_basic_df, latest_date, lookback=60):
    """历史分位计算"""
    # 输出: pe_percentile_60d, pe_percentile_label(高位/中位/低位)

def compute_multi_metric_label(...):
    """多指标综合标签"""
    # 输出: valuation_score, valuation_label, valuation_detail
```

**评分规则**：
- 板块位置：偏高+1 / 适中0 / 偏低-1
- 历史分位：高位+1 / 中位偏上+0.5 / 中位0 / 中位偏下-0.5 / 低位-1
- 权重：PE 0.5 / PB 0.3 / PS 0.2
- 板块权重 0.4 + 历史分位权重 0.6

### Step 3: 更新数据加载

**修改**: `src/price/analyzer.py` 的 `_load_daily_basic()`

- 提取 `ps_ttm` 字段（当前未提取）
- 支持多股票数据分离

### Step 4: 更新报告展示

**修改**: `src/dailyreport/reporter.py`

- 状态面板：估值标签增加简要说明
- 核心指标章节：新增估值分析表格

```markdown
## 估值分析

| 指标 | 当前值 | 板块均值 | 板块位置 | 近60日分位 |
|------|--------|----------|----------|------------|
| PE_TTM | 113.2 | 45.3 | 偏高 | 78% (中位偏上) |
| PB | 4.77 | 3.21 | 适中 | 65% (中位偏上) |
| PS_TTM | 12.1 | 5.8 | 偏高 | 82% (高位) |

> 综合估值: 估值偏高（PE板块偏高+历史高位，PB适中）
```

## 关键文件

| 文件 | 修改内容 |
|------|----------|
| `src/price/fetcher.py` | 扩展 daily_basic 获取范围 |
| `src/price/analyzer.py` | 新增 3 个估值函数，更新 _load_daily_basic |
| `src/dailyreport/reporter.py` | 更新估值展示格式 |

## 验证方法

```bash
# 运行完整流程
uv run python scripts/run_all.py

# 检查报告
cat reports/$(date +%Y%m%d)_blt_review.md

# 验证要点：
# 1. 估值分析表格出现
# 2. 板块均值、分位数据正确
# 3. 综合标签合理
```

## 边界情况处理

- PE ≤ 0（亏损）：标签显示"亏损状态"，不参与评分
- 板块数据不足：显示"板块数据不足"
- 历史数据 < 20 天：显示"历史数据不足"