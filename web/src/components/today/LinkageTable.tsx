import type { PoolCorrelations } from '@/types/dashboard-view';

interface LinkageTableProps {
  latestCorr?: PoolCorrelations;
}

const POOL_LABELS: Array<{ key: keyof Omit<PoolCorrelations, 'date'>; label: string; sub: string }> = [
  { key: 'industryChain', label: '主线池', sub: 'industry_chain' },
  { key: 'directPeers', label: '同业', sub: 'direct_peers' },
  { key: 'themePool', label: '主题池', sub: 'theme_pool' },
  { key: 'tradingWatchlist', label: '高 beta 池', sub: 'trading_watchlist' },
];

function fmtCorr(v: number | null | undefined): string {
  if (v == null) return '-';
  return v.toFixed(2);
}

function stateTag(pct: number | null | undefined, corr60d: number | null | undefined) {
  if (pct == null) return { cls: 'tc-tag-neu', text: '-' };
  if (pct <= 10) return { cls: 'tc-tag-critical', text: '脱钩' };
  if (pct <= 25) return { cls: 'tc-tag-warn', text: '偏低' };
  if (corr60d != null && corr60d >= 0.6) return { cls: 'tc-tag-good', text: '紧密' };
  return { cls: 'tc-tag-neu', text: '正常' };
}

export default function LinkageTable({ latestCorr }: LinkageTableProps) {
  if (!latestCorr) return null;

  // 统计脱钩池数量
  const decoupled = POOL_LABELS.filter(p => {
    const v = latestCorr[p.key];
    return v && v.percentile20d != null && v.percentile20d <= 10;
  });
  const tightWithDirect = latestCorr.directPeers?.corr60d != null && latestCorr.directPeers.corr60d >= 0.6;

  return (
    <section className="tc-card">
      <h2>联动状态 · 跟谁绑、跟谁脱</h2>
      <table className="tc-table">
        <thead>
          <tr>
            <th>池子</th>
            <th>20d 相关性</th>
            <th>历史百分位</th>
            <th>60d 相关性</th>
            <th>全样本</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {POOL_LABELS.map(p => {
            const data = latestCorr[p.key];
            if (!data) return null;
            const st = stateTag(data.percentile20d, data.corr60d);
            return (
              <tr key={p.key}>
                <td>
                  {p.label}
                  <br />
                  <span className="tc-small">{p.sub}</span>
                </td>
                <td className="tc-val">{fmtCorr(data.corr20d)}</td>
                <td className="tc-val">P{data.percentile20d ?? '-'}</td>
                <td className="tc-val">{fmtCorr(data.corr60d)}</td>
                <td className="tc-val tc-small">{fmtCorr(data.fullCorr)}</td>
                <td>
                  <span className={`tc-tag ${st.cls}`}>{st.text}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {decoupled.length >= 2 && (
        <p className="tc-hint">
          💡 <strong>{decoupled.length} 个池齐脱钩</strong>：
          {decoupled.map(p => p.label).join(' / ')} 的 20d 相关性都在 P10 以下，
          是近 242 天里最极端的脱钩状态之一。
          {tightWithDirect && '只有同业（direct_peers）还在保持联系。'}
        </p>
      )}
    </section>
  );
}
