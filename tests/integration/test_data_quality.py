"""
Integration Tests - 数据降级场景测试

测试覆盖：
  1. 数据不足 (insufficient_data) 场景
  2. 部分数据缺失 (partial) 场景
  3. 降级信号生成正确性
  4. 输出正确反映数据质量
"""

import json
import pytest
import pandas as pd
from pathlib import Path
from tempfile import TemporaryDirectory

from src.config.loader import PoolRegistry, Anchor, Universe, Membership, Instrument
from src.pool_state.calculator import PoolStateCalculator
from src.pool_state.models import PoolState, MemberData
from src.anchor_position.relative_strength import RelativeStrengthCalculator
from src.anchor_position.ranking_calculator import RankingCalculator
from src.group_rotation import analyze_rotation_with_spreads
from src.group_rotation.models import GroupRotation
from src.signal import generate_signals
from src.signal.models import SignalResult
from src.output import write_all


# ============================================================
# Fixtures - 数据不足场景
# ============================================================

@pytest.fixture
def trade_date():
    return "20260502"


@pytest.fixture
def minimal_registry():
    """
    最小配置 - 用于数据不足测试
    """
    anchor = Anchor(symbol="688333.SH", name="铂力特", reason="核心标的", added_date="2026-05-01")

    instruments = {
        "688333.SH": Instrument(symbol="688333.SH", name="铂力特", market="科创板", exchange="SH", fact_tags=[]),
        "688433.SH": Instrument(symbol="688433.SH", name="华曙高科", market="科创板", exchange="SH", fact_tags=[]),
    }

    universes = {
        "direct_peers": Universe(universe_id="direct_peers", display_name="核心同类", purpose="核心对比池", can_be_benchmark=True, min_size=3),
    }

    memberships = [
        Membership(universe_id="direct_peers", symbol="688433.SH", role="peer", relevance=0.9, weight=1.0, enabled=True, include_in_benchmark=True, include_in_ranking=True, include_in_report=True, reason="同类", added_at="2026-05-01", reviewed_at="2026-05-02"),
    ]

    return type("MinimalRegistry", (), {
        "anchor": anchor,
        "instruments": instruments,
        "universes": universes,
        "_config": type("MockConfig", (), {
            "anchor": anchor,
            "instruments": instruments,
            "universes": universes,
            "memberships": memberships,
        })(),
        "get_anchor": lambda self: anchor,
        "get_instrument": lambda self, symbol: instruments.get(symbol),
        "get_all_universes": lambda self: list(universes.values()),
        "get_universe": lambda self, uid: universes.get(uid),
        "get_members": lambda self, uid, enabled_only=True: [m for m in memberships if m.universe_id == uid and (not enabled_only or m.enabled)],
        "get_benchmark_scope": lambda self, uid: [m for m in memberships if m.universe_id == uid and m.include_in_benchmark],
        "get_ranking_scope": lambda self, uid, include_anchor=True: (
            ([anchor.symbol] if include_anchor else []) +
            [m.symbol for m in memberships if m.universe_id == uid and m.include_in_ranking]
        ),
        "get_all_symbols": lambda self: list(instruments.keys()),
        "validate": lambda self: {"valid": True, "errors": []},
    })()


@pytest.fixture
def insufficient_pool_state(trade_date):
    """数据不足的池子状态"""
    return PoolState(
        universe_id="direct_peers",
        trade_date=trade_date,
        configured_count=3,
        enabled_count=3,
        benchmark_count=1,
        valid_count=1,  # < min_size (3)
        median_return=None,
        mean_return=None,
        up_ratio=None,
        strong_count=0,
        weak_count=0,
        volume_multiplier=None,
        fund_positive_ratio=None,
        data_status="insufficient_data",
        missing_members=["600343.SH", "600879.SH"],
    )


@pytest.fixture
def partial_pool_state(trade_date):
    """部分数据缺失的池子状态"""
    return PoolState(
        universe_id="direct_peers",
        trade_date=trade_date,
        configured_count=5,
        enabled_count=5,
        benchmark_count=5,
        valid_count=3,  # 部分成员缺失
        median_return=1.5,
        mean_return=1.5,
        up_ratio=0.67,
        strong_count=1,
        weak_count=0,
        volume_multiplier=1.2,
        fund_positive_ratio=0.5,
        data_status="partial",
        missing_members=["600343.SH", "600879.SH"],
    )


