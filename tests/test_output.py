"""
Output Layer 单元测试

测试覆盖：
  1. IndustrySnapshot dataclass 结构
  2. Conclusion 计算逻辑
  3. JSON 输出格式
  4. CSV 多行输出
  5. Markdown 报告五章结构

按 implementation.md Phase 6 设计
"""

import pytest
import json
import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from src.output.models import (
    IndustrySnapshot,
    AnchorInfo,
    DataQuality,
    IndustryState,
    AnchorPositionOutput,
    GroupRotationOutput,
    SignalOutput,
    Conclusion,
)
from src.output.conclusion_builder import (
    determine_industry_beta,
    determine_anchor_alpha,
    determine_risk_level,
    generate_summary,
    generate_next_watch,
    build_conclusion,
)
from src.output.json_writer import (
    build_industry_snapshot,
    write_json,
    snapshot_to_dict,
)
from src.output.csv_writer import (
    write_peer_matrix,
    CSV_FIELDS,
)
from src.output.report_generator import (
    generate_report,
    write_report,
)
from src.output import write_all

from src.signal.models import SignalResult, Signal, Evidence
from src.pool_state.models import PoolState, MemberData
from src.anchor_position.relative_strength import RelativeStrength
from src.group_rotation.models import GroupRotation
from src.config.loader import PoolRegistry, Instrument, Universe, Membership, Anchor


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def sample_pool_registry():
    """样本 PoolRegistry"""
    instruments = {
        "688333.SH": Instrument(
            symbol="688333.SH",
            name="铂力特",
            market="科创板",
            exchange="SH",
            fact_tags=["3D打印", "商业航天"],
        ),
        "688433.SH": Instrument(
            symbol="688433.SH",
            name="华曙高科",
            market="科创板",
            exchange="SH",
            fact_tags=["3D打印"],
        ),
    }
    return type("MockRegistry", (), {
        "anchor": Anchor(
            symbol="688333.SH",
            name="铂力特",
            reason="核心标的",
            added_date="2025-01-01",
        ),
        "instruments": instruments,
        "get_anchor": lambda self: Anchor(
            symbol="688333.SH",
            name="铂力特",
            reason="核心标的",
            added_date="2025-01-01",
        ),
        "get_instrument": lambda self, symbol: instruments.get(symbol),
        "get_all_universes": lambda self: [
            Universe("direct_peers", "核心同类", "", True, 3),
            Universe("theme_pool", "主题扩散", "", False, 3),
        ],
        "get_members": lambda self, uid: [
            Membership(uid, "688333.SH", "anchor", 1.0, 1.0, True, True, True, "核心", "2025-01-01", "2025-01-01"),
            Membership(uid, "688433.SH", "peer", 0.8, 0.8, True, True, True, "同类", "2025-01-01", "2025-01-01"),
        ],
    })()


@pytest.fixture
def sample_pool_states():
    """样本池子状态"""
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
            up_ratio=0.80,
            strong_count=2,
            weak_count=0,
            volume_multiplier=1.8,
            fund_positive_ratio=0.70,
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
    }


@pytest.fixture
def sample_anchor_positions():
    """样本相对位置"""
    return {
        "direct_peers": RelativeStrength(
            universe_id="direct_peers",
            trade_date="20260502",
            anchor_return=3.5,
            pool_median=2.5,
            relative_strength=1.0,
            position="outperform",
            rank_return=1,
            rank_volume=2,
            rank_turnover=2,
            rank_fund=2,
            total_count=4,
            valuation_percentile=45.0,
            data_status="ok",
        ),
        "theme_pool": RelativeStrength(
            universe_id="theme_pool",
            trade_date="20260502",
            anchor_return=3.5,
            pool_median=3.0,
            relative_strength=0.5,
            position="neutral",
            rank_return=2,
            rank_volume=3,
            rank_turnover=3,
            rank_fund=3,
            total_count=8,
            valuation_percentile=None,
            data_status="ok",
        ),
    }


@pytest.fixture
def sample_group_rotation():
    """样本组间轮动"""
    return GroupRotation(
        trade_date="20260502",
        strongest_group="theme_pool",
        weakest_group="direct_peers",
        group_ranking=["theme_pool", "direct_peers"],
        spreads={"direct_peers": -0.5},
        core_vs_theme_spread=-0.5,
        core_vs_chain_spread=1.0,
        core_vs_trading_spread=1.7,
        group_medians={"direct_peers": 2.5, "theme_pool": 3.0},
        data_status="ok",
    )


