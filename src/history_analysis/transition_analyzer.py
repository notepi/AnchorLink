"""
状态转移矩阵模块

计算 beta×alpha 象限之间的转移概率。
"""

from src.history_analysis.models import HistoryRow, StateTransition
from src.history_analysis.quadrant_analyzer import classify_quadrant


def build_state_transitions(rows: list[HistoryRow]) -> list[StateTransition]:
    """
    计算状态转移：今天 X 象限 → 明天 Y 象限 的次数和概率。

    只计算有 next_1d_return 的相邻日对。
    """
    # 统计转移次数
    transition_counts: dict[str, dict[str, int]] = {}
    from_counts: dict[str, int] = {}

    for i in range(len(rows) - 1):
        from_state = classify_quadrant(rows[i].industry_beta, rows[i].anchor_alpha)
        to_state = classify_quadrant(rows[i + 1].industry_beta, rows[i + 1].anchor_alpha)

        transition_counts.setdefault(from_state, {})
        transition_counts[from_state][to_state] = transition_counts[from_state].get(to_state, 0) + 1
        from_counts[from_state] = from_counts.get(from_state, 0) + 1

    # 转为概率
    transitions: list[StateTransition] = []
    for from_state, to_states in sorted(transition_counts.items()):
        total = from_counts[from_state]
        for to_state, count in sorted(to_states.items()):
            transitions.append(StateTransition(
                from_state=from_state,
                to_state=to_state,
                count=count,
                probability=round(count / total, 6),
            ))

    return transitions
