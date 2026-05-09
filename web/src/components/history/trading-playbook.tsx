'use client';

import type { TradingPlaybook } from '@/types';
import { cn } from '@/lib/utils';

interface TradingPlaybookProps {
  playbook: TradingPlaybook;
}

// 倾向视觉映射
const stanceVisual = {
  active_watch: {
    label: '积极观察',
    color: 'text-anchor-positive',
    bg: 'bg-anchor-positive/10',
    border: 'border-l-2 border-l-anchor-positive',
    icon: '▲',
  },
  cautious_watch: {
    label: '谨慎观察',
    color: 'text-anchor-accent',
    bg: 'bg-anchor-accent/10',
    border: 'border-l-2 border-l-anchor-accent',
    icon: '◆',
  },
  wait: {
    label: '观望',
    color: 'text-anchor-textMuted',
    bg: 'bg-anchor-bgTertiary',
    border: 'border-l-2 border-l-anchor-border',
    icon: '○',
  },
};

// 置信度映射
const confidenceVisual = {
  high: { label: '高置信度', color: 'text-anchor-positive' },
  medium: { label: '中等置信度', color: 'text-anchor-accent' },
  low: { label: '低置信度', color: 'text-anchor-negative' },
};

export function TradingPlaybookCard({ playbook }: TradingPlaybookProps) {
  const visual = stanceVisual[playbook.stance];

  return (
    <div
      className={cn(
        'bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border',
        visual.border
      )}
    >
      {/* 头部：倾向 + 置信度 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className={cn('text-lg', visual.color)}>{visual.icon}</span>
          <div>
            <h2 className={cn('text-sm font-medium', visual.color)}>
              {visual.label}
            </h2>
            <span className={cn('text-xs', confidenceVisual[playbook.confidence].color)}>
              {confidenceVisual[playbook.confidence].label} · {playbook.sampleNote}
            </span>
          </div>
        </div>
      </div>

      {/* 核心结论 */}
      <p className="text-sm text-anchor-text mb-4 leading-relaxed">
        {playbook.summary}
      </p>

      {/* 证据：最多 2 条 */}
      {playbook.evidence.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-medium text-anchor-textSecondary mb-2">
            判断依据
          </div>
          <ul className="space-y-1">
            {playbook.evidence.slice(0, 2).map((e, i) => (
              <li
                key={i}
                className="text-xs text-anchor-textSecondary flex items-start gap-2"
              >
                <span className="text-anchor-positive">✓</span>
                {e}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-anchor-border pt-4">
        {/* 触发条件 */}
        <div>
          <div className="text-xs font-medium text-anchor-textSecondary mb-2">
            触发条件
          </div>
          {playbook.triggers.length > 0 ? (
            <ul className="space-y-1">
              {playbook.triggers.map((t, i) => (
                <li
                  key={i}
                  className="text-xs text-anchor-text flex items-start gap-2"
                >
                  <span className="text-anchor-accent">{i + 1}.</span>
                  {t}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-anchor-textMuted">暂无明确触发条件</p>
          )}
        </div>

        {/* 反证条件 */}
        <div>
          <div className="text-xs font-medium text-anchor-textSecondary mb-2">
            反证条件
          </div>
          {playbook.invalidations.length > 0 ? (
            <ul className="space-y-1">
              {playbook.invalidations.map((inv, i) => (
                <li
                  key={i}
                  className="text-xs text-anchor-text flex items-start gap-2"
                >
                  <span className="text-anchor-negative">×</span>
                  {inv}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-anchor-textMuted">暂无明确反证条件</p>
          )}
        </div>
      </div>
    </div>
  );
}
