"""
Pool State 数据模型

定义 PoolState 层的核心数据结构，基于 architecture.md 第 6 节

数据类：
  - PoolState: 池子状态（包含所有指标）
  - MemberData: 成员当日数据（用于计算）
  - PoolStateResult: 计算结果容器
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class PoolState:
    """
    池子状态 - 按 architecture.md 第 6 节定义

    包含：
      - 计数指标（口径分离）
      - 价格类指标
      - 成交类指标
      - 资金类指标
      - 数据质量状态
    """

    # 基础标识
    universe_id: str
    trade_date: str  # YYYYMMDD 格式

    # 计数指标（口径分离）
    configured_count: int      # 配置成员数（所有 membership）
    enabled_count: int         # 启用成员数（enabled=true）
    benchmark_count: int       # 可参与 benchmark 数（enabled + include_in_benchmark）
    valid_count: int           # 当日有效数据数（有涨跌幅且正常交易）

    # 价格类指标（基于 benchmark_scope + valid 数据）
    median_return: Optional[float]   # 中位数涨跌幅（%）
    mean_return: Optional[float]     # 平均涨跌幅（%）
    up_ratio: Optional[float]        # 上涨比例（0-1）
    strong_count: int                # 强势股数量（涨幅 > 强势阈值）
    weak_count: int                  # 弱势股数量（涨幅 < 弱势阈值）

    # 成交类指标
    volume_multiplier: Optional[float]  # 成交额放大倍数（相对历史均值）

    # 资金类指标
    fund_positive_ratio: Optional[float]  # 资金净流入为正比例（0-1）

    # 数据质量
    data_status: str  # "ok" | "insufficient_data" | "partial"
    missing_members: list[str] = field(default_factory=list)  # 缺失数据的 symbol 列表
    partial_reason: Optional[str] = None  # partial 状态的原因说明


@dataclass(frozen=True)
class MemberData:
    """
    成员当日数据（用于计算）

    包含当日行情、成交、资金数据，以及有效性标记
    """

    symbol: str
    trade_date: str

    # 价格数据
    close: float
    pct_chg: Optional[float]  # 涨跌幅（%）

    # 成交数据
    amount: Optional[float]    # 成交额（千元）
    turnover_rate: Optional[float]  # 换手率（%）

    # 资金数据
    net_mf_amount: Optional[float]  # 资金净流入（元）

    # 数据有效性标记
    is_valid: bool  # 是否有效（正常交易且有涨跌幅）
    invalid_reason: Optional[str] = None  # 无效原因（停牌/缺失/无涨跌幅）


@dataclass(frozen=True)
class PoolStateResult:
    """
    池子状态计算结果（包含所有池子）

    作为 calculator.calculate() 的返回值
    """

    trade_date: str
    anchor_symbol: str
    pool_states: dict[str, PoolState]  # universe_id -> PoolState
    overall_status: str  # "ok" | "error" | "partial"
    errors: list[str] = field(default_factory=list)