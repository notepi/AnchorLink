"""
Anchor Position 单元测试

测试覆盖：
  1. determine_position() 位置判断
  2. RankingCalculator 排名计算（涨幅/成交/换手/资金）
  3. calculate_relative_strength() 相对强弱
  4. RelativeStrengthCalculator 多池聚合
  5. 边界情况（并列排名、极端涨跌幅、数据缺失）
"""

import pytest
from typing import Optional

from src.anchor_position.relative_strength import (
    RelativeStrength,
    determine_position,
    calculate_relative_strength,
    check_relative_strength_quality,
    RelativeStrengthCalculator,
    NEUTRAL_THRESHOLD,
)
from src.anchor_position.ranking_calculator import RankingCalculator
from src.pool_state.models import PoolState, MemberData, PoolStateResult
from src.config.loader import PoolRegistry


# ==================== Fixtures ====================

@pytest.fixture
def registry():
    """PoolRegistry fixture"""
    return PoolRegistry()


@pytest.fixture
def ranking_calculator(registry):
    """RankingCalculator fixture"""
    return RankingCalculator(registry)


@pytest.fixture
def sample_anchor_data():
    """样本 Anchor 数据"""
    return MemberData(
        symbol="688333.SH",
        trade_date="20260502",
        close=50.0,
        pct_chg=3.5,
        amount=120000.0,
        turnover_rate=5.0,
        net_mf_amount=8000000.0,
        pe_ttm=None, pb=None, is_valid=True,
    )


@pytest.fixture
def sample_market_data():
    """样本市场数据（其他成员）"""
    return {
        "688433.SH": MemberData(
            symbol="688433.SH",
            trade_date="20260502",
            close=45.0,
            pct_chg=2.0,
            amount=100000.0,
            turnover_rate=3.0,
            net_mf_amount=5000000.0,
            pe_ttm=None, pb=None, is_valid=True,
        ),
        "600343.SH": MemberData(
            symbol="600343.SH",
            trade_date="20260502",
            close=30.0,
            pct_chg=-1.5,
            amount=80000.0,
            turnover_rate=2.0,
            net_mf_amount=-2000000.0,
            pe_ttm=None, pb=None, is_valid=True,
        ),
        "600879.SH": MemberData(
            symbol="600879.SH",
            trade_date="20260502",
            close=25.0,
            pct_chg=5.0,
            amount=150000.0,
            turnover_rate=6.0,
            net_mf_amount=10000000.0,
            pe_ttm=None, pb=None, is_valid=True,
        ),
    }


@pytest.fixture
def sample_pool_state():
    """样本池子状态"""
    return PoolState(
        universe_id="direct_peers",
        trade_date="20260502",
        configured_count=5,
        enabled_count=5,
        benchmark_count=3,
        valid_count=3,
        median_return=2.0,
        mean_return=1.83,
        up_ratio=0.67,
        strong_count=1,
        weak_count=0,
        volume_multiplier=1.2,
        fund_positive_ratio=0.67,
        data_status="ok",
        missing_members=[],
    )


@pytest.fixture
def sample_ranking_data():
    """样本排名数据"""
    return {
        "rank_return": 2,
        "rank_volume": 3,
        "rank_turnover": 2,
        "rank_fund": 2,
        "total_count": 4,
        "valuation_percentile": None,
    }


# ==================== determine_position() 测试 ====================

