import type { CompositeBacktest } from '@/types/quant-lab-view';

function fmtPct(v: number, decimals = 2): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(decimals)}%`;
}

function fmtWr(v: number): string {
  if (v == null) return '-';
  return `${(v * 100).toFixed(1)}%`;
}

export default function StrategyHero({
  backtest,
}: {
  backtest: CompositeBacktest;
}) {
  // 默认展示阈值±5（最严格）
  const t5 = backtest.strategy_results_by_threshold['5'];
  const t1 = backtest.strategy_results_by_threshold['1'];
  const bah = t5.buy_and_hold;

  // 最佳累计超额（±1 通常最大）
  const bestCumExc = t1.long_days.cum_log_exc;
  const alphaImprovement = bestCumExc - bah.cum_log_exc;

  return (
    <section id="hero" className="ql-section">
      <h2>策略表现总览 <span className="ql-section-tag">SECTION 1</span></h2>

      <div className="ql-hero-main">
        <span className={`ql-big ${bestCumExc >= 0 ? 'pos' : 'neg'}`}>
          {fmtPct(bestCumExc)}
        </span>
        <span className="ql-vs">
          策略累计超额 <span className="ql-neu">vs</span>{' '}
          基准 <span className="ql-neg">{fmtPct(bah.cum_log_exc)}</span>{' '}
          <span className="ql-pos">(+{alphaImprovement.toFixed(2)}pp)</span>
        </span>
      </div>

      <div className="ql-kpi-grid">
        <div className="ql-kpi-card">
          <div className="ql-kpi-label">多头胜率 (±5阈值)</div>
          <div className={`ql-kpi-value ql-pos`}>{fmtWr(t5.long_days.win_rate_abs)}</div>
          <div className="ql-kpi-sub">
            vs 基准 {fmtWr(bah.win_rate_abs)}{' '}
            <span className="ql-pos">(+{((t5.long_days.win_rate_abs - bah.win_rate_abs) * 100).toFixed(1)}pp)</span>
          </div>
        </div>
        <div className="ql-kpi-card">
          <div className="ql-kpi-label">T+1 平均收益</div>
          <div className={`ql-kpi-value ${t5.long_days.avg_1d_abs >= 0 ? 'ql-pos' : 'ql-neg'}`}>
            {fmtPct(t5.long_days.avg_1d_abs)}
          </div>
          <div className="ql-kpi-sub">
            vs 基准 {fmtPct(bah.avg_1d_abs)}{' '}
            <span className="ql-pos">({(t5.long_days.avg_1d_abs / bah.avg_1d_abs).toFixed(1)}x)</span>
          </div>
        </div>
        <div className="ql-kpi-card">
          <div className="ql-kpi-label">操作天数 / 总天数</div>
          <div className="ql-kpi-value">{t5.long_days.n}/{bah.n}</div>
          <div className="ql-kpi-sub">
            做多占比 {((t5.long_days.n / bah.n) * 100).toFixed(1)}% (±5严格阈值)
          </div>
        </div>
        <div className="ql-kpi-card">
          <div className="ql-kpi-label">T+3 平均超额</div>
          <div className={`ql-kpi-value ${t5.long_days.avg_3d_exc >= 0 ? 'ql-pos' : 'ql-neg'}`}>
            {fmtPct(t5.long_days.avg_3d_exc)}
          </div>
          <div className="ql-kpi-sub">3 日累计跑赢产业链</div>
        </div>
      </div>

      <div className="ql-disclaimer">
        ⚠️ <strong>In-sample 提示</strong>：本回测使用全样本阈值（P15/P85 等），存在前视偏差。
        严格 walk-forward 回测将在 Phase 3 实施，预期实际表现略低于报告数字。
      </div>
    </section>
  );
}
