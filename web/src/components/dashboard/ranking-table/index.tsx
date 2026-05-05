'use client';

import { useState } from 'react';
import { PeerMatrixRow } from '@/types';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { cn, getPctColorClass, formatPct } from '@/lib/utils';

interface RankingTableProps {
  data: PeerMatrixRow[];
}

const poolNames: Record<string, string> = {
  direct_peers: '核心同类',
  industry_chain: '产业链',
  theme_pool: '主题情绪',
  trading_watchlist: '交易观察',
};

export function RankingTable({ data }: RankingTableProps) {
  const [selectedPool, setSelectedPool] = useState<string>('all');

  const poolFilters = [
    { value: 'all', label: '全部' },
    { value: 'direct_peers', label: '核心同类' },
    { value: 'industry_chain', label: '产业链' },
    { value: 'theme_pool', label: '主题情绪' },
    { value: 'trading_watchlist', label: '交易观察' },
  ];

  const filteredData = selectedPool === 'all'
    ? data
    : data.filter(row => row.universe === selectedPool);

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>同类矩阵</CardTitle>
        <CardDescription>共 {filteredData.length} 条记录</CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {/* 过滤器 - 直接用 onClick 不用任何 wrapper */}
        <div className="px-4 py-2 border-b border-anchor-border bg-anchor-bgSecondary">
          <div className="flex gap-1">
            {poolFilters.map(filter => (
              <button
                key={filter.value}
                onClick={() => {
                  console.log('[RankingTable] Button clicked:', filter.value);
                  setSelectedPool(filter.value);
                }}
                className={cn(
                  'px-2 py-0.5 text-xs rounded-sm transition-colors',
                  selectedPool === filter.value
                    ? 'bg-anchor-accent text-anchor-text'
                    : 'text-anchor-textSecondary hover:text-anchor-text hover:bg-anchor-bg'
                )}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>

        {/* 简化表格 */}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px]">
            <thead className="bg-anchor-bg border-b border-anchor-border">
              <tr>
                <th className="px-3 py-1.5 text-left text-xs font-medium text-anchor-textSecondary">池子</th>
                <th className="px-3 py-1.5 text-left text-xs font-medium text-anchor-textSecondary">代码</th>
                <th className="px-3 py-1.5 text-left text-xs font-medium text-anchor-textSecondary">名称</th>
                <th className="px-3 py-1.5 text-left text-xs font-medium text-anchor-textSecondary">角色</th>
                <th className="px-3 py-1.5 text-left text-xs font-medium text-anchor-textSecondary">涨跌幅</th>
              </tr>
            </thead>
            <tbody>
              {filteredData.map((row, i) => (
                <tr
                  key={`${row.symbol}-${i}`}
                  className="border-b border-anchor-border/50 hover:bg-anchor-bgSecondary/50"
                >
                  <td className="px-3 py-1 text-xs text-anchor-text">
                    {poolNames[row.universe] || row.universe}
                  </td>
                  <td className="px-3 py-1 text-xs font-mono text-anchor-text">{row.symbol}</td>
                  <td className="px-3 py-1 text-xs text-anchor-text">{row.name || '--'}</td>
                  <td className="px-3 py-1 text-xs text-anchor-textSecondary">{row.role || '--'}</td>
                  <td className={cn('px-3 py-1 text-xs font-mono font-medium', getPctColorClass(row.pct_chg))}>
                    {formatPct(row.pct_chg)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}