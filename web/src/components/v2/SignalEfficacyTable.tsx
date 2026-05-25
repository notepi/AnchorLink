'use client';

interface SignalEfficacyTableProps {
  strategyResults: Record<string, any>;
}

// 硬编码验证数据来自 analysis_framework.md 3.1/3.2 节
const BUY_SIGNALS = [
  { name: 'MR + streak≤-3', source: 'S×J', n: 9, exc: '+3.11%', wr: '77.8%', rating: '★★★' },
  { name: 'MR + streak≤-2', source: 'S×J', n: 20, exc: '+1.91%', wr: '65.0%', rating: '★★★' },
  { name: 'excess_5d P15-', source: 'M', n: 37, exc: '+1.80%', wr: '59.5%', rating: '★★' },
  { name: 'TS + streak≤-2', source: 'S×J', n: 21, exc: '+0.75%', wr: '66.7%', rating: '★★' },
  { name: '跌但资金支撑', source: 'H', n: '—', exc: '—', wr: '63%', rating: '★★' },
  { name: 'MACD 柱负', source: 'R', n: 95, exc: '+0.32%', wr: '54.7%', rating: '★' },
];

const SELL_SIGNALS = [
  { name: 'TS + streak≥+2', source: 'S×J', n: 12, exc: '-0.97%', wr: '25.0%', rating: '★★★' },
  { name: '周五 + ADX<25', source: 'U×R', n: 24, exc: '-1.51%', wr: '33.3%', rating: '★★★' },
  { name: 'RSI 超买(>70)', source: 'R', n: 17, exc: '-1.67%', wr: '35.3%', rating: '★★' },
  { name: 'BB 上轨触及', source: 'R', n: 19, exc: '-1.26%', wr: '36.8%', rating: '★★' },
  { name: '看跌 FVG', source: 'T', n: 22, exc: '-1.65%', wr: '31.8%', rating: '★★' },
  { name: '周五效应', source: 'U', n: 49, exc: '-0.81%', wr: '36.7%', rating: '★★' },
  { name: '放量大涨', source: 'H', n: '—', exc: '-0.79%', wr: '38%', rating: '★★' },
];

export function SignalEfficacyTable(_props: SignalEfficacyTableProps) {
  return (
    <div className="v2-card">
      <div className="v2-card-title">买入信号效力</div>
      <table className="v2-table">
        <thead>
          <tr>
            <th>信号</th><th>来源</th><th>n</th><th>T+1超额</th><th>胜率</th><th>评级</th>
          </tr>
        </thead>
        <tbody>
          {BUY_SIGNALS.map(s => (
            <tr key={s.name}>
              <td>{s.name}</td>
              <td>{s.source}</td>
              <td>{s.n}</td>
              <td style={{ color: '#dc2626' }}>{s.exc}</td>
              <td>{s.wr}</td>
              <td>{s.rating}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="v2-card-title" style={{ marginTop: 16 }}>卖出/回避信号效力</div>
      <table className="v2-table">
        <thead>
          <tr>
            <th>信号</th><th>来源</th><th>n</th><th>T+1超额</th><th>胜率</th><th>评级</th>
          </tr>
        </thead>
        <tbody>
          {SELL_SIGNALS.map(s => (
            <tr key={s.name}>
              <td>{s.name}</td>
              <td>{s.source}</td>
              <td>{s.n}</td>
              <td style={{ color: '#16a34a' }}>{s.exc}</td>
              <td>{s.wr}</td>
              <td>{s.rating}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
