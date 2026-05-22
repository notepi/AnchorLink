'use client';

import { useMemo, useState } from 'react';
import type { AlphaSignalRow } from '@/types/quant-lab-view';

function typeColor(t: string): string {
  if (t.includes('纯Alpha')) return '#10b981';
  if (t.includes('隐藏Alpha')) return '#06b6d4';
  if (t.includes('负向')) return '#ef4444';
  return '#6b7280';
}
function typeLabel(t: string): string {
  if (t.includes('纯Alpha')) return '🟢 纯Alpha';
  if (t.includes('隐藏Alpha')) return '💡 隐藏Alpha';
  if (t.includes('负向')) return '🔴 负向';
  return '⬜ 中性';
}
function fmtPct(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

interface Props {
  signals: AlphaSignalRow[];
}

interface Tip {
  x: number; y: number;
  signal: string; n: number;
  absLift: number; excLift: number;
  avgAbs1d: number; avgExc1d: number;
  wr1d: number; wrExc1d: number;
  signalType: string;
}

export default function SignalAlphaScatter({ signals }: Props) {
  const [tip, setTip] = useState<Tip | null>(null);

  const W = 560;
  const H = 420;
  const PAD = { top: 30, right: 30, bottom: 40, left: 50 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  // 计算坐标范围
  const xMax = Math.max(...signals.map((s) => Math.abs(s.absLift)));
  const yMax = Math.max(...signals.map((s) => Math.abs(s.excLift)));
  const xRange = Math.ceil(Math.max(xMax, yMax, 1.5) * 10) / 10 + 0.3;
  const yRange = xRange;

  const xScale = (v: number) => PAD.left + ((v + xRange) / (xRange * 2)) * plotW;
  const yScale = (v: number) => PAD.top + plotH - ((v + yRange) / (yRange * 2)) * plotH;

  // 大小比例尺
  const maxN = Math.max(...signals.map((s) => s.n));
  const rScale = (n: number) => 4 + (n / maxN) * 10;

  // Top 10 / Bottom 5 排行
  const ranked = useMemo(() => [...signals].sort((a, b) => b.excLift - a.excLift), [signals]);

  return (
    <section id="alpha-scatter" className="ql-section">
      <h2>信号 Alpha/Beta 散点图（K 维）<span className="ql-section-tag">SECTION 5</span></h2>

      <div className="ql-scatter-wrap">
        <div>
          <svg className="ql-scatter-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
            {/* 四象限背景着色 */}
            <rect x={PAD.left} y={PAD.top} width={plotW / 2} height={plotH / 2} fill="rgba(6, 182, 212, 0.05)" />
            <rect x={PAD.left + plotW / 2} y={PAD.top} width={plotW / 2} height={plotH / 2} fill="rgba(16, 185, 129, 0.05)" />
            <rect x={PAD.left} y={PAD.top + plotH / 2} width={plotW / 2} height={plotH / 2} fill="rgba(239, 68, 68, 0.05)" />
            <rect x={PAD.left + plotW / 2} y={PAD.top + plotH / 2} width={plotW / 2} height={plotH / 2} fill="rgba(245, 158, 11, 0.05)" />

            {/* 0 轴 */}
            <line x1={PAD.left} x2={W - PAD.right} y1={yScale(0)} y2={yScale(0)} stroke="#4b5563" strokeWidth="0.5" />
            <line x1={xScale(0)} x2={xScale(0)} y1={PAD.top} y2={H - PAD.bottom} stroke="#4b5563" strokeWidth="0.5" />

            {/* 网格刻度 */}
            {[-1, -0.5, 0.5, 1].map((v) => (
              <g key={v}>
                <line x1={xScale(v)} x2={xScale(v)} y1={PAD.top} y2={H - PAD.bottom} stroke="#1f2937" strokeWidth="0.3" />
                <line x1={PAD.left} x2={W - PAD.right} y1={yScale(v)} y2={yScale(v)} stroke="#1f2937" strokeWidth="0.3" />
                <text x={xScale(v)} y={H - PAD.bottom + 12} fill="#6b7280" fontSize="9" textAnchor="middle" fontFamily="ui-monospace, monospace">
                  {v > 0 ? '+' : ''}{v}
                </text>
                <text x={PAD.left - 6} y={yScale(v) + 3} fill="#6b7280" fontSize="9" textAnchor="end" fontFamily="ui-monospace, monospace">
                  {v > 0 ? '+' : ''}{v}
                </text>
              </g>
            ))}

            {/* 轴标签 */}
            <text x={W / 2} y={H - 6} fill="#9ca3af" fontSize="11" textAnchor="middle">
              绝对 lift (vs 基线)
            </text>
            <text
              x={-H / 2}
              y={14}
              fill="#9ca3af"
              fontSize="11"
              textAnchor="middle"
              transform="rotate(-90)"
            >
              超额 lift (vs 产业链)
            </text>

            {/* 象限标签 */}
            <text x={xScale(-xRange * 0.6)} y={yScale(yRange * 0.85)} fill="#06b6d4" fontSize="10" fontWeight="600">💡 隐藏Alpha</text>
            <text x={xScale(xRange * 0.4)} y={yScale(yRange * 0.85)} fill="#10b981" fontSize="10" fontWeight="600">🟢 纯Alpha</text>
            <text x={xScale(-xRange * 0.6)} y={yScale(-yRange * 0.85)} fill="#ef4444" fontSize="10" fontWeight="600">🔴 负向</text>
            <text x={xScale(xRange * 0.4)} y={yScale(-yRange * 0.85)} fill="#f59e0b" fontSize="10" fontWeight="600">⚠️ Beta骑乘</text>

            {/* 数据点 */}
            {signals.map((s) => (
              <circle
                key={s.signal}
                cx={xScale(s.absLift)}
                cy={yScale(s.excLift)}
                r={rScale(s.n)}
                fill={typeColor(s.signalType)}
                fillOpacity="0.65"
                stroke={typeColor(s.signalType)}
                strokeWidth="1"
                style={{ cursor: 'pointer' }}
                onMouseEnter={(e) =>
                  setTip({
                    x: e.clientX + 10,
                    y: e.clientY + 10,
                    signal: s.signal,
                    n: s.n,
                    absLift: s.absLift,
                    excLift: s.excLift,
                    avgAbs1d: s.avgAbs1d,
                    avgExc1d: s.avgExc1d,
                    wr1d: s.wr1d,
                    wrExc1d: s.wrExc1d,
                    signalType: s.signalType,
                  })
                }
                onMouseLeave={() => setTip(null)}
              />
            ))}
          </svg>
          <div className="ql-scatter-legend">
            <span><span className="ql-dot" style={{ background: '#10b981' }} /> 纯 Alpha</span>
            <span><span className="ql-dot" style={{ background: '#06b6d4' }} /> 隐藏 Alpha</span>
            <span><span className="ql-dot" style={{ background: '#f59e0b' }} /> Beta 骑乘</span>
            <span><span className="ql-dot" style={{ background: '#ef4444' }} /> 负向</span>
            <span><span className="ql-dot" style={{ background: '#6b7280' }} /> 中性</span>
            <span style={{ marginLeft: 'auto', color: 'var(--ql-text-muted)' }}>圆圈大小 = 样本量 n</span>
          </div>
        </div>

        {/* Top/Bottom 排行 */}
        <div>
          <h3>Top 8 by 超额 lift</h3>
          <table className="ql-table" style={{ fontSize: 11 }}>
            <thead>
              <tr><th>信号</th><th>n</th><th>超额 lift</th><th>类型</th></tr>
            </thead>
            <tbody>
              {ranked.slice(0, 8).map((s) => (
                <tr key={s.signal}>
                  <td style={{ fontSize: 11 }}>{s.signal}</td>
                  <td>{s.n}</td>
                  <td className="ql-pos">{fmtPct(s.excLift)}</td>
                  <td style={{ fontSize: 10 }}>{typeLabel(s.signalType)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h3 style={{ marginTop: 16 }}>Bottom 5 (负向信号)</h3>
          <table className="ql-table" style={{ fontSize: 11 }}>
            <thead>
              <tr><th>信号</th><th>n</th><th>超额 lift</th><th>类型</th></tr>
            </thead>
            <tbody>
              {ranked.slice(-5).reverse().map((s) => (
                <tr key={s.signal}>
                  <td style={{ fontSize: 11 }}>{s.signal}</td>
                  <td>{s.n}</td>
                  <td className="ql-neg">{fmtPct(s.excLift)}</td>
                  <td style={{ fontSize: 10 }}>{typeLabel(s.signalType)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {tip && (
        <div className="ql-tooltip" style={{ left: tip.x, top: tip.y }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>{tip.signal}</div>
          <div style={{ color: typeColor(tip.signalType), fontSize: 11, marginBottom: 4 }}>
            {typeLabel(tip.signalType)}
          </div>
          <div>样本量 n = {tip.n}</div>
          <div>绝对 lift: <strong>{fmtPct(tip.absLift)}</strong></div>
          <div>超额 lift: <strong>{fmtPct(tip.excLift)}</strong></div>
          <div style={{ marginTop: 4, paddingTop: 4, borderTop: '1px solid #2a3441' }}>
            T+1 绝对均值: {fmtPct(tip.avgAbs1d)}
          </div>
          <div>T+1 超额均值: {fmtPct(tip.avgExc1d)}</div>
          <div>绝对胜率: {(tip.wr1d * 100).toFixed(0)}% / 超额胜率: {(tip.wrExc1d * 100).toFixed(0)}%</div>
        </div>
      )}

      <div className="ql-hint">
        🎯 散点图把 31 个信号按「绝对 lift × 超额 lift」分到四象限：
        右上 = 真信号，左上 = Beta 环境掩盖的隐藏 Alpha，右下 = 看似涨实则跑输的 Beta 骑乘陷阱，左下 = 全面负向。
      </div>
    </section>
  );
}
