"""
虚拟 ETF / 自定义指数 NAV 构建
====================================
从 pools.yaml 配置和归一化行情数据构建 ETF 类 NAV 指数，
计算锚定标的相对各指数的超额收益，并与旧口径对照。

输入（只读）：
  - config/pools.yaml
  - data/price/normalized/market_data_normalized.parquet
  - data/price/raw/market_data.parquet
  - data/output/history_summary.csv（仅用于对照）
  - data/output/history_rolling_metrics.csv（仅用于对照）

输出：
  - data/price/analytics/index_products/constant_universe_{version}/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.index_products.builder import build_all_indexes


def main():
    parser = argparse.ArgumentParser(description="虚拟 ETF / 自定义指数 NAV 构建")
    parser.add_argument("--rebalance-freq", default="monthly", choices=["monthly", "quarterly", "none"])
    parser.add_argument("--allow-stale-anchor", action="store_true", help="Anchor 缺最新日时仅警告，不中断")
    args = parser.parse_args()

    print("=" * 60)
    print("虚拟 ETF / 自定义指数 NAV 构建")
    print(f"  rebalance_freq = {args.rebalance_freq}")
    print(f"  allow_stale_anchor = {args.allow_stale_anchor}")
    print("=" * 60)

    summary = build_all_indexes(
        rebalance_freq=args.rebalance_freq,
        allow_stale_anchor=args.allow_stale_anchor,
    )

    # 打印摘要
    print("\n" + "=" * 60)
    print("验收摘要")
    print("=" * 60)

    print(f"\nAnchor: {summary.get('anchor', 'N/A')}")

    for idx_id, info in summary.get("indexes", {}).items():
        print(f"\n--- {idx_id} ---")
        print(f"  成员数量: {info['member_count']}")
        print(f"  起始日: {info['start_date']}")
        print(f"  结束日: {info['end_date']}")
        print(f"  最新 NAV: {info['latest_nav']:.4f}")
        print(f"  fresh_quote_ratio: {info['latest_fresh_quote_ratio']:.4f}")
        print(f"  universe_inclusion_ratio: {info['latest_universe_inclusion_ratio']:.4f}")
        print(f"  data_status: {info['latest_data_status']}")
        if info['latest_stale_symbols']:
            print(f"  stale_symbols: {info['latest_stale_symbols']}")
        for w in ["1d", "3d", "5d", "10d"]:
            ret = info.get(f"latest_index_return_{w}")
            if ret is not None:
                print(f"  index_return_{w}: {ret:.4f}%")

    excess = summary.get("latest_excess_vs_industry_chain", {})
    if excess:
        print(f"\n铂力特 vs industry_chain_index 超额:")
        for w in ["1d", "3d", "5d", "10d"]:
            val = excess.get(w)
            if val is not None:
                print(f"  excess_{w}: {val:.4f}%")

    comp = summary.get("legacy_comparison", {})
    if comp:
        print(f"\n新旧口径对照 (共同区间):")
        print(f"  overlap: {comp['overlap_start']} ~ {comp['overlap_end']} ({comp['overlap_n']} 天)")
        print(f"  相关系数: {comp['correlation']:.4f}")
        print(f"  MAE(1d): {comp['mae_1d']:.4f}")
        print(f"  最大差异(1d): {comp['max_diff_1d']:.4f}")

    print("\n[OK] 构建完成")


if __name__ == "__main__":
    main()
