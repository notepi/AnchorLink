"""
Integration Tests - 全流程测试

测试覆盖：
  1. 从配置加载到输出生成的完整流程
  2. 多模块数据流转一致性
  3. 输出文件格式正确性
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
from src.signal.models import SignalResult, Signal, Evidence
from src.output import write_all


# ============================================================
# Fixtures - 测试数据
# ============================================================

@pytest.fixture
def trade_date():
    """测试日期"""
    return "20260502"


@pytest.fixture
def sample_registry():
    """
    样本 PoolRegistry - 使用 type() 动态创建 mock 对象

    包含：
      - anchor: 688333.SH
      - 4 universes: direct_peers, industry_chain, theme_pool, trading_watchlist
      - 多个 memberships
    """
    anchor = Anchor(
        symbol="688333.SH",
        name="铂力特",
        reason="核心标的",
        added_date="2026-05-01",
    )

    instruments = {
        "688333.SH": Instrument(symbol="688333.SH", name="铂力特", market="科创板", exchange="SH", fact_tags=["3D打印", "航空航天"]),
        "688433.SH": Instrument(symbol="688433.SH", name="华曙高科", market="科创板", exchange="SH", fact_tags=["3D打印"]),
        "600343.SH": Instrument(symbol="600343.SH", name="航天动力", market="主板", exchange="SH", fact_tags=["航空航天"]),
        "600879.SH": Instrument(symbol="600879.SH", name="航天电子", market="主板", exchange="SH", fact_tags=["航空航天"]),
        "002049.SZ": Instrument(symbol="002049.SZ", name="紫光国微", market="中小板", exchange="SZ", fact_tags=["半导体"]),
        "300034.SZ": Instrument(symbol="300034.SZ", name="钢研高纳", market="创业板", exchange="SZ", fact_tags=["高温合金"]),
    }

    universes = {
        "direct_peers": Universe(
            universe_id="direct_peers",
            display_name="核心同类",
            purpose="核心对比池",
            can_be_benchmark=True,
            min_size=3,
        ),
        "industry_chain": Universe(
            universe_id="industry_chain",
            display_name="产业链",
            purpose="上下游关联",
            can_be_benchmark=True,
            min_size=2,
        ),
        "theme_pool": Universe(
            universe_id="theme_pool",
            display_name="主题扩散",
            purpose="主题热度观察",
            can_be_benchmark=False,
            min_size=2,
        ),
        "trading_watchlist": Universe(
            universe_id="trading_watchlist",
            display_name="交易观察",
            purpose="交易候选池",
            can_be_benchmark=False,
            min_size=1,
        ),
    }

    memberships = [
        # direct_peers
        Membership(universe_id="direct_peers", symbol="688433.SH", role="direct_comparable", relevance=0.9, weight=1.0, enabled=True, include_in_benchmark=True, include_in_ranking=True, include_in_report=True, reason="同类公司", added_at="2026-05-01", reviewed_at="2026-05-02"),
        Membership(universe_id="direct_peers", symbol="600343.SH", role="sector_peer", relevance=0.7, weight=0.8, enabled=True, include_in_benchmark=True, include_in_ranking=True, include_in_report=True, reason="同板块", added_at="2026-05-01", reviewed_at="2026-05-02"),
        Membership(universe_id="direct_peers", symbol="600879.SH", role="sector_peer", relevance=0.7, weight=0.8, enabled=True, include_in_benchmark=True, include_in_ranking=True, include_in_report=True, reason="同板块", added_at="2026-05-01", reviewed_at="2026-05-02"),
        # industry_chain
        Membership(universe_id="industry_chain", symbol="002049.SZ", role="upstream", relevance=0.6, weight=0.6, enabled=True, include_in_benchmark=True, include_in_ranking=True, include_in_report=True, reason="上游供应商", added_at="2026-05-01", reviewed_at="2026-05-02"),
        Membership(universe_id="industry_chain", symbol="300034.SZ", role="downstream", relevance=0.5, weight=0.5, enabled=True, include_in_benchmark=True, include_in_ranking=True, include_in_report=True, reason="下游客户", added_at="2026-05-01", reviewed_at="2026-05-02"),
        # theme_pool
        Membership(universe_id="theme_pool", symbol="688433.SH", role="theme_heat_proxy", relevance=0.8, weight=0.7, enabled=True, include_in_benchmark=False, include_in_ranking=True, include_in_report=True, reason="主题热度代理", added_at="2026-05-01", reviewed_at="2026-05-02"),
        Membership(universe_id="theme_pool", symbol="002049.SZ", role="theme_heat_proxy", relevance=0.6, weight=0.5, enabled=True, include_in_benchmark=False, include_in_ranking=True, include_in_report=True, reason="主题热度代理", added_at="2026-05-01", reviewed_at="2026-05-02"),
        # trading_watchlist
        Membership(universe_id="trading_watchlist", symbol="600343.SH", role="trading_candidate", relevance=0.4, weight=0.3, enabled=True, include_in_benchmark=False, include_in_ranking=True, include_in_report=True, reason="交易候选", added_at="2026-05-01", reviewed_at="2026-05-02"),
    ]

    return type("MockRegistry", (), {
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
def sample_market_df(trade_date):
    """样本行情 DataFrame（多日数据）"""
    dates = pd.date_range("20260425", trade_date, freq="B")
    symbols = ["688333.SH", "688433.SH", "600343.SH", "600879.SH", "002049.SZ", "300034.SZ"]

    rows = []
    for symbol in symbols:
        base_close = 50.0 if symbol == "688333.SH" else 30.0
        for i, date in enumerate(dates):
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


@pytest.fixture
def sample_daily_basic_df(trade_date):
    """样本估值 DataFrame"""
    symbols = ["688333.SH", "688433.SH", "600343.SH", "600879.SH", "002049.SZ", "300034.SZ"]

    rows = []
    for symbol in symbols:
        rows.append({
            "ts_code": symbol,
            "trade_date": pd.to_datetime(trade_date, format="%Y%m%d"),
            "turnover_rate": 3.0 + hash(symbol) % 5,
            "pe": 30.0,
            "pb": 5.0,
        })

    return pd.DataFrame(rows)


@pytest.fixture
def sample_moneyflow_df(trade_date):
    """样本资金流向 DataFrame"""
    symbols = ["688333.SH", "688433.SH", "600343.SH", "600879.SH"]

    rows = []
    for symbol in symbols:
        rows.append({
            "ts_code": symbol,
            "trade_date": pd.to_datetime(trade_date, format="%Y%m%d"),
            "net_mf_amount": 5000000.0 + hash(symbol) % 10000000,
        })

    return pd.DataFrame(rows)


@pytest.fixture
def sample_member_data_dict(trade_date):
    """样本成员数据字典"""
    return {
        "688333.SH": MemberData(
            symbol="688333.SH",
            trade_date=trade_date,
            close=52.5,
            pct_chg=2.0,
            amount=105000.0,
            turnover_rate=3.5,
            net_mf_amount=8000000.0,
            is_valid=True,
        ),
        "688433.SH": MemberData(
            symbol="688433.SH",
            trade_date=trade_date,
            close=32.5,
            pct_chg=1.5,
            amount=102000.0,
            turnover_rate=4.0,
            net_mf_amount=5000000.0,
            is_valid=True,
        ),
        "600343.SH": MemberData(
            symbol="600343.SH",
            trade_date=trade_date,
            close=32.0,
            pct_chg=1.0,
            amount=100000.0,
            turnover_rate=3.0,
            net_mf_amount=None,
            is_valid=True,
        ),
        "600879.SH": MemberData(
            symbol="600879.SH",
            trade_date=trade_date,
            close=32.5,
            pct_chg=0.5,
            amount=98000.0,
            turnover_rate=None,
            net_mf_amount=None,
            is_valid=True,
        ),
        "002049.SZ": MemberData(
            symbol="002049.SZ",
            trade_date=trade_date,
            close=35.0,
            pct_chg=2.5,
            amount=110000.0,
            turnover_rate=5.0,
            net_mf_amount=None,
            is_valid=True,
        ),
        "300034.SZ": MemberData(
            symbol="300034.SZ",
            trade_date=trade_date,
            close=25.0,
            pct_chg=-1.0,
            amount=90000.0,
            turnover_rate=2.5,
            net_mf_amount=None,
            is_valid=True,
        ),
    }


@pytest.fixture
def sample_pool_states(trade_date):
    """样本池子状态"""
    return {
        "direct_peers": PoolState(
            universe_id="direct_peers",
            trade_date=trade_date,
            configured_count=3,
            enabled_count=3,
            benchmark_count=3,
            valid_count=3,
            median_return=1.0,
            mean_return=1.0,
            up_ratio=1.0,
            strong_count=1,
            weak_count=0,
            volume_multiplier=1.2,
            fund_positive_ratio=0.67,
            data_status="ok",
            missing_members=[],
        ),
        "industry_chain": PoolState(
            universe_id="industry_chain",
            trade_date=trade_date,
            configured_count=2,
            enabled_count=2,
            benchmark_count=2,
            valid_count=2,
            median_return=0.75,
            mean_return=0.75,
            up_ratio=0.5,
            strong_count=1,
            weak_count=1,
            volume_multiplier=1.1,
            fund_positive_ratio=None,
            data_status="ok",
            missing_members=[],
        ),
        "theme_pool": PoolState(
            universe_id="theme_pool",
            trade_date=trade_date,
            configured_count=2,
            enabled_count=2,
            benchmark_count=0,
            valid_count=2,
            median_return=2.0,
            mean_return=2.0,
            up_ratio=1.0,
            strong_count=2,
            weak_count=0,
            volume_multiplier=1.3,
            fund_positive_ratio=None,
            data_status="ok",
            missing_members=[],
        ),
        "trading_watchlist": PoolState(
            universe_id="trading_watchlist",
            trade_date=trade_date,
            configured_count=1,
            enabled_count=1,
            benchmark_count=0,
            valid_count=1,
            median_return=1.0,
            mean_return=1.0,
            up_ratio=1.0,
            strong_count=1,
            weak_count=0,
            volume_multiplier=1.0,
            fund_positive_ratio=None,
            data_status="ok",
            missing_members=[],
        ),
    }


@pytest.fixture
def sample_group_rotation(trade_date):
    """样本组间轮动"""
    return GroupRotation(
        trade_date=trade_date,
        strongest_group="theme_pool",
        weakest_group="industry_chain",
        group_ranking=["theme_pool", "direct_peers", "trading_watchlist", "industry_chain"],
        spreads={},
        core_vs_theme_spread=-1.0,
        core_vs_chain_spread=0.25,
        core_vs_trading_spread=0.0,
        group_medians={"direct_peers": 1.0, "industry_chain": 0.75, "theme_pool": 2.0, "trading_watchlist": 1.0},
        data_status="ok",
    )


@pytest.fixture
def sample_signal_result(trade_date):
    """样本信号结果"""
    signals = [
        Signal(
            label="行业Beta为正",
            category="beta",
            confidence="high",
            evidence=Evidence(value=1.0, threshold=0.5, source_pool="direct_peers", source_field="median_return"),
            trade_date=trade_date,
        ),
        Signal(
            label="跑赢核心同类",
            category="alpha",
            confidence="medium",
            evidence=Evidence(value=1.0, threshold=0.5, source_pool="direct_peers", source_field="relative_strength"),
            trade_date=trade_date,
        ),
    ]

    return SignalResult(
        trade_date=trade_date,
        anchor_symbol="688333.SH",
        signals=signals,
        beta_count=1,
        alpha_count=1,
        volume_count=0,
        rotation_count=0,
        abnormal_count=0,
        data_status="ok",
    )


# ============================================================
# Tests - PoolState 层
# ============================================================

class TestPoolStateLayer:
    """测试 PoolState 层"""

    def test_calculator_creates_pool_states(
        self, sample_registry, sample_market_df, sample_daily_basic_df, sample_moneyflow_df, trade_date
    ):
        """测试 PoolStateCalculator 生成池子状态"""
        calculator = PoolStateCalculator(
            sample_registry, sample_market_df, sample_daily_basic_df, sample_moneyflow_df
        )

        result = calculator.calculate(trade_date)

        # 验证返回结构
        assert result.trade_date == trade_date
        assert result.anchor_symbol == "688333.SH"
        assert len(result.pool_states) == 4
        assert result.overall_status in ["ok", "partial"]

    def test_pool_state_has_required_fields(self, sample_registry, sample_market_df, trade_date):
        """测试 PoolState 包含必需字段"""
        calculator = PoolStateCalculator(sample_registry, sample_market_df)
        result = calculator.calculate(trade_date)

        for universe_id, state in result.pool_states.items():
            assert state.universe_id == universe_id
            assert state.trade_date == trade_date
            assert state.configured_count >= 0
            assert state.valid_count >= 0
            assert state.data_status in ["ok", "partial", "insufficient_data"]
            assert state.median_return is not None or state.data_status == "insufficient_data"


# ============================================================
# Tests - AnchorPosition 层
# ============================================================

class TestAnchorPositionLayer:
    """测试 AnchorPosition 层"""

    def test_relative_strength_calculator(
        self, sample_registry, sample_pool_states, sample_member_data_dict, trade_date
    ):
        """测试 RelativeStrengthCalculator 计算相对强弱"""
        ranking_calc = RankingCalculator(sample_registry)
        rs_calc = RelativeStrengthCalculator(sample_registry, ranking_calc)

        anchor_data = sample_member_data_dict["688333.SH"]

        result = rs_calc.calculate_all(
            trade_date, anchor_data, sample_pool_states, sample_member_data_dict
        )

        # 验证返回结构
        assert len(result) == 4
        for universe_id, rs in result.items():
            assert rs.universe_id == universe_id
            assert rs.trade_date == trade_date
            assert rs.anchor_return == anchor_data.pct_chg
            assert rs.position in ["outperform", "underperform", "neutral"]

    def test_ranking_calculator(self, sample_registry, sample_member_data_dict, trade_date):
        """测试 RankingCalculator 计算排名"""
        ranking_calc = RankingCalculator(sample_registry)
        anchor_data = sample_member_data_dict["688333.SH"]

        result = ranking_calc.calculate_ranks(
            "direct_peers", trade_date, anchor_data, sample_member_data_dict
        )

        # 验证排名字段存在
        assert "rank_return" in result
        assert "rank_volume" in result
        assert "total_count" in result
        assert result["total_count"] > 0


# ============================================================
# Tests - GroupRotation 层
# ============================================================

class TestGroupRotationLayer:
    """测试 GroupRotation 层"""

    def test_analyze_rotation_with_spreads(self, sample_registry, sample_pool_states, trade_date):
        """测试 analyze_rotation_with_spreads"""
        result = analyze_rotation_with_spreads(sample_pool_states, trade_date, sample_registry)

        # 验证返回结构
        assert result.trade_date == trade_date
        assert result.strongest_group is not None
        assert result.weakest_group is not None
        # ranking 只包含有有效 median_return 的池子
        assert len(result.group_ranking) >= 2
        assert result.core_vs_chain_spread is not None


# ============================================================
# Tests - Signal 层
# ============================================================

class TestSignalLayer:
    """测试 Signal 层"""

    def test_generate_signals(
        self, sample_registry, sample_pool_states, sample_group_rotation, sample_member_data_dict, trade_date
    ):
        """测试 generate_signals"""
        # 先计算 anchor_positions
        ranking_calc = RankingCalculator(sample_registry)
        rs_calc = RelativeStrengthCalculator(sample_registry, ranking_calc)
        anchor_data = sample_member_data_dict["688333.SH"]
        anchor_positions = rs_calc.calculate_all(
            trade_date, anchor_data, sample_pool_states, sample_member_data_dict
        )

        result = generate_signals(sample_pool_states, anchor_positions, sample_group_rotation, sample_registry)

        # 验证返回结构
        assert result.trade_date == trade_date
        assert result.anchor_symbol == "688333.SH"
        assert len(result.signals) > 0
        assert result.data_status in ["ok", "partial"]

        # 验证分类统计一致
        total = result.beta_count + result.alpha_count + result.volume_count + result.rotation_count + result.abnormal_count
        assert total == len(result.signals)

    def test_each_signal_has_evidence(
        self, sample_registry, sample_pool_states, sample_group_rotation, sample_member_data_dict, trade_date
    ):
        """测试每个信号都有 evidence"""
        ranking_calc = RankingCalculator(sample_registry)
        rs_calc = RelativeStrengthCalculator(sample_registry, ranking_calc)
        anchor_data = sample_member_data_dict["688333.SH"]
        anchor_positions = rs_calc.calculate_all(
            trade_date, anchor_data, sample_pool_states, sample_member_data_dict
        )

        result = generate_signals(sample_pool_states, anchor_positions, sample_group_rotation, sample_registry)

        for signal in result.signals:
            assert signal.evidence is not None
            assert signal.evidence.value is not None
            assert signal.evidence.threshold is not None


# ============================================================
# Tests - Output 层
# ============================================================

class TestOutputLayer:
    """测试 Output 层"""

    def test_write_all_creates_three_files(
        self, sample_registry, sample_pool_states, sample_group_rotation, sample_signal_result, sample_member_data_dict
    ):
        """测试 write_all 生成三个输出文件"""
        # 构建 anchor_positions
        ranking_calc = RankingCalculator(sample_registry)
        rs_calc = RelativeStrengthCalculator(sample_registry, ranking_calc)
        anchor_data = sample_member_data_dict["688333.SH"]
        anchor_positions = rs_calc.calculate_all(
            "20260502", anchor_data, sample_pool_states, sample_member_data_dict
        )

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            snapshot = write_all(
                sample_registry,
                sample_pool_states,
                anchor_positions,
                sample_group_rotation,
                sample_signal_result,
                sample_member_data_dict,
                output_dir,
            )

            # 验证三文件存在
            assert (output_dir / "industry_snapshot.json").exists()
            assert (output_dir / "peer_matrix.csv").exists()
            assert (output_dir / "industry_report.md").exists()

    def test_json_has_required_structure(
        self, sample_registry, sample_pool_states, sample_group_rotation, sample_signal_result, sample_member_data_dict
    ):
        """测试 JSON 结构完整"""
        ranking_calc = RankingCalculator(sample_registry)
        rs_calc = RelativeStrengthCalculator(sample_registry, ranking_calc)
        anchor_data = sample_member_data_dict["688333.SH"]
        anchor_positions = rs_calc.calculate_all(
            "20260502", anchor_data, sample_pool_states, sample_member_data_dict
        )

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            write_all(
                sample_registry, sample_pool_states, anchor_positions,
                sample_group_rotation, sample_signal_result, sample_member_data_dict,
                output_dir
            )

            # 读取并验证 JSON
            with open(output_dir / "industry_snapshot.json", encoding="utf-8") as f:
                data = json.load(f)

            assert data["anchor"]["symbol"] == "688333.SH"
            assert "as_of_date" in data
            assert "data_quality" in data
            assert "industry_state" in data
            assert "anchor_position" in data
            assert "group_rotation" in data
            assert "signals" in data
            assert "conclusion" in data

    def test_markdown_has_five_chapters(
        self, sample_registry, sample_pool_states, sample_group_rotation, sample_signal_result, sample_member_data_dict
    ):
        """测试 Markdown 报告五章结构"""
        ranking_calc = RankingCalculator(sample_registry)
        rs_calc = RelativeStrengthCalculator(sample_registry, ranking_calc)
        anchor_data = sample_member_data_dict["688333.SH"]
        anchor_positions = rs_calc.calculate_all(
            "20260502", anchor_data, sample_pool_states, sample_member_data_dict
        )

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            write_all(
                sample_registry, sample_pool_states, anchor_positions,
                sample_group_rotation, sample_signal_result, sample_member_data_dict,
                output_dir
            )

            # 读取并验证 Markdown
            with open(output_dir / "industry_report.md", encoding="utf-8") as f:
                content = f.read()

            assert "# 铂力特 行业锚定分析报告" in content
            assert "## 一、行业状态概览" in content
            assert "## 二、行业结构拆解" in content
            assert "## 三、锚定标的相对位置" in content
            assert "## 四、行业联动与异常信号" in content
            assert "## 五、行业模块结论" in content


# ============================================================
# Tests - 数据一致性
# ============================================================

class TestDataConsistency:
    """测试数据流转一致性"""

    def test_signal_count_matches_classification(
        self, sample_registry, sample_pool_states, sample_group_rotation, sample_member_data_dict, trade_date
    ):
        """验证信号分类统计一致"""
        ranking_calc = RankingCalculator(sample_registry)
        rs_calc = RelativeStrengthCalculator(sample_registry, ranking_calc)
        anchor_data = sample_member_data_dict["688333.SH"]
        anchor_positions = rs_calc.calculate_all(
            trade_date, anchor_data, sample_pool_states, sample_member_data_dict
        )

        result = generate_signals(sample_pool_states, anchor_positions, sample_group_rotation, sample_registry)

        # 分类统计之和 == 总信号数
        total = result.beta_count + result.alpha_count + result.volume_count + result.rotation_count + result.abnormal_count
        assert total == len(result.signals)

        # 按类别分组验证
        beta_signals = [s for s in result.signals if s.category == "beta"]
        assert len(beta_signals) == result.beta_count

    def test_pool_state_consistent_with_registry(self, sample_registry, sample_market_df, trade_date):
        """验证池子状态与配置一致"""
        calculator = PoolStateCalculator(sample_registry, sample_market_df)
        result = calculator.calculate(trade_date)

        for universe in sample_registry.get_all_universes():
            universe_id = universe.universe_id
            state = result.pool_states.get(universe_id)

            if state:
                # configured_count 应等于配置的成员数
                all_members = sample_registry.get_members(universe_id, enabled_only=False)
                assert state.configured_count == len(all_members)


# ============================================================
# Tests - Scope 分离验证
# ============================================================

class TestScopeSeparation:
    """测试 benchmark/ranking/report 口径分离"""

    def test_benchmark_excludes_anchor(self, sample_registry):
        """验证 benchmark_scope 不包含 anchor"""
        anchor_symbol = sample_registry.get_anchor().symbol

        for universe in sample_registry.get_all_universes():
            benchmark_members = sample_registry.get_benchmark_scope(universe.universe_id)
            symbols = [m.symbol for m in benchmark_members]
            assert anchor_symbol not in symbols

    def test_ranking_includes_anchor(self, sample_registry):
        """验证 ranking_scope 包含 anchor"""
        anchor_symbol = sample_registry.get_anchor().symbol

        for universe in sample_registry.get_all_universes():
            ranking_symbols = sample_registry.get_ranking_scope(universe.universe_id, include_anchor=True)
            assert anchor_symbol in ranking_symbols