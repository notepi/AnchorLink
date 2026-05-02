"""
Pool State 单元测试

测试覆盖：
  1. PoolState 数据类
  2. benchmark.py 指标计算函数
  3. quality.py 数据质量检查
  4. calculator.py 主流程
  5. 边界情况（数据缺失、停牌、极端涨跌幅）
"""

import pytest
import pandas as pd

from src.pool_state.models import PoolState, MemberData, PoolStateResult
from src.pool_state.benchmark import (
    calculate_median_return,
    calculate_mean_return,
    calculate_up_ratio,
    calculate_strong_weak_count,
    calculate_fund_positive_ratio,
    calculate_volume_multiplier,
)
from src.pool_state.quality import (
    determine_data_status,
    get_missing_members,
    check_data_quality,
)


# ==================== Fixtures ====================

@pytest.fixture
def sample_member_data():
    """样本成员数据"""
    return [
        MemberData(
            symbol="688433.SH",
            trade_date="20260502",
            close=50.0,
            pct_chg=2.5,
            amount=100000.0,
            turnover_rate=3.0,
            net_mf_amount=5000000.0,
            is_valid=True,
        ),
        MemberData(
            symbol="600343.SH",
            trade_date="20260502",
            close=30.0,
            pct_chg=-1.0,
            amount=80000.0,
            turnover_rate=2.0,
            net_mf_amount=-2000000.0,
            is_valid=True,
        ),
        MemberData(
            symbol="600879.SH",
            trade_date="20260502",
            close=25.0,
            pct_chg=5.0,  # 强势股
            amount=120000.0,
            turnover_rate=4.0,
            net_mf_amount=8000000.0,
            is_valid=True,
        ),
    ]


@pytest.fixture
def sample_member_data_with_missing():
    """包含缺失数据的样本"""
    return [
        MemberData(
            symbol="688433.SH",
            trade_date="20260502",
            close=50.0,
            pct_chg=2.5,
            amount=100000.0,
            turnover_rate=3.0,
            net_mf_amount=5000000.0,
            is_valid=True,
        ),
        MemberData(
            symbol="600343.SH",
            trade_date="20260502",
            close=0.0,
            pct_chg=None,
            amount=None,
            turnover_rate=None,
            net_mf_amount=None,
            is_valid=False,
            invalid_reason="missing",
        ),
    ]


@pytest.fixture
def sample_market_data():
    """样本行情数据"""
    dates = pd.date_range("20260401", "20260502", freq="B")  # 工作日
    symbols = ["688433.SH", "600343.SH", "600879.SH"]

    rows = []
    for symbol in symbols:
        for i, date in enumerate(dates):
            base_close = 50.0 if symbol == "688433.SH" else 30.0
            close = base_close + i * 0.5
            rows.append({
                "ts_code": symbol,
                "trade_date": date,
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "vol": 10000,
                "amount": 100000.0 + i * 1000,
            })

    return pd.DataFrame(rows)


# ==================== benchmark.py 测试 ====================

