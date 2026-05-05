'use client';

import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip, ReferenceLine } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GroupRotation } from '@/types';
import { getPoolDisplayName, formatPct } from '@/lib/utils';

interface GroupRotationChartProps {
  groupRotation: GroupRotation;
}

/**
 * 组间轮动图 - A股风格
 */
export function GroupRotationChart({ groupRotation }: GroupRotationChartProps) {
  const data = groupRotation.group_ranking
    .map((universeId, index) => ({
      name: getPoolDisplayName(universeId),
      value: groupRotation.group_medians[universeId] || 0,
      rank: index + 1,
      universeId,
    }));

  const spreadTexts: string[] = [];
  if (groupRotation.core_vs_chain_spread !== null) {
    spreadTexts.push(`核心vs产业链: ${formatPct(groupRotation.core_vs_chain_spread)}`);
  }
  if (groupRotation.core_vs_theme_spread !== null) {
    spreadTexts.push(`核心vs主题: ${formatPct(groupRotation.core_vs_theme_spread)}`);
  }
  if (groupRotation.core_vs_trading_spread !== null) {
    spreadTexts.push(`核心vs交易: ${formatPct(groupRotation.core_vs_trading_spread)}`);
  }

  // A股颜色：涨红跌绿
  const getColor = (rank: number, total: number) => {
    if (rank === 1) return '#ef4444'; // 最强 = 红色
    if (rank === total) return '#22c55e'; // 最弱 = 绿色
    return '#71717a';
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xs">组间轮动</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-28">
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
                <ReferenceLine x={0} stroke="#262626" />
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
                    <Cell key={index} fill={getColor(entry.rank, data.length)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-xs text-anchor-textMuted h-full flex items-center justify-center">
              暂无数据
            </div>
          )}
        </div>
        {/* Spread 值 */}
        {spreadTexts.length > 0 && (
          <div className="mt-1 text-xs text-anchor-textMuted space-y-0.5">
            {spreadTexts.map((text, index) => (
              <div key={index}>{text}</div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}