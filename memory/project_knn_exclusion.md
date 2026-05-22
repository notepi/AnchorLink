---
name: project-knn-exclusion
description: kNN prediction in 2nd-order analysis is statistically worse than random — must be excluded when integrating into dashboard or /today page
metadata:
  type: project
---

kNN相似度加权预测（`history_2nd_order_analysis.json` 的 `knnSignal` 字段）方向命中率仅 48.5%，低于随机基准（50%），且 Q5（预测最高收益档）实际产生最差收益（-0.62%）。

已在 `scripts/analyze_2nd_order_signals.py` E. 节（第255行附近）添加 `[WARNING]` 注释。

**Why:** 该信号不仅无效，且反向有害——投资者若依赖它反而会亏损，必须防止其进入用户可见的判断界面。

**How to apply:** 当把 `history_2nd_order_analysis.json` 的字段接入 `build_dashboard_view.py` 或 `/today` 页面时，**必须跳过 `knnSignal` 字段**，或在 UI 上显著标注"不建议使用"。应优先使用的替代信号：
- 复合得分 `compositeScore`（Pearson r=0.222）
- 二元路径标签 `gram2`
- 三周期一致性信号 `consensus`
