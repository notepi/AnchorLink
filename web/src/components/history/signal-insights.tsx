import type { SignalInsight } from '@/types';

interface SignalInsightsProps {
  highValueSignals: SignalInsight[];
  lowValueSignals: SignalInsight[];
}

function deltaPpColor(value: number): string {
  if (value > 0) return 'text-anchor-positive';
  if (value < 0) return 'text-anchor-negative';
  return 'text-anchor-text';
}

function InsightSection({ signals, type }: { signals: SignalInsight[]; type: 'high' | 'low' }) {
  const title = type === 'high' ? '高价值信号' : '需谨慎的信号';
  const titleColor = type === 'high' ? 'text-anchor-positive' : 'text-anchor-negative';
  const borderColor = type === 'high' ? 'border-l-2 border-anchor-positive' : 'border-l-2 border-anchor-negative';

  if (signals.length === 0) {
    return (
      <div className={`bg-anchor-bgSecondary rounded-sm border border-anchor-border p-4 ${borderColor}`}>
        <h3 className={`text-xs font-medium ${titleColor} mb-2`}>{title}</h3>
        <p className="text-xs text-anchor-textMuted">暂无</p>
      </div>
    );
  }

  return (
    <div className={`bg-anchor-bgSecondary rounded-sm border border-anchor-border p-4 ${borderColor}`}>
      <h3 className={`text-xs font-medium ${titleColor} mb-3`}>
        {title} ({signals.length}个)
      </h3>
      <ul className="space-y-1.5">
        {signals.map((s) => (
          <li key={s.label} className="flex items-center justify-between gap-3 text-xs">
            <span className="text-anchor-text truncate" title={s.label}>{s.label}</span>
            <div className="flex items-center gap-3 shrink-0">
              <span className={`font-mono ${deltaPpColor(s.deltaPp)}`}>
                {s.deltaPp >= 0 ? '+' : ''}{s.deltaPp.toFixed(2)}pp
              </span>
              <span className={`font-mono ${s.winRate >= 0.5 ? 'text-anchor-positive' : 'text-anchor-negative'}`}>
                {(s.winRate * 100).toFixed(0)}%
              </span>
              <span className="text-anchor-textMuted">样本{s.count}</span>
              <span className="text-anchor-textMuted w-10 text-right" title="稳定性评分">
                {s.stabilityScore}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SignalInsights({ highValueSignals, lowValueSignals }: SignalInsightsProps) {
  return (
    <div>
      <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-3">
        信号洞察
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <InsightSection signals={highValueSignals} type="high" />
        <InsightSection signals={lowValueSignals} type="low" />
      </div>
    </div>
  );
}
