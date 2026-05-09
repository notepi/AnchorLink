import type { OperatorConfirmationPair } from '@/types';

interface OperatorCombinationSummaryProps {
  pairs: OperatorConfirmationPair[];
}

export function OperatorCombinationSummary({ pairs }: OperatorCombinationSummaryProps) {
  return (
    <section className="bg-anchor-bgSecondary rounded-sm border border-anchor-border p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
            组合确认
          </h2>
          <p className="text-xs text-anchor-textMuted mt-1">只展示比单信号更有解释力的组合。</p>
        </div>
        <button className="text-xs text-anchor-accent hover:text-anchor-accent/80">
          查看组合明细
        </button>
      </div>
      {pairs.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {pairs.slice(0, 3).map((pair) => (
            <div key={pair.labels.join('+')} className="bg-anchor-bgTertiary border border-anchor-border rounded-sm p-3">
              <div className="text-xs text-anchor-text mb-2 truncate" title={pair.display_labels.join(' + ')}>
                {pair.display_labels.join(' + ')}
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-anchor-textMuted">协同增量</span>
                <span className="font-mono text-anchor-positive">+{pair.synergy.toFixed(2)}pp</span>
              </div>
              <div className="flex items-center justify-between text-xs mt-1">
                <span className="text-anchor-textMuted">样本</span>
                <span className="font-mono text-anchor-textSecondary">{pair.count}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-anchor-bgTertiary border border-anchor-border rounded-sm p-4 text-xs text-anchor-textSecondary">
          当前没有比单信号更有解释力的组合
        </div>
      )}
    </section>
  );
}
