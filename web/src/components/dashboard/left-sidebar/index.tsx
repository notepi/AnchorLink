'use client';

import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Membership, IndustrySnapshot, PeerMatrixRow, PoolConfig } from '@/types';
import { getPoolDisplayName, getPctColorClass, formatPct } from '@/lib/utils';

interface LeftSidebarProps {
  memberships: Membership[];
  instruments: PoolConfig['instruments'];
  matrix: PeerMatrixRow[];
  snapshot: IndustrySnapshot | null;
}

/**
 * 左侧股票池列表 - Client Component（支持 Tab 切换交互）
 */
export function LeftSidebar({ memberships, instruments, matrix, snapshot }: LeftSidebarProps) {
  const [activePool, setActivePool] = useState('direct_peers');

  // 按池子分组的成员
  const membershipsByPool = memberships
    .filter(m => m.enabled)
    .reduce((acc, m) => {
      if (!acc[m.universe_id]) acc[m.universe_id] = [];
      acc[m.universe_id].push(m);
      return acc;
    }, {} as Record<string, Membership[]>);

  // 获取股票名称映射
  const instrumentMap = instruments.reduce((acc, i) => {
    acc[i.symbol] = i;
    return acc;
  }, {} as Record<string, { name: string; symbol: string }>);

  // 获取 matrix 数据（用于显示涨跌幅）
  const matrixMap = matrix.reduce((acc, row) => {
    acc[row.symbol] = row;
    return acc;
  }, {} as Record<string, PeerMatrixRow>);

  // 池子列表
  const pools = ['direct_peers', 'industry_chain', 'theme_pool', 'trading_watchlist'];

  return (
    <aside className="w-64 border-r border-anchor-border bg-anchor-bgSecondary overflow-y-auto shrink-0">
      <div className="p-2">
        <Tabs value={activePool} onValueChange={setActivePool} className="w-full">
          <TabsList className="w-full grid grid-cols-4 h-6">
            {pools.map(poolId => (
              <TabsTrigger key={poolId} value={poolId} className="text-xs px-1">
                {poolId === 'direct_peers' ? '核心' :
                 poolId === 'industry_chain' ? '产业' :
                 poolId === 'theme_pool' ? '主题' : '交易'}
              </TabsTrigger>
            ))}
          </TabsList>

          {pools.map(poolId => (
            <TabsContent key={poolId} value={poolId} className="mt-2">
              <div className="space-y-1">
                {/* 池子状态汇总 */}
                {snapshot && snapshot.group_rotation.group_medians[poolId] !== undefined && (
                  <div className="text-xs text-anchor-textSecondary px-2 py-1 bg-anchor-bg rounded-sm mb-2">
                    中位数: {formatPct(snapshot.group_rotation.group_medians[poolId])}
                  </div>
                )}

                {/* 成员列表 */}
                {(membershipsByPool[poolId] || []).length > 0 ? (
                  membershipsByPool[poolId].map(member => {
                    const instrument = instrumentMap[member.symbol];
                    const matrixRow = matrixMap[member.symbol];
                    return (
                      <div
                        key={`${member.universe_id}-${member.symbol}`}
                        className="flex items-center justify-between px-2 py-1 hover:bg-anchor-bg rounded-sm cursor-pointer transition-colors"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-xs font-mono text-anchor-textSecondary truncate">
                            {member.symbol.slice(0, 6)}
                          </span>
                          <span className="text-xs text-anchor-text truncate">
                            {instrument?.name || member.symbol}
                          </span>
                        </div>
                        <span className={`text-xs font-mono ${getPctColorClass(matrixRow?.pct_chg)}`}>
                          {formatPct(matrixRow?.pct_chg)}
                        </span>
                      </div>
                    );
                  })
                ) : (
                  <div className="text-xs text-anchor-textMuted p-2">
                    {getPoolDisplayName(poolId)}池暂无成员
                  </div>
                )}
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </aside>
  );
}