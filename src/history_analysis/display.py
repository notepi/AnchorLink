"""历史分析展示口径工具。"""

SIGNAL_LABEL_DISPLAY_MAP = {
    "主线池强于主题情绪": "核心池强于主题",
    "主题情绪强于主线池": "主题强于核心池",
    "交易观察池升温": "交易池升温",
    "交易观察池降温": "交易池降温",
    "跑赢主线池": "跑赢核心池",
    "跑输主线池": "跑输核心池",
}


def format_signal_label(label: str) -> str:
    """返回前端展示用信号名，计算仍保留原始 label。"""
    return SIGNAL_LABEL_DISPLAY_MAP.get(label, label)


def business_tag_for_label(label: str, category: str = "") -> str:
    """粗粒度业务标签，只作为辅助展示，不作为主分组。"""
    if label in {"放量上涨", "放量下跌", "主力资金领先", "资金价格共振", "资金价格背离"}:
        return "资金验证"
    if label in {"行业Beta为正", "行业Beta为负", "个股Alpha为正", "个股Alpha为负"}:
        return "趋势跟随"
    if "强但" in label or "弱但" in label or "背离" in label:
        return "异常反证"
    if "主题" in label or "交易" in label:
        return "情绪背景"
    if "跑赢" in label or "跑输" in label or "前排" in label:
        return "相对强弱"
    return category or "其他"
