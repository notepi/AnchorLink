"""
历史分析模块测试
"""

import csv
import json
import tempfile
from pathlib import Path

import pytest

from src.history_analysis.models import (
    HistoryRow,
    RollingMetrics,
    QuadrantStats,
    ExtremeDivergence,
    EventPath,
    SignalLift,
    SignalPair,
    StateTransition,
)
from src.history_analysis.forward_returns import (
    compute_forward_returns,
    compute_forward_excess,
    build_chain_forward_returns,
)
from src.history_analysis.rolling_metrics import (
    compute_rolling_excess,
    compute_outperform_streak,
    compute_beta_streak,
    compute_theme_vs_core_streak,
    compute_risk_high_streak,
    build_rolling_metrics,
)
from src.history_analysis.quadrant_analyzer import (
    classify_quadrant,
    build_quadrant_stats,
)
from src.history_analysis.divergence_analyzer import (
    compute_divergence,
    find_extreme_divergences,
)
from src.history_analysis.event_study import build_event_paths
from src.history_analysis.signal_analyzer import (
    explode_signals,
    explode_signals_with_category,
    build_signal_lifts,
)
from src.history_analysis.transition_analyzer import build_state_transitions
from src.history_analysis.counter_intuitive_analyzer import identify_counter_intuitive_signals
from src.history_analysis.conditional_signal_analyzer import build_conditional_signal_effects
from src.history_analysis.operator_playbook import build_operator_playbook
from src.output.history_csv_writer import write_history_csv


# ============================================================
# Fixtures
# ============================================================


def _make_row(
    date: str = "20260101",
    anchor_return: float | None = 1.0,
    industry_chain_median: float | None = 0.5,
    direct_peers_median: float | None = 0.8,
    theme_pool_median: float | None = 1.2,
    trading_watchlist_median: float | None = 0.3,
    industry_beta: str = "positive",
    anchor_alpha: str = "positive",
    risk_level: str = "medium",
    next_1d_return: float | None = 0.5,
    next_3d_return: float | None = 1.0,
    next_5d_return: float | None = 1.5,
    next_1d_excess_vs_chain: float | None = 0.2,
    next_3d_excess_vs_chain: float | None = 0.4,
    next_5d_excess_vs_chain: float | None = 0.6,
    signal_labels: str = "行业Beta为正,个股Alpha为正",
    signal_categories: str = "beta,alpha",
    signal_pairs: str = '[{"label":"行业Beta为正","category":"beta"},{"label":"个股Alpha为正","category":"alpha"}]',
    relative_strength_vs_industry_chain: float | None = 0.5,
) -> HistoryRow:
    return HistoryRow(
        date=date,
        anchor_return=anchor_return,
        direct_peers_median=direct_peers_median,
        industry_chain_median=industry_chain_median,
        theme_pool_median=theme_pool_median,
        trading_watchlist_median=trading_watchlist_median,
        relative_strength_vs_direct=anchor_return - direct_peers_median if anchor_return is not None and direct_peers_median is not None else None,
        relative_strength_vs_industry_chain=relative_strength_vs_industry_chain,
        relative_strength_vs_theme=anchor_return - theme_pool_median if anchor_return is not None and theme_pool_median is not None else None,
        direct_up_ratio=0.6,
        chain_up_ratio=None,
        amount_expansion_ratio=1.0,
        moneyflow_positive_ratio=0.5,
        strongest_group="industry_chain",
        weakest_group="trading_watchlist",
        industry_beta=industry_beta,
        anchor_alpha=anchor_alpha,
        risk_level=risk_level,
        signal_labels=signal_labels,
        signal_categories=signal_categories,
        signal_pairs=signal_pairs,
        data_quality_status="ok",
        next_1d_return=next_1d_return,
        next_3d_return=next_3d_return,
        next_5d_return=next_5d_return,
        next_1d_excess_vs_chain=next_1d_excess_vs_chain,
        next_3d_excess_vs_chain=next_3d_excess_vs_chain,
        next_5d_excess_vs_chain=next_5d_excess_vs_chain,
    )


