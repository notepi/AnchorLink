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

  return (
    <section id="hero" className="ql-section">
      <h2>历史信号复盘（样本内）<span className="ql-section-tag">SECTION 1</span></h2>

      <div className="ql-hero-main">
        <span className={`ql-big ${bestCumExc >= 0 ? 'pos' : 'neg'}`}>
          {fmtPct(bestCumExc)}
        </span>
        <span className="ql-vs">
          信号日事后累计超额（样本内复盘）
          <span className="ql-neu" style={{ display: 'block', fontSize: 11, marginTop: 2 }}>
            ⚠️ 口径不对等：此数字只累加被信号选中的做多日，
            全样本持有累计超额仅 {fmtPct(bah.cum_log_exc)}，两者部署天数不同，不可直接比"跑赢"
          </span>
        </span>
      </div>

      <div className="ql-kpi-grid">
        <div className="ql-kpi-card">
          <div className="ql-kpi-label">多头胜率 (±5阈值)</div>
          <div className={`ql-kpi-value ql-neu`}>{fmtWr(t5.long_days.win_rate_abs)}</div>
          <div className="ql-kpi-sub">
            n={t5.long_days.n}（样本太小，95% 置信区间约 [45%, 73%]，与抛硬币无法区分）
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
        ⚠️ <strong>这不是已验证的策略，是样本内复盘</strong>：信号集、阈值（P15/P85 等）、权重
        都是在同一段 ~243 天上挑出来又在同段数据回测的（"开卷考"），数字必然好看，
        <strong>不代表未来表现</strong>。
        本页 ML 面板用的 walk-forward（样本外/"闭卷"）已经跑过——方向命中率仅 48–53%（50% = 抛硬币），
        说明同一份数据换成诚实方法后优势基本消失。
        <strong>请把本页当作复盘 / 盘感工具，不要据此预测或下单。</strong>
      </div>
    </section>
  );
}
