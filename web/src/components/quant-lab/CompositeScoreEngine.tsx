'use client';

import { useState } from 'react';
import type { CompositeBacktest, ThresholdResult } from '@/types/quant-lab-view';

function fmtPct(v: number | null | undefined, decimals = 2): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(decimals)}%`;
}
function fmtWr(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${(v * 100).toFixed(1)}%`;
}
function colorClass(v: number | null | undefined): string {
  if (v == null) return 'ql-neu';
  return v > 0 ? 'ql-pos' : v < 0 ? 'ql-neg' : 'ql-neu';
}

export default function CompositeScoreEngine({
  backtest,
}: {
  backtest: CompositeBacktest;
}) {
  const [threshold, setThreshold] = useState<string>('5');
  const result: ThresholdResult = backtest.strategy_results_by_threshold[threshold];

  const long_ = result.long_days;
  const short = result.short_days;
  const bah = result.buy_and_hold;

  return (
    <section id="engine" className="ql-section">
      <h2>综合评分系统 · 阈值切换 <span className="ql-section-tag">SECTION 2</span></h2>

      <div className="ql-threshold-tabs">
        {[1, 2, 3, 4, 5].map((t) => (
          <button
            key={t}
            className={`ql-threshold-tab ${threshold === String(t) ? 'active' : ''}`}
            onClick={() => setThreshold(String(t))}
          >
            ±{t} 阈值
          </button>
        ))}
      </div>

      <div className="ql-strategy-cols">
        {/* 做多组 */}
        <div className="ql-strategy-col long">
          <h4>🟢 做多组（score ≥ +{threshold}）</h4>
          <div className="ql-stat-row">
            <span className="ql-stat-label">操作天数</span>
            <span className="ql-stat-val">{long_.n}</span>
          </div>
          <div className="ql-stat-row">
            <span className="ql-stat-label">T+1 绝对</span>
            <span className={`ql-stat-val ${colorClass(long_.avg_1d_abs)}`}>{fmtPct(long_.avg_1d_abs)}</span>
          </div>
          <div className="ql-stat-row">
            <span className="ql-stat-label">T+1 超额</span>
            <span className={`ql-stat-val ${colorClass(long_.avg_1d_exc)}`}>{fmtPct(long_.avg_1d_exc)}</span>
          </div>
          <div className="ql-stat-row">
            <span className="ql-stat-label">绝对胜率</span>
            <span className="ql-stat-val">{fmtWr(long_.win_rate_abs)}</span>
          </div>
          <div className="ql-stat-row">
            <span className="ql-stat-label">超额胜率</span>
            <span className="ql-stat-val">{fmtWr(long_.win_rate_exc)}</span>
          </div>
          <div className="ql-stat-row">
            <span className="ql-stat-label">T+3 超额</span>
            <span className={`ql-stat-val ${colorClass(long_.avg_3d_exc)}`}>{fmtPct(long_.avg_3d_exc)}</span>
          </div>
          <div className="ql-stat-row" style={{ borderTop: '1px solid var(--ql-border)', marginTop: 6, paddingTop: 6 }}>
            <span className="ql-stat-label">累计超额</span>
            <span className={`ql-stat-val ${colorClass(long_.cum_log_exc)}`} style={{ fontSize: 14, fontWeight: 700 }}>
              {fmtPct(long_.cum_log_exc)}
            </span>
          </div>
        </div>

        {/* 空仓组 */}
        <div className="ql-strategy-col short">
          <h4>🔴 空仓组（score ≤ -{threshold}）</h4>
          <div className="ql-stat-row">
            <span className="ql-stat-label">触发天数</span>
            <span className="ql-stat-val">{short.n}</span>
          </div>
          <div className="ql-stat-row">
            <span className="ql-stat-label">T+1 绝对</span>
            <span className={`ql-stat-val ${colorClass(short.avg_1d_abs)}`}>{fmtPct(short.avg_1d_abs)}</span>
          </div>
          <div className="ql-stat-row">
            <span className="ql-stat-label">T+1 超额</span>
            <span className={`ql-stat-val ${colorClass(short.avg_1d_exc)}`}>{fmtPct(short.avg_1d_exc)}</span>
          </div>
          <div className="ql-stat-row">
            <span className="ql-stat-label">跌幅胜率</span>
            <span className="ql-stat-val ql-warn">{fmtWr(short.win_rate_abs)}</span>
          </div>
          <div className="ql-stat-row">
            <span className="ql-stat-label">中性天数</span>
            <span className="ql-stat-val">{result.neutral_days.n}</span>
          </div>
          <div className="ql-stat-row">
            <span className="ql-stat-label" style={{ fontStyle: 'italic' }}>说明</span>
            <span className="ql-stat-val ql-neu" style={{ fontSize: 11 }}>
              空仓即避损
            </span>
          </div>
        </div>

        {/* Buy-and-Hold */}
        <div className="ql-strategy-col bah">
          <h4>⬜ Buy-and-Hold 基准</h4>
          <div className="ql-stat-row">
            <span className="ql-stat-label">总天数</span>
            <span className="ql-stat-val">{bah.n}</span>
          </div>
          <div className="ql-stat-row">
            <span className="ql-stat-label">T+1 绝对</span>
            <span className={`ql-stat-val ${colorClass(bah.avg_1d_abs)}`}>{fmtPct(bah.avg_1d_abs)}</span>
          </div>
          <div className="ql-stat-row">
            <span className="ql-stat-label">T+1 超额</span>
            <span className={`ql-stat-val ${colorClass(bah.avg_1d_exc)}`}>{fmtPct(bah.avg_1d_exc)}</span>
          </div>
          <div className="ql-stat-row">
            <span className="ql-stat-label">绝对胜率</span>
            <span className="ql-stat-val">{fmtWr(bah.win_rate_abs)}</span>
          </div>
          <div className="ql-stat-row">
            <span className="ql-stat-label">累计绝对</span>
            <span className={`ql-stat-val ${colorClass(bah.cum_log_abs)}`}>{fmtPct(bah.cum_log_abs)}</span>
          </div>
          <div className="ql-stat-row" style={{ borderTop: '1px solid var(--ql-border)', marginTop: 6, paddingTop: 6 }}>
            <span className="ql-stat-label">累计超额</span>
            <span className={`ql-stat-val ${colorClass(bah.cum_log_exc)}`} style={{ fontSize: 14, fontWeight: 700 }}>
              {fmtPct(bah.cum_log_exc)}
            </span>
          </div>
        </div>
      </div>

      <div className="ql-hint">
        💡 <strong>阈值越严格 → 操作越少 → 单次平均收益越高</strong>。±1 触发频繁，累计绝对收益最大；
        ±5 触发稀疏，单次精度最高（59.6% 胜率，T+1 平均 +1.42%）。
      </div>
    </section>
  );
}
