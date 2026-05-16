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


def compute_similar_cases(history_summary: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    latest = latest_row(history_summary)
    if not latest:
        return [], []

    weights = {
        "industry_beta": 0.25,
        "anchor_alpha": 0.25,
        "risk_level": 0.20,
        "strongest_group": 0.15,
        "weakest_group": 0.15,
    }

    def ordinal_score(a: Any, b: Any, order: list[str]) -> float:
        if not a or not b:
            return 0.0
        aa = str(a).strip().lower()
        bb = str(b).strip().lower()
        if aa not in order or bb not in order:
            return 1.0 if aa == bb else 0.0
        distance = abs(order.index(aa) - order.index(bb))
        return 1.0 if distance == 0 else 0.5 if distance == 1 else 0.0

    def exact_score(a: Any, b: Any) -> float:
        if not a or not b:
            return 0.0
        return 1.0 if str(a).strip().lower() == str(b).strip().lower() else 0.0

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
            ordinal_score(latest.get("industry_beta"), candidate.get("industry_beta"), BETA_ORDER) * weights["industry_beta"]
            + ordinal_score(latest.get("anchor_alpha"), candidate.get("anchor_alpha"), BETA_ORDER) * weights["anchor_alpha"]
            + ordinal_score(latest.get("risk_level"), candidate.get("risk_level"), RISK_ORDER) * weights["risk_level"]
            + exact_score(latest.get("strongest_group"), candidate.get("strongest_group")) * weights["strongest_group"]
            + exact_score(latest.get("weakest_group"), candidate.get("weakest_group")) * weights["weakest_group"]
        )

    target_signals = signal_set(latest)
    candidates = [
        row
        for row in history_summary[:-1]
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

    target_labels = set(split_signals(latest.get("signal_labels")))
    similar_cases: list[dict[str, Any]] = []
    for similarity, row in top_candidates:
        matching_states = []
        if row.get("industry_beta") == latest.get("industry_beta"):
            matching_states.append(f"行业Beta:{BETA_TEXT.get(str(row.get('industry_beta')), row.get('industry_beta'))}")
        if row.get("anchor_alpha") == latest.get("anchor_alpha"):
            matching_states.append(f"个股Alpha:{BETA_TEXT.get(str(row.get('anchor_alpha')), row.get('anchor_alpha'))}")
        if row.get("risk_level") == latest.get("risk_level"):
            matching_states.append(f"风险:{RISK_TEXT.get(str(row.get('risk_level')), row.get('risk_level'))}")
        if row.get("strongest_group") == latest.get("strongest_group"):
            matching_states.append(f"最强组:{row.get('strongest_group')}")
        if row.get("weakest_group") == latest.get("weakest_group"):
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
        })

    rows = [row for _, row in top_candidates]
    window_stats = [
        {
            "window": "1d",
            "avgReturn": avg([row.get("next_1d_return") for row in rows]),
            "winRate": win_rate([row.get("next_1d_return") for row in rows]),
            "avgExcess": avg([row.get("next_1d_excess_vs_chain") for row in rows]),
        },
        {
            "window": "3d",
            "avgReturn": avg([row.get("next_3d_return") for row in rows]),
            "winRate": win_rate([row.get("next_3d_return") for row in rows]),
            "avgExcess": avg([row.get("next_3d_excess_vs_chain") for row in rows]),
        },
        {
            "window": "5d",
            "avgReturn": avg([row.get("next_5d_return") for row in rows]),
            "winRate": win_rate([row.get("next_5d_return") for row in rows]),
            "avgExcess": avg([row.get("next_5d_excess_vs_chain") for row in rows]),
        },
    ]
    return similar_cases, window_stats


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
    playbook = operator_playbook.get("playbook", {})
    watch_points = playbook.get("watch_for", [])[:3] or operator_playbook.get("regime", {}).get("reasons", [])[:3]
    if not watch_points:
        watch_points = ["观察行业Beta是否延续", "关注个股Alpha能否修复", "监测风险信号是否退潮"]

    personality_summary = personality_profile.get("personality_summary", {})
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
) -> dict[str, Any]:
    print("正在构建 trends...")
    recent_rolling = last_n(rolling_metrics, 30)
    excess_return = [
        {
            "date": str(row.get("date") or ""),
            "excess5d": row.get("excess_5d"),
            "excess10d": row.get("excess_10d"),
            "outperformStreak": row.get("outperform_streak"),
            "betaStreak": row.get("beta_streak"),
            "themeVsCoreStreak": row.get("theme_vs_core_streak"),
            "riskHighStreak": row.get("risk_high_streak"),
        }
        for row in recent_rolling
    ]

    recent_summary = last_n(history_summary, 30)
    follow_deviation = []
    for row in recent_summary:
        anchor = row.get("anchor_return")
        industry = row.get("industry_chain_median")
        excess = row.get("relative_strength_vs_industry_chain")
        if excess is None and anchor is not None and industry is not None:
            excess = anchor - industry
        follow_deviation.append({
            "date": str(row.get("date") or ""),
            "anchor": anchor,
            "industry": industry,
            "excess": excess,
            "deviation": excess,
        })

    habit_type_map = build_habit_type_map(personality_profile)
    signal_timeline = []
    price = 100.0
    for row in history_summary:
        day_return = row.get("anchor_return") or 0
        price *= 1 + float(day_return) / 100
        signals = split_signals(row.get("signal_labels"))
        signal_timeline.append({
            "date": str(row.get("date") or ""),
            "price": round(price, 4),
            "return": day_return,
            "signals": signals,
            "groups": signal_groups_for_row(row, habit_type_map),
        })

    return {
        "excessReturn": excess_return,
        "followDeviation": follow_deviation,
        "signalTimeline": signal_timeline,
        "pathPatterns": {
            pattern.get("event_label") or pattern.get("eventLabel") or "未知事件": camelize(pattern.get("avg_path") or pattern.get("avgPath") or [])
            for pattern in personality_profile.get("path_patterns", [])
        },
    }


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

    quadrant_stats_list = []
    for row in quadrant_stats:
        key = normalize_state(row.get("quadrant"))
        quadrant_stats_list.append({
            "quadrant": key,
            "quadrantName": state_label(key),
            "count": row.get("count", 0),
            "avgReturn1d": row.get("avg_next_1d"),
            "avgReturn3d": row.get("avg_next_3d"),
            "avgReturn5d": row.get("avg_next_5d"),
            "winRate1d": row.get("win_rate_1d"),
            "winRate3d": row.get("win_rate_3d"),
            "winRate5d": row.get("win_rate_5d"),
            "riskLevel": "medium",
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
            "divergenceType": row.get("divergence_type", ""),
            "divergenceDegree": row.get("divergence_degree") or row.get("divergence"),
            "anchorReturn": row.get("anchor_return"),
            "chainReturn": row.get("chain_return") or row.get("industry_chain_median"),
            "subsequentReturn1d": row.get("subsequent_return_1d") or row.get("t1_return"),
            "subsequentReturn3d": row.get("subsequent_return_3d") or row.get("t3_return"),
            "subsequentReturn5d": row.get("subsequent_return_5d"),
            "reversionDays": row.get("reversion_days"),
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
            "baselineWinRate1d": summary_metrics.get("baseline_win_rate_1d"),
            "baselineWinRate3d": summary_metrics.get("baseline_win_rate_3d"),
            "baselineWinRate5d": summary_metrics.get("baseline_win_rate_5d"),
            "medianExcess3d": summary_metrics.get("median_excess_3d"),
            "medianAdverse3d": summary_metrics.get("median_adverse_3d_proxy"),
            "payoffRatio": summary_metrics.get("payoff_ratio"),
            "sharpeLikeRatio": summary_metrics.get("sharpe_like_ratio"),
            "signalCoverageRatio": summary_metrics.get("signal_coverage_ratio"),
        },
        "conclusion": {
            "summary": personality_profile.get("personality_summary", {}).get("headline", ""),
            "confidence": personality_profile.get("personality_summary", {}).get("confidence", "medium"),
            "traits": personality_profile.get("personality_summary", {}).get("traits", []),
            "stabilityStatus": personality_profile.get("stability", {}).get("status", "insufficient"),
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
        "signalDetail": None,
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


def build_operator(operator_playbook: dict[str, Any]) -> dict[str, Any]:
    print("正在构建 operator...")
    playbook = operator_playbook.get("playbook", {})
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
    }


def build_ai_insight(operator_playbook: dict[str, Any], personality_profile: dict[str, Any]) -> dict[str, Any]:
    print("正在构建 aiInsight...")
    playbook = operator_playbook.get("playbook", {})
    return {
        "advice": {
            "watch": (playbook.get("watch_for") or [""])[0],
            "confirm": (playbook.get("confirmations") or [""])[0],
            "failure": (playbook.get("invalidations") or [""])[0],
            "constraint": playbook.get("sample_note") or (personality_profile.get("sample_warnings") or [""])[0],
        },
        "watchPoints": operator_playbook.get("regime", {}).get("reasons", []),
        "researchDetails": "",
    }


def main() -> None:
    print("=" * 60)
    print("开始生成 dashboard_view.json")
    print("=" * 60)
    data = load_all_data()
    transitions = build_transitions(data["history_summary"], data["state_transitions"])
    similar_cases, window_stats = compute_similar_cases(data["history_summary"])

    dashboard_view = {
        "meta": build_meta(data["personality_profile"], data["config"], data["history_summary"]),
        "filter": build_filter(data["personality_profile"], data["history_summary"]),
        "summary": build_summary(
            data["personality_profile"],
            data["operator_playbook"],
            data["history_summary"],
            similar_cases,
            window_stats,
        ),
        "cards": build_cards(
            data["personality_profile"],
            data["operator_playbook"],
            data["history_summary"],
            data["rolling_metrics"],
            data["quadrant_stats"],
        ),
        "mapData": build_map_data(transitions, data["history_summary"], data["personality_profile"]),
        "trends": build_trends(data["rolling_metrics"], data["history_summary"], data["personality_profile"]),
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
        "operator": build_operator(data["operator_playbook"]),
        "aiInsight": build_ai_insight(data["operator_playbook"], data["personality_profile"]),
    }

    path_label = dashboard_view["summary"].get("pathLabel")
    if path_label not in PATH_LABELS:
        dashboard_view["summary"]["pathLabel"] = "unknown"

    print(f"正在写入输出文件到 {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(dashboard_view, handle, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"生成完成！文件大小：{os.path.getsize(OUTPUT_PATH) / 1024:.2f} KB")
    print("=" * 60)


if __name__ == "__main__":
    main()
