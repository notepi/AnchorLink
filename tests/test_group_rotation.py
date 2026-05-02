"""
Group Rotation 单元测试

测试覆盖：
  1. determine_strongest_weakest() 组间排名
  2. calculate_single_spread() 差值计算
  3. SpreadCalculator.spreads 计算逻辑
  4. analyze_group_rotation() 整体流程
  5. analyze_rotation_with_spreads() 完整流程
  6. 数据质量检查（池子缺失、数据不足）
  7. 边界情况（只有 1 个池子、所有池子涨跌幅相同）
"""

import pytest

from src.group_rotation.models import GroupRotation
from src.group_rotation.rotation_analyzer import (
    analyze_group_rotation,
    determine_strongest_weakest,
)
from src.group_rotation.spread_calculator import (
    SpreadCalculator,
    calculate_single_spread,
    analyze_rotation_with_spreads,
)
from src.pool_state.models import PoolState
from src.config.loader import PoolRegistry


# ==================== Fixtures ====================

@pytest.fixture
def registry():
    """PoolRegistry fixture"""
    return PoolRegistry()


@pytest.fixture
def sample_pool_states():
    """样本池子状态（4 个池子）"""
    return {
        "direct_peers": PoolState(
            universe_id="direct_peers",
            trade_date="20260502",
            configured_count=5,
            enabled_count=5,
            benchmark_count=3,
            valid_count=3,
            median_return=2.5,  # 最强
            mean_return=2.3,
            up_ratio=0.67,
            strong_count=1,
            weak_count=0,
            volume_multiplier=1.2,
            fund_positive_ratio=0.67,
            data_status="ok",
            missing_members=[],
        ),
        "theme_pool": PoolState(
            universe_id="theme_pool",
            trade_date="20260502",
            configured_count=8,
            enabled_count=8,
            benchmark_count=0,  # can_be_benchmark=False
            valid_count=6,
            median_return=3.0,  # 不应参与比较
            mean_return=2.8,
            up_ratio=0.75,
            strong_count=2,
            weak_count=0,
            volume_multiplier=1.5,
            fund_positive_ratio=0.70,
            data_status="ok",
            missing_members=[],
        ),
        "industry_chain": PoolState(
            universe_id="industry_chain",
            trade_date="20260502",
            configured_count=5,
            enabled_count=5,
            benchmark_count=4,
            valid_count=4,
            median_return=1.0,  # 中等
            mean_return=0.9,
            up_ratio=0.50,
            strong_count=0,
            weak_count=1,
            volume_multiplier=1.0,
            fund_positive_ratio=0.50,
            data_status="ok",
            missing_members=[],
        ),
        "trading_watchlist": PoolState(
            universe_id="trading_watchlist",
            trade_date="20260502",
            configured_count=5,
            enabled_count=5,
            benchmark_count=0,  # can_be_benchmark=False
            valid_count=5,
            median_return=-1.5,  # 不应参与比较
            mean_return=-1.3,
            up_ratio=0.20,
            strong_count=0,
            weak_count=2,
            volume_multiplier=0.8,
            fund_positive_ratio=0.30,
            data_status="ok",
            missing_members=[],
        ),
    }


@pytest.fixture
def sample_pool_states_with_insufficient():
    """包含数据不足池子的样本"""
    return {
        "direct_peers": PoolState(
            universe_id="direct_peers",
            trade_date="20260502",
            configured_count=5,
            enabled_count=5,
            benchmark_count=3,
            valid_count=3,
            median_return=2.5,
            mean_return=2.3,
            up_ratio=0.67,
            strong_count=1,
            weak_count=0,
            volume_multiplier=1.2,
            fund_positive_ratio=0.67,
            data_status="ok",
            missing_members=[],
        ),
        "industry_chain": PoolState(
            universe_id="industry_chain",
            trade_date="20260502",
            configured_count=5,
            enabled_count=5,
            benchmark_count=4,
            valid_count=1,  # 低于 min_size
            median_return=None,
            mean_return=None,
            up_ratio=None,
            strong_count=0,
            weak_count=0,
            volume_multiplier=None,
            fund_positive_ratio=None,
            data_status="insufficient_data",
            missing_members=["A", "B", "C"],
        ),
    }


