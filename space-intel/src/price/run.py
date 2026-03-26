"""
行情数据线入口
运行完整的行情数据处理流程

用法：
    python -m src.price.run
"""

import sys

from src.price.fetcher import fetch_market_data
from src.price.normalizer import normalize
from src.price.analyzer import analyze_anchor_symbol, save_metrics
from src.price.data_product import build_price_data_product


def main():
    """运行行情数据线完整流程"""
    print("=" * 60)
    print("行情数据线 - 开始运行")
    print("=" * 60)

    # Step 1: 获取数据
    print("\n[Step 1/7] 获取市场数据...")
    try:
        df = fetch_market_data()
        if df.empty:
            print("[ERROR] 未获取到数据，流程终止")
            return 1
    except Exception as e:
        print(f"[ERROR] 获取数据失败: {e}")
        return 1

    # Step 2: 标准化
    print("\n[Step 2/7] 数据标准化...")
    try:
        normalize()
    except Exception as e:
        print(f"[ERROR] 标准化失败: {e}")
        return 1

    # Step 3: 构建数据产品
    print("\n[Step 3/7] 构建价格数据产品...")
    try:
        product = build_price_data_product()
        print(f"[INFO] 数据产品状态: {product.get('overall_status')}")
    except Exception as e:
        print(f"[WARN] 数据产品构建失败（不影响主流程）: {e}")

    # Step 4: 计算指标
    print("\n[Step 4/7] 计算分析指标...")
    try:
        result = analyze_anchor_symbol()
        save_metrics(result)
        print(f"[INFO] 分析完成，日期: {result['trade_date']}")
    except Exception as e:
        print(f"[ERROR] 指标计算失败: {e}")
        return 1

    # Step 5: 连续观察层
    print("\n[Step 5/7] 计算连续观察指标...")
    try:
        from src.price.rolling_analyzer import compute_rolling_metrics
        rolling = compute_rolling_metrics()
        if rolling:
            print(f"[INFO] 连续观察完成: {rolling.get('momentum_label', 'N/A')}")
        else:
            print("[INFO] 连续观察层跳过（archive 数据不足）")
    except Exception as e:
        print(f"[WARN] 连续观察层失败（不影响主流程）: {e}")

    # Step 6: 评分层
    print("\n[Step 6/7] 计算评分层...")
    try:
        from src.price.score_layer import load_archive_metrics, add_score_to_df
        from src.shared.storage import Storage

        storage = Storage("price")
        archive_df = load_archive_metrics()
        if not archive_df.empty:
            scored_df = add_score_to_df(archive_df)
            analytics_path = storage.get_analytics_path("scored_metrics.parquet")
            scored_df.to_parquet(analytics_path, index=False)
            latest = scored_df.iloc[-1]
            print(f"[INFO] 评分完成: {latest.get('signal_rating', 'N/A')}")
    except Exception as e:
        print(f"[WARN] 评分层失败（不影响主流程）: {e}")

    # Step 7: 反抽观察层
    print("\n[Step 7/7] 计算反抽观察...")
    try:
        import pandas as pd
        from src.price.rolling_analyzer import load_rolling_metrics
        from src.price.rebound_watch_layer import calc_rebound_watch
        from src.shared.storage import Storage

        storage = Storage("price")
        metrics_path = storage.get_processed_path("daily_metrics.parquet")
        if metrics_path.exists():
            df_metrics = pd.read_parquet(metrics_path)
            if not df_metrics.empty:
                latest = df_metrics.iloc[0].to_dict()
                rolling = load_rolling_metrics()

                rebound_data = {
                    "overall_signal_label": latest.get("overall_signal_label"),
                    "price_strength_label": latest.get("price_strength_label"),
                    "volume_strength_label": latest.get("volume_strength_label"),
                    "capital_flow_trend_label": rolling.get("capital_flow_trend_label", "") if rolling else "",
                    "relative_strength": latest.get("relative_strength"),
                    "anchor_return": latest.get("anchor_return"),
                    "momentum_label": rolling.get("momentum_label", "") if rolling else "",
                    "price_trend_label": rolling.get("price_trend_label", "") if rolling else "",
                }
                rebound = calc_rebound_watch(rebound_data)
                if rebound.get("rebound_watch_flag"):
                    print(f"[INFO] 反抽观察触发: {rebound.get('rebound_reason', '')}")
                else:
                    print("[INFO] 反抽观察未触发")
    except Exception as e:
        print(f"[WARN] 反抽观察层失败（不影响主流程）: {e}")

    print("\n" + "=" * 60)
    print("行情数据线 - 运行完成")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())