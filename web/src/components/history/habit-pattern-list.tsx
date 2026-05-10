'use client';

import { useState } from 'react';
import { PersonalityPattern } from '@/types';

interface HabitPatternListProps {
  patterns: PersonalityPattern[];
  title?: string;
  type: 'likes' | 'dislikes' | 'counter_intuitive' | 'trap';
}

export function HabitPatternList({ patterns, title, type }: HabitPatternListProps) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (!patterns || patterns.length === 0) {
    return null;
  }

  const lineColor = {
    likes: 'border-l-red-500',
    dislikes: 'border-l-green-500',
    counter_intuitive: 'border-l-purple-500',
    trap: 'border-l-orange-500',
  }[type];

  const sectionTitle = title || (type === 'likes' ? '偏好环境' :
    type === 'dislikes' ? '规避环境' :
    type === 'counter_intuitive' ? '反直觉机会' : '信号陷阱');

  const significanceMap = {
    strong: { label: '强', stars: 5, color: 'bg-red-500/20 text-red-400' },
    suggestive: { label: '提示', stars: 3, color: 'bg-yellow-500/20 text-yellow-400' },
    weak: { label: '弱', stars: 1, color: 'bg-gray-500/20 text-gray-400' },
    insufficient: { label: '-', stars: 0, color: 'bg-gray-500/20 text-gray-400' },
  };

  const toggleExpand = (idx: number) => {
    setExpandedIdx(expandedIdx === idx ? null : idx);
  };

  return (
    <div>
      <h3 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-2 px-1">
        {sectionTitle} <span className="text-anchor-textMuted">({patterns.length})</span>
      </h3>

      <div className="space-y-0.5">
        {patterns.map((pattern, idx) => {
          const sig = significanceMap[pattern.significance] || significanceMap.weak;
          const isPositive = (pattern.avg_next_1d ?? 0) >= 0;
          const barWidth = Math.min(Math.abs(pattern.avg_next_1d ?? 0) / 10 * 100, 100);
          const isExpanded = expandedIdx === idx;

          return (
            <div
              key={idx}
              className={`border-l-2 ${lineColor} bg-anchor-bgTertiary hover:bg-anchor-bgSecondary transition-colors cursor-pointer`}
              onClick={() => toggleExpand(idx)}
            >
              {/* 主行 */}
              <div className="flex items-center gap-2 px-2 py-1.5">
                {/* 标签名 */}
                <span className="text-xs text-anchor-text truncate flex-1 min-w-0" title={pattern.display_label}>
                  {pattern.display_label}
                </span>

                {/* significance badge */}
                <span className={`px-1 py-0.5 text-[10px] rounded-sm ${sig.color}`}>
                  {sig.label}
                </span>

                {/* n=xx */}
                <span className="text-[10px] text-anchor-textMuted w-10 text-right">
                  n={pattern.count}
                </span>

                {/* 次日收益 */}
                <span className={`text-xs font-medium w-12 text-right ${isPositive ? 'text-red-400' : 'text-green-400'}`}>
                  {pattern.avg_next_1d !== null ? `${isPositive ? '+' : ''}${pattern.avg_next_1d.toFixed(2)}` : '-'}
                </span>

                {/* 星级 */}
                <div className="flex gap-0.5 w-12 justify-end">
                  {Array.from({ length: 5 }).map((_, sidx) => (
                    <span
                      key={sidx}
                      className={`text-[10px] ${sidx < sig.stars ? 'text-yellow-400' : 'text-gray-600'}`}
                    >
                      ★
                    </span>
                  ))}
                </div>

                {/* 迷你方向条 */}
                <div className="w-12 h-1.5 bg-anchor-bgSecondary rounded-full overflow-hidden flex-shrink-0">
                  <div
                    className={`h-full rounded-full ${isPositive ? 'bg-red-500' : 'bg-green-500'}`}
                    style={{ width: `${barWidth}%`, marginLeft: isPositive ? '0' : `${100 - barWidth}%` }}
                  />
                </div>
              </div>

              {/* 展开详情 */}
              {isExpanded && (
                <div className="px-2 pb-2 pt-0 border-t border-anchor-border/30">
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-anchor-textMuted pt-1.5">
                    {pattern.avg_next_1d_delta_pp !== null && (
                      <span>超额: <span className={pattern.avg_next_1d_delta_pp >= 0 ? 'text-red-400' : 'text-green-400'}>
                        {pattern.avg_next_1d_delta_pp >= 0 ? '+' : ''}{pattern.avg_next_1d_delta_pp.toFixed(2)}pp
                      </span></span>
                    )}
                    {pattern.win_rate_1d !== null && (
                      <span>胜率: {(pattern.win_rate_1d * 100).toFixed(0)}%</span>
                    )}
                    {pattern.avg_next_3d !== null && (
                      <span>T+3: {pattern.avg_next_3d >= 0 ? '+' : ''}{pattern.avg_next_3d.toFixed(2)}pp</span>
                    )}
                    {pattern.avg_next_5d !== null && (
                      <span>T+5: {pattern.avg_next_5d >= 0 ? '+' : ''}{pattern.avg_next_5d.toFixed(2)}pp</span>
                    )}
                    {pattern.best_condition && (
                      <span>最佳: {pattern.best_condition.quadrant} ({pattern.best_condition.avg_next_1d !== null ? `${pattern.best_condition.avg_next_1d >= 0 ? '+' : ''}${pattern.best_condition.avg_next_1d.toFixed(2)}pp` : '-'})</span>
                    )}
                  </div>
                  <p className="text-[10px] text-anchor-textMuted mt-1">{pattern.explanation}</p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
