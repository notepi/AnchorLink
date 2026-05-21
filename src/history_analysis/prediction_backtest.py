"""
历史相似性预测回测验证模块

核心逻辑：
1. 对历史每一天，模拟"当日预测"场景
2. 用当日之前的数据找相似案例，计算预测值
3. 对比预测值与实际值，统计准确度指标
4. 分时段（30/60/90天）统计指标
"""

from dataclasses import dataclass
from typing import Optional
import json

from src.history_analysis.models import (
    HistoryRow,
    PredictionAccuracy,
    BacktestMetrics,
    BacktestMetricsWindow,
    BacktestMetricsByPeriod,
    StabilityMetrics,
    ConfidenceInterval,
    PredictionBacktestResult,
)


# 相似度计算参数（与前端 today-history-mapping.ts 保持一致）
STATE_WEIGHTS = {
    "industry_beta": 0.25,
    "anchor_alpha": 0.25,
    "risk_level": 0.20,
    "strongest_group": 0.15,
    "weakest_group": 0.15,
}
BETA_ORDER = ["positive", "neutral", "negative"]
RISK_ORDER = ["low", "medium", "high"]
MIN_EFFECTIVE_SAMPLES = 5
MAX_TOP_N = 12
TOP_N_RATIO = 0.15


def _ordinal_score(a: str | None, b: str | None, order: list[str]) -> float:
    """计算序数相似度"""
    if not a or not b:
        return 0.0
    aa = a.strip().lower()
    bb = b.strip().lower()
    if aa not in order or bb not in order:
        return 1.0 if aa == bb else 0.0
    distance = abs(order.index(aa) - order.index(bb))
    return 1.0 if distance == 0 else 0.5 if distance == 1 else 0.0


def _exact_score(a: str | None, b: str | None) -> float:
    """计算精确匹配相似度"""
    if not a or not b:
        return 0.0
    return 1.0 if a.strip().lower() == b.strip().lower() else 0.0


def _parse_signals(row: HistoryRow) -> set[str]:
    """解析信号集合"""
    if row.signal_pairs:
        try:
            pairs = json.loads(row.signal_pairs)
            return {f"{p.get('category', '')}::{p.get('label', '')}" for p in pairs if p.get('label')}
        except (json.JSONDecodeError, TypeError):
            pass
    if row.signal_labels:
        return {f"::{s.strip()}" for s in row.signal_labels.split(',') if s.strip()}
    return set()


def compute_state_score(target: HistoryRow, candidate: HistoryRow) -> float:
    """计算状态相似度（与前端逻辑一致）"""
    scores = {
        "industry_beta": _ordinal_score(target.industry_beta, candidate.industry_beta, BETA_ORDER),
        "anchor_alpha": _ordinal_score(target.anchor_alpha, candidate.anchor_alpha, BETA_ORDER),
        "risk_level": _ordinal_score(target.risk_level, candidate.risk_level, RISK_ORDER),
        "strongest_group": _exact_score(target.strongest_group, candidate.strongest_group),
        "weakest_group": _exact_score(target.weakest_group, candidate.weakest_group),
    }
    total_weight = sum(STATE_WEIGHTS.values())
    weighted_sum = sum(scores[k] * STATE_WEIGHTS[k] for k in scores)
    return weighted_sum / total_weight


def compute_signal_jaccard(target: HistoryRow, candidate: HistoryRow) -> float:
    """计算信号 Jaccard 相似度"""
    target_signals = _parse_signals(target)
    candidate_signals = _parse_signals(candidate)
    if not target_signals and not candidate_signals:
        return 0.0
    intersection = len(target_signals & candidate_signals)
    union = len(target_signals | candidate_signals)
    return intersection / union if union > 0 else 0.0


def compute_similarity(target: HistoryRow, candidate: HistoryRow) -> float:
    """计算综合相似度（与前端逻辑一致）"""
    state_score = compute_state_score(target, candidate)
    signal_jaccard = compute_signal_jaccard(target, candidate)
    return state_score * 0.6 + signal_jaccard * 0.4


