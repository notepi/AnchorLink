import React from 'react';
import type { DashboardView } from '@/types/dashboard-view';
import type { QuadrantState } from '@/types/dashboard-view';
import { BETA_LABEL, ALPHA_LABEL } from '@/lib/glossary';

interface QuadrantGridProps {
  data: DashboardView['tableData']['quadrantStats'];
  bestQuadrant: DashboardView['tableData']['conclusion']['bestQuadrant'];
  worstQuadrant: DashboardView['tableData']['conclusion']['worstQuadrant'];
}

const BETA_ORDER = ['positive', 'neutral', 'negative'] as const;
const ALPHA_ORDER = ['positive', 'neutral', 'negative'] as const;

function formatPct(v: number | null | undefined): string {
  if (v == null) return '--';
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(2)}%`;
}

export default function QuadrantGrid({ data, bestQuadrant, worstQuadrant }: QuadrantGridProps) {
  const lookup = new Map<QuadrantState, (typeof data)[number]>((data ?? []).map(q => [q.quadrant, q]));
  const bestKey = bestQuadrant?.quadrant;
  const worstKey = worstQuadrant?.quadrant;

  return (
    <div className="list-card">
      <h3>九宫格统计</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'auto repeat(3, 1fr)', gap: '1px', background: 'var(--border)', borderRadius: '4px', overflow: 'hidden' }}>
        <div style={{ background: 'var(--bg-tertiary)', padding: '8px' }} />
        {ALPHA_ORDER.map(alpha => (
          <div key={alpha} style={{ background: 'var(--bg-tertiary)', padding: '6px 8px', textAlign: 'center', fontSize: '11px', color: 'var(--text-secondary)' }}>
            {ALPHA_LABEL[alpha]}
          </div>
        ))}
        {BETA_ORDER.map(beta => (
          <React.Fragment key={beta}>
            <div style={{ background: 'var(--bg-tertiary)', padding: '6px 8px', fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center' }}>
              {BETA_LABEL[beta]}
            </div>
            {ALPHA_ORDER.map(alpha => {
              const key = `${beta}+${alpha}` as QuadrantState;
              const stat = lookup.get(key);
              const isEmpty = !stat || stat.count === 0;
              const isBest = key === bestKey;
              const isWorst = key === worstKey;

              let bg = 'var(--bg-secondary)';
              if (isBest) bg = 'rgba(255,77,79,0.1)';
              else if (isWorst) bg = 'rgba(34,197,94,0.1)';

              const avgReturn = stat?.avgNext1d;
              const winRate = stat?.winRate1d;

              return (
                <div key={key} style={{ background: bg, padding: '8px', opacity: isEmpty ? 0.4 : 1 }}>
                  <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '4px' }}>
                    {stat?.count ?? 0} 天
                    {isBest && <span style={{ color: '#ff4d4f', marginLeft: '4px' }}>最佳</span>}
                    {isWorst && <span style={{ color: '#20d477', marginLeft: '4px' }}>最差</span>}
                  </div>
                  <div className={`mono ${avgReturn != null ? (avgReturn > 0 ? 'red' : avgReturn < 0 ? 'green' : '') : 'muted'}`} style={{ fontSize: '13px' }}>
                    {formatPct(avgReturn)}
                  </div>
                  <div className="muted mono" style={{ fontSize: '11px' }}>
                    胜率 {winRate != null ? `${(winRate * 100).toFixed(0)}%` : '--'}
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