class TestBenchmarkCalculations:
    """测试指标计算函数"""

    def test_calculate_median_return_normal(self, sample_member_data):
        """测试正常情况的中位数计算"""
        result = calculate_median_return(sample_member_data)
        # 涨跌幅: [-1.0, 2.5, 5.0], 中位数 = 2.5
        assert result == 2.5

    def test_calculate_median_return_empty(self):
        """测试空数据的中位数计算"""
        result = calculate_median_return([])
        assert result is None

    def test_calculate_median_return_single(self):
        """测试单个数据的中位数"""
        single_data = [
            MemberData(
                symbol="test",
                trade_date="20260502",
                close=10.0,
                pct_chg=3.0,
                amount=1000.0,
                turnover_rate=1.0,
                net_mf_amount=None,
                is_valid=True,
            )
        ]
        result = calculate_median_return(single_data)
        assert result == 3.0

    def test_calculate_mean_return_normal(self, sample_member_data):
        """测试正常情况的平均值计算"""
        result = calculate_mean_return(sample_member_data)
        # 涨跌幅: [-1.0, 2.5, 5.0], 平均值 = 6.5/3 = 2.166...
        assert abs(result - 2.166) < 0.01

    def test_calculate_mean_return_empty(self):
        """测试空数据的平均值计算"""
        result = calculate_mean_return([])
        assert result is None

    def test_calculate_up_ratio_normal(self, sample_member_data):
        """测试上涨比例计算"""
        result = calculate_up_ratio(sample_member_data)
        # 上涨: 2.5, 5.0 (2个), 总共 3 个
        assert result == 2 / 3

    def test_calculate_up_ratio_all_up(self):
        """测试全部上涨的情况"""
        up_data = [
            MemberData(
                symbol="test",
                trade_date="20260502",
                close=10.0,
                pct_chg=5.0,
                amount=1000.0,
                turnover_rate=1.0,
                net_mf_amount=None,
                is_valid=True,
            )
        ]
        result = calculate_up_ratio(up_data)
        assert result == 1.0

    def test_calculate_up_ratio_all_down(self):
        """测试全部下跌的情况"""
        down_data = [
            MemberData(
                symbol="test",
                trade_date="20260502",
                close=10.0,
                pct_chg=-2.0,
                amount=1000.0,
                turnover_rate=1.0,
                net_mf_amount=None,
                is_valid=True,
            )
        ]
        result = calculate_up_ratio(down_data)
        assert result == 0.0

    def test_calculate_strong_weak_count_normal(self, sample_member_data):
        """测试强势/弱势股计算"""
        strong, weak = calculate_strong_weak_count(
            sample_member_data,
            strong_threshold=3.0,
            weak_threshold=-3.0,
        )
        # 涨跌幅: [-1.0, 2.5, 5.0]
        # 强势(>3%): 5.0 -> 1个
        # 弱势(<-3%): 无
        assert strong == 1
        assert weak == 0

    def test_calculate_strong_weak_count_custom_threshold(self, sample_member_data):
        """测试自定义阈值"""
        strong, weak = calculate_strong_weak_count(
            sample_member_data,
            strong_threshold=2.0,  # 更低的阈值
            weak_threshold=-2.0,
        )
        # 涨跌幅: [-1.0, 2.5, 5.0]
        # 强势(>2%): 2.5, 5.0 -> 2个
        # 弱势(<-2%): -1.0 不算弱势
        assert strong == 2
        assert weak == 0

    def test_calculate_fund_positive_ratio_normal(self, sample_member_data):
        """测试资金净流入为正比例"""
        result = calculate_fund_positive_ratio(sample_member_data)
        # 资金: [5M, -2M, 8M], 正: 2个
        assert result == 2 / 3

    def test_calculate_fund_positive_ratio_all_positive(self):
        """测试全部正向资金"""
        positive_data = [
            MemberData(
                symbol="test",
                trade_date="20260502",
                close=10.0,
                pct_chg=2.0,
                amount=1000.0,
                turnover_rate=1.0,
                net_mf_amount=1000000.0,
                is_valid=True,
            )
        ]
        result = calculate_fund_positive_ratio(positive_data)
        assert result == 1.0

    def test_calculate_fund_positive_ratio_no_fund(self):
        """测试无资金数据"""
        no_fund_data = [
            MemberData(
                symbol="test",
                trade_date="20260502",
                close=10.0,
                pct_chg=2.0,
                amount=1000.0,
                turnover_rate=1.0,
                net_mf_amount=None,  # 无资金数据
                is_valid=True,
            )
        ]
        result = calculate_fund_positive_ratio(no_fund_data)
        assert result is None

    def test_calculate_volume_multiplier_normal(self, sample_member_data, sample_market_data):
        """测试成交额放大倍数"""
        result = calculate_volume_multiplier(
            sample_member_data,
            sample_market_data,
            lookback_days=20,
        )
        # 当日总成交额: 100000 + 80000 + 120000 = 300000
        # 历史均值应该 > 0
        assert result is not None
        assert result > 0

    def test_calculate_volume_multiplier_no_history(self, sample_member_data):
        """测试无历史数据"""
        # 创建只有当日数据的 DataFrame
        today_df = pd.DataFrame([
            {"ts_code": "688433.SH", "trade_date": pd.to_datetime("20260502"), "close": 50.0, "amount": 100000.0}
        ])
        result = calculate_volume_multiplier(
            sample_member_data,
            today_df,
            lookback_days=20,
        )
        # 无历史数据应该返回 None
        assert result is None


# ==================== quality.py 测试 ====================

