"""
统一存储层访问
支持 price 和 news 两个数据域
"""
from pathlib import Path
from typing import Optional
import pandas as pd


class Storage:
    """统一存储层访问"""

    DATA_ROOT = Path(__file__).parent.parent.parent / "data"

    def __init__(self, domain: str):
        """
        初始化存储层

        Args:
            domain: "price" 或 "news"
        """
        if domain not in ("price", "news"):
            raise ValueError(f"domain 必须是 'price' 或 'news'，当前: {domain}")
        self.domain = domain
        self.root = self.DATA_ROOT / domain

    @property
    def raw_dir(self) -> Path:
        """原始数据目录"""
        return self.root / "raw"

    @property
    def processed_dir(self) -> Path:
        """处理后数据目录"""
        return self.root / "processed"

    @property
    def archive_dir(self) -> Path:
        """归档数据目录"""
        return self.root / "archive"

    @property
    def normalized_dir(self) -> Path:
        """标准化数据目录 (仅 price 域)"""
        if self.domain != "price":
            raise AttributeError("normalized_dir 仅在 price 域可用")
        return self.root / "normalized"

    @property
    def analytics_dir(self) -> Path:
        """分析数据目录 (仅 price 域)"""
        if self.domain != "price":
            raise AttributeError("analytics_dir 仅在 price 域可用")
        return self.root / "analytics"

    def get_raw_path(self, filename: str) -> Path:
        """获取原始数据文件路径"""
        return self.raw_dir / filename

    def get_processed_path(self, filename: str) -> Path:
        """获取处理后数据文件路径"""
        return self.processed_dir / filename

    def get_archive_path(self, filename: str) -> Path:
        """获取归档数据文件路径"""
        return self.archive_dir / filename

    def ensure_dirs(self) -> None:
        """确保所有目录存在"""
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        if self.domain == "price":
            self.normalized_dir.mkdir(parents=True, exist_ok=True)
            self.analytics_dir.mkdir(parents=True, exist_ok=True)

    def save_parquet(
        self,
        df: pd.DataFrame,
        filename: str,
        location: str = "processed"
    ) -> Path:
        """
        保存 DataFrame 到 parquet 文件

        Args:
            df: 要保存的数据
            filename: 文件名
            location: "raw", "processed", "archive" 或 "normalized"

        Returns:
            保存的文件路径
        """
        if df is None or df.empty:
            raise ValueError("数据为空，无法保存")

        location_map = {
            "raw": self.raw_dir,
            "processed": self.processed_dir,
            "archive": self.archive_dir,
        }
        if self.domain == "price":
            location_map["normalized"] = self.normalized_dir

        if location not in location_map:
            raise ValueError(f"location 必须是 {list(location_map.keys())} 之一")

        target_dir = location_map[location]
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / filename
        df.to_parquet(path, index=False)
        return path

    def load_parquet(
        self,
        filename: str,
        location: str = "processed"
    ) -> pd.DataFrame:
        """
        从 parquet 文件加载数据

        Args:
            filename: 文件名
            location: "raw", "processed", "archive" 或 "normalized"

        Returns:
            加载的 DataFrame
        """
        location_map = {
            "raw": self.raw_dir,
            "processed": self.processed_dir,
            "archive": self.archive_dir,
        }
        if self.domain == "price":
            location_map["normalized"] = self.normalized_dir

        if location not in location_map:
            raise ValueError(f"location 必须是 {list(location_map.keys())} 之一")

        path = location_map[location] / filename
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        return pd.read_parquet(path)

    def list_files(self, location: str = "processed", pattern: str = "*.parquet") -> list[Path]:
        """
        列出目录中的文件

        Args:
            location: "raw", "processed", "archive" 或 "normalized"
            pattern: 文件匹配模式

        Returns:
            文件路径列表
        """
        location_map = {
            "raw": self.raw_dir,
            "processed": self.processed_dir,
            "archive": self.archive_dir,
        }
        if self.domain == "price":
            location_map["normalized"] = self.normalized_dir

        if location not in location_map:
            raise ValueError(f"location 必须是 {list(location_map.keys())} 之一")

        return list(location_map[location].glob(pattern))


# 报告目录（共享）
REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"

# 配置目录（共享）
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"