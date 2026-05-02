"""
PoolRegistry 单元测试

测试覆盖：
  1. 配置加载（anchor/instruments/universes/memberships 解析）
  2. 查询接口（get_members/get_benchmark_scope/get_ranking_scope）
  3. 多对多关系（同一 symbol 在多个 universe 的不同角色）
  4. 口径分离（benchmark/ranking/report 不同成员列表）
  5. 配置验证（min_size 检查、instrument 引用检查）
"""

import pytest
from pathlib import Path
import yaml
import tempfile

from src.config.loader import PoolRegistry, Instrument, Universe, Membership, Anchor, PoolConfig


# ==================== 基础加载测试 ====================

class TestPoolRegistryLoad:
    """测试配置加载"""

    def test_load_valid_config(self):
        """测试加载有效配置"""
        registry = PoolRegistry()
        assert registry.get_version() == "2026-05-02"
        assert len(registry.get_all_universes()) == 4

    def test_load_missing_config_raises_error(self):
        """测试加载缺失配置抛出错误"""
        with pytest.raises(FileNotFoundError):
            PoolRegistry(config_path="/nonexistent/path/pools.yaml")

    def test_parse_anchor(self):
        """测试解析 anchor"""
        registry = PoolRegistry()
        anchor = registry.get_anchor()
        assert anchor.symbol == "688333.SH"
        assert anchor.name == "铂力特"

    def test_parse_instruments(self):
        """测试解析 instruments"""
        registry = PoolRegistry()
        instruments = registry._config.instruments
        assert len(instruments) >= 15  # 至少15只股票
        assert "688333.SH" in instruments
        assert instruments["688333.SH"].name == "铂力特"

    def test_parse_universes(self):
        """测试解析 universes"""
        registry = PoolRegistry()
        universes = registry._config.universes
        assert "direct_peers" in universes
        assert "industry_chain" in universes
        assert "theme_pool" in universes
        assert "trading_watchlist" in universes

        # 验证 universe 属性
        direct_peers = universes["direct_peers"]
        assert direct_peers.can_be_benchmark == True
        assert direct_peers.min_size == 1  # 目前只有华曙高科一个核心同类

        theme_pool = universes["theme_pool"]
        assert theme_pool.can_be_benchmark == False

    def test_parse_memberships(self):
        """测试解析 memberships"""
        registry = PoolRegistry()
        memberships = registry._config.memberships
        assert len(memberships) >= 16

        # 验证多对多：688433.SH 应该出现多次
        huashu_memberships = [m for m in memberships if m.symbol == "688433.SH"]
        assert len(huashu_memberships) == 2  # direct_peers + theme_pool


# ==================== 查询接口测试 ====================

