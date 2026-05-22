import type { SignalWeights } from '@/types/quant-lab-view';

export default function SignalWeightTable({
  weights,
}: {
  weights: SignalWeights;
}) {
  const buy = Object.entries(weights.buy).sort((a, b) => b[1] - a[1]);
  const sell = Object.entries(weights.sell).sort((a, b) => a[1] - b[1]);

  return (
    <section id="weights" className="ql-section">
      <h2>信号权重表（综合评分构成）<span className="ql-section-tag">SECTION 9</span></h2>

      <details className="ql-collapsible" open>
        <summary>展开查看 17 个信号 + 权重 + 来源维度</summary>
        <div className="ql-weight-grid" style={{ marginTop: 10 }}>
          <div>
            <h3>🟢 买入信号</h3>
            <table className="ql-table">
              <thead>
                <tr><th>信号</th><th>权重</th></tr>
              </thead>
              <tbody>
                {buy.map(([name, w]) => (
                  <tr key={name}>
                    <td style={{ fontSize: 11 }}>{name}</td>
                    <td className="ql-pos" style={{ fontWeight: 700 }}>+{w}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <h3>🔴 卖出/减仓信号</h3>
            <table className="ql-table">
              <thead>
                <tr><th>信号</th><th>权重</th></tr>
              </thead>
              <tbody>
                {sell.map(([name, w]) => (
                  <tr key={name}>
                    <td style={{ fontSize: 11 }}>{name}</td>
                    <td className="ql-neg" style={{ fontWeight: 700 }}>{w}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="ql-hint" style={{ marginTop: 10 }}>
          ⚙️ 综合评分 = Σ(信号激活 × 权重)。
          「放量大涨」同时是「-3 卖出信号」+「一票否决」（直接 SKIP 当日做多）。
          阈值 ±5 时只在最强信号叠加日才操作，胜率 59.6%。
        </div>
      </details>
    </section>
  );
}
