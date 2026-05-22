'use client';

import { useMemo, useState } from 'react';
import type { DailyResult } from '@/types/quant-lab-view';

interface Props {
  daily: DailyResult[];
  /** 用哪个阈值的策略（默认 ±3，中等严格） */
  defaultThreshold?: number;
}

interface TooltipState {
  x: number;
  y: number;
  date: string;
  score: number;
  signalsCount: number;
  next_1d: number | null;
  next_1d_exc: number | null;
  strategy_cum: number;
  bah_cum: number;
}

function fmtPct(v: number | null | undefined, decimals = 2): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(decimals)}%`;
}

export default function StrategyCurve({ daily, defaultThreshold = 3 }: Props) {
  const [threshold, setThreshold] = useState(defaultThreshold);
  const [tip, setTip] = useState<TooltipState | null>(null);

  // 计算累计对数收益曲线
  const points = useMemo(() => {
    let cumStrategy = 0;
    let cumBah = 0;
    return daily
      .filter((d) => d.next_1d_excess != null)
      .map((d) => {
        const exc = d.next_1d_excess ?? 0;
        // 策略：score >= threshold 时做多
        if (!d.veto && d.score >= threshold) {
          cumStrategy += Math.log(1 + exc / 100);
        }
        // BAH：每天都持有
        cumBah += Math.log(1 + exc / 100);
        return {
          date: d.date,
          score: d.score,
          signals: d.signals,
          next_1d: d.next_1d_return,
          next_1d_exc: d.next_1d_excess,
          strategy_cum: (Math.exp(cumStrategy) - 1) * 100,
          bah_cum: (Math.exp(cumBah) - 1) * 100,
          active: !d.veto && d.score >= threshold,
        };
      });
  }, [daily, threshold]);

  // SVG 尺寸（响应式由 viewBox 负责）
  const W = 900;
  const H = 280;
  const PAD = { top: 20, right: 20, bottom: 30, left: 50 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  // 计算 y 轴范围
  const allY = points.flatMap((p) => [p.strategy_cum, p.bah_cum]);
  const yMin = Math.min(...allY, -10);
  const yMax = Math.max(...allY, 10);
  const yRange = yMax - yMin;

  // 坐标转换
  const xScale = (i: number) => PAD.left + (i / Math.max(1, points.length - 1)) * plotW;
  const yScale = (v: number) => PAD.top + plotH - ((v - yMin) / yRange) * plotH;

  // 生成路径
  const pathStrategy = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i).toFixed(1)} ${yScale(p.strategy_cum).toFixed(1)}`)
    .join(' ');
  const pathBah = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i).toFixed(1)} ${yScale(p.bah_cum).toFixed(1)}`)
    .join(' ');

  // 极端信号日标记
  const extremeBuy = points.filter((p) => p.score >= 12);
  const extremeSell = points.filter((p) => p.score <= -12);

  // Y 轴刻度
  const yTicks = useMemo(() => {
    const step = Math.ceil(yRange / 5 / 10) * 10;
    const ticks: number[] = [];
    let v = Math.ceil(yMin / step) * step;
    while (v <= yMax) {
      ticks.push(v);
      v += step;
    }
    return ticks;
  }, [yMin, yMax, yRange]);

  return (
    <section id="curve" className="ql-section">
      <h2>累计超额收益曲线 <span className="ql-section-tag">SECTION 3</span></h2>

      <div className="ql-threshold-tabs">
        <span style={{ fontSize: 11, color: 'var(--ql-text-muted)', marginRight: 8, alignSelf: 'center' }}>
          策略阈值：
        </span>
        {[1, 2, 3, 4, 5].map((t) => (
          <button
            key={t}
            className={`ql-threshold-tab ${threshold === t ? 'active' : ''}`}
            onClick={() => setThreshold(t)}
          >
            ±{t}
          </button>
        ))}
      </div>

      <svg className="ql-curve-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
        {/* Y 网格 */}
        {yTicks.map((v) => (
          <g key={v}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={yScale(v)}
              y2={yScale(v)}
              stroke="#2a3441"
              strokeWidth="0.5"
            />
            <text
              x={PAD.left - 6}
              y={yScale(v) + 3}
              fill="#6b7280"
              fontSize="9"
              textAnchor="end"
              fontFamily="ui-monospace, monospace"
            >
              {v >= 0 ? '+' : ''}{v}%
            </text>
          </g>
        ))}
        {/* 0 线 */}
        <line
          x1={PAD.left}
          x2={W - PAD.right}
          y1={yScale(0)}
          y2={yScale(0)}
          stroke="#4b5563"
          strokeDasharray="3 3"
          strokeWidth="0.5"
        />

        {/* BAH 曲线 */}
        <path d={pathBah} fill="none" stroke="#9ca3af" strokeWidth="1.5" />
        {/* 策略曲线 */}
        <path d={pathStrategy} fill="none" stroke="#10b981" strokeWidth="2" />

        {/* 极端买入日（绿点） */}
        {extremeBuy.map((p) => {
          const i = points.indexOf(p);
          return (
            <circle
              key={`b-${p.date}`}
              cx={xScale(i)}
              cy={yScale(p.strategy_cum)}
              r="3"
              fill="#10b981"
              stroke="#fff"
              strokeWidth="0.5"
            />
          );
        })}
        {/* 极端卖出日（红点） */}
        {extremeSell.map((p) => {
          const i = points.indexOf(p);
          return (
            <circle
              key={`s-${p.date}`}
              cx={xScale(i)}
              cy={yScale(p.bah_cum)}
              r="3"
              fill="#ef4444"
              stroke="#fff"
              strokeWidth="0.5"
            />
          );
        })}

        {/* 悬浮命中区 */}
        {points.map((p, i) => (
          <rect
            key={`hover-${p.date}`}
            x={xScale(i) - plotW / points.length / 2}
            y={PAD.top}
            width={plotW / points.length}
            height={plotH}
            fill="transparent"
            onMouseEnter={(e) =>
              setTip({
                x: e.clientX + 10,
                y: e.clientY + 10,
                date: p.date,
                score: p.score,
                signalsCount: p.signals.length,
                next_1d: p.next_1d,
                next_1d_exc: p.next_1d_exc,
                strategy_cum: p.strategy_cum,
                bah_cum: p.bah_cum,
              })
            }
            onMouseLeave={() => setTip(null)}
          />
        ))}

        {/* X 轴标签（每月一个） */}
        {points
          .map((p, i) => ({ p, i }))
          .filter((_, idx) => idx % 22 === 0)
          .map(({ p, i }) => (
            <text
              key={`x-${p.date}`}
              x={xScale(i)}
              y={H - 10}
              fill="#6b7280"
              fontSize="9"
              textAnchor="middle"
              fontFamily="ui-monospace, monospace"
            >
              {p.date.slice(2, 4)}/{p.date.slice(4, 6)}
            </text>
          ))}
      </svg>

      <div className="ql-curve-legend">
        <span><span className="ql-swatch" style={{ background: '#10b981' }} /> 策略累计 (±{threshold})</span>
        <span><span className="ql-swatch" style={{ background: '#9ca3af' }} /> Buy-and-Hold 累计</span>
        <span><span className="ql-swatch" style={{ background: '#10b981', borderRadius: '50%', width: 8, height: 8 }} /> score ≥ +12</span>
        <span><span className="ql-swatch" style={{ background: '#ef4444', borderRadius: '50%', width: 8, height: 8 }} /> score ≤ -12</span>
      </div>

      {tip && (
        <div className="ql-tooltip" style={{ left: tip.x, top: tip.y }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>{tip.date}</div>
          <div>综合分: <strong style={{ color: tip.score >= 0 ? '#10b981' : '#ef4444' }}>{tip.score >= 0 ? '+' : ''}{tip.score}</strong></div>
          <div>激活信号: {tip.signalsCount}</div>
          <div>实际 T+1: {fmtPct(tip.next_1d)} (超额 {fmtPct(tip.next_1d_exc)})</div>
          <div style={{ marginTop: 4, paddingTop: 4, borderTop: '1px solid #2a3441' }}>
            策略累计: <strong style={{ color: '#10b981' }}>{fmtPct(tip.strategy_cum)}</strong>
          </div>
          <div>BAH 累计: <span style={{ color: '#9ca3af' }}>{fmtPct(tip.bah_cum)}</span></div>
        </div>
      )}

      <div className="ql-hint">
        ⚙️ 策略仅在 score ≥ +{threshold}（非 veto）当日做多，持有 1 天获取 T+1 超额收益；其他日子空仓。
      </div>
    </section>
  );
}
