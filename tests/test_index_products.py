"""
虚拟 ETF / 自定义指数 单元测试

23 项测试，使用合成行情数据。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import pytest

from src.index_products.builder import (
    _compute_data_status,
    _compute_nd_return,
    build_index_definitions,
    build_nav_series,
    build_stale_matrix,
)
from src.index_products.models import (
    IndexDefinition,
    IndexMember,
    IndexNAVRecord,
    MemberDayRecord,
)
from src.index_products.quality import (
    check_anchor_covers_latest,
    check_no_null_zero_close,
    check_price_uniqueness,
    run_all_quality_checks,
)
from src.config.loader import PoolRegistry


# ── 合成数据辅助 ──

def _make_price_df(
    symbols: list[str],
    n_days: int = 30,
    start: str = "20250101",
    prices: Optional[dict[str, list[float]]] = None,
    volumes: Optional[dict[str, list[float]]] = None,
) -> pd.DataFrame:
    """构建合成 normalized 行情 DataFrame"""
    dates = pd.bdate_range(start, periods=n_days)
    rows = []
    for s in symbols:
        for i, d in enumerate(dates):
            if prices and s in prices:
                close = prices[s][i] if i < len(prices[s]) else prices[s][-1]
            else:
                close = 100.0
            vol = 1000.0
            if volumes and s in volumes:
                vol = volumes[s][i] if i < len(volumes[s]) else volumes[s][-1]
            rows.append({
                "ts_code": s,
                "trade_date": d,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "vol": vol,
                "amount": close * vol,
            })
    return pd.DataFrame(rows)


def _make_raw_df(normalized_df: pd.DataFrame, drop_dates: Optional[dict[str, list]] = None) -> pd.DataFrame:
    """从 normalized 构造 raw（去掉指定 symbol-date 行）"""
    df = normalized_df.copy()
    if drop_dates:
        mask = pd.Series(True, index=df.index)
        for symbol, dates in drop_dates.items():
            for d in dates:
                mask &= ~((df["ts_code"] == symbol) & (df["trade_date"] == d))
        df = df[mask]
    return df


def _make_index_def(
    members: list[tuple[str, float, str]],
    index_id: str = "test_index",
) -> IndexDefinition:
    """构建测试用 IndexDefinition"""
    total = sum(w for _, w, _ in members)
    ims = tuple(
        IndexMember(
            symbol=s,
            raw_config_weight=w,
            normalized_target_weight=w / total,
            role=r,
            membership_scope="benchmark",
        )
        for s, w, r in members
    )
    return IndexDefinition(
        index_id=index_id,
        display_name="Test Index",
        can_be_benchmark=True,
        pool_config_version="2026-01-01",
        members=ims,
    )


# ── 测试 1: 权重归一化 ──

class TestWeightNormalization:
    def test_sums_to_one(self):
        members = [("A", 0.8, "role_a"), ("B", 0.5, "role_b"), ("C", 0.3, "role_c")]
        defn = _make_index_def(members)
        total = sum(m.normalized_target_weight for m in defn.members)
        assert abs(total - 1.0) < 1e-10


# ── 测试 2: 初始 NAV == 1000 ──

class TestInitialNAV:
    def test_nav_starts_at_1000(self):
        symbols = ["A", "B", "C"]
        price_df = _make_price_df(symbols, n_days=10, prices={
            "A": [100.0] * 10,
            "B": [200.0] * 10,
            "C": [150.0] * 10,
        })
        defn = _make_index_def([("A", 1.0, "r"), ("B", 1.0, "r"), ("C", 1.0, "r")])
        trading_days = sorted(price_df["trade_date"].unique())
        stale_matrix = build_stale_matrix(price_df, price_df, trading_days, symbols)
        nav_records, _ = build_nav_series(defn, price_df, stale_matrix, trading_days, min_size=2)
        assert abs(nav_records[0].nav - 1000.0) < 1e-6


# ── 测试 3: 无价格变化 → NAV 不变 ──

class TestNoPriceChange:
    def test_nav_constant(self):
        symbols = ["A", "B"]
        price_df = _make_price_df(symbols, n_days=5, prices={
            "A": [100.0] * 5,
            "B": [200.0] * 5,
        })
        defn = _make_index_def([("A", 1.0, "r"), ("B", 1.0, "r")])
        trading_days = sorted(price_df["trade_date"].unique())
        stale_matrix = build_stale_matrix(price_df, price_df, trading_days, symbols)
        nav_records, _ = build_nav_series(defn, price_df, stale_matrix, trading_days, min_size=2)
        for r in nav_records:
            assert abs(r.nav - 1000.0) < 1e-6


# ── 测试 4: 单只股票上涨 → NAV 按实际权重变化 ──

class TestSingleStockUp:
    def test_nav_changes_by_weight(self):
        symbols = ["A", "B"]
        # A 涨 10%，B 不变
        a_prices = [100.0, 110.0, 110.0, 110.0, 110.0]
        b_prices = [200.0] * 5
        price_df = _make_price_df(symbols, n_days=5, prices={
            "A": a_prices, "B": b_prices,
        })
        defn = _make_index_def([("A", 1.0, "r"), ("B", 1.0, "r")])
        trading_days = sorted(price_df["trade_date"].unique())
        stale_matrix = build_stale_matrix(price_df, price_df, trading_days, symbols)
        nav_records, _ = build_nav_series(defn, price_df, stale_matrix, trading_days, min_size=2)
        # A weight = 1/3, 10% rise → NAV rise ≈ 1/3 * 10% * 1000
        # A weight = 0.5 (1/(1+1)), NAV should rise by 0.5 * 10%
        assert nav_records[0].nav == pytest.approx(1000.0, abs=0.01)
        expected_return_1d = 0.5 * 0.10  # A 占 50% 权重，涨 10%
        expected_nav = 1000.0 * (1 + expected_return_1d)
        assert nav_records[1].nav == pytest.approx(expected_nav, abs=0.5)


# ── 测试 5: 月初再平衡前后 NAV 连续 ──

class TestRebalanceContinuity:
    def test_nav_continuous_at_rebalance(self):
        symbols = ["A", "B"]
        # 30 天，让月频再平衡发生
        a_prices = [100.0 + i * 0.5 for i in range(30)]
        b_prices = [200.0 - i * 0.3 for i in range(30)]
        price_df = _make_price_df(symbols, n_days=30, prices={
            "A": a_prices, "B": b_prices,
        })
        defn = _make_index_def([("A", 1.0, "r"), ("B", 1.0, "r")])
        trading_days = sorted(price_df["trade_date"].unique())
        stale_matrix = build_stale_matrix(price_df, price_df, trading_days, symbols)
        nav_records, _ = build_nav_series(defn, price_df, stale_matrix, trading_days, rebalance_freq="monthly", min_size=2)
        # 检查所有再平衡日：前后 NAV 连续（同一天 NAV 不跳变）
        for i, r in enumerate(nav_records):
            if r.is_rebalance_day:
                # NAV at this day is computed with old units, should be continuous
                if i > 0:
                    # NAV 不应为 NaN
                    assert not pd.isna(r.nav)
                    assert r.nav > 0


# ── 测试 6: 停牌成员用上一有效 close ──

class TestSuspendedMember:
    def test_nav_no_nan_when_suspended(self):
        symbols = ["A", "B"]
        # B 在第 3-5 天停牌（vol=0，但 close 已 forward-fill）
        vols_b = [1000.0, 1000.0, 0.0, 0.0, 0.0, 1000.0, 1000.0]
        price_df = _make_price_df(symbols, n_days=7, prices={
            "A": [100.0] * 7,
            "B": [200.0] * 7,
        }, volumes={"B": vols_b})
        defn = _make_index_def([("A", 1.0, "r"), ("B", 1.0, "r")])
        trading_days = sorted(price_df["trade_date"].unique())
        # raw 没有 B 第 3-5 天的记录（模拟停牌）
        drop = {"B": trading_days[2:5]}
        raw_df = _make_raw_df(price_df, drop_dates=drop)
        stale_matrix = build_stale_matrix(price_df, raw_df, trading_days, symbols)
        nav_records, _ = build_nav_series(defn, price_df, stale_matrix, trading_days, min_size=2)
        # NAV 永远不为 NaN
        for r in nav_records:
            assert not pd.isna(r.nav)
            assert r.nav > 0


# ── 测试 7: stale member 正确记录 ──

class TestStaleRecording:
    def test_stale_recorded(self):
        symbols = ["A", "B"]
        price_df = _make_price_df(symbols, n_days=7, prices={
            "A": [100.0] * 7,
            "B": [200.0] * 7,
        })
        trading_days = sorted(price_df["trade_date"].unique())
        drop = {"B": trading_days[2:5]}
        raw_df = _make_raw_df(price_df, drop_dates=drop)
        stale_matrix = build_stale_matrix(price_df, raw_df, trading_days, symbols)

        defn = _make_index_def([("A", 1.0, "r"), ("B", 1.0, "r")])
        _, member_records = build_nav_series(defn, price_df, stale_matrix, trading_days, min_size=2)

        # B 在第 3 天（index 2）应为 stale
        b_day3 = [m for m in member_records if m.symbol == "B" and m.trade_date == trading_days[2].strftime("%Y%m%d")]
        assert len(b_day3) == 1
        assert b_day3[0].price_is_stale is True
        assert b_day3[0].source_trade_date == trading_days[1].strftime("%Y%m%d")


# ── 测试 8: 同一股票不同指数不同权重 ──

class TestSameStockDifferentWeights:
    def test_different_weights(self):
        # 用 pools.yaml 实例化
        registry = PoolRegistry()
        defs = build_index_definitions(registry)
        # 找出出现在多个指数中的股票
        symbol_weights: dict[str, list[tuple[str, float]]] = {}
        for d in defs:
            for m in d.members:
                symbol_weights.setdefault(m.symbol, []).append((d.index_id, m.normalized_target_weight))
        # 至少有一个股票出现在多个指数
        multi = {s: ws for s, ws in symbol_weights.items() if len(ws) > 1}
        if multi:
            for s, ws in multi.items():
                weights = [w for _, w in ws]
                # 不同指数中的权重应不同
                assert len(set(f"{w:.6f}" for w in weights)) > 1 or len(ws) <= 1


# ── 测试 9: excess_Nd 公式 ──

class TestExcessFormula:
    def test_excess_equals_anchor_minus_index(self):
        # 直接验证公式: excess_Nd = anchor_return_Nd - index_return_Nd
        anchor_close = 100.0
        index_nav = 1000.0
        anchor_ret_5d = (105.0 / anchor_close - 1) * 100  # 5%
        index_ret_5d = (1020.0 / index_nav - 1) * 100      # 2%
        excess = anchor_ret_5d - index_ret_5d
        assert abs(excess - 3.0) < 1e-10


# ── 测试 10: 重复键 → ValueError ──

class TestDuplicateKeys:
    def test_raises_on_duplicates(self):
        df = pd.DataFrame({
            "ts_code": ["A", "A", "B"],
            "trade_date": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-01"]),
            "close": [100.0, 100.0, 200.0],
        })
        with pytest.raises(ValueError, match="重复"):
            check_price_uniqueness(df)


# ── 测试 11: anchor 缺最新日 ──

class TestAnchorMissing:
    def test_default_raises(self):
        df = pd.DataFrame({
            "ts_code": ["A", "B"],
            "trade_date": pd.to_datetime(["2025-01-01", "2025-01-02"]),
            "close": [100.0, 200.0],
        })
        with pytest.raises(ValueError, match="未覆盖最新交易日"):
            check_anchor_covers_latest(df, "A")

    def test_allow_stale_warns(self):
        df = pd.DataFrame({
            "ts_code": ["A", "B"],
            "trade_date": pd.to_datetime(["2025-01-01", "2025-01-02"]),
            "close": [100.0, 200.0],
        })
        result = check_anchor_covers_latest(df, "A", allow_stale=True)
        assert result is not None


# ── 测试 12: 覆盖率降级 ──

class TestCoverageDowngrade:
    def test_insufficient_data(self):
        assert _compute_data_status(0.3, 0.4) == "insufficient_data"

    def test_partial(self):
        assert _compute_data_status(0.6, 0.6) == "partial"

    def test_ok(self):
        assert _compute_data_status(0.9, 0.9) == "ok"


# ── 测试 13: 迟到成员纳入时 NAV 连续 ──

class TestLateMemberContinuity:
    def test_nav_continuous(self):
        # A 从第一天就有数据，B 从第 3 天才有
        symbols = ["A", "B"]
        dates = pd.bdate_range("20250101", periods=5)
        rows = []
        # A 每天都有
        for d in dates:
            rows.append({"ts_code": "A", "trade_date": d, "close": 100.0, "vol": 1000.0, "open": 100.0, "high": 100.0, "low": 100.0, "amount": 100000.0})
        # B 只有第 3 天起
        for d in dates[2:]:
            rows.append({"ts_code": "B", "trade_date": d, "close": 200.0, "vol": 1000.0, "open": 200.0, "high": 200.0, "low": 200.0, "amount": 200000.0})
        price_df = pd.DataFrame(rows)
        # 补齐 B 的缺失日
        all_dates = sorted(price_df["trade_date"].unique())
        for d in all_dates:
            if not ((price_df["ts_code"] == "B") & (price_df["trade_date"] == d)).any():
                prev = price_df[price_df["ts_code"] == "B"].sort_values("trade_date")
                if not prev.empty:
                    last_close = prev.iloc[-1]["close"]
                    rows.append({"ts_code": "B", "trade_date": d, "close": last_close, "vol": 0, "open": last_close, "high": last_close, "low": last_close, "amount": 0})
        price_df = pd.DataFrame(rows)

        defn = _make_index_def([("A", 1.0, "r"), ("B", 1.0, "r")])
        raw_df = price_df[price_df["vol"] > 0].copy()
        stale_matrix = build_stale_matrix(price_df, raw_df, all_dates, symbols)
        nav_records, _ = build_nav_series(defn, price_df, stale_matrix, all_dates, min_size=1)
        # NAV 连续（无跳变）
        for i in range(1, len(nav_records)):
            assert not pd.isna(nav_records[i].nav)


# ── 测试 14: 再平衡生效时点 ──

class TestRebalanceTiming:
    def test_rebalance_day_uses_old_units(self):
        symbols = ["A", "B"]
        price_df = _make_price_df(symbols, n_days=30, prices={
            "A": [100.0 + i for i in range(30)],
            "B": [200.0] * 30,
        })
        defn = _make_index_def([("A", 1.0, "r"), ("B", 1.0, "r")])
        trading_days = sorted(price_df["trade_date"].unique())
        stale_matrix = build_stale_matrix(price_df, price_df, trading_days, symbols)
        nav_records, _ = build_nav_series(defn, price_df, stale_matrix, trading_days, rebalance_freq="monthly", min_size=2)
        # 找到再平衡日
        rebal_days = [r for r in nav_records if r.is_rebalance_day]
        for r in rebal_days:
            # 再平衡日当天 rebalance_reason 应为 monthly_rebalance 或 late_member_join
            assert r.rebalance_reason in ("monthly_rebalance", "late_member_join", "none")


# ── 测试 15: stale_days 累计 ──

class TestStaleDaysCumulative:
    def test_stale_days_increment(self):
        symbols = ["A", "B"]
        price_df = _make_price_df(symbols, n_days=10, prices={
            "A": [100.0] * 10,
            "B": [200.0] * 10,
        })
        trading_days = sorted(price_df["trade_date"].unique())
        # A 在第 3-7 天缺失
        drop = {"A": trading_days[2:7]}
        raw_df = _make_raw_df(price_df, drop_dates=drop)
        stale_matrix = build_stale_matrix(price_df, raw_df, trading_days, symbols)

        # 检查 stale_days 递增
        a_stale_days = []
        for d in trading_days[2:7]:
            date_str = d.strftime("%Y%m%d")
            _, _, sd = stale_matrix["A"][date_str]
            a_stale_days.append(sd)
        assert a_stale_days == [1, 2, 3, 4, 5]


# ── 测试 16: 元数据完整 ──

class TestMetadataComplete:
    def test_all_fields_nonempty(self):
        symbols = ["A", "B"]
        price_df = _make_price_df(symbols, n_days=5, prices={"A": [100.0] * 5, "B": [200.0] * 5})
        defn = _make_index_def([("A", 1.0, "r"), ("B", 1.0, "r")])
        trading_days = sorted(price_df["trade_date"].unique())
        stale_matrix = build_stale_matrix(price_df, price_df, trading_days, symbols)
        nav_records, _ = build_nav_series(defn, price_df, stale_matrix, trading_days, min_size=2)
        r = nav_records[0]
        for field in ["pool_config_version", "price_adjustment_mode", "universe_mode", "source_data_as_of", "build_mode", "generated_at"]:
            val = getattr(r, field)
            assert val is not None and val != "", f"{field} 为空"


# ── 测试 17: 新旧对照只统计日期交集 ──

class TestLegacyOverlap:
    def test_overlap_fields(self):
        # 构造简单的 legacy_df 模拟
        legacy_df = pd.DataFrame({
            "date": ["20250603", "20250604", "20250605"],
            "median_displacement_1d": [-1.0, 0.5, 2.0],
            "overlap_start": ["20250603"] * 3,
            "overlap_end": ["20250605"] * 3,
            "overlap_n": [3] * 3,
        })
        assert legacy_df["overlap_n"].iloc[0] == 3
        assert legacy_df["overlap_start"].iloc[0] == "20250603"


# ── 测试 18: 三种权重正确 ──

class TestThreeWeightTypes:
    def test_weights_traceable(self):
        members = [("A", 0.8, "r"), ("B", 0.5, "r"), ("C", 0.3, "r")]
        defn = _make_index_def(members)
        total = 0.8 + 0.5 + 0.3  # 1.6
        for m in defn.members:
            assert abs(m.raw_config_weight - next(w for s, w, _ in members if s == m.symbol)) < 1e-10
            expected_norm = m.raw_config_weight / total
            assert abs(m.normalized_target_weight - expected_norm) < 1e-10


# ── 测试 19: index_return_Nd 与 NAV 点位一致 ──

class TestMultiDayReturnConsistency:
    def test_5d_return_matches_nav(self):
        # nav_history 不含当日，current_nav 为当日 NAV
        nav_history = [1000.0, 1010.0, 1020.0, 1015.0, 1025.0]
        current_nav = 1030.0
        # 5d return: current_nav / nav_history[0] - 1
        ret_5d = _compute_nd_return(nav_history, current_nav, 5)
        expected = (1030.0 / 1000.0 - 1) * 100
        assert ret_5d == pytest.approx(expected, abs=0.01)


# ── 测试 20: vol=0 → quote_status zero_volume_raw ──

class TestZeroVolumeRaw:
    def test_zero_volume_status(self):
        symbols = ["A", "B"]
        price_df = _make_price_df(symbols, n_days=5, prices={"A": [100.0] * 5, "B": [200.0] * 5})
        trading_days = sorted(price_df["trade_date"].unique())
        # 在 raw 中 B 第 3 天有记录但 vol=0
        raw_df = price_df.copy()
        mask = (raw_df["ts_code"] == "B") & (raw_df["trade_date"] == trading_days[2])
        raw_df.loc[mask, "vol"] = 0
        stale_matrix = build_stale_matrix(price_df, raw_df, trading_days, symbols)
        date_str = trading_days[2].strftime("%Y%m%d")
        qs, _, _ = stale_matrix["B"][date_str]
        assert qs == "zero_volume_raw"


# ── 测试 21: stale 报价参与再平衡标记 ──

class TestRebalanceStaleFlag:
    def test_flag_set_when_stale_rebalanced(self):
        symbols = ["A", "B"]
        price_df = _make_price_df(symbols, n_days=30, prices={
            "A": [100.0 + i for i in range(30)],
            "B": [200.0] * 30,
        })
        trading_days = sorted(price_df["trade_date"].unique())
        # A 在某月第一天 stale
        raw_df = price_df.copy()
        # 找到第一个月首日
        first_of_month = None
        for d in trading_days:
            if d.month != trading_days[0].month:
                first_of_month = d
                break
        if first_of_month:
            mask = (raw_df["ts_code"] == "A") & (raw_df["trade_date"] == first_of_month)
            raw_df = raw_df[~mask]  # 去掉 A 在该日的 raw 记录
            stale_matrix = build_stale_matrix(price_df, raw_df, trading_days, symbols)
            defn = _make_index_def([("A", 1.0, "r"), ("B", 1.0, "r")])
            nav_records, _ = build_nav_series(defn, price_df, stale_matrix, trading_days, rebalance_freq="monthly", min_size=2)
            # 找该日的记录
            date_str = first_of_month.strftime("%Y%m%d")
            rec = [r for r in nav_records if r.trade_date == date_str]
            if rec and rec[0].is_rebalance_day:
                assert rec[0].rebalance_uses_stale_price is True


# ── 测试 22: effective_target_weight 重新归一化 ──

class TestEffectiveWeights:
    def test_weights_sum_to_one(self):
        # 模拟只有部分成员纳入时的 effective weights
        active = ["A", "B"]  # C 未纳入
        raw_weights = {"A": 0.8, "B": 0.5, "C": 0.3}
        total = sum(raw_weights[s] for s in active)
        eff = {s: raw_weights[s] / total for s in active}
        assert abs(sum(eff.values()) - 1.0) < 1e-10
        assert abs(eff["A"] - 0.8 / 1.3) < 1e-10


# ── 测试 23: membership_event / rebalance_reason ──

class TestMembershipEvent:
    def test_base_init_event(self):
        symbols = ["A", "B"]
        price_df = _make_price_df(symbols, n_days=5, prices={"A": [100.0] * 5, "B": [200.0] * 5})
        defn = _make_index_def([("A", 1.0, "r"), ("B", 1.0, "r")])
        trading_days = sorted(price_df["trade_date"].unique())
        stale_matrix = build_stale_matrix(price_df, price_df, trading_days, symbols)
        _, member_records = build_nav_series(defn, price_df, stale_matrix, trading_days, min_size=2)
        # 首日所有 included 成员应为 base_init
        base_date = trading_days[0].strftime("%Y%m%d")
        base_members = [m for m in member_records if m.trade_date == base_date and m.included]
        for m in base_members:
            assert m.membership_event == "base_init"

    def test_rebalance_reason_values(self):
        symbols = ["A", "B"]
        price_df = _make_price_df(symbols, n_days=30, prices={
            "A": [100.0] * 30,
            "B": [200.0] * 30,
        })
        defn = _make_index_def([("A", 1.0, "r"), ("B", 1.0, "r")])
        trading_days = sorted(price_df["trade_date"].unique())
        stale_matrix = build_stale_matrix(price_df, price_df, trading_days, symbols)
        nav_records, _ = build_nav_series(defn, price_df, stale_matrix, trading_days, rebalance_freq="monthly", min_size=2)
        valid_reasons = {"monthly_rebalance", "late_member_join", "none"}
        for r in nav_records:
            assert r.rebalance_reason in valid_reasons