# ==================== determine_strongest_weakest() 测试 ====================

class TestDetermineStrongestWeakest:
    """测试组间强弱排名"""

    def test_normal_ranking(self):
        """测试正常排名"""
        group_medians = {
            "direct_peers": 2.5,
            "industry_chain": 1.0,
            "sector_pool": 0.5,
        }

        strongest, weakest, ranking = determine_strongest_weakest(group_medians)

        # 最强：direct_peers (2.5)
        assert strongest == "direct_peers"
        # 最弱：sector_pool (0.5)
        assert weakest == "sector_pool"
        # 排名：降序
        assert ranking == ["direct_peers", "industry_chain", "sector_pool"]

    def test_single_group(self):
        """测试单个池子"""
        group_medians = {"direct_peers": 2.5}

        strongest, weakest, ranking = determine_strongest_weakest(group_medians)

        assert strongest == "direct_peers"
        assert weakest == "direct_peers"
        assert ranking == ["direct_peers"]

    def test_empty_groups(self):
        """测试空池子"""
        strongest, weakest, ranking = determine_strongest_weakest({})

        assert strongest == ""
        assert weakest == ""
        assert ranking == []

    def test_negative_returns(self):
        """测试负涨跌幅"""
        group_medians = {
            "direct_peers": -1.0,
            "industry_chain": -3.0,
            "sector_pool": -2.0,
        }

        strongest, weakest, ranking = determine_strongest_weakest(group_medians)

        # 最强：direct_peers (-1.0, 跌得最少)
        assert strongest == "direct_peers"
        # 最弱：industry_chain (-3.0, 跌得最多)
        assert weakest == "industry_chain"

    def test_same_values(self):
        """测试相同涨跌幅"""
        group_medians = {
            "direct_peers": 2.0,
            "industry_chain": 2.0,
            "sector_pool": 2.0,
        }

        strongest, weakest, ranking = determine_strongest_weakest(group_medians)

        # 相同值按出现顺序
        assert strongest in ["direct_peers", "industry_chain", "sector_pool"]
        assert weakest in ["direct_peers", "industry_chain", "sector_pool"]
        assert len(ranking) == 3


# ==================== calculate_single_spread() 测试 ====================

class TestCalculateSingleSpread:
    """测试单个 spread 计算"""

    def test_positive_spread(self):
        """测试核心池更强"""
        # 核心池涨 3%, 其他池涨 1%
        spread = calculate_single_spread(3.0, 1.0)
        assert spread == 2.0  # spread > 0 → 核心更强

    def test_negative_spread(self):
        """测试其他池更强"""
        # 核心池涨 1%, 其他池涨 3%
        spread = calculate_single_spread(1.0, 3.0)
        assert spread == -2.0  # spread < 0 → 其他池更强

    def test_zero_spread(self):
        """测试相同强弱"""
        spread = calculate_single_spread(2.0, 2.0)
        assert spread == 0.0

    def test_negative_returns(self):
        """测试负涨跌幅"""
        # 核心池跌 1%, 其他池跌 3%
        spread = calculate_single_spread(-1.0, -3.0)
        assert spread == 2.0  # 核心跌得少 → 更强

        # 核心池跌 3%, 其他池跌 1%
        spread = calculate_single_spread(-3.0, -1.0)
        assert spread == -2.0  # 核心跌得多 → 更弱


# ==================== SpreadCalculator 测试 ====================

