import type { DashboardView } from '@/types/dashboard-view';
import { formatPp, getValueColorClass } from '@/lib/history-v2/formatters';

interface DivergenceTimelineProps {
  data: DashboardView['tableData']['extremeDivergences'];
}

function formatDate(date: string) {
  if (!date || date.length !== 8) return date;
  return `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`;
}

export default function DivergenceTimeline({ data }: DivergenceTimelineProps) {
  const sorted = [...(data ?? [])].sort((a, b) => String(b.date).localeCompare(String(a.date)));

  return (
    <div className="list-card">
      <h3>极端背离事件 <span className="muted">({sorted.length})</span></h3>
      {sorted.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {sorted.map(d => {
            const isPositive = (d.divergence ?? 0) > 0;
            return (
              <div key={d.date} style={{ background: 'var(--bg-tertiary)', borderRadius: '3px', padding: '8px 12px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '8px', height: '8px', borderRadius: '50%', flexShrink: 0,
                  background: isPositive ? '#ff4d4f' : '#20d477',
                }} />
                <span className="mono muted" style={{ fontSize: '12px' }}>{formatDate(d.date)}</span>
                <span className={`mono ${getValueColorClass(d.divergence)}`} style={{ fontWeight: 600 }}>
                  {formatPp(d.divergence)}
                </span>
                <span className="muted" style={{ fontSize: '11px' }}>背离</span>
                <div style={{ display: 'flex', gap: '12px', fontSize: '11px' }}>
                  {d.t1Return != null && (
                    <span className="muted">T+1: <span className={`mono ${getValueColorClass(d.t1Return)}`}>{formatPp(d.t1Return)}</span></span>
                  )}
                  {d.t3Return != null && (
                    <span className="muted">T+3: <span className={`mono ${getValueColorClass(d.t3Return)}`}>{formatPp(d.t3Return)}</span></span>
                  )}
                </div>
                <div style={{ marginLeft: 'auto', fontSize: '11px' }} className="muted">
                  个股 {formatPp(d.anchorReturn)} · {formatPp(d.industryChainMedian)}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="muted text-center py-3">暂无极端背离事件</p>
      )}
    </div>
  );
}