@pytest.fixture
def sample_signal_result():
    """样本信号结果"""
    signals = [
        Signal(
            label="行业Beta为正",
            category="beta",
            confidence="high",
            evidence=Evidence(value=2.5, threshold=0.5, source_pool="direct_peers", source_field="median_return"),
            trade_date="20260502",
        ),
        Signal(
            label="个股Alpha为正",
            category="alpha",
            confidence="medium",
            evidence=Evidence(value=1.0, threshold=0.5, source_pool="direct_peers", source_field="relative_strength"),
            trade_date="20260502",
        ),
        Signal(
            label="跑赢核心同类",
            category="alpha",
            confidence="medium",
            evidence=Evidence(value=1.0, threshold=0.5, source_pool="direct_peers", source_field="position"),
            trade_date="20260502",
        ),
    ]

    return SignalResult(
        trade_date="20260502",
        anchor_symbol="688333.SH",
        signals=signals,
        beta_count=1,
        alpha_count=2,
        volume_count=0,
        rotation_count=0,
        abnormal_count=0,
        data_status="ok",
    )


@pytest.fixture
def sample_market_data():
    """样本行情数据"""
    return {
        "688333.SH": MemberData(
            symbol="688333.SH",
            trade_date="20260502",
            close=50.0,
            pct_chg=3.5,
            amount=500000,
            turnover_rate=2.5,
            net_mf_amount=10000000,
            pe_ttm=None, pb=None, is_valid=True,
        ),
        "688433.SH": MemberData(
            symbol="688433.SH",
            trade_date="20260502",
            close=30.0,
            pct_chg=1.5,
            amount=300000,
            turnover_rate=1.8,
            net_mf_amount=5000000,
            pe_ttm=None, pb=None, is_valid=True,
        ),
    }


# ============================================================
# Conclusion 计算测试
# ============================================================

class TestConclusionBuilder:
    """测试 Conclusion 计算"""

    def test_determine_industry_beta_positive(self, sample_signal_result):
        """测试行业Beta为正"""
        beta = determine_industry_beta(sample_signal_result)
        assert beta == "positive"

    def test_determine_industry_beta_negative(self):
        """测试行业Beta为负"""
        signals = [
            Signal(
                label="行业Beta为负",
                category="beta",
                confidence="high",
                evidence=Evidence(value=-2.0, threshold=-0.5),
                trade_date="20260502",
            )
        ]
        signal_result = SignalResult(
            trade_date="20260502",
            anchor_symbol="688333.SH",
            signals=signals,
            beta_count=1,
        )
        beta = determine_industry_beta(signal_result)
        assert beta == "negative"

    def test_determine_industry_beta_neutral(self):
        """测试行业Beta中性"""
        signals = []
        signal_result = SignalResult(
            trade_date="20260502",
            anchor_symbol="688333.SH",
            signals=signals,
            beta_count=0,
        )
        beta = determine_industry_beta(signal_result)
        assert beta == "neutral"

    def test_determine_anchor_alpha_positive(self, sample_signal_result):
        """测试个股Alpha为正"""
        alpha = determine_anchor_alpha(sample_signal_result)
        assert alpha == "positive"

    def test_determine_anchor_alpha_negative(self):
        """测试个股Alpha为负"""
        signals = [
            Signal(
                label="个股Alpha为负",
                category="alpha",
                confidence="high",
                evidence=Evidence(value=-1.0, threshold=-0.5),
                trade_date="20260502",
            )
        ]
        signal_result = SignalResult(
            trade_date="20260502",
            anchor_symbol="688333.SH",
            signals=signals,
            alpha_count=1,
        )
        alpha = determine_anchor_alpha(signal_result)
        assert alpha == "negative"

    def test_determine_risk_level_low(self, sample_signal_result, sample_pool_states):
        """测试风险等级低"""
        risk = determine_risk_level(sample_signal_result, sample_pool_states)
        assert risk == "low"

    def test_determine_risk_level_high_insufficient_data(self, sample_pool_states):
        """测试风险等级高（数据不足）"""
        signal_result = SignalResult(
            trade_date="20260502",
            anchor_symbol="688333.SH",
            signals=[],
            data_status="insufficient_data",
        )
        risk = determine_risk_level(signal_result, sample_pool_states)
        assert risk == "high"

    def test_determine_risk_level_high_abnormal(self, sample_pool_states):
        """测试风险等级高（异常联动）"""
        signals = [
            Signal(
                label="行业强但个股弱",
                category="abnormal",
                confidence="high",
                evidence=Evidence(value=3.0, threshold=2.0),
                trade_date="20260502",
            )
        ]
        signal_result = SignalResult(
            trade_date="20260502",
            anchor_symbol="688333.SH",
            signals=signals,
            abnormal_count=1,
            data_status="ok",
        )
        risk = determine_risk_level(signal_result, sample_pool_states)
        assert risk == "high"

    def test_determine_risk_level_medium_divergence(self, sample_signal_result):
        """测试风险等级中（行业分化）"""
        pool_states = {
            "direct_peers": PoolState(
                universe_id="direct_peers",
                trade_date="20260502",
                configured_count=5,
                enabled_count=5,
                benchmark_count=3,
                valid_count=3,
                median_return=0.5,
                mean_return=0.5,
                up_ratio=0.50,
                strong_count=4,  # 强势股 >= 3 → 行业分化
                weak_count=1,
                volume_multiplier=1.0,
                fund_positive_ratio=0.50,
                data_status="ok",
                missing_members=[],
            )
        }
        risk = determine_risk_level(sample_signal_result, pool_states)
        assert risk == "medium"

    def test_generate_next_watch(self, sample_signal_result, sample_anchor_positions, sample_pool_states):
        """测试次日观察点生成"""
        watch_points = generate_next_watch(sample_signal_result, sample_anchor_positions, sample_pool_states)
        assert len(watch_points) > 0
        assert "是否连续跑赢主线池" in watch_points

    def test_build_conclusion(self, sample_signal_result, sample_pool_states, sample_anchor_positions, sample_group_rotation):
        """测试完整结论构建"""
        conclusion = build_conclusion(sample_signal_result, sample_pool_states, sample_anchor_positions, sample_group_rotation)

        assert conclusion.industry_beta == "positive"
        assert conclusion.anchor_alpha == "positive"
        assert conclusion.risk_level == "low"
        assert len(conclusion.summary) > 0
        assert len(conclusion.next_watch) > 0


