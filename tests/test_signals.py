"""
Signals Layer 单元测试

测试覆盖：
  1. Signal dataclass 结构
  2. Evidence 结构
  3. generate_signals() 主流程
  4. 各类标签生成（beta/alpha/volume/rotation/abnormal）
  5. 置信度计算
  6. 边界情况（阈值附近、数据缺失、极端值）

按 implementation.md Phase 5 设计
"""

import pytest

from src.signal.models import Signal, SignalResult, Evidence
from src.signal.label_generator import (
    generate_signals,
    generate_beta_signals,
    generate_alpha_signals,
    generate_volume_signals,
    generate_rotation_signals,
    generate_abnormal_signals,
)
from src.signal.confidence import calculate_confidence, calculate_confidence_from_rank
from src.signal.rules import (
    BETA_POSITIVE_THRESHOLD,
    BETA_NEGATIVE_THRESHOLD,
    ALPHA_POSITIVE_THRESHOLD,
    VOLUME_HIGH_THRESHOLD,
)
from src.pool_state.models import PoolState
from src.anchor_position.relative_strength import RelativeStrength
from src.group_rotation.models import GroupRotation


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def sample_pool_states():
    """样本池子状态 - Beta为正、扩散增强"""
    return {
        "direct_peers": PoolState(
            universe_id="direct_peers",
            trade_date="20260502",
            configured_count=5,
            enabled_count=5,
            benchmark_count=3,
            valid_count=3,
            median_return=2.5,      # Beta为正
            mean_return=2.3,
            up_ratio=0.80,          # 扩散增强
            strong_count=2,
            weak_count=0,
            volume_multiplier=1.8,  # 放量
            fund_positive_ratio=0.70,  # 主力资金领先
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
            median_return=3.0,
            mean_return=2.8,
            up_ratio=0.75,
            strong_count=2,
            weak_count=0,
            volume_multiplier=1.5,
            fund_positive_ratio=0.65,
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
            median_return=0.8,      # 温和上涨
            mean_return=0.7,
            up_ratio=0.50,
            strong_count=0,
            weak_count=1,
            volume_multiplier=1.0,
            fund_positive_ratio=0.40,
            data_status="ok",
            missing_members=[],
        ),
    }


@pytest.fixture
def sample_anchor_positions():
    """样本 Anchor 相对位置 - Alpha为正、跑赢核心"""
    return {
        "direct_peers": RelativeStrength(
            universe_id="direct_peers",
            trade_date="20260502",
            anchor_return=3.5,
            pool_median=2.5,
            relative_strength=1.0,    # Alpha为正
            position="outperform",
            rank_return=1,            # 排名第一（前排）
            rank_volume=2,
            rank_turnover=2,
            rank_fund=2,
            total_count=4,
            valuation_percentile=None,
            data_status="ok",
        ),
    }


@pytest.fixture
def sample_group_rotation():
    """样本组间轮动 - 主题池略强"""
    return GroupRotation(
        trade_date="20260502",
        strongest_group="theme_pool",
        weakest_group="trading_watchlist",
        group_ranking=["theme_pool", "direct_peers", "trading_watchlist"],
        spreads={"theme_pool": -0.5},
        core_vs_theme_spread=-0.5,  # 主题池略强于核心
        core_vs_chain_spread=1.0,
        core_vs_trading_spread=1.7,
        group_medians={"direct_peers": 2.5, "theme_pool": 3.0, "trading_watchlist": 0.8},
        data_status="ok",
    )


# ============================================================
# 置信度计算测试
# ============================================================

class TestConfidenceCalculation:
    """测试置信度计算"""

    def test_high_confidence(self):
        """高置信度：远超阈值"""
        confidence = calculate_confidence(5.0, 1.0, is_direction_positive=True)
        assert confidence == "high"  # margin = 4.0, ratio = 4.0

    def test_medium_confidence(self):
        """中等置信度：明显满足"""
        confidence = calculate_confidence(2.0, 1.0, is_direction_positive=True)
        assert confidence == "medium"  # margin = 1.0, ratio = 1.0

    def test_low_confidence(self):
        """低置信度：刚好满足"""
        confidence = calculate_confidence(1.2, 1.0, is_direction_positive=True)
        assert confidence == "low"  # margin = 0.2, ratio = 0.2

    def test_negative_direction(self):
        """负方向置信度"""
        confidence = calculate_confidence(-2.0, -0.5, is_direction_positive=False)
        # value < threshold: margin = threshold - value = -0.5 - (-2.0) = 1.5
        # ratio = 1.5 / 0.5 = 3.0 → high
        assert confidence == "high"

    def test_zero_threshold(self):
        """零阈值特殊处理"""
        confidence = calculate_confidence(3.0, 0.0)
        assert confidence == "high"


