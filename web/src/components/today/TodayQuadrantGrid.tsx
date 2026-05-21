import type { QuadrantStat, QuadrantState } from '@/types/dashboard-view';

interface TodayQuadrantGridProps {
  quadrants: QuadrantStat[];
  currentQuadrant?: QuadrantState | string;
}

// 3×3 显示顺序
const ORDER: QuadrantState[] = [
  'positive+positive', 'positive+neutral', 'positive+negative',
  'neutral+positive',  'neutral+neutral',  'neutral+negative',
  'negative+positive', 'negative+neutral', 'negative+negative',
];

function fmt(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

export default function TodayQuadrantGrid({ quadrants, currentQuadrant }: TodayQuadrantGridProps) {
  const lookup = new Map(quadrants.map(q => [q.quadrant, q]));

  return (
    <section className="tc-card">
      <h2>当前象限 · 9 格定位</h2>
      <div className="tc-quad-grid">
        {ORDER.map(key => {
          const q = lookup.get(key);
          const isCurrent = key === currentQuadrant;
          if (!q) {
            return (
              <div key={key} className="tc-quad-cell tc-quad-neu">
                <div className="tc-quad-name">{key}</div>
                <div className="tc-small">无数据</div>
              </div>
            );
          }
          const tier = q.guidance?.tier ?? 'neu';
          const cls = `tc-quad-cell tc-quad-${tier}${isCurrent ? ' tc-current' : ''}`;
          const wr = q.winRate1d != null ? (q.winRate1d * 100).toFixed(0) : '-';
          return (
            <div key={key} className={cls}>
              {isCurrent && <div className="tc-current-marker">← 今天</div>}
              <div className="tc-quad-header">
                <span className="tc-quad-name">{q.quadrantName}</span>
                {q.guidance && (
                  <span className={`tc-quad-tier-tag tc-tier-${q.guidance.tier}`}>
                    {q.guidance.icon} {q.guidance.label}
                  </span>
                )}
              </div>
              <div className="tc-quad-metrics">
                <span>
                  胜率 <strong>{wr}%</strong>
                </span>
                <span className="tc-muted"> · </span>
                <span>
                  P50 <strong>{fmt(q.t1P50)}</strong>
                </span>
                <span className="tc-muted"> · </span>
                <span className="tc-muted">n={q.count}</span>
              </div>
              <div className="tc-quad-action">
                <strong>{q.guidance?.action ?? '-'}</strong>：{q.reason ?? ''}
              </div>
            </div>
          );
        })}
      </div>
      <p className="tc-hint">
        💡 每格含义：<strong>🟢 好买点</strong>（胜率≥55%）·{' '}
        <strong>⚪ 中性</strong>（45-55%）· <strong>⚠️ 偏弱</strong>（40-45%）·{' '}
        <strong>🔴 回避</strong>（&lt;40%）。
        <br />
        <strong>关键观察</strong>：最高胜率的格子往往是「个股弱」组合——铂力特是均值回归型，
        <strong>真正的买点不在「个股强」格里，而在跌下来之后</strong>。
      </p>
    </section>
  );
}