class TestDeterminePosition:
    """测试位置判断函数"""

    def test_outperform_threshold(self):
        """测试跑赢阈值"""
        # 恰好超过阈值
        result = determine_position(NEUTRAL_THRESHOLD + 0.01)
        assert result == "outperform"

        # 明显跑赢
        result = determine_position(5.0)
        assert result == "outperform"

        # 大幅跑赢
        result = determine_position(20.0)
        assert result == "outperform"

    def test_underperform_threshold(self):
        """测试跑输阈值"""
        # 恰好低于阈值
        result = determine_position(-NEUTRAL_THRESHOLD - 0.01)
        assert result == "underperform"

        # 明显跑输
        result = determine_position(-5.0)
        assert result == "underperform"

        # 大幅跑输
        result = determine_position(-20.0)
        assert result == "underperform"

    def test_neutral_zone(self):
        """测试中性区间"""
        # 阈值边界内
        result = determine_position(0.0)
        assert result == "neutral"

        # 正向但未超阈值
        result = determine_position(NEUTRAL_THRESHOLD - 0.01)
        assert result == "neutral"

        # 负向但未超阈值
        result = determine_position(-NEUTRAL_THRESHOLD + 0.01)
        assert result == "neutral"

        # 恰好等于阈值（不算跑赢/跑输）
        result = determine_position(NEUTRAL_THRESHOLD)
        assert result == "neutral"

        result = determine_position(-NEUTRAL_THRESHOLD)
        assert result == "neutral"

    def test_extreme_values(self):
        """测试极端值"""
        # 涨停板
        result = determine_position(20.0)
        assert result == "outperform"

        # 跌停板
        result = determine_position(-20.0)
        assert result == "underperform"


# ==================== RankingCalculator 测试 ====================

class TestRankingCalculator:
    """测试排名计算器"""

    def test_calculate_ranks_normal(
        self, ranking_calculator, sample_anchor_data, sample_market_data
    ):
        """测试正常排名计算"""
        result = ranking_calculator.calculate_ranks(
            universe_id="direct_peers",
            trade_date="20260502",
            anchor_data=sample_anchor_data,
            market_data=sample_market_data,
        )

        # 验证返回结构
        assert "rank_return" in result
        assert "rank_volume" in result
        assert "rank_turnover" in result
        assert "rank_fund" in result
        assert "total_count" in result
        assert "valuation_percentile" in result

        # 验证 total_count
        assert result["total_count"] >= 1

    def test_calculate_rank_descending(self, ranking_calculator):
        """测试降序排名（值越大排名越高）"""
        # 构造测试数据
        dataset = [
            {"symbol": "A", "pct_chg": 5.0},
            {"symbol": "B", "pct_chg": 3.0},
            {"symbol": "C", "pct_chg": 1.0},
            {"symbol": "D", "pct_chg": -1.0},
        ]

        # 计算涨幅排名（降序）
        rank_a = ranking_calculator._calculate_rank(
            dataset, "pct_chg", "A", descending=True
        )
        assert rank_a == 1  # 最高涨幅，排名第一

        rank_d = ranking_calculator._calculate_rank(
            dataset, "pct_chg", "D", descending=True
        )
        assert rank_d == 4  # 最低涨幅，排名第四

    def test_calculate_rank_ties(self, ranking_calculator):
        """测试并列排名（相同值取第一个出现排名）"""
        # 构造测试数据（有并列）
        dataset = [
            {"symbol": "A", "pct_chg": 5.0},
            {"symbol": "B", "pct_chg": 5.0},  # 与 A 相同
            {"symbol": "C", "pct_chg": 3.0},
        ]

        # 计算排名
        rank_a = ranking_calculator._calculate_rank(
            dataset, "pct_chg", "A", descending=True
        )
        rank_b = ranking_calculator._calculate_rank(
            dataset, "pct_chg", "B", descending=True
        )

        # 并列排名：都应该是第一名（取第一个出现的排名）
        assert rank_a == 1
        assert rank_b == 1

    def test_calculate_rank_with_none_values(self, ranking_calculator):
        """测试过滤 None 值"""
        dataset = [
            {"symbol": "A", "pct_chg": 5.0},
            {"symbol": "B", "pct_chg": None},  # 无效数据
            {"symbol": "C", "pct_chg": 3.0},
        ]

        # 计算排名（应过滤 None）
        rank_a = ranking_calculator._calculate_rank(
            dataset, "pct_chg", "A", descending=True
        )

        # 只有 A 和 C 有效，A 最高
        assert rank_a == 1

    def test_calculate_rank_anchor_not_in_dataset(self, ranking_calculator):
        """测试 Anchor 不在数据集中"""
        dataset = [
            {"symbol": "A", "pct_chg": 5.0},
            {"symbol": "B", "pct_chg": 3.0},
        ]

        # Anchor symbol 不在数据集中
        rank = ranking_calculator._calculate_rank(
            dataset, "pct_chg", "X", descending=True
        )
        assert rank == 0  # 返回 0 表示无排名

    def test_calculate_rank_empty_dataset(self, ranking_calculator):
        """测试空数据集"""
        rank = ranking_calculator._calculate_rank(
            [], "pct_chg", "A", descending=True
        )
        assert rank == 0

    def test_calculate_rank_all_none(self, ranking_calculator):
        """测试全部 None 值"""
        dataset = [
            {"symbol": "A", "pct_chg": None},
            {"symbol": "B", "pct_chg": None},
        ]

        rank = ranking_calculator._calculate_rank(
            dataset, "pct_chg", "A", descending=True
        )
        assert rank == 0


