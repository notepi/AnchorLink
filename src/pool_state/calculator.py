"""
Pool State 计算主入口

职责：
  - 协调市场数据加载和池子状态计算
  - 遍历所有 universes，调用 benchmark.py 计算指标
  - 调用 quality.py 检查数据质量
  - 返回 PoolStateResult

流程：
  1. 加载 PoolRegistry（配置）
  2. 加载市场数据（market_data / daily_basic / moneyflow）
  3. 对每个 universe：
     a. 获取 benchmark_scope 成员
     b. 过滤当日有效数据
     c. 计算池子指标
     d. 检查数据质量
  4. 返回所有池子状态
"""

from typing import Optional
import pandas as pd

from src.config.loader import PoolRegistry
from src.pool_state.models import PoolState, PoolStateResult, MemberData
from src.pool_state.benchmark import (
    calculate_median_return,
    calculate_mean_return,
    calculate_up_ratio,
    calculate_volume_multiplier,
    calculate_fund_positive_ratio,
    calculate_strong_weak_count,
)
from src.pool_state.quality import (
    determine_data_status,
)


class PoolStateCalculator:
    """池子状态计算器"""

    # 强势/弱势阈值（可配置）
    STRONG_THRESHOLD = 3.0   # 涨幅 > 3% 为强势
    WEAK_THRESHOLD = -3.0    # 涨幅 < -3% 为弱势

    # 成交额历史回溯天数
    VOLUME_LOOKBACK_DAYS = 20

    def __init__(
        self,
        registry: PoolRegistry,
        market_data: pd.DataFrame,
        daily_basic: Optional[pd.DataFrame] = None,
        moneyflow: Optional[pd.DataFrame] = None,
    ):
        """
        初始化计算器

        Args:
            registry: PoolRegistry 配置注册表
            market_data: 日线行情数据（必须包含 ts_code, trade_date, close, amount）
            daily_basic: 估值/换手率数据（可选）
            moneyflow: 资金流向数据（可选）
        """
        self.registry = registry
        self.market_data = market_data
        self.daily_basic = daily_basic
        self.moneyflow = moneyflow

    def calculate(self, trade_date: str) -> PoolStateResult:
        """
        计算指定日期的所有池子状态

        Args:
            trade_date: 交易日期，格式 YYYYMMDD

        Returns:
            PoolStateResult 包含所有池子状态
        """
        pool_states = {}
        errors = []

        for universe in self.registry.get_all_universes():
            try:
                state = self._calculate_universe_state(universe.universe_id, trade_date)
                pool_states[universe.universe_id] = state
            except Exception as e:
                errors.append(f"{universe.universe_id}: {str(e)}")

        # 确定整体状态
        overall_status = self._determine_overall_status(pool_states, errors)

        return PoolStateResult(
            trade_date=trade_date,
            anchor_symbol=self.registry.get_anchor().symbol,
            pool_states=pool_states,
            overall_status=overall_status,
            errors=errors,
        )

    def _calculate_universe_state(self, universe_id: str, trade_date: str) -> PoolState:
        """计算单个池子的状态"""

        # 1. 获取 benchmark_scope 成员
        benchmark_members = self.registry.get_benchmark_scope(universe_id)
        universe = self.registry.get_universe(universe_id)

        if universe is None:
            raise ValueError(f"Universe not found: {universe_id}")

        # 2. 统计计数
        all_members = self.registry.get_members(universe_id, enabled_only=False)
        enabled_members = self.registry.get_members(universe_id, enabled_only=True)

        configured_count = len(all_members)
        enabled_count = len(enabled_members)
        benchmark_count = len(benchmark_members)

        # 3. 获取成员当日数据
        member_data_list = self._get_member_data(benchmark_members, trade_date)

        # 4. 分离有效/无效数据
        valid_data = [m for m in member_data_list if m.is_valid]
        invalid_data = [m for m in member_data_list if not m.is_valid]

        valid_count = len(valid_data)
        missing_members = [m.symbol for m in invalid_data]

        # 5. 计算价格类指标（仅有效数据）
        median_return = calculate_median_return(valid_data)
        mean_return = calculate_mean_return(valid_data)
        up_ratio = calculate_up_ratio(valid_data)
        strong_count, weak_count = calculate_strong_weak_count(
            valid_data,
            strong_threshold=self.STRONG_THRESHOLD,
            weak_threshold=self.WEAK_THRESHOLD,
        )

        # 6. 计算成交类指标
        volume_multiplier = calculate_volume_multiplier(
            valid_data,
            self.market_data,
            lookback_days=self.VOLUME_LOOKBACK_DAYS,
        )

        # 7. 计算资金类指标
        fund_positive_ratio = calculate_fund_positive_ratio(valid_data)

        # 8. 数据质量检查
        has_price_data = len(valid_data) > 0
        has_fund_data = any(m.net_mf_amount is not None for m in valid_data)

        data_status, partial_reason = determine_data_status(
            valid_count=valid_count,
            min_size=universe.min_size,
            has_price_data=has_price_data,
            has_fund_data=has_fund_data,
        )

        return PoolState(
            universe_id=universe_id,
            trade_date=trade_date,
            configured_count=configured_count,
            enabled_count=enabled_count,
            benchmark_count=benchmark_count,
            valid_count=valid_count,
            median_return=median_return,
            mean_return=mean_return,
            up_ratio=up_ratio,
            strong_count=strong_count,
            weak_count=weak_count,
            volume_multiplier=volume_multiplier,
            fund_positive_ratio=fund_positive_ratio,
            data_status=data_status,
            missing_members=missing_members,
            partial_reason=partial_reason,
        )

    def _get_member_data(
        self,
        members: list,
        trade_date: str
    ) -> list[MemberData]:
        """获取成员当日数据"""

        result = []
        date_dt = pd.to_datetime(trade_date, format="%Y%m%d")

        for member in members:
            symbol = member.symbol

            # 从 market_data 获取当日行情
            day_data = self.market_data[
                (self.market_data["ts_code"] == symbol) &
                (self.market_data["trade_date"] == date_dt)
            ]

            if day_data.empty:
                # 数据缺失
                result.append(MemberData(
                    symbol=symbol,
                    trade_date=trade_date,
                    close=0.0,
                    pct_chg=None,
                    amount=None,
                    turnover_rate=None,
                    net_mf_amount=None,
                    is_valid=False,
                    invalid_reason="missing",
                ))
                continue

            row = day_data.iloc[0]

            # 计算涨跌幅（需要前一日收盘价）
            pct_chg = self._calculate_pct_chg(symbol, trade_date)

            if pct_chg is None:
                result.append(MemberData(
                    symbol=symbol,
                    trade_date=trade_date,
                    close=row["close"],
                    pct_chg=None,
                    amount=row.get("amount"),
                    turnover_rate=None,
                    net_mf_amount=None,
                    is_valid=False,
                    invalid_reason="no_pct_chg",
                ))
                continue

            # 获取换手率（从 daily_basic）
            turnover_rate = self._get_turnover_rate(symbol, trade_date)

            # 获取资金净流入（从 moneyflow）
            net_mf_amount = self._get_net_mf_amount(symbol, trade_date)

            result.append(MemberData(
                symbol=symbol,
                trade_date=trade_date,
                close=row["close"],
                pct_chg=pct_chg,
                amount=row.get("amount"),
                turnover_rate=turnover_rate,
                net_mf_amount=net_mf_amount,
                is_valid=True,
                invalid_reason=None,
            ))

        return result

    def _calculate_pct_chg(self, symbol: str, trade_date: str) -> Optional[float]:
        """计算涨跌幅（需要前一日收盘价）"""

        date_dt = pd.to_datetime(trade_date, format="%Y%m%d")

        # 获取当日数据
        today_data = self.market_data[
            (self.market_data["ts_code"] == symbol) &
            (self.market_data["trade_date"] == date_dt)
        ]

        if today_data.empty:
            return None

        today_close = today_data.iloc[0]["close"]

        # 获取前一日数据
        prev_data = self.market_data[
            (self.market_data["ts_code"] == symbol) &
            (self.market_data["trade_date"] < date_dt)
        ].sort_values("trade_date", ascending=False)

        if prev_data.empty:
            return None

        prev_close = prev_data.iloc[0]["close"]

        if prev_close == 0:
            return None

        pct_chg = (today_close - prev_close) / prev_close * 100
        return pct_chg

    def _get_turnover_rate(self, symbol: str, trade_date: str) -> Optional[float]:
        """获取换手率"""

        if self.daily_basic is None or self.daily_basic.empty:
            return None

        date_dt = pd.to_datetime(trade_date, format="%Y%m%d")

        data = self.daily_basic[
            (self.daily_basic["ts_code"] == symbol) &
            (self.daily_basic["trade_date"] == date_dt)
        ]

        if data.empty:
            return None

        return data.iloc[0].get("turnover_rate")

    def _get_net_mf_amount(self, symbol: str, trade_date: str) -> Optional[float]:
        """获取资金净流入"""

        if self.moneyflow is None or self.moneyflow.empty:
            return None

        date_dt = pd.to_datetime(trade_date, format="%Y%m%d")

        data = self.moneyflow[
            (self.moneyflow["ts_code"] == symbol) &
            (self.moneyflow["trade_date"] == date_dt)
        ]

        if data.empty:
            return None

        return data.iloc[0].get("net_mf_amount")

    def _determine_overall_status(
        self,
        pool_states: dict[str, PoolState],
        errors: list[str]
    ) -> str:
        """确定整体状态"""

        if errors:
            return "error"

        # 如果任何 benchmark 池子数据不足，整体状态为 partial
        benchmark_universes = [
            uid for uid, uni in self.registry._config.universes.items()
            if uni.can_be_benchmark
        ]

        for uid in benchmark_universes:
            if uid in pool_states and pool_states[uid].data_status != "ok":
                return "partial"

        return "ok"