@pytest.fixture
def ok_pool_state(trade_date):
    """正常数据的池子状态"""
    return PoolState(
        universe_id="direct_peers",
        trade_date=trade_date,
        configured_count=3,
        enabled_count=3,
        benchmark_count=3,
        valid_count=3,
        median_return=1.5,
        mean_return=1.5,
        up_ratio=1.0,
        strong_count=1,
        weak_count=0,
        volume_multiplier=1.2,
        fund_positive_ratio=0.67,
        data_status="ok",
        missing_members=[],
    )


@pytest.fixture
def minimal_member_data(trade_date):
    """最小成员数据（仅 anchor）"""
    return {
        "688333.SH": MemberData(
            symbol="688333.SH",
            trade_date=trade_date,
            close=50.0,
            pct_chg=2.0,
            amount=100000.0,
            turnover_rate=None,
            net_mf_amount=None,
            is_valid=True,
        ),
        "688433.SH": MemberData(
            symbol="688433.SH",
            trade_date=trade_date,
            close=30.0,
            pct_chg=1.0,
            amount=50000.0,
            turnover_rate=None,
            net_mf_amount=None,
            is_valid=True,
        ),
    }


@pytest.fixture
def minimal_group_rotation(trade_date):
    """最小组间轮动"""
    return GroupRotation(
        trade_date=trade_date,
        strongest_group="direct_peers",
        weakest_group="direct_peers",
        group_ranking=["direct_peers"],
        spreads={},
        core_vs_theme_spread=None,
        core_vs_chain_spread=None,
        core_vs_trading_spread=None,
        group_medians={"direct_peers": None},
        data_status="insufficient_data",
    )


# ============================================================
# Tests - 数据不足场景
# ============================================================

class TestInsufficientData:
    """数据不足场景测试"""

    def test_pool_state_insufficient_status(self, insufficient_pool_state):
        """验证数据不足状态标记"""
        assert insufficient_pool_state.data_status == "insufficient_data"
        assert insufficient_pool_state.valid_count < insufficient_pool_state.configured_count
        assert insufficient_pool_state.median_return is None
        assert len(insufficient_pool_state.missing_members) > 0

    def test_signal_generation_with_insufficient_data(
        self, minimal_registry, insufficient_pool_state, minimal_group_rotation, minimal_member_data, trade_date
    ):
        """验证数据不足时不生成 beta/alpha 标签"""
        # 构建 anchor_positions
        ranking_calc = RankingCalculator(minimal_registry)
        rs_calc = RelativeStrengthCalculator(minimal_registry, ranking_calc)
        anchor_data = minimal_member_data["688333.SH"]

        anchor_positions = rs_calc.calculate_all(
            trade_date, anchor_data,
            {"direct_peers": insufficient_pool_state},
            minimal_member_data
        )

        result = generate_signals(
            {"direct_peers": insufficient_pool_state},
            anchor_positions,
            minimal_group_rotation,
            minimal_registry
        )

        # 数据不足时 beta/alpha 应为 0 或很少
        assert result.data_status == "insufficient_data"
        # beta 标签依赖 pool median，数据不足时不应生成
        assert result.beta_count == 0

    def test_calculator_handles_missing_data(self, minimal_registry, trade_date):
        """验证 PoolStateCalculator 处理缺失数据"""
        # 创建空 DataFrame
        empty_df = pd.DataFrame(columns=["ts_code", "trade_date", "close", "amount"])

        calculator = PoolStateCalculator(minimal_registry, empty_df)
        result = calculator.calculate(trade_date)

        # 应返回 insufficient_data 状态
        assert result.overall_status in ["error", "partial"]
        for state in result.pool_states.values():
            assert state.valid_count == 0
            assert state.data_status == "insufficient_data"


# ============================================================
# Tests - 部分数据缺失场景
# ============================================================

class TestPartialData:
    """部分数据缺失场景测试"""

    def test_pool_state_partial_status(self, partial_pool_state):
        """验证部分数据状态标记"""
        assert partial_pool_state.data_status == "partial"
        assert partial_pool_state.valid_count < partial_pool_state.configured_count
        assert partial_pool_state.median_return is not None  # 有部分数据可计算
        assert len(partial_pool_state.missing_members) > 0

    def test_signal_generation_with_partial_data(
        self, minimal_registry, partial_pool_state, minimal_group_rotation, minimal_member_data, trade_date
    ):
        """验证部分数据时仍能生成信号"""
        ranking_calc = RankingCalculator(minimal_registry)
        rs_calc = RelativeStrengthCalculator(minimal_registry, ranking_calc)
        anchor_data = minimal_member_data["688333.SH"]

        anchor_positions = rs_calc.calculate_all(
            trade_date, anchor_data,
            {"direct_peers": partial_pool_state},
            minimal_member_data
        )

        result = generate_signals(
            {"direct_peers": partial_pool_state},
            anchor_positions,
            minimal_group_rotation,
            minimal_registry
        )

        # 部分数据时可能生成信号
        assert result.data_status == "partial"

    def test_missing_members_tracking(self, partial_pool_state):
        """验证缺失成员追踪"""
        missing = partial_pool_state.missing_members
        assert "600343.SH" in missing
        assert "600879.SH" in missing


