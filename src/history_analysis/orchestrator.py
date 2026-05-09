"""
历史分析编排模块

一次性运行全部分析阶段，输出历史分析 CSV 和操盘视图 JSON。
"""

from pathlib import Path

from src.history_analysis.summary_builder import build_history_rows
from src.history_analysis.rolling_metrics import build_rolling_metrics
from src.history_analysis.quadrant_analyzer import build_quadrant_stats
from src.history_analysis.divergence_analyzer import find_extreme_divergences
from src.history_analysis.event_study import build_event_paths
from src.history_analysis.signal_analyzer import build_signal_lifts
from src.history_analysis.transition_analyzer import build_state_transitions
from src.history_analysis.counter_intuitive_analyzer import identify_counter_intuitive_signals
from src.history_analysis.conditional_signal_analyzer import build_conditional_signal_effects
from src.history_analysis.operator_playbook import build_operator_playbook
from src.output.history_csv_writer import (
    write_history_csv,
    write_rolling_csv,
    write_quadrant_csv,
    write_divergence_csv,
    write_event_study_csv,
    write_signal_lift_csv,
    write_transition_csv,
    write_counter_intuitive_csv,
    write_conditional_signal_csv,
    write_operator_playbook_json,
)


def build_history_analysis(
    output_root: Path,
    market_data_path: Path,
    divergence_threshold: float = 8.0,
    signal_min_count: int = 5,
) -> dict[str, int]:
    """
    编排全部历史分析阶段。

    Args:
        output_root: data/output/ 目录
        market_data_path: data/price/ 目录
        divergence_threshold: 极端背离阈值（百分点）
        signal_min_count: 信号最低出现次数

    Returns:
        各 CSV 的行数统计
    """
    rows = build_history_rows(output_root, market_data_path)
    if not rows:
        return {}

    results: dict[str, int] = {}

    # 1. 汇总表
    write_history_csv(rows, output_root / "history_summary.csv")
    results["history_summary.csv"] = len(rows)

    # 2. 滚动指标
    rolling = build_rolling_metrics(rows)
    write_rolling_csv(rolling, output_root / "history_rolling_metrics.csv")
    results["history_rolling_metrics.csv"] = len(rolling)

    # 3. 四象限
    quadrant = build_quadrant_stats(rows)
    write_quadrant_csv(quadrant, output_root / "history_quadrant_stats.csv")
    results["history_quadrant_stats.csv"] = len(quadrant)

    # 4. 极端背离 + 事件研究
    divergences = find_extreme_divergences(rows, divergence_threshold)
    write_divergence_csv(divergences, output_root / "history_extreme_divergences.csv")
    results["history_extreme_divergences.csv"] = len(divergences)

    event_dates = [d.date for d in divergences]
    event_paths = build_event_paths(event_dates, rows)
    write_event_study_csv(event_paths, output_root / "history_event_study.csv")
    results["history_event_study.csv"] = len(event_paths)

    # 5. 信号 lift
    lifts = build_signal_lifts(rows, signal_min_count)
    write_signal_lift_csv(lifts, output_root / "history_signal_lift.csv")
    results["history_signal_lift.csv"] = len(lifts)

    # 6. 状态转移
    transitions = build_state_transitions(rows)
    write_transition_csv(transitions, output_root / "history_state_transitions.csv")
    results["history_state_transitions.csv"] = len(transitions)

    # 7. 反直觉信号
    counter_intuitive = identify_counter_intuitive_signals(lifts, signal_min_count)
    write_counter_intuitive_csv(counter_intuitive, output_root / "history_counter_intuitive_signals.csv")
    results["history_counter_intuitive_signals.csv"] = len(counter_intuitive)

    # 8. 象限条件信号效果
    conditional_effects = build_conditional_signal_effects(rows, lifts)
    write_conditional_signal_csv(conditional_effects, output_root / "history_conditional_signal_effects.csv")
    results["history_conditional_signal_effects.csv"] = len(conditional_effects)

    # 9. 操盘工作台视图
    operator_view = build_operator_playbook(
        rows=rows,
        rolling=rolling,
        signal_lifts=lifts,
        counter_intuitive=counter_intuitive,
        conditional_effects=conditional_effects,
        min_signal_count=signal_min_count,
        min_combo_count=8,
    )
    write_operator_playbook_json(operator_view, output_root / "history_operator_playbook.json")
    results["history_operator_playbook.json"] = 1

    return results
