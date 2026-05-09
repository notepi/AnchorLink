'use client';

import type { DecisionSummary } from '@/types';
import { cn } from '@/lib/utils';

interface DecisionSummaryProps {
  summary: DecisionSummary;
  sampleDays: number;
}

// 可信度视觉映射
const confidenceVisual = {
  high: {
    color: 'text-anchor-positive',
    bg: 'bg-anchor-positive/10',
    label: '高',
  },
  medium: {
    color: 'text-anchor-accent',
    bg: 'bg-anchor-accent/10',
    label: '中',
  },
  low: {
    color: 'text-anchor-negative',
    bg: 'bg-anchor-negative/10',
    label: '低',
  },
};

// 操作倾向视觉映射
const stanceVisual = {
  active_watch: {
    label: '积极观察',
    color: 'text-anchor-positive',
    icon: '▲',
  },
  cautious_watch: {
    label: '谨慎观察',
    color: 'text-anchor-accent',
    icon: '◆',
  },
  wait: {
    label: '观望',
    color: 'text-anchor-textMuted',
    icon: '○',
  },
};

export function DecisionSummaryCard({ summary, sampleDays }: DecisionSummaryProps) {
  return (
    <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
      {/* 头部：可信度 + 倾向 并排 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className={confidenceVisual[summary.confidence].color}>
            可信度：{confidenceVisual[summary.confidence].label}
          </span>
          <span className={stanceVisual[summary.stance].color}>
            {stanceVisual[summary.stance].icon} {stanceVisual[summary.stance].label}
          </span>
        </div>
        {/* 样本天数提示 */}
        <span className="text-xs text-anchor-textMuted">样本 {sampleDays} 天</span>
      </div>

      {/* 主标题：一句话结论 */}
      <h2 className="text-sm font-medium text-anchor-text mb-3">{summary.headline}</h2>

      {/* 判断理由：最多 2 条 */}
      {summary.reasons.length > 0 && (
        <div className="mb-3">
          <ul className="space-y-1">
            {summary.reasons.slice(0, 2).map((r, i) => (
              <li
                key={i}
                className="text-xs text-anchor-textSecondary flex items-start gap-2"
              >
                <span className="text-anchor-accent">•</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 风险点：最多 3 条，可展开 */}
      {summary.riskPoints.length > 0 && (
        <div className="border-t border-anchor-border pt-3">
          <div className="text-xs font-medium text-anchor-textSecondary mb-2">
            主要风险点
          </div>
          <ul className="space-y-1">
            {summary.riskPoints.slice(0, 3).map((r, i) => (
              <li
                key={i}
                className="text-xs text-anchor-negative flex items-start gap-2"
              >
                <span>⚠</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
