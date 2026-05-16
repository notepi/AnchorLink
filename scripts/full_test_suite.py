#!/usr/bin/env python3
"""
完整测试套件
功能：对数据层进行全面测试，确保所有功能正常工作
测试范围：
1. 结构完整性测试 - 所有字段都存在
2. 类型一致性测试 - 字段类型与定义一致
3. 计算逻辑正确性测试 - 派生字段计算正确
4. 相似度算法测试 - 相似案例匹配正确
5. 边界情况测试 - 空值、极值处理正确
6. 性能测试 - 脚本运行速度符合要求
"""

import os
import json
import time
import csv
from pathlib import Path
from typing import Dict, List, Any, get_type_hints

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "output"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_dashboard_view.py"

# 加载生成的数据
with open(DATA_DIR / "dashboard_view.json", "r", encoding="utf-8") as f:
    dashboard = json.load(f)

# 加载原始数据
def load_csv(filename: str) -> list:
    data = []
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k, v in row.items():
                if v == "":
                    row[k] = None
                else:
                    try:
                        row[k] = float(v)
                        if row[k].is_integer():
                            row[k] = int(row[k])
                    except (ValueError, TypeError):
                        pass
            data.append(row)
    return data

def load_json(filename: str) -> dict:
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)

history_summary = load_csv("history_summary.csv")
personality_profile = load_json("history_personality_profile.json")
operator_playbook = load_json("history_operator_playbook.json")

test_results = []

def add_test_result(name: str, passed: bool, message: str = "") -> None:
    test_results.append({
        "name": name,
        "passed": passed,
        "message": message
    })
    status = "✅ 通过" if passed else "❌ 失败"
    print(f"{status} {name}")
    if message:
        print(f"   {message}")

print("=" * 80)
print("🚀 开始完整测试套件")
print("=" * 80)

# ------------------------------------------------------------------------------
# 1. 结构完整性测试
# ------------------------------------------------------------------------------
print("\n📋 1. 结构完整性测试")
print("-" * 40)

required_top_level_fields = [
    "meta", "filter", "summary", "cards", "mapData",
    "trends", "tableData", "personality", "operator", "aiInsight"
]

missing_fields = [f for f in required_top_level_fields if f not in dashboard]
if missing_fields:
    add_test_result("一级字段完整性", False, f"缺失字段: {', '.join(missing_fields)}")
else:
    add_test_result("一级字段完整性", True, f"所有{len(required_top_level_fields)}个一级字段都存在")

# 测试tableData子字段完整性
required_table_fields = [
    "coreMetrics", "conclusion", "quadrantStats", "signalLifts",
    "extremeDivergences", "stateTransitions", "transitionSummaries",
    "rankedTransitionPaths", "signalCombinations", "combinationSynergies",
    "decisionSummary", "tradingPlaybook", "pathStats", "windowStats",
    "similarCases", "signalDetail", "signalShift", "preferenceList",
    "avoidList", "relationshipProfile", "contraList", "trapList"
]

missing_table_fields = [f for f in required_table_fields if f not in dashboard["tableData"]]
if missing_table_fields:
    add_test_result("tableData字段完整性", False, f"缺失字段: {', '.join(missing_table_fields)}")
else:
    add_test_result("tableData字段完整性", True, f"所有{len(required_table_fields)}个tableData字段都存在")

# 测试personality字段完整性
required_personality_fields = [
    "asOfDate", "dateRangeStart", "dateRangeEnd", "sampleDays",
    "validSampleDays", "summaryMetrics", "summary", "habitPatterns",
    "counterIntuitivePatterns", "trapPatterns", "relationshipProfile",
    "pathPatterns", "stability", "sampleWarnings"
]

missing_personality_fields = [f for f in required_personality_fields if f not in dashboard["personality"]]
if missing_personality_fields:
    add_test_result("personality字段完整性", False, f"缺失字段: {', '.join(missing_personality_fields)}")
else:
    add_test_result("personality字段完整性", True, f"所有{len(required_personality_fields)}个personality字段都存在")

# ------------------------------------------------------------------------------
# 2. 类型一致性测试
# ------------------------------------------------------------------------------
print("\n📐 2. 类型一致性测试")
print("-" * 40)

def check_type(value: Any, expected_type: Any, field_name: str) -> bool:
    if value is None:
        return True  # 空值允许
    if expected_type == int and isinstance(value, float) and value.is_integer():
        return True  # 整数型的float也接受
    return isinstance(value, expected_type)

