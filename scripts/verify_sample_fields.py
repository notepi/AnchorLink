#!/usr/bin/env python3
from __future__ import annotations
"""
/history-v2 key-field regression checks.

This script compares dashboard_view.json with the source CSV/JSON files for
the fields that directly affect visual trust on /history-v2.
"""

import csv
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "output"
STATE_KEYS = {
    "positive+positive", "positive+neutral", "positive+negative",
    "neutral+positive", "neutral+neutral", "neutral+negative",
    "negative+positive", "negative+neutral", "negative+negative",
}


def parse_csv_value(key: str, value: str | None) -> Any:
    if value is None or value == "":
        return None
    if key in {"date", "event_date"}:
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    return int(number) if number.is_integer() else number


def load_csv(filename: str) -> list[dict[str, Any]]:
    with open(DATA_DIR / filename, "r", encoding="utf-8") as handle:
        rows = [
            {key: parse_csv_value(key, value) for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]
    if rows and "date" in rows[0]:
        rows.sort(key=lambda row: row.get("date") or "")
    return rows


def load_json(filename: str) -> dict[str, Any]:
    with open(DATA_DIR / filename, "r", encoding="utf-8") as handle:
        return json.load(handle)


def eq(a: Any, b: Any) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-6
        except (TypeError, ValueError):
            return False
    return a == b


dashboard = load_json("dashboard_view.json")
history_summary = load_csv("history_summary.csv")
rolling_metrics = load_csv("history_rolling_metrics.csv")
personality_profile = load_json("history_personality_profile.json")

latest_summary = history_summary[-1]
latest_rolling = rolling_metrics[-1]
max_summary_date = max(row["date"] for row in history_summary)
max_rolling_date = max(row["date"] for row in rolling_metrics)

ranked_paths = dashboard["tableData"]["rankedTransitionPaths"]
state_transitions = dashboard["tableData"]["stateTransitions"]
similar_cases = dashboard["tableData"]["similarCases"]

test_cases = [
    {
        "name": "1. 当前映射日期使用最新交易日",
        "generated_value": dashboard["summary"]["currentMapping"]["date"],
        "expected_value": max_summary_date,
    },
    {
        "name": "2. 筛选结束日期使用最新交易日",
        "generated_value": dashboard["filter"]["endDate"],
        "expected_value": max_summary_date,
    },
    {
        "name": "3. 当前映射日期必须是字符串",
        "generated_value": type(dashboard["summary"]["currentMapping"]["date"]).__name__,
        "expected_value": "str",
    },
    {
        "name": "4. 信号时间轴最后一天等于最新日",
        "generated_value": dashboard["trends"]["signalTimeline"][-1]["date"],
        "expected_value": max_summary_date,
    },
    {
        "name": "5. 滚动超额最后一天等于最新滚动日",
        "generated_value": dashboard["trends"]["excessReturn"][-1]["date"],
        "expected_value": max_rolling_date,
    },
    {
        "name": "6. 当前行业 Beta 对齐原始最新行",
        "generated_value": dashboard["summary"]["currentMapping"]["industryBeta"],
        "expected_value": latest_summary["industry_beta"],
    },
    {
        "name": "7. 当前个股 Alpha 对齐原始最新行",
        "generated_value": dashboard["summary"]["currentMapping"]["anchorAlpha"],
        "expected_value": latest_summary["anchor_alpha"],
    },
    {
        "name": "8. 当前风险等级对齐原始最新行",
        "generated_value": dashboard["summary"]["currentMapping"]["riskLevel"],
        "expected_value": latest_summary["risk_level"],
    },
    {
        "name": "9. 最新 5 日超额来自 rolling_metrics",
        "generated_value": dashboard["trends"]["excessReturn"][-1]["excess5d"],
        "expected_value": latest_rolling["excess_5d"],
    },
    {
        "name": "10. 迁移矩阵使用标准状态 key",
        "generated_value": state_transitions[0]["fromState"] in STATE_KEYS and state_transitions[0]["toState"] in STATE_KEYS,
        "expected_value": True,
    },
    {
        "name": "11. Top 路径有 rank/count/from/to",
        "generated_value": all(key in ranked_paths[0] for key in ["rank", "count", "fromState", "toState", "fromStateLabel", "toStateLabel"]),
        "expected_value": True,
    },
    {
        "name": "12. Top 路径无未知状态",
        "generated_value": "未知" in f"{ranked_paths[0].get('fromStateLabel', '')}{ranked_paths[0].get('toStateLabel', '')}",
        "expected_value": False,
    },
    {
        "name": "13. 相似案例至少恢复 5 条展示",
        "generated_value": len(similar_cases) >= 5,
        "expected_value": True,
    },
    {
        "name": "14. 相似样本计数等于实际列表长度",
        "generated_value": dashboard["summary"]["currentMapping"]["similarSampleCount"],
        "expected_value": len(similar_cases),
    },
    {
        "name": "15. 样本天数来自 personality_profile",
        "generated_value": dashboard["meta"]["sampleDays"],
        "expected_value": personality_profile["sample_days"],
    },
]

print("=" * 92)
print("/history-v2 关键字段回归验证")
print("=" * 92)
print(f"{'字段名称':<44} {'生成值':<22} {'期望值':<22} {'结果':<8}")
print("-" * 92)

passed = 0
failed = 0

for case in test_cases:
    generated = case["generated_value"]
    expected = case["expected_value"]
    success = eq(generated, expected)
    if success:
        passed += 1
        status = "通过"
    else:
        failed += 1
        status = "失败"

    generated_text = repr(generated)
    expected_text = repr(expected)
    if len(generated_text) > 20:
        generated_text = generated_text[:19] + "…"
    if len(expected_text) > 20:
        expected_text = expected_text[:19] + "…"
    print(f"{case['name']:<44} {generated_text:<22} {expected_text:<22} {status:<8}")

print("-" * 92)
print(f"验证结果：{passed} 个通过，{failed} 个失败")
print("=" * 92)

if failed:
    raise SystemExit(1)