def find_similar_cases(
    target: HistoryRow,
    candidates: list[HistoryRow],
) -> list[tuple[HistoryRow, float]]:
    """
    找出相似案例

    Returns:
        [(row, similarity), ...] 按相似度降序排列
    """
    scored = []
    for candidate in candidates:
        sim = compute_similarity(target, candidate)
        scored.append((candidate, sim))

    scored.sort(key=lambda x: x[1], reverse=True)

    # 自适应 Top N
    top_n = min(MAX_TOP_N, max(MIN_EFFECTIVE_SAMPLES, round(len(scored) * TOP_N_RATIO)))
    return scored[:top_n]


def _weighted_avg(cases: list[tuple[HistoryRow, float]], field: str) -> float | None:
    """加权平均，权重=相似度"""
    values = [(getattr(r, field), s) for r, s in cases if getattr(r, field) is not None]
    if not values:
        return None
    total_weight = sum(s for _, s in values)
    return sum(v * s for v, s in values) / total_weight if total_weight > 0 else None


def _calc_error(pred: float | None, actual: float | None) -> float | None:
    """计算预测误差"""
    if pred is None or actual is None:
        return None
    return pred - actual


def _direction_correct(pred: float | None, actual: float | None) -> bool | None:
    """判断方向是否正确"""
    if pred is None or actual is None:
        return None
    if pred > 0 and actual > 0:
        return True
    if pred < 0 and actual < 0:
        return True
    if abs(pred) < 0.1 and abs(actual) < 0.1:
        return True
    return False


def _run_single_backtest(
    rows: list[HistoryRow],
    start_idx: int,
    end_idx: int,
) -> list[PredictionAccuracy]:
    """对指定范围运行回测"""
    predictions = []

    for i in range(start_idx, end_idx):
        target = rows[i]

        # 确保有前瞻收益
        if target.next_1d_return is None:
            continue

        # 候选样本：目标日期之前的数据
        candidates = [
            r for r in rows[:i]
            if r.next_1d_return is not None or r.next_3d_return is not None or r.next_5d_return is not None
        ]

        if len(candidates) < MIN_EFFECTIVE_SAMPLES:
            continue

        # 找相似案例
        similar_cases = find_similar_cases(target, candidates)

        if not similar_cases:
            continue

        # 计算预测值
        pred_1d = _weighted_avg(similar_cases, 'next_1d_return')
        pred_3d = _weighted_avg(similar_cases, 'next_3d_return')
        pred_5d = _weighted_avg(similar_cases, 'next_5d_return')

        # 实际值
        actual_1d = target.next_1d_return
        actual_3d = target.next_3d_return
        actual_5d = target.next_5d_return

        # 相似度统计
        similarities = [s for _, s in similar_cases]
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
        confidence_score = avg_similarity * min(len(similar_cases) / 10, 1.0)

        predictions.append(PredictionAccuracy(
            target_date=target.date,
            predicted_return_1d=pred_1d,
            predicted_return_3d=pred_3d,
            predicted_return_5d=pred_5d,
            actual_return_1d=actual_1d,
            actual_return_3d=actual_3d,
            actual_return_5d=actual_5d,
            prediction_error_1d=_calc_error(pred_1d, actual_1d),
            prediction_error_3d=_calc_error(pred_3d, actual_3d),
            prediction_error_5d=_calc_error(pred_5d, actual_5d),
            direction_correct_1d=_direction_correct(pred_1d, actual_1d),
            direction_correct_3d=_direction_correct(pred_3d, actual_3d),
            direction_correct_5d=_direction_correct(pred_5d, actual_5d),
            sample_count=len(similar_cases),
            avg_similarity=round(avg_similarity, 4),
            confidence_score=round(confidence_score, 4),
        ))

    return predictions