type_tests = [
    ("meta.sampleDays", dashboard["meta"]["sampleDays"], int),
    ("meta.validSampleDays", dashboard["meta"]["validSampleDays"], int),
    ("tableData.coreMetrics.baselineWinRate1d", dashboard["tableData"]["coreMetrics"]["baselineWinRate1d"], (float, int, type(None))),
    ("tableData.similarCases", dashboard["tableData"]["similarCases"], list),
    ("tableData.similarCases[0].similarity", dashboard["tableData"]["similarCases"][0]["similarity"], (float, int) if dashboard["tableData"]["similarCases"] else type(None)),
    ("tableData.signalLifts", dashboard["tableData"]["signalLifts"], list),
    ("tableData.stateTransitions", dashboard["tableData"]["stateTransitions"], list),
    ("personality.sampleDays", dashboard["personality"]["sampleDays"], int),
    ("aiInsight.advice.watch", dashboard["aiInsight"]["advice"]["watch"], str),
    ("cards", dashboard["cards"], list),
]

type_errors = []
for field_name, value, expected_type in type_tests:
    if not check_type(value, expected_type, field_name):
        type_errors.append(f"{field_name}: 期望{expected_type.__name__}, 实际{type(value).__name__}")

if type_errors:
    add_test_result("字段类型一致性", False, f"类型不匹配: {'; '.join(type_errors)}")
else:
    add_test_result("字段类型一致性", True, "所有测试字段类型都正确")

# ------------------------------------------------------------------------------
# 3. 计算逻辑正确性测试
# ------------------------------------------------------------------------------
print("\n🧮 3. 计算逻辑正确性测试")
print("-" * 40)

# 3.1 测试窗口统计计算
window_stats = dashboard["tableData"]["windowStats"]
if window_stats and len(window_stats) >= 3:
    add_test_result("窗口统计存在", True, f"有{len(window_stats)}个窗口统计：{[w['window'] for w in window_stats]}")
else:
    add_test_result("窗口统计存在", False, "窗口统计缺失或不足3个")

# 3.2 测试状态转移摘要
transition_summaries = dashboard["tableData"]["transitionSummaries"]
if transition_summaries and len(transition_summaries) > 0:
    add_test_result("状态转移摘要存在", True, f"生成了{len(transition_summaries)}个转移摘要")
else:
    add_test_result("状态转移摘要存在", False, "状态转移摘要缺失")

# 3.3 测试决策摘要
decision_summary = dashboard["tableData"]["decisionSummary"]
expected_stance = operator_playbook["playbook"].get("stance", "")
stance_map = {
    "active_watch": "积极观察",
    "cautious_watch": "谨慎观察",
    "wait": "观望"
}
expected_stance_name = stance_map.get(expected_stance, "观望")

if decision_summary.get("stance") == expected_stance and decision_summary.get("stanceName") == expected_stance_name:
    add_test_result("决策摘要计算", True, f"操作倾向正确：{expected_stance_name}")
else:
    add_test_result("决策摘要计算", False, f"操作倾向不匹配，期望{expected_stance_name}, 实际{decision_summary.get('stanceName')}")

# 3.4 测试性格档案映射
if dashboard["summary"]["stabilityVerdict"] == personality_profile["stability"].get("status"):
    add_test_result("稳定性判断映射", True, f"稳定性判断正确：{dashboard['summary']['stabilityVerdict']}")
else:
    add_test_result("稳定性判断映射", False, f"稳定性判断不匹配")

# ------------------------------------------------------------------------------
# 4. 相似度算法正确性测试
# ------------------------------------------------------------------------------
print("\n🔍 4. 相似度算法正确性测试")
print("-" * 40)

similar_cases = dashboard["tableData"]["similarCases"]
if similar_cases:
    # 检查是否按相似度降序排列
    similarities = [sc.get("similarity", 0) for sc in similar_cases]
    if similarities == sorted(similarities, reverse=True):
        add_test_result("相似案例排序", True, "按相似度降序排列正确")
    else:
        add_test_result("相似案例排序", False, "排序不正确")

    # 检查相似度值范围是否在0-1之间
    invalid_similarities = [s for s in similarities if not (0 <= s <= 1)]
    if not invalid_similarities:
        add_test_result("相似度值范围", True, "所有相似度值都在0-1之间")
    else:
        add_test_result("相似度值范围", False, f"有{len(invalid_similarities)}个异常值")

    # 验证相似案例都能在原始数据中找到
    missing_cases = []
    for sc in similar_cases:
        date = sc.get("date")
        found = any(str(row.get("date")) == str(date) for row in history_summary)
        if not found:
            missing_cases.append(date)

    if not missing_cases:
        add_test_result("相似案例有效性", True, "所有相似案例都能在原始数据中找到")
    else:
        add_test_result("相似案例有效性", False, f"找不到案例：{', '.join(missing_cases)}")