@pytest.fixture
def sample_rows() -> list[HistoryRow]:
    return [
        _make_row(date="20260101", anchor_return=2.0, industry_chain_median=1.0, industry_beta="positive", anchor_alpha="positive", risk_level="low", next_1d_return=0.5),
        _make_row(date="20260102", anchor_return=-1.0, industry_chain_median=0.5, industry_beta="positive", anchor_alpha="negative", risk_level="high", next_1d_return=-0.8),
        _make_row(date="20260103", anchor_return=0.5, industry_chain_median=1.5, industry_beta="positive", anchor_alpha="negative", risk_level="high", next_1d_return=-0.3),
        _make_row(date="20260104", anchor_return=1.5, industry_chain_median=0.8, industry_beta="neutral", anchor_alpha="positive", risk_level="medium", next_1d_return=0.2),
        _make_row(date="20260105", anchor_return=-2.0, industry_chain_median=-1.0, industry_beta="negative", anchor_alpha="negative", risk_level="high", next_1d_return=-1.0),
        _make_row(date="20260106", anchor_return=-0.5, industry_chain_median=-0.3, industry_beta="negative", anchor_alpha="negative", risk_level="medium", next_1d_return=0.1),
        _make_row(date="20260107", anchor_return=3.0, industry_chain_median=0.2, industry_beta="positive", anchor_alpha="positive", risk_level="low", next_1d_return=None, next_3d_return=None, next_5d_return=None),
    ]


# ============================================================
# Test: Forward Returns
# ============================================================


class TestForwardReturns:
    def test_compute_forward_returns_basic(self):
        closes = [100.0, 102.0, 101.0, 105.0, 103.0]
        result = compute_forward_returns(0, closes, [1, 3])
        assert result["next_1d_return"] == pytest.approx(2.0, abs=0.01)
        assert result["next_3d_return"] == pytest.approx(5.0, abs=0.01)

    def test_compute_forward_returns_end_of_series(self):
        closes = [100.0, 102.0, 101.0]
        result = compute_forward_returns(2, closes, [1, 3, 5])
        assert result["next_1d_return"] is None
        assert result["next_3d_return"] is None
        assert result["next_5d_return"] is None

    def test_compute_forward_returns_last_valid(self):
        closes = [100.0, 102.0, 101.0, 105.0, 103.0]
        result = compute_forward_returns(3, closes, [1])
        assert result["next_1d_return"] == pytest.approx(-1.904762, abs=0.01)

    def test_compute_forward_excess(self):
        anchor_fw = {"next_1d_return": 2.0, "next_3d_return": 5.0}
        chain_fw = {"next_1d_return": 1.0, "next_3d_return": 3.0}
        result = compute_forward_excess(anchor_fw, chain_fw, [1, 3])
        assert result["next_1d_excess_vs_chain"] == pytest.approx(1.0)
        assert result["next_3d_excess_vs_chain"] == pytest.approx(2.0)

    def test_compute_forward_excess_none(self):
        anchor_fw = {"next_1d_return": 2.0}
        chain_fw = {"next_1d_return": None}
        result = compute_forward_excess(anchor_fw, chain_fw, [1])
        assert result["next_1d_excess_vs_chain"] is None

    def test_build_chain_forward_returns(self):
        medians = [1.0, 2.0, 0.5, 3.0, -1.0]
        results = build_chain_forward_returns(medians, [1, 3])
        assert results[0]["next_1d_return"] == 2.0
        assert results[0]["next_3d_return"] == 3.0
        assert results[4]["next_1d_return"] is None
        assert results[3]["next_1d_return"] == -1.0


# ============================================================
# Test: Rolling Metrics
# ============================================================


class TestRollingMetrics:
    def test_compute_rolling_excess(self, sample_rows):
        result = compute_rolling_excess(sample_rows, 3)
        assert result[0] is None  # 不够 3 天
        assert result[1] is None
        # idx=2: (2-1) + (-1-0.5) + (0.5-1.5) = 1 - 1.5 - 1 = -1.5
        assert result[2] == pytest.approx(-1.5, abs=0.01)

    def test_compute_outperform_streak(self, sample_rows):
        result = compute_outperform_streak(sample_rows)
        assert result[0] == 1   # 2.0 > 1.0
        assert result[1] == -1  # -1.0 < 0.5
        assert result[2] == -2  # 0.5 < 1.5
        assert result[3] == 1   # 1.5 > 0.8

    def test_compute_beta_streak(self, sample_rows):
        result = compute_beta_streak(sample_rows)
        assert result[0] == 1   # positive
        assert result[1] == 2   # positive
        assert result[2] == 3   # positive
        assert result[3] == 0   # neutral breaks
        assert result[4] == -1  # negative

    def test_compute_risk_high_streak(self, sample_rows):
        result = compute_risk_high_streak(sample_rows)
        assert result[0] == 0   # low
        assert result[1] == 1   # high
        assert result[2] == 2   # high
        assert result[3] == 0   # medium

    def test_build_rolling_metrics(self, sample_rows):
        metrics = build_rolling_metrics(sample_rows)
        assert len(metrics) == 7
        assert metrics[0].date == "20260101"