class TestSpreadCalculator:
    """测试 SpreadCalculator 类"""

    def test_calculate_spreads_normal(self):
        """测试正常 spread 计算"""
        calculator = SpreadCalculator(core_pool_id="direct_peers")

        group_medians = {
            "direct_peers": 2.5,
            "industry_chain": 1.0,
            "sector_pool": 0.5,
        }

        spreads = calculator.calculate_spreads(group_medians)

        # direct_peers 不在 spreads 中（核心池本身）
        assert "direct_peers" not in spreads

        # industry_chain spread = 2.5 - 1.0 = 1.5
        assert spreads["industry_chain"] == 1.5

        # sector_pool spread = 2.5 - 0.5 = 2.0
        assert spreads["sector_pool"] == 2.0

    def test_core_pool_missing(self):
        """测试核心池数据缺失"""
        calculator = SpreadCalculator(core_pool_id="direct_peers")

        group_medians = {
            "industry_chain": 1.0,
            "sector_pool": 0.5,
        }

        spreads = calculator.calculate_spreads(group_medians)

        # 核心池缺失，无法计算
        assert spreads == {}

    def test_other_pool_missing(self):
        """测试其他池数据缺失"""
        calculator = SpreadCalculator(core_pool_id="direct_peers")

        group_medians = {
            "direct_peers": 2.5,
            "industry_chain": None,  # 缺失
            "sector_pool": 0.5,
        }

        spreads = calculator.calculate_spreads(group_medians)

        # industry_chain 被跳过
        assert "industry_chain" not in spreads
        assert spreads["sector_pool"] == 2.0

    def test_custom_core_pool(self):
        """测试自定义核心池"""
        calculator = SpreadCalculator(core_pool_id="sector_pool")

        group_medians = {
            "direct_peers": 2.5,
            "industry_chain": 1.0,
            "sector_pool": 0.5,
        }

        spreads = calculator.calculate_spreads(group_medians)

        # 以 sector_pool 为基准
        assert spreads["direct_peers"] == -2.0  # 0.5 - 2.5
        assert spreads["industry_chain"] == -0.5  # 0.5 - 1.0


# ==================== analyze_group_rotation() 测试 ====================

class TestAnalyzeGroupRotation:
    """测试组间轮动分析"""

    def test_normal_analysis(self, sample_pool_states, registry):
        """测试正常分析"""
        rotation = analyze_group_rotation(
            sample_pool_states, "20260502", registry
        )

        # 只比较 can_be_benchmark=True 的池子
        # direct_peers (2.5) 和 industry_chain (1.0)
        assert rotation.strongest_group == "direct_peers"
        assert rotation.weakest_group == "industry_chain"
        assert rotation.group_ranking == ["direct_peers", "industry_chain"]
        assert rotation.data_status == "ok"

        # group_medians 只包含 benchmark 池子
        assert "direct_peers" in rotation.group_medians
        assert "industry_chain" in rotation.group_medians
        assert "theme_pool" not in rotation.group_medians

    def test_without_registry(self, sample_pool_states):
        """测试无 registry（比较所有池子）"""
        rotation = analyze_group_rotation(
            sample_pool_states, "20260502", registry=None
        )

        # 比较 4 个池子（包含 theme_pool 和 trading_watchlist）
        assert len(rotation.group_ranking) == 4

        # 最强：theme_pool (3.0)
        assert rotation.strongest_group == "theme_pool"
        # 最弱：trading_watchlist (-1.5)
        assert rotation.weakest_group == "trading_watchlist"

    def test_insufficient_data(self, sample_pool_states_with_insufficient, registry):
        """测试数据不足"""
        rotation = analyze_group_rotation(
            sample_pool_states_with_insufficient, "20260502", registry
        )

        # 只有 1 个有效池子（direct_peers），低于 MIN_VALID_GROUPS=2
        assert rotation.data_status == "insufficient_data"
        assert rotation.strongest_group == ""
        assert rotation.weakest_group == ""
        assert rotation.group_ranking == []

    def test_frozen_dataclass(self, sample_pool_states, registry):
        """测试 GroupRotation 不可变"""
        rotation = analyze_group_rotation(
            sample_pool_states, "20260502", registry
        )

        with pytest.raises(AttributeError):
            rotation.strongest_group = "theme_pool"


