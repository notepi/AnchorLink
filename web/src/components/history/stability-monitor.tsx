'use client';

import { useState } from 'react';
import type { RollingMetricRow, HistorySummaryRow } from '@/types';
import { cn } from '@/lib/utils';
import { RollingMetricsChart } from './rolling-metrics-chart';
import { HistoryTrendChart } from './history-trend-chart';

interface StabilityMonitorProps {
  rollingMetrics: RollingMetricRow[];
  trendData: HistorySummaryRow[];
  sampleDays: number;
}

type StabilityStatus = 'stable' | 'deteriorating' | 'concerning' | 'insufficient';

interface StabilityAssessment {
  status: StabilityStatus;
  message: string;
  details: string[];
}

// 稳定性状态判定
function assessStability(metrics: RollingMetricRow[]): StabilityAssessment {
  if (metrics.length < 5) {
    return {
      status: 'insufficient',
      message: '近期样本不足，无法判断稳定性',
      details: ['滚动指标需要至少5个数据点'],
    };
  }

  const latest = metrics[metrics.length - 1];
  const prev = metrics[metrics.length - 2];
  const recent5 = metrics.slice(-5);

  // 恶化信号检查
  const deterioratingSignals: string[] = [];

  if (
    latest.excess_5d !== null &&
    latest.excess_5d < 0 &&
    latest.excess_10d !== null &&
    latest.excess_10d < 0
  ) {
    deterioratingSignals.push('5日和10日超额收益均为负');
  }

  if (
    prev.excess_10d !== null &&
    prev.excess_10d >= 0 &&
    latest.excess_10d !== null &&
    latest.excess_10d < 0
  ) {
    deterioratingSignals.push('10日超额收益由正转负');
  }

  if (latest.risk_high_streak !== null && latest.risk_high_streak >= 3) {
    deterioratingSignals.push(`高风险连胜${latest.risk_high_streak}天`);
  }

  if (
    latest.outperform_streak !== null &&
    latest.outperform_streak <= -3
  ) {
    deterioratingSignals.push(
      `跑输连胜${Math.abs(latest.outperform_streak)}天`
    );
  }

  // 稳定信号检查
  const negative10dCount = recent5.filter(
    (m) => m.excess_10d !== null && m.excess_10d < 0
  ).length;

  if (deterioratingSignals.length >= 2) {
    return {
      status: 'concerning',
      message: '近期历史规律出现明显失效信号',
      details: deterioratingSignals,
    };
  }

  if (deterioratingSignals.length === 1 || negative10dCount >= 2) {
    return {
      status: 'deteriorating',
      message: '近期历史规律稳定性下降',
      details:
        deterioratingSignals.length > 0
          ? deterioratingSignals
          : ['近5日中10日超额为负的天数较多'],
    };
  }

  return {
    status: 'stable',
    message: '近期历史规律表现稳定',
    details: ['滚动指标未出现明显恶化信号'],
  };
}

// 状态视觉映射
const statusVisual = {
  stable: {
    color: 'text-anchor-positive',
    bg: 'bg-anchor-positive/10',
    border: 'border-l-2 border-l-anchor-positive',
    icon: '✓',
  },
  deteriorating: {
    color: 'text-anchor-accent',
    bg: 'bg-anchor-accent/10',
    border: 'border-l-2 border-l-anchor-accent',
    icon: '◆',
  },
  concerning: {
    color: 'text-anchor-negative',
    bg: 'bg-anchor-negative/10',
    border: 'border-l-2 border-l-anchor-negative',
    icon: '⚠',
  },
  insufficient: {
    color: 'text-anchor-textMuted',
    bg: 'bg-anchor-bgTertiary',
    border: 'border-l-2 border-l-anchor-border',
    icon: '○',
  },
};

export function StabilityMonitor({
  rollingMetrics,
  trendData,
  sampleDays,
}: StabilityMonitorProps) {
  const [showDetails, setShowDetails] = useState(false);

  const stability = assessStability(rollingMetrics);
  const visual = statusVisual[stability.status];

  return (
    <div
      className={cn(
        'bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border',
        visual.border
      )}
    >
      {/* 头部：稳定性状态 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className={cn('text-lg', visual.color)}>{visual.icon}</span>
          <div>
            <h2 className="text-xs font-medium text-anchor-textSecondary uppercase">
              历史规律稳定性
            </h2>
            <span className={cn('text-sm font-medium', visual.color)}>
              {stability.message}
            </span>
          </div>
        </div>
        <span className="text-xs text-anchor-textMuted">样本 {sampleDays} 天</span>
      </div>

      {/* 状态说明 */}
      <p
        className={cn(
          'text-sm mb-3',
          stability.status === 'stable' && 'text-anchor-positive',
          stability.status === 'deteriorating' && 'text-anchor-accent',
          (stability.status === 'concerning' ||
            stability.status === 'insufficient') &&
            'text-anchor-negative'
        )}
      >
        {stability.message}
      </p>

      {/* 详细指标（可展开） */}
      {stability.details.length > 0 && (
        <div className="mb-4">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="text-xs text-anchor-textMuted hover:text-anchor-text flex items-center gap-1 mb-2"
          >
            {showDetails ? '▲' : '▼'} 详细指标
          </button>

          {showDetails && (
            <ul className="space-y-1">
              {stability.details.map((d, i) => (
                <li
                  key={i}
                  className="text-xs text-anchor-textSecondary flex items-start gap-2"
                >
                  <span
                    className={cn(
                      stability.status === 'stable'
                        ? 'text-anchor-positive'
                        : stability.status === 'deteriorating'
                          ? 'text-anchor-accent'
                          : 'text-anchor-negative'
                    )}
                  >
                    •
                  </span>
                  {d}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* 双图表布局 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-anchor-textMuted mb-2">滚动指标</div>
          <RollingMetricsChart data={rollingMetrics} />
        </div>
        <div>
          <div className="text-xs text-anchor-textMuted mb-2">收益趋势</div>
          <HistoryTrendChart data={trendData} />
        </div>
      </div>
    </div>
  );
}