else:
    add_test_result("相似案例存在", False, "没有相似案例数据")

# ------------------------------------------------------------------------------
# 5. 边界情况测试
# ------------------------------------------------------------------------------
print("\n⚠️ 5. 边界情况测试")
print("-" * 40)

# 5.1 空值处理测试
null_fields = []
for field in ["signalDetail", "signalShift"]:
    if dashboard["tableData"][field] is None:
        null_fields.append(field)

if null_fields:
    add_test_result("空值字段处理", True, f"按需加载字段正确设置为None：{', '.join(null_fields)}")
else:
    add_test_result("空值字段处理", False, "按需加载字段没有正确设置为None")

# 5.2 数组为空处理测试
empty_array_tests = [
    ("偏好环境列表", dashboard["tableData"]["preferenceList"]),
    ("规避环境列表", dashboard["tableData"]["avoidList"]),
    ("反直觉机会列表", dashboard["tableData"]["contraList"]),
    ("信号陷阱列表", dashboard["tableData"]["trapList"]),
]

empty_array_errors = []
for name, arr in empty_array_tests:
    if not isinstance(arr, list):
        empty_array_errors.append(f"{name} 不是数组类型")

if empty_array_errors:
    add_test_result("数组类型处理", False, "; ".join(empty_array_errors))
else:
    add_test_result("数组类型处理", True, "所有列表字段都是正确的数组类型")

# ------------------------------------------------------------------------------
# 6. 性能测试
# ------------------------------------------------------------------------------
print("\n⚡ 6. 性能测试")
print("-" * 40)

# 测试数据合并脚本运行时间
start_time = time.time()
result = os.system(f"python3 {SCRIPT_PATH} > /dev/null 2>&1")
end_time = time.time()
run_time = end_time - start_time

if result == 0:
    add_test_result("脚本运行成功", True, "数据合并脚本运行成功")
else:
    add_test_result("脚本运行成功", False, "数据合并脚本运行失败")

if run_time < 30:  # 要求<30秒
    add_test_result("脚本运行速度", True, f"运行时间：{run_time:.2f}秒，符合<30秒要求")
else:
    add_test_result("脚本运行速度", False, f"运行时间：{run_time:.2f}秒，超过30秒要求")

# ------------------------------------------------------------------------------
# 7. 校验脚本测试
# ------------------------------------------------------------------------------
print("\n✅ 7. 校验脚本测试")
print("-" * 40)

validate_script = PROJECT_ROOT / "scripts" / "validate_data.py"
start_time = time.time()
result = os.system(f"python3 {validate_script} > /dev/null 2>&1")
end_time = time.time()
validate_time = end_time - start_time

if result == 0:
    add_test_result("校验脚本运行成功", True, f"校验脚本运行成功，耗时{validate_time:.2f}秒")
else:
    add_test_result("校验脚本运行成功", False, "校验脚本运行失败")

# ------------------------------------------------------------------------------
# 测试结果汇总
# ------------------------------------------------------------------------------
print("\n" + "=" * 80)
print("📊 测试结果汇总")
print("=" * 80)

passed = sum(1 for r in test_results if r["passed"])
failed = sum(1 for r in test_results if not r["passed"])
total = len(test_results)

print(f"总测试用例：{total}个")
print(f"通过：{passed}个 ✅")
print(f"失败：{failed}个 ❌")
print(f"通过率：{passed/total*100:.1f}%")

print("\n📋 详细测试结果：")
for r in test_results:
    status = "✅" if r["passed"] else "❌"
    print(f"{status} {r['name']}")
    if r["message"]:
        print(f"   {r['message']}")

print("\n" + "=" * 80)
if failed == 0:
    print("🎉 所有测试全部通过！数据层质量符合生产环境要求。")
else:
    print("⚠️  部分测试失败，请检查相关问题后重新测试。")
    exit(1)
