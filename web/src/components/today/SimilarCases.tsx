import type { SimilarCase } from '@/types/dashboard-view';

interface SimilarCasesProps {
  cases?: SimilarCase[];
}

function fmt(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

function colorClass(v: number | null | undefined): string {
  if (v == null) return 'tc-neu';
  if (v < -0.5) return 'tc-neg';
  if (v > 0.5) return 'tc-pos';
  return 'tc-neu';
}

export default function SimilarCases({ cases }: SimilarCasesProps) {
  if (!cases || cases.length === 0) return null;

  const validT1 = cases.filter(c => c.next1dReturn != null);
  const upCount = validT1.filter(c => (c.next1dReturn ?? 0) > 0).length;
  const upRate = validT1.length > 0 ? (upCount / validT1.length) * 100 : 0;

  return (
    <section className="tc-card">
      <h2>历史相似案例 · {cases.length} 个</h2>
      <p className="tc-disclaimer">
        ⚠️ 仅展示个案，<strong>不展示平均值</strong>（模型方向命中率 48%，平均是噪音）
      </p>
      <table className="tc-table">
        <thead>
          <tr>
            <th>日期</th>
            <th>状态</th>
            <th>相似度</th>
            <th>T+1</th>
            <th>T+3</th>
            <th>T+5</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((c, i) => (
            <tr key={i}>
              <td>{c.date}</td>
              <td className="tc-small">{c.state ?? '-'}</td>
              <td>{c.similarity.toFixed(2)}</td>
              <td>
                <span className={colorClass(c.next1dReturn)}>{fmt(c.next1dReturn)}</span>
              </td>
              <td>
                <span className={colorClass(c.next3dReturn)}>{fmt(c.next3dReturn)}</span>
              </td>
              <td>
                <span className={colorClass(c.next5dReturn)}>{fmt(c.next5dReturn)}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {validT1.length > 0 && (
        <p className="tc-hint">
          💡 {cases.length} 个相似案例里，T+1 上涨{' '}
          <strong>
            {upCount}/{validT1.length}
          </strong>{' '}
          = <strong>{upRate.toFixed(0)}%</strong>
          {upRate < 50 ? '（少于一半，偏空）' : upRate > 60 ? '（多于六成，偏多）' : '（接近半数）'}
          。但样本太小，不构成统计依据。
        </p>
      )}
    </section>
  );
}
