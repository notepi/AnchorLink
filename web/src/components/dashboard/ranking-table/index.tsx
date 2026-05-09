'use client';

import { useState } from 'react';
import { PeerMatrixRow } from '@/types';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { cn, getPctColorClass, formatPct, formatAmount } from '@/lib/utils';

interface RankingTableProps {
  data: PeerMatrixRow[];
}

const poolNames: Record<string, string> = {
  direct_peers: '核心',
  industry_chain: '产业',
  theme_pool: '主题',
  trading_watchlist: '交易',
};

// 格式化资金流向（正数绿色，负数红色）
function formatFundFlow(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}万`;
}

function getFundFlowColorClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'text-anchor-textSecondary';
  if (value > 0) return 'text-anchor-positive';
  if (value < 0) return 'text-anchor-negative';
  return 'text-anchor-textSecondary';
}

// 格式化换手率
function formatTurnover(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return `${value.toFixed(2)}%`;
}

// 格式化估值分位
function formatValuation(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return `${value.toFixed(0)}%`;
}

export function RankingTable({ data }: RankingTableProps) {
  const [selectedPool, setSelectedPool] = useState<string>('all');

  const poolFilters = [
    { value: 'all', label: '全部' },
    { value: 'direct_peers', label: '核心' },
    { value: 'industry_chain', label: '产业' },
    { value: 'theme_pool', label: '主题' },
    { value: 'trading_watchlist', label: '交易' },
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

        {/* 完整表格 */}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1200px]">
            <thead className="bg-anchor-bg border-b border-anchor-border">
              <tr>
                <th className="px-3 py-1.5 text-left text-xs font-medium text-anchor-textSecondary">池子</th>
                <th className="px-3 py-1.5 text-left text-xs font-medium text-anchor-textSecondary">代码</th>
                <th className="px-3 py-1.5 text-left text-xs font-medium text-anchor-textSecondary">名称</th>
                <th className="px-3 py-1.5 text-left text-xs font-medium text-anchor-textSecondary">角色</th>
                <th className="px-3 py-1.5 text-left text-xs font-medium text-anchor-textSecondary">涨跌幅</th>
                <th className="px-3 py-1.5 text-left text-xs font-medium text-anchor-textSecondary">成交额</th>
                <th className="px-3 py-1.5 text-left text-xs font-medium text-anchor-textSecondary">换手率</th>
                <th className="px-3 py-1.5 text-left text-xs font-medium text-anchor-textSecondary">资金流向</th>
                <th className="px-3 py-1.5 text-left text-xs font-medium text-anchor-textSecondary">估值分位</th>
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
                  <td className="px-3 py-1 text-xs font-mono text-anchor-text">
                    {formatAmount(row.amount)}
                  </td>
                  <td className="px-3 py-1 text-xs font-mono text-anchor-text">
                    {formatTurnover(row.turnover_rate)}
                  </td>
                  <td className={cn('px-3 py-1 text-xs font-mono font-medium', getFundFlowColorClass(row.fund_flow))}>
                    {formatFundFlow(row.fund_flow)}
                  </td>
                  <td className="px-3 py-1 text-xs font-mono text-anchor-text">
                    {formatValuation(row.valuation_percentile)}
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