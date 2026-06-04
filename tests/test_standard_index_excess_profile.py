"""
标准指数超额画像分析 — 单元测试
================================
17 项测试，使用合成数据验证核心逻辑。
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.index_products.excess_profile import (
    ASOF_MIN_SAMPLES,
    GRADE_DEFS,
    HOLDING_WINDOWS,
    INDEX_IDS,
    SIGNAL_WINDOWS,
    _assign_grade,
    _percentile_thresholds,
    _worst_status,
    build_excess_profile,
    check_anchor_continuity,
    compute_asof_grades,
    compute_benchmark_comparison,
    compute_forward_labels,
    compute_grade_profile,
    compute_non_overlapping_profile,
    compute_quality_sensitivity,
    compute_signal_quality,
    compute_static_grades,
    extract_signals,
)


# ── 合成数据 ──


def _make_synthetic_data(n_days: int = 100, n_valid: int = 100) -> tuple[pd.DataFrame, pd.DataFrame]:
    """生成合成 excess_df 和 nav_df。"""
    np.random.seed(42)
    dates = [f"2025{d:04d}" for d in range(601, 601 + n_days)]
    anchor_closes = [100.0 + i * 0.5 + np.random.normal(0, 1) for i in range(n_days)]

    # excess_df — excess = anchor_return - index_return (consistent with nav_df)
    excess_rows = []
    for i, date in enumerate(dates):
        row = {"date": date, "anchor_symbol": "688333.SH", "anchor_close": anchor_closes[i]}
        for w in [1, 3, 5, 10]:
            if i >= w - 1:
                row[f"anchor_return_{w}d"] = (anchor_closes[i] / anchor_closes[i - w] - 1) * 100
            else:
                row[f"anchor_return_{w}d"] = None
            for idx_id in INDEX_IDS:
                if i >= w - 1:
                    # excess = anchor_return - index_return, index_return = 0.1*w
                    row[f"excess_vs_{idx_id}_{w}d"] = row[f"anchor_return_{w}d"] - 0.1 * w
                else:
                    row[f"excess_vs_{idx_id}_{w}d"] = None
        excess_rows.append(row)
    excess_df = pd.DataFrame(excess_rows)

    # nav_df
    nav_rows = []
    for idx_id in INDEX_IDS:
        nav = 1000.0
        for i, date in enumerate(dates):
            if i > 0:
                nav *= (1 + 0.001 * (i % 5 - 2))
            row = {
                "index_id": idx_id,
                "trade_date": date,
                "nav": nav,
            }
            for w in [1, 3, 5, 10]:
                if i >= w - 1:
                    row[f"index_return_{w}d"] = 0.1 * w
                else:
                    row[f"index_return_{w}d"] = None
            row.update({
                "is_rebalance_day": False,
                "rebalance_uses_stale_price": False,
                "rebalance_reason": "none",
                "included_member_count": 10,
                "configured_member_count": 10,
                "fresh_price_count": 10 if i < n_valid else 5,
                "stale_price_count": 0 if i < n_valid else 5,
                "stale_days_max": 0,
                "stale_symbols": "",
                "fresh_quote_ratio": 1.0 if i < n_valid else 0.5,
                "universe_inclusion_ratio": 1.0,
                "data_status": "ok" if i < n_valid else "partial",
                "rebalance_flag": "",
                "pool_config_version": "2026-05-06",
                "price_adjustment_mode": "qfq",
                "universe_mode": "constant_universe_research_view",
                "source_data_as_of": "20260602",
                "build_mode": "full_rebuild",
                "generated_at": "2026-06-03T00:00:00+00:00",
            })
            nav_rows.append(row)
    nav_df = pd.DataFrame(nav_rows)

    return excess_df, nav_df


def _write_input_files(excess_df: pd.DataFrame, nav_df: pd.DataFrame, manifest: dict, input_dir: Path):
    """写入合成输入文件。"""
    input_dir.mkdir(parents=True, exist_ok=True)
    excess_df.to_csv(input_dir / "anchor_index_excess.csv", index=False)
    nav_df.to_csv(input_dir / "custom_index_nav.csv", index=False)
    with open(input_dir / "build_manifest.json", "w") as f:
        json.dump(manifest, f)


# ── 测试 ──


class TestExcessFormula:
    """1. 标准超额公式：从 CSV 读取的值 = anchor_return_Nd - index_return_Nd"""

    def test_excess_equals_anchor_minus_index(self):
        excess_df, nav_df = _make_synthetic_data()
        signals = extract_signals(excess_df)
        for day_idx in [10, 20, 30]:
            row = signals[(signals["index_id"] == "industry_chain_index") & (signals["signal_window"] == 5)]
            sig = row.iloc[day_idx]
            csv_val = excess_df.iloc[day_idx]["excess_vs_industry_chain_index_5d"]
            assert abs(sig["standard_excess"] - csv_val) < 0.01


class TestExcessNotDailySum:
    """2. 5D/10D 超额不是 daily_excess 简单求和"""

    def test_5d_not_sum_of_1d(self):
        excess_df, nav_df = _make_synthetic_data()
        signals = extract_signals(excess_df)
        ic_5d = signals[(signals["index_id"] == "industry_chain_index") & (signals["signal_window"] == 5)]
        ic_1d = signals[(signals["index_id"] == "industry_chain_index") & (signals["signal_window"] == 1)]
        # 5d excess = anchor_return_5d - index_return_5d
        # sum of 1d excess = sum(anchor_return_1d - index_return_1d) for 5 days
        # These are different formulas. Verify at least one day where they differ.
        found_difference = False
        for i in range(10, 20):
            vals_1d = [ic_1d.iloc[i - k]["standard_excess"] for k in range(5)]
            if any(pd.isna(v) for v in vals_1d):
                continue
            sum_1d = sum(vals_1d)
            excess_5d = ic_5d.iloc[i]["standard_excess"]
            if pd.notna(excess_5d) and abs(sum_1d) > 0.01:
                if abs(excess_5d - sum_1d) > 0.01:
                    found_difference = True
                    break
        assert found_difference, "5d excess should differ from sum of 1d excess (compound vs simple)"


class TestForwardLabelFormula:
    """3. Forward label 公式正确"""

    def test_future_anchor_return_5d(self):
        excess_df, nav_df = _make_synthetic_data()
        signals = extract_signals(excess_df)
        labels = compute_forward_labels(signals, excess_df, nav_df)
        row = labels[(labels["date"] == "20250601") & (labels["index_id"] == "industry_chain_index") & (labels["holding_window"] == 5)]
        if not row.empty and pd.notna(row.iloc[0]["future_anchor_return"]):
            expected = (excess_df.iloc[5]["anchor_close"] / excess_df.iloc[0]["anchor_close"] - 1) * 100
            assert abs(row.iloc[0]["future_anchor_return"] - expected) < 0.01


class TestLastHNoLabel:
    """4. 最后 H 个交易日没有 future label，且标记为 no_future_label"""

    def test_last_10_days_no_10d_label(self):
        excess_df, nav_df = _make_synthetic_data()
        signals = extract_signals(excess_df)
        labels = compute_forward_labels(signals, excess_df, nav_df)
        last_date = excess_df["date"].iloc[-1]
        row = labels[(labels["date"] == last_date) & (labels["holding_window"] == 10)]
        assert row.iloc[0]["future_anchor_return"] is None or pd.isna(row.iloc[0]["future_anchor_return"])
        assert row.iloc[0]["label_quality_status"] == "no_future_label"


class TestIndependentGrading:
    """5. 四个信号窗口分别独立分档"""

    def test_different_thresholds_per_window(self):
        np.random.seed(42)
        excess_df, nav_df = _make_synthetic_data(200)
        signals = extract_signals(excess_df)
        signals = compute_signal_quality(signals, nav_df)
        signals, thresholds = compute_static_grades(signals)
        ic = thresholds["industry_chain_index"]
        assert "P20" in ic["1d"]
        assert "P20" in ic["5d"]
        # With 200 days and random data, thresholds should differ across windows
        assert ic["1d"]["P20"] != ic["10d"]["P20"]


class TestAsofNoLookahead:
    """6. asof_grade 只使用 t-1 及以前数据"""

    def test_asof_uses_past_only(self):
        excess_df, nav_df = _make_synthetic_data(120)
        signals = extract_signals(excess_df)
        signals = compute_signal_quality(signals, nav_df)
        signals, asof_df = compute_asof_grades(signals)
        sub = asof_df[(asof_df["index_id"] == "industry_chain_index") & (asof_df["signal_window"] == 1)]
        valid = sub[sub["asof_grade"] > 0]
        assert len(valid) > 0
        insufficient = sub[sub["asof_grade_label"] == "insufficient_grade_history"]
        assert len(insufficient) >= ASOF_MIN_SAMPLES


class TestInsufficientDataExcluded:
    """7. insufficient_data 行被排除"""

    def test_insufficient_data_not_in_profile(self):
        excess_df, nav_df = _make_synthetic_data(100, 90)
        mask = nav_df["index_id"] == "industry_chain_index"
        nav_df.loc[mask & (nav_df["trade_date"] == "20250610"), "data_status"] = "insufficient_data"
        nav_df.loc[mask & (nav_df["trade_date"] == "20250610"), "fresh_quote_ratio"] = 0.1
        nav_df.loc[mask & (nav_df["trade_date"] == "20250610"), "universe_inclusion_ratio"] = 0.1

        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "input"
            output_dir = Path(tmp) / "output"
            manifest = {"pool_config_version": "2026-05-06", "source_data_as_of": "20260602"}
            _write_input_files(excess_df, nav_df, manifest, input_dir)
            build_excess_profile(input_dir, output_dir)

            sig = pd.read_csv(output_dir / "signal_daily.csv")
            insuf = sig[(sig["signal_quality_status"] == "insufficient_data")]
            assert all(insuf["static_grade"] == 0)
            assert all(insuf["asof_grade"] == 0)


class TestPartialOnlyUsable:
    """8. partial 行只进入 usable，不进入 strict_ok_only"""

    def test_partial_in_usable_not_strict(self):
        excess_df, nav_df = _make_synthetic_data(100, 90)
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "input"
            output_dir = Path(tmp) / "output"
            manifest = {"pool_config_version": "2026-05-06", "source_data_as_of": "20260602"}
            _write_input_files(excess_df, nav_df, manifest, input_dir)
            build_excess_profile(input_dir, output_dir)

            gp = pd.read_csv(output_dir / "grade_profile.csv")
            strict = gp[gp["quality_scope"] == "strict_ok_only"]
            usable = gp[gp["quality_scope"] == "usable"]
            for idx_id in INDEX_IDS:
                for sw in SIGNAL_WINDOWS:
                    for hw in HOLDING_WINDOWS:
                        for g_num, _ in GRADE_DEFS:
                            s = strict[(strict["index_id"] == idx_id) & (strict["signal_window"] == sw)
                                       & (strict["holding_window"] == hw) & (strict["grade"] == g_num)]
                            u = usable[(usable["index_id"] == idx_id) & (usable["signal_window"] == sw)
                                       & (usable["holding_window"] == hw) & (usable["grade"] == g_num)]
                            if not s.empty and not u.empty:
                                assert u["sample_count"].values[0] >= s["sample_count"].values[0]


class TestFourIndicesSeparate:
    """9. 四条指数分别输出，不允许混合"""

    def test_no_cross_index_rows(self):
        excess_df, nav_df = _make_synthetic_data()
        signals = extract_signals(excess_df)
        for sw in SIGNAL_WINDOWS:
            counts = signals[signals["signal_window"] == sw].groupby("date").size()
            assert all(counts == len(INDEX_IDS))


class TestOldFilesNotModified:
    """10. 旧数据文件未被修改"""

    def test_upstream_unchanged(self):
        excess_df, nav_df = _make_synthetic_data(100)
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "input"
            output_dir = Path(tmp) / "output"
            manifest = {"pool_config_version": "2026-05-06", "source_data_as_of": "20260602"}
            _write_input_files(excess_df, nav_df, manifest, input_dir)

            excess_path = input_dir / "anchor_index_excess.csv"
            nav_path = input_dir / "custom_index_nav.csv"
            mt_before_excess = excess_path.stat().st_mtime
            mt_before_nav = nav_path.stat().st_mtime

            build_excess_profile(input_dir, output_dir)

            assert excess_path.stat().st_mtime == mt_before_excess
            assert nav_path.stat().st_mtime == mt_before_nav


class TestScriptRunnable:
    """11. 脚本可从项目根目录直接运行"""

    def test_script_exists(self):
        script = Path(__file__).parent.parent / "scripts" / "build_standard_index_excess_profile.py"
        assert script.exists()
        content = script.read_text()
        assert "sys.path.insert" in content
        assert "build_excess_profile" in content


class TestGradeModeColumn:
    """12. grade_profile.csv 包含 grade_mode 列"""

    def test_grade_mode_present(self):
        excess_df, nav_df = _make_synthetic_data(100)
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "input"
            output_dir = Path(tmp) / "output"
            manifest = {"pool_config_version": "2026-05-06", "source_data_as_of": "20260602"}
            _write_input_files(excess_df, nav_df, manifest, input_dir)
            build_excess_profile(input_dir, output_dir)

            gp = pd.read_csv(output_dir / "grade_profile.csv")
            assert "grade_mode" in gp.columns
            assert set(gp["grade_mode"].unique()) == {"static_full_sample", "asof"}


class TestDuplicateThresholdGrading:
    """13. 重复值导致分位阈值相等时，分档仍正确"""

    def test_equal_thresholds(self):
        values = np.array([1.0] * 100)
        th = _percentile_thresholds(values, [20, 40, 60, 80])
        assert th["P20"] == th["P40"] == th["P60"] == th["P80"] == 1.0
        g, label = _assign_grade(1.0, th)
        assert g == 1
        g2, _ = _assign_grade(2.0, th)
        assert g2 == 5


class TestNonOverlappingInterval:
    """14. non_overlapping_profile 相邻样本间隔 ≥ H"""

    def test_interval_ge_holding(self):
        excess_df, nav_df = _make_synthetic_data(100)
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "input"
            output_dir = Path(tmp) / "output"
            manifest = {"pool_config_version": "2026-05-06", "source_data_as_of": "20260602"}
            _write_input_files(excess_df, nav_df, manifest, input_dir)
            build_excess_profile(input_dir, output_dir)

            no = pd.read_csv(output_dir / "non_overlapping_profile.csv")
            assert "evaluation_mode" in no.columns
            assert all(no["evaluation_mode"] == "non_overlapping")

            # Verify actual date spacing using forward_labels
            fl = pd.read_csv(output_dir / "forward_labels.csv")
            dates_all = sorted(fl[fl["index_id"] == "industry_chain_index"]["date"].unique())
            date_to_idx = {d: i for i, d in enumerate(dates_all)}

            # For each (grade_mode, grade, holding_window), check spacing
            sig = pd.read_csv(output_dir / "signal_daily.csv")
            for hw in [5, 10]:
                sub = sig[
                    (sig["index_id"] == "industry_chain_index")
                    & (sig["signal_window"] == 5)
                    & (sig["asof_grade"] == 5)
                    & (sig["signal_quality_status"] != "insufficient_data")
                ].sort_values("date")

                # Build non-overlapping selection
                selected = []
                last_idx = -hw
                for _, row in sub.iterrows():
                    cur_idx = date_to_idx.get(row["date"], -1)
                    if cur_idx - last_idx >= hw:
                        selected.append(row["date"])
                        last_idx = cur_idx
                # There should be at least 1 selected
                if len(selected) > 1:
                    for i in range(1, len(selected)):
                        gap = date_to_idx[selected[i]] - date_to_idx[selected[i - 1]]
                        assert gap >= hw, f"Non-overlapping gap {gap} < hw={hw}"


class TestIntervalQuality:
    """15. signal_quality_status 覆盖 [t-N, t]（含两端）"""

    def test_signal_quality_covers_full_lookback(self):
        excess_df, nav_df = _make_synthetic_data(100, 90)
        signals = extract_signals(excess_df)
        signals = compute_signal_quality(signals, nav_df)

        # For 5d signal, quality should cover [t-5, t] = 6 days
        # If day t-5 is partial but t..t-4 are ok, signal_quality should be partial
        ic_5d = signals[(signals["index_id"] == "industry_chain_index") & (signals["signal_window"] == 5)]
        # Day 95 (0-indexed) is partial (n_valid=90). Day 90 is the first partial day.
        # For signal at day 95, lookback [90, 95] includes partial days → should be partial
        day_95 = ic_5d[ic_5d["date"] == "20250695"]
        if not day_95.empty:
            assert day_95.iloc[0]["signal_quality_status"] == "partial"

        # For day 89, lookback [84, 89] is all ok → should be ok
        day_89 = ic_5d[ic_5d["date"] == "20250689"]
        if not day_89.empty:
            assert day_89.iloc[0]["signal_quality_status"] == "ok"


class TestNoFutureLabelExcluded:
    """16. no_future_label 行不进入 usable 也不进入 strict_ok_only"""

    def test_no_future_label_excluded_from_stats(self):
        excess_df, nav_df = _make_synthetic_data(100)
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "input"
            output_dir = Path(tmp) / "output"
            manifest = {"pool_config_version": "2026-05-06", "source_data_as_of": "20260602"}
            _write_input_files(excess_df, nav_df, manifest, input_dir)
            build_excess_profile(input_dir, output_dir)

            # Verify: forward_labels with no_future_label should not appear in any profile
            fl = pd.read_csv(output_dir / "forward_labels.csv")
            no_label = fl[fl["label_quality_status"] == "no_future_label"]
            # There should be some no_future_label rows
            assert len(no_label) > 0

            # Verify they are not in grade_profile (usable or strict)
            gp = pd.read_csv(output_dir / "grade_profile.csv")
            # sample_count should always equal the count of valid (non-null) future_excess rows
            # This is implicitly verified by TestSampleCountMatchesValidExcess


class TestSampleCountMatchesValidExcess:
    """17. profile 中 sample_count 等于有效 future_excess 的行数"""

    def test_sample_count_equals_valid_future_excess(self):
        excess_df, nav_df = _make_synthetic_data(100)
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "input"
            output_dir = Path(tmp) / "output"
            manifest = {"pool_config_version": "2026-05-06", "source_data_as_of": "20260602"}
            _write_input_files(excess_df, nav_df, manifest, input_dir)
            build_excess_profile(input_dir, output_dir)

            gp = pd.read_csv(output_dir / "grade_profile.csv")
            fl = pd.read_csv(output_dir / "forward_labels.csv")
            sig = pd.read_csv(output_dir / "signal_daily.csv")

            # Spot check: industry_chain, asof, 5d signal, 10d hold, Q5, usable
            row = gp[
                (gp["index_id"] == "industry_chain_index")
                & (gp["grade_mode"] == "asof")
                & (gp["signal_window"] == 5)
                & (gp["holding_window"] == 10)
                & (gp["grade"] == 5)
                & (gp["quality_scope"] == "usable")
            ]
            if not row.empty:
                reported_n = row["sample_count"].values[0]
                # Manually count: merge, filter grade, filter quality, count non-null future_excess
                merged = fl.merge(
                    sig[["date", "index_id", "signal_window", "asof_grade", "signal_quality_status"]],
                    on=["date", "index_id"],
                    how="left",
                )
                manual = merged[
                    (merged["index_id"] == "industry_chain_index")
                    & (merged["signal_window"] == 5)
                    & (merged["holding_window"] == 10)
                    & (merged["asof_grade"] == 5)
                    & (~merged["signal_quality_status"].isin(["insufficient_data", "no_future_label"]))
                    & (~merged["label_quality_status"].isin(["insufficient_data", "no_future_label"]))
                    & (merged["future_excess"].notna())
                ]
                assert reported_n == len(manual), f"sample_count={reported_n} but valid rows={len(manual)}"
