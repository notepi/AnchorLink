'use client';

import type { Conclusion } from '@/lib/history-analysis';

const quadrantDisplayName: Record<string, string> = {
  'positive+positive': '行业强+个股强',
  'positive+neutral': '行业强+个股中性',
  'positive+negative': '行业强+个股弱',
  'neutral+positive': '行业中性+个股强',
  'neutral+neutral': '行业中性+个股中性',
  'neutral+negative': '行业中性+个股弱',
  'negative+positive': '行业弱+个股强',
  'negative+neutral': '行业弱+个股中性',
  'negative+negative': '行业弱+个股弱',
};

function formatPct(value: number | null): string {
  if (value === null) return '--';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

interface ConclusionCardProps {
  conclusion: Conclusion;
}

export function ConclusionCard({ conclusion }: ConclusionCardProps) {
  const { sampleDays, bestQuadrant, worstQuadrant, meanReversion, warning } = conclusion;

  // 生成一句话总结
  let summaryText = '';
  if (sampleDays >= 30) {
    const parts: string[] = [];

    if (bestQuadrant) {
      const bestName = quadrantDisplayName[bestQuadrant.quadrant] || bestQuadrant.quadrant;
      parts.push(`${bestName} 场景样本 ${bestQuadrant.count} 天，次日均值 ${formatPct(bestQuadrant.avg_next_1d)}`);
    }

    if (worstQuadrant) {
      const worstName = quadrantDisplayName[worstQuadrant.quadrant] || worstQuadrant.quadrant;
      parts.push(`${worstName} 场景样本 ${worstQuadrant.count} 天，次日均值 ${formatPct(worstQuadrant.avg_next_1d)}`);
    }

    // 均值回归特征
    if (meanReversion.outperformThenReverseRate && meanReversion.outperformThenReverseRate > 0.5) {
      parts.push('跑赢后次日大概率反转');
    }
    if (meanReversion.underperformThenReverseRate && meanReversion.underperformThenReverseRate > 0.5) {
      parts.push('跑输后次日大概率反转');
    }

    if (parts.length > 0) {
      summaryText = '样本内观察：' + parts.join('，');
    }
  }

  return (
    <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
      <h2 className="text-sm font-medium text-anchor-textSecondary uppercase tracking-wide mb-3">
        样本内结论
      </h2>

      {summaryText && (
        <div className="mb-3 text-anchor-text">
          {summaryText}
        </div>
      )}

      {/* 最佳/最差场景 */}
      {(bestQuadrant || worstQuadrant) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
          {bestQuadrant && (
            <div className="bg-anchor-positive/10 border border-anchor-positive/20 rounded p-3">
              <div className="text-sm text-anchor-positive font-medium mb-1">最佳场景</div>
              <div className="text-anchor-text">
                {quadrantDisplayName[bestQuadrant.quadrant] || bestQuadrant.quadrant}
              </div>
              <div className="text-sm text-anchor-textMuted mt-1">
                样本 {bestQuadrant.count} 天 · 次日均值 {formatPct(bestQuadrant.avg_next_1d)}
                {bestQuadrant.win_rate_1d !== null && ` · 胜率 ${(bestQuadrant.win_rate_1d * 100).toFixed(0)}%`}
              </div>
            </div>
          )}
          {worstQuadrant && (
            <div className="bg-anchor-negative/10 border border-anchor-negative/20 rounded p-3">
              <div className="text-sm text-anchor-negative font-medium mb-1">最差场景</div>
              <div className="text-anchor-text">
                {quadrantDisplayName[worstQuadrant.quadrant] || worstQuadrant.quadrant}
              </div>
              <div className="text-sm text-anchor-textMuted mt-1">
                样本 {worstQuadrant.count} 天 · 次日均值 {formatPct(worstQuadrant.avg_next_1d)}
                {worstQuadrant.win_rate_1d !== null && ` · 胜率 ${(worstQuadrant.win_rate_1d * 100).toFixed(0)}%`}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 均值回归指标 */}
      {(meanReversion.outperformThenReverseRate !== null || meanReversion.underperformThenReverseRate !== null) && (
        <div className="text-sm text-anchor-textMuted mb-3">
          {meanReversion.outperformThenReverseRate !== null && (
            <span className="mr-4">
              跑赢后次日反转率 {(meanReversion.outperformThenReverseRate * 100).toFixed(0)}%
            </span>
          )}
          {meanReversion.underperformThenReverseRate !== null && (
            <span>
              跑输后次日反转率 {(meanReversion.underperformThenReverseRate * 100).toFixed(0)}%
            </span>
          )}
        </div>
      )}

      {/* 风险提示 */}
      <div className="text-xs text-anchor-textMuted bg-anchor-bgTertiary rounded p-2">
        {warning}
      </div>
    </div>
  );
}
