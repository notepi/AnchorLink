"""
信号标签规则定义

定义 5 类 35+ 个标签的判断规则：
  - 阈值常量
  - 置信度计算参数

按 implementation.md Phase 5 设计
"""

# ============================================================
# Beta 类阈值（行业 Beta）
# ============================================================

BETA_POSITIVE_THRESHOLD = 0.5      # median_return > 0.5% → 行业Beta为正
BETA_NEGATIVE_THRESHOLD = -0.5     # median_return < -0.5% → 行业Beta为负

DIFFUSION_ENHANCE_THRESHOLD = 0.70  # up_ratio > 70% → 行业扩散增强
DIFFUSION_INSUFFICIENT_THRESHOLD = 0.30  # up_ratio < 30% → 行业扩散不足

DIVERGENCE_STRONG_THRESHOLD = 3    # 强势股 >= 3 → 行业分化明显
DIVERGENCE_WEAK_THRESHOLD = 3      # 弱势股 >= 3 → 行业分化明显


# ============================================================
# Alpha 类阈值（个股 Alpha）
# ============================================================

ALPHA_POSITIVE_THRESHOLD = 0.5     # relative_strength > 0.5% → 个股Alpha为正
ALPHA_NEGATIVE_THRESHOLD = -0.5    # relative_strength < -0.5% → 个股Alpha为负

OUTPERFORM_RANK_THRESHOLD = 0.30   # rank_percentile < 30% → 处于行业前排
UNDERPERFORM_RANK_THRESHOLD = 0.70  # rank_percentile > 70% → 处于行业后排


# ============================================================
# Volume 类阈值（资金成交）
# ============================================================

VOLUME_HIGH_THRESHOLD = 1.5        # volume_multiplier > 1.5 → 放量
VOLUME_LOW_THRESHOLD = 0.7         # volume_multiplier < 0.7 → 缩量

FUND_LEAD_THRESHOLD = 0.60         # fund_positive_ratio > 60% → 主力资金领先
FUND_DRAG_THRESHOLD = 0.40         # fund_positive_ratio < 40% → 主力资金拖累


# ============================================================
# Rotation 类阈值（组间轮动）
# ============================================================

ROTATION_SPREAD_THRESHOLD = 1.0    # spread > 1% → 明显轮动
ROTATION_STRONG_THRESHOLD = 0.5    # spread > 0.5% → 轻微轮动

TRADING_POOL_HEAT_THRESHOLD = 0.5  # trading_pool median > 0.5% → 交易观察池升温


# ============================================================
# Abnormal 类阈值（联动背离）
# ============================================================

ABNORMAL_SPREAD_THRESHOLD = 2.0    # spread > 2% → 明显背离
ABNORMAL_MODERATE_THRESHOLD = 1.0  # spread > 1% → 中度背离


# ============================================================
# 置信度计算参数
# ============================================================

# 置信度 = 满足条件的强度
# high:   远超阈值（超过阈值 2 倍以上）
# medium: 明显满足（超过阈值 1-2 倍）
# low:    刚好满足（超过阈值 0-1 倍）

CONFIDENCE_HIGH_MULTIPLIER = 2.0
CONFIDENCE_MEDIUM_MULTIPLIER = 1.0


# ============================================================
# 数据质量阈值
# ============================================================

MIN_VALID_GROUPS = 2               # 组间轮动最少有效池子数
MIN_POOL_MEMBERS = 3               # 池子最少有效成员数