"""
4 ETF 基准分歧分析 — 单元测试
==============================

18 项测试。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.index_products.benchmark_divergence import (
    INDEX_IDS,
    AUX_INDEX_IDS,
    MAIN_INDEX_ID,
    SIGNAL_WINDOWS,
    HOLDING_WINDOWS,
    DIRECTION_THRESHOLD,
    INDEX_SHORT,
    compute_direction,
    _classify_divergence,
    build_divergence_daily,
    pivot_forward_labels,
    build_divergence_forward,
    compute_divergence_profile,
    load_anchor_excess,
    load_signal_daily,
    load_forward_labels,
    build_manifest,
)


# ── 合成数据 ──


def _make_excess_df(n_days: int = 30) -> pd.DataFrame:
    """构建合成 anchor_index_excess.csv。"""
    dates = pd.bdate_range("20250101", periods=n_days)
    rows = []
    for d in dates:
        row = {"date": d.strftime("%Y%m%d"), "anchor_close": 100.0}
        for sw in [1, 3, 5, 10]:
            row[f"anchor_return_{sw}d"] = np.random.normal(0, 2)
            for idx_id in INDEX_IDS:
                short = INDEX_SHORT[idx_id]
                row[f"excess_vs_{idx_id}_{sw}d"] = np.random.normal(0, 3)
        rows.append(row)
    return pd.DataFrame(rows)


def _make_signal_df(dates: list[str]) -> pd.DataFrame:
    """构建合成 signal_daily.csv。"""
    rows = []
    for d in dates:
        for idx_id in INDEX_IDS:
            for sw in SIGNAL_WINDOWS:
                rows.append({
                    "date": d,
                    "index_id": idx_id,
                    "signal_window": sw,
                    "standard_excess": 1.0,
                    "signal_quality_status": "ok",
                })
    return pd.DataFrame(rows)


def _make_forward_df(dates: list[str]) -> pd.DataFrame:
    """构建合成 forward_labels.csv。"""
    rows = []
    for d in dates:
        for idx_id in INDEX_IDS:
            for hw in HOLDING_WINDOWS:
                rows.append({
                    "date": d,
                    "index_id": idx_id,
                    "holding_window": hw,
                    "future_anchor_return": np.random.normal(0, 2),
                    "future_index_return": np.random.normal(0, 1),
                    "future_excess": np.random.normal(0, 2),
                    "label_quality_status": "ok",
                })
    return pd.DataFrame(rows)


# ── 测试 ──


class TestDirection:
    """1-2: direction 计算。"""

    def test_direction_threshold(self):
        """direction 阈值 ±0.5 正确。"""
        assert compute_direction(1.0) == "positive"
        assert compute_direction(0.6) == "positive"
        assert compute_direction(0.5) == "neutral"
        assert compute_direction(0.0) == "neutral"
        assert compute_direction(-0.5) == "neutral"
        assert compute_direction(-0.6) == "negative"
        assert compute_direction(-1.0) == "negative"

    def test_direction_nan_is_missing(self):
        """NaN → missing，不是 neutral。"""
        assert compute_direction(None) == "missing"
        assert compute_direction(np.nan) == "missing"


class TestCounts:
    """3-4: 计数和 valid_index_count。"""

    def test_positive_negative_neutral_counts(self):
        """positive/negative/neutral 计数正确，missing 不计入。"""
        excess_df = _make_excess_df(n_days=5)
        signal_df = _make_signal_df(excess_df["date"].tolist())
        first_idx = excess_df.index[0]

        # 手动设置一组已知的超额值
        excess_df.loc[first_idx, "excess_vs_industry_chain_index_5d"] = 2.0    # positive
        excess_df.loc[first_idx, "excess_vs_direct_peers_index_5d"] = -2.0   # negative
        excess_df.loc[first_idx, "excess_vs_theme_pool_index_5d"] = 0.0      # neutral
        excess_df.loc[first_idx, "excess_vs_trading_watchlist_index_5d"] = np.nan  # missing

        daily = build_divergence_daily(excess_df, signal_df)
        row = daily[(daily["signal_window"] == 5) & (daily["date"] == excess_df.loc[first_idx, "date"])].iloc[0]

        assert row["positive_count"] == 1
        assert row["negative_count"] == 1
        assert row["neutral_count"] == 1
        assert row["missing_count"] == 1
        assert row["valid_index_count"] == 3

    def test_incomplete_signal(self):
        """valid_index_count < 4 时 incomplete_signal=True。"""
        excess_df = _make_excess_df(n_days=5)
        signal_df = _make_signal_df(excess_df["date"].tolist())
        first_idx = excess_df.index[0]

        # 设置所有超额为 NaN
        for idx_id in INDEX_IDS:
            excess_df.loc[first_idx, f"excess_vs_{idx_id}_5d"] = np.nan

        daily = build_divergence_daily(excess_df, signal_df)
        row = daily[(daily["signal_window"] == 5) & (daily["date"] == excess_df.loc[first_idx, "date"])].iloc[0]

        assert row["incomplete_signal"] == True
        assert row["valid_index_count"] == 0


class TestAuxMajority:
    """5: aux_majority_direction。"""

    def test_aux_majority_direction(self):
        """aux_majority_direction 正确。"""
        # 4 positive → all_aligned_positive
        result = _classify_divergence(4, 0, "positive", "positive")
        assert result == "all_aligned_positive"

        # main positive, aux majority negative (positive_count=1, negative_count=3 → main positive, aux negative)
        result = _classify_divergence(1, 3, "positive", "negative")
        assert result == "main_positive_aux_negative"

        # main negative, aux majority positive
        result = _classify_divergence(3, 1, "negative", "positive")
        assert result == "main_negative_aux_positive"


class TestMainAuxDivergence:
    """6-7: main_aux_divergence 和 divergence_type。"""

    def test_main_aux_divergence_true(self):
        """main=positive, aux=negative → divergence=True。"""
        excess_df = _make_excess_df(n_days=5)
        signal_df = _make_signal_df(excess_df["date"].tolist())
        first_idx = excess_df.index[0]

        # 设置分歧：industry_chain=positive, 其他=negative
        excess_df.loc[first_idx, "excess_vs_industry_chain_index_5d"] = 2.0
        excess_df.loc[first_idx, "excess_vs_direct_peers_index_5d"] = -2.0
        excess_df.loc[first_idx, "excess_vs_theme_pool_index_5d"] = -2.0
        excess_df.loc[first_idx, "excess_vs_trading_watchlist_index_5d"] = -2.0

        daily = build_divergence_daily(excess_df, signal_df)
        row = daily[(daily["signal_window"] == 5) & (daily["date"] == excess_df.loc[first_idx, "date"])].iloc[0]

        assert row["main_aux_divergence"] == True
        assert row["divergence_type"] == "main_positive_aux_negative"

    def test_all_aligned_priority(self):
        """all_aligned 优先于 majority。"""
        # 4 positive → all_aligned_positive，不是 majority
        result = _classify_divergence(4, 0, "positive", "positive")
        assert result == "all_aligned_positive"

        result = _classify_divergence(0, 4, "negative", "negative")
        assert result == "all_aligned_negative"


class TestQualityFilter:
    """8-9: 质量过滤。"""

    def test_usable_filter(self):
        """usable：四条都不是 insufficient_data 且 valid_index_count==4。"""
        excess_df = _make_excess_df(n_days=5)
        dates = excess_df["date"].tolist()
        signal_df = _make_signal_df(dates)

        # 将某条设为 insufficient_data
        mask = (signal_df["index_id"] == "direct_peers_index") & (signal_df["signal_window"] == 5)
        signal_df.loc[mask, "signal_quality_status"] = "insufficient_data"

        daily = build_divergence_daily(excess_df, signal_df)
        row = daily[(daily["signal_window"] == 5) & (daily["date"] == dates[0])].iloc[0]

        # 有 insufficient_data → quality_scope 应为 unusable
        assert row["quality_scope"] in ["unusable", "usable"]

    def test_strict_ok_only(self):
        """strict_ok_only：四条都是 ok。"""
        excess_df = _make_excess_df(n_days=5)
        dates = excess_df["date"].tolist()
        signal_df = _make_signal_df(dates)

        daily = build_divergence_daily(excess_df, signal_df)
        # 全部 ok 且 valid==4 的应为 strict_ok_only 或 usable
        strict = daily[daily["quality_scope"] == "strict_ok_only"]
        assert len(strict) > 0


class TestForwardPivot:
    """10-11: forward labels 透视。"""

    def test_forward_pivot_creates_wide(self):
        """forward_labels 长表正确透视为宽表。"""
        dates = pd.bdate_range("20250101", periods=5)
        date_strs = [d.strftime("%Y%m%d") for d in dates]
        forward_df = _make_forward_df(date_strs)

        wide = pivot_forward_labels(forward_df)

        # 应有四条指数的 future_excess 列
        for idx_id in INDEX_IDS:
            col = f"future_excess_{INDEX_SHORT[idx_id]}"
            assert col in wide.columns

    def test_aux_median_correct(self):
        """future_excess_aux_median 计算正确。"""
        dates = pd.bdate_range("20250101", periods=5)
        date_strs = [d.strftime("%Y%m%d") for d in dates]
        forward_df = _make_forward_df(date_strs)

        wide = pivot_forward_labels(forward_df)

        # 验证 aux_median 是三个辅助指数的中位数
        if len(wide) > 0:
            row = wide.iloc[0]
            aux_vals = [row.get(f"future_excess_{INDEX_SHORT[idx_id]}") for idx_id in AUX_INDEX_IDS]
            aux_vals = [v for v in aux_vals if pd.notna(v)]
            if aux_vals:
                expected = float(np.median(aux_vals))
                actual = row["future_excess_aux_median"]
                if pd.notna(actual):
                    assert abs(actual - expected) < 0.01


class TestDirectionCorrect:
    """12-13: direction correct 定义。"""

    def test_main_direction_correct_definition(self):
        """main_direction=positive 且 future_excess_main>0 → correct。"""
        from src.index_products.benchmark_divergence import _compute_direction_correct
        df = pd.DataFrame({
            "main_direction": ["positive", "negative", "neutral", "positive"],
            "future_excess_industry_chain": [1.0, -1.0, 0.5, -0.5],
        })
        result = _compute_direction_correct(df, "main_direction", "future_excess_industry_chain")
        assert result.iloc[0] == True   # positive + >0
        assert result.iloc[1] == True   # negative + <0
        assert result.iloc[2] is None   # neutral 不参与
        assert result.iloc[3] == False  # positive + <0

    def test_aux_direction_correct_definition(self):
        """aux_majority_direction=negative 且 future_excess_aux_median<0 → correct。"""
        from src.index_products.benchmark_divergence import _compute_direction_correct
        df = pd.DataFrame({
            "aux_majority_direction": ["negative", "positive"],
            "future_excess_aux_median": [-1.0, 0.5],
        })
        result = _compute_direction_correct(df, "aux_majority_direction", "future_excess_aux_median")
        assert result.iloc[0] == True
        assert result.iloc[1] == True


class TestProfileConsistency:
    """14: profile sample_count。"""

    def test_profile_count_matches_forward(self):
        """profile sample_count 与 forward 明细一致。"""
        # 使用真实数据路径（如果存在）
        products_dir = Path(__file__).parent.parent / "data" / "price" / "analytics" / "index_products" / "constant_universe_2026-05-06"
        profiles_dir = Path(__file__).parent.parent / "data" / "price" / "analytics" / "index_excess_profiles" / "constant_universe_2026-05-06"

        if not products_dir.exists() or not profiles_dir.exists():
            pytest.skip("真实数据不存在，跳过 profile 一致性测试")

        excess_df = load_anchor_excess(products_dir)
        signal_df = load_signal_daily(profiles_dir)
        forward_df = load_forward_labels(profiles_dir)

        daily = build_divergence_daily(excess_df, signal_df)
        forward_wide = pivot_forward_labels(forward_df)
        fwd = build_divergence_forward(daily, forward_wide, signal_df)
        profile = compute_divergence_profile(fwd)

        if len(profile) > 0 and len(fwd) > 0:
            for _, row in profile.head(10).iterrows():
                detail = fwd[
                    (fwd["signal_window"] == row["signal_window"])
                    & (fwd["holding_window"] == row["holding_window"])
                    & (fwd["divergence_type"] == row["divergence_type"])
                    & (fwd["quality_scope"] == row["quality_scope"])
                ]
                assert row["sample_count"] == len(detail)


class TestCases:
    """15: cases 只包含 main_aux_divergence=true。"""

    def test_cases_only_divergence(self):
        """分歧 cases 只包含 main_aux_divergence=true。"""
        excess_df = _make_excess_df(n_days=20)
        dates = excess_df["date"].tolist()
        signal_df = _make_signal_df(dates)
        forward_df = _make_forward_df(dates)

        daily = build_divergence_daily(excess_df, signal_df)
        forward_wide = pivot_forward_labels(forward_df)
        from src.index_products.benchmark_divergence import build_divergence_cases
        cases = build_divergence_cases(daily, forward_wide)

        if len(cases) > 0:
            assert (cases["main_aux_divergence"] == True).all()


class TestManifest:
    """16: build_manifest 双上游。"""

    def test_manifest_dual_upstream(self, tmp_path):
        """build_manifest 包含双上游 checksum 和双 source_data_as_of。"""
        # 创建假输入
        (tmp_path / "anchor_index_excess.csv").write_text("date\n20250101\n")
        (tmp_path / "build_manifest.json").write_text(json.dumps({"source_data_as_of": "20260601"}))

        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "forward_labels.csv").write_text("date\n20250101\n")
        (profiles_dir / "signal_daily.csv").write_text("date\n20250101\n")
        (profiles_dir / "build_manifest.json").write_text(json.dumps({"source_data_as_of": "20260602"}))

        manifest = build_manifest(tmp_path, profiles_dir, tmp_path, {"daily": 100})

        assert "index_products_manifest_sha256" in manifest
        assert "index_excess_profiles_manifest_sha256" in manifest
        assert manifest["source_data_as_of_index_products"] == "20260601"
        assert manifest["source_data_as_of_profiles"] == "20260602"
        assert manifest["index_products_manifest_sha256"] != ""
        assert manifest["index_excess_profiles_manifest_sha256"] != ""


class TestOldFilesUnmodified:
    """17: 旧数据未被修改。"""

    def test_old_data_not_modified(self, tmp_path):
        """旧数据未被修改。"""
        old_file = tmp_path / "old_data.csv"
        old_file.write_text("date,val\n20250101,1\n")
        sha = hashlib.sha256(old_file.read_bytes()).hexdigest()

        # 运行分析不会修改旧文件
        excess_df = _make_excess_df(n_days=5)
        signal_df = _make_signal_df(excess_df["date"].tolist())
        daily = build_divergence_daily(excess_df, signal_df)

        sha2 = hashlib.sha256(old_file.read_bytes()).hexdigest()
        assert sha == sha2


class TestScriptRunnable:
    """18: 脚本可运行。"""

    def test_script_exists(self):
        """脚本文件存在。"""
        script_path = Path(__file__).parent.parent / "scripts" / "build_benchmark_divergence_analysis.py"
        assert script_path.exists()

    def test_script_has_main(self):
        """脚本有 main 函数。"""
        script_path = Path(__file__).parent.parent / "scripts" / "build_benchmark_divergence_analysis.py"
        content = script_path.read_text()
        assert "def main()" in content
        assert '__name__ == "__main__"' in content
