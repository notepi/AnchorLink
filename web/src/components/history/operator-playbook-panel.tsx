import type { OperatorHistoryView } from '@/types';

interface OperatorPlaybookPanelProps {
  view: OperatorHistoryView;
}

function Column({ title, items, tone }: { title: string; items: string[]; tone?: 'good' | 'bad' }) {
  const marker = tone === 'good' ? 'text-anchor-positive' : tone === 'bad' ? 'text-anchor-negative' : 'text-anchor-accent';
  return (
    <div>
      <div className="text-xs font-medium text-anchor-textSecondary mb-2">{title}</div>
      <ul className="space-y-1.5">
        {items.length > 0 ? items.map((item) => (
          <li key={item} className="text-xs text-anchor-text flex gap-2 leading-relaxed">
            <span className={marker}>•</span>
            <span>{item}</span>
          </li>
        )) : (
          <li className="text-xs text-anchor-textMuted">暂无</li>
        )}
      </ul>
    </div>
  );
}

export function OperatorPlaybookPanel({ view }: OperatorPlaybookPanelProps) {
  return (
    <section className="bg-anchor-bgSecondary rounded-sm border border-anchor-border p-4">
      <div className="flex items-baseline justify-between mb-4">
        <div>
          <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
            交易观察建议
          </h2>
          <p className="text-xs text-anchor-textMuted mt-1">{view.playbook.headline}</p>
        </div>
        <span className="text-xs text-anchor-textMuted">{view.playbook.sample_note}</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Column title="看什么" items={view.playbook.watch_for} tone="good" />
        <Column title="用什么确认" items={view.playbook.confirmations} />
        <Column title="什么会失效" items={view.playbook.invalidations} tone="bad" />
        <div>
          <div className="text-xs font-medium text-anchor-textSecondary mb-2">样本约束</div>
          <p className="text-xs text-anchor-text leading-relaxed">{view.playbook.sample_note}</p>
          <p className="text-xs text-anchor-textMuted mt-2">
            组合样本不足不进入主建议，完整明细放在折叠区。
          </p>
        </div>
      </div>
    </section>
  );
}
