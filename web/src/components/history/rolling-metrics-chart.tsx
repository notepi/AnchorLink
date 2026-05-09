'use client';

import {
  LineChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import type { RollingMetricRow } from '@/types';

interface RollingMetricsChartProps {
  data: RollingMetricRow[];
}

function formatTick(date: string) {
  if (!date || date.length !== 8) return date;
  return `${date.slice(4, 6)}/${date.slice(6, 8)}`;
}

export function RollingMetricsChart({ data }: RollingMetricsChartProps) {
  const excessData = data.map((row) => ({
    date: row.date,
    excess_5d: row.excess_5d,
    excess_10d: row.excess_10d,
  }));

  const streakData = data.map((row) => ({
    date: row.date,
    outperform: row.outperform_streak,
    beta: row.beta_streak,
    risk: row.risk_high_streak,
  }));

  return (
    <div>
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
          滚动指标
        </h2>
      </div>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={excessData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
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
              tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(0)}%`}
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
                  excess_5d: '5日超额',
                  excess_10d: '10日超额',
                };
                const sign = v >= 0 ? '+' : '';
                return [`${sign}${v.toFixed(2)}%`, labels[name] || name];
              }}
            />
            <ReferenceLine y={0} stroke="#262626" />
            <Area
              type="monotone"
              dataKey="excess_5d"
              stroke="#3b82f6"
              strokeWidth={1}
              fill="#3b82f6"
              fillOpacity={0.06}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="excess_10d"
              stroke="#8b5cf6"
              strokeWidth={1}
              dot={false}
              connectNulls
              strokeDasharray="4 2"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="h-28 mt-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={streakData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
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
                  outperform: '超额连胜',
                  beta: 'Beta连胜',
                  risk: '高风险连胜',
                };
                return [`${v}`, labels[name] || name];
              }}
            />
            <ReferenceLine y={0} stroke="#262626" />
            <Line
              type="monotone"
              dataKey="outperform"
              stroke="#ef4444"
              strokeWidth={1}
              dot={false}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="beta"
              stroke="#3b82f6"
              strokeWidth={1}
              dot={false}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="risk"
              stroke="#f59e0b"
              strokeWidth={1}
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap items-center gap-3 mt-2 text-xs">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-anchor-accent" />
          <span className="text-anchor-textMuted">5日超额: 过去5日超额收益累计</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-signal-alpha border-dashed" style={{ borderTop: '1px dashed #8b5cf6' }} />
          <span className="text-anchor-textMuted">10日超额: 过去10日超额收益累计</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-anchor-positive" />
          <span className="text-anchor-textMuted">超额连胜: 连续跑赢/跑输天数</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-signal-volume" />
          <span className="text-anchor-textMuted">高风险连胜: 连续处于高风险状态天数</span>
        </div>
      </div>
    </div>
  );
}
