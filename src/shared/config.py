"""
配置加载工具
统一管理所有配置文件的加载
"""
from pathlib import Path
from typing import Any, Optional
import yaml

from src.shared.storage import CONFIG_DIR


def load_config(config_path: Optional[str] = None) -> dict:
    """
    加载 YAML 配置文件

    Args:
        config_path: 配置文件路径。如果为 None，默认加载 stocks.yaml

    Returns:
        配置字典
    """
    if config_path is None:
        config_path = CONFIG_DIR / "stocks.yaml"
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config_by_name(config_name: str) -> dict:
    """
    通过名称加载配置文件

    Args:
        config_name: 配置文件名（不含扩展名），如 "stocks", "news_sources"

    Returns:
        配置字典
    """
    config_path = CONFIG_DIR / f"{config_name}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_stock_pool(layer: Optional[str] = None) -> dict:
    """
    获取股票池配置

    Args:
        layer: 可选，指定层级 "core", "extended", "research_core", "research_candidates"

    Returns:
        股票池配置字典，包含：
        - version: 版本
        - anchor: 锚定标的
        - core_universe: 核心股票池
        - extended_universe: 扩展股票池
        - 如果指定 layer，则只返回该层级的股票列表
    """
    config = load_config()

    if layer is None:
        return config

    layer_map = {
        "core": config.get("core_universe", []),
        "extended": config.get("extended_universe", []),
        "research_core": config.get("research_core", []),
        "research_candidates": config.get("research_candidates", []),
    }

    if layer not in layer_map:
        raise ValueError(f"layer 必须是 {list(layer_map.keys())} 之一，当前: {layer}")

    return layer_map[layer]


def get_all_stock_codes() -> list[str]:
    """
    获取所有股票代码（用于行情获取）

    Returns:
        股票代码列表，格式如 "600343.SH"
    """
    config = load_config()
    codes = []

    # 添加锚定标的
    if "anchor" in config:
        codes.append(config["anchor"]["code"])

    # 添加各层级股票
    for layer in ["core_universe", "extended_universe", "research_core", "research_candidates"]:
        for stock in config.get(layer, []):
            if stock.get("active", True):
                codes.append(stock["code"])

    return codes


def get_benchmark_codes() -> list[str]:
    """
    获取参与板块均值计算的股票代码

    Returns:
        股票代码列表（排除 anchor 和 benchmark_included=False 的股票）
    """
    config = load_config()
    codes = []

    # 只添加 benchmark_included=True 的股票
    for layer in ["core_universe", "extended_universe"]:
        for stock in config.get(layer, []):
            if stock.get("active", True) and stock.get("benchmark_included", True):
                codes.append(stock["code"])

    return codes


def get_news_sources() -> list[str]:
    """
    获取新闻源列表

    Returns:
        新闻源 URL 列表
    """
    config = load_config_by_name("news_sources")
    return config.get("sources", [])


def get_catalyst_rules() -> dict:
    """
    获取催化筛选规则

    Returns:
        催化规则配置
    """
    return load_config_by_name("catalyst_rules")