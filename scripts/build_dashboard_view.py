#!/usr/bin/env python3
"""
Build data/output/dashboard_view.json for /history-v2.

The v2 page is driven by one stable contract:
- CSV rows are stored in ascending date order.
- Every date field is emitted as a YYYYMMDD string.
- The current trading day is max(history_summary.date), not the first CSV row.
- State transitions use stable keys such as positive+negative, with labels
  carried separately for display.
"""
from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from statistics import mean
from typing import Any

import pandas as pd
import yaml


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "output")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "pools.yaml")
OUTPUT_PATH = os.path.join(DATA_OUTPUT_DIR, "dashboard_view.json")

DATE_FIELDS = {"date", "event_date", "as_of_date", "date_range_start", "date_range_end"}

BETA_ORDER = ["positive", "neutral", "negative"]
RISK_ORDER = ["low", "medium", "high"]
BETA_TEXT = {"positive": "偏强", "neutral": "中性", "negative": "偏弱"}
RISK_TEXT = {"low": "低风险", "medium": "中风险", "high": "高风险"}

STATE_ORDER = [
    "positive+positive",
    "positive+neutral",
    "positive+negative",
    "neutral+positive",
    "neutral+neutral",
    "neutral+negative",
    "negative+positive",
    "negative+neutral",
    "negative+negative",
]
STATE_CHAR = {"positive": "强", "neutral": "中", "negative": "弱"}
CHAR_STATE = {"强": "positive", "中": "neutral", "弱": "negative"}
STATE_LABELS = {
    key: f"行业{STATE_CHAR[key.split('+')[0]]}+个股{STATE_CHAR[key.split('+')[1]]}"
    for key in STATE_ORDER
}
STATE_SHORT_LABELS = {
    key: f"{STATE_CHAR[key.split('+')[0]]}+{STATE_CHAR[key.split('+')[1]]}"
    for key in STATE_ORDER
}
STATE_LABEL_TO_KEY = {value: key for key, value in STATE_LABELS.items()}

PATH_LABELS = {
    "strong_rise",
    "pullback_after_rise",
    "continue_fall",
    "weak_repair",
    "range_bound",
    "disagreement",
    "unknown",
}


def parse_scalar(key: str, value: str | None) -> Any:
    if value is None or value == "":
        return None
    if key in DATE_FIELDS:
        return str(value).strip()
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    return int(number) if number.is_integer() else number


