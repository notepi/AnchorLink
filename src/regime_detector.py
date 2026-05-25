"""
Regime 检测模块

基于 ADX 的市场状态分类：
- mean_reverting (ADX<=20): 均值回归，买入阈值=3
- trending (ADX>=25): 趋势市，买入阈值=4
- transition (20<ADX<25): 过渡期，买入阈值=4

阈值来源：analysis_framework.md 4.2 节
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegimeInfo:
    adx: float | None
    regime: str  # "mean_reverting" | "trending" | "transition"
    thresholdBuy: int
    thresholdSell: int


def classify_regime(adx: float | None) -> RegimeInfo:
    if adx is None:
        return RegimeInfo(adx=None, regime="transition", thresholdBuy=4, thresholdSell=-3)
    if adx <= 20:
        return RegimeInfo(adx=adx, regime="mean_reverting", thresholdBuy=3, thresholdSell=-2)
    if adx >= 25:
        return RegimeInfo(adx=adx, regime="trending", thresholdBuy=4, thresholdSell=-3)
    return RegimeInfo(adx=adx, regime="transition", thresholdBuy=4, thresholdSell=-3)