# ==================== calculate_relative_strength() 测试 ====================

class TestCalculateRelativeStrength:
    """测试相对强弱计算"""

    def test_outperform_scenario(
        self, sample_anchor_data, sample_pool_state, sample_ranking_data
    ):
        """测试跑赢场景"""
        # Anchor 涨幅 3.5%, 池子中位数 2.0%
        # relative_strength = 1.5% > 0.5% → outperform
        rs = calculate_relative_strength(
            universe_id="direct_peers",
            trade_date="20260502",
            anchor_data=sample_anchor_data,
            pool_state=sample_pool_state,
            ranking_data=sample_ranking_data,
        )

        assert rs.universe_id == "direct_peers"
        assert rs.trade_date == "20260502"
        assert rs.anchor_return == 3.5
        assert rs.pool_median == 2.0
        assert rs.relative_strength == 1.5
        assert rs.position == "outperform"
        assert rs.data_status == "ok"

    def test_underperform_scenario(
        self, sample_pool_state, sample_ranking_data
    ):
        """测试跑输场景"""
        # Anchor 涨幅 -2.0%, 池子中位数 2.0%
        # relative_strength = -4.0% < -0.5% → underperform
        anchor_data = MemberData(
            symbol="688333.SH",
            trade_date="20260502",
            close=48.0,
            pct_chg=-2.0,
            amount=100000.0,
            turnover_rate=3.0,
            net_mf_amount=-5000000.0,
            pe_ttm=None, pb=None, is_valid=True,
        )

        rs = calculate_relative_strength(
            universe_id="direct_peers",
            trade_date="20260502",
            anchor_data=anchor_data,
            pool_state=sample_pool_state,
            ranking_data=sample_ranking_data,
        )

        assert rs.relative_strength == -4.0
        assert rs.position == "underperform"

    def test_neutral_scenario(
        self, sample_pool_state, sample_ranking_data
    ):
        """测试中性场景"""
        # Anchor 涨幅 2.3%, 池子中位数 2.0%
        # relative_strength = 0.3% < 0.5% → neutral
        anchor_data = MemberData(
            symbol="688333.SH",
            trade_date="20260502",
            close=50.0,
            pct_chg=2.3,
            amount=100000.0,
            turnover_rate=3.0,
            net_mf_amount=3000000.0,
            pe_ttm=None, pb=None, is_valid=True,
        )

        rs = calculate_relative_strength(
            universe_id="direct_peers",
            trade_date="20260502",
            anchor_data=anchor_data,
            pool_state=sample_pool_state,
            ranking_data=sample_ranking_data,
        )

        assert rs.relative_strength == pytest.approx(0.3)
        assert rs.position == "neutral"

    def test_ranking_data_included(
        self, sample_anchor_data, sample_pool_state, sample_ranking_data
    ):
        """测试排名数据正确传递"""
        rs = calculate_relative_strength(
            universe_id="direct_peers",
            trade_date="20260502",
            anchor_data=sample_anchor_data,
            pool_state=sample_pool_state,
            ranking_data=sample_ranking_data,
        )

        assert rs.rank_return == sample_ranking_data["rank_return"]
        assert rs.rank_volume == sample_ranking_data["rank_volume"]
        assert rs.rank_turnover == sample_ranking_data["rank_turnover"]
        assert rs.rank_fund == sample_ranking_data["rank_fund"]
        assert rs.total_count == sample_ranking_data["total_count"]

    def test_frozen_dataclass(
        self, sample_anchor_data, sample_pool_state, sample_ranking_data
    ):
        """测试 RelativeStrength 不可变"""
        rs = calculate_relative_strength(
            universe_id="direct_peers",
            trade_date="20260502",
            anchor_data=sample_anchor_data,
            pool_state=sample_pool_state,
            ranking_data=sample_ranking_data,
        )

        with pytest.raises(AttributeError):
            rs.relative_strength = 5.0

        with pytest.raises(AttributeError):
            rs.position = "underperform"


