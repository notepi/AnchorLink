"""
多池排名计算模块

职责：
  - 获取 ranking_scope 成员数据
  - 计算五个排名维度
  - 计算估值分位（仅 direct_peers）

排名维度：
  1. 涨幅排名（rank_return）
  2. 成交额排名（rank_volume）
  3. 换手率排名（rank_turnover）
  4. 资金净流入排名（rank_fund）
  5. 估值分位（valuation_percentile）

排名规则：
  - 降序排名（值越大排名越高，1 = 第一名）
  - 使用 ranking_scope 成员（include_anchor=True）
  - 过滤 None 值
"""

from typing import Optional

from src.config.loader import PoolRegistry
from src.pool_state.models import MemberData


class RankingCalculator:
    """
    排名计算器

    计算 Anchor 在各池子中的排名位置
    """

    def __init__(self, registry: PoolRegistry):
        self.registry = registry

    def calculate_ranks(
        self,
        universe_id: str,
        trade_date: str,
        anchor_data: MemberData,
        market_data: dict[str, MemberData],
    ) -> dict:
        """
        计算 Anchor 在指定池子中的排名

        Args:
            universe_id: 池子ID
            trade_date: 交易日期
            anchor_data: Anchor 当日数据
            market_data: symbol -> MemberData（其他成员数据）

        Returns:
            {
                "rank_return": int,
                "rank_volume": int,
                "rank_turnover": int,
                "rank_fund": int,
                "total_count": int,
                "valuation_percentile": Optional[float],
            }
        """
        # 1. 获取 ranking_scope 成员（包含 Anchor）
        ranking_symbols = self.registry.get_ranking_scope(universe_id, include_anchor=True)

        # 2. 构建排名数据集（包含 Anchor）
        members_data = self._build_ranking_dataset(
            ranking_symbols, anchor_data, market_data
        )

        if not members_data:
            return self._empty_ranking_result()

        # 3. 计算各维度排名
        rank_return = self._calculate_rank(
            members_data, "pct_chg", anchor_data.symbol, descending=True
        )
        rank_volume = self._calculate_rank(
            members_data, "amount", anchor_data.symbol, descending=True
        )
        rank_turnover = self._calculate_rank(
            members_data, "turnover_rate", anchor_data.symbol, descending=True
        )
        rank_fund = self._calculate_rank(
            members_data, "net_mf_amount", anchor_data.symbol, descending=True
        )

        # 4. 计算估值分位（仅 direct_peers）
        valuation_percentile = None
        if universe_id == "direct_peers":
            valuation_percentile = self._calculate_valuation_percentile(
                anchor_data, market_data, ranking_symbols
            )

        return {
            "rank_return": rank_return,
            "rank_volume": rank_volume,
            "rank_turnover": rank_turnover,
            "rank_fund": rank_fund,
            "total_count": len(members_data),
            "valuation_percentile": valuation_percentile,
        }

    def _build_ranking_dataset(
        self,
        ranking_symbols: list[str],
        anchor_data: MemberData,
        market_data: dict[str, MemberData],
    ) -> list[dict]:
        """
        构建排名数据集

        Args:
            ranking_symbols: ranking_scope symbol 列表
            anchor_data: Anchor 数据
            market_data: 其他成员数据

        Returns:
            [{"symbol": str, "pct_chg": float, ...}, ...]
        """
        dataset = []

        for symbol in ranking_symbols:
            if symbol == anchor_data.symbol:
                # 使用 Anchor 数据
                data = {
                    "symbol": symbol,
                    "pct_chg": anchor_data.pct_chg,
                    "amount": anchor_data.amount,
                    "turnover_rate": anchor_data.turnover_rate,
                    "net_mf_amount": anchor_data.net_mf_amount,
                }
            else:
                # 使用 market_data
                member_data = market_data.get(symbol)
                if member_data is None:
                    continue
                data = {
                    "symbol": symbol,
                    "pct_chg": member_data.pct_chg,
                    "amount": member_data.amount,
                    "turnover_rate": member_data.turnover_rate,
                    "net_mf_amount": member_data.net_mf_amount,
                }

            dataset.append(data)

        return dataset

    def _calculate_rank(
        self,
        dataset: list[dict],
        field: str,
        anchor_symbol: str,
        descending: bool = True,
    ) -> int:
        """
        计算单维度排名

        Args:
            dataset: 排名数据集
            field: 排名字段（如 pct_chg, amount）
            anchor_symbol: Anchor symbol
            descending: 是否降序（True = 值越大排名越高）

        Returns:
            Anchor 的排名（1 = 最高），无有效数据时返回 0

        Note:
            - 过滤 None 值
            - 相同值按并列排名处理
        """
        # 过滤有效数据
        valid_data = [
            (d["symbol"], d.get(field))
            for d in dataset
            if d.get(field) is not None
        ]

        if not valid_data:
            return 0

        # 排序
        if descending:
            sorted_data = sorted(valid_data, key=lambda x: x[1], reverse=True)
        else:
            sorted_data = sorted(valid_data, key=lambda x: x[1])

        # 找到 Anchor 的值
        anchor_value = None
        for symbol, value in valid_data:
            if symbol == anchor_symbol:
                anchor_value = value
                break

        if anchor_value is None:
            return 0

        # 计算排名（并列处理：相同值取第一个出现的排名）
        rank = 1
        for i, (symbol, value) in enumerate(sorted_data):
            # 先更新 rank（处理并列）
            if i > 0 and sorted_data[i - 1][1] != value:
                rank = i + 1
            # 再检查是否为 anchor
            if value == anchor_value:
                return rank

        return rank

    def _calculate_valuation_percentile(
        self,
        anchor_data: MemberData,
        market_data: dict[str, MemberData],
        ranking_symbols: list[str],
    ) -> Optional[float]:
        """
        计算估值分位（仅 direct_peers）

        Args:
            anchor_data: Anchor 数据
            market_data: 其他成员数据
            ranking_symbols: ranking_scope symbols

        Returns:
            估值分位（0-100），None 表示无法计算

        Note:
            - 当前 MemberData 不含估值数据（pe/pb）
            - 后续版本需要扩展 MemberData 或在此处单独获取 daily_basic
        """
        # 当前 MemberData 不含估值数据，返回 None
        # TODO: 后续版本扩展 MemberData 添加 pe/pb 字段
        return None

    def _empty_ranking_result(self) -> dict:
        """返回空排名结果"""
        return {
            "rank_return": 0,
            "rank_volume": 0,
            "rank_turnover": 0,
            "rank_fund": 0,
            "total_count": 0,
            "valuation_percentile": None,
        }