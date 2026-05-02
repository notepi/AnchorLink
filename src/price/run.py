"""
行情数据线入口（MVP 版本）
只保留数据获取和标准化功能

用法：
    python -m src.price.run
"""

import sys

from src.config.loader import PoolRegistry
from src.price.fetcher import fetch_for_registry
from src.price.normalizer import normalize
from src.price.data_product import build_price_data_product


def main():
    """运行行情数据线 MVP 流程"""
    print("=" * 60)
    print("行情数据线 MVP - 开始运行")
    print("=" * 60)

    # Step 1: 加载 PoolRegistry
    print("\n[Step 0/3] 加载配置...")
    try:
        registry = PoolRegistry()
        print(f"[INFO] 配置加载成功: anchor={registry.get_anchor().symbol}")
    except Exception as e:
        print(f"[ERROR] 配置加载失败: {e}")
        return 1

    # Step 1: 获取数据（使用 PoolRegistry）
    print("\n[Step 1/3] 获取市场数据...")
    try:
        df = fetch_for_registry(registry)
        if df.empty:
            print("[ERROR] 未获取到数据，流程终止")
            return 1
        print(f"[INFO] 获取数据成功: {len(df)} 条记录")
    except Exception as e:
        print(f"[ERROR] 获取数据失败: {e}")
        return 1

    # Step 2: 标准化
    print("\n[Step 2/3] 数据标准化...")
    try:
        normalize()
        print("[INFO] 数据标准化完成")
    except Exception as e:
        print(f"[ERROR] 标准化失败: {e}")
        return 1

    # Step 3: 构建数据产品
    print("\n[Step 3/3] 构建价格数据产品...")
    try:
        product = build_price_data_product()
        print(f"[INFO] 数据产品状态: {product.get('overall_status')}")
    except Exception as e:
        print(f"[WARN] 数据产品构建失败: {e}")

    print("\n" + "=" * 60)
    print("行情数据线 MVP - 运行完成")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())