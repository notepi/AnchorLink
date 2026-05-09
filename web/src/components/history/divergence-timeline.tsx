'use client';

import { useState } from 'react';
import type { EventPathRow } from '@/types';
import type { DivergenceWithFollowThrough } from '@/lib/history-analysis';

interface DivergenceTimelineProps {
  divergences: DivergenceWithFollowThrough[];
  events: EventPathRow[];
}

function formatDate(date: string) {
  if (!date || date.length !== 8) return date;
  return `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`;
}

function pctColor(value: number | null): string {
  if (value === null) return 'text-anchor-textMuted';
  if (value > 0) return 'text-anchor-positive';
  if (value < 0) return 'text-anchor-negative';
  return 'text-anchor-text';
}

function formatPct(v: number | null): string {
  if (v === null) return '--';
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}%`;
}

export function DivergenceTimeline({ divergences, events }: DivergenceTimelineProps) {
  const [expanded, setExpanded] = useState<string | null>(null);

  const eventMap = new Map<string, EventPathRow[]>();
  for (const e of events) {
    const list = eventMap.get(e.event_date) || [];
    list.push(e);
    eventMap.set(e.event_date, list);
  }

  // 按日期倒序展示
  const sortedDivergences = [...divergences].sort((a, b) => {
    const dateA = String(a.date);
    const dateB = String(b.date);
    return dateB.localeCompare(dateA);
  });

  return (
    <div>
      <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-3">
        极端背离事件
      </h2>
      <div className="space-y-2">
        {sortedDivergences.map((d) => {
          const isExpanded = expanded === d.date;
          const paths = eventMap.get(d.date) || [];
          const isPositive = d.divergence > 0;

          return (
            <div key={d.date} className="bg-anchor-bgSecondary rounded-sm border border-anchor-border overflow-hidden">
              <button
                type="button"
                onClick={() => setExpanded(isExpanded ? null : d.date)}
                className="w-full text-left px-3 py-2 flex items-center gap-3 hover:bg-anchor-bgTertiary/50 transition-colors"
              >
                <div
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    isPositive ? 'bg-anchor-positive' : 'bg-anchor-negative'
                  }`}
                />
                <span className="text-xs font-mono text-anchor-textSecondary">
                  {formatDate(d.date)}
                </span>
                <span className={`text-sm font-mono font-medium ${pctColor(d.divergence)}`}>
                  {formatPct(d.divergence)}
                </span>
                <span className="text-xs text-anchor-textMuted">背离</span>
                <div className="flex items-center gap-3 text-xs font-mono">
                  <span className="text-anchor-textMuted">T+1:</span>
                  <span className={pctColor(d.t1Return)}>{formatPct(d.t1Return)}</span>
                  <span className={pctColor(d.t1Excess)}>({formatPct(d.t1Excess)})</span>
                  <span className="text-anchor-textMuted">T+3:</span>
                  <span className={pctColor(d.t3Return)}>{formatPct(d.t3Return)}</span>
                  <span className={pctColor(d.t3Excess)}>({formatPct(d.t3Excess)})</span>
                </div>
                <div className="ml-auto flex items-center gap-2">
                  {d.industry_beta && (
                    <span className="text-xs text-anchor-textMuted">
                      Beta={d.industry_beta === 'positive' ? '+' : d.industry_beta === 'negative' ? '-' : '0'}
                    </span>
                  )}
                  <span className="text-xs text-anchor-textMuted">
                    {isExpanded ? '收起' : '展开路径'}
                  </span>
                </div>
              </button>

              {isExpanded && paths.length > 0 && (
                <div className="px-3 pb-3 border-t border-anchor-borderSubtle pt-2">
                  <div className="text-xs text-anchor-textMuted mb-2">
                    T-5 → T+5 事件路径
                  </div>
                  <div className="flex items-end gap-1 h-20">
                    {paths.map((p) => {
                      const barHeight = Math.min(Math.abs(p.excess ?? 0) * 3, 72);
                      const isUp = (p.excess ?? 0) >= 0;
                      return (
                        <div
                          key={p.offset}
                          className="flex-1 flex flex-col items-center gap-0.5"
                        >
                          <div
                            className={`w-full rounded-sm ${isUp ? 'bg-anchor-positive/30' : 'bg-anchor-negative/30'}`}
                            style={{
                              height: `${barHeight}px`,
                              marginTop: isUp ? 'auto' : undefined,
                            }}
                          />
                          <span className="text-[9px] text-anchor-textMuted font-mono">
                            T{p.offset >= 0 ? '+' : ''}{p.offset}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  <div className="mt-2 grid grid-cols-6 gap-2 text-xs">
                    {paths.map((p) => (
                      <div key={p.offset} className="text-center">
                        <div className={`font-mono ${pctColor(p.anchor_return)}`}>
                          {formatPct(p.anchor_return)}
                        </div>
                        <div className="font-mono text-anchor-textMuted">
                          {formatPct(p.chain_median)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
        {sortedDivergences.length === 0 && (
          <div className="text-center text-anchor-textMuted py-4 text-sm">
            暂无极端背离事件
          </div>
        )}
      </div>
    </div>
  );
}