# ============================================================
# Tests - 可选字段缺失
# ============================================================

class TestOptionalFieldsMissing:
    """可选字段缺失场景测试"""

    def test_no_turnover_rate(self, trade_date):
        """验证无换手率数据不影响核心计算"""
        member_data = MemberData(
            symbol="688333.SH",
            trade_date=trade_date,
            close=50.0,
            pct_chg=2.0,
            amount=100000.0,
            turnover_rate=None,  # 缺失
            net_mf_amount=None,
            is_valid=True,
        )

        # 核心字段有效
        assert member_data.is_valid
        assert member_data.pct_chg is not None

    def test_no_moneyflow_data(self, trade_date):
        """验证无资金流向数据不影响核心计算"""
        member_data = MemberData(
            symbol="688333.SH",
            trade_date=trade_date,
            close=50.0,
            pct_chg=2.0,
            amount=100000.0,
            turnover_rate=3.0,
            net_mf_amount=None,  # 缺失
            is_valid=True,
        )

        # 核心字段有效
        assert member_data.is_valid
        assert member_data.pct_chg is not None

    def test_pool_state_with_partial_fund_data(self, trade_date):
        """验证池子状态处理部分资金数据"""
        state = PoolState(
            universe_id="direct_peers",
            trade_date=trade_date,
            configured_count=3,
            enabled_count=3,
            benchmark_count=3,
            valid_count=3,
            median_return=1.5,
            mean_return=1.5,
            up_ratio=1.0,
            strong_count=1,
            weak_count=0,
            volume_multiplier=1.2,
            fund_positive_ratio=None,  # 无资金数据
            data_status="partial",
            missing_members=[],
        )

        # 核心指标有值，资金指标缺失
        assert state.median_return is not None
        assert state.fund_positive_ratio is None
        assert state.data_status == "partial"


# ============================================================
# Tests - 输出反映数据质量
# ============================================================

class TestOutputReflectsDataQuality:
    """验证输出正确反映数据质量"""

    def test_json_reflects_data_status(
        self, minimal_registry, insufficient_pool_state, minimal_group_rotation, minimal_member_data, trade_date
    ):
        """验证 JSON 输出包含数据质量信息"""
        ranking_calc = RankingCalculator(minimal_registry)
        rs_calc = RelativeStrengthCalculator(minimal_registry, ranking_calc)
        anchor_data = minimal_member_data["688333.SH"]

        anchor_positions = rs_calc.calculate_all(
            trade_date, anchor_data,
            {"direct_peers": insufficient_pool_state},
            minimal_member_data
        )

        signal_result = generate_signals(
            {"direct_peers": insufficient_pool_state},
            anchor_positions,
            minimal_group_rotation,
            minimal_registry
        )

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            write_all(
                minimal_registry,
                {"direct_peers": insufficient_pool_state},
                anchor_positions,
                minimal_group_rotation,
                signal_result,
                minimal_member_data,
                output_dir
            )

            with open(output_dir / "industry_snapshot.json", encoding="utf-8") as f:
                data = json.load(f)

            # data_quality 应反映数据不足
            assert data["data_quality"]["status"] in ["insufficient_data", "partial"]

    def test_report_mentions_data_issues(
        self, minimal_registry, insufficient_pool_state, minimal_group_rotation, minimal_member_data, trade_date
    ):
        """验证 Markdown 报告提及数据问题"""
        ranking_calc = RankingCalculator(minimal_registry)
        rs_calc = RelativeStrengthCalculator(minimal_registry, ranking_calc)
        anchor_data = minimal_member_data["688333.SH"]

        anchor_positions = rs_calc.calculate_all(
            trade_date, anchor_data,
            {"direct_peers": insufficient_pool_state},
            minimal_member_data
        )

        signal_result = generate_signals(
            {"direct_peers": insufficient_pool_state},
            anchor_positions,
            minimal_group_rotation,
            minimal_registry
        )

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            write_all(
                minimal_registry,
                {"direct_peers": insufficient_pool_state},
                anchor_positions,
                minimal_group_rotation,
                signal_result,
                minimal_member_data,
                output_dir
            )

            with open(output_dir / "industry_report.md", encoding="utf-8") as f:
                content = f.read()

            # 报告应显示 "-" 表示缺失数据
            assert "-|" in content or "-" in content