# ==================== check_relative_strength_quality() 测试 ====================

class TestQualityCheck:
    """测试数据质量检查"""

    def test_quality_ok(
        self, sample_anchor_data, sample_pool_state, sample_ranking_data
    ):
        """测试正常数据质量"""
        status, reason = check_relative_strength_quality(
            sample_anchor_data, sample_pool_state, sample_ranking_data
        )
        assert status == "ok"
        assert reason is None

    def test_anchor_no_return(self, sample_pool_state, sample_ranking_data):
        """测试 Anchor 无涨跌幅"""
        anchor_data = MemberData(
            symbol="688333.SH",
            trade_date="20260502",
            close=50.0,
            pct_chg=None,  # 无涨跌幅
            amount=100000.0,
            turnover_rate=3.0,
            net_mf_amount=5000000.0,
            pe_ttm=None, pb=None, is_valid=True,
        )

        status, reason = check_relative_strength_quality(
            anchor_data, sample_pool_state, sample_ranking_data
        )
        assert status == "insufficient_data"
        assert "anchor" in reason.lower()

    def test_pool_insufficient_data(
        self, sample_anchor_data, sample_ranking_data
    ):
        """测试池子数据不足"""
        pool_state = PoolState(
            universe_id="direct_peers",
            trade_date="20260502",
            configured_count=5,
            enabled_count=5,
            benchmark_count=3,
            valid_count=1,  # 低于 min_size
            median_return=None,
            mean_return=None,
            up_ratio=None,
            strong_count=0,
            weak_count=0,
            volume_multiplier=None,
            fund_positive_ratio=None,
            data_status="insufficient_data",
            missing_members=["A", "B"],
        )

        status, reason = check_relative_strength_quality(
            sample_anchor_data, pool_state, sample_ranking_data
        )
        assert status == "insufficient_data"
        assert "pool" in reason.lower()

    def test_no_ranking_data(
        self, sample_anchor_data, sample_pool_state
    ):
        """测试无排名数据"""
        ranking_data = {
            "rank_return": 0,
            "rank_volume": 0,
            "rank_turnover": 0,
            "rank_fund": 0,
            "total_count": 0,
            "valuation_percentile": None,
        }

        status, reason = check_relative_strength_quality(
            sample_anchor_data, sample_pool_state, ranking_data
        )
        assert status == "partial"
        assert "ranking" in reason.lower()

    def test_fund_ranking_missing(
        self, sample_anchor_data, sample_pool_state
    ):
        """测试资金排名缺失"""
        ranking_data = {
            "rank_return": 2,
            "rank_volume": 3,
            "rank_turnover": 2,
            "rank_fund": 0,  # 资金排名缺失
            "total_count": 4,
            "valuation_percentile": None,
        }

        status, reason = check_relative_strength_quality(
            sample_anchor_data, sample_pool_state, ranking_data
        )
        assert status == "partial"
        assert "fund" in reason.lower()


# ==================== RelativeStrengthCalculator 测试 ====================