def read_csv(file_name: str) -> list[dict[str, Any]]:
    file_path = os.path.join(DATA_OUTPUT_DIR, file_name)
    if not os.path.exists(file_path):
        print(f"警告：文件不存在 {file_path}")
        return []

    rows: list[dict[str, Any]] = []
    with open(file_path, "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append({key: parse_scalar(key, value) for key, value in row.items()})

    if rows and "date" in rows[0]:
        rows.sort(key=lambda row: str(row.get("date") or ""))
    if rows and "event_date" in rows[0]:
        rows.sort(key=lambda row: (str(row.get("event_date") or ""), int(row.get("offset") or 0)))
    return rows


def read_json(file_name: str) -> dict[str, Any]:
    file_path = os.path.join(DATA_OUTPUT_DIR, file_name)
    if not os.path.exists(file_path):
        print(f"警告：文件不存在 {file_path}")
        return {}

    with open(file_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_yaml(file_path: str) -> dict[str, Any]:
    if not os.path.exists(file_path):
        print(f"警告：文件不存在 {file_path}")
        return {}

    with open(file_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def format_date(value: Any, format_type: str = "normal") -> str:
    text = "" if value is None else str(value)
    if len(text) != 8:
        return text
    formatted = f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return f"{formatted} 18:00" if format_type == "full" else formatted


def latest_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[-1] if rows else {}


def last_n(rows: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    return rows[-n:] if len(rows) > n else rows[:]


def camel_key(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def camelize(value: Any) -> Any:
    if isinstance(value, list):
        return [camelize(item) for item in value]
    if isinstance(value, dict):
        return {camel_key(str(key)): camelize(item) for key, item in value.items()}
    return value


def split_signals(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def normalize_state(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if text in STATE_ORDER:
        return text
    if text in STATE_LABEL_TO_KEY:
        return STATE_LABEL_TO_KEY[text]
    for label, key in STATE_LABEL_TO_KEY.items():
        if label.replace("行业", "").replace("个股", "") == text:
            return key
    if "+" in text:
        left, right = [part.strip() for part in text.split("+", 1)]
        left_char = left.replace("行业", "").replace("主线", "").replace("池", "")
        right_char = right.replace("个股", "").replace("标的", "")
        if left_char in CHAR_STATE and right_char in CHAR_STATE:
            return f"{CHAR_STATE[left_char]}+{CHAR_STATE[right_char]}"
    return "neutral+neutral"


def state_key_from_row(row: dict[str, Any]) -> str:
    industry = row.get("industry_beta") or "neutral"
    anchor = row.get("anchor_alpha") or "neutral"
    key = f"{industry}+{anchor}"
    return key if key in STATE_ORDER else "neutral+neutral"


def state_label(key: str) -> str:
    return STATE_LABELS.get(normalize_state(key), "行业中+个股中")


def state_short_label(key: str) -> str:
    return STATE_SHORT_LABELS.get(normalize_state(key), "中+中")


def avg(values: list[Any]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return mean(clean) if clean else None


def win_rate(values: list[Any]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return len([value for value in clean if value > 0]) / len(clean) if clean else None


def _weighted_avg(values: list[float], weights: list[float]) -> float | None:
    if not values or not weights or len(values) != len(weights):
        return None
    total_w = sum(weights)
    return sum(v * w for v, w in zip(values, weights)) / total_w if total_w > 0 else None


def _weighted_win_rate(values: list[float], weights: list[float]) -> float | None:
    if not values or not weights or len(values) != len(weights):
        return None
    total_w = sum(weights)
    return sum(w for v, w in zip(values, weights) if v > 0) / total_w if total_w > 0 else None


def _ordinal_score(a: Any, b: Any, order: list[str]) -> float:
    if not a or not b:
        return 0.0
    aa = str(a).strip().lower()
    bb = str(b).strip().lower()
    if aa not in order or bb not in order:
        return 1.0 if aa == bb else 0.0
    distance = abs(order.index(aa) - order.index(bb))
    return 1.0 if distance == 0 else 0.5 if distance == 1 else 0.0


def _exact_score(a: Any, b: Any) -> float:
    if not a or not b:
        return 0.0
    return 1.0 if str(a).strip().lower() == str(b).strip().lower() else 0.0


# ==============================
# 今日看板 - 辅助函数
# ==============================

def compute_percentiles_inplace(values: list[Any]) -> list[int | None]:
    """对每个 value 计算它在非 None 子集里的百分位（0-100 整数）。"""
    valid = [(i, float(v)) for i, v in enumerate(values) if v is not None]
    if not valid:
        return [None] * len(values)
    sorted_vals = sorted(v for _, v in valid)
    n = len(sorted_vals)
    result: list[int | None] = [None] * len(values)
    for i, v in valid:
        below = sum(1 for x in sorted_vals if x < v)
        result[i] = round(below / n * 100)
    return result


def pearson_corr(a: list[Any], b: list[Any]) -> float | None:
    """Pearson 相关系数，跳过 None。"""
    pairs = [(float(x), float(y)) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    n = len(pairs)
    mean_x = sum(x for x, _ in pairs) / n
    mean_y = sum(y for _, y in pairs) / n
    sum_xy = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    sum_xx = sum((x - mean_x) ** 2 for x, _ in pairs)
    sum_yy = sum((y - mean_y) ** 2 for _, y in pairs)
    denom = (sum_xx * sum_yy) ** 0.5
    return sum_xy / denom if denom > 0 else None


def compute_rolling_corr(
    history_summary: list[dict[str, Any]],
    pool_col: str,
    window: int,
) -> list[float | None]:
    """每一行算 N 日滚动相关系数（anchor_return vs pool_col）。"""
    n = len(history_summary)
    result: list[float | None] = []
    for i in range(n):
        if i + 1 < window:
            result.append(None)
            continue
        sub = history_summary[i + 1 - window: i + 1]
        anchor_vals = [r.get("anchor_return") for r in sub]
        pool_vals = [r.get(pool_col) for r in sub]
        result.append(pearson_corr(anchor_vals, pool_vals))
    return result


POOL_COL_MAP = {
    "industry_chain_median": "industryChain",
    "direct_peers_median": "directPeers",
    "theme_pool_median": "themePool",
    "trading_watchlist_median": "tradingWatchlist",
}


def build_pool_correlations(history_summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """每日 4 池 20d/60d 滚动相关性 + 20d 百分位 + 全样本相关性。"""
    rolling_data: dict[str, dict[str, Any]] = {}
    for col, name in POOL_COL_MAP.items():
        corr_20d = compute_rolling_corr(history_summary, col, 20)
        corr_60d = compute_rolling_corr(history_summary, col, 60)
        pct_20d = compute_percentiles_inplace(corr_20d)
        anchor_all = [r.get("anchor_return") for r in history_summary]
        pool_all = [r.get(col) for r in history_summary]
        full_corr = pearson_corr(anchor_all, pool_all)
        rolling_data[name] = {
            "corr20d": corr_20d,
            "corr60d": corr_60d,
            "pct20d": pct_20d,
            "fullCorr": full_corr,
        }

    result: list[dict[str, Any]] = []
    for i, row in enumerate(history_summary):
        date = str(row.get("date") or "")
        entry: dict[str, Any] = {"date": date}
        for name, data in rolling_data.items():
            entry[name] = {
                "corr20d": data["corr20d"][i],
                "corr60d": data["corr60d"][i],
                "percentile20d": data["pct20d"][i],
                "fullCorr": data["fullCorr"],
            }
        result.append(entry)
    return result


def build_quadrant_distributions(history_summary: list[dict[str, Any]], target_date: str | None = None) -> dict[str, dict[str, Any]]:
    """每个象限的 T+1 分布：P10/P50/P90 + 胜率 + count。
    target_date: Walk-Forward，只用该日之前的数据。None 表示用全量。"""
    if target_date:
        cutoff_idx = next((i for i, r in enumerate(history_summary) if str(r.get("date")) == target_date), len(history_summary))
        rows = history_summary[:cutoff_idx]
    else:
        rows = history_summary

    quad_groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        t1 = row.get("next_1d_return")
        if t1 is None:
            continue
        key = state_key_from_row(row)
        quad_groups[key].append(float(t1))

    result: dict[str, dict[str, Any]] = {}
    for key, vals in quad_groups.items():
        if not vals:
            continue
        sorted_vals = sorted(vals)
        n = len(sorted_vals)
        p10_idx = max(0, min(n - 1, int(n * 0.1)))
        p90_idx = max(0, min(n - 1, int(n * 0.9)))
        result[key] = {
            "count": n,
            "p10": sorted_vals[p10_idx],
            "p50": sorted_vals[n // 2],
            "p90": sorted_vals[p90_idx],
            "winRate": sum(1 for v in vals if v > 0) / n,
        }
    return result


def guidance_for_winrate(wr: float | None) -> dict[str, str]:
    """4 档操作建议：好买点 / 中性 / 偏弱 / 回避。"""
    if wr is None:
        return {"tier": "neu", "icon": "⚪", "label": "无数据", "action": "观望"}
    pct = wr * 100
    if pct >= 55:
        return {"tier": "good", "icon": "🟢", "label": "好买点", "action": "关注买入"}
    if pct >= 45:
        return {"tier": "neu", "icon": "⚪", "label": "中性", "action": "持仓观望"}
    if pct >= 40:
        return {"tier": "warn", "icon": "⚠️", "label": "偏弱", "action": "暂不加仓"}
    return {"tier": "bad", "icon": "🔴", "label": "回避", "action": "不追不加"}


QUADRANT_REASONS = {
    "positive+positive": "双强已透支，trap 格",
    "positive+neutral": "个股没跟上行业，弱势",
    "positive+negative": "跑输主线，机构或在出货",
    "neutral+positive": "个股独走无行业支撑",
    "neutral+neutral": "典型平淡日，无信号",
    "neutral+negative": "历史最佳，反弹概率最高",
    "negative+positive": "没方向优势，等下次迁移",
    "negative+neutral": "最差格，无逆势能力",
    "negative+negative": "双跌反弹机会，均值回归型最佳",
}


def build_transition_top5(
    history_summary: list[dict[str, Any]],
    quadrant_dist: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """从当前状态出发的 top 5 转移目标，含目标格的胜率和操作建议。"""
    if not history_summary:
        return []
    latest = history_summary[-1]
    cur_state = state_key_from_row(latest)

    transitions: list[str] = []
    for i in range(len(history_summary) - 1):
        if state_key_from_row(history_summary[i]) == cur_state:
            transitions.append(state_key_from_row(history_summary[i + 1]))

    if not transitions:
        return []
    total = len(transitions)
    counts = Counter(transitions).most_common(5)

    result: list[dict[str, Any]] = []
    for state, count in counts:
        dist = quadrant_dist.get(state, {})
        guidance = guidance_for_winrate(dist.get("winRate"))
        result.append({
            "toState": state,
            "toStateLabel": state_label(state),
            "count": count,
            "probability": round(count / total, 3),
            "targetP50": dist.get("p50"),
            "targetWinRate": dist.get("winRate"),
            "isStay": state == cur_state,
            "guidance": guidance,
        })
    return result


POOL_ZH_NAMES = {
    "industryChain": "主线池",
    "directPeers": "同业",
    "themePool": "主题池",
    "tradingWatchlist": "高 beta 池",
}


def build_today_alerts(
    excess_return: list[dict[str, Any]],
    pool_correlations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """今天的极端位置警报（百分位 ≥ 85 或 ≤ 10）。"""
    alerts: list[dict[str, Any]] = []
    if not excess_return:
        return alerts
    latest_excess = excess_return[-1]

    # 超额过热 / 超卖
    e5_pct = latest_excess.get("excess5dPercentile")
    e5_val = latest_excess.get("excess5d")
    if e5_pct is not None and e5_val is not None:
        if e5_pct >= 90:
            alerts.append({
                "level": "warning", "icon": "⚠️",
                "text": f"5d 超额 +{e5_val:.2f}%，处于历史 P{e5_pct}（过热）",
            })
        elif e5_pct >= 85:
            alerts.append({
                "level": "warning", "icon": "⚠️",
                "text": f"5d 超额 +{e5_val:.2f}%，处于历史 P{e5_pct}（接近过热）",
            })
        elif e5_pct <= 10:
            alerts.append({
                "level": "warning", "icon": "⚠️",
                "text": f"5d 超额 {e5_val:+.2f}%，处于历史 P{e5_pct}（接近超卖）",
            })

    # 池子脱钩
    if pool_correlations:
        latest_corr = pool_correlations[-1]
        for pool_key, pool_zh in POOL_ZH_NAMES.items():
            cd = latest_corr.get(pool_key, {})
            pct = cd.get("percentile20d")
            cv = cd.get("corr20d")
            if pct is None or cv is None:
                continue
            if pct <= 5:
                alerts.append({
                    "level": "critical", "icon": "🚨",
                    "text": f"跟{pool_zh} 20d 相关性 = {cv:.2f}，处于历史 P{pct}（极端脱钩）",
                })
            elif pct <= 10:
                alerts.append({
                    "level": "critical", "icon": "🚨",
                    "text": f"跟{pool_zh} 20d 相关性 = {cv:.2f}，处于历史 P{pct}",
                })

    return alerts


def build_today_attribution(history_summary: list[dict[str, Any]]) -> dict[str, Any] | None:
    """今日归因：anchor return 拆解到 4 池 + Alpha vs 同业。"""
    if not history_summary:
        return None
    latest = history_summary[-1]
    anchor_return = latest.get("anchor_return")
    if anchor_return is None:
        return None
    return {
        "date": str(latest.get("date") or ""),
        "anchorReturn": anchor_return,
        "pools": {
            "directPeers": latest.get("direct_peers_median"),
            "industryChain": latest.get("industry_chain_median"),
            "themePool": latest.get("theme_pool_median"),
            "tradingWatchlist": latest.get("trading_watchlist_median"),
        },
        "alphaVsIndustryChain": latest.get("relative_strength_vs_industry_chain"),
        "alphaVsDirectPeers": latest.get("relative_strength_vs_direct"),
        "alphaVsThemePool": latest.get("relative_strength_vs_theme"),
        "currentQuadrant": state_key_from_row(latest),
        "currentQuadrantLabel": state_label(state_key_from_row(latest)),
    }


def build_habit_type_map(personality_profile: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for habit in classified_habits(personality_profile):
        habit_type = habit.get("habit_type")
        for key in ("label", "display_label"):
            label = habit.get(key)
            if label and habit_type:
                result[str(label)] = str(habit_type)
    return result


def classify_habit(pattern: dict[str, Any]) -> str:
    existing_type = pattern.get("habit_type")
    label = str(pattern.get("label") or "")
    category = str(pattern.get("category") or "")
    avg_return = pattern.get("avg_next_1d") or 0
    delta = pattern.get("avg_next_1d_delta_pp")

    if existing_type in {"likes", "dislikes", "counter_intuitive", "trap", "context"}:
        return str(existing_type)
    if "放量" in label:
        return "trap"
    if "背离" in label and (delta is None or delta > 0):
        return "counter_intuitive"
    if "拖累" in label and avg_return > 0:
        return "counter_intuitive"
    if category == "abnormal" and avg_return > 1:
        return "counter_intuitive"
    return "likes" if avg_return > 0 else "dislikes"


def classified_habits(personality_profile: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for pattern in personality_profile.get("habit_patterns", []):
        item = dict(pattern)
        item["habit_type"] = classify_habit(item)
        result.append(item)
    return result


def signal_group(signal: str, habit_type_map: dict[str, str]) -> str:
    habit_type = habit_type_map.get(signal)
    if habit_type == "likes":
        return "pref"
    if habit_type == "dislikes":
        return "avoid"
    if habit_type == "counter_intuitive":
        return "contra"
    if habit_type == "trap":
        return "trap"
    if any(keyword in signal for keyword in ["放量", "陷阱"]):
        return "trap"
    if any(keyword in signal for keyword in ["背离", "拖累", "反直觉"]):
        return "contra"
    if any(keyword in signal for keyword in ["跑输", "后排", "负", "降温", "弱"]):
        return "avoid"
    return "pref"


def signal_groups_for_row(row: dict[str, Any], habit_type_map: dict[str, str]) -> dict[str, list[str]]:
    groups = {"pref": [], "avoid": [], "contra": [], "trap": []}
    for signal in split_signals(row.get("signal_labels")):
        groups[signal_group(signal, habit_type_map)].append(signal)
    return groups


def load_anchor_close_prices(anchor_code: str) -> dict[str, float]:
    parquet_path = os.path.join(PROJECT_ROOT, "data", "price", "normalized", "market_data_normalized.parquet")
    if not os.path.exists(parquet_path):
        print("[WARN] 真实股价文件不存在，将使用归一化指数")
        return {}
    df = pd.read_parquet(parquet_path)
    anchor_df = df[df["ts_code"] == anchor_code]
    close_by_date: dict[str, float] = {}
    for _, row in anchor_df.iterrows():
        trade_date = str(row["trade_date"])[:10].replace("-", "")
        close_by_date[trade_date] = float(row["close"])
    print(f"[OK] 加载真实收盘价：{len(close_by_date)} 条，标的 {anchor_code}")
    return close_by_date


def load_all_data() -> dict[str, Any]:
    print("正在加载所有数据文件...")
    data = {
        "history_summary": read_csv("history_summary.csv"),
        "quadrant_stats": read_csv("history_quadrant_stats.csv"),
        "signal_lifts": read_csv("history_signal_lift.csv"),
        "extreme_divergences": read_csv("history_extreme_divergences.csv"),
        "rolling_metrics": read_csv("history_rolling_metrics.csv"),
        "state_transitions": read_csv("history_state_transitions.csv"),
        "event_study": read_csv("history_event_study.csv"),
        "operator_playbook": read_json("history_operator_playbook.json"),
        "personality_profile": read_json("history_personality_profile.json"),
        "prediction_backtest": read_json("history_prediction_backtest.json"),
        "v2_scoring": read_json("v2_scoring.json"),
        "drift_report": read_json("param_drift_report.json"),
        "config": read_yaml(CONFIG_PATH),
    }
    print(f"加载完成：共 {len(data['history_summary'])} 条 history_summary")
    print(f"加载完成：共 {len(data['rolling_metrics'])} 条 rolling_metrics")
    if data["history_summary"]:
        print(f"当前交易日：{latest_row(data['history_summary']).get('date')}")
    return data


def build_meta(personality_profile: dict[str, Any], config: dict[str, Any], history_summary: list[dict[str, Any]]) -> dict[str, Any]:
    start_date = personality_profile.get("date_range_start") or (history_summary[0].get("date") if history_summary else "")
    end_date = personality_profile.get("date_range_end") or (latest_row(history_summary).get("date") if history_summary else "")
    sample_days = personality_profile.get("sample_days") or len(history_summary)
    return {
        "dateRange": f"{start_date} ~ {end_date}",
        "dataUpdateTime": format_date(personality_profile.get("as_of_date") or end_date, "full"),
        "stockName": config.get("anchor", {}).get("name", ""),
        "stockCode": config.get("anchor", {}).get("symbol", ""),
        "sampleDays": sample_days,
        "validSampleDays": personality_profile.get("valid_sample_days", 0),
    }


def build_filter(personality_profile: dict[str, Any], history_summary: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "startDate": str(personality_profile.get("date_range_start") or (history_summary[0].get("date") if history_summary else "")),
        "endDate": str(personality_profile.get("date_range_end") or (latest_row(history_summary).get("date") if history_summary else "")),
        "signalCategory": "all",
    }


def compute_score_bucket_stats(v2_data: dict[str, Any], history_summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 V2 评分分档计算历史 T+1/T+3/T+5 统计，Walk-Forward，含状态加权"""
    daily = v2_data.get("dailyResults", [])
    if not daily:
        return []

    # history_summary 按 date 索引，用于 T+3/T+5 数据及状态
    summary_by_date: dict[str, dict[str, Any]] = {str(r.get("date")): r for r in history_summary}

    BUCKETS = [
        (-99, -8, "≤-8"),
        (-8, -5, "-7~-5"),
        (-5, -2, "-4~-2"),
        (-2, 0, "-1~0"),
        (0, 2, "+1~+2"),
        (2, 5, "+3~+5"),
        (5, 8, "+6~+7"),
        (8, 99, "≥+8"),
    ]

    def safe_float(v):
        try:
            return float(v) if v else None
        except (ValueError, TypeError):
            return None

    def _bucket_stat(exc_vals: list[float], abs_vals: list[float]) -> dict[str, Any]:
        return {
            "avgExcess": round(mean(exc_vals), 4) if exc_vals else None,
            "excessPosRate": round(sum(1 for v in exc_vals if v > 0) / len(exc_vals), 4) if exc_vals else None,
            "avgAbsReturn": round(mean(abs_vals), 4) if abs_vals else None,
            "absPosRate": round(sum(1 for v in abs_vals if v > 0) / len(abs_vals), 4) if abs_vals else None,
        }

    def _weighted_bucket_stat(exc_vals: list[float], exc_ws: list[float],
                               abs_vals: list[float], abs_ws: list[float]) -> dict[str, Any] | None:
        total_w = sum(exc_ws)
        if total_w < 2.0:
            return None
        return {
            "avgExcess": round(_weighted_avg(exc_vals, exc_ws) or 0, 4) if exc_vals else None,
            "excessPosRate": round(_weighted_win_rate(exc_vals, exc_ws) or 0, 4) if exc_vals else None,
            "avgAbsReturn": round(_weighted_avg(abs_vals, abs_ws) or 0, 4) if abs_vals else None,
            "absPosRate": round(_weighted_win_rate(abs_vals, abs_ws) or 0, 4) if abs_vals else None,
        }

    # Walk-Forward：只用 target 日之前的数据
    results = []
    for i, day in enumerate(daily):
        score = day["score"]
        bucket = None
        for lo, hi, label in BUCKETS:
            if lo <= score < hi:
                bucket = (lo, hi, label)
                break
        if bucket is None:
            continue

        lo, hi, label = bucket
        peers = [d for d in daily[:i] if lo <= d["score"] < hi and d.get("next1dExcess") is not None]
        if len(peers) < 3:
            continue

        target_state = summary_by_date.get(str(day["date"]))

        # 单次遍历收集加权数据
        exc_1d, abs_1d = [], []
        exc_3d, abs_3d, exc_5d, abs_5d = [], [], [], []
        exc_1d_w, abs_1d_w = [], []
        exc_3d_w, abs_3d_w, exc_5d_w, abs_5d_w = [], [], [], []
        peer_state_keys = []

        for p in peers:
            peer_state = summary_by_date.get(str(p["date"]))

            # 状态相似度权重
            if target_state and peer_state:
                w = (
                    _ordinal_score(target_state.get("industry_beta"), peer_state.get("industry_beta"), BETA_ORDER) * 0.35
                    + _ordinal_score(target_state.get("anchor_alpha"), peer_state.get("anchor_alpha"), BETA_ORDER) * 0.35
                    + _ordinal_score(target_state.get("risk_level"), peer_state.get("risk_level"), RISK_ORDER) * 0.30
                )
                peer_state_keys.append(state_key_from_row(peer_state))
            else:
                w = 1.0

            # T+1 从 v2_scoring
            e1 = p["next1dExcess"]
            a1 = p.get("next1dAbs")
            exc_1d.append(e1)
            exc_1d_w.append(w)
            if a1 is not None:
                abs_1d.append(a1)
                abs_1d_w.append(w)

            # T+3/T+5 从 history_summary
            if peer_state:
                v = safe_float(peer_state.get("next_3d_excess_vs_chain"))
                if v is not None:
                    exc_3d.append(v)
                    exc_3d_w.append(w)
                v = safe_float(peer_state.get("next_3d_return"))
                if v is not None:
                    abs_3d.append(v)
                    abs_3d_w.append(w)
                v = safe_float(peer_state.get("next_5d_excess_vs_chain"))
                if v is not None:
                    exc_5d.append(v)
                    exc_5d_w.append(w)
                v = safe_float(peer_state.get("next_5d_return"))
                if v is not None:
                    abs_5d.append(v)
                    abs_5d_w.append(w)

        # 状态偏离元数据
        effective_sample = round(sum(exc_1d_w), 2)
        state_divergence = round(1.0 - (sum(exc_1d_w) / len(peers)), 4) if peers else None
        dominant_state = Counter(peer_state_keys).most_common(1)[0][0] if peer_state_keys else None
        current_state = state_key_from_row(target_state) if target_state else None
        state_mismatch = (current_state != dominant_state) if (current_state and dominant_state) else None

        results.append({
            "date": day["date"],
            "score": score,
            "bucketLabel": label,
            "bucketLo": lo,
            "bucketHi": hi,
            "sampleSize": len(peers),
            "effectiveSampleSize": effective_sample,
            "stateDivergence": state_divergence,
            "dominantState": dominant_state,
            "currentState": current_state,
            "stateMismatch": state_mismatch,
            "t1": _bucket_stat(exc_1d, abs_1d),
            "t3": _bucket_stat(exc_3d, abs_3d),
            "t5": _bucket_stat(exc_5d, abs_5d),
            "stateWeightedT1": _weighted_bucket_stat(exc_1d, exc_1d_w, abs_1d, abs_1d_w),
            "stateWeightedT3": _weighted_bucket_stat(exc_3d, exc_3d_w, abs_3d, abs_3d_w),
            "stateWeightedT5": _weighted_bucket_stat(exc_5d, exc_5d_w, abs_5d, abs_5d_w),
        })

    return results


def compute_similar_cases(history_summary: list[dict[str, Any]], close_by_date: dict[str, float], target_date: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if target_date:
        target = next((r for r in history_summary if str(r.get("date")) == target_date), None)
    else:
        target = latest_row(history_summary)
    if not target:
        return [], []

    weights = {
        "industry_beta": 0.25,
        "anchor_alpha": 0.25,
        "risk_level": 0.20,
        "strongest_group": 0.15,
        "weakest_group": 0.15,
    }

    def signal_set(row: dict[str, Any]) -> set[str]:
        raw_pairs = row.get("signal_pairs")
        if raw_pairs:
            try:
                pairs = json.loads(raw_pairs)
                if isinstance(pairs, list):
                    return {
                        f"{pair.get('category', '')}::{pair.get('label', '')}"
                        for pair in pairs
                        if pair.get("label")
                    }
            except (TypeError, ValueError):
                pass
        return {f"::{signal}" for signal in split_signals(row.get("signal_labels"))}

    def jaccard(a: set[str], b: set[str]) -> float:
        union = len(a | b)
        return len(a & b) / union if union else 0.0

    def state_score(candidate: dict[str, Any]) -> float:
        return (
            _ordinal_score(target.get("industry_beta"), candidate.get("industry_beta"), BETA_ORDER) * weights["industry_beta"]
            + _ordinal_score(target.get("anchor_alpha"), candidate.get("anchor_alpha"), BETA_ORDER) * weights["anchor_alpha"]
            + _ordinal_score(target.get("risk_level"), candidate.get("risk_level"), RISK_ORDER) * weights["risk_level"]
            + _exact_score(target.get("strongest_group"), candidate.get("strongest_group")) * weights["strongest_group"]
            + _exact_score(target.get("weakest_group"), candidate.get("weakest_group")) * weights["weakest_group"]
        )

    target_signals = signal_set(target)
    # 只取目标日期之前的数据作为候选
    target_idx = next((i for i, r in enumerate(history_summary) if str(r.get("date")) == str(target.get("date"))), len(history_summary))
    candidates = [
        row
        for row in history_summary[:target_idx]
        if row.get("next_1d_return") is not None
        or row.get("next_3d_return") is not None
        or row.get("next_5d_return") is not None
    ]
    scored = []
    for candidate in candidates:
        similarity = state_score(candidate) * 0.6 + jaccard(target_signals, signal_set(candidate)) * 0.4
        scored.append((similarity, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    top_n = min(12, max(5, round(len(scored) * 0.15))) if scored else 0
    top_candidates = scored[:top_n]

    target_labels = set(split_signals(target.get("signal_labels")))
    similar_cases: list[dict[str, Any]] = []
    for similarity, row in top_candidates:
        matching_states = []
        if row.get("industry_beta") == target.get("industry_beta"):
            matching_states.append(f"行业Beta:{BETA_TEXT.get(str(row.get('industry_beta')), row.get('industry_beta'))}")
        if row.get("anchor_alpha") == target.get("anchor_alpha"):
            matching_states.append(f"个股Alpha:{BETA_TEXT.get(str(row.get('anchor_alpha')), row.get('anchor_alpha'))}")
        if row.get("risk_level") == target.get("risk_level"):
            matching_states.append(f"风险:{RISK_TEXT.get(str(row.get('risk_level')), row.get('risk_level'))}")
        if row.get("strongest_group") == target.get("strongest_group"):
            matching_states.append(f"最强组:{row.get('strongest_group')}")
        if row.get("weakest_group") == target.get("weakest_group"):
            matching_states.append(f"最弱组:{row.get('weakest_group')}")

        row_labels = set(split_signals(row.get("signal_labels")))
        matching_signals = sorted(target_labels & row_labels)
        similar_cases.append({
            "date": str(row.get("date") or ""),
            "state": f"{state_label(state_key_from_row(row))} · {RISK_TEXT.get(str(row.get('risk_level')), row.get('risk_level'))}",
            "next1dReturn": row.get("next_1d_return"),
            "next3dReturn": row.get("next_3d_return"),
            "next5dReturn": row.get("next_5d_return"),
            "similarity": round(similarity, 2),
            "matchingStates": matching_states or ["状态相似"],
            "matchingSignals": matching_signals or ["信号组合相似"],
            "price": close_by_date.get(str(row.get("date") or "")),
        })

    rows = [row for _, row in top_candidates]
    sims = [sim for sim, _ in top_candidates]

    def _wavg(field: str) -> float | None:
        vals = [float(row.get(field, 0) or 0) for row in rows]
        return _weighted_avg(vals, sims)

    def _wwr(field: str) -> float | None:
        vals = [float(row.get(field, 0) or 0) for row in rows]
        return _weighted_win_rate(vals, sims)

    window_stats = [
        {
            "window": "1d",
            "avgReturn": _wavg("next_1d_return"),
            "winRate": _wwr("next_1d_return"),
            "avgExcess": _wavg("next_1d_excess_vs_chain"),
        },
        {
            "window": "3d",
            "avgReturn": _wavg("next_3d_return"),
            "winRate": _wwr("next_3d_return"),
            "avgExcess": _wavg("next_3d_excess_vs_chain"),
        },
        {
            "window": "5d",
            "avgReturn": _wavg("next_5d_return"),
            "winRate": _wwr("next_5d_return"),
            "avgExcess": _wavg("next_5d_excess_vs_chain"),
        },
    ]
    return similar_cases, window_stats


def _build_date_cards(summary_row: dict[str, Any], rolling_row: dict[str, Any] | None, strength_label: Any) -> list[dict[str, Any]]:
    excess_5d = rolling_row.get("excess_5d") if rolling_row else None
    excess_10d = rolling_row.get("excess_10d") if rolling_row else None
    deviation = summary_row.get("relative_strength_vs_industry_chain")
    if deviation is None:
        deviation = (summary_row.get("anchor_return") or 0) - (summary_row.get("industry_chain_median") or 0)
    return [
        {"title": "5日超额", "value": strength_label(excess_5d), "description": f"{excess_5d:+.2f}%" if excess_5d is not None else "--"},
        {"title": "10日超额", "value": strength_label(excess_10d), "description": f"{excess_10d:+.2f}%" if excess_10d is not None else "--"},
        {"title": "今日偏离", "value": strength_label(deviation), "description": f"{deviation:+.2f}%" if deviation is not None else "--"},
    ]


def attribution_for_date(row: dict[str, Any]) -> dict[str, Any] | None:
    """单日归因：从 history_summary 某行计算 anchor return 拆解。"""
    anchor_return = row.get("anchor_return")
    if anchor_return is None:
        return None
    date_str = str(row.get("date") or "")
    sk = state_key_from_row(row)
    return {
        "date": date_str,
        "anchorReturn": anchor_return,
        "pools": {
            "directPeers": row.get("direct_peers_median"),
            "industryChain": row.get("industry_chain_median"),
            "themePool": row.get("theme_pool_median"),
            "tradingWatchlist": row.get("trading_watchlist_median"),
        },
        "alphaVsIndustryChain": row.get("relative_strength_vs_industry_chain"),
        "alphaVsDirectPeers": row.get("relative_strength_vs_direct"),
        "alphaVsThemePool": row.get("relative_strength_vs_theme"),
        "currentQuadrant": sk,
        "currentQuadrantLabel": state_label(sk),
    }


def alerts_for_date(
    excess_entry: dict[str, Any] | None,
    corr_snap: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """单日极端位置警报（百分位 ≥ 85 或 ≤ 10）。"""
    alerts: list[dict[str, Any]] = []

    if excess_entry:
        e5_pct = excess_entry.get("excess5dPercentile")
        e5_val = excess_entry.get("excess5d")
        if e5_pct is not None and e5_val is not None:
            if e5_pct >= 90:
                alerts.append({
                    "level": "warning", "icon": "⚠️",
                    "text": f"5d 超额 +{e5_val:.2f}%，处于历史 P{e5_pct}（过热）",
                })
            elif e5_pct >= 85:
                alerts.append({
                    "level": "warning", "icon": "⚠️",
                    "text": f"5d 超额 +{e5_val:.2f}%，处于历史 P{e5_pct}（接近过热）",
                })
            elif e5_pct <= 10:
                alerts.append({
                    "level": "warning", "icon": "⚠️",
                    "text": f"5d 超额 {e5_val:+.2f}%，处于历史 P{e5_pct}（接近超卖）",
                })

    if corr_snap:
        for pool_key, pool_zh in POOL_ZH_NAMES.items():
            cd = corr_snap.get(pool_key, {})
            pct = cd.get("percentile20d")
            cv = cd.get("corr20d")
            if pct is None or cv is None:
                continue
            if pct <= 5:
                alerts.append({
                    "level": "critical", "icon": "🚨",
                    "text": f"跟{pool_zh} 20d 相关性 = {cv:.2f}，处于历史 P{pct}（极端脱钩）",
                })
            elif pct <= 10:
                alerts.append({
                    "level": "critical", "icon": "🚨",
                    "text": f"跟{pool_zh} 20d 相关性 = {cv:.2f}，处于历史 P{pct}",
                })

    return alerts


def transition_top5_for_state(
    history_summary: list[dict[str, Any]],
    quadrant_dist: dict[str, dict[str, Any]],
    cur_state: str,
) -> list[dict[str, Any]]:
    """从指定状态出发的 top 5 转移目标。"""
    transitions: list[str] = []
    for i in range(len(history_summary) - 1):
        if state_key_from_row(history_summary[i]) == cur_state:
            transitions.append(state_key_from_row(history_summary[i + 1]))

    if not transitions:
        return []
    total = len(transitions)
    counts = Counter(transitions).most_common(5)

    result: list[dict[str, Any]] = []
    for state, count in counts:
        dist = quadrant_dist.get(state, {})
        guidance = guidance_for_winrate(dist.get("winRate"))
        result.append({
            "toState": state,
            "toStateLabel": state_label(state),
            "count": count,
            "probability": round(count / total, 3),
            "targetP50": dist.get("p50"),
            "targetWinRate": dist.get("winRate"),
            "isStay": state == cur_state,
            "guidance": guidance,
        })
    return result


def build_date_index(
    history_summary: list[dict[str, Any]],
    close_by_date: dict[str, float],
    rolling_metrics: list[dict[str, Any]],
    pool_correlations_by_date: dict[str, dict[str, Any]],
    quadrant_dist: dict[str, dict[str, Any]],
    v2_data: dict[str, Any],
    score_bucket_stats: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    print("正在构建 dateIndex...")
    rolling_by_date: dict[str, dict[str, Any]] = {}
    for rm in rolling_metrics:
        d = str(rm.get("date") or "")
        if d:
            rolling_by_date[d] = rm

    def strength_label(value: Any) -> str:
        if value is None:
            return "无数据"
        value = float(value)
        if value > 5:
            return "强"
        if value > 2:
            return "偏强"
        if value < -5:
            return "弱"
        if value < -2:
            return "偏弱"
        return "震荡"

    # 预建 excess_by_date（从 rolling_metrics 里取 excess 字段）
    excess_by_date: dict[str, dict[str, Any]] = {}
    for rm in rolling_metrics:
        d = str(rm.get("date") or "")
        if d:
            excess_by_date[d] = rm

    # 预建 Walk-Forward 象限分布（每天用之前的数据，避免前瞻偏差）
    quadrant_dist_by_date: dict[str, dict[str, dict[str, Any]]] = {}
    for i, row in enumerate(history_summary):
        d = str(row.get("date") or "")
        if d and i > 0:
            quadrant_dist_by_date[d] = build_quadrant_distributions(history_summary, target_date=d)

    date_index: dict[str, dict[str, Any]] = {}
    for row in history_summary:
        date_str = str(row.get("date") or "")
        if not date_str:
            continue
        industry_beta = str(row.get("industry_beta") or "").strip().lower()
        anchor_alpha = str(row.get("anchor_alpha") or "").strip().lower()
        risk_level = str(row.get("risk_level") or "").strip().lower()
        signals = split_signals(row.get("signal_labels"))
        state_key = state_key_from_row(row)
        state_desc = f"{state_label(state_key)} · {RISK_TEXT.get(risk_level, risk_level)}"

        similar_cases, window_stats = compute_similar_cases(history_summary, close_by_date, target_date=date_str)
        state_cockpit = build_state_cockpit(
            history_summary,
            v2_data,
            score_bucket_stats,
            similar_cases,
            window_stats,
            target_date=date_str,
        )

        # 新增：该日的 4 个「今日看板」动态字段
        corr_snap = pool_correlations_by_date.get(date_str)
        excess_entry = excess_by_date.get(date_str)
        day_alerts = alerts_for_date(excess_entry, corr_snap)
        day_attribution = attribution_for_date(row)
        day_dist = quadrant_dist_by_date.get(date_str, quadrant_dist)
        day_t5 = transition_top5_for_state(history_summary, day_dist, state_key)

        date_index[date_str] = {
            "currentMapping": {
                "date": date_str,
                "state": state_desc,
                "tags": signals,
                "similarSampleCount": len(similar_cases),
                "industryBeta": industry_beta,
                "anchorAlpha": anchor_alpha,
                "riskLevel": risk_level,
                "strongestGroup": row.get("strongest_group") or "",
                "weakestGroup": row.get("weakest_group") or "",
                "signalLabels": signals,
            },
            "similarCases": similar_cases,
            "windowStats": window_stats,
            "pathLabel": infer_path_label(window_stats),
            "cards": _build_date_cards(row, rolling_by_date.get(date_str), strength_label),
            # 动态字段
            "todayAttribution": day_attribution,
            "alerts": day_alerts,
            "transitionTop5": day_t5,
            "poolCorrSnapshot": corr_snap,
            "stateCockpit": state_cockpit,
        }
    print(f"[OK] dateIndex: {len(date_index)} 个日期")
    return date_index


def infer_path_label(window_stats: list[dict[str, Any]]) -> str:
    by_window = {item.get("window"): item for item in window_stats}
    next_1d = by_window.get("1d", {}).get("avgReturn")
    next_3d = by_window.get("3d", {}).get("avgReturn")
    if next_1d is None or next_3d is None:
        return "unknown"
    if next_1d > 1 and next_3d > 1:
        return "strong_rise"
    if next_1d > 1 and next_3d < -1:
        return "pullback_after_rise"
    if next_1d < -1 and next_3d < -1:
        return "continue_fall"
    if next_1d < -1 and next_3d > 1:
        return "weak_repair"
    if abs(next_1d) <= 1 and abs(next_3d) <= 1:
        return "range_bound"
    return "disagreement"


def build_summary(
    personality_profile: dict[str, Any],
    operator_playbook: dict[str, Any],
    history_summary: list[dict[str, Any]],
    similar_cases: list[dict[str, Any]],
    window_stats: list[dict[str, Any]],
    today_alerts: list[dict[str, Any]] | None = None,
    transition_top5: list[dict[str, Any]] | None = None,
    today_attribution: dict[str, Any] | None = None,
    quadrant_distributions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    print("正在构建 summary...")
    latest = latest_row(history_summary)
    signals = split_signals(latest.get("signal_labels"))
    industry_beta = str(latest.get("industry_beta") or "neutral")
    anchor_alpha = str(latest.get("anchor_alpha") or "neutral")
    risk_level = str(latest.get("risk_level") or "medium")
    state_desc = (
        f"行业{BETA_TEXT.get(industry_beta, industry_beta)} + "
        f"个股{BETA_TEXT.get(anchor_alpha, anchor_alpha)} + "
        f"{RISK_TEXT.get(risk_level, risk_level)}"
    )

    habit_counts = Counter(habit.get("habit_type", "context") for habit in classified_habits(personality_profile))
    habit_counts["counter_intuitive"] = len(personality_profile.get("counter_intuitive_patterns", []))
    habit_counts["trap"] = len(personality_profile.get("trap_patterns", []))
    playbook = operator_playbook.get("playbook", {})
    watch_points = playbook.get("watch_for", [])[:3] or operator_playbook.get("regime", {}).get("reasons", [])[:3]
    if not watch_points:
        watch_points = ["观察行业Beta是否延续", "关注个股Alpha能否修复", "监测风险信号是否退潮"]

    personality_summary = personality_profile.get("personality_summary", {})
    # 当前格的操作建议
    cur_state_key = state_key_from_row(latest)
    cur_dist = (quadrant_distributions or {}).get(cur_state_key, {})
    current_guidance = guidance_for_winrate(cur_dist.get("winRate"))
    return {
        "currentMapping": {
            "date": str(latest.get("date") or ""),
            "state": state_desc,
            "tags": signals,
            "similarSampleCount": len(similar_cases),
            "industryBeta": industry_beta,
            "anchorAlpha": anchor_alpha,
            "riskLevel": risk_level,
            "strongestGroup": latest.get("strongest_group") or "",
            "weakestGroup": latest.get("weakest_group") or "",
            "signalLabels": signals,
        },
        "pathLabel": infer_path_label(window_stats),
        "transitionVerdict": {
            "title": playbook.get("headline", ""),
            "description": "；".join(playbook.get("watch_for", [])[:2]) or operator_playbook.get("regime", {}).get("headline", ""),
            "watchPoints": watch_points,
        },
        "stabilityVerdict": personality_profile.get("stability", {}).get("status", "insufficient"),
        "profile": {
            "donutData": {
                "likes": habit_counts.get("likes", 0),
                "dislikes": habit_counts.get("dislikes", 0),
                "counter_intuitive": habit_counts.get("counter_intuitive", 0),
                "trap": habit_counts.get("trap", 0),
                "context": habit_counts.get("context", 0),
            },
            "tags": personality_summary.get("traits", []),
            "title": "历史性格档案",
            "description": personality_summary.get("headline", ""),
        },
        # 「今日看板」专属字段
        "alerts": today_alerts or [],
        "transitionTop5": transition_top5 or [],
        "todayAttribution": today_attribution,
        "currentQuadrantGuidance": current_guidance,
    }


def build_cards(
    personality_profile: dict[str, Any],
    operator_playbook: dict[str, Any],
    history_summary: list[dict[str, Any]],
    rolling_metrics: list[dict[str, Any]],
    quadrant_stats: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    print("正在构建 cards...")
    latest_summary = latest_row(history_summary)
    latest_rolling = latest_row(rolling_metrics)
    excess_5d = latest_rolling.get("excess_5d")
    excess_10d = latest_rolling.get("excess_10d")
    deviation = latest_summary.get("relative_strength_vs_industry_chain")
    if deviation is None and latest_summary:
        deviation = (latest_summary.get("anchor_return") or 0) - (latest_summary.get("industry_chain_median") or 0)

    def strength_label(value: Any) -> str:
        if value is None:
            return "无数据"
        value = float(value)
        if value > 5:
            return "强"
        if value > 2:
            return "偏强"
        if value < -5:
            return "弱"
        if value < -2:
            return "偏弱"
        return "震荡"

    summary_metrics = personality_profile.get("summary_metrics", {})
    best_win_rate = max(
        [row.get("win_rate_1d") for row in quadrant_stats if row.get("win_rate_1d") is not None],
        default=None,
    )
    playbook = operator_playbook.get("playbook", {})
    return [
        {
            "title": "历史规律可信度",
            "value": personality_profile.get("personality_summary", {}).get("confidence", ""),
            "badge": personality_profile.get("stability", {}).get("status", ""),
            "description": f"基于{personality_profile.get('sample_days', len(history_summary))}个交易日样本，有效样本{personality_profile.get('valid_sample_days', 0)}个",
        },
        {
            "title": "当前操作倾向",
            "value": {"active_watch": "积极观察", "cautious_watch": "谨慎观察", "wait": "观望"}.get(playbook.get("stance"), "观望"),
            "description": "；".join(playbook.get("confirmations", [])[:1]),
        },
        {
            "title": "主要失效点",
            "value": "；".join(playbook.get("invalidations", [])[:1]) or "暂无主要失效点",
            "description": "",
        },
        {"title": "5日超额", "value": strength_label(excess_5d), "description": f"{excess_5d:+.2f}%" if excess_5d is not None else "--"},
        {"title": "10日超额", "value": strength_label(excess_10d), "description": f"{excess_10d:+.2f}%" if excess_10d is not None else "--"},
        {"title": "今日偏离", "value": strength_label(deviation), "description": f"{deviation:+.2f}%" if deviation is not None else "--"},
        {"label": "样本", "value": f"{personality_profile.get('valid_sample_days', 0)}/{personality_profile.get('sample_days', len(history_summary))}", "description": ""},
        {"label": "置信度", "value": personality_profile.get("personality_summary", {}).get("confidence", ""), "description": ""},
        {"label": "基线胜率", "value": f"{summary_metrics.get('baseline_win_rate_1d', 0) * 100:.1f}%" if summary_metrics.get("baseline_win_rate_1d") is not None else "--%", "description": ""},
        {"label": "胜率", "value": summary_metrics.get("baseline_win_rate_1d") or 0, "description": f"最优象限胜率{best_win_rate * 100:.0f}%" if best_win_rate is not None else ""},
        {"label": "T+3 超额", "value": summary_metrics.get("median_excess_3d") or 0, "description": f"历史中位{summary_metrics.get('median_excess_3d'):+.2f}pp" if summary_metrics.get("median_excess_3d") is not None else ""},
        {"label": "T+3 不利", "value": summary_metrics.get("median_adverse_3d_proxy") or 0, "description": ""},
        {"label": "盈亏比", "value": summary_metrics.get("payoff_ratio") or 0, "description": ""},
        {"label": "夏普", "value": summary_metrics.get("sharpe_like_ratio") or 0, "description": ""},
        {"label": "信号覆盖", "value": summary_metrics.get("signal_coverage_ratio") or 0, "description": ""},
    ]


def build_transitions(history_summary: list[dict[str, Any]], state_transitions_csv: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {
        "count": 0,
        "next1": [],
        "next3": [],
        "next5": [],
    })
    total_by_from: Counter[str] = Counter()
    for index in range(len(history_summary) - 1):
        row = history_summary[index]
        next_row = history_summary[index + 1]
        from_state = state_key_from_row(row)
        to_state = state_key_from_row(next_row)
        grouped[(from_state, to_state)]["count"] += 1
        grouped[(from_state, to_state)]["next1"].append(row.get("next_1d_return"))
        grouped[(from_state, to_state)]["next3"].append(row.get("next_3d_return"))
        grouped[(from_state, to_state)]["next5"].append(row.get("next_5d_return"))
        total_by_from[from_state] += 1

    if not grouped:
        for row in state_transitions_csv:
            from_state = normalize_state(row.get("from_state"))
            to_state = normalize_state(row.get("to_state"))
            grouped[(from_state, to_state)]["count"] += row.get("count") or 0
            total_by_from[from_state] += row.get("count") or 0

    transitions = []
    for from_state, to_state in sorted(grouped.keys(), key=lambda pair: (STATE_ORDER.index(pair[0]), STATE_ORDER.index(pair[1]))):
        item = grouped[(from_state, to_state)]
        count = int(item["count"])
        denominator = total_by_from.get(from_state) or count or 1
        transitions.append({
            "fromState": from_state,
            "toState": to_state,
            "fromStateLabel": state_label(from_state),
            "toStateLabel": state_label(to_state),
            "count": count,
            "probability": count / denominator,
            "avgNext1dReturn": avg(item["next1"]),
            "avgNext3dReturn": avg(item["next3"]),
            "avgNext5dReturn": avg(item["next5"]),
            "winRate1d": win_rate(item["next1"]),
            "winRate3d": win_rate(item["next3"]),
            "winRate5d": win_rate(item["next5"]),
        })
    return transitions


def build_map_data(
    transitions: list[dict[str, Any]],
    history_summary: list[dict[str, Any]],
    personality_profile: dict[str, Any],
) -> dict[str, Any]:
    print("正在构建 mapData...")
    transition_matrix: dict[str, dict[str, float]] = {key: {} for key in STATE_ORDER}
    for transition in transitions:
        transition_matrix[transition["fromState"]][transition["toState"]] = transition["probability"]

    habit_type_map = build_habit_type_map(personality_profile)
    signal_marks = []
    for row in history_summary:
        for signal in split_signals(row.get("signal_labels")):
            signal_marks.append({
                "date": str(row.get("date") or ""),
                "signalName": signal,
                "signalType": signal_group(signal, habit_type_map),
                "return": row.get("anchor_return") or 0,
            })

    recent_rows = last_n(history_summary, 30)
    signal_lanes = {"pref": [], "avoid": [], "contra": [], "trap": []}
    for row in recent_rows:
        groups = signal_groups_for_row(row, habit_type_map)
        for group in signal_lanes:
            signal_lanes[group].append(bool(groups[group]))

    return {
        "transitionMatrix": transition_matrix,
        "signalMarks": signal_marks,
        "signalLanes": signal_lanes,
        "dates": [str(row.get("date") or "") for row in recent_rows],
    }


def build_trends(
    rolling_metrics: list[dict[str, Any]],
    history_summary: list[dict[str, Any]],
    personality_profile: dict[str, Any],
    close_by_date: dict[str, float],
) -> dict[str, Any]:
    print("正在构建 trends...")
    recent_rolling = rolling_metrics
    excess_return = []
    for row in recent_rolling:
        date_str = str(row.get("date") or "")
        excess_return.append({
            "date": date_str,
            "price": close_by_date.get(date_str),
            "excess5d": row.get("excess_5d"),
            "excess10d": row.get("excess_10d"),
            "outperformStreak": row.get("outperform_streak"),
            "betaStreak": row.get("beta_streak"),
            "themeVsCoreStreak": row.get("theme_vs_core_streak"),
            "riskHighStreak": row.get("risk_high_streak"),
        })

    recent_summary = history_summary
    follow_deviation = []
    for row in recent_summary:
        date_str = str(row.get("date") or "")
        anchor = row.get("anchor_return")
        industry = row.get("industry_chain_median")
        excess = row.get("relative_strength_vs_industry_chain")
        if excess is None and anchor is not None and industry is not None:
            excess = anchor - industry
        follow_deviation.append({
            "date": date_str,
            "price": close_by_date.get(date_str),
            "anchor": anchor,
            "industry": industry,
            "excess": excess,
            "deviation": excess,
        })

    habit_type_map = build_habit_type_map(personality_profile)
    signal_timeline = []
    for row in history_summary:
        date_str = str(row.get("date") or "")
        day_return = row.get("anchor_return") or 0
        signals = split_signals(row.get("signal_labels"))
        signal_timeline.append({
            "date": date_str,
            "price": close_by_date.get(date_str),
            "return": day_return,
            "signals": signals,
            "groups": signal_groups_for_row(row, habit_type_map),
        })

    # 「今日看板」专属：5d/10d 超额的历史百分位
    e5_pcts = compute_percentiles_inplace([r["excess5d"] for r in excess_return])
    e10_pcts = compute_percentiles_inplace([r["excess10d"] for r in excess_return])
    for i, r in enumerate(excess_return):
        r["excess5dPercentile"] = e5_pcts[i]
        r["excess10dPercentile"] = e10_pcts[i]

    # 「今日看板」专属：每日 4 池 20d/60d 相关性 + 20d 百分位
    pool_correlations = build_pool_correlations(history_summary)

    return {
        "excessReturn": excess_return,
        "followDeviation": follow_deviation,
        "signalTimeline": signal_timeline,
        "pathPatterns": {
            pattern.get("event_label") or pattern.get("eventLabel") or "未知事件": camelize(pattern.get("avg_path") or pattern.get("avgPath") or [])
            for pattern in personality_profile.get("path_patterns", [])
        },
        "poolCorrelations": pool_correlations,
    }


def _compute_sample_return(history_summary: list[dict[str, Any]]) -> dict[str, Any]:
    returns = [r.get("next_1d_return") for r in history_summary if r.get("next_1d_return") is not None]
    if not returns:
        return {"avgDailyReturn": None, "medianReturn": None, "positiveRatio": None}
    sorted_returns = sorted(returns)
    avg = sum(returns) / len(returns)
    mid = sorted_returns[len(sorted_returns) // 2]
    pos = sum(1 for r in returns if r > 0) / len(returns)
    return {"avgDailyReturn": round(avg, 4), "medianReturn": round(mid, 4), "positiveRatio": round(pos, 4)}


def _compute_relative_to_industry(history_summary: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = [
        (r["anchor_return"], r["industry_chain_median"])
        for r in history_summary
        if r.get("anchor_return") is not None and r.get("industry_chain_median") is not None
    ]
    if not pairs:
        return {"avgChainMedian": None, "avgDailyExcess": None, "outperformRatio": None}
    chain_meds = [p[1] for p in pairs]
    excesses = [p[0] - p[1] for p in pairs]
    avg_chain = sum(chain_meds) / len(chain_meds)
    avg_excess = sum(excesses) / len(excesses)
    outperform = sum(1 for e in excesses if e > 0) / len(excesses)
    return {
        "avgChainMedian": round(avg_chain, 4),
        "avgDailyExcess": round(avg_excess, 4),
        "outperformRatio": round(outperform, 4),
    }


def _compute_scenario_quality(quadrant_stats_list: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [q for q in quadrant_stats_list if (q.get("count") or 0) >= 3]
    best = None
    worst = None
    if valid:
        best = max(valid, key=lambda q: q.get("avgReturn1d") or float("-inf"))
        worst = min(valid, key=lambda q: q.get("avgReturn1d") or float("inf"))
    return {
        "bestQuadrant": best,
        "worstQuadrant": worst,
        "validQuadrantCount": len(valid),
    }


def _compute_event_risk(extreme_divergences_list: list[dict[str, Any]]) -> dict[str, Any]:
    degrees = [d.get("divergenceDegree") or 0 for d in extreme_divergences_list]
    pos = [d for d in degrees if d > 0]
    neg = [d for d in degrees if d < 0]
    return {
        "divergenceCount": len(extreme_divergences_list),
        "maxPositiveDivergence": round(max(pos), 4) if pos else None,
        "maxNegativeDivergence": round(min(neg), 4) if neg else None,
    }


def _best_quadrant(quadrant_stats_list: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [q for q in quadrant_stats_list if (q.get("count") or 0) >= 3]
    if not valid:
        return None
    return max(valid, key=lambda q: q.get("avgReturn1d") or float("-inf"))


def _worst_quadrant(quadrant_stats_list: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [q for q in quadrant_stats_list if (q.get("count") or 0) >= 3]
    if not valid:
        return None
    return min(valid, key=lambda q: q.get("avgReturn1d") or float("inf"))


def _compute_mean_reversion(history_summary: list[dict[str, Any]]) -> dict[str, Any]:
    outperform_days = []
    underperform_days = []
    for i, row in enumerate(history_summary):
        anchor = row.get("anchor_return")
        chain = row.get("industry_chain_median")
        next_ret = row.get("next_1d_return")
        if anchor is None or chain is None or next_ret is None:
            continue
        if anchor > chain:
            outperform_days.append(next_ret)
        else:
            underperform_days.append(next_ret)
    out_reverse = sum(1 for r in outperform_days if r < 0) / len(outperform_days) if outperform_days else None
    under_reverse = sum(1 for r in underperform_days if r > 0) / len(underperform_days) if underperform_days else None
    return {
        "outperformThenReverseRate": round(out_reverse, 4) if out_reverse is not None else None,
        "underperformThenReverseRate": round(under_reverse, 4) if under_reverse is not None else None,
    }


def _build_signal_detail(signal_lifts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "label": row.get("label", ""),
            "displayLabel": row.get("display_label", row.get("label", "")),
            "category": row.get("category", ""),
            "appearanceCount": row.get("count") or row.get("appearance_count") or 0,
            "avgNext1d": row.get("avg_return_1d") or row.get("avg_next_1d"),
            "avgNext3d": row.get("avg_return_3d") or row.get("avg_next_3d"),
            "avgNext5d": row.get("avg_return_5d") or row.get("avg_next_5d"),
            "avgNext1dExcess": row.get("excess_return_1d") or row.get("avg_next_1d_excess"),
            "winRate1d": row.get("win_rate_1d"),
            "baselineAvgNext1d": row.get("baseline_avg_next_1d"),
            "baselineWinRate1d": row.get("baseline_win_rate_1d"),
            "avgNext1dDeltaPp": row.get("avg_next_1d_delta_pp"),
            "liftNext1d": row.get("lift_next_1d"),
            "liftWinRate": row.get("lift_win_rate"),
            "minCountPassed": row.get("min_count_passed", False),
        }
        for row in signal_lifts
    ]


def build_table_data(
    transitions: list[dict[str, Any]],
    history_summary: list[dict[str, Any]],
    signal_lifts: list[dict[str, Any]],
    extreme_divergences: list[dict[str, Any]],
    quadrant_stats: list[dict[str, Any]],
    personality_profile: dict[str, Any],
    operator_playbook: dict[str, Any],
    similar_cases: list[dict[str, Any]],
    window_stats: list[dict[str, Any]],
) -> dict[str, Any]:
    print("正在构建 tableData...")
    summary_metrics = personality_profile.get("summary_metrics", {})
    latest = latest_row(history_summary)
    current_state = state_key_from_row(latest)

    # 「今日看板」专属：每个象限的 P10/P50/P90 分布 + 操作建议
    quadrant_dist = build_quadrant_distributions(history_summary)
    quadrant_stats_list = []
    for row in quadrant_stats:
        key = normalize_state(row.get("quadrant"))
        dist = quadrant_dist.get(key, {})
        guidance = guidance_for_winrate(dist.get("winRate") or row.get("win_rate_1d"))
        quadrant_stats_list.append({
            "quadrant": key,
            "quadrantName": state_label(key),
            "count": row.get("count", 0),
            "avgNext1d": row.get("avg_next_1d"),
            "avgNext3d": row.get("avg_next_3d"),
            "avgNext5d": row.get("avg_next_5d"),
            "avgNext1dExcess": row.get("avg_next_1d_excess") or row.get("avg_relative_strength"),
            "winRate1d": row.get("win_rate_1d"),
            "avgRelativeStrength": row.get("avg_relative_strength"),
            # 「今日看板」专属
            "t1P10": dist.get("p10"),
            "t1P50": dist.get("p50"),
            "t1P90": dist.get("p90"),
            "guidance": guidance,
            "reason": QUADRANT_REASONS.get(key, ""),
        })

    signal_lifts_list = [
        {
            "signalName": row.get("label", ""),
            "displayLabel": row.get("display_label", row.get("label", "")),
            "signalCategory": row.get("category", ""),
            "count": row.get("count") or row.get("appearance_count") or 0,
            "avgReturn1d": row.get("avg_return_1d") or row.get("avg_next_1d"),
            "avgReturn3d": row.get("avg_return_3d") or row.get("avg_next_3d"),
            "avgReturn5d": row.get("avg_return_5d") or row.get("avg_next_5d"),
            "winRate1d": row.get("win_rate_1d"),
            "winRate3d": row.get("win_rate_3d"),
            "winRate5d": row.get("win_rate_5d"),
            "excessReturn1d": row.get("excess_return_1d") or row.get("avg_next_1d_excess"),
            "sharpeRatio": row.get("sharpe_ratio"),
            "effectScore": row.get("effect_score"),
        }
        for row in signal_lifts
    ]

    extreme_divergences_list = [
        {
            "date": str(row.get("date") or ""),
            "divergence": row.get("divergence_degree") or row.get("divergence"),
            "anchorReturn": row.get("anchor_return"),
            "industryChainMedian": row.get("chain_return") or row.get("industry_chain_median"),
            "t1Return": row.get("subsequent_return_1d") or row.get("t1_return"),
            "t3Return": row.get("subsequent_return_3d") or row.get("t3_return"),
            "t5Return": row.get("subsequent_return_5d"),
            "t1Excess": row.get("subsequent_excess_1d") or row.get("t1_excess"),
            "t3Excess": row.get("subsequent_excess_3d") or row.get("t3_excess"),
            "industryBeta": row.get("industry_beta"),
            "anchorAlpha": row.get("anchor_alpha"),
            "riskLevel": row.get("risk_level"),
            "signalLabels": row.get("signal_labels"),
        }
        for row in extreme_divergences
    ]

    ranked_source = [item for item in transitions if item["fromState"] == current_state] or transitions[:]
    ranked_source.sort(key=lambda item: (item.get("probability") or 0, item.get("count") or 0), reverse=True)
    ranked_transition_paths = [
        {
            "rank": index + 1,
            "fromState": item["fromState"],
            "toState": item["toState"],
            "fromStateLabel": item["fromStateLabel"],
            "toStateLabel": item["toStateLabel"],
            "probability": item["probability"],
            "count": item["count"],
            "avgReturn3d": item.get("avgNext3dReturn"),
            "winRate3d": item.get("winRate3d"),
        }
        for index, item in enumerate(ranked_source)
    ]

    transition_summaries = [
        f"从{item['fromStateLabel']}转向{item['toStateLabel']}的概率为{item['probability'] * 100:.1f}%"
        for item in ranked_source[:3]
    ]
    path_stats = [
        {
            "path": f"{item['fromState']}→{item['toState']}",
            "count": item["count"],
            "avgReturn": item.get("avgNext1dReturn"),
            "winRate": item.get("winRate1d"),
        }
        for item in transitions
    ]

    habits = camelize(classified_habits(personality_profile))
    preference_list = [
        {
            "name": item.get("displayLabel") or item.get("label", ""),
            "description": item.get("explanation", ""),
            "count": item.get("count", 0),
            "avgReturn": item.get("avgNext1d"),
            "winRate": item.get("winRate1d"),
            "starLevel": min(5, max(1, round(abs(item.get("effectScore") or 1)))),
        }
        for item in habits
        if item.get("habitType") == "likes"
    ][:5]
    avoid_list = [
        {
            "name": item.get("displayLabel") or item.get("label", ""),
            "description": item.get("explanation", ""),
            "count": item.get("count", 0),
            "avgReturn": item.get("avgNext1d"),
            "winRate": item.get("winRate1d"),
            "starLevel": min(5, max(1, round(abs(item.get("effectScore") or 1)))),
        }
        for item in habits
        if item.get("habitType") == "dislikes"
    ][:5]

    playbook = operator_playbook.get("playbook", {})
    return {
        "coreMetrics": {
            "sampleReturn": _compute_sample_return(history_summary),
            "relativeToIndustry": _compute_relative_to_industry(history_summary),
            "scenarioQuality": _compute_scenario_quality(quadrant_stats_list),
            "eventRisk": _compute_event_risk(extreme_divergences_list),
        },
        "conclusion": {
            "summary": personality_profile.get("personality_summary", {}).get("headline", ""),
            "confidence": personality_profile.get("personality_summary", {}).get("confidence", "medium"),
            "traits": personality_profile.get("personality_summary", {}).get("traits", []),
            "stabilityStatus": personality_profile.get("stability", {}).get("status", "insufficient"),
            "sampleDays": personality_profile.get("sample_days", len(history_summary)),
            "dateRange": {
                "start": str(history_summary[0].get("date", "")) if history_summary else "",
                "end": str(history_summary[-1].get("date", "")) if history_summary else "",
            },
            "bestQuadrant": _best_quadrant(quadrant_stats_list),
            "worstQuadrant": _worst_quadrant(quadrant_stats_list),
            "meanReversion": _compute_mean_reversion(history_summary),
            "warning": "；".join(personality_profile.get("sample_warnings", [])),
        },
        "quadrantStats": quadrant_stats_list,
        "signalLifts": signal_lifts_list,
        "extremeDivergences": extreme_divergences_list,
        "stateTransitions": transitions,
        "transitionSummaries": transition_summaries,
        "rankedTransitionPaths": ranked_transition_paths,
        "signalCombinations": camelize(operator_playbook.get("signal_combinations", [])),
        "combinationSynergies": camelize(operator_playbook.get("combination_synergies", [])),
        "decisionSummary": {
            "stance": playbook.get("stance", "wait"),
            "stanceName": {"active_watch": "积极观察", "cautious_watch": "谨慎观察", "wait": "观望"}.get(playbook.get("stance"), "观望"),
            "primaryTrigger": playbook.get("primary_trigger", ""),
            "confidence": playbook.get("confidence", "medium"),
        },
        "tradingPlaybook": {
            "watchFor": playbook.get("watch_for", []),
            "confirmations": playbook.get("confirmations", []),
            "invalidations": playbook.get("invalidations", []),
            "positionSizing": playbook.get("position_sizing", ""),
            "stopLoss": playbook.get("stop_loss", ""),
            "takeProfit": playbook.get("take_profit", ""),
        },
        "pathStats": path_stats,
        "windowStats": window_stats,
        "similarCases": similar_cases,
        "signalDetail": _build_signal_detail(signal_lifts),
        "signalShift": None,
        "preferenceList": preference_list,
        "avoidList": avoid_list,
        "relationshipProfile": camelize(personality_profile.get("relationship_profile", {})),
        "contraList": camelize(operator_playbook.get("counter_intuitive_signals", []))[:5] or [item for item in habits if item.get("habitType") == "counter_intuitive"][:5],
        "trapList": camelize(operator_playbook.get("signal_traps", []))[:5] or [item for item in habits if item.get("habitType") == "trap"][:5],
    }


def build_personality(personality_profile: dict[str, Any], operator_playbook: dict[str, Any]) -> dict[str, Any]:
    print("正在构建 personality...")
    habits = camelize(classified_habits(personality_profile))
    path_patterns = []
    for pattern in personality_profile.get("path_patterns", []):
        path_patterns.append({
            "eventLabel": pattern.get("event_label") or pattern.get("eventLabel", "未知事件"),
            "count": pattern.get("count", 0),
            "avgPath": camelize(pattern.get("avg_path") or pattern.get("avgPath") or []),
            "summary": pattern.get("summary", ""),
            "confidence": pattern.get("confidence", "low"),
        })

    counter_intuitive_patterns = camelize(operator_playbook.get("counter_intuitive_signals", []))
    if not counter_intuitive_patterns:
        counter_intuitive_patterns = [item for item in habits if item.get("habitType") == "counter_intuitive"]
    trap_patterns = camelize(operator_playbook.get("signal_traps", []))
    if not trap_patterns:
        trap_patterns = [item for item in habits if item.get("habitType") == "trap"]

    return {
        "asOfDate": str(personality_profile.get("as_of_date") or ""),
        "dateRangeStart": str(personality_profile.get("date_range_start") or ""),
        "dateRangeEnd": str(personality_profile.get("date_range_end") or ""),
        "sampleDays": personality_profile.get("sample_days", 0),
        "validSampleDays": personality_profile.get("valid_sample_days", 0),
        "summaryMetrics": camelize(personality_profile.get("summary_metrics", {})),
        "summary": camelize(personality_profile.get("personality_summary", {})),
        "habitPatterns": habits,
        "counterIntuitivePatterns": counter_intuitive_patterns,
        "trapPatterns": trap_patterns,
        "relationshipProfile": camelize(personality_profile.get("relationship_profile", {})),
        "pathPatterns": path_patterns,
        "stability": camelize(personality_profile.get("stability", {})),
        "sampleWarnings": personality_profile.get("sample_warnings", []),
    }


def build_operator(operator_playbook: dict[str, Any], drift_report: dict[str, Any] | None = None) -> dict[str, Any]:
    print("正在构建 operator...")
    playbook = operator_playbook.get("playbook", {})

    # 漂移告警
    drift_alert = {}
    if drift_report and drift_report.get("driftDetected"):
        checks = drift_report.get("checks", {})
        items = []
        labels = {
            "percentileThresholds": "百分位阈值漂移",
            "signalWeights": "信号权重漂移",
            "regimeDistribution": "Regime分布漂移",
            "strategyPerformance": "策略整体漂移",
        }
        for key, label in labels.items():
            if checks.get(key, {}).get("drift"):
                items.append(label)
        drift_alert = {
            "detected": True,
            "summary": drift_report.get("summary", ""),
            "items": items,
        }
    else:
        drift_alert = {"detected": False, "summary": "", "items": []}

    return {
        "asOfDate": str(operator_playbook.get("as_of_date") or ""),
        "dateRangeStart": str(operator_playbook.get("date_range_start") or ""),
        "dateRangeEnd": str(operator_playbook.get("date_range_end") or ""),
        "sampleDays": operator_playbook.get("sample_days", 0),
        "regime": camelize(operator_playbook.get("regime", {})),
        "playbook": {
            "stance": playbook.get("stance", "wait"),
            "headline": playbook.get("headline", ""),
            "watch": playbook.get("watch_for", []),
            "confirm": playbook.get("confirmations", []),
            "failure": playbook.get("invalidations", []),
            "constraint": playbook.get("sample_note", ""),
        },
        "signalRoles": camelize(operator_playbook.get("signal_roles", [])),
        "counterIntuitiveSignals": camelize(operator_playbook.get("counter_intuitive_signals", [])),
        "signalTraps": camelize(operator_playbook.get("signal_traps", [])),
        "conditionalEffects": camelize(operator_playbook.get("conditional_effects", [])),
        "confirmationPairs": camelize(operator_playbook.get("confirmation_pairs", [])),
        "driftAlert": drift_alert,
    }


def build_prediction_evaluation(prediction_backtest: dict[str, Any]) -> dict[str, Any]:
    """构建预测评估数据"""
    print("正在构建 predictionEvaluation...")

    if not prediction_backtest:
        return {
            "metricsByPeriod": [],
            "stabilityMetrics": None,
            "recentPredictions": [],
            "confidenceIntervals": [],
        }

    # 分时段指标
    metrics_by_period = []
    for period in prediction_backtest.get("metrics_by_period", []):
        period_data = {
            "periodDays": period.get("period_days"),
            "metrics": _transform_backtest_metrics(period.get("metrics", {})),
        }
        metrics_by_period.append(period_data)

    # 稳定性指标
    stability = prediction_backtest.get("stability_metrics", {})
    stability_metrics = None
    if stability:
        sim_dist = stability.get("similarity_distribution", [])
        stability_metrics = {
            "predictionVolatility1d": stability.get("prediction_volatility_1d"),
            "stabilityScore": stability.get("stability_score"),
            "similarityDistribution": dict(sim_dist) if sim_dist else {},
        }

    # 最近预测
    recent_predictions = prediction_backtest.get("recent_predictions", [])

    # 置信区间
    confidence_intervals = prediction_backtest.get("confidence_intervals", [])

    return {
        "metricsByPeriod": metrics_by_period,
        "stabilityMetrics": stability_metrics,
        "recentPredictions": camelize(recent_predictions),
        "confidenceIntervals": camelize(confidence_intervals) if confidence_intervals else [],
    }


def _transform_backtest_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """转换回测指标为前端格式"""
    window_1d = metrics.get("window_1d", {})
    window_3d = metrics.get("window_3d", {})
    window_5d = metrics.get("window_5d", {})

    return {
        "window1d": {
            "ic": window_1d.get("ic"),
            "directionAccuracy": window_1d.get("direction_accuracy"),
            "rmse": window_1d.get("rmse"),
            "mae": window_1d.get("mae"),
            "meanError": window_1d.get("mean_error"),
        },
        "window3d": {
            "ic": window_3d.get("ic"),
            "directionAccuracy": window_3d.get("direction_accuracy"),
            "rmse": window_3d.get("rmse"),
            "mae": window_3d.get("mae"),
            "meanError": window_3d.get("mean_error"),
        },
        "window5d": {
            "ic": window_5d.get("ic"),
            "directionAccuracy": window_5d.get("direction_accuracy"),
            "rmse": window_5d.get("rmse"),
            "mae": window_5d.get("mae"),
            "meanError": window_5d.get("mean_error"),
        },
        "totalPredictions": metrics.get("total_predictions"),
        "validPredictions1d": metrics.get("valid_predictions_1d"),
        "validPredictions3d": metrics.get("valid_predictions_3d"),
        "validPredictions5d": metrics.get("valid_predictions_5d"),
        "quintileReturns": metrics.get("quintile_returns"),
    }


def build_ai_insight(operator_playbook: dict[str, Any], personality_profile: dict[str, Any], signal_lifts: list[dict[str, Any]], extreme_divergences: list[dict[str, Any]]) -> dict[str, Any]:
    print("正在构建 aiInsight...")
    playbook = operator_playbook.get("playbook", {})

    top_signals = sorted(
        [s for s in signal_lifts if (s.get("avg_next_1d_delta_pp") or 0) != 0],
        key=lambda s: abs(s.get("avg_next_1d_delta_pp") or 0),
        reverse=True,
    )[:3]
    top_signal_names = [s.get("display_label") or s.get("label", "") for s in top_signals]

    parts = []
    if top_signal_names:
        parts.append(f"最强信号：{'、'.join(top_signal_names)}")
    parts.append(f"极端背离事件 {len(extreme_divergences)} 次")
    combos = operator_playbook.get("combination_synergies", [])
    if combos:
        parts.append(f"信号组合效应 {len(combos)} 条")
    research_details = "；".join(parts)

    return {
        "advice": {
            "watch": (playbook.get("watch_for") or [""])[0],
            "confirm": (playbook.get("confirmations") or [""])[0],
            "failure": (playbook.get("invalidations") or [""])[0],
            "constraint": playbook.get("sample_note") or (personality_profile.get("sample_warnings") or [""])[0],
        },
        "watchPoints": operator_playbook.get("regime", {}).get("reasons", []),
        "researchDetails": research_details,
    }


def _classify_bucket(value: float | None, thresholds: dict[str, Any]) -> str:
    """根据超额值和 M 维阈值判断所属档位。"""
    if value is None:
        return ""
    p15 = thresholds.get("P15-")
    p30 = thresholds.get("P15-P30") or thresholds.get("P30")
    p70 = thresholds.get("P70-P85") or thresholds.get("P70")
    p85 = thresholds.get("P85+")
    # thresholds 存的是阈值数值，从 bucket key 提取
    # 实际用 thresholds dict 的 values 来判断
    if p85 is not None and value >= float(p85):
        return "P85+(过热)"
    if p70 is not None and value >= float(p70):
        return "P70-P85"
    if p30 is not None and value >= float(p30):
        return "P30-P70(中性)"
    if p15 is not None and value >= float(p15):
        return "P15-P30"
    return "P15-(过冷)"


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _fmt_pct(value: Any, digits: int = 1) -> str:
    number = _safe_float(value)
    if number is None:
        return "无数据"
    return f"{number:+.{digits}f}%"


def _metric_level(score: int, low: int, high: int) -> str:
    if score >= high:
        return "high"
    if score >= low:
        return "medium"
    return "low"


def build_state_cockpit(
    history_summary: list[dict[str, Any]],
    v2_data: dict[str, Any],
    score_bucket_stats: list[dict[str, Any]],
    similar_cases: list[dict[str, Any]],
    window_stats: list[dict[str, Any]],
    target_date: str | None = None,
) -> dict[str, Any]:
    """构建态势感知驾驶舱：状态、决策链、证据、可信度、回溯校准。"""
    if target_date:
        target_row = next((r for r in history_summary if str(r.get("date")) == target_date), None)
    else:
        target_row = latest_row(history_summary)
    if not target_row:
        return {}

    date_str = str(target_row.get("date") or "")
    v2_daily = v2_data.get("dailyResults", [])
    v2_by_date = {str(item.get("date")): item for item in v2_daily}
    v2_day = v2_by_date.get(date_str, {})
    score = int(v2_day.get("score") or 0)
    veto = _safe_bool(v2_day.get("veto"))
    regime = v2_day.get("regime") or "unknown"
    signals = v2_day.get("signals") or []
    signal_breakdown = v2_day.get("signalBreakdown") or []
    technical = v2_day.get("technicalIndicators") or {}

    bucket_by_date = {str(item.get("date")): item for item in score_bucket_stats}
    bucket = bucket_by_date.get(date_str, {})
    by_window = {item.get("window"): item for item in window_stats}
    t1 = by_window.get("1d", {})
    t3 = by_window.get("3d", {})
    t5 = by_window.get("5d", {})
    path_label = infer_path_label(window_stats)

    t1_avg = _safe_float(t1.get("avgReturn"))
    t3_avg = _safe_float(t3.get("avgReturn"))
    t5_avg = _safe_float(t5.get("avgReturn"))
    micro_positive = sum(1 for value in [t1_avg, t3_avg, t5_avg] if value is not None and value > 0)
    micro_negative = sum(1 for value in [t1_avg, t3_avg, t5_avg] if value is not None and value < 0)
    micro_flat = all(value is not None and abs(value) <= 0.35 for value in [t1_avg, t3_avg])
    macro_bearish = veto or score <= -3
    macro_extreme_bearish = veto or score <= -8
    macro_bullish = score >= 3
    conflict = (macro_bearish and micro_positive >= 2) or (macro_bullish and micro_negative >= 2)

    if macro_extreme_bearish and (micro_positive >= 2 or micro_flat):
        state_label_text = "过热但惯性未坏"
        state_summary = "宏观风险分数已经很重，但相似路径没有同步转成单边下跌，更像高位惯性与回撤风险并存。"
        posture = {"code": "avoid_chase", "label": "不追高，等确认", "tone": "warning"}
    elif macro_extreme_bearish:
        state_label_text = "过热风险确认区"
        state_summary = "V2 分数进入强风险档，同档历史偏弱，优先控制回撤和仓位暴露。"
        posture = {"code": "reduce_risk", "label": "减仓优先", "tone": "danger"}
    elif macro_bearish and conflict:
        state_label_text = "风险偏空但路径冲突"
        state_summary = "主模型偏空，但微观相似路径仍有惯性，适合等转弱信号而不是抢先下结论。"
        posture = {"code": "wait_confirm", "label": "等转弱确认", "tone": "warning"}
    elif macro_bearish:
        state_label_text = "偏空观察区"
        state_summary = "风险证据多于修复证据，操作上应降低进攻性。"
        posture = {"code": "cautious_watch", "label": "谨慎观察", "tone": "warning"}
    elif macro_bullish and micro_negative >= 2:
        state_label_text = "模型偏多但路径转弱"
        state_summary = "分数偏多但相似路径短期不配合，先看确认，不把分数当成直接买点。"
        posture = {"code": "wait_confirm", "label": "等确认", "tone": "neutral"}
    elif macro_bullish:
        state_label_text = "修复延续区"
        state_summary = "主模型和路径没有明显冲突，可以作为积极观察状态。"
        posture = {"code": "active_watch", "label": "积极观察", "tone": "positive"}
    else:
        state_label_text = "震荡观察区"
        state_summary = "主模型没有给出强方向，更多是路径和状态的观察价值。"
        posture = {"code": "watch", "label": "观望", "tone": "neutral"}

    bucket_t1 = bucket.get("stateWeightedT1") or bucket.get("t1") or {}
    bucket_t3 = bucket.get("stateWeightedT3") or bucket.get("t3") or {}
    bucket_sample = bucket.get("effectiveSampleSize") or bucket.get("sampleSize")
    similar_count = len(similar_cases)

    evidence_items = [
        {
            "id": "v2-score",
            "title": "V2 Walk-Forward 主线",
            "stance": "risk" if macro_bearish else ("positive" if macro_bullish else "neutral"),
            "strength": "high" if abs(score) >= 8 or veto else ("medium" if abs(score) >= 3 else "low"),
            "sourceTag": "Walk-Forward",
            "detail": f"score={score}，regime={regime}，信号 {len(signals)} 个",
            "metrics": [
                {"label": "score", "value": score},
                {"label": "veto", "value": veto},
            ],
        },
        {
            "id": "score-bucket",
            "title": "同档历史统计",
            "stance": "risk" if (_safe_float(bucket_t1.get("avgAbsReturn")) or 0) < 0 else "neutral",
            "strength": "medium" if (bucket_sample or 0) >= 6 else "low",
            "sourceTag": "Walk-Forward 小样本",
            "detail": f"当前评分档 {bucket.get('bucketLabel', '未知')}，有效样本 {bucket_sample or 0}",
            "metrics": [
                {"label": "T+1 个股均值", "value": bucket_t1.get("avgAbsReturn")},
                {"label": "T+3 个股均值", "value": bucket_t3.get("avgAbsReturn")},
            ],
        },
        {
            "id": "micro-path",
            "title": "微观相似路径",
            "stance": "positive" if micro_positive >= 2 else ("risk" if micro_negative >= 2 else "neutral"),
            "strength": "medium" if similar_count >= 8 else "low",
            "sourceTag": "相似案例",
            "detail": f"相似案例 {similar_count} 个，路径={path_label}",
            "metrics": [
                {"label": "T+1 均值", "value": t1.get("avgReturn")},
                {"label": "T+3 均值", "value": t3.get("avgReturn")},
                {"label": "T+5 均值", "value": t5.get("avgReturn")},
            ],
        },
        {
            "id": "technical-temperature",
            "title": "技术温度",
            "stance": "risk" if (technical.get("stochK") or 0) >= 80 or (technical.get("bbPctb") or 0) >= 1 else "neutral",
            "strength": "medium",
            "sourceTag": "描述性指标",
            "detail": f"StochK={technical.get('stochK', '无')}，BB%b={technical.get('bbPctb', '无')}，ADX={technical.get('adx14', '无')}",
            "metrics": [
                {"label": "RSI14", "value": technical.get("rsi14")},
                {"label": "StochK", "value": technical.get("stochK")},
            ],
        },
    ]

    supporting_evidence = [
        {
            "title": "V2 主模型进入风险档",
            "summary": f"score={score}，卖出阈值={v2_day.get('thresholdSell', '无')}，当前信号数 {len(signals)}。",
            "sourceTag": "Walk-Forward",
            "weight": "high" if abs(score) >= 8 or veto else "medium",
            "stance": "risk",
        },
        {
            "title": "同档历史偏弱",
            "summary": f"评分档 {bucket.get('bucketLabel', '未知')}，T+1 个股均值 {_fmt_pct(bucket_t1.get('avgAbsReturn'))}，T+3 个股均值 {_fmt_pct(bucket_t3.get('avgAbsReturn'))}。",
            "sourceTag": "Walk-Forward 小样本",
            "weight": "medium" if (bucket_sample or 0) >= 6 else "low",
            "stance": "risk",
        },
    ]
    if (technical.get("stochK") or 0) >= 80 or (technical.get("bbPctb") or 0) >= 1:
        supporting_evidence.append({
            "title": "技术温度处在高位",
            "summary": f"StochK={technical.get('stochK', '无')}，BB%b={technical.get('bbPctb', '无')}，提示短线过热。",
            "sourceTag": "描述性指标",
            "weight": "medium",
            "stance": "risk",
        })

    opposing_evidence = [
        {
            "title": "微观相似路径未同步转弱",
            "summary": f"相似样本 {similar_count}，T+1 {_fmt_pct(t1_avg)}，T+3 {_fmt_pct(t3_avg)}，T+5 {_fmt_pct(t5_avg)}。",
            "sourceTag": "相似案例",
            "weight": "medium" if similar_count >= 8 else "low",
            "stance": "positive" if micro_positive >= 2 or micro_flat else "neutral",
        },
        {
            "title": "行业和个股状态仍强",
            "summary": f"当前象限 {state_label(state_key_from_row(target_row))}，风险等级 {RISK_TEXT.get(str(target_row.get('risk_level')), target_row.get('risk_level'))}。",
            "sourceTag": "状态识别",
            "weight": "medium",
            "stance": "positive" if state_key_from_row(target_row) == "positive+positive" else "neutral",
        },
    ]
    if signals:
        opposing_evidence.append({
            "title": "风险信号不等于立即下跌",
            "summary": "当前负分更多描述过热与位置风险，仍需微观路径或价格行为确认。",
            "sourceTag": "模型解释",
            "weight": "medium",
            "stance": "neutral",
        })

    conflict_title = "宏观风险强，微观惯性未断" if conflict or (macro_extreme_bearish and (micro_positive >= 2 or micro_flat)) else "证据冲突可控"
    conflict_summary = (
        "主模型和同档历史提示高风险，但相似案例短线仍偏震荡/惯性，所以当前不是单向看跌，而是等待转弱确认。"
        if conflict or (macro_extreme_bearish and (micro_positive >= 2 or micro_flat))
        else "主模型、路径和状态没有形成强烈反向拉扯，按当前主判断处理。"
    )
    evidence_matrix = {
        "supporting": supporting_evidence[:4],
        "opposing": opposing_evidence[:4],
        "conflicts": [
            {
                "title": conflict_title,
                "summary": conflict_summary,
                "leftLabel": "宏观风险",
                "leftValue": "强" if macro_extreme_bearish else ("中" if macro_bearish else "弱"),
                "rightLabel": "微观惯性",
                "rightValue": "强" if micro_positive >= 2 else ("中" if micro_flat else "弱"),
                "severity": "high" if conflict or macro_extreme_bearish else "medium",
            }
        ],
    }

    consistency_score = 1
    if conflict:
        consistency_score = 0
    elif (macro_bearish and micro_negative >= 2) or (macro_bullish and micro_positive >= 2):
        consistency_score = 2

    stat_score = 0
    if similar_count >= 8:
        stat_score += 1
    if (bucket_sample or 0) >= 6:
        stat_score += 1

    recent_rows = [d for d in v2_daily if str(d.get("date")) < date_str and d.get("next1dAbs") is not None]

    def recent_window(n: int) -> dict[str, Any]:
        rows = recent_rows[-n:]
        if not rows:
            return {"windowDays": n, "sampleSize": 0, "directionAccuracy": None, "avgAbsReturn": None, "avgExcess": None}
        direction_hits = 0
        directional = 0
        abs_values = []
        exc_values = []
        soft_hits = 0
        for item in rows:
            s = int(item.get("score") or 0)
            abs_ret = _safe_float(item.get("next1dAbs"))
            exc_ret = _safe_float(item.get("next1dExcess"))
            if abs_ret is not None:
                abs_values.append(abs_ret)
                if abs(s) >= 3:
                    directional += 1
                    if (s > 0 and abs_ret > 0) or (s < 0 and abs_ret < 0):
                        direction_hits += 1
                if (abs(s) < 3 and abs(abs_ret) <= 1.0) or (s >= 3 and abs_ret > -1.0) or (s <= -3 and abs_ret < 1.0):
                    soft_hits += 1
            if exc_ret is not None:
                exc_values.append(exc_ret)
        return {
            "windowDays": n,
            "sampleSize": len(rows),
            "directionAccuracy": round(direction_hits / directional, 4) if directional else None,
            "softAccuracy": round(soft_hits / len(rows), 4) if rows else None,
            "avgAbsReturn": round(mean(abs_values), 4) if abs_values else None,
            "avgExcess": round(mean(exc_values), 4) if exc_values else None,
        }

    calibration = {
        "recentWindows": [recent_window(n) for n in [10, 20, 30, 60]],
        "currentState": {
            "similarSampleSize": similar_count,
            "scoreBucketSampleSize": bucket.get("sampleSize"),
            "scoreBucketEffectiveSampleSize": bucket.get("effectiveSampleSize"),
            "pathLabel": path_label,
            "scoreBucketLabel": bucket.get("bucketLabel"),
        },
        "longTerm": {
            "sampleSize": len(recent_rows),
            "directionAccuracy": recent_window(len(recent_rows)).get("directionAccuracy") if recent_rows else None,
            "softAccuracy": recent_window(len(recent_rows)).get("softAccuracy") if recent_rows else None,
        },
    }

    credibility = {
        "dataQuality": {
            "level": "high" if target_row and v2_day else "low",
            "score": 90 if target_row and v2_day else 45,
            "reason": "历史状态、V2 评分和相似案例均可用" if target_row and v2_day else "关键数据缺失",
        },
        "statisticalCredibility": {
            "level": _metric_level(stat_score, 1, 2),
            "score": 35 + stat_score * 25,
            "reason": f"相似样本 {similar_count}，评分档有效样本 {bucket_sample or 0}",
        },
        "modelConsistency": {
            "level": _metric_level(consistency_score, 1, 2),
            "score": 35 + consistency_score * 25,
            "reason": "宏观风险与微观路径冲突" if conflict else "核心证据方向基本可解释",
        },
        "stateStability": {
            "level": "medium" if conflict or macro_extreme_bearish else "high",
            "score": 58 if conflict or macro_extreme_bearish else 76,
            "reason": "当前处在高位风险与惯性冲突区，容易快速切换" if conflict or macro_extreme_bearish else "状态冲突不明显",
        },
    }

    model_attitude = "strong" if abs(score) >= 8 or veto else ("medium" if abs(score) >= 3 else "weak")
    evidence_conflict = "high" if conflict or (macro_extreme_bearish and (micro_positive >= 2 or micro_flat)) else ("medium" if macro_bearish or macro_bullish else "low")
    thesis = {
        "judgement": state_label_text,
        "actionMeaning": posture["label"],
        "summary": state_summary,
        "modelAttitude": model_attitude,
        "statisticalCredibility": credibility["statisticalCredibility"]["level"],
        "evidenceConflict": evidence_conflict,
        "riskLevel": "high" if macro_extreme_bearish else ("medium" if macro_bearish else "low"),
    }

    reasoning_chain = [
        {
            "step": "观测",
            "title": "先看到了什么",
            "summary": f"V2 score={score}，当前状态 {state_label(state_key_from_row(target_row))}，活跃信号 {len(signals)} 个。",
            "tags": ["Walk-Forward", "状态识别"],
        },
        {
            "step": "态势",
            "title": "这些信号组合成什么状态",
            "summary": state_summary,
            "tags": ["态势归纳"],
        },
        {
            "step": "投影",
            "title": "历史同类路径怎么走",
            "summary": f"相似案例 T+1 {_fmt_pct(t1_avg)}，T+3 {_fmt_pct(t3_avg)}，T+5 {_fmt_pct(t5_avg)}。",
            "tags": ["相似案例", "回溯"],
        },
        {
            "step": "决策",
            "title": "今天该怎么理解",
            "summary": posture["label"],
            "tags": ["决策支持"],
        },
    ]

    invalidation_rules = []
    if macro_extreme_bearish and (micro_positive >= 2 or micro_flat):
        invalidation_rules = [
            "若微观相似路径 T+1/T+3 同时转负，状态从“惯性未坏”切到“风险确认”。",
            "若 V2 负分收敛到 -3 以内且过热技术信号退潮，风险态势降级。",
            "若评分档样本继续显示 T+3/T+5 大幅转弱，优先相信回撤风险。",
        ]
    elif macro_bearish:
        invalidation_rules = [
            "若 V2 score 回到中性区且相似路径转正，偏空判断降级。",
            "若新增负向信号继续增加，风险判断升级。",
        ]
    else:
        invalidation_rules = [
            "若 V2 score 跌破卖出阈值，当前状态转入风险观察。",
            "若相似案例短中期均值同时转负，降低进攻性。",
        ]

    base_probability = 0.50
    risk_probability = 0.35 if macro_bearish else 0.25
    reflexive_probability = max(0.10, round(1.0 - base_probability - risk_probability, 2))
    scenario_projection = [
        {
            "id": "base",
            "title": "基准情景",
            "probability": base_probability,
            "stance": "neutral",
            "summary": "高位震荡，惯性未断，等待更明确的转弱或修复信号。",
            "path": [
                {"window": "T+1", "value": t1_avg},
                {"window": "T+3", "value": t3_avg},
                {"window": "T+5", "value": t5_avg},
            ],
            "triggers": ["相似路径维持震荡", "V2 负分不继续扩大", "行业个股状态仍强"],
            "risk": "容易把高位震荡误读成低风险。",
        },
        {
            "id": "risk",
            "title": "风险情景",
            "probability": risk_probability,
            "stance": "risk",
            "summary": "微观路径转弱后，过热风险释放，回撤确认。",
            "path": [
                {"window": "T+1", "value": bucket_t1.get("avgAbsReturn")},
                {"window": "T+3", "value": bucket_t3.get("avgAbsReturn")},
                {"window": "T+5", "value": (bucket.get("stateWeightedT5") or bucket.get("t5") or {}).get("avgAbsReturn")},
            ],
            "triggers": ["T+1/T+3 相似路径同时转负", "负向信号增加", "技术高位回落"],
            "risk": "风险确认时再反应，可能已经错过第一段回撤。",
        },
        {
            "id": "reflexive",
            "title": "反身性情景",
            "probability": reflexive_probability,
            "stance": "positive",
            "summary": "强势惯性继续上冲，随后再释放位置风险。",
            "path": [
                {"window": "T+1", "value": max([v for v in [t1_avg, 0.0] if v is not None])},
                {"window": "T+3", "value": max([v for v in [t3_avg, 0.0] if v is not None])},
                {"window": "T+5", "value": t5_avg},
            ],
            "triggers": ["行业个股继续强", "高位信号钝化", "相似案例仍不转弱"],
            "risk": "逼空阶段容易追在情绪最热的位置。",
        },
    ]

    post_check = {
        "windows": calibration["recentWindows"],
        "longTerm": calibration["longTerm"],
        "stateGroup": {
            "label": state_label_text,
            "sampleSize": similar_count,
            "avgT1": t1_avg,
            "avgT3": t3_avg,
            "avgT5": t5_avg,
            "winRateT1": t1.get("winRate"),
            "scoreBucketSampleSize": bucket.get("sampleSize"),
            "note": "当前分组用于校验“体感准”是否只是近期印象；样本少时只作弱证据。",
        },
    }

    return {
        "date": date_str,
        "stateLabel": state_label_text,
        "stateSummary": state_summary,
        "decisionPosture": posture,
        "thesis": thesis,
        "modelSource": {
            "primary": "V2 Walk-Forward",
            "secondary": ["相似案例", "同档历史统计", "技术温度"],
            "note": "V2 暂作实时主线；其他证据用于解释、冲突识别和可信度降级。",
        },
        "reasoningChain": reasoning_chain,
        "evidenceItems": evidence_items,
        "evidenceMatrix": evidence_matrix,
        "scenarioProjection": scenario_projection,
        "credibility": credibility,
        "calibration": calibration,
        "postCheck": post_check,
        "invalidationRules": invalidation_rules,
        "diagnostics": {
            "score": score,
            "veto": veto,
            "regime": regime,
            "signals": signals,
            "signalBreakdown": signal_breakdown,
            "conflict": conflict,
            "pathLabel": path_label,
        },
    }


def build_decision(
    history_summary: list[dict[str, Any]],
    rolling_metrics: list[dict[str, Any]],
    quadrant_distributions: dict[str, dict[str, Any]],
    similar_cases: list[dict[str, Any]],
    window_stats: list[dict[str, Any]],
    operator_playbook: dict[str, Any],
    excess_return_data: list[dict[str, Any]] | None = None,
    target_date: str | None = None,
) -> dict[str, Any]:
    """构建决策模块：今日判定 + 明日操作。"""
    # 加载量化实验室数据
    composite_bt = read_json("composite_signal_backtest.json")
    second_order = read_json("history_2nd_order_analysis.json")
    deep_quant = read_json("history_deep_quant_analysis.json")

    # 确定目标日期
    if target_date:
        target_row = next((r for r in history_summary if str(r.get("date")) == target_date), None)
    else:
        target_row = latest_row(history_summary)
    if not target_row:
        return {}
    date_str = str(target_row.get("date") or "")

    # 获取昨日信号列表（判断新出现 vs 持续）
    target_idx = next((i for i, r in enumerate(history_summary) if str(r.get("date")) == date_str), -1)
    prev_signals: set[str] = set()
    if target_idx > 0:
        prev_signals = set(split_signals(history_summary[target_idx - 1].get("signal_labels")))
    today_signals = split_signals(target_row.get("signal_labels"))

    # ── 1. 综合分 + 否决 ──
    daily_results = composite_bt.get("daily_results", [])
    day_result = next((r for r in daily_results if str(r.get("date")) == date_str), {})
    score = day_result.get("score", 0)
    veto = day_result.get("veto", False)
    active_composite = day_result.get("signals", [])
    signal_weights = composite_bt.get("signal_weights", {})
    buy_weights = signal_weights.get("buy", {})
    sell_weights = signal_weights.get("sell", {})

    score_breakdown = []
    for sig in active_composite:
        w = buy_weights.get(sig, sell_weights.get(sig, 0))
        score_breakdown.append({"signal": sig, "weight": w})

    # ── 2. 超额回归档位 ──
    rolling_by_date = {str(r.get("date")): r for r in rolling_metrics}
    rolling_row = rolling_by_date.get(date_str, {})
    excess_5d = rolling_row.get("excess_5d")
    excess_10d = rolling_row.get("excess_10d")

    m_reversal = deep_quant.get("M_excessMeanReversion", {}).get("extremeReversal", {})
    e5_buckets = m_reversal.get("by_excess_5d", {}).get("buckets", {})
    e10_buckets = m_reversal.get("by_excess_10d", {}).get("buckets", {})

    def _bucket_info(value: float | None, buckets: dict[str, Any]) -> dict[str, Any]:
        if value is None or not buckets:
            return {"value": value, "bucket": "", "bucketAvgExc1d": None, "bucketWr1d": None}
        # 找到对应 bucket
        bucket_name = ""
        for name, bdata in buckets.items():
            exc1d = bdata.get("exc_1d", {})
            bucket_name = name
            break  # 先设默认
        # 按阈值判断
        if value >= 5.73:
            bucket_name = "P85+(过热)"
        elif value >= 2.74:
            bucket_name = "P70-P85"
        elif value >= -2.12:
            bucket_name = "P30-P70(中性)"
        elif value >= -4.91:
            bucket_name = "P15-P30"
        else:
            bucket_name = "P15-(过冷)"
        bdata = buckets.get(bucket_name, {})
        exc1d = bdata.get("exc_1d", {})
        return {
            "value": round(value, 2),
            "bucket": bucket_name,
            "bucketAvgExc1d": exc1d.get("avg"),
            "bucketWr1d": exc1d.get("wr"),
        }

    # 更精确的阈值判断：从 trends.excessReturn 的百分位
    excess_by_date = {str(e.get("date")): e for e in (excess_return_data or [])}
    excess_entry = excess_by_date.get(date_str, {})
    e5_pct = excess_entry.get("excess5dPercentile")
    e10_pct = excess_entry.get("excess10dPercentile")
    e10_pct = excess_entry.get("excess10dPercentile")

    def _bucket_by_pct(pct: int | None, buckets: dict[str, Any]) -> str:
        if pct is None:
            return ""
        if pct >= 85:
            return "P85+(过热)"
        if pct >= 70:
            return "P70-P85"
        if pct >= 30:
            return "P30-P70(中性)"
        if pct >= 15:
            return "P15-P30"
        return "P15-(过冷)"

    e5_bucket_name = _bucket_by_pct(e5_pct, e5_buckets)
    e10_bucket_name = _bucket_by_pct(e10_pct, e10_buckets)
    e5_bdata = e5_buckets.get(e5_bucket_name, {}).get("exc_1d", {})
    e10_bdata = e10_buckets.get(e10_bucket_name, {}).get("exc_1d", {})

    excess_reversion = {
        "excess5d": {
            "value": round(excess_5d, 2) if excess_5d is not None else None,
            "bucket": e5_bucket_name,
            "bucketAvgExc1d": e5_bdata.get("avg"),
            "bucketWr1d": e5_bdata.get("wr"),
        },
        "excess10d": {
            "value": round(excess_10d, 2) if excess_10d is not None else None,
            "bucket": e10_bucket_name,
            "bucketAvgExc1d": e10_bdata.get("avg"),
            "bucketWr1d": e10_bdata.get("wr"),
        },
    }

    # ── 3. 象限胜率 ──
    cur_state = state_key_from_row(target_row)
    cur_dist = quadrant_distributions.get(cur_state, {})
    quadrant_wr = cur_dist.get("winRate")

    # ── 4. 信号 Alpha 分类 + 方向一致性 ──
    alpha_rank = {s["signal"]: s for s in second_order.get("alphaSignalRank", [])}
    consistency_map = {s["signal"]: s for s in second_order.get("multiPeriodConsistency", [])}
    delta_map = {s["signal"]: s for s in second_order.get("signalDelta", [])}

    signal_evidence: dict[str, dict[str, Any]] = {}
    bullish: list[dict[str, Any]] = []
    bearish: list[dict[str, Any]] = []

    for sig in today_signals:
        alpha = alpha_rank.get(sig, {})
        cons = consistency_map.get(sig, {})
        delta = delta_map.get(sig, {})

        alpha_type_raw = alpha.get("signalType", "中性")
        # 简化分类名
        if "纯Alpha" in alpha_type_raw:
            alpha_type = "纯Alpha"
        elif "隐藏Alpha" in alpha_type_raw:
            alpha_type = "隐藏Alpha"
        elif "负向" in alpha_type_raw:
            alpha_type = "负向"
        else:
            alpha_type = "中性"

        is_new = sig not in prev_signals
        new_data = delta.get("new", {}).get("1d", {})
        cont_data = delta.get("continued", {}).get("1d", {})
        new_vs_cont_delta = delta.get("newVsContinued1d")

        entry = {
            "alphaType": alpha_type,
            "excLift": alpha.get("excLift"),
            "wrExc1d": alpha.get("wrExc1d"),
            "directionPattern": cons.get("pattern", ""),
            "isConsistent": cons.get("consistent"),
            "flipPeriod": cons.get("flip"),
            "isNew": is_new,
            "newVsContinuedDelta": new_vs_cont_delta,
        }
        signal_evidence[sig] = entry

        verdict_entry = {
            "signal": sig,
            "alphaType": alpha_type,
            "excLift": alpha.get("excLift"),
            "directionPattern": cons.get("pattern", ""),
            "isNew": is_new,
        }
        if alpha_type in ("纯Alpha", "隐藏Alpha"):
            bullish.append(verdict_entry)
        elif alpha_type == "负向":
            bearish.append(verdict_entry)

    # ── 5. 今日判定结论 ──
    if veto or score <= -3:
        today_conclusion = "偏空，不做多"
    elif score >= 3:
        today_conclusion = "偏多，可做多"
    else:
        today_conclusion = "中性，观望"

    # ── 6. 明日操作结论 ──
    if veto:
        action = "不操作"
        confidence = "high"
    elif score >= 3:
        action = "做多"
        confidence = "high" if score >= 5 else "medium"
    elif score <= -3:
        action = "减仓"
        confidence = "high" if score <= -5 else "medium"
    else:
        action = "观望"
        confidence = "medium"

    # ── 7. 关键风险点 ──
    key_risks = []
    if veto:
        veto_sigs = [s for s in active_composite if sell_weights.get(s, 0) <= -3]
        for vs in veto_sigs:
            key_risks.append(f"一票否决({vs})")
    for sig, ev in signal_evidence.items():
        if ev.get("directionPattern") == "方向不稳定":
            key_risks.append(f"「{sig}」方向不稳定")
        if ev.get("alphaType") == "负向" and ev.get("isNew"):
            key_risks.append(f"「{sig}」新出现且为负向")

    # ── 8. 翻转条件 ──
    flip_conditions = []
    # 从象限转移概率推导
    t5 = transition_top5_for_state(history_summary, quadrant_distributions, cur_state)
    for t in t5:
        to_label = t.get("toStateLabel", "")
        to_wr = t.get("targetWinRate")
        prob = t.get("probability", 0)
        if to_wr is not None and to_wr >= 0.55 and prob >= 0.10:
            flip_conditions.append(f"若转入「{to_label}」(概率{prob*100:.0f}%)，历史胜率{to_wr*100:.0f}%")
    # 从超额回归推导
    if e5_bucket_name in ("P15-(过冷)", "P15-P30"):
        flip_conditions.append(f"5d超额过冷({e5_bucket_name})，均值回归概率高")
    if e10_bucket_name == "P15-(过冷)":
        flip_conditions.append(f"10d超额过冷，历史同档T+1超额+{e10_bdata.get('avg', 0):.2f}%")

    # ── 9. 历史类比 ──
    by_window = {item.get("window"): item for item in window_stats}
    historical_analogy = {
        "similarCount": len(similar_cases),
        "avgT1": by_window.get("1d", {}).get("avgReturn"),
        "avgT3": by_window.get("3d", {}).get("avgReturn"),
        "winRate1d": by_window.get("1d", {}).get("winRate"),
    }

    return {
        "todayVerdict": {
            "conclusion": today_conclusion,
            "score": score,
            "veto": veto,
            "scoreBreakdown": score_breakdown,
            "excessReversion": excess_reversion,
            "quadrantWinRate": quadrant_wr,
        },
        "tomorrowAction": {
            "action": action,
            "confidence": confidence,
            "bullishSignals": bullish,
            "bearishSignals": bearish,
            "keyRisks": key_risks[:5],
            "historicalAnalogy": historical_analogy,
            "flipConditions": flip_conditions[:3],
        },
        "signals": signal_evidence,
    }



    print("正在构建 aiInsight...")
    playbook = operator_playbook.get("playbook", {})

    top_signals = sorted(
        [s for s in signal_lifts if (s.get("avg_next_1d_delta_pp") or 0) != 0],
        key=lambda s: abs(s.get("avg_next_1d_delta_pp") or 0),
        reverse=True,
    )[:3]
    top_signal_names = [s.get("display_label") or s.get("label", "") for s in top_signals]

    parts = []
    if top_signal_names:
        parts.append(f"最强信号：{'、'.join(top_signal_names)}")
    parts.append(f"极端背离事件 {len(extreme_divergences)} 次")
    combos = operator_playbook.get("combination_synergies", [])
    if combos:
        parts.append(f"信号组合效应 {len(combos)} 条")
    research_details = "；".join(parts)

    return {
        "advice": {
            "watch": (playbook.get("watch_for") or [""])[0],
            "confirm": (playbook.get("confirmations") or [""])[0],
            "failure": (playbook.get("invalidations") or [""])[0],
            "constraint": playbook.get("sample_note") or (personality_profile.get("sample_warnings") or [""])[0],
        },
        "watchPoints": operator_playbook.get("regime", {}).get("reasons", []),
        "researchDetails": research_details,
    }


def main() -> None:
    print("=" * 60)
    print("开始生成 dashboard_view.json")
    print("=" * 60)
    data = load_all_data()
    anchor_code = data["config"].get("anchor", {}).get("symbol", "")
    close_by_date = load_anchor_close_prices(anchor_code) if anchor_code else {}
    transitions = build_transitions(data["history_summary"], data["state_transitions"])
    similar_cases, window_stats = compute_similar_cases(data["history_summary"], close_by_date)
    score_bucket_stats = compute_score_bucket_stats(data["v2_scoring"], data["history_summary"])

    # 「今日看板」专属数据预计算
    print("正在构建 today 数据...")
    trends_payload = build_trends(data["rolling_metrics"], data["history_summary"], data["personality_profile"], close_by_date)
    quadrant_distributions = build_quadrant_distributions(data["history_summary"])
    today_alerts = build_today_alerts(trends_payload["excessReturn"], trends_payload["poolCorrelations"])
    transition_top5 = build_transition_top5(data["history_summary"], quadrant_distributions)
    today_attribution = build_today_attribution(data["history_summary"])

    # 决策模块
    print("正在构建 decision...")
    today_decision = build_decision(
        data["history_summary"],
        data["rolling_metrics"],
        quadrant_distributions,
        similar_cases,
        window_stats,
        data["operator_playbook"],
        excess_return_data=trends_payload.get("excessReturn"),
    )
    state_cockpit = build_state_cockpit(
        data["history_summary"],
        data["v2_scoring"],
        score_bucket_stats,
        similar_cases,
        window_stats,
    )

    dashboard_view = {
        "meta": build_meta(data["personality_profile"], data["config"], data["history_summary"]),
        "filter": build_filter(data["personality_profile"], data["history_summary"]),
        "summary": build_summary(
            data["personality_profile"],
            data["operator_playbook"],
            data["history_summary"],
            similar_cases,
            window_stats,
            today_alerts=today_alerts,
            transition_top5=transition_top5,
            today_attribution=today_attribution,
            quadrant_distributions=quadrant_distributions,
        ),
        "cards": build_cards(
            data["personality_profile"],
            data["operator_playbook"],
            data["history_summary"],
            data["rolling_metrics"],
            data["quadrant_stats"],
        ),
        "mapData": build_map_data(transitions, data["history_summary"], data["personality_profile"]),
        "trends": trends_payload,
        "tableData": build_table_data(
            transitions,
            data["history_summary"],
            data["signal_lifts"],
            data["extreme_divergences"],
            data["quadrant_stats"],
            data["personality_profile"],
            data["operator_playbook"],
            similar_cases,
            window_stats,
        ),
        "personality": build_personality(data["personality_profile"], data["operator_playbook"]),
        "operator": build_operator(data["operator_playbook"], data.get("drift_report", {})),
        "aiInsight": build_ai_insight(data["operator_playbook"], data["personality_profile"], data["signal_lifts"], data["extreme_divergences"]),
        "predictionEvaluation": build_prediction_evaluation(data["prediction_backtest"]),
        "decision": today_decision,
        "stateCockpit": state_cockpit,
        "dateIndex": build_date_index(
            data["history_summary"],
            close_by_date,
            data["rolling_metrics"],
            {entry["date"]: entry for entry in trends_payload.get("poolCorrelations", [])},
            quadrant_distributions,
            data["v2_scoring"],
            score_bucket_stats,
        ),
    }

    path_label = dashboard_view["summary"].get("pathLabel")
    if path_label not in PATH_LABELS:
        dashboard_view["summary"]["pathLabel"] = "unknown"

    dashboard_view["scoreBucketStats"] = score_bucket_stats

    print(f"正在写入输出文件到 {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(dashboard_view, handle, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"生成完成！文件大小：{os.path.getsize(OUTPUT_PATH) / 1024:.2f} KB")
    print("=" * 60)


if __name__ == "__main__":
    main()
