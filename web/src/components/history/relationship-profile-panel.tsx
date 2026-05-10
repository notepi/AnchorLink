'use client';

import { useState } from 'react';
import { RelationshipProfile } from '@/types';

interface RelationshipProfilePanelProps {
  profile: RelationshipProfile;
}

const relationLabels: Record<string, string> = {
  follows: '跟随',
  leads: '领先',
  lags: '滞后',
  mean_reverts: '均值回归',
  diverges: '独立',
  unstable: '不稳定'
};

const relationColors: Record<string, string> = {
  follows: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  leads: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  lags: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  mean_reverts: 'bg-green-500/20 text-green-400 border-green-500/30',
  diverges: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  unstable: 'bg-gray-500/20 text-gray-400 border-gray-500/30'
};

export function RelationshipProfilePanel({ profile }: RelationshipProfilePanelProps) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const pools = [
    { key: 'anchor_vs_chain' as const, name: '产业链' },
    { key: 'anchor_vs_theme' as const, name: '主题池' },
    { key: 'anchor_vs_core' as const, name: '主线池' },
    { key: 'anchor_vs_trading_watchlist' as const, name: '交易观察池' }
  ];

  return (
    <div>
      <h3 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-2 px-1">
        产业联动关系
      </h3>

      <div className="space-y-0.5">
        {pools.map((pool, idx) => {
          const pattern = profile[pool.key];
          const colorClass = relationColors[pattern.relation] || relationColors.unstable;
          const isHovered = hoveredIdx === idx;

          return (
            <div
              key={pool.key}
              className={`flex items-center gap-3 px-2 py-2 bg-anchor-bgTertiary hover:bg-anchor-bgSecondary transition-colors cursor-pointer`}
              onMouseEnter={() => setHoveredIdx(idx)}
              onMouseLeave={() => setHoveredIdx(null)}
            >
              {/* 池名 */}
              <span className="text-xs text-anchor-text w-20 flex-shrink-0">{pool.name}</span>

              {/* relation 胶囊 */}
              <span className={`px-1.5 py-0.5 text-[10px] rounded-sm border ${colorClass}`}>
                {relationLabels[pattern.relation] || pattern.relation}
              </span>

              {/* avg_relative_strength */}
              {pattern.avg_relative_strength !== null && (
                <span className={`text-xs font-medium ${pattern.avg_relative_strength >= 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {pattern.avg_relative_strength >= 0 ? '+' : ''}{pattern.avg_relative_strength.toFixed(2)}pp
                </span>
              )}

              {/* same_day_corr */}
              {pattern.same_day_corr !== null && (
                <span className="text-[10px] text-anchor-textMuted">
                  r={pattern.same_day_corr >= 0 ? '+' : ''}{pattern.same_day_corr.toFixed(2)}
                </span>
              )}

              {/* evidence 悬停展开 */}
              {isHovered && pattern.evidence.length > 0 && (
                <div className="absolute z-10 mt-16 bg-anchor-bgTertiary border border-anchor-border rounded-sm px-3 py-2 shadow-lg max-w-[280px]">
                  {pattern.evidence.map((ev, eidx) => (
                    <p key={eidx} className="text-[10px] text-anchor-textMuted">{ev}</p>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
