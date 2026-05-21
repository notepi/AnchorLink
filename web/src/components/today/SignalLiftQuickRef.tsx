import type { SignalLift } from '@/types/dashboard-view';

interface SignalLiftQuickRefProps {
  /** 当日激活的信号标签（来自 currentMapping.signalLabels） */
  todaySignals: string[];
  /** 全部信号 lift 数据，用来 lookup */
  allLifts: SignalLift[];
}

function fmt(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

function classify(deltaPp: number | null | undefined): { tag: string; cls: string } {
  if (deltaPp == null) return { tag: '-', cls: 'tc-tag-neu' };
  if (deltaPp > 0.5) return { tag: '机会', cls: 'tc-tag-good' };
  if (deltaPp < -0.5) return { tag: 'trap', cls: 'tc-tag-critical' };
  return { tag: '中性', cls: 'tc-tag-neu' };
}

function colorClass(v: number | null | undefined): string {
  if (v == null) return 'tc-neu';
  if (v < -0.5) return 'tc-neg';
  if (v > 0.5) return 'tc-pos';
  return 'tc-neu';
}

export default function SignalLiftQuickRef({ todaySignals, allLifts }: SignalLiftQuickRefProps) {
  if (!todaySignals || todaySignals.length === 0) return null;

  // 用 label 做 lookup
  const lookup = new Map(allLifts.map(l => [l.label, l]));
  // 加 displayLabel 备用
  allLifts.forEach(l => {
    if (l.displayLabel && !lookup.has(l.displayLabel)) lookup.set(l.displayLabel, l);
  });

  const rows = todaySignals.map(s => ({ label: s, lift: lookup.get(s) }));
  const trapCount = rows.filter(r => r.lift && (r.lift.avgNext1dDeltaPp ?? 0) < -0.5).length;
  const oppCount = rows.filter(r => r.lift && (r.lift.avgNext1dDeltaPp ?? 0) > 0.5).length;

  return (
    <section className="tc-card">
      <h2>今日 {todaySignals.length} 信号 · lift 速查</h2>
      <table className="tc-table">
        <thead>
          <tr>
            <th>信号</th>
            <th>类别</th>
            <th>T+1 lift</th>
            <th>胜率</th>
            <th>n</th>
            <th>判定</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const l = r.lift;
            const cl = classify(l?.avgNext1dDeltaPp);
            const wr = l?.winRate1d != null ? `${(l.winRate1d * 100).toFixed(0)}%` : '-';
            return (
              <tr key={i}>
                <td>{r.label}</td>
                <td className="tc-small">{l?.category ?? '-'}</td>
                <td className={colorClass(l?.avgNext1d)}>{fmt(l?.avgNext1d)}</td>
                <td>{wr}</td>
                <td>{l?.appearanceCount ?? '-'}</td>
                <td>
                  <span className={`tc-tag ${cl.cls}`}>{cl.tag}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="tc-hint">
        💡 {todaySignals.length} 个信号里 <strong>{trapCount} 个 trap</strong>、
        <strong>{oppCount} 个机会</strong>、其余中性。
        {trapCount > oppCount
          ? '今天的信号组合偏弱，没有统计上看涨的依据。'
          : oppCount > trapCount
          ? '今天信号组合偏正面，但仍要结合位置看。'
          : '今天信号组合中性，无明显方向倾向。'}
      </p>
    </section>
  );
}