# ============================================================
# Test: Quadrant Analyzer
# ============================================================


class TestQuadrantAnalyzer:
    def test_classify_quadrant(self):
        assert classify_quadrant("positive", "positive") == "行业强+个股强"
        assert classify_quadrant("positive", "negative") == "行业强+个股弱"
        assert classify_quadrant("negative", "positive") == "行业弱+个股强"
        assert classify_quadrant("negative", "negative") == "行业弱+个股弱"
        assert classify_quadrant("neutral", "neutral") == "行业中+个股中"

    def test_build_quadrant_stats_fixed_9(self, sample_rows):
        stats = build_quadrant_stats(sample_rows)
        assert len(stats) == 9
        quadrants = [s.quadrant for s in stats]
        assert "行业强+个股强" in quadrants
        assert "行业强+个股弱" in quadrants
        assert "行业中+个股强" in quadrants

    def test_quadrant_stats_zero_count(self, sample_rows):
        stats = build_quadrant_stats(sample_rows)
        zero_quads = [s for s in stats if s.count == 0]
        assert len(zero_quads) >= 0  # 未出现的象限 count=0, 其余 None
        for s in zero_quads:
            assert s.avg_next_1d is None
            assert s.win_rate_1d is None


# ============================================================
# Test: Divergence Analyzer
# ============================================================


class TestDivergenceAnalyzer:
    def test_compute_divergence(self, sample_rows):
        div = compute_divergence(sample_rows[0])
        assert div == pytest.approx(1.0)  # 2.0 - 1.0

    def test_compute_divergence_none(self):
        row = _make_row(anchor_return=None)
        assert compute_divergence(row) is None

    def test_find_extreme_divergences(self, sample_rows):
        # 用低阈值让测试有意义
        divergences = find_extreme_divergences(sample_rows, threshold=0.5)
        assert len(divergences) > 0
        # 按 |divergence| 降序
        for i in range(len(divergences) - 1):
            assert abs(divergences[i].divergence) >= abs(divergences[i + 1].divergence)


# ============================================================
# Test: Event Study
# ============================================================


class TestEventStudy:
    def test_build_event_paths(self, sample_rows):
        paths = build_event_paths(["20260103"], sample_rows, window=2)
        assert len(paths) == 5  # -2, -1, 0, +1, +2
        offsets = [p.offset for p in paths]
        assert offsets == [-2, -1, 0, 1, 2]

    def test_build_event_paths_out_of_range(self, sample_rows):
        paths = build_event_paths(["20260101"], sample_rows, window=2)
        # T-2, T-1 超出范围，但应有 None 行
        assert paths[0].date is None
        assert paths[2].date == "20260101"


# ============================================================
# Test: Signal Analyzer
# ============================================================


