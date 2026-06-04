"""
Q5 极热负超额来源拆解 — 单元测试
===================================
11 项测试覆盖桶分类、筛选、profile 一致性、non-overlapping、双口径比率。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.index_products.excess_decomposition import (
    FLAT_THRESHOLD,
    ALL_BUCKETS,
    NEGATIVE_BUCKETS,
    POSITIVE_BUCKETS,
    TARGET_INDEX_ID,
    EXCLUDED_STATUSES,
    classify_decomposition_bucket,
    compute_decomposition_daily,
    compute_decomposition_profile,
    _mark_non_overlapping,
    _trading_day_diff,
)


# ── 辅助：构造合成数据 ──


def _make_synthetic_signal(n_days: int = 120, seed: int = 42) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    dates = [f"2025{d:04d}" for d in range(101, 101 + n_days)]
    rows = []
    for d in dates:
        for sw in [1, 3, 5, 10]:
            for idx_id in [TARGET_INDEX_ID, "direct_peers_index"]:
                sq = "ok"
                grade = rng.choice([0, 1, 2, 3, 4, 5], p=[0.05, 0.19, 0.19, 0.19, 0.19, 0.19])
                if grade == 0:
                    sq = "insufficient_data"
                rows.append({
                    "date": d,
                    "index_id": idx_id,
                    "signal_window": sw,
                    "standard_excess": rng.randn() * 3,
                    "signal_quality_status": sq,
                    "asof_grade": grade,
                    "asof_grade_label": {0: "insufficient_grade_history",
                                         1: "极冷", 2: "偏冷", 3: "中性",
                                         4: "偏热", 5: "极热"}[grade],
                })
    return pd.DataFrame(rows)


def _make_synthetic_labels(n_days: int = 120, seed: int = 43) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    dates = [f"2025{d:04d}" for d in range(101, 101 + n_days)]
    rows = []
    for d in dates:
        for hw in [1, 3, 5, 10]:
            for idx_id in [TARGET_INDEX_ID, "direct_peers_index"]:
                anchor_ret = rng.randn() * 3
                index_ret = rng.randn() * 2
                excess = anchor_ret - index_ret
                lq = "ok" if rng.random() > 0.05 else "no_future_label"
                if lq == "no_future_label":
                    excess = None
                    anchor_ret = None
                    index_ret = None
                rows.append({
                    "date": d,
                    "index_id": idx_id,
                    "holding_window": hw,
                    "future_anchor_return": anchor_ret,
                    "future_index_return": index_ret,
                    "future_excess": excess,
                    "label_quality_status": lq,
                })
    return pd.DataFrame(rows)


# ── 测试 ──


class TestBucketMutualExclusiveExhaustive:
    """1. 桶互斥且穷尽：每个样本恰好落入一个桶"""

    def test_exhaustive(self):
        rng = np.random.RandomState(99)
        for _ in range(500):
            ar = rng.randn() * 5
            ir = rng.randn() * 4
            ex = ar - ir
            bucket = classify_decomposition_bucket(ar, ir, ex)
            assert bucket in ALL_BUCKETS, f"Unknown bucket: {bucket}"

    def test_mutually_exclusive(self):
        rng = np.random.RandomState(100)
        seen = set()
        for _ in range(500):
            ar = rng.randn() * 5
            ir = rng.randn() * 4
            ex = ar - ir
            bucket = classify_decomposition_bucket(ar, ir, ex)
            # Each (ar, ir, ex) maps to exactly one bucket — this is implicit
            # in the function, but we verify the bucket is valid
            if ex < 0:
                assert bucket in NEGATIVE_BUCKETS, f"Negative excess {ex} but bucket {bucket} not in NEGATIVE_BUCKETS"
            else:
                assert bucket in POSITIVE_BUCKETS, f"Positive excess {ex} but bucket {bucket} not in POSITIVE_BUCKETS"


class TestAnchorDownIndexUp:
    """2. anchor < -0.5, index > 0, excess < 0 → anchor_down_index_up"""

    def test_basic(self):
        bucket = classify_decomposition_bucket(-2.0, 1.5, -3.5)
        assert bucket == "anchor_down_index_up"

    def test_boundary(self):
        bucket = classify_decomposition_bucket(-0.6, 0.1, -0.7)
        assert bucket == "anchor_down_index_up"


class TestAnchorFlatIndexUp:
    """3. |anchor| ≤ 0.5, index > 0, excess < 0 → anchor_flat_index_up"""

    def test_basic(self):
        bucket = classify_decomposition_bucket(0.2, 2.0, -1.8)
        assert bucket == "anchor_flat_index_up"

    def test_at_threshold(self):
        bucket = classify_decomposition_bucket(0.5, 1.0, -0.5)
        assert bucket == "anchor_flat_index_up"

    def test_negative_anchor_at_threshold(self):
        bucket = classify_decomposition_bucket(-0.5, 1.0, -1.5)
        assert bucket == "anchor_flat_index_up"


class TestPositiveBucketUpOutperform:
    """4. anchor > 0.5, index > 0.5, anchor > index → anchor_up_outperform"""

    def test_basic(self):
        bucket = classify_decomposition_bucket(3.0, 1.5, 1.5)
        assert bucket == "anchor_up_outperform"

    def test_zero_excess(self):
        # excess = 0 → positive side
        bucket = classify_decomposition_bucket(1.0, 1.0, 0.0)
        assert bucket in POSITIVE_BUCKETS


class TestUsableFiltering:
    """5. usable 筛选排除 insufficient_data 和 no_future_label"""

    def test_insufficient_data_excluded(self):
        sig = _make_synthetic_signal()
        lab = _make_synthetic_labels()
        daily = compute_decomposition_daily(sig, lab)
        if daily.empty:
            pytest.skip("No valid rows in synthetic data")
        # No insufficient_data in signal_quality_status
        assert not (daily["signal_quality_status"].isin(EXCLUDED_STATUSES)).any()
        # No no_future_label in label_quality_status
        assert not (daily["label_quality_status"].isin(EXCLUDED_STATUSES)).any()


class TestAsofGradeZeroExcluded:
    """6. asof_grade=0 排除：insufficient_grade_history 行不进入统计"""

    def test_no_grade_zero(self):
        sig = _make_synthetic_signal()
        lab = _make_synthetic_labels()
        daily = compute_decomposition_daily(sig, lab)
        if daily.empty:
            pytest.skip("No valid rows in synthetic data")
        assert (daily["grade"] > 0).all()


class TestProfileSampleCountMatchesDaily:
    """7. profile sample_count 求和 = daily 有效行数（按 signal_window, grade, holding_window, evaluation_mode）"""

    def test_all_signals(self):
        sig = _make_synthetic_signal()
        lab = _make_synthetic_labels()
        daily = compute_decomposition_daily(sig, lab)
        if daily.empty:
            pytest.skip("No valid rows in synthetic data")
        profile = compute_decomposition_profile(daily)

        all_sig_profile = profile[profile["evaluation_mode"] == "all_signals"]
        for (sw, grade, hw), group in all_sig_profile.groupby(["signal_window", "grade", "holding_window"]):
            daily_count = len(daily[
                (daily["signal_window"] == sw)
                & (daily["grade"] == grade)
                & (daily["holding_window"] == hw)
            ])
            profile_count = group["sample_count"].sum()
            assert profile_count == daily_count, \
                f"sw={sw} grade={grade} hw={hw}: profile={profile_count} vs daily={daily_count}"


class TestIndustryChainOnly:
    """8. 输出只含 industry_chain_index"""

    def test_no_other_index(self):
        sig = _make_synthetic_signal()
        lab = _make_synthetic_labels()
        daily = compute_decomposition_daily(sig, lab)
        if daily.empty:
            pytest.skip("No valid rows in synthetic data")
        assert (daily["index_id"] == TARGET_INDEX_ID).all()


class TestDenominatorConsistency:
    """9. 分母一致性：negative bucket 求和 = negative_excess_count 等"""

    def test_consistency(self):
        sig = _make_synthetic_signal()
        lab = _make_synthetic_labels()
        daily = compute_decomposition_daily(sig, lab)
        if daily.empty:
            pytest.skip("No valid rows in synthetic data")
        profile = compute_decomposition_profile(daily)

        for _, row in profile.iterrows():
            neg_bucket_sum = sum(row[f"{b}_count"] for b in NEGATIVE_BUCKETS)
            pos_bucket_sum = sum(row[f"{b}_count"] for b in POSITIVE_BUCKETS)

            assert neg_bucket_sum == row["negative_excess_count"], \
                f"Negative bucket sum {neg_bucket_sum} != negative_excess_count {row['negative_excess_count']}"
            assert pos_bucket_sum == row["positive_excess_count"], \
                f"Positive bucket sum {pos_bucket_sum} != positive_excess_count {row['positive_excess_count']}"
            assert neg_bucket_sum + pos_bucket_sum == row["sample_count"], \
                f"neg+pos {neg_bucket_sum + pos_bucket_sum} != sample_count {row['sample_count']}"


class TestNonOverlappingInterval:
    """10. is_non_overlapping=True 的行，同组内相邻日期间隔 ≥ H 个交易日"""

    def test_interval(self):
        sig = _make_synthetic_signal()
        lab = _make_synthetic_labels()
        daily = compute_decomposition_daily(sig, lab)
        if daily.empty:
            pytest.skip("No valid rows in synthetic data")

        all_dates = np.sort(daily["date"].unique())

        for (sw, grade, hw), group in daily[
            daily["is_non_overlapping"]
        ].groupby(["signal_window", "grade", "holding_window"]):
            dates = group["date"].sort_values().values
            for i in range(1, len(dates)):
                diff = _trading_day_diff(dates[i - 1], dates[i], all_dates)
                assert diff >= hw, \
                    f"sw={sw} grade={grade} hw={hw}: {dates[i-1]}→{dates[i]} diff={diff} < {hw}"


class TestDualRateCorrectness:
    """11. 双口径比率：rate_in_all = count / sample_count; rate_in_negative = count / negative_excess_count"""

    def test_rates(self):
        sig = _make_synthetic_signal()
        lab = _make_synthetic_labels()
        daily = compute_decomposition_daily(sig, lab)
        if daily.empty:
            pytest.skip("No valid rows in synthetic data")
        profile = compute_decomposition_profile(daily)

        for _, row in profile.iterrows():
            n = row["sample_count"]
            neg_n = row["negative_excess_count"]
            pos_n = row["positive_excess_count"]

            for b in NEGATIVE_BUCKETS:
                bc = row[f"{b}_count"]
                assert abs(row[f"{b}_rate_in_all"] - bc / n) < 1e-10, \
                    f"{b}_rate_in_all mismatch"
                if neg_n > 0:
                    assert abs(row[f"{b}_rate_in_negative"] - bc / neg_n) < 1e-10, \
                        f"{b}_rate_in_negative mismatch"
                else:
                    assert row[f"{b}_rate_in_negative"] == 0.0

            for b in POSITIVE_BUCKETS:
                bc = row[f"{b}_count"]
                assert abs(row[f"{b}_rate_in_all"] - bc / n) < 1e-10, \
                    f"{b}_rate_in_all mismatch"
                if pos_n > 0:
                    assert abs(row[f"{b}_rate_in_positive"] - bc / pos_n) < 1e-10, \
                        f"{b}_rate_in_positive mismatch"
                else:
                    assert row[f"{b}_rate_in_positive"] == 0.0
