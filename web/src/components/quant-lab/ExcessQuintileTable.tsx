import type { ExtremeReversal } from '@/types/quant-lab-view';

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

export default function ExcessQuintileTable({
  data,
  title,
}: {
  data: ExtremeReversal;
  title: string;
}) {
  const ordered = ['P15-(过冷)', 'P15-P30', 'P30-P70(中性)', 'P70-P85', 'P85+(过热)'];
  return (
    <div>
      <h3>{title}</h3>
      <table className="ql-table">
        <thead>
          <tr>
            <th>档位</th>
            <th>n</th>
            <th>T+1 绝对</th>
            <th>T+1 超额</th>
            <th>T+3 超额</th>
            <th>T+5 超额</th>
            <th>胜率</th>
          </tr>
        </thead>
        <tbody>
          {ordered.map((label) => {
            const b = data.buckets[label];
            if (!b) return null;
            const isHotOrCold = label === 'P85+(过热)' || label === 'P15-(过冷)';
            const isWinning = b.exc_1d.avg > 0.5;
            const isLosing = b.exc_1d.avg < -0.4;
            return (
              <tr
                key={label}
                className={
                  isHotOrCold && isWinning
                    ? 'ql-highlight'
                    : isHotOrCold && isLosing
                    ? 'ql-highlight-neg'
                    : ''
                }
              >
                <td>{label}</td>
                <td>{b.n}</td>
                <td className={cls(b.abs_1d.avg)}>{fmtPct(b.abs_1d.avg)}</td>
                <td className={cls(b.exc_1d.avg)}>{fmtPct(b.exc_1d.avg)}</td>
                <td className={cls(b.exc_3d.avg)}>{fmtPct(b.exc_3d.avg)}</td>
                <td className={cls(b.exc_5d.avg)}>{fmtPct(b.exc_5d.avg)}</td>
                <td>{fmtWr(b.abs_1d.wr)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="ql-hint" style={{ marginTop: 6 }}>
        阈值：P15={data.thresholds.p15.toFixed(2)}%, P30={data.thresholds.p30.toFixed(2)}%,
        P70={data.thresholds.p70.toFixed(2)}%, P85={data.thresholds.p85.toFixed(2)}%
      </div>
    </div>
  );
}