class TestPoolRegistryQuery:
    """测试查询接口"""

    def test_get_members_enabled_only(self):
        """测试获取池子成员（只返回 enabled）"""
        registry = PoolRegistry()

        # industry_chain 应该有 4-5 个 enabled 成员
        members = registry.get_members("industry_chain", enabled_only=True)
        assert len(members) >= 4

        # 验证所有成员都是 enabled
        for m in members:
            assert m.enabled == True

    def test_get_members_include_disabled(self):
        """测试获取池子成员（包含 disabled）"""
        registry = PoolRegistry()

        # trading_watchlist 包含一个 disabled 成员（航天工程）
        members = registry.get_members("trading_watchlist", enabled_only=False)
        disabled_members = [m for m in members if not m.enabled]
        assert len(disabled_members) >= 1

    def test_get_benchmark_scope(self):
        """测试获取 benchmark 口径"""
        registry = PoolRegistry()

        # industry_chain 的 benchmark 口径
        benchmark_members = registry.get_benchmark_scope("industry_chain")

        # 验证所有成员都是 enabled + include_in_benchmark
        for m in benchmark_members:
            assert m.enabled == True
            assert m.include_in_benchmark == True

        # 003009.SZ 中天火箭应该不参与 benchmark（研究层）
        zhongtian_members = [m for m in benchmark_members if m.symbol == "003009.SZ"]
        assert len(zhongtian_members) == 0

    def test_get_ranking_scope(self):
        """测试获取 ranking 口径"""
        registry = PoolRegistry()

        # industry_chain 的 ranking 口径（默认包含 anchor）
        ranking_symbols = registry.get_ranking_scope("industry_chain", include_anchor=True)

        # 必须包含 anchor
        assert "688333.SH" in ranking_symbols

        # 必须包含所有 enabled + include_in_ranking 的成员
        # 003009.SZ 中天火箭应该参与 ranking
        assert "003009.SZ" in ranking_symbols

    def test_get_ranking_scope_exclude_anchor(self):
        """测试获取 ranking 口径（不包含 anchor）"""
        registry = PoolRegistry()

        ranking_symbols = registry.get_ranking_scope("industry_chain", include_anchor=False)
        assert "688333.SH" not in ranking_symbols

    def test_get_report_scope(self):
        """测试获取 report 口径"""
        registry = PoolRegistry()

        # theme_pool 的 report 口径
        report_members = registry.get_report_scope("theme_pool")

        # 验证所有成员都是 enabled + include_in_report
        for m in report_members:
            assert m.enabled == True
            assert m.include_in_report == True

    def test_get_all_symbols(self):
        """测试获取所有股票代码"""
        registry = PoolRegistry()

        symbols = registry.get_all_symbols()

        # 必须包含 anchor
        assert "688333.SH" in symbols

        # 必须去重
        assert len(symbols) == len(set(symbols))

        # 至少 15 只股票
        assert len(symbols) >= 15

    def test_get_universe(self):
        """测试获取池子定义"""
        registry = PoolRegistry()

        universe = registry.get_universe("direct_peers")
        assert universe is not None
        assert universe.display_name == "核心同类池"

    def test_get_instrument(self):
        """测试获取证券主数据"""
        registry = PoolRegistry()

        instrument = registry.get_instrument("688333.SH")
        assert instrument is not None
        assert instrument.name == "铂力特"


# ==================== 多对多关系测试 ====================

class TestManyToManyRelation:
    """测试多对多关系"""

    def test_same_symbol_in_multiple_universes(self):
        """测试同一 symbol 在多个池子"""
        registry = PoolRegistry()

        # 688433.SH 华曙高科应该出现在 direct_peers 和 theme_pool
        memberships = registry._config.memberships
        huashu_memberships = [m for m in memberships if m.symbol == "688433.SH"]

        assert len(huashu_memberships) == 2

        # 验证不同池子的不同角色
        universes = [m.universe_id for m in huashu_memberships]
        assert "direct_peers" in universes
        assert "theme_pool" in universes

        # 验证不同角色
        roles = {m.universe_id: m.role for m in huashu_memberships}
        assert roles["direct_peers"] == "direct_comparable"
        assert roles["theme_pool"] == "theme_heat_proxy"

    def test_different_benchmark_flags_in_different_universes(self):
        """测试不同池子的不同 benchmark 标记"""
        registry = PoolRegistry()

        memberships = registry._config.memberships
        huashu_memberships = [m for m in memberships if m.symbol == "688433.SH"]

        # direct_peers 参与 benchmark
        direct_member = [m for m in huashu_memberships if m.universe_id == "direct_peers"][0]
        assert direct_member.include_in_benchmark == True

        # theme_pool 不参与 benchmark
        theme_member = [m for m in huashu_memberships if m.universe_id == "theme_pool"][0]
        assert theme_member.include_in_benchmark == False


# ==================== 口径分离测试 ====================