# ============================================================
# JSON 输出测试
# ============================================================

class TestJsonWriter:
    """测试 JSON 输出"""

    def test_build_industry_snapshot(self, sample_pool_registry, sample_pool_states, sample_anchor_positions, sample_group_rotation, sample_signal_result):
        """测试 IndustrySnapshot 构建"""
        snapshot = build_industry_snapshot(
            sample_pool_registry,
            sample_pool_states,
            sample_anchor_positions,
            sample_group_rotation,
            sample_signal_result,
        )

        assert snapshot.anchor.symbol == "688333.SH"
        assert snapshot.anchor.name == "铂力特"
        assert snapshot.as_of_date == "2026-05-02"
        assert snapshot.data_quality.status == "ok"
        assert snapshot.industry_state.direct_peers_return_median == 2.5
        assert snapshot.anchor_position.anchor_return == 3.5
        assert snapshot.group_rotation.strongest_group == "theme_pool"
        assert len(snapshot.signals) == 3
        assert snapshot.conclusion.industry_beta == "positive"

    def test_snapshot_to_dict(self, sample_pool_registry, sample_pool_states, sample_anchor_positions, sample_group_rotation, sample_signal_result):
        """测试 Snapshot 转 dict"""
        snapshot = build_industry_snapshot(
            sample_pool_registry,
            sample_pool_states,
            sample_anchor_positions,
            sample_group_rotation,
            sample_signal_result,
        )

        data = snapshot_to_dict(snapshot)

        assert "anchor" in data
        assert "as_of_date" in data
        assert "data_quality" in data
        assert "industry_state" in data
        assert "anchor_position" in data
        assert "group_rotation" in data
        assert "signals" in data
        assert "conclusion" in data

        # 验证嵌套结构
        assert data["anchor"]["symbol"] == "688333.SH"
        assert data["industry_state"]["direct_peers_return_median"] == 2.5

    def test_write_json(self, sample_pool_registry, sample_pool_states, sample_anchor_positions, sample_group_rotation, sample_signal_result):
        """测试 JSON 文件写入"""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "industry_snapshot.json"

            snapshot = build_industry_snapshot(
                sample_pool_registry,
                sample_pool_states,
                sample_anchor_positions,
                sample_group_rotation,
                sample_signal_result,
            )

            write_json(snapshot, output_path)

            # 验证文件存在
            assert output_path.exists()

            # 验证内容可解析
            with open(output_path, encoding="utf-8") as f:
                data = json.load(f)
                assert data["anchor"]["symbol"] == "688333.SH"


# ============================================================
# CSV 输出测试
# ============================================================

