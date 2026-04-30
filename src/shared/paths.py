"""
统一路径管理
所有模块应从此处导入路径常量，避免重复定义

用法：
    from src.shared.paths import PROJECT_ROOT, CONFIG_DIR, DATA_DIR
"""

from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 核心目录
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
ARCHIVE_DIR = PROJECT_ROOT / "archive"
REPORTS_DIR = PROJECT_ROOT / "reports"

# 数据子目录
PRICE_DATA_DIR = DATA_DIR / "price"
NEWS_DATA_DIR = DATA_DIR / "news"

# 归档子目录
ARCHIVE_METRICS_DIR = ARCHIVE_DIR / "metrics"
ARCHIVE_EVENTS_DIR = ARCHIVE_DIR / "events"