'use client';

import { useState } from 'react';
import type { BusinessGroup, SignalLiftRow } from '@/types';

interface SignalBusinessGroupsProps {
  groups: BusinessGroup[];
}

function deltaPpColor(value: number | null): string {
  if (value === null) return 'text-anchor-textMuted';
  if (value > 0) return 'text-anchor-positive';
  if (value < 0) return 'text-anchor-negative';
  return 'text-anchor-text';
}

function GroupSignalItem({ signal }: { signal: SignalLiftRow }) {
  return (
    <li className="flex items-center justify-between gap-2 text-xs py-1">
      <span className="text-anchor-text truncate" title={signal.label}>{signal.label}</span>
      <span className={`font-mono shrink-0 ${deltaPpColor(signal.avg_next_1d_delta_pp)}`}>
        {signal.avg_next_1d_delta_pp !== null
          ? `${signal.avg_next_1d_delta_pp >= 0 ? '+' : ''}${signal.avg_next_1d_delta_pp.toFixed(2)}pp`
          : '--'}
      </span>
    </li>
  );
}

function BusinessGroupCard({ group }: { group: BusinessGroup }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const avgDelta = group.signals.length > 0
    ? group.signals.reduce((sum, s) => sum + (s.avg_next_1d_delta_pp ?? 0), 0) / group.signals.length
    : null;

  return (
    <div className="bg-anchor-bgSecondary rounded-sm border border-anchor-border overflow-hidden">
      <button
        className="w-full p-3 border-b border-anchor-border flex items-center justify-between cursor-pointer hover:bg-anchor-bgTertiary text-left"
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
      >
        <div>
          <h3 className="text-xs font-medium text-anchor-text">{group.name}</h3>
          <p className="text-xs text-anchor-textMuted mt-0.5">{group.description}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`font-mono text-xs ${deltaPpColor(avgDelta)}`}>
            {avgDelta !== null ? `${avgDelta >= 0 ? '+' : ''}${avgDelta.toFixed(2)}pp` : '--'}
          </span>
          <span className="text-xs text-anchor-textMuted">{group.signals.length}个</span>
          <span className="text-xs text-anchor-textMuted">{isExpanded ? '▲' : '▼'}</span>
        </div>
      </button>
      {isExpanded && (
        <ul className="p-2 space-y-0.5">
          {group.signals.map((s) => (
            <GroupSignalItem key={s.label} signal={s} />
          ))}
        </ul>
      )}
    </div>
  );
}

export function SignalBusinessGroups({ groups }: SignalBusinessGroupsProps) {
  if (groups.length === 0) return null;

  return (
    <div>
      <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-3">
        信号业务分组
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {groups.map((group) => (
          <BusinessGroupCard key={group.name} group={group} />
        ))}
      </div>
    </div>
  );
}