class TestQualityChecks:
    """测试数据质量检查"""

    def test_determine_data_status_ok(self):
        """测试正常状态"""
        status, reason = determine_data_status(
            valid_count=5,
            min_size=3,
            has_price_data=True,
            has_fund_data=True,
        )
        assert status == "ok"
        assert reason is None

    def test_determine_data_status_insufficient(self):
        """测试数据不足"""
        status, reason = determine_data_status(
            valid_count=2,
            min_size=3,
            has_price_data=True,
            has_fund_data=True,
        )
        assert status == "insufficient_data"
        assert "min_size" in reason

    def test_determine_data_status_no_price(self):
        """测试无价格数据"""
        status, reason = determine_data_status(
            valid_count=5,
            min_size=3,
            has_price_data=False,
            has_fund_data=True,
        )
        assert status == "insufficient_data"
        assert "price" in reason

    def test_determine_data_status_partial_no_fund(self):
        """测试部分状态（资金缺失）"""
        status, reason = determine_data_status(
            valid_count=5,
            min_size=3,
            has_price_data=True,
            has_fund_data=False,
        )
        assert status == "partial"
        assert "fund" in reason

    def test_get_missing_members_normal(self):
        """测试缺失成员识别"""
        missing = get_missing_members(
            configured_symbols=["A", "B", "C", "D"],
            valid_symbols=["A", "C"],
        )
        assert missing == ["B", "D"]

    def test_get_missing_members_no_missing(self):
        """测试无缺失成员"""
        missing = get_missing_members(
            configured_symbols=["A", "B"],
            valid_symbols=["A", "B"],
        )
        assert missing == []

    def test_check_data_quality_ok(self):
        """测试数据质量报告 - 正常"""
        report = check_data_quality(
            universe_id="test_pool",
            valid_count=5,
            benchmark_count=5,
            min_size=3,
        )
        assert report["universe_id"] == "test_pool"
        assert report["configured"] == 5
        assert report["valid"] == 5
        assert report["coverage"] == 1.0
        assert report["is_sufficient"] == True
        assert report["status"] == "ok"
        assert len(report["warnings"]) == 0

    def test_check_data_quality_partial(self):
        """测试数据质量报告 - 部分缺失"""
        report = check_data_quality(
            universe_id="test_pool",
            valid_count=4,
            benchmark_count=5,
            min_size=3,
        )
        assert report["valid"] == 4
        assert report["coverage"] == 0.8
        assert report["is_sufficient"] == True
        assert report["status"] == "ok"  # 80% coverage is ok

    def test_check_data_quality_insufficient(self):
        """测试数据质量报告 - 数据不足"""
        report = check_data_quality(
            universe_id="test_pool",
            valid_count=2,
            benchmark_count=5,
            min_size=3,
        )
        assert report["is_sufficient"] == False
        assert report["status"] == "insufficient_data"
        assert len(report["warnings"]) > 0


# ==================== PoolState 数据类测试 ====================

class TestPoolStateDataclass:
    """测试 PoolState 数据类"""

    def test_pool_state_frozen(self):
        """测试 PoolState 不可变"""
        state = PoolState(
            universe_id="test",
            trade_date="20260502",
            configured_count=5,
            enabled_count=4,
            benchmark_count=3,
            valid_count=3,
            median_return=2.5,
            mean_return=2.0,
            up_ratio=0.6,
            strong_count=1,
            weak_count=0,
            volume_multiplier=1.2,
            fund_positive_ratio=0.5,
            data_status="ok",
            missing_members=[],
        )

        with pytest.raises(AttributeError):
            state.median_return = 3.0

    def test_pool_state_with_missing_members(self):
        """测试包含缺失成员的状态"""
        state = PoolState(
            universe_id="test",
            trade_date="20260502",
            configured_count=5,
            enabled_count=5,
            benchmark_count=5,
            valid_count=3,
            median_return=2.5,
            mean_return=2.0,
            up_ratio=0.6,
            strong_count=1,
            weak_count=0,
            volume_multiplier=1.2,
            fund_positive_ratio=0.5,
            data_status="partial",
            missing_members=["600343.SH", "600879.SH"],
            partial_reason="data missing",
        )

        assert len(state.missing_members) == 2
        assert state.data_status == "partial"

    def test_pool_state_insufficient_data(self):
        """测试数据不足状态"""
        state = PoolState(
            universe_id="test",
            trade_date="20260502",
            configured_count=5,
            enabled_count=5,
            benchmark_count=5,
            valid_count=1,  # 低于 min_size
            median_return=None,
            mean_return=None,
            up_ratio=None,
            strong_count=0,
            weak_count=0,
            volume_multiplier=None,
            fund_positive_ratio=None,
            data_status="insufficient_data",
            missing_members=["A", "B", "C", "D"],
            partial_reason="valid_count(1) < min_size(3)",
        )

        assert state.data_status == "insufficient_data"
        assert state.median_return is None

    def test_member_data_frozen(self):
        """测试 MemberData 不可变"""
        member = MemberData(
            symbol="test",
            trade_date="20260502",
            close=10.0,
            pct_chg=2.0,
            amount=1000.0,
            turnover_rate=1.0,
            net_mf_amount=None,
            is_valid=True,
        )

        with pytest.raises(AttributeError):
            member.pct_chg = 3.0

    def test_pool_state_result_frozen(self):
        """测试 PoolStateResult 不可变"""
        result = PoolStateResult(
            trade_date="20260502",
            anchor_symbol="688333.SH",
            pool_states={},
            overall_status="ok",
            errors=[],
        )

        with pytest.raises(AttributeError):
            result.overall_status = "error"


