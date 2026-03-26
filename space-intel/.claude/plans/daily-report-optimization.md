# 日报系统优化计划

## 背景
日报系统存在三个问题影响报告质量：
1. 近5日状态不可用（归档数据不足）
2. 研究层对比不可用（fetcher 未获取 research_core 数据）
3. 信号判断模板化（"今日关注信号"文字与实际矛盾）

## 状态：✅ 已完成

### 1. 近5日状态不可用

**方案**: 运行 backfill 回填历史数据
```bash
uv run python -m src.backfill --days 10
```

**结果**: ✅ 已回填 6 天归档数据

### 2. 研究层对比不可用

**方案**: 修改 `src/price/fetcher.py` 添加 research_core 支持

**结果**: ✅ 已修改，成功获取华曙高科、中天火箭数据

### 3. 信号判断模板化

**方案**: 修改 `src/dailyreport/reporter.py` 动态生成信号描述

**结果**: ✅ 已修改，现在根据板块涨跌和相对强弱动态生成

## 修改的文件
- `space-intel/src/price/fetcher.py`
- `space-intel/src/dailyreport/reporter.py`

## 验证结果
- 近5日状态：完整显示5日趋势
- 研究层对比：正常显示对比表
- 今日关注信号：与实际涨跌情况一致