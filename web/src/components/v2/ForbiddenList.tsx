'use client';

// 来自 analysis_framework.md 5.4 节
const FORBIDDEN = [
  { action: '追涨（MACD 金叉、Stoch 金叉、创新高买入）', reason: '均值回归股追涨必亏' },
  { action: '周五做多', reason: '36.7%胜率，周末避险效应' },
  { action: '看跌 FVG 后继续持有', reason: '信号 T+2 就失效' },
  { action: 'TS 环境下低阈值做多', reason: '50%胜率，噪音太多' },
  { action: '相信 kNN 相似度预测', reason: '48.5%命中率，不如随机' },
];

export function ForbiddenList() {
  return (
    <div className="v2-card">
      <div className="v2-card-title">禁忌清单</div>
      <div className="v2-warning">
        铂力特是均值回归股，所有"看起来强"的信号都是减仓信号。
      </div>
      <table className="v2-table">
        <thead>
          <tr><th>禁忌操作</th><th>原因</th></tr>
        </thead>
        <tbody>
          {FORBIDDEN.map(f => (
            <tr key={f.action}>
              <td style={{ color: '#dc2626' }}>{f.action}</td>
              <td>{f.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
