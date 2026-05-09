'use client';

import { useState, useMemo } from 'react';
import type { Combination } from '@/types';

interface SignalCombinationsProps {
  combinations: Combination[];
}

function deltaPpColor(value: number | null): string {
  if (value === null) return 'text-anchor-textMuted';
  if (value > 0) return 'text-anchor-positive';
  if (value < 0) return 'text-anchor-negative';
  return 'text-anchor-text';
}

function CombinationItem({ combination }: { combination: Combination }) {
  return (
    <li className="bg-anchor-bgTertiary rounded px-3 py-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-anchor-text truncate" title={combination.labels.join(' + ')}>
          {combination.labels.join(' + ')}
        </span>
        <span className="text-xs text-anchor-textMuted shrink-0 ml-2">样本{combination.count}</span>
      </div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-anchor-textSecondary">
          组合 Lift: <span className={`font-mono ml-1 ${deltaPpColor(combination.avgNext1d)}`}>
            {combination.avgNext1d !== null
              ? `${combination.avgNext1d >= 0 ? '+' : ''}${combination.avgNext1d.toFixed(2)}pp`
              : '--'}
          </span>
        </span>
        <span className="text-anchor-textSecondary">
          胜率: <span className={`font-mono ml-1 ${combination.winRate !== null && combination.winRate >= 0.5 ? 'text-anchor-positive' : 'text-anchor-negative'}`}>
            {combination.winRate !== null ? `${(combination.winRate * 100).toFixed(0)}%` : '--'}
          </span>
        </span>
      </div>
    </li>
  );
}

export function SignalCombinations({ combinations }: SignalCombinationsProps) {
  const [sortBy, setSortBy] = useState<'count' | 'delta' | 'winRate'>('delta');

  const sortedCombinations = useMemo(() => {
    return [...combinations].sort((a, b) => {
      if (sortBy === 'count') return b.count - a.count;
      if (sortBy === 'delta') return (b.avgNext1d ?? 0) - (a.avgNext1d ?? 0);
      return (b.winRate ?? 0) - (a.winRate ?? 0);
    });
  }, [combinations, sortBy]);

  return (
    <div className="bg-anchor-bgSecondary rounded-sm border border-anchor-border p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
          信号组合效应
        </h2>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          className="bg-anchor-bgTertiary border border-anchor-border text-xs rounded px-2 py-1 text-anchor-text"
          aria-label="排序方式"
        >
          <option value="delta">按 Lift 排序</option>
          <option value="winRate">按胜率排序</option>
          <option value="count">按样本排序</option>
        </select>
      </div>
      {sortedCombinations.length > 0 ? (
        <ul className="space-y-2">
          {sortedCombinations.map((c) => (
            <CombinationItem key={c.labels.join('+')} combination={c} />
          ))}
        </ul>
      ) : (
        <p className="text-xs text-anchor-textMuted text-center py-4">
          当前筛选条件下，样本 &gt;= 3 的组合未找到
        </p>
      )}
    </div>
  );
}
