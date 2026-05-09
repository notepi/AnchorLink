import type { OperatorHistoryView } from '@/types';

interface OperatorDecisionPanelProps {
  view: OperatorHistoryView;
}

const confidenceLabel = {
  high: '高',
  medium: '中',
  low: '低',
};

const statusLabel = {
  stable: '稳定',
  weakening: '近期转弱',
  invalid: '失效/样本不足',
};

const stanceLabel = {
  active_watch: '积极观察',
  cautious_watch: '谨慎观察',
  wait: '等待',
};

function toneClass(tone: 'good' | 'warn' | 'bad') {
  if (tone === 'good') return 'text-anchor-positive border-anchor-positive/40 bg-anchor-positive/10';
  if (tone === 'bad') return 'text-anchor-negative border-anchor-negative/40 bg-anchor-negative/10';
  return 'text-anchor-warning border-anchor-warning/40 bg-anchor-warning/10';
}

export function OperatorDecisionPanel({ view }: OperatorDecisionPanelProps) {
  const tone = view.regime.status === 'stable'
    ? 'good'
    : view.regime.status === 'invalid'
      ? 'bad'
      : 'warn';

  return (
    <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="bg-anchor-bgSecondary rounded-sm border border-anchor-border p-4">
        <div className="text-xs text-anchor-textMuted mb-2">历史规律可信度</div>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-2xl font-semibold text-anchor-text">
            {confidenceLabel[view.regime.confidence]}
          </span>
          <span className={`text-xs border rounded px-2 py-0.5 ${toneClass(tone)}`}>
            {statusLabel[view.regime.status]}
          </span>
        </div>
        <p className="text-xs text-anchor-textSecondary leading-relaxed">{view.regime.headline}</p>
      </div>

      <div className="bg-anchor-bgSecondary rounded-sm border border-anchor-border p-4">
        <div className="text-xs text-anchor-textMuted mb-2">当前操作倾向</div>
        <div className="text-2xl font-semibold text-anchor-text mb-2">
          {stanceLabel[view.playbook.stance]}
        </div>
        <p className="text-xs text-anchor-textSecondary leading-relaxed">{view.playbook.headline}</p>
      </div>

      <div className="bg-anchor-bgSecondary rounded-sm border border-anchor-border p-4">
        <div className="text-xs text-anchor-textMuted mb-2">主要失效点</div>
        {view.regime.risk_points.length > 0 ? (
          <ul className="space-y-1.5">
            {view.regime.risk_points.slice(0, 3).map((point) => (
              <li key={point} className="text-xs text-anchor-textSecondary flex gap-2">
                <span className="text-anchor-warning">!</span>
                <span>{point}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-anchor-textSecondary">暂无主要失效点</p>
        )}
      </div>
    </section>
  );
}
