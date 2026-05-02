"""
数据质量检查

职责：
  - 检查 valid_count 是否满足 min_size
  - 识别 missing_members
  - 判断 data_status（ok/insufficient_data/partial）
  - 提供数据质量报告

按 architecture.md 第 11 节降级规则设计

降级规则：
  - Anchor 没有行情 → 本次分析失败
  - 某个池子样本不足 → 标记 insufficient_data，不输出强结论
  - 资金数据缺失 → 不输出资金类强标签
  - 成员停牌 → 不参与当日均值，进入 missing_members
"""

from typing import Optional


def determine_data_status(
    valid_count: int,
    min_size: int,
    has_price_data: bool,
    has_fund_data: bool,
) -> tuple[str, Optional[str]]:
    """
    判断池子数据状态

    Args:
        valid_count: 有效数据数
        min_size: 最小样本数
        has_price_data: 是否有价格数据
        has_fund_data: 是否有资金数据

    Returns:
        (data_status, partial_reason)

    Status 定义：
        - "ok": 有效数据 >= min_size，价格/资金数据完整
        - "insufficient_data": 有效数据 < min_size，无法计算
        - "partial": 有效数据 >= min_size，但部分数据缺失
    """
    # 检查样本数是否足够
    if valid_count < min_size:
        return "insufficient_data", f"valid_count({valid_count}) < min_size({min_size})"

    # 检查价格数据
    if not has_price_data:
        return "insufficient_data", "no valid price data"

    # 检查资金数据（资金缺失不阻止计算，但标记 partial）
    if not has_fund_data:
        return "partial", "fund flow data missing"

    return "ok", None


def get_missing_members(
    configured_symbols: list[str],
    valid_symbols: list[str],
) -> list[str]:
    """
    获取缺失数据的成员列表

    Args:
        configured_symbols: 配置的成员 symbol 列表
        valid_symbols: 有有效数据的 symbol 列表

    Returns:
        缺失数据的 symbol 列表
    """
    return [s for s in configured_symbols if s not in valid_symbols]


def check_data_quality(
    universe_id: str,
    valid_count: int,
    benchmark_count: int,
    min_size: int,
) -> dict:
    """
    生成数据质量报告

    Args:
        universe_id: 池子ID
        valid_count: 有效数据数
        benchmark_count: benchmark 成员数
        min_size: 最小样本数

    Returns:
        数据质量报告 dict

    Example:
        {
            "universe_id": "direct_peers",
            "configured": 5,
            "valid": 4,
            "coverage": 0.8,
            "is_sufficient": true,
            "status": "ok",
            "warnings": []
        }
    """
    warnings = []

    # 计算覆盖率
    coverage = valid_count / benchmark_count if benchmark_count > 0 else 0

    # 判断是否足够
    is_sufficient = valid_count >= min_size

    # 生成警告
    if valid_count < benchmark_count:
        warnings.append(
            f"{benchmark_count - valid_count} members missing data"
        )

    if not is_sufficient:
        warnings.append(
            f"valid_count({valid_count}) < min_size({min_size})"
        )

    # 确定状态
    if not is_sufficient:
        status = "insufficient_data"
    elif coverage < 0.8:
        status = "partial"
    else:
        status = "ok"

    return {
        "universe_id": universe_id,
        "configured": benchmark_count,
        "valid": valid_count,
        "coverage": coverage,
        "is_sufficient": is_sufficient,
        "status": status,
        "warnings": warnings,
    }