# ============================================================
# Beta 信号测试
# ============================================================

class TestBetaSignals:
    """测试 Beta 类信号生成"""

    def test_beta_positive(self, sample_pool_states):
        """测试行业Beta为正"""
        signals = generate_beta_signals(sample_pool_states, "20260502")

        beta_positive = [s for s in signals if s.label == "行业Beta为正"]
        assert len(beta_positive) == 1
        assert beta_positive[0].is_active == True
        assert beta_positive[0].category == "beta"
        assert beta_positive[0].evidence.value == 2.5
        assert beta_positive[0].evidence.threshold == BETA_POSITIVE_THRESHOLD

    def test_diffusion_enhance(self, sample_pool_states):
        """测试行业扩散增强"""
        signals = generate_beta_signals(sample_pool_states, "20260502")

        diffusion = [s for s in signals if s.label == "行业扩散增强"]
        assert len(diffusion) == 1
        assert diffusion[0].evidence.value == 0.80

    def test_beta_negative_scenario(self):
        """测试行业Beta为负场景"""
        pool_states = {
            "direct_peers": PoolState(
                universe_id="direct_peers",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=3,
                valid_count=3,
                median_return=-2.0,  # Beta为负
                mean_return=-1.8,
                up_ratio=0.20,      # 扩散不足
                strong_count=0,
                weak_count=3,       # 行业分化
                volume_multiplier=0.6,
                fund_positive_ratio=0.20,
                data_status="ok",
                missing_members=[],
            )
        }

        signals = generate_beta_signals(pool_states, "20260502")

        beta_negative = [s for s in signals if s.label == "行业Beta为负"]
        assert len(beta_negative) == 1

        diffusion_insufficient = [s for s in signals if s.label == "行业扩散不足"]
        assert len(diffusion_insufficient) == 1

        divergence = [s for s in signals if s.label == "行业分化"]
        assert len(divergence) == 1

    def test_neutral_zone(self):
        """测试中性区间"""
        pool_states = {
            "direct_peers": PoolState(
                universe_id="direct_peers",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=3,
                valid_count=3,
                median_return=0.0,  # 中性
                mean_return=0.0,
                up_ratio=0.50,
                strong_count=0,
                weak_count=0,
                volume_multiplier=1.0,
                fund_positive_ratio=0.50,
                data_status="ok",
                missing_members=[],
            )
        }

        signals = generate_beta_signals(pool_states, "20260502")

        beta_neutral = [s for s in signals if s.label == "行业Beta为中性"]
        assert len(beta_neutral) == 1
        assert beta_neutral[0].is_active == True

    def test_missing_pool_data(self):
        """测试池子数据缺失"""
        pool_states = {}  # 无 direct_peers

        signals = generate_beta_signals(pool_states, "20260502")
        assert len(signals) == 0


# ============================================================
# Alpha 信号测试
# ============================================================

