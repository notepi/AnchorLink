"""
历史分析 CSV 输出模块

职责：将历史分析结果写入 CSV 文件到 data/output/ 根目录。
归 Output 层管辖（只做格式化写入，不做业务判断）。
"""

import csv
import json
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path

from src.history_analysis.models import (
    ConditionalSignalEffect,
    CounterIntuitiveSignal,
    HistoryRow,
    RollingMetrics,
    QuadrantStats,
    ExtremeDivergence,
    EventPath,
    OperatorHistoryView,
    SignalLift,
    StateTransition,
)


def _dataclass_to_dict(obj: object) -> dict:
    """Frozen dataclass → dict，用于 csv.DictWriter"""
    return {f.name: getattr(obj, f.name) for f in fields(obj)}


def write_history_csv(rows: list[HistoryRow], path: Path) -> None:
    """写入 history_summary.csv"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        return

    fieldnames = [f.name for f in fields(HistoryRow)]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_dataclass_to_dict(row) for row in rows)


def write_rolling_csv(metrics: list[RollingMetrics], path: Path) -> None:
    """写入 history_rolling_metrics.csv"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not metrics:
        return

    fieldnames = [f.name for f in fields(RollingMetrics)]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_dataclass_to_dict(m) for m in metrics)


def write_quadrant_csv(stats: list[QuadrantStats], path: Path) -> None:
    """写入 history_quadrant_stats.csv"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not stats:
        return

    fieldnames = [f.name for f in fields(QuadrantStats)]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_dataclass_to_dict(s) for s in stats)


def write_divergence_csv(divergences: list[ExtremeDivergence], path: Path) -> None:
    """写入 history_extreme_divergences.csv"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not divergences:
        return

    fieldnames = [f.name for f in fields(ExtremeDivergence)]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_dataclass_to_dict(d) for d in divergences)


def write_event_study_csv(paths: list[EventPath], path: Path) -> None:
    """写入 history_event_study.csv"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not paths:
        return

    fieldnames = [f.name for f in fields(EventPath)]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_dataclass_to_dict(p) for p in paths)


def write_signal_lift_csv(lifts: list[SignalLift], path: Path) -> None:
    """写入 history_signal_lift.csv"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not lifts:
        return

    fieldnames = [f.name for f in fields(SignalLift)]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_dataclass_to_dict(l) for l in lifts)


def write_transition_csv(transitions: list[StateTransition], path: Path) -> None:
    """写入 history_state_transitions.csv"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not transitions:
        return

    fieldnames = [f.name for f in fields(StateTransition)]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_dataclass_to_dict(t) for t in transitions)


def write_counter_intuitive_csv(signals: list[CounterIntuitiveSignal], path: Path) -> None:
    """写入 history_counter_intuitive_signals.csv"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not signals:
        return

    fieldnames = [f.name for f in fields(CounterIntuitiveSignal)]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_dataclass_to_dict(s) for s in signals)


def write_conditional_signal_csv(effects: list[ConditionalSignalEffect], path: Path) -> None:
    """写入 history_conditional_signal_effects.csv"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not effects:
        return

    fieldnames = [f.name for f in fields(ConditionalSignalEffect)]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(_dataclass_to_dict(e) for e in effects)


def _json_default(obj: object) -> object:
    if is_dataclass(obj):
        return asdict(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def write_operator_playbook_json(view: OperatorHistoryView, path: Path) -> None:
    """写入 history_operator_playbook.json"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(view), f, ensure_ascii=False, indent=2, default=_json_default)