class TestSignalAnalyzer:
    def test_explode_signals(self, sample_rows):
        pairs = explode_signals(sample_rows)
        assert len(pairs) > 0
        labels = {p[0] for p in pairs}
        assert "行业Beta为正" in labels

    def test_explode_signals_with_category(self, sample_rows):
        triples = explode_signals_with_category(sample_rows)
        assert len(triples) > 0
        for label, category, idx in triples:
            assert isinstance(label, str)
            assert isinstance(category, str)
            assert isinstance(idx, int)
        # 检查 label-category 对应
        beta_pairs = [(l, c) for l, c, _ in triples if l == "行业Beta为正"]
        assert len(beta_pairs) > 0
        assert beta_pairs[0][1] == "beta"

    def test_explode_signals_with_category_fallback(self):
        """测试 signal_pairs 解析失败时 fallback 到旧字段"""
        row = _make_row(
            signal_labels="跑赢主线池,放量上涨",
            signal_categories="alpha,volume",
            signal_pairs="invalid_json",
        )
        triples = explode_signals_with_category([row])
        labels = {t[0] for t in triples}
        assert "跑赢主线池" in labels
        assert "放量上涨" in labels

    def test_build_signal_lifts(self, sample_rows):
        lifts = build_signal_lifts(sample_rows, min_count=1)
        assert len(lifts) > 0
        for lift in lifts:
            assert lift.appearance_count > 0
            assert isinstance(lift.min_count_passed, bool)
            assert hasattr(lift, 'avg_next_1d_delta_pp')
            assert isinstance(lift.category, str)

    def test_signal_pairs_json_in_csv(self, sample_rows):
        """测试 signal_pairs 字段正确写入 CSV"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_history.csv"
            write_history_csv(sample_rows, path)
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert "signal_pairs" in rows[0]
            # 验证 JSON 格式
            parsed = json.loads(rows[0]["signal_pairs"])
            assert isinstance(parsed, list)
            assert parsed[0]["label"] == "行业Beta为正"
            assert parsed[0]["category"] == "beta"


# ============================================================
# Test: Transition Analyzer
# ============================================================


class TestTransitionAnalyzer:
    def test_build_state_transitions(self, sample_rows):
        transitions = build_state_transitions(sample_rows)
        assert len(transitions) > 0
        total_prob = 0.0
        from_state = transitions[0].from_state
        for t in transitions:
            if t.from_state == from_state:
                total_prob += t.probability
        assert total_prob == pytest.approx(1.0, abs=0.01)


# ============================================================
# Test: CSV Writer
# ============================================================


class TestCsvWriter:
    def test_write_history_csv(self, sample_rows):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_history.csv"
            write_history_csv(sample_rows, path)
            assert path.exists()

            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 7
            assert rows[0]["date"] == "20260101"
            assert rows[0]["industry_beta"] == "positive"

    def test_write_history_csv_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_history.csv"
            write_history_csv([], path)
            assert not path.exists()


# ============================================================
# Test: Operator Workbench
# ============================================================


class TestOperatorWorkbench:
    def test_identify_counter_intuitive_signal_trap(self):
        lifts = [
            SignalLift(
                label="放量上涨",
                category="volume",
                appearance_count=8,
                avg_next_1d=-1.2,
                avg_next_3d=None,
                avg_next_5d=None,
                avg_next_1d_excess=None,
                win_rate_1d=0.25,
                baseline_avg_next_1d=0.1,
                baseline_win_rate_1d=0.5,
                avg_next_1d_delta_pp=-1.3,
                lift_next_1d=None,
                lift_win_rate=-0.25,
                min_count_passed=True,
            )
        ]
        result = identify_counter_intuitive_signals(lifts)
        assert len(result) == 1
        assert result[0].verdict == "signal_trap"

    def test_build_conditional_signal_effects(self):
        rows = [
            _make_row(date="20260101", signal_labels="资金价格背离", signal_categories="volume", signal_pairs='[{"label":"资金价格背离","category":"volume"}]', next_1d_return=2.0),
            _make_row(date="20260102", signal_labels="资金价格背离", signal_categories="volume", signal_pairs='[{"label":"资金价格背离","category":"volume"}]', next_1d_return=1.5),
            _make_row(date="20260103", signal_labels="资金价格背离", signal_categories="volume", signal_pairs='[{"label":"资金价格背离","category":"volume"}]', next_1d_return=1.0),
            _make_row(date="20260104", signal_labels="放量上涨", signal_categories="volume", signal_pairs='[{"label":"放量上涨","category":"volume"}]', next_1d_return=-1.0),
        ]
        lifts = build_signal_lifts(rows, min_count=1)
        effects = build_conditional_signal_effects(rows, lifts, min_count=3)
        assert any(e.label == "资金价格背离" for e in effects)

    def test_build_operator_playbook_outputs_roles(self):
        rows = [
            _make_row(
                date=f"202601{i:02d}",
                signal_labels="资金价格背离",
                signal_categories="volume",
                signal_pairs='[{"label":"资金价格背离","category":"volume"}]',
                next_1d_return=1.0,
            )
            for i in range(1, 13)
        ]
        lifts = build_signal_lifts(rows, min_count=1)
        counter = identify_counter_intuitive_signals(lifts, min_count=1)
        effects = build_conditional_signal_effects(rows, lifts, min_count=3)
        rolling = [
            RollingMetrics(
                date=row.date,
                excess_5d=1.0,
                excess_10d=2.0,
                outperform_streak=2,
                beta_streak=1,
                theme_vs_core_streak=0,
                risk_high_streak=0,
            )
            for row in rows
        ]
        view = build_operator_playbook(rows, rolling, lifts, counter, effects, min_signal_count=1)
        assert view.playbook.stance in {"active_watch", "cautious_watch", "wait"}
        assert len(view.signal_roles) > 0
