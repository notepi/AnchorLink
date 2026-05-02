"""
PoolRegistry - 股票池配置加载与管理

基于 architecture.md 第 4.4 节三层结构：
  - Instrument: 证券主数据（symbol 全局唯一）
  - Universe: 股票池定义（四类池子）
  - Membership: 成员关系（多对多，允许同一 symbol 在多个 universe）

职责：
  - 加载 pools.yaml 配置
  - 提供 benchmark/ranking/report 三种计算口径
  - 验证配置完整性
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import yaml


@dataclass(frozen=True)
class Instrument:
    """证券主数据"""
    symbol: str
    name: str
    market: str
    exchange: str
    fact_tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Universe:
    """股票池定义"""
    universe_id: str
    display_name: str
    purpose: str
    can_be_benchmark: bool
    min_size: int
    description: Optional[str] = None


@dataclass(frozen=True)
class Membership:
    """成员关系"""
    universe_id: str
    symbol: str
    role: str
    relevance: float
    weight: float
    enabled: bool
    include_in_benchmark: bool
    include_in_ranking: bool
    include_in_report: bool
    reason: str
    added_at: str
    reviewed_at: Optional[str] = None


@dataclass(frozen=True)
class Anchor:
    """锚定标的"""
    symbol: str
    name: str
    reason: str
    added_date: str


@dataclass(frozen=True)
class PoolConfig:
    """完整配置容器"""
    version: str
    changelog: list[dict[str, str]]
    anchor: Anchor
    instruments: dict[str, Instrument]  # symbol -> Instrument
    universes: dict[str, Universe]  # universe_id -> Universe
    memberships: list[Membership]
    reference_indices: list[dict[str, str]]
    data_source: str
    lookback_days: int
    event_keywords: dict[str, list[str]]


class PoolRegistry:
    """股票池配置注册表"""

    def __init__(self, config_path: Optional[str | Path] = None):
        """
        初始化 PoolRegistry

        Args:
            config_path: pools.yaml 路径，默认为 config/pools.yaml
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "pools.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        self._config_path = config_path
        self._raw_config: dict = self._load_yaml(config_path)
        self._config: PoolConfig = self._parse_config(self._raw_config)

    def _load_yaml(self, path: Path) -> dict:
        """加载 YAML 文件（带错误处理）"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data is None:
                    raise ValueError(f"配置文件为空: {path}")
                return data
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 解析错误 {path}: {e}") from e

    # 必填配置字段
    REQUIRED_KEYS = ["anchor", "instruments", "universes", "memberships"]

    def _parse_config(self, raw: dict) -> PoolConfig:
        """解析配置为数据结构"""
        # 验证必填字段
        for key in self.REQUIRED_KEYS:
            if key not in raw:
                raise ValueError(f"缺少必填配置字段: {key}")

        # 解析 anchor
        anchor = Anchor(
            symbol=raw["anchor"]["symbol"],
            name=raw["anchor"]["name"],
            reason=raw["anchor"]["reason"],
            added_date=raw["anchor"]["added_date"],
        )

        # 解析 instruments (symbol -> Instrument)
        instruments = {}
        for item in raw.get("instruments", []):
            inst = Instrument(
                symbol=item["symbol"],
                name=item["name"],
                market=item.get("market", "A-share"),
                exchange=item.get("exchange", "SH"),
                fact_tags=item.get("fact_tags", []),
            )
            instruments[inst.symbol] = inst

        # 解析 universes (universe_id -> Universe)
        universes = {}
        for item in raw.get("universes", []):
            uni = Universe(
                universe_id=item["universe_id"],
                display_name=item["display_name"],
                purpose=item["purpose"],
                can_be_benchmark=item.get("can_be_benchmark", True),
                min_size=item.get("min_size", 3),
                description=item.get("description"),
            )
            universes[uni.universe_id] = uni

        # 解析 memberships
        memberships = []
        for item in raw.get("memberships", []):
            mem = Membership(
                universe_id=item["universe_id"],
                symbol=item["symbol"],
                role=item["role"],
                relevance=item.get("relevance", 1.0),
                weight=item.get("weight", 1.0),
                enabled=item.get("enabled", True),
                include_in_benchmark=item.get("include_in_benchmark", True),
                include_in_ranking=item.get("include_in_ranking", True),
                include_in_report=item.get("include_in_report", True),
                reason=item["reason"],
                added_at=item["added_at"],
                reviewed_at=item.get("reviewed_at"),
            )
            memberships.append(mem)

        return PoolConfig(
            version=raw.get("version", "unknown"),
            changelog=raw.get("changelog", []),
            anchor=anchor,
            instruments=instruments,
            universes=universes,
            memberships=memberships,
            reference_indices=raw.get("reference_indices", []),
            data_source=raw.get("data_source", "tushare"),
            lookback_days=raw.get("lookback_days", 60),
            event_keywords=raw.get("event_keywords", {}),
        )

    # ==================== 核心接口 ====================

    def get_members(self, universe_id: str, enabled_only: bool = True) -> list[Membership]:
        """
        获取指定池子的所有成员

        Args:
            universe_id: 池子ID，如 "direct_peers", "industry_chain"
            enabled_only: 是否只返回 enabled=true 的成员

        Returns:
            成员列表
        """
        members = [m for m in self._config.memberships if m.universe_id == universe_id]
        if enabled_only:
            members = [m for m in members if m.enabled]
        return members

    def get_benchmark_scope(self, universe_id: str) -> list[Membership]:
        """
        获取指定池子的 benchmark 计算口径

        Args:
            universe_id: 池子ID

        Returns:
            enabled=true 且 include_in_benchmark=true 的成员列表

        Note:
            返回 Membership 对象列表，包含完整 metadata（role, relevance, weight）
            用于计算池子均值、中位数、广度等核心状态
        """
        return [
            m for m in self._config.memberships
            if m.universe_id == universe_id
            and m.enabled
            and m.include_in_benchmark
        ]

    def get_ranking_scope(self, universe_id: str, include_anchor: bool = True) -> list[str]:
        """
        获取指定池子的 ranking 计算口径（symbol 列表）

        Args:
            universe_id: 池子ID
            include_anchor: 是否显式加入 Anchor

        Returns:
            symbol 列表（enabled=true 且 include_in_ranking=true）

        Design Decision:
            返回 list[str] 而非 list[Membership]，原因：
            - Ranking 需要包含 Anchor，但 Anchor 不在任何 Membership 中
            - 下游系统（行情获取、排名计算）只需要 symbol 列表
            - 如果需要完整 Membership 信息，使用 get_ranking_scope_members()
        """
        symbols = [
            m.symbol for m in self._config.memberships
            if m.universe_id == universe_id
            and m.enabled
            and m.include_in_ranking
        ]

        if include_anchor:
            anchor_symbol = self._config.anchor.symbol
            if anchor_symbol not in symbols:
                symbols.append(anchor_symbol)

        return symbols

    def get_ranking_scope_members(self, universe_id: str) -> list[Membership]:
        """
        获取指定池子的 ranking 成员（Membership 列表，不含 Anchor）

        Args:
            universe_id: 池子ID

        Returns:
            enabled=true 且 include_in_ranking=true 的 Membership 列表

        Note:
            不包含 Anchor（Anchor 不在任何 Membership 中）
            如果需要 symbol 列表含 Anchor，使用 get_ranking_scope()
        """
        return [
            m for m in self._config.memberships
            if m.universe_id == universe_id
            and m.enabled
            and m.include_in_ranking
        ]

    def get_report_scope(self, universe_id: str) -> list[Membership]:
        """
        获取指定池子的 report 展示口径

        Args:
            universe_id: 池子ID

        Returns:
            enabled=true 且 include_in_report=true 的成员列表

        Note:
            返回 Membership 对象列表，用于生成 peer_matrix.csv 和 industry_report.md
        """
        return [
            m for m in self._config.memberships
            if m.universe_id == universe_id
            and m.enabled
            and m.include_in_report
        ]

    # ==================== 辅助接口 ====================

    def get_universe(self, universe_id: str) -> Optional[Universe]:
        """获取池子定义"""
        return self._config.universes.get(universe_id)

    def get_instrument(self, symbol: str) -> Optional[Instrument]:
        """获取证券主数据"""
        return self._config.instruments.get(symbol)

    def get_all_universes(self) -> list[Universe]:
        """获取所有池子定义"""
        return list(self._config.universes.values())

    def get_all_symbols(self) -> list[str]:
        """
        获取所有股票代码（用于行情获取）

        Returns:
            唯一的 symbol 列表（包含 anchor）
        """
        symbols = set(self._config.instruments.keys())
        symbols.add(self._config.anchor.symbol)
        return list(symbols)

    def get_anchor(self) -> Anchor:
        """获取锚定标的"""
        return self._config.anchor

    def get_version(self) -> str:
        """获取配置版本"""
        return self._config.version

    def get_changelog(self) -> list[dict[str, str]]:
        """获取变更日志"""
        return self._config.changelog

    def validate(self) -> dict[str, Any]:
        """
        验证配置完整性

        Returns:
            验证结果：{
                "valid": bool,
                "errors": list[str],
                "warnings": list[str],
                "stats": dict
            }
        """
        errors = []
        warnings = []

        # 验证每个 universe 的 min_size
        for universe in self._config.universes.values():
            benchmark_members = self.get_benchmark_scope(universe.universe_id)
            if len(benchmark_members) < universe.min_size:
                if universe.can_be_benchmark:
                    errors.append(
                        f"{universe.display_name}({universe.universe_id}) "
                        f"benchmark成员数({len(benchmark_members)}) < min_size({universe.min_size})"
                    )
                else:
                    warnings.append(
                        f"{universe.display_name}({universe.universe_id}) "
                        f"成员数不足，但该池子不参与benchmark"
                    )

        # 验证 membership 中的 symbol 必须存在于 instruments
        for mem in self._config.memberships:
            if mem.symbol not in self._config.instruments:
                errors.append(
                    f"Membership({mem.universe_id}/{mem.symbol}) "
                    f"引用的 symbol 不存在于 instruments"
                )

        # 统计信息
        stats = {
            "total_instruments": len(self._config.instruments),
            "total_universes": len(self._config.universes),
            "total_memberships": len(self._config.memberships),
            "memberships_per_universe": {
                uni_id: len(self.get_members(uni_id))
                for uni_id in self._config.universes.keys()
            },
        }

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "stats": stats,
        }