"""
AnchorLink MVP 流程入口

整合六层模块调用，生成三类输出：
  - industry_snapshot.json（机器可读）
  - peer_matrix.csv（数据检查）
  - industry_report.md（人工阅读）

Usage:
    uv run python -m src.dailyreport.run --date 20260502
    uv run python -m src.dailyreport.run  # 使用最新交易日
"""

import argparse
from pathlib import Path
from typing import Optional

import pandas as pd

from src.config.loader import PoolRegistry
from src.pool_state.calculator import PoolStateCalculator
from src.pool_state.models import MemberData
from src.anchor_position.relative_strength import RelativeStrengthCalculator
from src.anchor_position.ranking_calculator import RankingCalculator
from src.group_rotation import analyze_rotation_with_spreads
from src.signal import generate_signals
from src.output import write_all
from src.price import load_price_inputs
from src.linkage import calculate_daily_linkage


def run_daily_analysis(trade_date: Optional[str] = None) -> dict:
    """
    执行每日分析流程

    Args:
        trade_date: 分析日期 (YYYYMMDD)，默认使用最新交易日

    Returns:
        {
            "trade_date": str,
            "output_dir": str,
            "snapshot": IndustrySnapshot,
        }
    """
    print("[INFO] 开始 AnchorLink 每日分析...")

    # Phase 1: 加载配置
    print("[INFO] Phase 1: 加载配置...")
    registry = PoolRegistry()
    validation = registry.validate()
    if not validation["valid"]:
        raise ValueError(f"配置验证失败: {validation['errors']}")
    print(f"[OK] 配置加载完成: anchor={registry.get_anchor().symbol}")

    # Phase 2: 加载行情数据
    print("[INFO] Phase 2: 加载行情数据...")
    price_inputs = load_price_inputs()
    market_df = price_inputs["market_data"]
    daily_basic_df = price_inputs.get("daily_basic_data")
    moneyflow_df = price_inputs.get("moneyflow_data")
    print(f"[OK] 行情数据加载完成: {len(market_df)} 条记录")

    # 确定分析日期
    if trade_date is None:
        trade_date = _get_latest_trade_date(market_df)
    print(f"[INFO] 分析日期: {trade_date}")

    # Phase 3: 计算池子状态
    print("[INFO] Phase 3: 计算池子状态...")
    pool_calc = PoolStateCalculator(registry, market_df, daily_basic_df, moneyflow_df)
    pool_result = pool_calc.calculate(trade_date)
    pool_states = pool_result.pool_states
    print(f"[OK] 池子状态计算完成: {len(pool_states)} 个池子, 状态={pool_result.overall_status}")

    # Phase 4: 构建成员数据字典
    print("[INFO] Phase 4: 构建成员数据字典...")
    market_data_dict = _build_member_data_dict(
        market_df, daily_basic_df, moneyflow_df, trade_date, registry
    )
    anchor_symbol = registry.get_anchor().symbol
    anchor_data = market_data_dict.get(anchor_symbol)
    if anchor_data is None:
        raise ValueError(f"Anchor 数据缺失: {anchor_symbol}")
    print(f"[OK] 成员数据字典构建完成: {len(market_data_dict)} 个成员")

    # Phase 5: 计算相对强弱
    print("[INFO] Phase 5: 计算相对强弱...")
    ranking_calc = RankingCalculator(registry)
    rs_calc = RelativeStrengthCalculator(registry, ranking_calc)
    anchor_positions = rs_calc.calculate_all(
        trade_date, anchor_data, pool_states, market_data_dict
    )
    print(f"[OK] 相对强弱计算完成: {len(anchor_positions)} 个池子")

    # Phase 6: 计算组间轮动
    print("[INFO] Phase 6: 计算组间轮动...")
    group_rotation = analyze_rotation_with_spreads(
        pool_states,
        trade_date,
        registry,
        core_pool_id="industry_chain",
    )
    print(f"[OK] 组间轮动计算完成: 最强={group_rotation.strongest_group}, 最弱={group_rotation.weakest_group}")

    # Phase 7: 生成信号
    print("[INFO] Phase 7: 生成信号...")
    signal_result = generate_signals(pool_states, anchor_positions, group_rotation, registry)
    print(f"[OK] 信号生成完成: {len(signal_result.signals)} 个信号")

    # Phase 8: 股价联动分析
    print("[INFO] Phase 8: 计算日线股价联动...")
    linkage_analysis = calculate_daily_linkage(registry, market_df, trade_date)
    print(f"[OK] 日线股价联动完成: 状态={linkage_analysis.status}")

    # Phase 9: 输出
    print("[INFO] Phase 9: 写入输出文件...")
    output_dir = Path(f"data/output/{trade_date}")
    snapshot = write_all(
        registry,
        pool_states,
        anchor_positions,
        group_rotation,
        signal_result,
        market_data_dict,
        output_dir,
        linkage_analysis,
    )
    print(f"[OK] 输出写入完成: {output_dir}")

    print(f"\n[OK] 分析完成!")
    print(f"  - JSON: {output_dir}/industry_snapshot.json")
    print(f"  - CSV:  {output_dir}/peer_matrix.csv")
    print(f"  - MD:   {output_dir}/industry_report.md")

    return {
        "trade_date": trade_date,
        "output_dir": str(output_dir),
        "snapshot": snapshot,
    }


