import type { TodayAttribution } from '@/types/dashboard-view';

interface AttributionCardProps {
  attribution?: TodayAttribution | null;
}

function colorClass(v: number | null | undefined): string {
  if (v == null) return 'tc-neu';
  if (v < -0.5) return 'tc-neg';
  if (v > 0.5) return 'tc-pos';
  return 'tc-neu';
}

function fmt(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

const POOLS: Array<{ key: keyof TodayAttribution['pools']; label: string }> = [
  { key: 'directPeers', label: 'direct_peers（华曙、超卓）' },
  { key: 'industryChain', label: 'industry_chain（主线 11 只）' },
  { key: 'themePool', label: 'theme_pool（商业航天主题）' },
  { key: 'tradingWatchlist', label: 'trading_watchlist（高 beta）' },
];

export default function AttributionCard({ attribution }: AttributionCardProps) {
  if (!attribution) return null;
  const ar = attribution.anchorReturn;
  const arClass = colorClass(ar);

  // 哪个池子和 anchor 同向（最可能是"带涨/带跌"来源）
  const sameDirectionPools = POOLS.filter(p => {
    const v = attribution.pools[p.key];
    return v != null && Math.sign(v) === Math.sign(ar);
  });
  const verdict =
    sameDirectionPools.length === 0
      ? '4 池都未同向，铂力特今天完全独立'
      : sameDirectionPools.length === 1
      ? `仅有 ${sameDirectionPools[0].label.split('（')[0]} 与铂力特同向，是主要带动池`
      : `${sameDirectionPools.length} 个池子同向，行业整体在动`;

  return (
    <section className="tc-card">
      <h2>今日归因 · 谁带的</h2>
      <div className="tc-big-number">
        铂力特 <span className={arClass}>{fmt(ar)}</span>
      </div>
      <div className="tc-pool-bars">
        {POOLS.map(p => {
          const v = attribution.pools[p.key];
          const cls = colorClass(v);
          const barClass = v != null && v > 0 ? 'tc-pos' : 'tc-neg';
          const width = v != null ? Math.min(Math.abs(v) * 10, 100) : 0;
          return (
            <div key={p.key} className="tc-pool-row">
              <span className="tc-pool-name">{p.label}</span>
              <span className={`tc-pool-val ${cls}`}>{fmt(v)}</span>
              <div className="tc-bar">
                <div className={`tc-bar-fill ${barClass}`} style={{ width: `${width}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      <div className="tc-alpha-box">
        <div className="tc-alpha-row">
          <span className="tc-label">Alpha vs industry_chain（主线）</span>
          <span className={`tc-val ${colorClass(attribution.alphaVsIndustryChain)}`}>
            {fmt(attribution.alphaVsIndustryChain)}
          </span>
        </div>
        <div className="tc-alpha-row">
          <span className="tc-label">Alpha vs direct_peers（同业）</span>
          <span className={`tc-val ${colorClass(attribution.alphaVsDirectPeers)}`}>
            {fmt(attribution.alphaVsDirectPeers)}
          </span>
        </div>
      </div>
      <p className="tc-verdict">
        📌 <strong>事实</strong>：{verdict}。
        {attribution.alphaVsDirectPeers != null && (
          <>
            真正的"个股独立"溢价（Alpha vs 同业） <strong>{fmt(attribution.alphaVsDirectPeers)}</strong>。
          </>
        )}
      </p>
    </section>
  );
}
