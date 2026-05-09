import type { TrendStatus, SignalTrend } from '@/types';

interface SignalTrendIndicatorProps {
  trend: SignalTrend;
  compact?: boolean;
}

const TREND_CONFIG: Record<TrendStatus, { icon: string; color: string; text: string }> = {
  trend_improving: { icon: '↗', color: 'text-anchor-positive', text: '趋势改善' },
  trend_deteriorating: { icon: '↘', color: 'text-anchor-negative', text: '趋势恶化' },
  trend_stable: { icon: '→', color: 'text-anchor-textMuted', text: '趋势稳定' },
  trend_insufficient: { icon: '·', color: 'text-anchor-textMuted', text: '样本不足' },
};

function formatDelta(value: number | null): string {
  if (value === null) return '--';
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}pp`;
}

export function SignalTrendIndicator({ trend }: SignalTrendIndicatorProps) {
  const config = TREND_CONFIG[trend.trend];

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className={`${config.color} font-medium`}>{config.icon} {config.text}</span>
      {trend.trend !== 'trend_insufficient' && trend.recentDelta !== null && trend.historicalDelta !== null && (
        <span className="text-anchor-textMuted">
          {formatDelta(trend.historicalDelta)} → {formatDelta(trend.recentDelta)}
        </span>
      )}
    </div>
  );
}
