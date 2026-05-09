import React from 'react';
import type { QuadrantStat } from '@/types';

interface QuadrantGridProps {
  data: QuadrantStat[];
  bestQuadrant?: QuadrantStat | null;
  worstQuadrant?: QuadrantStat | null;
}

// 新旧格式映射
const QUADRANT_DISPLAY_TO_INTERNAL: Record<string, string> = {
  '行业强+个股强': 'positive+positive',
  '行业强+个股中': 'positive+neutral',
  '行业强+个股弱': 'positive+negative',
  '行业中+个股强': 'neutral+positive',
  '行业中+个股中': 'neutral+neutral',
  '行业中+个股弱': 'neutral+negative',
  '行业弱+个股强': 'negative+positive',
  '行业弱+个股中': 'negative+neutral',
  '行业弱+个股弱': 'negative+negative',
};

const BETA_ORDER = ['行业强', '行业中', '行业弱'] as const;
const ALPHA_ORDER = ['个股强', '个股中', '个股弱'] as const;

function pctColor(value: number | null): string {
  if (value === null) return 'text-anchor-textMuted';
  if (value > 0) return 'text-anchor-positive';
  if (value < 0) return 'text-anchor-negative';
  return 'text-anchor-text';
}

function winRateColor(value: number | null): string {
  if (value === null) return 'text-anchor-textMuted';
  if (value >= 0.5) return 'text-anchor-positive';
  return 'text-anchor-negative';
}

function formatPct(v: number | null): string {
  if (v === null) return '--';
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}%`;
}

export function QuadrantGrid({ data, bestQuadrant, worstQuadrant }: QuadrantGridProps) {
  const lookup = new Map(data.map((q) => [q.quadrant, q]));

  // 最佳/最差象限集合
  const bestKeys = new Set<string>();
  const worstKeys = new Set<string>();
  if (bestQuadrant) {
    bestKeys.add(bestQuadrant.quadrant);
    // 也找一下 display 格式的 key
    const displayKey = Object.entries(QUADRANT_DISPLAY_TO_INTERNAL).find(
      ([, internal]) => internal === bestQuadrant.quadrant
    )?.[0];
    if (displayKey) bestKeys.add(displayKey);
  }
  if (worstQuadrant) {
    worstKeys.add(worstQuadrant.quadrant);
    const displayKey = Object.entries(QUADRANT_DISPLAY_TO_INTERNAL).find(
      ([, internal]) => internal === worstQuadrant.quadrant
    )?.[0];
    if (displayKey) worstKeys.add(displayKey);
  }

  return (
    <div>
      <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-3">
        四象限统计
      </h2>
      <div className="grid grid-cols-[auto_repeat(3,1fr)] gap-px bg-anchor-border rounded-sm overflow-hidden">
        {/* Header row */}
        <div className="bg-anchor-bgTertiary p-2" />
        {ALPHA_ORDER.map((alpha) => (
          <div
            key={alpha}
            className="bg-anchor-bgTertiary px-2 py-1.5 text-xs text-anchor-textSecondary text-center font-medium"
          >
            {alpha}
          </div>
        ))}

        {/* Data rows */}
        {BETA_ORDER.map((beta) => (
          <React.Fragment key={beta}>
            <div
              className="bg-anchor-bgTertiary px-2 py-1.5 text-xs text-anchor-textSecondary font-medium flex items-center"
            >
              {beta}
            </div>
            {ALPHA_ORDER.map((alpha) => {
              const displayKey = `${beta}+${alpha}`;
              const internalKey = QUADRANT_DISPLAY_TO_INTERNAL[displayKey];
              const stat = lookup.get(displayKey) || lookup.get(internalKey);
              const isEmpty = !stat || stat.count === 0;
              const isBest = bestKeys.has(displayKey) || bestKeys.has(internalKey!);
              const isWorst = worstKeys.has(displayKey) || worstKeys.has(internalKey!);
              const isLowSample = stat && stat.count > 0 && stat.count < 5;

              let bgClass = 'bg-anchor-bgSecondary';
              if (isBest) bgClass = 'bg-anchor-positive/20';
              else if (isWorst) bgClass = 'bg-anchor-negative/20';

              return (
                <div
                  key={displayKey}
                  className={`${bgClass} p-2 ${isEmpty ? 'opacity-40' : ''}`}
                >
                  <div className="text-xs text-anchor-textMuted mb-1">
                    {stat?.count ?? 0} 天
                    {isLowSample && <span className="ml-1 text-anchor-textMuted">· 样本少</span>}
                    {isBest && <span className="ml-1 text-anchor-positive">· 最佳</span>}
                    {isWorst && <span className="ml-1 text-anchor-negative">· 最差</span>}
                  </div>
                  <div className={`text-sm font-mono font-medium ${pctColor(stat?.avg_next_1d ?? null)}`}>
                    {formatPct(stat?.avg_next_1d ?? null)}
                  </div>
                  <div className="text-xs text-anchor-textMuted font-mono">
                    5日: {formatPct(stat?.avg_next_5d ?? null)}
                  </div>
                  <div className={`text-xs font-mono ${winRateColor(stat?.win_rate_1d ?? null)}`}>
                    {stat && stat.win_rate_1d !== null
                      ? `胜率 ${(stat.win_rate_1d * 100).toFixed(0)}%`
                      : '--'}
                  </div>
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
