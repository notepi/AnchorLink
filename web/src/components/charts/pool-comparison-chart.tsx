'use client';

import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GroupRotation } from '@/types';
import { getPoolDisplayName } from '@/lib/utils';

interface PoolComparisonChartProps {
  groupRotation: GroupRotation;
}

/**
 * 池子强弱对比图 - A股风格（涨红跌绿）
 */
export function PoolComparisonChart({ groupRotation }: PoolComparisonChartProps) {
  const data = Object.entries(groupRotation.group_medians)
    .map(([universeId, median]) => ({
      name: getPoolDisplayName(universeId),
      value: median || 0,
      universeId,
    }))
    .sort((a, b) => b.value - a.value);

  // A股颜色：涨红跌绿
  const getColor = (value: number) => {
    if (value > 0.5) return '#ef4444'; // 涨 = 红色
    if (value < -0.5) return '#22c55e'; // 跌 = 绿色
    return '#71717a';
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xs">池子强弱对比</CardTitle>
      </CardHeader>
      <CardContent className="h-28">
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical">
              <XAxis
                type="number"
                tickFormatter={(v) => `${v.toFixed(1)}%`}
                tick={{ fontSize: 10, fill: '#737373' }}
                axisLine={{ stroke: '#262626' }}
                tickLine={{ stroke: '#262626' }}
              />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fontSize: 10, fill: '#a3a3a3' }}
                axisLine={{ stroke: '#262626' }}
                tickLine={{ stroke: '#262626' }}
                width={50}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#111111',
                  border: '1px solid #262626',
                  borderRadius: '2px',
                  fontSize: '10px',
                }}
                formatter={(value: number) => [`${value.toFixed(2)}%`, '涨跌幅']}
              />
              <Bar dataKey="value" radius={[0, 2, 2, 0]}>
                {data.map((entry, index) => (
                  <Cell key={index} fill={getColor(entry.value)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="text-xs text-anchor-textMuted h-full flex items-center justify-center">
            暂无数据
          </div>
        )}
      </CardContent>
    </Card>
  );
}