class TestAlphaSignals:
    """测试 Alpha 类信号生成"""

    def test_alpha_positive(self, sample_anchor_positions, sample_pool_states):
        """测试个股Alpha为正"""
        signals = generate_alpha_signals(sample_anchor_positions, sample_pool_states, "20260502")

        alpha_positive = [s for s in signals if s.label == "个股Alpha为正"]
        assert len(alpha_positive) == 1
        assert alpha_positive[0].evidence.value == 1.0

    def test_outperform_core(self, sample_anchor_positions, sample_pool_states):
        """测试跑赢核心同类"""
        signals = generate_alpha_signals(sample_anchor_positions, sample_pool_states, "20260502")

        outperform = [s for s in signals if s.label == "跑赢核心同类"]
        assert len(outperform) == 1

    def test_front_rank(self, sample_anchor_positions, sample_pool_states):
        """测试处于行业前排"""
        signals = generate_alpha_signals(sample_anchor_positions, sample_pool_states, "20260502")

        front_rank = [s for s in signals if s.label == "处于行业前排"]
        assert len(front_rank) == 1
        assert front_rank[0].evidence.percentile == 25.0  # rank=1, total=4

    def test_alpha_negative_scenario(self):
        """测试个股Alpha为负场景"""
        anchor_positions = {
            "direct_peers": RelativeStrength(
                universe_id="direct_peers",
                trade_date="20260502",
                anchor_return=-1.0,
                pool_median=1.0,
                relative_strength=-2.0,  # Alpha为负
                position="underperform",
                rank_return=4,  # 排名最后
                rank_volume=4,
                rank_turnover=4,
                rank_fund=4,
                total_count=4,
                valuation_percentile=None,
                data_status="ok",
            )
        }

        pool_states = {
            "direct_peers": PoolState(
                universe_id="direct_peers",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=3,
                valid_count=3,
                median_return=1.0,
                mean_return=0.8,
                up_ratio=0.60,
                strong_count=1,
                weak_count=0,
                volume_multiplier=1.2,
                fund_positive_ratio=0.55,
                data_status="ok",
                missing_members=[],
            )
        }

        signals = generate_alpha_signals(anchor_positions, pool_states, "20260502")

        alpha_negative = [s for s in signals if s.label == "个股Alpha为负"]
        assert len(alpha_negative) == 1

        underperform = [s for s in signals if s.label == "跑输核心同类"]
        assert len(underperform) == 1


# ============================================================
# Volume 信号测试
# ============================================================

class TestVolumeSignals:
    """测试 Volume 类信号生成"""

    def test_volume_up(self, sample_pool_states, sample_anchor_positions):
        """测试放量上涨"""
        signals = generate_volume_signals(sample_pool_states, sample_anchor_positions, "20260502")

        volume_up = [s for s in signals if s.label == "放量上涨"]
        assert len(volume_up) == 1
        assert volume_up[0].evidence.value == 1.8
        assert volume_up[0].evidence.secondary_value == 3.5

    def test_fund_lead(self, sample_pool_states, sample_anchor_positions):
        """测试主力资金领先"""
        signals = generate_volume_signals(sample_pool_states, sample_anchor_positions, "20260502")

        fund_lead = [s for s in signals if s.label == "主力资金领先"]
        assert len(fund_lead) == 1
        assert fund_lead[0].evidence.value == 0.70

    def test_fund_price_resonance(self, sample_pool_states, sample_anchor_positions):
        """测试资金价格共振"""
        signals = generate_volume_signals(sample_pool_states, sample_anchor_positions, "20260502")

        resonance = [s for s in signals if s.label == "资金价格共振"]
        assert len(resonance) == 1

    def test_low_volume_scenario(self):
        """测试缩量场景"""
        pool_states = {
            "direct_peers": PoolState(
                universe_id="direct_peers",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=3,
                valid_count=3,
                median_return=0.5,
                mean_return=0.3,
                up_ratio=0.50,
                strong_count=0,
                weak_count=0,
                volume_multiplier=0.5,  # 缩量
                fund_positive_ratio=0.50,
                data_status="ok",
                missing_members=[],
            )
        }

        anchor_positions = {
            "direct_peers": RelativeStrength(
                universe_id="direct_peers",
                trade_date="20260502",
                anchor_return=0.5,
                pool_median=0.5,
                relative_strength=0.0,
                position="neutral",
                rank_return=2,
                rank_volume=2,
                rank_turnover=2,
                rank_fund=2,
                total_count=4,
                valuation_percentile=None,
                data_status="ok",
            )
        }

        signals = generate_volume_signals(pool_states, anchor_positions, "20260502")

        low_volume = [s for s in signals if s.label == "缩量调整"]
        assert len(low_volume) == 1


# ============================================================
# Rotation 信号测试
# ============================================================

