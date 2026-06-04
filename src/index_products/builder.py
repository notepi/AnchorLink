"""
虚拟 ETF / 自定义指数 — NAV 构建引擎

职责：
  - 从 PoolRegistry 构建指数定义
  - 陈旧报价溯源（raw vs normalized）
  - ETF-like NAV 构建（含月频再平衡）
  - Anchor 标准超额计算
  - 新旧口径对照
  - 输出写入
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.config.loader import PoolRegistry
from src.index_products.models import (
    AnchorExcessRecord,
    IndexDefinition,
    IndexMember,
    IndexNAVRecord,
    MemberDayRecord,
)
from src.index_products.quality import run_all_quality_checks

# ── 常量 ──

BASE_LEVEL = 1000.0
INDEX_IDS = ["industry_chain_index", "direct_peers_index", "theme_pool_index", "trading_watchlist_index"]
UNIVERSE_IDS = ["industry_chain", "direct_peers", "theme_pool", "trading_watchlist"]
EXCESS_WINDOWS = [1, 3, 5, 10]
METADATA_FIELDS = [
    "pool_config_version",
    "price_adjustment_mode",
    "universe_mode",
    "source_data_as_of",
    "build_mode",
    "generated_at",
]


# ── 指数定义构建 ──

def build_index_definitions(registry: PoolRegistry) -> list[IndexDefinition]:
    """从 PoolRegistry 构建四条指数定义"""
    version = registry.get_version()
    definitions = []

    for universe_id, index_id in zip(UNIVERSE_IDS, INDEX_IDS):
        universe = registry.get_universe(universe_id)
        if universe is None:
            raise ValueError(f"Universe {universe_id} 不存在于 pools.yaml")

        # 按筛选规则获取成员
        if universe_id in ("industry_chain", "direct_peers"):
            memberships = registry.get_benchmark_scope(universe_id)
            scope = "benchmark"
        else:
            memberships = registry.get_ranking_scope_members(universe_id)
            scope = "ranking"

        if not memberships:
            raise ValueError(f"指数 {index_id} 无有效成员")

        # 构建归一化权重
        total_weight = sum(m.weight for m in memberships)
        members = tuple(
            IndexMember(
                symbol=m.symbol,
                raw_config_weight=m.weight,
                normalized_target_weight=m.weight / total_weight,
                role=m.role,
                membership_scope=scope,
            )
            for m in sorted(memberships, key=lambda x: x.symbol)
        )

        definitions.append(IndexDefinition(
            index_id=index_id,
            display_name=universe.display_name,
            can_be_benchmark=universe.can_be_benchmark,
            pool_config_version=version,
            members=members,
        ))

    return definitions


# ── 陈旧报价溯源 ──

def build_stale_matrix(
    normalized_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    trading_days: list[pd.Timestamp],
    symbols: list[str],
) -> dict[str, dict[str, tuple[str, str, int]]]:
    """构建陈旧报价溯源矩阵

    Returns:
        {symbol: {date_str: (quote_status, source_trade_date, stale_days)}}
    """
    # raw 中的键集合
    raw_df_copy = raw_df.copy()
    if raw_df_copy["trade_date"].dtype.kind != "M":
        raw_df_copy["trade_date"] = pd.to_datetime(raw_df_copy["trade_date"], format="%Y%m%d")
    raw_keys = set(zip(
        raw_df_copy["ts_code"],
        raw_df_copy["trade_date"].dt.strftime("%Y%m%d"),
    ))
    raw_zero_vol = set(zip(
        raw_df_copy.loc[raw_df_copy["vol"] == 0, "ts_code"],
        raw_df_copy.loc[raw_df_copy["vol"] == 0, "trade_date"].dt.strftime("%Y%m%d"),
    ))

    # normalized 中 pivot
    norm_copy = normalized_df.copy()
    if norm_copy["trade_date"].dtype.kind == "M":
        norm_copy["_date_str"] = norm_copy["trade_date"].dt.strftime("%Y%m%d")
    else:
        norm_copy["_date_str"] = norm_copy["trade_date"].astype(str)

    result: dict[str, dict[str, tuple[str, str, int]]] = {}

    for symbol in symbols:
        sym_data = norm_copy[norm_copy["ts_code"] == symbol]
        sym_dates = sym_data.set_index("_date_str")
        result[symbol] = {}

        stale_count = 0
        last_fresh_date: Optional[str] = None

        for td in trading_days:
            date_str = td.strftime("%Y%m%d") if hasattr(td, "strftime") else str(td)

            if date_str not in sym_dates.index:
                # normalized 中无此 symbol 此日数据
                result[symbol][date_str] = ("carried_forward", last_fresh_date or "", stale_count + 1)
                stale_count += 1
                continue

            key = (symbol, date_str)
            if key not in raw_keys:
                quote_status = "carried_forward"
            elif key in raw_zero_vol:
                quote_status = "zero_volume_raw"
            else:
                quote_status = "fresh"

            if quote_status == "fresh":
                stale_count = 0
                last_fresh_date = date_str
                source_date = date_str
            else:
                stale_count += 1
                source_date = last_fresh_date or ""

            result[symbol][date_str] = (quote_status, source_date, stale_count)

    return result


# ── 再平衡日期检测 ──

def _find_rebalance_dates(
    trading_days: list[pd.Timestamp],
    freq: str = "monthly",
) -> set[pd.Timestamp]:
    """检测再平衡日期集合"""
    if freq == "none":
        return set()
    if freq == "monthly":
        rebalance = set()
        prev_month = None
        for d in sorted(trading_days):
            m = d.month if hasattr(d, "month") else pd.Timestamp(d).month
            if prev_month is not None and m != prev_month:
                rebalance.add(d)
            prev_month = m
        return rebalance
    if freq == "quarterly":
        rebalance = set()
        prev_q = None
        for d in sorted(trading_days):
            ts = d if hasattr(d, "month") else pd.Timestamp(d)
            q = (ts.year, (ts.month - 1) // 3)
            if prev_q is not None and q != prev_q:
                rebalance.add(d)
            prev_q = q
        return rebalance
    raise ValueError(f"Unknown rebalance_freq: {freq}")


# ── NAV 构建 ──

def build_nav_series(
    index_def: IndexDefinition,
    price_df: pd.DataFrame,
    stale_matrix: dict[str, dict[str, tuple[str, str, int]]],
    trading_days: list[pd.Timestamp],
    rebalance_freq: str = "monthly",
    min_size: int = 3,
) -> tuple[list[IndexNAVRecord], list[MemberDayRecord]]:
    """构建单条指数的 NAV 序列

    Returns:
        (nav_records, member_records)
    """
    now = datetime.now(timezone.utc).isoformat()
    source_data_as_of = trading_days[-1].strftime("%Y%m%d") if trading_days else ""

    # 准备价格 pivot
    symbols = [m.symbol for m in index_def.members]
    close_pivot = price_df.pivot(index="trade_date", columns="ts_code", values="close")
    close_pivot = close_pivot.ffill()  # forward-fill for missing dates

    # 确定交易日历
    sorted_days = sorted(trading_days)

    # 确定每条指数独立的 base_date
    base_date: Optional[pd.Timestamp] = None
    for d in sorted_days:
        included_count = sum(
            1 for s in symbols
            if s in close_pivot.columns and d in close_pivot.index
            and pd.notna(close_pivot.loc[d, s]) and close_pivot.loc[d, s] > 0
        )
        inclusion_ratio = included_count / len(symbols) if symbols else 0
        if included_count >= min_size and inclusion_ratio >= 0.8:
            base_date = d
            break
    if base_date is None:
        raise ValueError(f"指数 {index_def.index_id} 无法确定 base_date：无交易日满足 min_size={min_size} 且 inclusion_ratio>=0.8")

    # 检测再平衡日
    rebalance_dates = _find_rebalance_dates(sorted_days, rebalance_freq)

    # 初始化
    active_symbols: list[str] = []
    units: dict[str, float] = {}
    member_first_fresh: dict[str, Optional[pd.Timestamp]] = {}

    # 找出每个 symbol 的首个 fresh 日期
    for s in symbols:
        for d in sorted_days:
            date_str = d.strftime("%Y%m%d")
            if s in stale_matrix and date_str in stale_matrix[s]:
                qs, _, _ = stale_matrix[s][date_str]
                if qs == "fresh":
                    member_first_fresh[s] = d
                    break
        else:
            member_first_fresh[s] = None

    # base_date 当日纳入的成员
    for m in index_def.members:
        s = m.symbol
        if s in close_pivot.columns and base_date in close_pivot.index:
            c = close_pivot.loc[base_date, s]
            if pd.notna(c) and c > 0:
                active_symbols.append(s)

    # 重新归一化 active members 的 effective_target_weight
    def _effective_weights(active: list[str]) -> dict[str, float]:
        raw_weights = {
            s: next(m.raw_config_weight for m in index_def.members if m.symbol == s)
            for s in active
        }
        total = sum(raw_weights.values())
        return {s: w / total for s, w in raw_weights.items()}

    eff_w = _effective_weights(active_symbols)
    for s in active_symbols:
        c = close_pivot.loc[base_date, s]
        units[s] = BASE_LEVEL * eff_w[s] / c

    nav_records: list[IndexNAVRecord] = []
    member_records: list[MemberDayRecord] = []

    prev_nav: Optional[float] = None

    # 逐日迭代
    for d in sorted_days:
        if d < base_date:
            continue

        date_str = d.strftime("%Y%m%d")
        is_rebalance_day = d in rebalance_dates

        # 检查迟到成员
        late_joiners: list[str] = []
        for m in index_def.members:
            s = m.symbol
            if s not in active_symbols and s in close_pivot.columns and d in close_pivot.index:
                c = close_pivot.loc[d, s]
                if pd.notna(c) and c > 0:
                    # 该 symbol 在当日有有效 close 且尚未纳入
                    first_fresh = member_first_fresh.get(s)
                    if first_fresh is not None and first_fresh <= d:
                        late_joiners.append(s)

        rebalance_reason = "none"
        rebalance_uses_stale = False

        # 处理迟到成员（全量连续再平衡）
        if late_joiners:
            for s in late_joiners:
                active_symbols.append(s)
            eff_w = _effective_weights(active_symbols)
            nav_pre = sum(units.get(s, 0) * close_pivot.loc[d, s] for s in units if s in close_pivot.columns and d in close_pivot.index)
            for s in active_symbols:
                c = close_pivot.loc[d, s]
                if pd.notna(c) and c > 0:
                    units[s] = nav_pre * eff_w[s] / c
            rebalance_reason = "late_member_join"
            # 检查是否使用了 stale 报价
            for s in active_symbols:
                if s in stale_matrix and date_str in stale_matrix[s]:
                    qs, _, _ = stale_matrix[s][date_str]
                    if qs != "fresh":
                        rebalance_uses_stale = True
                        break

        # 计算 NAV
        nav = 0.0
        for s in active_symbols:
            if s in close_pivot.columns and d in close_pivot.index:
                c = close_pivot.loc[d, s]
                if pd.notna(c):
                    nav += units.get(s, 0) * c

        # 计算 1d return
        index_return_1d: Optional[float] = None
        if prev_nav is not None and prev_nav > 0:
            index_return_1d = (nav / prev_nav - 1) * 100

        # 计算 multi-day returns
        nav_series_so_far = [r.nav for r in nav_records]
        index_return_3d = _compute_nd_return(nav_series_so_far, nav, 3)
        index_return_5d = _compute_nd_return(nav_series_so_far, nav, 5)
        index_return_10d = _compute_nd_return(nav_series_so_far, nav, 10)

        # 统计 staleness
        fresh_count = 0
        stale_count = 0
        stale_syms: list[str] = []
        stale_days_max = 0

        for s in active_symbols:
            if s in stale_matrix and date_str in stale_matrix[s]:
                qs, _, sd = stale_matrix[s][date_str]
                if qs == "fresh":
                    fresh_count += 1
                else:
                    stale_count += 1
                    stale_syms.append(s)
                    stale_days_max = max(stale_days_max, sd)
            else:
                # 不在 stale_matrix 中，视为 fresh
                fresh_count += 1

        included_count = len(active_symbols)
        configured_count = len(index_def.members)
        fresh_quote_ratio = fresh_count / included_count if included_count > 0 else 0.0
        universe_inclusion_ratio = included_count / configured_count if configured_count > 0 else 0.0
        data_status = _compute_data_status(fresh_quote_ratio, universe_inclusion_ratio)

        # 月度再平衡
        if is_rebalance_day and rebalance_reason != "late_member_join":
            eff_w = _effective_weights(active_symbols)
            for s in active_symbols:
                if s in close_pivot.columns and d in close_pivot.index:
                    c = close_pivot.loc[d, s]
                    if pd.notna(c) and c > 0:
                        units[s] = nav * eff_w[s] / c
            rebalance_reason = "monthly_rebalance"
            # 检查 stale
            if not rebalance_uses_stale:
                for s in active_symbols:
                    if s in stale_matrix and date_str in stale_matrix[s]:
                        qs, _, _ = stale_matrix[s][date_str]
                        if qs != "fresh":
                            rebalance_uses_stale = True
                            break

        # 记录 IndexNAVRecord
        nav_records.append(IndexNAVRecord(
            index_id=index_def.index_id,
            trade_date=date_str,
            nav=nav,
            index_return_1d=index_return_1d,
            index_return_3d=index_return_3d,
            index_return_5d=index_return_5d,
            index_return_10d=index_return_10d,
            is_rebalance_day=is_rebalance_day or (rebalance_reason == "late_member_join"),
            rebalance_uses_stale_price=rebalance_uses_stale,
            rebalance_reason=rebalance_reason,
            included_member_count=included_count,
            configured_member_count=configured_count,
            fresh_price_count=fresh_count,
            stale_price_count=stale_count,
            stale_days_max=stale_days_max,
            stale_symbols=",".join(stale_syms),
            fresh_quote_ratio=fresh_quote_ratio,
            universe_inclusion_ratio=universe_inclusion_ratio,
            data_status=data_status,
            rebalance_flag=rebalance_freq if (is_rebalance_day or rebalance_reason != "none") else "",
            pool_config_version=index_def.pool_config_version,
            price_adjustment_mode="qfq",
            universe_mode="constant_universe_research_view",
            source_data_as_of=source_data_as_of,
            build_mode="full_rebuild",
            generated_at=now,
        ))

        # 记录 MemberDayRecord
        for m in index_def.members:
            s = m.symbol
            is_included = s in active_symbols

            if is_included and s in close_pivot.columns and d in close_pivot.index:
                c = close_pivot.loc[d, s]
                if pd.notna(c):
                    actual_w = (units.get(s, 0) * c) / nav if nav > 0 else None
                else:
                    actual_w = None
                    c = None
            else:
                c = None
                actual_w = None

            if is_included and s in stale_matrix and date_str in stale_matrix[s]:
                qs, src_date, sd = stale_matrix[s][date_str]
            elif is_included:
                qs = "fresh"
                src_date = date_str
                sd = 0
            else:
                qs = ""
                src_date = None
                sd = 0

            # membership_event
            if d == base_date and is_included:
                event = "base_init"
            elif s in late_joiners:
                event = "late_member_join"
            else:
                event = "none"

            member_records.append(MemberDayRecord(
                index_id=index_def.index_id,
                trade_date=date_str,
                symbol=s,
                raw_config_weight=m.raw_config_weight,
                normalized_target_weight=m.normalized_target_weight,
                actual_weight=actual_w,
                close=c,
                quote_status=qs,
                price_is_stale=(qs not in ("fresh", "")),
                source_trade_date=src_date,
                stale_days=sd,
                included=is_included,
                membership_role=m.role,
                membership_event=event,
                pool_config_version=index_def.pool_config_version,
                price_adjustment_mode="qfq",
                universe_mode="constant_universe_research_view",
                source_data_as_of=source_data_as_of,
                build_mode="full_rebuild",
                generated_at=now,
            ))

        prev_nav = nav

    return nav_records, member_records


def _compute_nd_return(
    nav_history: list[float],
    current_nav: float,
    n: int,
) -> Optional[float]:
    """计算 N 日收益率（百分比）"""
    if len(nav_history) < n - 1:
        return None
    idx = len(nav_history) - n
    if idx < 0:
        return None
    past_nav = nav_history[idx]
    if past_nav <= 0:
        return None
    return (current_nav / past_nav - 1) * 100


def _compute_data_status(
    fresh_quote_ratio: float,
    universe_inclusion_ratio: float,
) -> str:
    """计算 data_status"""
    if fresh_quote_ratio >= 0.8 and universe_inclusion_ratio >= 0.8:
        return "ok"
    if fresh_quote_ratio >= 0.5 and universe_inclusion_ratio >= 0.5:
        return "partial"
    return "insufficient_data"


# ── Anchor 超额计算 ──

def compute_anchor_excess(
    all_nav_records: dict[str, list[IndexNAVRecord]],
    anchor_symbol: str,
    price_df: pd.DataFrame,
    pool_config_version: str,
    source_data_as_of: str,
) -> list[AnchorExcessRecord]:
    """计算 Anchor 相对各指数的标准超额

    严格按照需求公式：
      anchor_return_Nd = anchor_close(t) / anchor_close(t-N) - 1
      index_return_Nd  = index_nav(t)    / index_nav(t-N)    - 1
      excess_vs_index_Nd = anchor_return_Nd - index_return_Nd

    回溯 N 个交易日（不含当日），即 t-N 对应 sorted_dates[i-N]。
    """
    now = datetime.now(timezone.utc).isoformat()

    # Anchor close 序列
    anchor_df = price_df[price_df["ts_code"] == anchor_symbol].sort_values("trade_date")

    # 构建日期 → anchor_close 映射
    anchor_close_map: dict[str, float] = {}
    for _, row in anchor_df.iterrows():
        date_str = row["trade_date"].strftime("%Y%m%d")
        anchor_close_map[date_str] = row["close"]

    # 构建各指数的日期 → NAV record 映射
    nav_record_maps: dict[str, dict[str, IndexNAVRecord]] = {}
    for index_id, records in all_nav_records.items():
        nav_record_maps[index_id] = {r.trade_date: r for r in records}

    # 获取所有交易日（取所有指数和 anchor 的交集）
    all_dates: set[str] = set(anchor_close_map.keys())
    for index_id in INDEX_IDS:
        if index_id in nav_record_maps:
            all_dates &= set(nav_record_maps[index_id].keys())
    sorted_dates = sorted(all_dates)

    # 构建 anchor close 序列用于回溯
    anchor_close_list: list[float] = [anchor_close_map[d] for d in sorted_dates]

    results: list[AnchorExcessRecord] = []

    for i, date_str in enumerate(sorted_dates):
        anchor_close = anchor_close_list[i]

        # Anchor returns: t-N 个交易日前的 close
        anchor_returns: dict[int, Optional[float]] = {}
        for n in EXCESS_WINDOWS:
            if i < n:
                anchor_returns[n] = None
            else:
                past_close = anchor_close_list[i - n]
                if past_close > 0:
                    anchor_returns[n] = (anchor_close / past_close - 1) * 100
                else:
                    anchor_returns[n] = None

        # 各指数超额：直接使用 NAV 记录中已计算的 index_return_Nd
        excess: dict[str, dict[int, Optional[float]]] = {}
        for index_id in INDEX_IDS:
            excess[index_id] = {}
            rec_map = nav_record_maps.get(index_id, {})
            rec = rec_map.get(date_str)

            for n in EXCESS_WINDOWS:
                if rec is None:
                    excess[index_id][n] = None
                    continue

                # 从 NAV 记录取 index_return
                ret_field = f"index_return_{n}d"
                index_ret = getattr(rec, ret_field, None)

                anchor_ret = anchor_returns.get(n)
                if anchor_ret is not None and index_ret is not None:
                    excess[index_id][n] = anchor_ret - index_ret
                else:
                    excess[index_id][n] = None

        results.append(AnchorExcessRecord(
            date=date_str,
            anchor_symbol=anchor_symbol,
            anchor_close=anchor_close,
            anchor_return_1d=anchor_returns.get(1),
            anchor_return_3d=anchor_returns.get(3),
            anchor_return_5d=anchor_returns.get(5),
            anchor_return_10d=anchor_returns.get(10),
            excess_vs_industry_chain_index_1d=excess.get("industry_chain_index", {}).get(1),
            excess_vs_industry_chain_index_3d=excess.get("industry_chain_index", {}).get(3),
            excess_vs_industry_chain_index_5d=excess.get("industry_chain_index", {}).get(5),
            excess_vs_industry_chain_index_10d=excess.get("industry_chain_index", {}).get(10),
            excess_vs_direct_peers_index_1d=excess.get("direct_peers_index", {}).get(1),
            excess_vs_direct_peers_index_3d=excess.get("direct_peers_index", {}).get(3),
            excess_vs_direct_peers_index_5d=excess.get("direct_peers_index", {}).get(5),
            excess_vs_direct_peers_index_10d=excess.get("direct_peers_index", {}).get(10),
            excess_vs_theme_pool_index_1d=excess.get("theme_pool_index", {}).get(1),
            excess_vs_theme_pool_index_3d=excess.get("theme_pool_index", {}).get(3),
            excess_vs_theme_pool_index_5d=excess.get("theme_pool_index", {}).get(5),
            excess_vs_theme_pool_index_10d=excess.get("theme_pool_index", {}).get(10),
            excess_vs_trading_watchlist_index_1d=excess.get("trading_watchlist_index", {}).get(1),
            excess_vs_trading_watchlist_index_3d=excess.get("trading_watchlist_index", {}).get(3),
            excess_vs_trading_watchlist_index_5d=excess.get("trading_watchlist_index", {}).get(5),
            excess_vs_trading_watchlist_index_10d=excess.get("trading_watchlist_index", {}).get(10),
            pool_config_version=pool_config_version,
            price_adjustment_mode="qfq",
            universe_mode="constant_universe_research_view",
            source_data_as_of=source_data_as_of,
            build_mode="full_rebuild",
            generated_at=now,
        ))

    return results


# ── 新旧对照 ──

def build_legacy_comparison(
    anchor_excess_records: list[AnchorExcessRecord],
    history_summary_path: Path,
    history_rolling_path: Path,
    pool_config_version: str,
    source_data_as_of: str,
) -> pd.DataFrame:
    """构建新旧口径对照 DataFrame"""
    now = datetime.now(timezone.utc).isoformat()

    # 读取旧数据
    summary_df = pd.read_csv(history_summary_path)
    rolling_df = pd.read_csv(history_rolling_path)

    # 旧 daily excess (median_displacement_1d)
    legacy_1d_map: dict[str, float] = {}
    if "relative_strength_vs_industry_chain" in summary_df.columns:
        for _, row in summary_df.iterrows():
            date_str = str(int(row["date"])) if "date" in row else ""
            val = row["relative_strength_vs_industry_chain"]
            if pd.notna(val):
                legacy_1d_map[date_str] = float(val)

    # 旧 5d/10d
    legacy_5d_map: dict[str, float] = {}
    legacy_10d_map: dict[str, float] = {}
    if "excess_5d" in rolling_df.columns:
        for _, row in rolling_df.iterrows():
            date_str = str(int(row["date"])) if "date" in row else ""
            if pd.notna(row.get("excess_5d")):
                legacy_5d_map[date_str] = float(row["excess_5d"])
            if pd.notna(row.get("excess_10d")):
                legacy_10d_map[date_str] = float(row["excess_10d"])

    # 新指数超额 (industry_chain_index)
    new_1d_map: dict[str, Optional[float]] = {}
    new_3d_map: dict[str, Optional[float]] = {}
    new_5d_map: dict[str, Optional[float]] = {}
    new_10d_map: dict[str, Optional[float]] = {}
    for r in anchor_excess_records:
        new_1d_map[r.date] = r.excess_vs_industry_chain_index_1d
        new_3d_map[r.date] = r.excess_vs_industry_chain_index_3d
        new_5d_map[r.date] = r.excess_vs_industry_chain_index_5d
        new_10d_map[r.date] = r.excess_vs_industry_chain_index_10d

    # 日期交集
    legacy_dates = set(legacy_1d_map.keys())
    new_dates = set(new_1d_map.keys())
    common_dates = sorted(legacy_dates & new_dates)

    if not common_dates:
        print("[WARN] 新旧口径无共同日期，无法对照")
        return pd.DataFrame()

    overlap_start = common_dates[0]
    overlap_end = common_dates[-1]
    overlap_n = len(common_dates)

    rows = []
    for d in common_dates:
        md_1d = legacy_1d_map.get(d)
        md_5d = legacy_5d_map.get(d)
        md_10d = legacy_10d_map.get(d)
        ie_1d = new_1d_map.get(d)
        ie_3d = new_3d_map.get(d)
        ie_5d = new_5d_map.get(d)
        ie_10d = new_10d_map.get(d)

        diff_1d = (ie_1d - md_1d) if ie_1d is not None and md_1d is not None else None
        diff_5d = (ie_5d - md_5d) if ie_5d is not None and md_5d is not None else None
        diff_10d = (ie_10d - md_10d) if ie_10d is not None and md_10d is not None else None

        rows.append({
            "date": d,
            "median_displacement_1d": md_1d,
            "median_displacement_5d": md_5d,
            "median_displacement_10d": md_10d,
            "index_excess_1d": ie_1d,
            "index_excess_3d": ie_3d,
            "index_excess_5d": ie_5d,
            "index_excess_10d": ie_10d,
            "diff_1d": diff_1d,
            "diff_5d": diff_5d,
            "diff_10d": diff_10d,
            "overlap_start": overlap_start,
            "overlap_end": overlap_end,
            "overlap_n": overlap_n,
            "pool_config_version": pool_config_version,
            "price_adjustment_mode": "qfq",
            "universe_mode": "constant_universe_research_view",
            "source_data_as_of": source_data_as_of,
            "build_mode": "full_rebuild",
            "generated_at": now,
        })

    return pd.DataFrame(rows)


# ── 输出写入 ──

def _write_outputs(
    output_dir: Path,
    nav_records: list[IndexNAVRecord],
    member_records: list[MemberDayRecord],
    excess_records: list[AnchorExcessRecord],
    legacy_df: pd.DataFrame,
    metadata: dict[str, str],
) -> None:
    """写入 CSV + parquet + build_manifest.json"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # NAV
    nav_df = pd.DataFrame([_dataclass_to_dict(r) for r in nav_records])
    _write_csv_parquet(nav_df, output_dir / "custom_index_nav", metadata)

    # Members
    mem_df = pd.DataFrame([_dataclass_to_dict(r) for r in member_records])
    _write_csv_parquet(mem_df, output_dir / "custom_index_members", metadata)

    # Excess
    exc_df = pd.DataFrame([_dataclass_to_dict(r) for r in excess_records])
    _write_csv_parquet(exc_df, output_dir / "anchor_index_excess", metadata)

    # Legacy comparison
    if not legacy_df.empty:
        _write_csv_parquet(legacy_df, output_dir / "legacy_vs_index_excess_comparison", metadata)

    # build_manifest.json
    import json
    manifest = {
        **metadata,
        "index_ids": INDEX_IDS,
        "nav_record_count": len(nav_records),
        "member_record_count": len(member_records),
        "excess_record_count": len(excess_records),
        "legacy_comparison_count": len(legacy_df),
    }
    with open(output_dir / "build_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"[OK] 输出写入 {output_dir}")


def _write_csv_parquet(
    df: pd.DataFrame,
    stem: Path,
    metadata: dict[str, str],
) -> None:
    """写入 CSV 和 parquet（parquet 含 schema metadata）"""
    # CSV
    df.to_csv(str(stem) + ".csv", index=False)

    # Parquet with metadata
    table = pa.Table.from_pandas(df)
    existing_meta = table.schema.metadata or {}
    merged_meta = {**existing_meta, **{k.encode(): v.encode() for k, v in metadata.items()}}
    table = table.replace_schema_metadata(merged_meta)
    pq.write_table(table, str(stem) + ".parquet")


def _dataclass_to_dict(obj) -> dict:
    """frozen dataclass → dict"""
    from dataclasses import asdict
    return asdict(obj)


# ── 主入口 ──

def build_all_indexes(
    config_path: str | None = None,
    price_path: str | None = None,
    raw_path: str | None = None,
    output_dir: str | None = None,
    rebalance_freq: str = "monthly",
    allow_stale_anchor: bool = False,
) -> dict:
    """构建全部指数并输出

    Returns:
        摘要 dict
    """
    root = Path(__file__).parent.parent.parent

    # 路径默认值
    if config_path is None:
        config_path = str(root / "config" / "pools.yaml")
    if price_path is None:
        price_path = str(root / "data" / "price" / "normalized" / "market_data_normalized.parquet")
    if raw_path is None:
        raw_path = str(root / "data" / "price" / "raw" / "market_data.parquet")

    # 加载配置
    print("[INFO] 加载配置...")
    registry = PoolRegistry(config_path)
    anchor_symbol = registry.get_anchor().symbol
    version = registry.get_version()

    # 加载行情
    print("[INFO] 加载行情数据...")
    normalized_df = pd.read_parquet(price_path)
    raw_df = pd.read_parquet(raw_path)

    # 确保 trade_date 是 datetime
    if normalized_df["trade_date"].dtype.kind != "M":
        normalized_df["trade_date"] = pd.to_datetime(normalized_df["trade_date"])
    if raw_df["trade_date"].dtype.kind != "M":
        raw_df["trade_date"] = pd.to_datetime(raw_df["trade_date"], format="%Y%m%d")

    # 质量检查
    print("[INFO] 运行质量检查...")
    warnings = run_all_quality_checks(normalized_df, raw_df, anchor_symbol, allow_stale_anchor)
    if warnings:
        print(f"[WARN] 质量检查 {len(warnings)} 项警告")

    # 构建指数定义
    print("[INFO] 构建指数定义...")
    definitions = build_index_definitions(registry)

    # 构建陈旧报价矩阵
    print("[INFO] 构建陈旧报价溯源矩阵...")
    all_symbols = list(set(s for d in definitions for m in d.members for s in [m.symbol]))
    trading_days = sorted(normalized_df["trade_date"].unique())
    stale_matrix = build_stale_matrix(normalized_df, raw_df, trading_days, all_symbols)

    # 构建各指数 NAV
    print("[INFO] 构建 NAV 序列...")
    all_nav: dict[str, list[IndexNAVRecord]] = {}
    all_members: list[MemberDayRecord] = []

    for defn in definitions:
        universe = registry.get_universe(defn.index_id.replace("_index", ""))
        min_size = universe.min_size if universe else 3
        nav_recs, mem_recs = build_nav_series(
            defn, normalized_df, stale_matrix, trading_days,
            rebalance_freq=rebalance_freq, min_size=min_size,
        )
        all_nav[defn.index_id] = nav_recs
        all_members.extend(mem_recs)
        print(f"[OK] {defn.index_id}: {len(nav_recs)} 天, "
              f"成员={defn.members.__len__()}, "
              f"NAV 范围=[{nav_recs[0].nav:.2f}, {nav_recs[-1].nav:.2f}]")

    # 计算超额
    print("[INFO] 计算 Anchor 标准超额...")
    source_data_as_of = trading_days[-1].strftime("%Y%m%d") if len(trading_days) > 0 else ""
    excess_records = compute_anchor_excess(
        all_nav, anchor_symbol, normalized_df, version, source_data_as_of,
    )

    # 新旧对照
    print("[INFO] 构建新旧口径对照...")
    history_summary_path = root / "data" / "output" / "history_summary.csv"
    history_rolling_path = root / "data" / "output" / "history_rolling_metrics.csv"
    legacy_df = pd.DataFrame()
    if history_summary_path.exists() and history_rolling_path.exists():
        legacy_df = build_legacy_comparison(
            excess_records, history_summary_path, history_rolling_path,
            version, source_data_as_of,
        )
    else:
        print("[WARN] 旧口径文件不存在，跳过对照")

    # 输出
    if output_dir is None:
        output_dir = str(
            root / "data" / "price" / "analytics" / "index_products"
            / f"constant_universe_{version}"
        )
    metadata = {
        "pool_config_version": version,
        "price_adjustment_mode": "qfq",
        "universe_mode": "constant_universe_research_view",
        "source_data_as_of": source_data_as_of,
        "build_mode": "full_rebuild",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_outputs(
        Path(output_dir),
        [r for recs in all_nav.values() for r in recs],
        all_members,
        excess_records,
        legacy_df,
        metadata,
    )

    # 摘要
    summary = _build_summary(all_nav, excess_records, legacy_df, definitions, anchor_symbol)
    return summary


def _build_summary(
    all_nav: dict[str, list[IndexNAVRecord]],
    excess_records: list[AnchorExcessRecord],
    legacy_df: pd.DataFrame,
    definitions: list[IndexDefinition],
    anchor_symbol: str,
) -> dict:
    """构建验收摘要"""
    summary: dict = {"anchor": anchor_symbol, "indexes": {}}

    for defn in definitions:
        idx_id = defn.index_id
        recs = all_nav.get(idx_id, [])
        if not recs:
            continue
        latest = recs[-1]
        summary["indexes"][idx_id] = {
            "member_count": len(defn.members),
            "start_date": recs[0].trade_date,
            "end_date": latest.trade_date,
            "latest_nav": latest.nav,
            "latest_fresh_quote_ratio": latest.fresh_quote_ratio,
            "latest_universe_inclusion_ratio": latest.universe_inclusion_ratio,
            "latest_data_status": latest.data_status,
            "latest_stale_symbols": latest.stale_symbols,
            "latest_index_return_1d": latest.index_return_1d,
            "latest_index_return_3d": latest.index_return_3d,
            "latest_index_return_5d": latest.index_return_5d,
            "latest_index_return_10d": latest.index_return_10d,
        }

    # 最新超额 vs industry_chain_index
    if excess_records:
        latest_excess = excess_records[-1]
        summary["latest_excess_vs_industry_chain"] = {
            "1d": latest_excess.excess_vs_industry_chain_index_1d,
            "3d": latest_excess.excess_vs_industry_chain_index_3d,
            "5d": latest_excess.excess_vs_industry_chain_index_5d,
            "10d": latest_excess.excess_vs_industry_chain_index_10d,
        }

    # 新旧对照统计
    if not legacy_df.empty and "diff_1d" in legacy_df.columns:
        valid_diffs = legacy_df["diff_1d"].dropna()
        if len(valid_diffs) > 0:
            import numpy as np
            summary["legacy_comparison"] = {
                "overlap_start": legacy_df["overlap_start"].iloc[0],
                "overlap_end": legacy_df["overlap_end"].iloc[0],
                "overlap_n": int(legacy_df["overlap_n"].iloc[0]),
                "correlation": float(legacy_df["median_displacement_1d"].corr(legacy_df["index_excess_1d"])),
                "mae_1d": float((valid_diffs.abs()).mean()),
                "max_diff_1d": float(valid_diffs.abs().max()),
            }

    return summary