# ==================== analyze_rotation_with_spreads() 测试 ====================

class TestAnalyzeRotationWithSpreads:
    """测试完整轮动分析（包含 spread）"""

    def test_full_analysis(self, sample_pool_states, registry):
        """测试完整流程"""
        rotation = analyze_rotation_with_spreads(
            sample_pool_states, "20260502", registry, core_pool_id="direct_peers"
        )

        # 验证基础字段
        assert rotation.strongest_group == "direct_peers"
        assert rotation.weakest_group == "industry_chain"

        # 验证 spread
        assert rotation.spreads["industry_chain"] == 1.5  # 2.5 - 1.0
        assert rotation.core_vs_chain_spread == 1.5

        # theme_pool 和 trading_watchlist 不是 benchmark 池子
        # 所以不在 group_medians 中，spread 也为 None
        assert rotation.core_vs_theme_spread is None
        assert rotation.core_vs_trading_spread is None

    def test_without_registry(self, sample_pool_states):
        """测试无 registry 的完整分析"""
        rotation = analyze_rotation_with_spreads(
            sample_pool_states, "20260502", registry=None
        )

        # 验证 spread 包含所有池子
        assert "industry_chain" in rotation.spreads
        assert "theme_pool" in rotation.spreads
        assert "trading_watchlist" in rotation.spreads

        # theme_pool spread = 2.5 - 3.0 = -0.5
        assert rotation.core_vs_theme_spread == -0.5
        # trading_watchlist spread = 2.5 - (-1.5) = 4.0
        assert rotation.core_vs_trading_spread == 4.0


# ==================== 边界情况测试 ====================

class TestEdgeCases:
    """测试边界情况"""

    def test_all_groups_same_return(self):
        """测试所有池子涨跌幅相同"""
        pool_states = {
            "direct_peers": PoolState(
                universe_id="direct_peers",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=3,
                valid_count=3,
                median_return=2.0,
                mean_return=2.0,
                up_ratio=0.67,
                strong_count=0,
                weak_count=0,
                volume_multiplier=1.0,
                fund_positive_ratio=0.5,
                data_status="ok",
                missing_members=[],
            ),
            "industry_chain": PoolState(
                universe_id="industry_chain",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=4,
                valid_count=4,
                median_return=2.0,
                mean_return=2.0,
                up_ratio=0.67,
                strong_count=0,
                weak_count=0,
                volume_multiplier=1.0,
                fund_positive_ratio=0.5,
                data_status="ok",
                missing_members=[],
            ),
        }

        rotation = analyze_group_rotation(pool_states, "20260502", registry=None)

        # 相同涨跌幅，按出现顺序
        assert rotation.strongest_group in ["direct_peers", "industry_chain"]
        assert rotation.weakest_group in ["direct_peers", "industry_chain"]

        # spread 应该为 0
        calculator = SpreadCalculator()
        spreads = calculator.calculate_spreads(rotation.group_medians)
        assert spreads["industry_chain"] == 0.0

    def test_zero_returns(self):
        """测试涨跌幅全为 0"""
        pool_states = {
            "direct_peers": PoolState(
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
            ),
            "industry_chain": PoolState(
                universe_id="industry_chain",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=4,
                valid_count=4,
                median_return=0.0,
                mean_return=0.0,
                up_ratio=0.0,
                strong_count=0,
                weak_count=0,
                volume_multiplier=1.0,
                fund_positive_ratio=0.5,
                data_status="ok",
                missing_members=[],
            ),
        }

        rotation = analyze_group_rotation(pool_states, "20260502", registry=None)

        assert rotation.data_status == "ok"
        assert rotation.group_ranking == ["direct_peers", "industry_chain"]

    def test_extreme_returns(self):
        """测试极端涨跌幅"""
        pool_states = {
            "direct_peers": PoolState(
                universe_id="direct_peers",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=3,
                valid_count=3,
                median_return=10.0,  # 大涨
                mean_return=9.0,
                up_ratio=1.0,
                strong_count=3,
                weak_count=0,
                volume_multiplier=2.0,
                fund_positive_ratio=1.0,
                data_status="ok",
                missing_members=[],
            ),
            "industry_chain": PoolState(
                universe_id="industry_chain",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=4,
                valid_count=4,
                median_return=-10.0,  # 大跌
                mean_return=-9.0,
                up_ratio=0.0,
                strong_count=0,
                weak_count=4,
                volume_multiplier=0.5,
                fund_positive_ratio=0.0,
                data_status="ok",
                missing_members=[],
            ),
        }

        rotation = analyze_group_rotation(pool_states, "20260502", registry=None)

        # direct_peers 最强，industry_chain 最弱
        assert rotation.strongest_group == "direct_peers"
        assert rotation.weakest_group == "industry_chain"

        # spread = 10.0 - (-10.0) = 20.0
        calculator = SpreadCalculator()
        spreads = calculator.calculate_spreads(rotation.group_medians)
        assert spreads["industry_chain"] == 20.0