class TestRelativeStrengthCalculator:
    """测试多池聚合计算器"""

    def test_calculate_all_pools(
        self, registry, ranking_calculator,
        sample_anchor_data, sample_market_data
    ):
        """测试计算所有池子"""
        # 构造池子状态
        pool_states = {}
        for universe in registry.get_all_universes():
            pool_states[universe.universe_id] = PoolState(
                universe_id=universe.universe_id,
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=3,
                valid_count=3,
                median_return=2.0,
                mean_return=1.83,
                up_ratio=0.67,
                strong_count=1,
                weak_count=0,
                volume_multiplier=1.2,
                fund_positive_ratio=0.67,
                data_status="ok",
                missing_members=[],
            )

        calculator = RelativeStrengthCalculator(registry, ranking_calculator)
        results = calculator.calculate_all(
            trade_date="20260502",
            anchor_data=sample_anchor_data,
            pool_states=pool_states,
            market_data=sample_market_data,
        )

        # 验证返回了所有池子
        assert len(results) == len(registry.get_all_universes())

        # 验证每个池子都有 RelativeStrength
        for universe_id, rs in results.items():
            assert isinstance(rs, RelativeStrength)
            assert rs.universe_id == universe_id
            assert rs.trade_date == "20260502"

    def test_missing_pool_state_skipped(
        self, registry, ranking_calculator,
        sample_anchor_data, sample_market_data
    ):
        """测试缺失池子状态被跳过"""
        # 只提供一个池子状态
        pool_states = {
            "direct_peers": PoolState(
                universe_id="direct_peers",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=3,
                valid_count=3,
                median_return=2.0,
                mean_return=1.83,
                up_ratio=0.67,
                strong_count=1,
                weak_count=0,
                volume_multiplier=1.2,
                fund_positive_ratio=0.67,
                data_status="ok",
                missing_members=[],
            )
        }

        calculator = RelativeStrengthCalculator(registry, ranking_calculator)
        results = calculator.calculate_all(
            trade_date="20260502",
            anchor_data=sample_anchor_data,
            pool_states=pool_states,
            market_data=sample_market_data,
        )

        # 只有 direct_peers 应该有结果
        assert "direct_peers" in results
        # 其他池子应该被跳过
        assert len(results) == 1


# ==================== 边界情况测试 ====================

