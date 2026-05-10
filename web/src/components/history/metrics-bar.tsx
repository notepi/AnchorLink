'use client';

import { PersonalitySummaryMetrics } from '@/types';

interface MetricsBarProps {
  metrics: PersonalitySummaryMetrics;
  sampleDays: number;
}

export function MetricsBar({ metrics, sampleDays }: MetricsBarProps) {
  const items = [
    {
      label: '胜率',
      value: metrics.baseline_win_rate_1d !== null ? (metrics.baseline_win_rate_1d * 100).toFixed(1) + '%' : '-',
      unit: '',
      isPositive: metrics.baseline_win_rate_1d !== null ? metrics.baseline_win_rate_1d >= 0.5 : false,
    },
    {
      label: 'T+3 超额',
      value: metrics.median_excess_3d !== null ? `${metrics.median_excess_3d >= 0 ? '+' : ''}${metrics.median_excess_3d.toFixed(2)}` : '-',
      unit: 'pp',
      isPositive: metrics.median_excess_3d !== null ? metrics.median_excess_3d >= 0 : false,
    },
    {
      label: 'T+3 不利',
      value: metrics.median_adverse_3d_proxy !== null ? `${metrics.median_adverse_3d_proxy.toFixed(2)}` : '-',
      unit: 'pp',
      isPositive: false,
    },
    {
      label: '盈亏比',
      value: metrics.payoff_ratio !== null ? metrics.payoff_ratio.toFixed(2) : '-',
      unit: 'x',
      isPositive: metrics.payoff_ratio !== null ? metrics.payoff_ratio >= 1 : false,
    },
    {
      label: '夏普',
      value: metrics.sharpe_like_ratio !== null ? metrics.sharpe_like_ratio.toFixed(2) : '-',
      unit: '',
      isPositive: metrics.sharpe_like_ratio !== null ? metrics.sharpe_like_ratio >= 0 : false,
    },
    {
      label: '信号覆盖',
      value: metrics.signal_coverage_ratio !== null ? (metrics.signal_coverage_ratio * 100).toFixed(0) + '%' : '-',
      unit: '',
      isPositive: metrics.signal_coverage_ratio !== null ? metrics.signal_coverage_ratio >= 0.3 : false,
    },
  ];

  return (
    <section className="border border-anchor-border bg-anchor-bgSecondary"
    >
      <div className="flex divide-x divide-anchor-border"
      >
        {items.map((item, idx) => (
          <div
            key={idx}
            className="flex-1 px-3 py-3 text-center"
          >
            <div className="text-[10px] text-anchor-textMuted uppercase tracking-wide mb-1"
            >
              {item.label}
            </div>
            <div className={`text-lg font-semibold ${item.isPositive ? 'text-red-400' : 'text-green-400'}`}
            >
              {item.value}
              {item.unit && (
                <span className="text-xs font-normal text-anchor-textMuted ml-0.5"
                >{item.unit}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
