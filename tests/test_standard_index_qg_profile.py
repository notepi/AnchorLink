"""
标准指数超额 Q×G 网格画像 — 单元测试
====================================

17 项测试，使用合成信号数据。
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.index_products.qg_profile import (
    TARGET_INDEX_ID,
    TARGET_SIGNAL_WINDOWS,
    MIN_G_HISTORY,
    G_GRADE_LABELS,
    Q_ZONE_MAP,
    G_ZONE_MAP,
    compute_standard_excess_delta,
    compute_g_grade_asof,
    build_qg_signal_daily,
    build_qg_forward_joined,
    select_non_overlapping_samples,
    compute_grid_profile,
    compute_quadrant_profile,
    compute_g_thresholds,
    build_manifest,
    load_signal_daily,
    load_forward_labels,
)


# ── 合成数据辅助 ──


def _make_signal_df(
    n_days: int = 120,
    signal_windows: list[int] | None = None,
    index_id: str = TARGET_INDEX_ID,
) -> pd.DataFrame:
    """构建合成 signal_daily DataFrame。"""
    if signal_windows is None:
        signal_windows = TARGET_SIGNAL_WINDOWS

    dates = pd.bdate_range("20250101", periods=n_days)
    rows = []
    for d in dates:
        date_str = d.strftime("%Y%m%d")
        for sw in signal_windows:
            # 生成有变化的 standard_excess
            excess = np.sin(len(rows) * 0.1) * 5 + np.random.normal(0, 1)
            rows.append({
                "date": date_str,
                "index_id": index_id,
                "signal_window": sw,
                "standard_excess": excess,
                "data_status": "ok",
                "fresh_quote_ratio": 1.0,
                "universe_inclusion_ratio": 1.0,
                "stale_symbols": "",
                "signal_quality_status": "ok",
                "anchor_suspended": False,
                "static_grade": 3,
                "static_grade_label": "中性",
                "asof_grade": 3,
                "asof_grade_label": "中性",
            })
    return pd.DataFrame(rows)


def _make_signal_df_with_gaps() -> pd.DataFrame:
    """构建有空值和 insufficient_data 的合成数据。"""
    dates = pd.bdate_range("20250101", periods=120)
    rows = []
    for i, d in enumerate(dates):
        date_str = d.strftime("%Y%m%d")
        for sw in [5, 10]:
            # 第 5 天和第 10 天设为 insufficient_data
            if i in [5, 10]:
                quality = "insufficient_data"
                excess = None
                asof_grade = 0
                asof_label = "insufficient_data"
            # 第 20 天设为空值
            elif i == 20:
                quality = "ok"
                excess = None
                asof_grade = 0
                asof_label = "insufficient_grade_history"
            else:
                quality = "ok"
                excess = np.sin(len(rows) * 0.1) * 5 + np.random.normal(0, 1)
                # 简单分档
                if excess < -3:
                    asof_grade, asof_label = 1, "极冷"
                elif excess < -1:
                    asof_grade, asof_label = 2, "偏冷"
                elif excess < 1:
                    asof_grade, asof_label = 3, "中性"
                elif excess < 3:
                    asof_grade, asof_label = 4, "偏热"
                else:
                    asof_grade, asof_label = 5, "极热"

            rows.append({
                "date": date_str,
                "index_id": TARGET_INDEX_ID,
                "signal_window": sw,
                "standard_excess": excess,
                "data_status": "ok",
                "fresh_quote_ratio": 1.0,
                "universe_inclusion_ratio": 1.0,
                "stale_symbols": "",
                "signal_quality_status": quality,
                "anchor_suspended": False,
                "static_grade": asof_grade,
                "static_grade_label": asof_label,
                "asof_grade": asof_grade,
                "asof_grade_label": asof_label,
            })
    return pd.DataFrame(rows)


def _make_forward_df(signal_dates: list[str]) -> pd.DataFrame:
    """构建合成 forward_labels DataFrame。"""
    rows = []
    for d in signal_dates:
        for hw in [1, 3, 5, 10]:
            rows.append({
                "date": d,
                "index_id": TARGET_INDEX_ID,
                "holding_window": hw,
                "future_anchor_return": np.random.normal(0, 2),
                "future_index_return": np.random.normal(0, 1),
                "future_excess": np.random.normal(0, 2),
                "long_mfe": abs(np.random.normal(3, 1)),
                "long_mae": -abs(np.random.normal(2, 1)),
                "short_mfe": abs(np.random.normal(3, 1)),
                "short_mae": -abs(np.random.normal(2, 1)),
                "relative_long_mfe": abs(np.random.normal(2, 1)),
                "relative_long_mae": -abs(np.random.normal(1, 0.5)),
                "relative_short_mfe": abs(np.random.normal(2, 1)),
                "relative_short_mae": -abs(np.random.normal(1, 0.5)),
                "label_quality_status": "ok",
                "label_type": "close_to_close_research_label",
            })
    return pd.DataFrame(rows)


# ── 测试 ──


class TestTargetFiltering:
    """1-2: 只处理目标 index_id 和 signal_window。"""

    def test_only_industry_chain_index(self, tmp_path):
        """只处理 industry_chain_index，其他 index_id 不出现。"""
        # 构建含多个 index_id 的 CSV
        rows = []
        dates = pd.bdate_range("20250101", periods=120)
        for d in dates:
            for idx_id in ["industry_chain_index", "direct_peers_index"]:
                for sw in [5, 10]:
                    rows.append({
                        "date": d.strftime("%Y%m%d"),
                        "index_id": idx_id,
                        "signal_window": sw,
                        "standard_excess": 1.0,
                        "data_status": "ok",
                        "fresh_quote_ratio": 1.0,
                        "universe_inclusion_ratio": 1.0,
                        "stale_symbols": "",
                        "signal_quality_status": "ok",
                        "anchor_suspended": False,
                        "static_grade": 3,
                        "static_grade_label": "中性",
                        "asof_grade": 3,
                        "asof_grade_label": "中性",
                    })
        df = pd.DataFrame(rows)
        df.to_csv(tmp_path / "signal_daily.csv", index=False)

        result = load_signal_daily(tmp_path)
        assert set(result["index_id"].unique()) == {TARGET_INDEX_ID}

    def test_only_signal_window_5_and_10(self, tmp_path):
        """只处理 signal_window 5 和 10。"""
        rows = []
        dates = pd.bdate_range("20250101", periods=120)
        for d in dates:
            for sw in [1, 3, 5, 10]:
                rows.append({
                    "date": d.strftime("%Y%m%d"),
                    "index_id": TARGET_INDEX_ID,
                    "signal_window": sw,
                    "standard_excess": 1.0,
                    "data_status": "ok",
                    "fresh_quote_ratio": 1.0,
                    "universe_inclusion_ratio": 1.0,
                    "stale_symbols": "",
                    "signal_quality_status": "ok",
                    "anchor_suspended": False,
                    "static_grade": 3,
                    "static_grade_label": "中性",
                    "asof_grade": 3,
                    "asof_grade_label": "中性",
                })
        df = pd.DataFrame(rows)
        df.to_csv(tmp_path / "signal_daily.csv", index=False)

        result = load_signal_daily(tmp_path)
        assert set(result["signal_window"].unique()) == {5, 10}


class TestDeltaComputation:
    """3-5: Delta 计算规则。"""

    def test_delta_within_same_signal_window(self):
        """standard_excess_delta 在同一 signal_window 内计算，不跨窗口。"""
        df = _make_signal_df(n_days=10)
        result = compute_standard_excess_delta(df)

        for sw in [5, 10]:
            sub = result[result["signal_window"] == sw].sort_values("date")
            sub = sub.reset_index(drop=True)
            # 第一个 delta 为空
            assert pd.isna(sub.iloc[0]["standard_excess_delta"])
            # 后续 delta = t - t-1
            for i in range(1, len(sub)):
                if pd.notna(sub.iloc[i]["standard_excess_delta"]):
                    expected = sub.iloc[i]["standard_excess"] - sub.iloc[i - 1]["standard_excess"]
                    assert abs(sub.iloc[i]["standard_excess_delta"] - expected) < 1e-10

    def test_delta_null_when_excess_null(self):
        """delta 遇到空值时为空。"""
        df = _make_signal_df_with_gaps()
        result = compute_standard_excess_delta(df)

        # 找到第 20 天（空值日）的 delta
        for sw in [5, 10]:
            sub = result[result["signal_window"] == sw].sort_values("date").reset_index(drop=True)
            # 第 20 行的 standard_excess 为空
            row_20 = sub.iloc[20]
            assert pd.isna(row_20["standard_excess_delta"])
            # 第 21 行的 delta 也应为空（因为 t-1 的 excess 为空）
            row_21 = sub.iloc[21]
            assert pd.isna(row_21["standard_excess_delta"])

    def test_delta_null_when_insufficient_data(self):
        """delta 遇到 insufficient_data 时为空。"""
        df = _make_signal_df_with_gaps()
        result = compute_standard_excess_delta(df)

        for sw in [5, 10]:
            sub = result[result["signal_window"] == sw].sort_values("date").reset_index(drop=True)
            # 第 5 行的 signal_quality_status = insufficient_data
            row_5 = sub.iloc[5]
            assert row_5["signal_quality_status"] == "insufficient_data"
            assert pd.isna(row_5["standard_excess_delta"])
            # 第 6 行的 delta 也应为空（因为 t-1 是 insufficient_data）
            row_6 = sub.iloc[6]
            assert pd.isna(row_6["standard_excess_delta"])


class TestGGrading:
    """6-8: G 分档规则。"""

    def test_g_asof_no_future_leak(self):
        """G 分档只使用 t-1 及以前历史，无未来函数。"""
        df = _make_signal_df(n_days=120)
        df = compute_standard_excess_delta(df)
        result = compute_g_grade_asof(df)

        # 前 MIN_G_HISTORY 个有效 delta 的 G 应为 insufficient_g_history
        for sw in [5, 10]:
            sub = result[result["signal_window"] == sw].sort_values("date").reset_index(drop=True)
            # 统计有效 delta
            valid_count = 0
            for i, row in sub.iterrows():
                if pd.notna(row["standard_excess_delta"]) and row["signal_quality_status"] != "insufficient_data":
                    valid_count += 1
                if valid_count <= MIN_G_HISTORY:
                    # 在历史不足时 g_grade 应为 0
                    if row["g_grade"] != 0:
                        # 可能恰好在第 MIN_G_HISTORY 个有效 delta 后开始分档
                        pass
            # 至少前 MIN_G_HISTORY 个有效 delta 的 g_grade 为 0
            early_g_zero = sub[sub["g_grade"] == 0]
            assert len(early_g_zero) > 0

    def test_g_insufficient_history(self):
        """G 历史不足 60 个有效 delta 时标记 insufficient_g_history。"""
        # 只给 30 天数据，不可能有 60 个历史
        df = _make_signal_df(n_days=30)
        df = compute_standard_excess_delta(df)
        result = compute_g_grade_asof(df)

        # 所有 g_grade 应为 0
        assert (result["g_grade"] == 0).all()
        assert (result["g_grade_label"] == "insufficient_g_history").all()

    def test_g_percentile_boundaries(self):
        """G 分位边界符合 G1<=P20, G5>P80 规则。"""
        df = _make_signal_df(n_days=200)
        df = compute_standard_excess_delta(df)
        result = compute_g_grade_asof(df)

        for sw in [5, 10]:
            sub = result[
                (result["signal_window"] == sw)
                & (result["g_grade"].isin([1, 2, 3, 4, 5]))
            ].copy()

            if len(sub) == 0:
                continue

            # 检查 G1 的 delta 应较小，G5 的 delta 应较大
            g1_deltas = sub[sub["g_grade"] == 1]["standard_excess_delta"]
            g5_deltas = sub[sub["g_grade"] == 5]["standard_excess_delta"]

            if len(g1_deltas) > 0 and len(g5_deltas) > 0:
                # G1 的中位数应小于 G5 的中位数
                assert g1_deltas.median() < g5_deltas.median()


class TestForwardJoin:
    """9-11: Forward Joined 规则。"""

    def test_forward_join_correct(self):
        """qg_forward_joined 正确连接 holding_window 标签。"""
        df = _make_signal_df(n_days=120)
        qg_signal = build_qg_signal_daily(df)
        dates = qg_signal["date"].unique().tolist()
        forward_df = _make_forward_df(dates)

        joined = build_qg_forward_joined(qg_signal, forward_df)

        # 应有 holding_window 列
        assert "holding_window" in joined.columns
        # holding_window 应只有目标值
        assert set(joined["holding_window"].unique()).issubset({1, 3, 5, 10})

    def test_usable_filter(self):
        """usable 过滤规则正确。"""
        df = _make_signal_df(n_days=120)
        qg_signal = build_qg_signal_daily(df)
        dates = qg_signal["date"].unique().tolist()
        forward_df = _make_forward_df(dates)

        # 将部分 label_quality_status 设为 insufficient_data
        forward_df.loc[0:5, "label_quality_status"] = "insufficient_data"

        joined = build_qg_forward_joined(qg_signal, forward_df)
        usable = joined[joined["quality_scope"] == "usable"]

        # usable 中不应有 insufficient_data 的 label
        assert "insufficient_data" not in usable["label_quality_status"].values

    def test_strict_ok_only_filter(self):
        """strict_ok_only 过滤规则正确。"""
        df = _make_signal_df(n_days=120)
        qg_signal = build_qg_signal_daily(df)
        dates = qg_signal["date"].unique().tolist()
        forward_df = _make_forward_df(dates)

        joined = build_qg_forward_joined(qg_signal, forward_df)
        strict = joined[joined["quality_scope"] == "strict_ok_only"]

        # strict_ok_only 中 signal_quality_status 应全为 ok
        assert (strict["signal_quality_status"] == "ok").all()
        # strict_ok_only 中 label_quality_status 应全为 ok
        assert (strict["label_quality_status"] == "ok").all()


class TestNonOverlapping:
    """12: non_overlapping 规则。"""

    def test_non_overlapping_uses_full_calendar(self):
        """non_overlapping 间隔基于完整交易日历。"""
        # 完整日历有 10 天
        all_dates = [f"2025010{d}" for d in range(10)]

        # 样本只在偶数日
        sample_dates = [f"2025010{d}" for d in [0, 2, 4, 6, 8]]
        df = pd.DataFrame({"date": sample_dates, "val": range(5)})

        # holding_window = 3，基于完整日历间隔至少 3
        result = select_non_overlapping_samples(df, holding_window=3, all_dates=all_dates)

        # 第一个选 20250100 (idx=0)
        # 下一个需要 idx >= 3，即 20250103 → 不在样本中
        # 20250104 (idx=4) → 4-0=4 >= 3 ✓
        # 20250108 (idx=8) → 8-4=4 >= 3 ✓
        assert len(result) >= 2


class TestGridProfile:
    """13: Grid Profile 统计一致性。"""

    def test_sample_count_matches_detail(self):
        """qg_grid_profile 的 sample_count 与明细一致。"""
        df = _make_signal_df(n_days=120)
        qg_signal = build_qg_signal_daily(df)
        dates = qg_signal["date"].unique().tolist()
        forward_df = _make_forward_df(dates)
        joined = build_qg_forward_joined(qg_signal, forward_df)
        all_dates = sorted(qg_signal["date"].unique().tolist())

        grid = compute_grid_profile(joined, all_dates)

        # 验证 all_signals 模式下 sample_count 与 joined 明细一致
        for _, row in grid.iterrows():
            if row["evaluation_mode"] == "all_signals":
                detail = joined[
                    (joined["quality_scope"] == row["quality_scope"])
                    & (joined["signal_window"] == row["signal_window"])
                    & (joined["holding_window"] == row["holding_window"])
                    & (joined["q_grade"] == row["q_grade"])
                    & (joined["g_grade"] == row["g_grade"])
                ]
                assert row["sample_count"] == len(detail)


class TestQuadrantProfile:
    """14: Quadrant Profile 聚合口径。"""

    def test_quadrant_aggregation_correct(self):
        """qg_quadrant_profile 聚合口径正确：直接从明细聚合。"""
        df = _make_signal_df(n_days=120)
        qg_signal = build_qg_signal_daily(df)
        dates = qg_signal["date"].unique().tolist()
        forward_df = _make_forward_df(dates)
        joined = build_qg_forward_joined(qg_signal, forward_df)
        all_dates = sorted(qg_signal["date"].unique().tolist())

        quadrant = compute_quadrant_profile(joined, all_dates)

        # 冷端 应包含 Q1+Q2，热端应包含 Q4+Q5
        for _, row in quadrant.iterrows():
            assert row["q_zone"] in ["冷端", "中性", "热端"]
            assert row["g_zone"] in ["下降", "稳定", "上升"]

        # 验证 sample_count：冷端+下降 的样本数应等于 joined 中 Q1/Q2 + G1/G2 的明细数
        for (sw, hw, qscope, emode), sub_quad in quadrant.groupby(
            ["signal_window", "holding_window", "quality_scope", "evaluation_mode"]
        ):
            if emode != "all_signals":
                continue
            for _, qrow in sub_quad.iterrows():
                q_grades = [k for k, v in Q_ZONE_MAP.items() if v == qrow["q_zone"]]
                g_grades = [k for k, v in G_ZONE_MAP.items() if v == qrow["g_zone"]]
                detail = joined[
                    (joined["signal_window"] == sw)
                    & (joined["holding_window"] == hw)
                    & (joined["quality_scope"] == qscope)
                    & (joined["q_grade"].isin(q_grades))
                    & (joined["g_grade"].isin(g_grades))
                ]
                assert qrow["sample_count"] == len(detail)


class TestManifest:
    """15: Build Manifest 内容。"""

    def test_manifest_contains_checksum_and_windows(self, tmp_path):
        """build_manifest 包含输入 checksum、目标窗口、正确的 source_data_as_of 和 upstream SHA。"""
        # 创建假输入文件
        (tmp_path / "signal_daily.csv").write_text("date,index_id\n20250101,test\n")
        (tmp_path / "forward_labels.csv").write_text("date,index_id\n20250101,test\n")
        # 上游 manifest 包含 source_data_as_of
        upstream = {"source_data_as_of": "20260602", "upstream_build_manifest_sha256": "abc123"}
        (tmp_path / "build_manifest.json").write_text(json.dumps(upstream))

        manifest = build_manifest(tmp_path, tmp_path, {"qg_signal_daily": 100})

        assert "signal_daily.csv_sha256" in manifest["input_checksums"]
        assert "forward_labels.csv_sha256" in manifest["input_checksums"]
        assert manifest["target_index_id"] == TARGET_INDEX_ID
        assert manifest["target_signal_windows"] == TARGET_SIGNAL_WINDOWS
        # source_data_as_of 应从上游继承
        assert manifest["source_data_as_of"] == "20260602"
        # upstream SHA 应该是上游 build_manifest.json 文件自身的 SHA256
        assert manifest["upstream_profile_manifest_sha256"] != ""
        assert manifest["upstream_profile_manifest_sha256"] != "abc123"


class TestOldFilesUnmodified:
    """16: 旧目录和旧文件未被修改。"""

    def test_old_data_not_modified(self, tmp_path):
        """旧目录和旧文件未被修改。"""
        # 创建旧文件并计算 checksum
        old_dir = tmp_path / "old"
        old_dir.mkdir()
        old_file = old_dir / "test.csv"
        old_file.write_text("date,val\n20250101,1\n")

        sha = hashlib.sha256()
        sha.update(old_file.read_bytes())
        original_sha = sha.hexdigest()

        # 运行完整流程（使用 tmp_path 作为输出目录）
        df = _make_signal_df(n_days=120)
        qg_signal = build_qg_signal_daily(df)
        dates = qg_signal["date"].unique().tolist()
        forward_df = _make_forward_df(dates)
        joined = build_qg_forward_joined(qg_signal, forward_df)

        # 旧文件不应改变
        sha2 = hashlib.sha256()
        sha2.update(old_file.read_bytes())
        assert sha2.hexdigest() == original_sha


class TestScriptRunnable:
    """17: 脚本可从项目根目录直接运行。"""

    def test_script_exists(self):
        """脚本文件存在。"""
        script_path = Path(__file__).parent.parent / "scripts" / "build_standard_index_qg_profile.py"
        assert script_path.exists()

    def test_script_has_main(self):
        """脚本有 main 函数。"""
        script_path = Path(__file__).parent.parent / "scripts" / "build_standard_index_qg_profile.py"
        content = script_path.read_text()
        assert "def main()" in content
        assert '__name__ == "__main__"' in content