# ==================== can_be_benchmark 过滤测试 ====================

class TestBenchmarkFiltering:
    """测试 can_be_benchmark 过滤"""

    def test_only_benchmark_groups(self, registry):
        """测试只比较 benchmark 池子"""
        pool_states = {
            "direct_peers": PoolState(
                universe_id="direct_peers",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=3,
                valid_count=3,
                median_return=2.5,
                mean_return=2.3,
                up_ratio=0.67,
                strong_count=1,
                weak_count=0,
                volume_multiplier=1.2,
                fund_positive_ratio=0.67,
                data_status="ok",
                missing_members=[],
            ),
            "industry_chain": PoolState(
                universe_id="industry_chain",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=4,
                valid_count=4,
                median_return=1.0,
                mean_return=0.9,
                up_ratio=0.5,
                strong_count=0,
                weak_count=1,
                volume_multiplier=1.0,
                fund_positive_ratio=0.5,
                data_status="ok",
                missing_members=[],
            ),
            "theme_pool": PoolState(
                universe_id="theme_pool",
                trade_date="20260502",
                configured_count=8,
                enabled_count=8,
                benchmark_count=0,
                valid_count=6,
                median_return=5.0,  # 高涨跌幅，但不参与比较
                mean_return=4.5,
                up_ratio=0.8,
                strong_count=3,
                weak_count=0,
                volume_multiplier=2.0,
                fund_positive_ratio=0.8,
                data_status="ok",
                missing_members=[],
            ),
        }

        rotation = analyze_group_rotation(pool_states, "20260502", registry)

        # 只有 direct_peers 和 industry_chain 参与比较（can_be_benchmark=True）
        assert len(rotation.group_ranking) == 2
        assert rotation.strongest_group == "direct_peers"
        assert rotation.weakest_group == "industry_chain"
        assert "theme_pool" not in rotation.group_medians

    def test_all_non_benchmark(self, registry):
        """测试所有池子都是非 benchmark"""
        pool_states = {
            "theme_pool": PoolState(
                universe_id="theme_pool",
                trade_date="20260502",
                configured_count=8,
                enabled_count=8,
                benchmark_count=0,
                valid_count=6,
                median_return=5.0,
                mean_return=4.5,
                up_ratio=0.8,
                strong_count=3,
                weak_count=0,
                volume_multiplier=2.0,
                fund_positive_ratio=0.8,
                data_status="ok",
                missing_members=[],
            ),
            "trading_watchlist": PoolState(
                universe_id="trading_watchlist",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=0,
                valid_count=5,
                median_return=3.0,
                mean_return=2.5,
                up_ratio=0.6,
                strong_count=1,
                weak_count=0,
                volume_multiplier=1.5,
                fund_positive_ratio=0.6,
                data_status="ok",
                missing_members=[],
            ),
        }

        rotation = analyze_group_rotation(pool_states, "20260502", registry)

        # 无 benchmark 池子，数据不足
        assert rotation.data_status == "insufficient_data"