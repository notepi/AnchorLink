"use client";

import { useMemo } from 'react';
import type { DashboardView } from '@/types/dashboard-view';

interface PredictionEvaluationPanelProps {
  predictionEvaluation: DashboardView['predictionEvaluation'];
}

function formatPct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function formatNumber(value: number | null | undefined, decimals: number = 2): string {
  if (value == null || Number.isNaN(value)) return '--';
  return value.toFixed(decimals);
}

function getIcColor(ic: number | null): string {
  if (ic == null) return 'var(--muted)';
  if (ic > 0.05) return 'var(--green)';
  if (ic < -0.05) return 'var(--red)';
  return 'var(--text-secondary)';
}

function getAccuracyColor(acc: number | null): string {
  if (acc == null) return 'var(--muted)';
  if (acc > 0.55) return 'var(--green)';
  if (acc < 0.45) return 'var(--red)';
  return 'var(--text-secondary)';
}

export default function PredictionEvaluationPanel({ predictionEvaluation }: PredictionEvaluationPanelProps) {
  const metricsByPeriod = predictionEvaluation?.metricsByPeriod ?? [];
  const stabilityMetrics = predictionEvaluation?.stabilityMetrics;
  const confidenceIntervals = predictionEvaluation?.confidenceIntervals ?? [];

  // 按 T+1 指标汇总
  const summaryByPeriod = useMemo(() => {
    return metricsByPeriod.map(period => ({
      periodDays: period.periodDays,
      ic1d: period.metrics.window1d.ic,
      directionAccuracy1d: period.metrics.window1d.directionAccuracy,
      rmse1d: period.metrics.window1d.rmse,
      totalPredictions: period.metrics.totalPredictions,
    }));
  }, [metricsByPeriod]);

  if (metricsByPeriod.length === 0) {
    return (
      <details className="collapsible-section">
        <summary>
          <div className="section-title-wrap">
            <h2 className="section-title">预测准确度评估</h2>
            <p className="section-note">验证历史相似案例预测的实际效果。</p>
          </div>
        </summary>
        <div style={{ padding: '20px', color: 'var(--muted)', textAlign: 'center' }}>
          暂无回测数据，请先运行数据管道
        </div>
      </details>
    );
  }

  return (
    <details className="collapsible-section" open>
      <summary>
        <div className="section-title-wrap">
          <h2 className="section-title">预测准确度评估</h2>
          <p className="section-note">验证历史相似案例预测的实际效果，评估预测可靠性。</p>
        </div>
        <span className="section-meta">
          IC(T+1): {formatNumber(summaryByPeriod[0]?.ic1d, 3) ?? '--'}
        </span>
      </summary>

      {/* 分时段指标表格 */}
      <div className="period-metrics-table">
        <table className="mini-table">
          <thead>
            <tr>
              <th>时段</th>
              <th>IC (T+1)</th>
              <th>方向准确率</th>
              <th>RMSE</th>
              <th>样本数</th>
            </tr>
          </thead>
          <tbody>
            {summaryByPeriod.map(row => (
              <tr key={row.periodDays}>
                <td>最近 {row.periodDays} 天</td>
                <td className={getIcColor(row.ic1d)}>
                  {formatNumber(row.ic1d, 3)}
                </td>
                <td className={getAccuracyColor(row.directionAccuracy1d)}>
                  {row.directionAccuracy1d != null ? `${(row.directionAccuracy1d * 100).toFixed(1)}%` : '--'}
                </td>
                <td>{formatNumber(row.rmse1d)}</td>
                <td>{row.totalPredictions}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 稳定性指标 */}
      {stabilityMetrics && (
        <div className="stability-section" style={{ marginTop: '16px' }}>
          <h3 style={{ fontSize: '14px', marginBottom: '8px', color: 'var(--text-secondary)' }}>稳定性分析</h3>
          <div className="stability-metrics" style={{ display: 'flex', gap: '20px' }}>
            <div className="metric-item">
              <span className="metric-label" style={{ color: 'var(--muted)', fontSize: '12px' }}>预测波动率</span>
              <span className="metric-value" style={{ marginLeft: '8px' }}>
                {formatNumber(stabilityMetrics.predictionVolatility1d)}
              </span>
            </div>
            <div className="metric-item">
              <span className="metric-label" style={{ color: 'var(--muted)', fontSize: '12px' }}>稳定性分数</span>
              <span className="metric-value" style={{ marginLeft: '8px' }}>
                {formatNumber(stabilityMetrics.stabilityScore)}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* 置信区间 */}
      {confidenceIntervals.length > 0 && (
        <div className="confidence-intervals" style={{ marginTop: '16px' }}>
          <h3 style={{ fontSize: '14px', marginBottom: '8px', color: 'var(--text-secondary)' }}>置信区间 (95%)</h3>
          <div style={{ display: 'flex', gap: '20px' }}>
            {confidenceIntervals.map(ci => (
              <div key={ci.window} className="ci-item" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '12px', color: 'var(--muted)' }}>T+{ci.window === '1d' ? '1' : ci.window === '3d' ? '3' : '5'}</div>
                <div style={{ fontWeight: 'bold' }}>
                  {formatPct(ci.pointEstimate)}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  [{formatPct(ci.lowerBound)}, {formatPct(ci.upperBound)}]
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 指标解读 */}
      <div className="metrics-interpretation" style={{ marginTop: '16px', padding: '12px', background: 'var(--card-bg)', borderRadius: '6px' }}>
        <h4 style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px' }}>指标解读</h4>
        <ul style={{ fontSize: '12px', color: 'var(--muted)', paddingLeft: '16px', margin: 0 }}>
          <li><strong>IC</strong>：预测值与实际收益的相关系数，{'>'}0.05 表示有预测价值</li>
          <li><strong>方向准确率</strong>：预测涨跌方向正确的比例，{'>'}55% 优于随机</li>
          <li><strong>RMSE</strong>：预测误差的均方根，越小越好</li>
          <li><strong>置信区间</strong>：由 Bootstrap 方法计算，区间越窄预测越可靠</li>
        </ul>
      </div>

      {/* 分组评估 */}
      {metricsByPeriod[0]?.metrics?.quintileReturns && (
        <div className="quintile-section" style={{ marginTop: '16px' }}>
          <h3 style={{ fontSize: '14px', marginBottom: '8px', color: 'var(--text-secondary)' }}>分组预测效果 (最近 {metricsByPeriod[0].periodDays} 天)</h3>
          <table className="mini-table">
            <thead>
              <tr>
                <th>分组</th>
                <th>样本数</th>
                <th>预测均值</th>
                <th>实际均值</th>
                <th>方向准确率</th>
              </tr>
            </thead>
            <tbody>
              {metricsByPeriod[0].metrics.quintileReturns?.map(q => (
                <tr key={q.quintile}>
                  <td>Q{q.quintile}</td>
                  <td>{q.count}</td>
                  <td className={q.avgPredicted != null && q.avgPredicted > 0 ? 'green' : q.avgPredicted != null && q.avgPredicted < 0 ? 'red' : ''}>
                    {formatPct(q.avgPredicted)}
                  </td>
                  <td className={q.avgActual != null && q.avgActual > 0 ? 'green' : q.avgActual != null && q.avgActual < 0 ? 'red' : ''}>
                    {formatPct(q.avgActual)}
                  </td>
                  <td>{q.directionAccuracy != null ? `${(q.directionAccuracy * 100).toFixed(1)}%` : '--'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </details>
  );
}
