import type { RollingMetric } from '@/types/dashboard-view';

interface ExcessCardsProps {
  /** 完整 excessReturn 时间序列，按 selectedDate 查找 */
  excessReturn: RollingMetric[];
  /** 当前选中日期 YYYYMMDD */
  selectedDate?: string;
  /** 今日偏离（来自 attribution.alphaVsIndustryChain） */
  todayDeviation?: number | null;
}

function fmt(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

function colorClass(v: number | null | undefined): string {
  if (v == null) return 'tc-neu';
  if (v < -0.5) return 'tc-neg';
  if (v > 0.5) return 'tc-pos';
  return 'tc-neu';
}

function PctBar({ percentile }: { percentile: number | null | undefined }) {
  if (percentile == null) return null;
  return (
    <div className="tc-pct-bar">
      <div className="tc-pct-marker" style={{ left: `${percentile}%` }} />
    </div>
  );
}

function tag(pct: number | null | undefined): string | null {
  if (pct == null) return null;
  if (pct >= 90) return '过热';
  if (pct >= 85) return '接近过热';
  if (pct <= 10) return '偏冷';
  return null;
}

export default function ExcessCards({ excessReturn, selectedDate, todayDeviation }: ExcessCardsProps) {
  if (!excessReturn || excessReturn.length === 0) return null;

  // 按 selectedDate 查找，找不到就用最新一条
  const entry = selectedDate
    ? (excessReturn.find(e => e.date === selectedDate) ?? excessReturn[excessReturn.length - 1])
    : excessReturn[excessReturn.length - 1];

  if (!entry) return null;

  const e5 = entry.excess5d;
  const e10 = entry.excess10d;
  const e5pct = entry.excess5dPercentile;
  const e10pct = entry.excess10dPercentile;
  const e5tag = tag(e5pct);
  const e10tag = tag(e10pct);

  const cellClass = (pct: number | null | undefined) =>
    pct != null && pct >= 85 ? 'tc-tag tc-tag-warn' : 'tc-tag tc-tag-neu';

  return (
    <section className="tc-card">
      <h2>三超额 · 历史位置</h2>
      <div className="tc-excess-grid">
        <div className="tc-excess-cell">
          <div className="tc-excess-title">5d 超额</div>
          <div className={`tc-excess-value ${colorClass(e5)}`}>{fmt(e5)}</div>
          <div className="tc-excess-percentile">
            历史 P{e5pct ?? '-'}{' '}
            {e5tag && <span className={cellClass(e5pct)}>{e5tag}</span>}
          </div>
          <PctBar percentile={e5pct} />
        </div>
        <div className="tc-excess-cell">
          <div className="tc-excess-title">10d 超额</div>
          <div className={`tc-excess-value ${colorClass(e10)}`}>{fmt(e10)}</div>
          <div className="tc-excess-percentile">
            历史 P{e10pct ?? '-'}{' '}
            {e10tag && <span className={cellClass(e10pct)}>{e10tag}</span>}
          </div>
          <PctBar percentile={e10pct} />
        </div>
        <div className="tc-excess-cell">
          <div className="tc-excess-title">今日偏离</div>
          <div className={`tc-excess-value ${colorClass(todayDeviation)}`}>{fmt(todayDeviation)}</div>
          <div className="tc-excess-percentile">单日跑赢产业链</div>
        </div>
      </div>
      {e5 != null && e10 != null && Math.abs(e5 - e10) < 1.5 && Math.abs(e5) > 4 && (
        <p className="tc-hint">
          💡 <strong>5d 和 10d 相近</strong>：近期超额集中在最近 5 天爆发，前段时间基本没动。
        </p>
      )}
    </section>
  );
}
