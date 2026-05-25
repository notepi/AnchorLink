'use client';

// 来自 analysis_framework.md 6.3 节
const HONESTY_ITEMS = [
  { issue: 'OOS 仅 127 天', fact: '统计结论需更长时间验证', impact: '可能过拟合' },
  { issue: '无严格统计显著性', fact: 'Bootstrap CI 大多跨零', impact: '不能说"确认有效"' },
  { issue: '夏普 6.58', fact: '31 个交易日算出来的', impact: '实际会更低' },
  { issue: 'Monte Carlo P=97.4%', fact: '还有 2.6% 可能是噪音', impact: '不是 100%' },
  { issue: '日历效应仅 1 年', fact: '8 月/4 月效应需 2-3 年验证', impact: '可能是年度特例' },
];

export function StatisticalHonesty() {
  return (
    <div className="v2-card">
      <div className="v2-card-title">统计诚实度</div>
      <div className="v2-honesty">
        所有结论基于 247 天数据，方向一致但统计力度不足。随数据积累，部分信号可能被证伪。
      </div>
      <table className="v2-table">
        <thead>
          <tr><th>问题</th><th>事实</th><th>影响</th></tr>
        </thead>
        <tbody>
          {HONESTY_ITEMS.map(h => (
            <tr key={h.issue}>
              <td>{h.issue}</td>
              <td>{h.fact}</td>
              <td style={{ color: '#92400e' }}>{h.impact}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
