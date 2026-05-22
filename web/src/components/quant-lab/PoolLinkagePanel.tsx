import type { PoolLinkageAnalysis } from '@/types/quant-lab-view';

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}
function fmtR(v: number | null | undefined): string {
  if (v == null) return '-';
  return v.toFixed(3);
}
function cls(v: number | null | undefined): string {
  if (v == null) return 'ql-neu';
  return v > 0 ? 'ql-pos' : v < 0 ? 'ql-neg' : 'ql-neu';
}

const POOLS = ['industryChain', 'directPeers', 'themePool', 'tradingWatchlist'] as const;

export default function PoolLinkagePanel({
  data,
}: {
  data: PoolLinkageAnalysis;
}) {
  return (
    <section id="pool" className="ql-section">
      <h2>行业联动结构（N 维）<span className="ql-section-tag">SECTION 7</span></h2>

      {/* 7.1 池子分布 */}
      <h3>四池相关性分布</h3>
      <table className="ql-table">
        <thead>
          <tr>
            <th>池子</th>
            <th>全样本 r</th>
            <th>20d 均值</th>
            <th>20d 最小</th>
            <th>20d 最大</th>
            <th>P15</th>
            <th>P85</th>
            <th>60d 均值</th>
          </tr>
        </thead>
        <tbody>
          {POOLS.map((p) => {
            const s = data.poolDistribution[p];
            if (!s) return null;
            return (
              <tr key={p}>
                <td>{s.label}</td>
                <td className={cls(s.fullSampleCorr)}>{fmtR(s.fullSampleCorr)}</td>
                <td>{fmtR(s.corr20d_stats.mean)}</td>
                <td>{fmtR(s.corr20d_stats.min)}</td>
                <td>{fmtR(s.corr20d_stats.max)}</td>
                <td>{fmtR(s.corr20d_stats.p15)}</td>
                <td>{fmtR(s.corr20d_stats.p85)}</td>
                <td>{fmtR(s.corr60d_stats.mean)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="ql-hint" style={{ marginTop: 4 }}>
        💡 反直觉发现：跟「同业」相关性最弱（0.475），跟「主题情绪池」最强（0.682）。
        说明铂力特定价更受主题情绪驱动而非基本面同业。
      </div>

      {/* 7.2 脱钩信号 */}
      <h3>脱钩 vs 紧密耦合 → T+1 反应</h3>
      <table className="ql-table">
        <thead>
          <tr>
            <th>池子</th>
            <th>脱钩 n</th>
            <th>脱钩 T+1 超额</th>
            <th>脱钩胜率</th>
            <th>紧密 n</th>
            <th>紧密 T+1 超额</th>
            <th>紧密胜率</th>
          </tr>
        </thead>
        <tbody>
          {POOLS.map((p) => {
            const sig = data.decouplingSignal[p];
            if (!sig) return null;
            const dec = sig['decoupled(P15-)'];
            const cou = sig['coupled(P85+)'];
            return (
              <tr key={p}>
                <td>{sig.label}</td>
                <td>{dec.n}</td>
                <td className={cls(dec.exc1d.avg)}>{fmtPct(dec.exc1d.avg)}</td>
                <td>{(dec.exc1d.wr * 100).toFixed(0)}%</td>
                <td>{cou.n}</td>
                <td className={cls(cou.exc1d.avg)}>{fmtPct(cou.exc1d.avg)}</td>
                <td>{(cou.exc1d.wr * 100).toFixed(0)}%</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* 7.3 相关性变化 → T+1 */}
      <h3>相关性 5 日变化 → T+1 反应（最强信号区）</h3>
      <table className="ql-table">
        <thead>
          <tr>
            <th>池子</th>
            <th>状态</th>
            <th>n</th>
            <th>T+1 超额</th>
            <th>胜率</th>
          </tr>
        </thead>
        <tbody>
          {POOLS.map((p) => {
            const ll = data.correlationLeadLag[p];
            if (!ll) return null;
            const keys = Object.keys(ll.buckets);
            return keys.map((k, idx) => {
              const b = ll.buckets[k];
              const isStrong = b.next1d_exc.avg > 0.4;
              return (
                <tr key={`${p}-${k}`} className={isStrong ? 'ql-highlight' : ''}>
                  {idx === 0 ? <td rowSpan={keys.length}>{ll.label}</td> : null}
                  <td style={{ fontSize: 11 }}>{k}</td>
                  <td>{b.n}</td>
                  <td className={cls(b.next1d_exc.avg)}>{fmtPct(b.next1d_exc.avg)}</td>
                  <td>{(b.next1d_exc.wr * 100).toFixed(0)}%</td>
                </tr>
              );
            });
          })}
        </tbody>
      </table>
      <div className="ql-hint">
        🟢 <strong>「交易观察池 相关性快速上升」</strong>是最强单一信号：T+1 超额 +0.62%, 胜率 61%, n=74。
      </div>
    </section>
  );
}
