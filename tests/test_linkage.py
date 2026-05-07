"""日线联动分析测试。"""

import pandas as pd

from src.config.loader import Anchor, Instrument, Membership, Universe
from src.linkage import calculate_daily_linkage


def _registry():
    anchor = Anchor("688333.SH", "铂力特", "核心标的", "2026-05-01")
    instruments = {
        "688333.SH": Instrument("688333.SH", "铂力特", "科创板", "SH", []),
        "688270.SH": Instrument("688270.SH", "ST臻镭", "科创板", "SH", []),
        "603267.SH": Instrument("603267.SH", "鸿远电子", "主板", "SH", []),
    }
    universes = {
        "industry_chain": Universe("industry_chain", "商业航天硬科技主池", "", True, 1),
        "trading_watchlist": Universe("trading_watchlist", "交易联动池", "", False, 1),
    }
    memberships = [
        Membership("industry_chain", "688270.SH", "satellite_payload_rf_proxy", 0.6, 0.6, True, True, True, True, "主线代理", "2026-05-01"),
        Membership("trading_watchlist", "603267.SH", "military_electronics_signal", 0.9, 0.8, True, False, True, True, "交易相关", "2026-05-01"),
    ]

    return type("MockRegistry", (), {
        "get_anchor": lambda self: anchor,
        "get_instrument": lambda self, symbol: instruments.get(symbol),
        "get_all_universes": lambda self: list(universes.values()),
        "get_members": lambda self, uid, enabled_only=True: [
            m for m in memberships if m.universe_id == uid and (not enabled_only or m.enabled)
        ],
    })()


def _market_df(days: int = 24) -> pd.DataFrame:
    dates = pd.date_range("2026-04-01", periods=days, freq="B")
    rows = []
    anchor_close = 100.0
    chain_close = 50.0
    trading_close = 30.0

    for i, date in enumerate(dates):
        anchor_close += 1.0 if i % 2 == 0 else -0.4
        chain_close += 1.4 if i % 2 == 0 else -0.5
        trading_close += 0.8 if i % 3 != 0 else -0.2
        rows.extend([
            {"ts_code": "688333.SH", "trade_date": date, "close": anchor_close},
            {"ts_code": "688270.SH", "trade_date": date, "close": chain_close},
            {"ts_code": "603267.SH", "trade_date": date, "close": trading_close},
        ])

    return pd.DataFrame(rows)


def test_daily_linkage_calculates_windows():
    result = calculate_daily_linkage(_registry(), _market_df(), "20260501")

    assert result.status == "ok"
    chain = result.pools["industry_chain"]
    assert chain.status == "ok"
    assert chain.top_members[0].symbol == "688270.SH"
    assert chain.top_members[0].corr_20d is not None
    assert chain.top_members[0].beta_20d is not None
    assert chain.top_members[0].direction_consistency_20d is not None


def test_daily_linkage_short_window_is_partial():
    result = calculate_daily_linkage(_registry(), _market_df(days=6), "20260408")

    assert result.status == "partial"
    chain_member = result.pools["industry_chain"].members[0]
    assert chain_member.data_status == "partial"
    assert chain_member.corr_5d is not None
    assert chain_member.corr_20d is None
