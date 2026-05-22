import type { DeltaMomentum } from '@/types/quant-lab-view';

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}
function fmtWr(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${(v * 100).toFixed(0)}%`;
}
function cls(v: number | null | undefined): string {
  if (v == null) return 'ql-neu';
  return v > 0 ? 'ql-pos' : v < 0 ? 'ql-neg' : 'ql-neu';
}

export default function DeltaReversalChart({ data }: { data: DeltaMomentum }) {
  return (
    <div>
      <h3>5d 超额变化率 Δ 五分位 → T+1 反应</h3>
      <table className="ql-table">
        <thead>
          <tr>
            <th>档位</th>
            <th>Δ 区间</th>
            <th>n</th>
            <th>T+1 绝对</th>
            <th>T+1 超额</th>
            <th>胜率</th>
          </tr>
        </thead>
        <tbody>
          {data.quintiles.map((q) => {
            // 第 2 档（温和回调）和第 5 档（最快上升）是关键
            const isReversal = q.quintile === 2 && q.exc1d.avg > 0.5;
            const isTrap = q.quintile === 5 && q.exc1d.avg < -0.5;
            return (
              <tr
                key={q.quintile}
                className={isReversal ? 'ql-highlight' : isTrap ? 'ql-highlight-neg' : ''}
              >
                <td>{q.label}</td>
                <td style={{ fontSize: 11, color: 'var(--ql-text-muted)' }}>
                  [{q.deltaRange[0].toFixed(2)}, {q.deltaRange[1].toFixed(2)}]
                </td>
                <td>{q.n}</td>
                <td className={cls(q.abs1d.avg)}>{fmtPct(q.abs1d.avg)}</td>
                <td className={cls(q.exc1d.avg)}>{fmtPct(q.exc1d.avg)}</td>
                <td>{fmtWr(q.exc1d.wr)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="ql-hint" style={{ marginTop: 6 }}>
        Pearson r (Δ vs T+1 绝对): <strong>{data.pearsonR_abs?.toFixed(4) ?? '-'}</strong>;
        (Δ vs T+1 超额): <strong>{data.pearsonR_exc?.toFixed(4) ?? '-'}</strong>。
        💡 <strong>温和回调档（Δ ∈ [-3, -1]）</strong>是最佳入场点（胜率 60%），不是最快下跌档。
      </div>
    </div>
  );
}
