#!/usr/bin/env python3
"""
数据校验脚本
功能：验证生成的dashboard_view.json是否符合规范，并且与旧页面显示值完全一致
校验层级：
1. Schema校验 - 验证JSON结构是否符合定义
2. 字段完整性校验 - 验证所有必要字段都存在
3. 数据范围校验 - 验证数值在合理范围内
4. 一致性校验 - 验证相关字段逻辑关系正确
5. 旧页面对齐校验 - 验证值与旧页面完全一致
"""

import os
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# 配置常量
PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = PROJECT_ROOT / "data" / "schema" / "dashboard_view.schema.json"
DATA_PATH = PROJECT_ROOT / "data" / "output" / "dashboard_view.json"
OLD_PAGE_DATA_PATH = PROJECT_ROOT / "data" / "output" / "old_page_data.json"  # 旧页面导出的数据，用于对比


class DataValidator:
    def __init__(self):
        self.schema = self._load_schema()
        self.data = self._load_data()
        self.old_page_data = self._load_old_page_data()
        self.errors = []
        self.warnings = []

    def _load_schema(self) -> Dict[str, Any]:
        """加载JSON Schema"""
        try:
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载Schema失败: {e}")
            sys.exit(1)

    def _load_data(self) -> Dict[str, Any]:
        """加载生成的dashboard_view.json"""
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载数据文件失败: {e}")
            sys.exit(1)

    def _load_old_page_data(self) -> Optional[Dict[str, Any]]:
        """加载旧页面导出的对比数据（如果存在）"""
        if not OLD_PAGE_DATA_PATH.exists():
            print(f"警告：旧页面对比数据文件不存在，将跳过旧页面对齐校验: {OLD_PAGE_DATA_PATH}")
            return None
        try:
            with open(OLD_PAGE_DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载旧页面数据失败: {e}")
            return None

    def validate_schema(self) -> bool:
        """验证JSON Schema符合性"""
        print("🔍 开始Schema校验...")
        try:
            from jsonschema import validate, ValidationError
            validate(instance=self.data, schema=self.schema)
            print("✅ Schema校验通过")
            return True
        except ImportError:
            print("⚠️  未安装jsonschema库，跳过Schema校验")
            print("   如需启用Schema校验，请运行: pip install jsonschema")
            return True
        except ValidationError as e:
            self.errors.append(f"Schema校验失败: {e.message}")
            print(f"❌ Schema校验失败: {e.message}")
            return False

    def validate_field_completeness(self) -> bool:
        """验证字段完整性"""
        print("🔍 开始字段完整性校验...")
        required_top_level_fields = [
            "meta", "filter", "summary", "cards", "mapData",
            "trends", "tableData", "personality", "operator", "aiInsight"
        ]

        # 检查一级字段
        missing_fields = [f for f in required_top_level_fields if f not in self.data]
        if missing_fields:
            error_msg = f"缺失一级字段: {', '.join(missing_fields)}"
            self.errors.append(error_msg)
            print(f"❌ {error_msg}")
            return False

        # 检查meta字段
        required_meta_fields = [
            "dateRange", "dataUpdateTime", "stockName", "stockCode",
            "sampleDays", "validSampleDays"
        ]
        missing_meta_fields = [f for f in required_meta_fields if f not in self.data["meta"]]
        if missing_meta_fields:
            error_msg = f"meta字段缺失: {', '.join(missing_meta_fields)}"
            self.errors.append(error_msg)
            print(f"❌ {error_msg}")
            return False

        # 检查tableData关键字段
        required_table_fields = [
            "coreMetrics", "conclusion", "quadrantStats", "signalLifts",
            "extremeDivergences", "stateTransitions", "similarCases",
            "preferenceList", "avoidList", "contraList", "trapList"
        ]
        missing_table_fields = [f for f in required_table_fields if f not in self.data["tableData"]]
        if missing_table_fields:
            error_msg = f"tableData字段缺失: {', '.join(missing_table_fields)}"
            self.errors.append(error_msg)
            print(f"❌ {error_msg}")
            return False

        print("✅ 字段完整性校验通过")
        return True

    def validate_data_ranges(self) -> bool:
        """验证数据范围合理性"""
        print("🔍 开始数据范围校验...")

        # 校验收益率范围（合理范围应该在-20到20之间，即-20%到20%，百分比形式）
        def check_return_range(value: Any, field_name: str) -> None:
            if value is None:
                return
            try:
                val = float(value)
                if not (-20 <= val <= 20):
                    self.warnings.append(f"{field_name} 值异常: {val}，超出合理范围[-20, 20]")
            except (ValueError, TypeError):
                pass

        # 校验胜率范围（0到1之间）
        def check_win_rate_range(value: Any, field_name: str) -> None:
            if value is None:
                return
            try:
                val = float(value)
                if not (0 <= val <= 1):
                    self.warnings.append(f"{field_name} 值异常: {val}，超出合理范围[0, 1]")
            except (ValueError, TypeError):
                pass

        # 校验概率范围（0到1之间）
        def check_probability_range(value: Any, field_name: str) -> None:
            if value is None:
                return
            try:
                val = float(value)
                if not (0 <= val <= 1):
                    self.warnings.append(f"{field_name} 值异常: {val}，超出合理范围[0, 1]")
            except (ValueError, TypeError):
                pass

        # 校验核心指标
        core_metrics = self.data["tableData"].get("coreMetrics", {})
        for field in ["baselineWinRate1d", "baselineWinRate3d", "baselineWinRate5d"]:
            check_win_rate_range(core_metrics.get(field), f"coreMetrics.{field}")

        for field in ["medianExcess3d", "payoffRatio", "sharpeLikeRatio"]:
            value = core_metrics.get(field)
            if value is not None and not isinstance(value, (int, float)):
                self.warnings.append(f"coreMetrics.{field} 类型异常，应该为数值类型")

        # 校验信号表现
        signal_lifts = self.data["tableData"].get("signalLifts", [])
        for i, sl in enumerate(signal_lifts):
            for field in ["avgReturn1d", "avgReturn3d", "avgReturn5d", "excessReturn1d"]:
                check_return_range(sl.get(field), f"signalLifts[{i}].{field}")
            for field in ["winRate1d", "winRate3d", "winRate5d"]:
                check_win_rate_range(sl.get(field), f"signalLifts[{i}].{field}")

        # 校验状态转移
        state_transitions = self.data["tableData"].get("stateTransitions", [])
        for i, st in enumerate(state_transitions):
            check_probability_range(st.get("probability"), f"stateTransitions[{i}].probability")
            for field in ["avgNext1dReturn", "avgNext3dReturn", "avgNext5dReturn"]:
                check_return_range(st.get(field), f"stateTransitions[{i}].{field}")
            for field in ["winRate1d", "winRate3d", "winRate5d"]:
                check_win_rate_range(st.get(field), f"stateTransitions[{i}].{field}")

        # 校验相似案例
        similar_cases = self.data["tableData"].get("similarCases", [])
        for i, sc in enumerate(similar_cases):
            for field in ["next1dReturn", "next3dReturn", "next5dReturn"]:
                check_return_range(sc.get(field), f"similarCases[{i}].{field}")
            similarity = sc.get("similarity")
            if similarity is not None and not (0 <= similarity <= 1):
                self.warnings.append(f"similarCases[{i}].similarity 值异常: {similarity}，超出合理范围[0, 1]")

        if self.warnings:
            print(f"⚠️  数据范围校验发现 {len(self.warnings)} 个警告")
            for w in self.warnings:
                print(f"   - {w}")
        else:
            print("✅ 数据范围校验通过")
        return True

    def validate_consistency(self) -> bool:
        """验证数据一致性"""
        print("🔍 开始一致性校验...")

        # 校验meta中的样本天数与personality中的样本天数一致
        meta_sample_days = self.data["meta"].get("sampleDays")
        personality_sample_days = self.data["personality"].get("sampleDays")
        if meta_sample_days is not None and personality_sample_days is not None:
            if meta_sample_days != personality_sample_days:
                self.errors.append(
                    f"样本天数不一致: meta.sampleDays={meta_sample_days}, "
                    f"personality.sampleDays={personality_sample_days}"
                )
                return False

        # 校验similarCases的相似度排序是否正确（降序）
        similar_cases = self.data["tableData"].get("similarCases", [])
        if similar_cases:
            similarities = [sc.get("similarity", 0) for sc in similar_cases]
            if similarities != sorted(similarities, reverse=True):
                self.warnings.append("similarCases 不是按相似度降序排列")

        print("✅ 一致性校验通过")
        return True

    def validate_v2_contract(self) -> bool:
        """/history-v2 关键数据契约校验。"""
        print("🔍 开始 /history-v2 契约校验...")
        ok = True

        allowed_states = {
            "positive+positive", "positive+neutral", "positive+negative",
            "neutral+positive", "neutral+neutral", "neutral+negative",
            "negative+positive", "negative+neutral", "negative+negative",
        }
        allowed_path_labels = {
            "strong_rise", "pullback_after_rise", "continue_fall",
            "weak_repair", "range_bound", "disagreement", "unknown",
        }

        def add_error(message: str) -> None:
            nonlocal ok
            ok = False
            self.errors.append(message)
            print(f"❌ {message}")

        def require_string_date(value: Any, path: str) -> None:
            if not isinstance(value, str) or len(value) != 8 or not value.isdigit():
                add_error(f"{path} 必须是 YYYYMMDD 字符串，当前为 {value!r}")

        end_date = self.data.get("filter", {}).get("endDate")
        require_string_date(self.data.get("filter", {}).get("startDate"), "filter.startDate")
        require_string_date(end_date, "filter.endDate")

        current_date = self.data.get("summary", {}).get("currentMapping", {}).get("date")
        require_string_date(current_date, "summary.currentMapping.date")
        if current_date != end_date:
            add_error(f"currentMapping.date 必须等于 filter.endDate，当前 {current_date!r} != {end_date!r}")

        path_label = self.data.get("summary", {}).get("pathLabel")
        if path_label not in allowed_path_labels:
            add_error(f"summary.pathLabel 必须是稳定枚举，当前为 {path_label!r}")

        trends = self.data.get("trends", {})
        for field in ["signalTimeline", "excessReturn", "followDeviation"]:
            rows = trends.get(field, [])
            if not rows:
                add_error(f"trends.{field} 不能为空")
                continue
            for index, row in enumerate(rows):
                require_string_date(row.get("date"), f"trends.{field}[{index}].date")
            if rows[-1].get("date") != end_date:
                add_error(f"trends.{field} 最后一天必须等于结束日，当前 {rows[-1].get('date')!r} != {end_date!r}")

        transitions = self.data.get("tableData", {}).get("stateTransitions", [])
        if not transitions:
            add_error("tableData.stateTransitions 不能为空")
        else:
            nonzero = False
            for index, transition in enumerate(transitions):
                from_state = transition.get("fromState")
                to_state = transition.get("toState")
                if from_state not in allowed_states:
                    add_error(f"stateTransitions[{index}].fromState 非标准状态 key: {from_state!r}")
                if to_state not in allowed_states:
                    add_error(f"stateTransitions[{index}].toState 非标准状态 key: {to_state!r}")
                if not transition.get("fromStateLabel") or not transition.get("toStateLabel"):
                    add_error(f"stateTransitions[{index}] 缺少中文状态标签")
                if (transition.get("probability") or 0) > 0:
                    nonzero = True
            if not nonzero:
                add_error("迁移矩阵不能全为 0")

        ranked_paths = self.data.get("tableData", {}).get("rankedTransitionPaths", [])
        if not ranked_paths:
            add_error("tableData.rankedTransitionPaths 不能为空")
        for index, path in enumerate(ranked_paths[:10]):
            if path.get("fromState") not in allowed_states or path.get("toState") not in allowed_states:
                add_error(f"rankedTransitionPaths[{index}] 存在非标准状态 key")
            label_text = f"{path.get('fromStateLabel', '')}{path.get('toStateLabel', '')}"
            if "未知" in label_text:
                add_error(f"rankedTransitionPaths[{index}] 不允许出现未知状态")
            if (path.get("count") or 0) <= 0:
                add_error(f"rankedTransitionPaths[{index}].count 必须大于 0")

        similar_cases = self.data.get("tableData", {}).get("similarCases", [])
        if len(similar_cases) < 5:
            add_error(f"similarCases 至少需要 5 条用于原型展示，当前 {len(similar_cases)} 条")
        for index, item in enumerate(similar_cases):
            require_string_date(item.get("date"), f"tableData.similarCases[{index}].date")

        if ok:
            print("✅ /history-v2 契约校验通过")
        return ok

    def validate_old_page_alignment(self) -> bool:
        """验证与旧页面数据对齐"""
        if not self.old_page_data:
            print("⚠️  没有旧页面对比数据，跳过旧页面对齐校验")
            return True

        print("🔍 开始旧页面对齐校验...")
        mismatches = []

        # 递归对比两个对象的字段
        def compare_objects(obj1: Any, obj2: Any, path: str = "") -> None:
            if type(obj1) != type(obj2):
                mismatches.append(f"{path}: 类型不一致，旧页面是{type(obj2).__name__}，新数据是{type(obj1).__name__}")
                return

            if isinstance(obj1, dict):
                # 检查obj2的所有字段在obj1中都存在
                for key in obj2:
                    if key not in obj1:
                        mismatches.append(f"{path}.{key}: 新数据缺失该字段")
                    else:
                        compare_objects(obj1[key], obj2[key], f"{path}.{key}")
                # 检查obj1是否有多余字段
                for key in obj1:
                    if key not in obj2:
                        self.warnings.append(f"{path}.{key}: 新数据包含旧页面没有的字段")

            elif isinstance(obj1, list):
                if len(obj1) != len(obj2):
                    mismatches.append(f"{path}: 数组长度不一致，旧页面是{len(obj2)}，新数据是{len(obj1)}")
                    return
                for i, (item1, item2) in enumerate(zip(obj1, obj2)):
                    compare_objects(item1, item2, f"{path}[{i}]")

            else:
                # 数值类型允许微小误差（浮点精度问题）
                if isinstance(obj1, (int, float)) and isinstance(obj2, (int, float)):
                    if abs(obj1 - obj2) > 1e-6:
                        mismatches.append(f"{path}: 值不一致，旧页面是{obj2}，新数据是{obj1}，差异{abs(obj1-obj2)}")
                else:
                    if obj1 != obj2:
                        mismatches.append(f"{path}: 值不一致，旧页面是{repr(obj2)}，新数据是{repr(obj1)}")

        compare_objects(self.data, self.old_page_data)

        if mismatches:
            print(f"❌ 旧页面对齐校验发现 {len(mismatches)} 个不匹配项:")
            for m in mismatches[:20]:  # 最多显示20个
                print(f"   - {m}")
            if len(mismatches) > 20:
                print(f"   - ... 还有 {len(mismatches) - 20} 个不匹配项")
            return False
        else:
            print("✅ 旧页面对齐校验通过，所有字段值与旧页面完全一致")
            return True

    def run_all_validations(self) -> bool:
        """运行所有校验"""
        print("=" * 70)
        print("开始数据校验")
        print("=" * 70)

        all_passed = True

        # 运行各项校验
        if not self.validate_schema():
            all_passed = False
        if not self.validate_field_completeness():
            all_passed = False
        if not self.validate_data_ranges():
            all_passed = False
        if not self.validate_consistency():
            all_passed = False
        if not self.validate_v2_contract():
            all_passed = False
        if not self.validate_old_page_alignment():
            all_passed = False

        print("=" * 70)
        if all_passed:
            print("✅ 所有校验通过！数据完全符合要求")
            if self.warnings:
                print(f"⚠️  注意：共有 {len(self.warnings)} 个警告，不影响使用，但建议检查")
        else:
            print(f"❌ 校验失败，共有 {len(self.errors)} 个错误，{len(self.warnings)} 个警告")
        print("=" * 70)

        return all_passed


def main():
    validator = DataValidator()
    success = validator.run_all_validations()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