class TestRotationSignals:
    """测试 Rotation 类信号生成"""

    def test_trading_pool_heat(self, sample_group_rotation, sample_pool_states):
        """测试交易观察池升温"""
        signals = generate_rotation_signals(sample_group_rotation, sample_pool_states, "20260502")

        trading_heat = [s for s in signals if s.label == "交易观察池升温"]
        assert len(trading_heat) == 1

    def test_theme_stronger_than_core(self):
        """测试主题扩散强于核心同类"""
        rotation = GroupRotation(
            trade_date="20260502",
            strongest_group="theme_pool",
            weakest_group="direct_peers",
            group_ranking=["theme_pool", "direct_peers"],
            spreads={"direct_peers": -2.0},  # 主题池强于核心 2%
            core_vs_theme_spread=-2.0,
            core_vs_chain_spread=1.0,
            core_vs_trading_spread=1.0,
            group_medians={"theme_pool": 3.5, "direct_peers": 1.5},
            data_status="ok",
        )

        pool_states = {
            "trading_watchlist": PoolState(
                universe_id="trading_watchlist",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=0,
                valid_count=5,
                median_return=0.3,
                mean_return=0.2,
                up_ratio=0.40,
                strong_count=0,
                weak_count=1,
                volume_multiplier=1.0,
                fund_positive_ratio=0.40,
                data_status="ok",
                missing_members=[],
            ),
        }

        signals = generate_rotation_signals(rotation, pool_states, "20260502")

        theme_stronger = [s for s in signals if s.label == "主题扩散强于核心同类"]
        assert len(theme_stronger) == 1


# ============================================================
# Abnormal 信号测试
# ============================================================

class TestAbnormalSignals:
    """测试 Abnormal 类信号生成"""

    def test_industry_strong_anchor_weak(self):
        """测试行业强但个股弱"""
        pool_states = {
            "direct_peers": PoolState(
                universe_id="direct_peers",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=3,
                valid_count=3,
                median_return=3.0,      # 行业涨 3%
                mean_return=2.8,
                up_ratio=0.80,
                strong_count=2,
                weak_count=0,
                volume_multiplier=1.5,
                fund_positive_ratio=0.70,
                data_status="ok",
                missing_members=[],
            )
        }

        anchor_positions = {
            "direct_peers": RelativeStrength(
                universe_id="direct_peers",
                trade_date="20260502",
                anchor_return=-1.0,     # Anchor 跌 1%
                pool_median=3.0,
                relative_strength=-4.0,  # 相对跌 4%
                position="underperform",
                rank_return=4,
                rank_volume=4,
                rank_turnover=4,
                rank_fund=4,
                total_count=4,
                valuation_percentile=None,
                data_status="ok",
            )
        }

        rotation = GroupRotation(
            trade_date="20260502",
            strongest_group="direct_peers",
            weakest_group="",
            group_ranking=["direct_peers"],
            spreads={},
            core_vs_theme_spread=None,
            core_vs_chain_spread=None,
            core_vs_trading_spread=None,
            group_medians={"direct_peers": 3.0},
            data_status="ok",
        )

        signals = generate_abnormal_signals(pool_states, anchor_positions, rotation, "20260502")

        abnormal = [s for s in signals if s.label == "行业强但个股弱"]
        assert len(abnormal) == 1
        assert abnormal[0].evidence.value == 7.0  # spread = 3.0 - (-4.0)

    def test_industry_weak_anchor_strong(self):
        """测试行业弱但个股强"""
        pool_states = {
            "direct_peers": PoolState(
                universe_id="direct_peers",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=3,
                valid_count=3,
                median_return=-2.0,     # 行业跌 2%
                mean_return=-1.8,
                up_ratio=0.20,
                strong_count=0,
                weak_count=2,
                volume_multiplier=0.8,
                fund_positive_ratio=0.30,
                data_status="ok",
                missing_members=[],
            )
        }

        anchor_positions = {
            "direct_peers": RelativeStrength(
                universe_id="direct_peers",
                trade_date="20260502",
                anchor_return=3.0,      # Anchor 涨 3%
                pool_median=-2.0,
                relative_strength=5.0,  # 相对涨 5%
                position="outperform",
                rank_return=1,
                rank_volume=1,
                rank_turnover=1,
                rank_fund=1,
                total_count=4,
                valuation_percentile=None,
                data_status="ok",
            )
        }

        rotation = GroupRotation(
            trade_date="20260502",
            strongest_group="anchor",
            weakest_group="direct_peers",
            group_ranking=["anchor", "direct_peers"],
            spreads={},
            core_vs_theme_spread=None,
            core_vs_chain_spread=None,
            core_vs_trading_spread=None,
            group_medians={"direct_peers": -2.0},
            data_status="ok",
        )

        signals = generate_abnormal_signals(pool_states, anchor_positions, rotation, "20260502")

        abnormal = [s for s in signals if s.label == "行业弱但个股强"]
        assert len(abnormal) == 1