def _get_latest_trade_date(market_df: pd.DataFrame) -> str:
    """获取最新交易日"""
    latest = market_df["trade_date"].max()
    return latest.strftime("%Y%m%d")


def _build_member_data_dict(
    market_df: pd.DataFrame,
    daily_basic_df: Optional[pd.DataFrame],
    moneyflow_df: Optional[pd.DataFrame],
    trade_date: str,
    registry: PoolRegistry,
) -> dict[str, MemberData]:
    """
    构建 MemberData 字典

    Args:
        market_df: 日线行情 DataFrame
        daily_basic_df: 估值/换手率 DataFrame（可选）
        moneyflow_df: 资金流向 DataFrame（可选）
        trade_date: 交易日期 YYYYMMDD
        registry: PoolRegistry（获取所有成员 symbols）

    Returns:
        symbol -> MemberData
    """
    date_dt = pd.to_datetime(trade_date, format="%Y%m%d")

    # 获取所有需要数据的 symbols
    all_symbols = registry.get_all_symbols()

    result = {}

    for symbol in all_symbols:
        # 从 market_df 获取当日行情
        day_data = market_df[
            (market_df["ts_code"] == symbol) &
            (market_df["trade_date"] == date_dt)
        ]

        if day_data.empty:
            # 数据缺失，标记无效
            result[symbol] = MemberData(
                symbol=symbol,
                trade_date=trade_date,
                close=0.0,
                pct_chg=None,
                amount=None,
                turnover_rate=None,
                net_mf_amount=None,
                is_valid=False,
                invalid_reason="missing",
            )
            continue

        row = day_data.iloc[0]
        close = row["close"]
        amount = row.get("amount")

        # 计算涨跌幅（需要前一日收盘价）
        pct_chg = _calculate_pct_chg(market_df, symbol, date_dt)

        # 获取换手率（从 daily_basic）
        turnover_rate = None
        if daily_basic_df is not None and not daily_basic_df.empty:
            basic_row = daily_basic_df[
                (daily_basic_df["ts_code"] == symbol) &
                (daily_basic_df["trade_date"] == date_dt)
            ]
            if not basic_row.empty:
                turnover_rate = basic_row.iloc[0].get("turnover_rate")

        # 获取资金净流入（从 moneyflow）
        net_mf_amount = None
        if moneyflow_df is not None and not moneyflow_df.empty:
            mf_row = moneyflow_df[
                (moneyflow_df["ts_code"] == symbol) &
                (moneyflow_df["trade_date"] == date_dt)
            ]
            if not mf_row.empty:
                net_mf_amount = mf_row.iloc[0].get("net_mf_amount")

        # 判断有效性
        is_valid = pct_chg is not None
        invalid_reason = None if is_valid else "no_pct_chg"

        result[symbol] = MemberData(
            symbol=symbol,
            trade_date=trade_date,
            close=close,
            pct_chg=pct_chg,
            amount=amount,
            turnover_rate=turnover_rate,
            net_mf_amount=net_mf_amount,
            is_valid=is_valid,
            invalid_reason=invalid_reason,
        )

    return result


def _calculate_pct_chg(
    market_df: pd.DataFrame,
    symbol: str,
    date_dt: pd.Timestamp,
) -> Optional[float]:
    """计算涨跌幅"""
    # 获取当日数据
    today_data = market_df[
        (market_df["ts_code"] == symbol) &
        (market_df["trade_date"] == date_dt)
    ]

    if today_data.empty:
        return None

    today_close = today_data.iloc[0]["close"]

    # 获取前一日数据
    prev_data = market_df[
        (market_df["ts_code"] == symbol) &
        (market_df["trade_date"] < date_dt)
    ].sort_values("trade_date", ascending=False)

    if prev_data.empty:
        return None

    prev_close = prev_data.iloc[0]["close"]

    if prev_close == 0:
        return None

    pct_chg = (today_close - prev_close) / prev_close * 100
    return pct_chg


def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(description="AnchorLink 每日分析")
    parser.add_argument("--date", help="分析日期 (YYYYMMDD)", default=None)
    args = parser.parse_args()

    try:
        result = run_daily_analysis(args.date)
        return 0
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1


if __name__ == "__main__":
    exit(main())