class TestScopeSeparation:
    """测试 benchmark/ranking/report 口径分离"""

    def test_benchmark_vs_ranking_scope(self):
        """测试 benchmark 和 ranking 口径不同"""
        registry = PoolRegistry()

        # industry_chain 的 benchmark 口径
        benchmark_symbols = [m.symbol for m in registry.get_benchmark_scope("industry_chain")]

        # industry_chain 的 ranking 口径（不含 anchor）
        ranking_symbols = registry.get_ranking_scope("industry_chain", include_anchor=False)

        # ranking 应该包含 benchmark 的所有成员
        for sym in benchmark_symbols:
            assert sym in ranking_symbols

        # ranking 可能包含更多成员（如 003009.SZ）
        assert len(ranking_symbols) >= len(benchmark_symbols)

    def test_theme_pool_not_in_benchmark(self):
        """测试 theme_pool 不参与 benchmark"""
        registry = PoolRegistry()

        # theme_pool 的 benchmark 口径应该为空或很少
        benchmark_members = registry.get_benchmark_scope("theme_pool")

        # 所有成员的 include_in_benchmark 应该为 False
        for m in benchmark_members:
            assert m.include_in_benchmark == False


# ==================== 验证测试 ====================

class TestPoolRegistryValidate:
    """测试配置验证"""

    def test_validate_valid_config(self):
        """测试验证有效配置"""
        registry = PoolRegistry()
        result = registry.validate()

        assert result["valid"] == True
        assert len(result["errors"]) == 0

    def test_validate_stats(self):
        """测试验证统计信息"""
        registry = PoolRegistry()
        result = registry.validate()

        stats = result["stats"]
        assert stats["total_instruments"] >= 15
        assert stats["total_universes"] == 4
        assert stats["total_memberships"] >= 16

        # 验证每个池子都有成员
        for uni_id, count in stats["memberships_per_universe"].items():
            assert count >= 1


# ==================== 数据结构测试 ====================

class TestDataStructures:
    """测试数据类"""

    def test_instrument_frozen(self):
        """测试 Instrument 不可变"""
        inst = Instrument(
            symbol="688333.SH",
            name="铂力特",
            market="A-share",
            exchange="SH",
            fact_tags=["金属3D打印"],
        )

        with pytest.raises(AttributeError):
            inst.name = "新名称"

    def test_membership_frozen(self):
        """测试 Membership 不可变"""
        mem = Membership(
            universe_id="direct_peers",
            symbol="688433.SH",
            role="direct_comparable",
            relevance=0.9,
            weight=1.0,
            enabled=True,
            include_in_benchmark=True,
            include_in_ranking=True,
            include_in_report=True,
            reason="test",
            added_at="2026-01-01",
        )

        with pytest.raises(AttributeError):
            mem.enabled = False

    def test_anchor_frozen(self):
        """测试 Anchor 不可变"""
        anchor = Anchor(
            symbol="688333.SH",
            name="铂力特",
            reason="test",
            added_date="2026-01-01",
        )

        with pytest.raises(AttributeError):
            anchor.symbol = "新代码"


# ==================== Anchor 排除测试 ====================

class TestAnchorExclusion:
    """测试 Anchor 不参与池子"""

    def test_anchor_not_in_any_pool(self):
        """测试 Anchor 不在任何池子的 members 中"""
        registry = PoolRegistry()

        anchor_symbol = registry.get_anchor().symbol

        # Anchor 不应该在 memberships 中出现
        anchor_memberships = [m for m in registry._config.memberships if m.symbol == anchor_symbol]
        assert len(anchor_memberships) == 0

    def test_anchor_in_ranking_scope_when_explicit(self):
        """测试 Anchor 可显式加入 ranking"""
        registry = PoolRegistry()

        # 默认 ranking 包含 anchor
        ranking_symbols = registry.get_ranking_scope("industry_chain", include_anchor=True)
        assert "688333.SH" in ranking_symbols

        # 不包含 anchor 时
        ranking_symbols_no_anchor = registry.get_ranking_scope("industry_chain", include_anchor=False)
        assert "688333.SH" not in ranking_symbols_no_anchor