# ============================================================
# 全流程测试
# ============================================================

class TestGenerateSignals:
    """测试完整信号生成"""

    def test_generate_all_signals(
        self, sample_pool_states, sample_anchor_positions, sample_group_rotation
    ):
        """测试生成所有信号"""
        result = generate_signals(
            sample_pool_states,
            sample_anchor_positions,
            sample_group_rotation,
        )

        assert result.trade_date == "20260502"
        assert result.data_status == "ok"
        assert len(result.signals) > 0

        # 验证分类统计
        assert result.beta_count >= 0
        assert result.alpha_count >= 0
        assert result.volume_count >= 0
        assert result.rotation_count >= 0
        assert result.abnormal_count >= 0

        # 验证总数一致
        total = result.beta_count + result.alpha_count + result.volume_count + result.rotation_count + result.abnormal_count
        assert total == len(result.signals)

    def test_insufficient_data(self):
        """测试数据不足"""
        pool_states = {
            "direct_peers": PoolState(
                universe_id="direct_peers",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=3,
                valid_count=1,  # 数据不足
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
        }

        anchor_positions = {}
        rotation = GroupRotation(
            trade_date="20260502",
            strongest_group="",
            weakest_group="",
            group_ranking=[],
            spreads={},
            core_vs_theme_spread=None,
            core_vs_chain_spread=None,
            core_vs_trading_spread=None,
            group_medians={},
            data_status="insufficient_data",
        )

        result = generate_signals(pool_states, anchor_positions, rotation)

        assert result.data_status == "insufficient_data"
        assert len(result.signals) == 0


# ============================================================
# 边界测试
# ============================================================

class TestBoundaryCases:
    """测试边界情况"""

    def test_threshold_exact_match(self):
        """测试恰好等于阈值"""
        pool_states = {
            "direct_peers": PoolState(
                universe_id="direct_peers",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=3,
                valid_count=3,
                median_return=0.5,  # 恰好等于阈值
                mean_return=0.5,
                up_ratio=0.50,
                strong_count=0,
                weak_count=0,
                volume_multiplier=1.0,
                fund_positive_ratio=0.50,
                data_status="ok",
                missing_members=[],
            )
        }

        signals = generate_beta_signals(pool_states, "20260502")

        # 恰好等于阈值不算激活（需要 > threshold）
        beta_positive = [s for s in signals if s.label == "行业Beta为正" and s.is_active]
        assert len(beta_positive) == 0

    def test_extreme_values(self):
        """测试极端值（涨停/跌停）"""
        pool_states = {
            "direct_peers": PoolState(
                universe_id="direct_peers",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=3,
                valid_count=3,
                median_return=10.0,  # 大涨
                mean_return=9.5,
                up_ratio=1.0,
                strong_count=3,
                weak_count=0,
                volume_multiplier=3.0,  # 大放量
                fund_positive_ratio=1.0,
                data_status="ok",
                missing_members=[],
            )
        }

        signals = generate_beta_signals(pool_states, "20260502")

        beta_positive = [s for s in signals if s.label == "行业Beta为正"]
        assert len(beta_positive) == 1
        assert beta_positive[0].confidence == "high"  # 远超阈值


# ============================================================
# 数据类不可变测试
# ============================================================

class TestDataclassFrozen:
    """测试数据类不可变"""

    def test_signal_frozen(self):
        """测试 Signal 不可变"""
        signal = Signal(
            label="行业Beta为正",
            category="beta",
            evidence=Evidence(value=2.5, threshold=0.5),
            confidence="high",
            trade_date="20260502",
        )

        with pytest.raises(AttributeError):
            signal.label = "行业Beta为负"

    def test_evidence_frozen(self):
        """测试 Evidence 不可变"""
        evidence = Evidence(value=2.5, threshold=0.5)

        with pytest.raises(AttributeError):
            evidence.value = 3.0

    def test_signal_result_frozen(self):
        """测试 SignalResult 不可变"""
        result = SignalResult(
            trade_date="20260502",
            anchor_symbol="688333.SH",
            signals=[],
        )

        with pytest.raises(AttributeError):
            result.trade_date = "20260503"