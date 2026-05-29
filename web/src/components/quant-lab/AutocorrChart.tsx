import type { AutocorrDecay } from '@/types/quant-lab-view';

function fmtR(v: number | null): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(3)}`;
}

function row(lag: number, val: number | null) {
  if (val == null) return null;
  const absVal = Math.abs(val);
  const width = `${Math.min(absVal * 100, 50)}%`;
  return (
    <div key={lag} className="ql-autocorr-row">
      <span className="ql-lag">lag{lag}</span>
      <div className={`ql-autocorr-bar ${val < 0 ? 'neg' : ''}`}>
        <span
          className="ql-fill"
          style={{
            width,
            ...(val < 0
              ? { right: '50%', left: 'auto', transformOrigin: 'right' }
              : {}),
          }}
        />
      </div>
      <span className={`ql-val ${val >= 0 ? 'ql-pos' : 'ql-neg'}`}>{fmtR(val)}</span>
    </div>
  );
}

export default function AutocorrChart({
  data,
}: {
  data: { excess_5d: AutocorrDecay; excess_10d: AutocorrDecay };
}) {
  const lags = [1, 5, 10, 20, 30] as const;

  return (
    <div className="ql-grid-2">
      <div>
        <h3>5d 超额自相关 <span style={{ fontWeight: 400 }}>半衰期 {data.excess_5d.half_life_days ?? '—'} 天</span></h3>
        {lags.map((lag) => row(lag, (data.excess_5d as unknown as Record<string, number | null>)[`lag${lag}`]))}
      </div>
      <div>
        <h3>10d 超额自相关 <span style={{ fontWeight: 400 }}>半衰期 {data.excess_10d.half_life_days ?? '—'} 天</span></h3>
        {lags.map((lag) => row(lag, (data.excess_10d as unknown as Record<string, number | null>)[`lag${lag}`]))}
      </div>
    </div>
  );
}