class TestCsvWriter:
    """测试 CSV 输出"""

    def test_csv_fields(self):
        """测试 CSV 字段定义"""
        assert "universe" in CSV_FIELDS
        assert "symbol" in CSV_FIELDS
        assert "pct_chg" in CSV_FIELDS
        assert "return_rank" in CSV_FIELDS

    def test_write_peer_matrix(self, sample_pool_registry, sample_anchor_positions, sample_market_data):
        """测试 CSV 文件写入"""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "peer_matrix.csv"

            write_peer_matrix(sample_pool_registry, sample_market_data, sample_anchor_positions, output_path)

            # 验证文件存在
            assert output_path.exists()

            # 验证内容可解析
            with open(output_path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                # 验证多行（同一股票在不同 universe）
                assert len(rows) > 0

                # 验证字段
                for row in rows:
                    assert "universe" in row
                    assert "symbol" in row
                    assert "pct_chg" in row


# ============================================================
# Markdown 报告测试
# ============================================================

class TestReportGenerator:
    """测试 Markdown 报告"""

    def test_generate_report(self, sample_pool_registry, sample_pool_states, sample_anchor_positions, sample_group_rotation, sample_signal_result):
        """测试报告生成"""
        snapshot = build_industry_snapshot(
            sample_pool_registry,
            sample_pool_states,
            sample_anchor_positions,
            sample_group_rotation,
            sample_signal_result,
        )

        report = generate_report(snapshot, sample_pool_states, sample_signal_result)

        # 验证五章结构
        assert "# 铂力特 行业锚定分析报告" in report
        assert "## 一、行业状态概览" in report
        assert "## 二、行业结构拆解" in report
        assert "## 三、锚定标的相对位置" in report
        assert "## 四、股价联动解释" in report
        assert "## 五、行业联动与异常信号" in report
        assert "## 六、行业模块结论" in report

    def test_write_report(self, sample_pool_registry, sample_pool_states, sample_anchor_positions, sample_group_rotation, sample_signal_result):
        """测试报告文件写入"""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "industry_report.md"

            snapshot = build_industry_snapshot(
                sample_pool_registry,
                sample_pool_states,
                sample_anchor_positions,
                sample_group_rotation,
                sample_signal_result,
            )

            write_report(snapshot, sample_pool_states, sample_signal_result, output_path)

            # 验证文件存在
            assert output_path.exists()

            # 验证内容
            with open(output_path, encoding="utf-8") as f:
                content = f.read()
                assert "行业状态概览" in content
                assert "行业模块结论" in content


# ============================================================
# write_all 测试
# ============================================================

class TestWriteAll:
    """测试一次性写入所有输出"""

    def test_write_all(self, sample_pool_registry, sample_pool_states, sample_anchor_positions, sample_group_rotation, sample_signal_result, sample_market_data):
        """测试 write_all 函数"""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            snapshot = write_all(
                sample_pool_registry,
                sample_pool_states,
                sample_anchor_positions,
                sample_group_rotation,
                sample_signal_result,
                sample_market_data,
                output_dir,
            )

            # 验证三个输出文件都存在
            assert (output_dir / "industry_snapshot.json").exists()
            assert (output_dir / "peer_matrix.csv").exists()
            assert (output_dir / "industry_report.md").exists()

            # 验证返回的 snapshot
            assert snapshot.anchor.symbol == "688333.SH"


# ============================================================
# 数据类不可变测试
# ============================================================

class TestDataclassFrozen:
    """测试数据类不可变"""

    def test_anchor_info_frozen(self):
        """测试 AnchorInfo 不可变"""
        anchor_info = AnchorInfo(symbol="688333.SH", name="铂力特")

        with pytest.raises(AttributeError):
            anchor_info.symbol = "688433.SH"

    def test_conclusion_frozen(self):
        """测试 Conclusion 不可变"""
        conclusion = Conclusion(
            industry_beta="positive",
            anchor_alpha="positive",
            risk_level="low",
            summary="测试总结",
            next_watch=["观察点"],
        )

        with pytest.raises(AttributeError):
            conclusion.industry_beta = "negative"

    def test_industry_snapshot_frozen(self):
        """测试 IndustrySnapshot 不可变"""
        snapshot = IndustrySnapshot(
            anchor=AnchorInfo(symbol="688333.SH", name="铂力特"),
            as_of_date="2026-05-02",
            data_quality=DataQuality(status="ok"),
            industry_state=IndustryState(),
            anchor_position=AnchorPositionOutput(anchor_return=3.5),
            group_rotation=GroupRotationOutput(strongest_group="theme_pool", weakest_group="direct_peers"),
            signals=[],
            conclusion=Conclusion(
                industry_beta="positive",
                anchor_alpha="positive",
                risk_level="low",
                summary="测试",
                next_watch=[],
            ),
        )

        with pytest.raises(AttributeError):
            snapshot.as_of_date = "2026-05-03"
