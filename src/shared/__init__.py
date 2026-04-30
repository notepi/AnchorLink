"""
共享模块
提供配置加载和存储访问的统一接口
"""

from src.shared.storage import Storage
from src.shared.config import load_config, get_stock_pool

__all__ = ["Storage", "load_config", "get_stock_pool"]