'use client';

import type { V2SignalBreakdown } from '@/types/v2-scoring';

interface SignalBreakdownProps {
  breakdown: V2SignalBreakdown[];
}

export function SignalBreakdown({ breakdown }: SignalBreakdownProps) {
  if (!breakdown.length) {
    return (
      <div className="v2-card">
        <div className="v2-card-title">信号分解</div>
        <div style={{ fontSize: 13, color: '#9ca3af' }}>无触发信号</div>
      </div>
    );
  }

  return (
    <div className="v2-card">
      <div className="v2-card-title">信号分解</div>
      <ul className="v2-signal-list">
        {breakdown.map((s, i) => {
          const weightClass = s.adjustedWeight > 0 ? 'v2-signal-weight--pos' : 'v2-signal-weight--neg';
          const catClass = s.category === 'v2_new' ? 'v2-signal-cat--v2' : 'v2-signal-cat--v1';
          const catLabel = s.category === 'v2_new' ? 'V2' : 'V1';
          return (
            <li key={i} className="v2-signal-item">
              <span className="v2-signal-name">{s.signal}</span>
              <span className={`v2-signal-weight ${weightClass}`}>
                {s.adjustedWeight > 0 ? '+' : ''}{s.adjustedWeight}
              </span>
              {s.rawWeight !== s.adjustedWeight && (
                <span style={{ fontSize: 11, color: '#9ca3af', marginRight: 4 }}>
                  (原{s.rawWeight > 0 ? '+' : ''}{s.rawWeight})
                </span>
              )}
              <span className={`v2-signal-cat ${catClass}`}>{catLabel}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
