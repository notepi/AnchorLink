'use client';

import { useState, useMemo } from 'react';
import type { DashboardView } from '@/types/dashboard-view';
import { formatPp, getValueColorClass } from '@/lib/history-v2/formatters';

interface SignalCombinationsProps {
  combinations: DashboardView['tableData']['signalCombinations'];
  synergies: DashboardView['tableData']['combinationSynergies'];
}

type SortKey = 'count' | 'delta' | 'winRate';

export default function SignalCombinations({ combinations, synergies }: SignalCombinationsProps) {
  const [sortBy, setSortBy] = useState<SortKey>('delta');
  const data = (synergies?.length ? synergies : combinations) ?? [];

  const sorted = useMemo(() => {
    return [...data].sort((a, b) => {
      if (sortBy === 'count') return (b.count ?? 0) - (a.count ?? 0);
      if (sortBy === 'delta') return (b.avgNext1d ?? 0) - (a.avgNext1d ?? 0);
      return (b.winRate ?? 0) - (a.winRate ?? 0);
    });
  }, [data, sortBy]);

  return (
    <div className="list-card">
      <h3>信号组合效应 <span className="muted">({data.length})</span></h3>
      {data.length > 0 ? (
        <>
          <div style={{ marginBottom: '8px' }}>
            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value as SortKey)}
              style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border)', borderRadius: '3px', padding: '2px 8px', fontSize: '11px', color: 'var(--text)' }}
            >
              <option value="delta">按 Lift 排序</option>
              <option value="winRate">按胜率排序</option>
              <option value="count">按样本排序</option>
            </select>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {sorted.map((c, i) => {
              const labels = c.labels ?? c.displayLabels ?? [`组合${i + 1}`];
              const labelStr = labels.join(' + ');
              return (
                <div key={i} style={{ background: 'var(--bg-tertiary)', borderRadius: '3px', padding: '8px 12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span className="name" style={{ maxWidth: '240px' }} title={labelStr}>{labelStr}</span>
                    <span className="muted" style={{ fontSize: '11px' }}>n={c.count ?? 0}</span>
                  </div>
                  <div style={{ display: 'flex', gap: '16px', fontSize: '11px' }}>
                    <span className="muted">Lift: <span className={`mono ${getValueColorClass(c.avgNext1d)}`}>{formatPp(c.avgNext1d)}</span></span>
                    <span className="muted">胜率: <span className={`mono ${getValueColorClass(c.winRate)}`}>{c.winRate != null ? `${(c.winRate * 100).toFixed(0)}%` : '--'}</span></span>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      ) : (
        <p className="muted text-center py-3">当前条件下无满足样本要求的组合</p>
      )}
    </div>
  );
}