def _compute_window_metrics(predictions: list[PredictionAccuracy], window: str) -> BacktestMetricsWindow:
    """计算单窗口的回测指标"""
    pred_key = f'predicted_return_{window}'
    actual_key = f'actual_return_{window}'
    error_key = f'prediction_error_{window}'
    correct_key = f'direction_correct_{window}'

    preds = []
    actuals = []
    errors = []
    corrects = []

    for p in predictions:
        pred = getattr(p, pred_key)
        actual = getattr(p, actual_key)
        error = getattr(p, error_key)
        correct = getattr(p, correct_key)

        if pred is not None and actual is not None:
            preds.append(pred)
            actuals.append(actual)
        if error is not None:
            errors.append(error)
        if correct is not None:
            corrects.append(correct)

    # IC (Spearman 相关系数)
    ic = None
    if len(preds) >= 10:
        try:
            from scipy import stats
            corr, _ = stats.spearmanr(preds, actuals)
            ic = round(corr, 4) if corr == corr else None  # NaN check
        except Exception:
            pass

    # 方向准确率
    direction_accuracy = round(sum(corrects) / len(corrects), 4) if corrects else None

    # RMSE
    rmse = None
    if errors:
        import math
        rmse = round(math.sqrt(sum(e**2 for e in errors) / len(errors)), 4)

    # MAE
    mae = round(sum(abs(e) for e in errors) / len(errors), 4) if errors else None

    # 平均误差
    mean_error = round(sum(errors) / len(errors), 4) if errors else None

    return BacktestMetricsWindow(
        ic=ic,
        direction_accuracy=direction_accuracy,
        rmse=rmse,
        mae=mae,
        mean_error=mean_error,
    )


def _compute_quintile_returns(predictions: list[PredictionAccuracy]) -> tuple[dict, ...] | None:
    """按预测值分 5 组，统计各组实际收益"""
    if len(predictions) < 20:
        return None

    # 提取 T+1 预测和实际值
    paired = [(p.predicted_return_1d, p.actual_return_1d) for p in predictions
              if p.predicted_return_1d is not None and p.actual_return_1d is not None]

    if len(paired) < 20:
        return None

    # 按预测值排序
    paired.sort(key=lambda x: x[0])
    n = len(paired)
    quintile_size = n // 5

    results = []
    for q in range(5):
        start = q * quintile_size
        end = (q + 1) * quintile_size if q < 4 else n
        group = paired[start:end]

        group_preds = [p for p, _ in group]
        group_actuals = [a for _, a in group]

        # 方向准确率
        correct = sum(1 for p, a in group if (p > 0 and a > 0) or (p < 0 and a < 0))

        results.append({
            'quintile': q + 1,
            'count': len(group),
            'avg_predicted': round(sum(group_preds) / len(group_preds), 4),
            'avg_actual': round(sum(group_actuals) / len(group_actuals), 4),
            'direction_accuracy': round(correct / len(group), 4),
        })

    return tuple(results)


def _compute_stability_metrics(predictions: list[PredictionAccuracy]) -> StabilityMetrics:
    """计算稳定性指标"""
    # 预测波动
    pred_values_1d = [p.predicted_return_1d for p in predictions if p.predicted_return_1d is not None]
    prediction_volatility_1d = None
    if len(pred_values_1d) >= 2:
        import math
        mean_val = sum(pred_values_1d) / len(pred_values_1d)
        variance = sum((v - mean_val) ** 2 for v in pred_values_1d) / len(pred_values_1d)
        prediction_volatility_1d = round(math.sqrt(variance), 4)

    # 相似度分布
    sim_dist = {'0.8-1.0': 0, '0.6-0.8': 0, '0.4-0.6': 0, '0.0-0.4': 0}
    for p in predictions:
        score = p.avg_similarity
        if score >= 0.8:
            sim_dist['0.8-1.0'] += 1
        elif score >= 0.6:
            sim_dist['0.6-0.8'] += 1
        elif score >= 0.4:
            sim_dist['0.4-0.6'] += 1
        else:
            sim_dist['0.0-0.4'] += 1

    # 稳定性分数
    stability_score = None
    if prediction_volatility_1d is not None:
        vol_score = max(0, 1 - prediction_volatility_1d / 2)
        stability_score = round(vol_score * 100, 1)

    return StabilityMetrics(
        prediction_volatility_1d=prediction_volatility_1d,
        stability_score=stability_score,
        similarity_distribution=tuple(sim_dist.items()),
    )