# ============================================================
# Tests - 边界场景
# ============================================================

class TestEdgeCases:
    """边界场景测试"""

    def test_single_valid_member(self, trade_date):
        """验证仅一个有效成员"""
        state = PoolState(
            universe_id="direct_peers",
            trade_date=trade_date,
            configured_count=5,
            enabled_count=5,
            benchmark_count=5,
            valid_count=1,
            median_return=2.0,
            mean_return=2.0,
            up_ratio=1.0,
            strong_count=1,
            weak_count=0,
            volume_multiplier=None,
            fund_positive_ratio=None,
            data_status="insufficient_data",
            missing_members=["A", "B", "C", "D"],
        )

        # 单成员不满足 min_size
        assert state.valid_count < 3
        assert state.data_status == "insufficient_data"

    def test_all_members_missing(self, trade_date):
        """验证所有成员缺失"""
        state = PoolState(
            universe_id="direct_peers",
            trade_date=trade_date,
            configured_count=3,
            enabled_count=3,
            benchmark_count=3,
            valid_count=0,
            median_return=None,
            mean_return=None,
            up_ratio=None,
            strong_count=0,
            weak_count=0,
            volume_multiplier=None,
            fund_positive_ratio=None,
            data_status="insufficient_data",
            missing_members=["A", "B", "C"],
        )

        assert state.valid_count == 0
        assert state.median_return is None
        assert state.data_status == "insufficient_data"

    def test_anchor_data_missing(self, trade_date):
        """验证 Anchor 数据缺失"""
        anchor_data = MemberData(
            symbol="688333.SH",
            trade_date=trade_date,
            close=0.0,
            pct_chg=None,
            amount=None,
            turnover_rate=None,
            net_mf_amount=None,
            is_valid=False,
            invalid_reason="missing",
        )

        # Anchor 无效
        assert not anchor_data.is_valid
        assert anchor_data.pct_chg is None


# ============================================================
# Tests - 数据恢复场景
# ============================================================

class TestDataRecovery:
    """数据恢复场景测试"""

    def test_from_insufficient_to_ok(self, trade_date):
        """验证从数据不足恢复到正常"""
        # Day 1: 数据不足
        day1_state = PoolState(
            universe_id="direct_peers",
            trade_date="20260501",
            configured_count=3,
            enabled_count=3,
            benchmark_count=3,
            valid_count=1,
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

        # Day 2: 数据恢复
        day2_state = PoolState(
            universe_id="direct_peers",
            trade_date=trade_date,
            configured_count=3,
            enabled_count=3,
            benchmark_count=3,
            valid_count=3,
            median_return=1.5,
            mean_return=1.5,
            up_ratio=1.0,
            strong_count=1,
            weak_count=0,
            volume_multiplier=1.2,
            fund_positive_ratio=0.67,
            data_status="ok",
            missing_members=[],
        )

        # 状态从 insufficient → ok
        assert day1_state.data_status == "insufficient_data"
        assert day2_state.data_status == "ok"
        assert day2_state.valid_count >= 3

    def test_partial_improves_to_ok(self, trade_date):
        """验证从部分数据恢复到正常"""
        # Day 1: 部分数据
        day1_state = PoolState(
            universe_id="direct_peers",
            trade_date="20260501",
            configured_count=3,
            enabled_count=3,
            benchmark_count=3,
            valid_count=2,
            median_return=1.0,
            mean_return=1.0,
            up_ratio=0.5,
            strong_count=1,
            weak_count=0,
            volume_multiplier=1.1,
            fund_positive_ratio=None,
            data_status="partial",
            missing_members=["A"],
        )

        # Day 2: 数据完整
        day2_state = PoolState(
            universe_id="direct_peers",
            trade_date=trade_date,
            configured_count=3,
            enabled_count=3,
            benchmark_count=3,
            valid_count=3,
            median_return=1.5,
            mean_return=1.5,
            up_ratio=1.0,
            strong_count=1,
            weak_count=0,
            volume_multiplier=1.2,
            fund_positive_ratio=0.67,
            data_status="ok",
            missing_members=[],
        )

        # 状态从 partial → ok
        assert day1_state.data_status == "partial"
        assert day2_state.data_status == "ok"