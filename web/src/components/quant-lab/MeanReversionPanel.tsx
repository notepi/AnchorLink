import type { MeanReversionAnalysis } from '@/types/quant-lab-view';
import AutocorrChart from './AutocorrChart';
import ExcessQuintileTable from './ExcessQuintileTable';
import DeltaReversalChart from './DeltaReversalChart';

export default function MeanReversionPanel({
  data,
}: {
  data: MeanReversionAnalysis;
}) {
  const ds5 = data.distributionStats.excess_5d;
  const ds10 = data.distributionStats.excess_10d;

  return (
    <section id="mean-reversion" className="ql-section">
      <h2>均值回归量化（M 维）<span className="ql-section-tag">SECTION 4</span></h2>

      {/* 4.0 分布检验 */}
      <h3>均值假设检验：「产业链就是均值」</h3>
      <table className="ql-table" style={{ marginBottom: 14 }}>
        <thead>
          <tr>
            <th>指标</th>
            <th>n</th>
            <th>均值</th>
            <th>标准差</th>
            <th>t 统计</th>
            <th>结论</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>excess_5d</td>
            <td>{ds5.n}</td>
            <td className="ql-neu">{ds5.mean >= 0 ? '+' : ''}{ds5.mean.toFixed(3)}%</td>
            <td>{ds5.std.toFixed(3)}%</td>
            <td>{ds5.t_stat.toFixed(2)} <span style={{ color: 'var(--ql-text-muted)', fontSize: 10 }}>(名义)</span></td>
            <td className="ql-neu">修正后不显著 *</td>
          </tr>
          <tr>
            <td>excess_10d</td>
            <td>{ds10.n}</td>
            <td className="ql-neu">{ds10.mean >= 0 ? '+' : ''}{ds10.mean.toFixed(3)}%</td>
            <td>{ds10.std.toFixed(3)}%</td>
            <td>{ds10.t_stat.toFixed(2)} <span style={{ color: 'var(--ql-text-muted)', fontSize: 10 }}>(名义)</span></td>
            <td className="ql-neu">修正后不显著 *</td>
          </tr>
        </tbody>
      </table>

      <div className="ql-hint" style={{ marginBottom: 14 }}>
        ⚠️ * <strong>名义 t 值高估了显著性。</strong>excess_5d / excess_10d 是滚动窗口，
        相邻两天共享 4–9 天数据，lag-1 自相关高达 0.74–0.85，把它们当独立样本会严重低估标准误。
        按重叠折算有效样本（≈ n / 窗口长度）后，真实 t 值降到约 0.8，<strong>两者都不显著</strong>。
        即"产业链就是均值 / 均值回归有效"这一结论，统计上并不成立。
      </div>

      {/* 4.1 自相关 */}
      <AutocorrChart data={data.autocorrelationDecay} />

      {/* 4.2 极端档反转 */}
      <ExcessQuintileTable data={data.extremeReversal.by_excess_5d} title="5d 超额分档 → 后续多周期反应" />
      <ExcessQuintileTable data={data.extremeReversal.by_excess_10d} title="10d 超额分档 → 后续多周期反应" />

      {/* 4.3 Δ 反转 */}
      <DeltaReversalChart data={data.deltaMomentum} />
    </section>
  );
}
