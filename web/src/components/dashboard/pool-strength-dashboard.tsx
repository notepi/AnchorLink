'use client';

import { TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GroupRotation, PoolType } from '@/types';
import { getPoolDisplayName, getPoolShortName, formatPct, cn } from '@/lib/utils';
import { STRONG_THRESHOLD, WEAK_THRESHOLD } from '@/lib/constants';

interface PoolStrengthDashboardProps {
  groupRotation: GroupRotation;
}

const POOL_ORDER: PoolType[] = ['direct_peers', 'industry_chain', 'theme_pool', 'trading_watchlist'];

/**
 * 池子强弱仪表盘
 */
export function PoolStrengthDashboard({ groupRotation }: PoolStrengthDashboardProps) {
  const { group_medians, strongest_group, weakest_group } = groupRotation;

  // 排序池子（按涨跌幅降序）- 使用 slice() 创建新数组避免 mutation
  const sortedPools = POOL_ORDER
    .map((id) => ({ id, value: group_medians[id] ?? null }))
    .slice()
    .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

  // 最强/最弱池数据
  const strongestValue = strongest_group ? group_medians[strongest_group] : null;
  const weakestValue = weakest_group ? group_medians[weakest_group] : null;
  const gap = strongestValue !== null && weakestValue !== null
    ? strongestValue - weakestValue
    : null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-xs">池子强弱仪表盘</CardTitle>
          <div className="text-xs text-anchor-textMuted">
            {sortedPools.length} 个池子
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* 池子卡片网格 */}
        <div className="grid grid-cols-4 gap-2">
          {POOL_ORDER.map((poolId) => {
            const value = group_medians[poolId];
            const isPositive = value !== null && value > 0;
            const isStrong = value !== null && value > STRONG_THRESHOLD;
            const isWeak = value !== null && value < WEAK_THRESHOLD;
            const isStrongest = poolId === strongest_group;
            const isWeakest = poolId === weakest_group;

            return (
              <div
                key={poolId}
                className={cn(
                  'rounded-sm border p-2.5 text-center transition-colors',
                  isStrongest
                    ? 'border-anchor-positive/60 bg-anchor-positive/10'
                    : isWeakest
                      ? 'border-anchor-negative/60 bg-anchor-negative/10'
                      : 'border-anchor-border bg-anchor-bg hover:bg-anchor-bgSecondary'
                )}
              >
                {/* 简称 */}
                <div className="text-xs text-anchor-textMuted mb-1">
                  {getPoolShortName(poolId)}
                </div>

                {/* 涨跌幅 */}
                <div className={cn(
                  'text-base font-mono font-semibold',
                  isStrong
                    ? 'text-anchor-positive'
                    : isWeak
                      ? 'text-anchor-negative'
                      : isPositive
                        ? 'text-anchor-positive/70'
                        : 'text-anchor-negative/70'
                )}>
                  {formatPct(value)}
                </div>

                {/* 方向箭头 */}
                <div className="mt-0.5">
                  {isPositive ? (
                    <ArrowUpRight className={cn(
                      'h-3.5 w-3.5 mx-auto',
                      isStrong ? 'text-anchor-positive' : 'text-anchor-positive/60'
                    )} />
                  ) : (
                    <ArrowDownRight className={cn(
                      'h-3.5 w-3.5 mx-auto',
                      isWeak ? 'text-anchor-negative' : 'text-anchor-negative/60'
                    )} />
                  )}
                </div>

                {/* 状态标记 */}
                {isStrongest && (
                  <div className="mt-1 text-xs text-anchor-positive font-medium">
                    最强
                  </div>
                )}
                {isWeakest && (
                  <div className="mt-1 text-xs text-anchor-negative font-medium">
                    最弱
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* 最强 vs 最弱 对比 */}
        <div className="flex items-center justify-between py-2 border-t border-anchor-border">
          {strongest_group && (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-anchor-textMuted">最强:</span>
              <span className="text-xs text-anchor-positive font-medium">
                {getPoolShortName(strongest_group)}
              </span>
              <span className="text-xs text-anchor-positive font-mono">
                {formatPct(strongestValue)}
              </span>
            </div>
          )}

          {/* 强弱差距 */}
          {gap !== null && (
            <div className={cn(
              'px-2 py-0.5 rounded-sm text-xs font-mono',
              gap > 0 ? 'text-anchor-positive bg-anchor-positive/10' : 'text-anchor-textMuted'
            )}>
              差距 {formatPct(gap)}
            </div>
          )}

          {weakest_group && (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-anchor-textMuted">最弱:</span>
              <span className="text-xs text-anchor-negative font-medium">
                {getPoolShortName(weakest_group)}
              </span>
              <span className="text-xs text-anchor-negative font-mono">
                {formatPct(weakestValue)}
              </span>
            </div>
          )}
        </div>

        {/* 强弱排名 */}
        <div className="border-t border-anchor-border pt-2">
          <div className="text-xs text-anchor-textSecondary mb-1.5">强弱排名</div>
          <div className="flex items-center gap-1">
            {sortedPools.map((pool, index) => (
              <div
                key={pool.id}
                className={cn(
                  'flex items-center gap-1 px-2 py-1 rounded-sm text-xs',
                  index === 0
                    ? 'bg-anchor-positive/10 text-anchor-positive'
                    : index === sortedPools.length - 1
                      ? 'bg-anchor-negative/10 text-anchor-negative'
                      : 'bg-anchor-bgSecondary text-anchor-textMuted'
                )}
              >
                <span className="font-mono text-xs opacity-60">#{index + 1}</span>
                <span>{getPoolShortName(pool.id)}</span>
                <span className="font-mono">
                  {formatPct(pool.value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}