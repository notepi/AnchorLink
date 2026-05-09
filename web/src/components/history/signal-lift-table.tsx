import type { SignalLiftRow, SignalTrend } from '@/types';
import { SignalTrendIndicator } from './signal-trend-indicator';

interface SignalLiftTableProps {
  data: SignalLiftRow[];
  trendMap?: Map<string, SignalTrend>;
}

function deltaPpColor(value: number | null): string {
  if (value === null) return 'text-anchor-textMuted';
  if (value > 0) return 'text-anchor-positive';
  if (value < 0) return 'text-anchor-negative';
  return 'text-anchor-text';
}

function formatPct(value: number | null): string {
  if (value === null) return '--';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function rowBgClass(value: number | null, index: number, validCount: number): string {
  if (value === null) return '';
  if (index < 3 && value > 0) return 'bg-anchor-positive/10 hover:bg-anchor-positive/20';
  if (index >= validCount - 3 && value < 0) return 'bg-anchor-negative/10 hover:bg-anchor-negative/20';
  return 'hover:bg-anchor-bgTertiary/50';
}

export function SignalLiftTable({ data, trendMap }: SignalLiftTableProps) {
  // 只展示样本足够的信号，按 delta_pp 排序
  const validSignals = data
    .filter((s) => s.min_count_passed)
    .sort((a, b) => (b.avg_next_1d_delta_pp ?? 0) - (a.avg_next_1d_delta_pp ?? 0));

  return (
    <div>
      <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-3">
        信号表现排行
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-anchor-border">
              <th className="text-left py-1.5 pr-3 text-anchor-textMuted font-medium">信号</th>
              <th className="text-right py-1.5 px-2 text-anchor-textMuted font-medium">样本</th>
              <th className="text-right py-1.5 px-2 text-anchor-textMuted font-medium">次日均值</th>
              <th className="text-right py-1.5 px-2 text-anchor-textMuted font-medium">相对基线</th>
              <th className="text-right py-1.5 px-2 text-anchor-textMuted font-medium">胜率</th>
              <th className="text-left py-1.5 px-2 text-anchor-textMuted font-medium">趋势</th>
            </tr>
          </thead>
          <tbody>
            {validSignals.map((row, index) => {
              const trend = trendMap?.get(row.label);
              return (
                <tr
                  key={row.label}
                  className={`border-b border-anchor-borderSubtle ${rowBgClass(row.avg_next_1d_delta_pp, index, validSignals.length)}`}
                >
                  <td className="py-1.5 pr-3 text-anchor-text max-w-[200px] truncate" title={row.label}>
                    {row.label}
                  </td>
                  <td className="text-right py-1.5 px-2 font-mono text-anchor-textSecondary">
                    {row.appearance_count}
                  </td>
                  <td className={`text-right py-1.5 px-2 font-mono ${deltaPpColor(row.avg_next_1d)}`}>
                    {formatPct(row.avg_next_1d)}
                  </td>
                  <td className={`text-right py-1.5 px-2 font-mono font-medium ${deltaPpColor(row.avg_next_1d_delta_pp)}`}>
                    {row.avg_next_1d_delta_pp !== null
                      ? `${row.avg_next_1d_delta_pp >= 0 ? '+' : ''}${row.avg_next_1d_delta_pp.toFixed(2)}pp`
                      : '--'}
                  </td>
                  <td className={`text-right py-1.5 px-2 font-mono ${deltaPpColor(row.win_rate_1d !== null ? (row.win_rate_1d >= 0.5 ? 1 : -1) : null)}`}>
                    {row.win_rate_1d !== null ? `${(row.win_rate_1d * 100).toFixed(0)}%` : '--'}
                  </td>
                  <td className="py-1.5 px-2">
                    {trend ? <SignalTrendIndicator trend={trend} /> : null}
                  </td>
                </tr>
              );
            })}
            {validSignals.length === 0 && (
              <tr>
                <td colSpan={6} className="py-3 text-center text-anchor-textMuted text-sm">
                  暂无满足条件的信号
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-2 text-xs text-anchor-textMuted">
        * 样本不足 5 次的信号不展示 · 相对基线 = 信号次日均值 - 所有交易日次日均值
      </div>
    </div>
  );
}
