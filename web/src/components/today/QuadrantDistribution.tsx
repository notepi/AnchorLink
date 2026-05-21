import type { QuadrantStat, QuadrantState } from '@/types/dashboard-view';

interface QuadrantDistributionProps {
  quadrants: QuadrantStat[];
  currentQuadrant?: QuadrantState | string;
}

function fmt(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

export default function QuadrantDistribution({ quadrants, currentQuadrant }: QuadrantDistributionProps) {
  // 按胜率降序
  const sorted = [...quadrants].sort((a, b) => (b.winRate1d ?? 0) - (a.winRate1d ?? 0));

  return (
    <section className="tc-card">
      <h2>9 象限 T+1 分布 · 看分布不看均值</h2>
      <p className="tc-disclaimer">P10/P50/P90 是 T+1 收益的<strong>分位数</strong>：80% 历史样本落在 P10~P90 之间</p>
      <table className="tc-table">
        <thead>
          <tr>
            <th>象限</th>
            <th>n</th>
            <th>P10 最差 10%</th>
            <th>P50 中位</th>
            <th>P90 最好 10%</th>
            <th>胜率</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(q => {
            const isCurrent = q.quadrant === currentQuadrant;
            const wr = q.winRate1d != null ? q.winRate1d * 100 : null;
            const wrCls =
              wr == null
                ? 'tc-tag-neu'
                : wr >= 55
                ? 'tc-tag-good'
                : wr >= 45
                ? 'tc-tag-neu'
                : wr >= 40
                ? 'tc-tag-warn'
                : 'tc-tag-bad';
            return (
              <tr key={q.quadrant} className={isCurrent ? 'tc-current-row' : ''}>
                <td>
                  {q.quadrantName}
                  {isCurrent && ' ← 今天'}
                </td>
                <td>{q.count}</td>
                <td className="tc-val tc-neg">{fmt(q.t1P10)}</td>
                <td className="tc-val">{fmt(q.t1P50)}</td>
                <td className="tc-val tc-pos">{fmt(q.t1P90)}</td>
                <td>
                  <span className={`tc-tag ${wrCls}`}>{wr != null ? `${wr.toFixed(0)}%` : '-'}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