def _compute_confidence_intervals(
    predictions: list[PredictionAccuracy],
    n_bootstrap: int = 1000,
) -> tuple[ConfidenceInterval, ...]:
    """Bootstrap 计算置信区间"""
    import random

    results = []

    for window in ['1d', '3d', '5d']:
        actual_key = f'actual_return_{window}'
        values = [getattr(p, actual_key) for p in predictions if getattr(p, actual_key) is not None]

        if not values:
            continue

        # Bootstrap 采样
        random.seed(42)
        bootstrap_means = []
        for _ in range(n_bootstrap):
            sample = random.choices(values, k=len(values))
            bootstrap_means.append(sum(sample) / len(sample))

        bootstrap_means.sort()
        lower_idx = int(n_bootstrap * 0.025)
        upper_idx = int(n_bootstrap * 0.975)

        results.append(ConfidenceInterval(
            window=window,
            point_estimate=round(sum(values) / len(values), 4),
            lower_bound=round(bootstrap_means[lower_idx], 4),
            upper_bound=round(bootstrap_means[upper_idx], 4),
            sample_size=len(values),
        ))

    return tuple(results)


def run_prediction_backtest(
    rows: list[HistoryRow],
    periods: tuple[int, ...] = (30, 60, 90),
) -> PredictionBacktestResult:
    """
    运行预测回测验证

    Args:
        rows: 历史数据（按日期排序）
        periods: 分时段统计的天数列表

    Returns:
        PredictionBacktestResult 包含所有评估结果
    """
    # 按日期排序
    sorted_rows = sorted(rows, key=lambda r: r.date)
    n = len(sorted_rows)

    if n < MIN_EFFECTIVE_SAMPLES + 5:  # 至少需要足够样本 + T+5 窗口
        return PredictionBacktestResult(
            metrics_by_period=(),
            stability_metrics=StabilityMetrics(
                prediction_volatility_1d=None,
                stability_score=None,
                similarity_distribution=(),
            ),
            recent_predictions=(),
            confidence_intervals=None,
        )

    # 排除最近 5 天（T+5 还没发生）
    end_idx = n - 5

    # 运行全量回测
    all_predictions = _run_single_backtest(sorted_rows, MIN_EFFECTIVE_SAMPLES + 5, end_idx)

    # 分时段统计
    metrics_by_period = []
    for period_days in periods:
        # 取最近 period_days 的预测
        period_predictions = all_predictions[-period_days:] if len(all_predictions) >= period_days else all_predictions

        if not period_predictions:
            continue

        metrics = BacktestMetrics(
            window_1d=_compute_window_metrics(period_predictions, '1d'),
            window_3d=_compute_window_metrics(period_predictions, '3d'),
            window_5d=_compute_window_metrics(period_predictions, '5d'),
            total_predictions=len(period_predictions),
            valid_predictions_1d=sum(1 for p in period_predictions if p.predicted_return_1d is not None),
            valid_predictions_3d=sum(1 for p in period_predictions if p.predicted_return_3d is not None),
            valid_predictions_5d=sum(1 for p in period_predictions if p.predicted_return_5d is not None),
            quintile_returns=_compute_quintile_returns(period_predictions),
        )
        metrics_by_period.append(BacktestMetricsByPeriod(
            period_days=period_days,
            metrics=metrics,
        ))

    # 稳定性指标
    stability_metrics = _compute_stability_metrics(all_predictions)

    # 最近 30 天预测（用于前端展示）
    recent_predictions = tuple(all_predictions[-30:]) if len(all_predictions) >= 30 else tuple(all_predictions)

    # 置信区间
    confidence_intervals = _compute_confidence_intervals(all_predictions)

    return PredictionBacktestResult(
        metrics_by_period=tuple(metrics_by_period),
        stability_metrics=stability_metrics,
        recent_predictions=recent_predictions,
        confidence_intervals=confidence_intervals if confidence_intervals else None,
    )