class TestEdgeCases:
    """测试边界情况"""

    def test_zero_returns(self, sample_ranking_data):
        """测试涨跌幅全为 0"""
        anchor_data = MemberData(
            symbol="688333.SH",
            trade_date="20260502",
            close=50.0,
            pct_chg=0.0,
            amount=100000.0,
            turnover_rate=3.0,
            net_mf_amount=0.0,
            pe_ttm=None, pb=None, is_valid=True,
        )

        pool_state = PoolState(
            universe_id="direct_peers",
            trade_date="20260502",
            configured_count=5,
            enabled_count=5,
            benchmark_count=3,
            valid_count=3,
            median_return=0.0,
            mean_return=0.0,
            up_ratio=0.0,
            strong_count=0,
            weak_count=0,
            volume_multiplier=1.0,
            fund_positive_ratio=0.5,
            data_status="ok",
            missing_members=[],
        )

        rs = calculate_relative_strength(
            universe_id="direct_peers",
            trade_date="20260502",
            anchor_data=anchor_data,
            pool_state=pool_state,
            ranking_data=sample_ranking_data,
        )

        assert rs.relative_strength == 0.0
        assert rs.position == "neutral"

    def test_extreme_outperform(self, sample_ranking_data):
        """测试极端跑赢（涨停）"""
        anchor_data = MemberData(
            symbol="688333.SH",
            trade_date="20260502",
            close=60.0,
            pct_chg=20.0,  # 涨停
            amount=500000.0,
            turnover_rate=15.0,
            net_mf_amount=50000000.0,
            pe_ttm=None, pb=None, is_valid=True,
        )

        pool_state = PoolState(
            universe_id="direct_peers",
            trade_date="20260502",
            configured_count=5,
            enabled_count=5,
            benchmark_count=3,
            valid_count=3,
            median_return=2.0,
            mean_return=1.83,
            up_ratio=0.67,
            strong_count=1,
            weak_count=0,
            volume_multiplier=1.2,
            fund_positive_ratio=0.67,
            data_status="ok",
            missing_members=[],
        )

        rs = calculate_relative_strength(
            universe_id="direct_peers",
            trade_date="20260502",
            anchor_data=anchor_data,
            pool_state=pool_state,
            ranking_data=sample_ranking_data,
        )

        assert rs.relative_strength == 18.0
        assert rs.position == "outperform"

    def test_extreme_underperform(self, sample_ranking_data):
        """测试极端跑输（跌停）"""
        anchor_data = MemberData(
            symbol="688333.SH",
            trade_date="20260502",
            close=40.0,
            pct_chg=-20.0,  # 跌停
            amount=500000.0,
            turnover_rate=15.0,
            net_mf_amount=-50000000.0,
            pe_ttm=None, pb=None, is_valid=True,
        )

        pool_state = PoolState(
            universe_id="direct_peers",
            trade_date="20260502",
            configured_count=5,
            enabled_count=5,
            benchmark_count=3,
            valid_count=3,
            median_return=2.0,
            mean_return=1.83,
            up_ratio=0.67,
            strong_count=1,
            weak_count=0,
            volume_multiplier=1.2,
            fund_positive_ratio=0.67,
            data_status="ok",
            missing_members=[],
        )

        rs = calculate_relative_strength(
            universe_id="direct_peers",
            trade_date="20260502",
            anchor_data=anchor_data,
            pool_state=pool_state,
            ranking_data=sample_ranking_data,
        )

        assert rs.relative_strength == -22.0
        assert rs.position == "underperform"

    def test_single_member_ranking(self, ranking_calculator):
        """测试单成员排名"""
        anchor_data = MemberData(
            symbol="688333.SH",
            trade_date="20260502",
            close=50.0,
            pct_chg=3.0,
            amount=100000.0,
            turnover_rate=3.0,
            net_mf_amount=5000000.0,
            pe_ttm=None, pb=None, is_valid=True,
        )

        market_data = {}  # 无其他成员

        result = ranking_calculator.calculate_ranks(
            universe_id="theme_pool",  # theme_pool 只有 Anchor
            trade_date="20260502",
            anchor_data=anchor_data,
            market_data=market_data,
        )

        # 单成员排名第一
        assert result["rank_return"] == 1
        assert result["total_count"] == 1

    def test_valuation_percentile_direct_peers_only(
        self, ranking_calculator, sample_anchor_data, sample_market_data
    ):
        """测试估值分位仅 direct_peers 计算"""
        # direct_peers
        result = ranking_calculator.calculate_ranks(
            universe_id="direct_peers",
            trade_date="20260502",
            anchor_data=sample_anchor_data,
            market_data=sample_market_data,
        )
        # 当前返回 None（TODO: 后续实现）
        assert result["valuation_percentile"] is None

        # 其他池子
        result = ranking_calculator.calculate_ranks(
            universe_id="sector_pool",
            trade_date="20260502",
            anchor_data=sample_anchor_data,
            market_data=sample_market_data,
        )
        # 其他池子不计算估值分位
        assert result["valuation_percentile"] is None


# ==================== 口径分离测试 ====================

class TestScopeSeparation:
    """测试 ranking_scope 口径"""

    def test_ranking_scope_includes_anchor(self, registry):
        """测试 ranking_scope 包含 Anchor"""
        anchor_symbol = registry.get_anchor().symbol

        for universe in registry.get_all_universes():
            ranking_symbols = registry.get_ranking_scope(universe.universe_id)
            assert anchor_symbol in ranking_symbols

    def test_ranking_vs_benchmark_difference(self, registry):
        """测试 ranking 与 benchmark 口径差异"""
        for universe in registry.get_all_universes():
            ranking_symbols = registry.get_ranking_scope(universe.universe_id)
            benchmark_members = registry.get_benchmark_scope(universe.universe_id)
            benchmark_symbols = [m.symbol for m in benchmark_members]

            # ranking_scope 包含 Anchor，benchmark_scope 不包含
            anchor_symbol = registry.get_anchor().symbol
            if anchor_symbol in ranking_symbols:
                assert anchor_symbol not in benchmark_symbols