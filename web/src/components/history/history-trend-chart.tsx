'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import type { HistorySummaryRow } from '@/types';

interface HistoryTrendChartProps {
  data: HistorySummaryRow[];
}

function formatTick(date: string): string {
  if (!date || date.length !== 8) return date;
  return `${date.slice(4, 6)}/${date.slice(6, 8)}`;
}

export function HistoryTrendChart({ data }: HistoryTrendChartProps) {
  const chartData = data.map((row) => ({
    date: row.date,
    anchor: row.anchor_return,
    chain: row.industry_chain_median,
    excess: row.relative_strength_vs_industry_chain,
  }));

  return (
    <div>
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
          当日收益与超额
        </h2>
        <span className="text-xs text-anchor-textMuted">
          {data.length} 个交易日
        </span>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f1f1f" />
            <XAxis
              dataKey="date"
              tickFormatter={formatTick}
              tick={{ fontSize: 10, fill: '#525252' }}
              axisLine={{ stroke: '#262626' }}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#525252' }}
              axisLine={{ stroke: '#262626' }}
              tickLine={false}
              tickFormatter={(v: number) => `${v.toFixed(0)}%`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#111111',
                border: '1px solid #262626',
                borderRadius: '4px',
                fontSize: '11px',
                color: '#e5e5e5',
              }}
              labelFormatter={(label: string) => {
                if (label.length === 8) {
                  return `${label.slice(0, 4)}-${label.slice(4, 6)}-${label.slice(6, 8)}`;
                }
                return label;
              }}
              formatter={(value: number | string, name: string) => {
                const v = typeof value === 'number' ? value : null;
                if (v === null) return ['--', name];
                const labels: Record<string, string> = {
                  anchor: '锚定收益',
                  chain: '产业链中位数',
                  excess: '当日超额',
                };
                const sign = v >= 0 ? '+' : '';
                return [`${sign}${v.toFixed(2)}%`, labels[name] || name];
              }}
            />
            <ReferenceLine y={0} stroke="#262626" />
            <Line
              type="monotone"
              dataKey="anchor"
              stroke="#ef4444"
              strokeWidth={1.5}
              dot={false}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="chain"
              stroke="#3b82f6"
              strokeWidth={1}
              dot={false}
              connectNulls
              strokeDasharray="4 2"
            />
            <Line
              type="monotone"
              dataKey="excess"
              stroke="#8b5cf6"
              strokeWidth={1}
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="flex items-center gap-4 mt-2">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-anchor-positive" />
          <span className="text-xs text-anchor-textMuted">锚定收益</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-anchor-accent border-dashed" style={{ borderTop: '1px dashed #3b82f6' }} />
          <span className="text-xs text-anchor-textMuted">产业链中位数</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-signal-alpha" />
          <span className="text-xs text-anchor-textMuted">当日超额</span>
        </div>
      </div>
    </div>
  );
}