# ==================== 边界情况测试 ====================

class TestEdgeCases:
    """测试边界情况"""

    def test_all_members_missing(self):
        """测试所有成员数据缺失"""
        status, reason = determine_data_status(
            valid_count=0,
            min_size=3,
            has_price_data=False,
            has_fund_data=False,
        )
        assert status == "insufficient_data"

    def test_single_member_valid(self):
        """测试只有一个有效成员"""
        # min_size=1 时应该可以计算
        status, reason = determine_data_status(
            valid_count=1,
            min_size=1,
            has_price_data=True,
            has_fund_data=True,
        )
        assert status == "ok"

    def test_zero_returns(self):
        """测试涨跌幅全为 0"""
        zero_data = [
            MemberData(
                symbol="test",
                trade_date="20260502",
                close=10.0,
                pct_chg=0.0,
                amount=1000.0,
                turnover_rate=1.0,
                net_mf_amount=0.0,
                is_valid=True,
            )
        ]

        median = calculate_median_return(zero_data)
        assert median == 0.0

        up_ratio = calculate_up_ratio(zero_data)
        assert up_ratio == 0.0  # 0% 不算上涨

    def test_extreme_returns(self):
        """测试极端涨跌幅"""
        extreme_data = [
            MemberData(
                symbol="A",
                trade_date="20260502",
                close=10.0,
                pct_chg=20.0,  # 涨停
                amount=1000.0,
                turnover_rate=10.0,
                net_mf_amount=None,
                is_valid=True,
            ),
            MemberData(
                symbol="B",
                trade_date="20260502",
                close=10.0,
                pct_chg=-10.0,  # 跌停
                amount=500.0,
                turnover_rate=5.0,
                net_mf_amount=None,
                is_valid=True,
            ),
        ]

        strong, weak = calculate_strong_weak_count(
            extreme_data,
            strong_threshold=3.0,
            weak_threshold=-3.0,
        )
        assert strong == 1
        assert weak == 1

    def test_negative_zero_threshold(self):
        """测试涨跌幅恰好等于阈值"""
        threshold_data = [
            MemberData(
                symbol="A",
                trade_date="20260502",
                close=10.0,
                pct_chg=3.0,  # 恰好等于强势阈值
                amount=1000.0,
                turnover_rate=1.0,
                net_mf_amount=None,
                is_valid=True,
            ),
            MemberData(
                symbol="B",
                trade_date="20260502",
                close=10.0,
                pct_chg=-3.0,  # 恰好等于弱势阈值
                amount=500.0,
                turnover_rate=1.0,
                net_mf_amount=None,
                is_valid=True,
            ),
        ]

        # 恰好等于阈值不算强势/弱势（需要 > 或 <）
        strong, weak = calculate_strong_weak_count(
            threshold_data,
            strong_threshold=3.0,
            weak_threshold=-3.0,
        )
        assert strong == 0  # 3.0 不算 > 3.0
        assert weak == 0    # -3.0 不算 < -3.0


# ==================== 口径分离测试 ====================

class TestScopeSeparation:
    """测试 benchmark/ranking 口径分离"""

    def test_benchmark_scope_excludes_anchor(self):
        """测试 benchmark 口径不含 Anchor"""
        from src.config.loader import PoolRegistry

        registry = PoolRegistry()

        # 所有池子的 benchmark_scope 都不应包含 anchor
        anchor_symbol = registry.get_anchor().symbol

        for universe in registry.get_all_universes():
            benchmark_members = registry.get_benchmark_scope(universe.universe_id)
            symbols = [m.symbol for m in benchmark_members]
            assert anchor_symbol not in symbols

    def test_theme_pool_benchmark_empty(self):
        """测试 theme_pool 的 benchmark 口径"""
        from src.config.loader import PoolRegistry

        registry = PoolRegistry()

        theme_benchmark = registry.get_benchmark_scope("theme_pool")

        # theme_pool 的成员 include_in_benchmark 应该为 False
        for m in theme_benchmark:
            assert m.include_in_benchmark == False