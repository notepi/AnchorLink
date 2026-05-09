'use client';

import type { CoreMetrics as CoreMetricsType } from '@/lib/history-analysis';

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

function formatRatio(value: number | null): string {
  if (value === null) return '--';
  return `${(value * 100).toFixed(0)}%`;
}

interface CoreMetricsProps {
  metrics: CoreMetricsType;
}

export function CoreMetrics({ metrics }: CoreMetricsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 样本收益 */}
      <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
        <h3 className="text-sm font-medium text-anchor-textSecondary uppercase tracking-wide mb-3">
          样本收益
        </h3>
        <div className="space-y-2">
          <div className="flex justify-between items-baseline">
            <span className="text-sm text-anchor-textMuted">日均收益</span>
            <span className={`text-lg font-mono font-medium ${
              metrics.sampleReturn.avgDailyReturn !== null && metrics.sampleReturn.avgDailyReturn > 0
                ? 'text-anchor-positive'
                : metrics.sampleReturn.avgDailyReturn !== null && metrics.sampleReturn.avgDailyReturn < 0
                ? 'text-anchor-negative'
                : 'text-anchor-text'
            }`}>
              {formatPct(metrics.sampleReturn.avgDailyReturn)}
            </span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="text-sm text-anchor-textMuted">中位数收益</span>
            <span className="text-sm font-mono text-anchor-text">
              {formatPct(metrics.sampleReturn.medianReturn)}
            </span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="text-sm text-anchor-textMuted">正收益占比</span>
            <span className="text-sm font-mono text-anchor-text">
              {formatRatio(metrics.sampleReturn.positiveRatio)}
            </span>
          </div>
        </div>
      </div>

      {/* 相对行业 */}
      <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
        <h3 className="text-sm font-medium text-anchor-textSecondary uppercase tracking-wide mb-3">
          相对行业
        </h3>
        <div className="space-y-2">
          <div className="flex justify-between items-baseline">
            <span className="text-sm text-anchor-textMuted">行业日均中位数</span>
            <span className={`text-lg font-mono font-medium ${
              metrics.relativeToIndustry.avgChainMedian !== null && metrics.relativeToIndustry.avgChainMedian > 0
                ? 'text-anchor-positive'
                : metrics.relativeToIndustry.avgChainMedian !== null && metrics.relativeToIndustry.avgChainMedian < 0
                ? 'text-anchor-negative'
                : 'text-anchor-text'
            }`}>
              {formatPct(metrics.relativeToIndustry.avgChainMedian)}
            </span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="text-sm text-anchor-textMuted">日均当日超额</span>
            <span className={`text-sm font-mono ${
              metrics.relativeToIndustry.avgDailyExcess !== null && metrics.relativeToIndustry.avgDailyExcess > 0
                ? 'text-anchor-positive'
                : metrics.relativeToIndustry.avgDailyExcess !== null && metrics.relativeToIndustry.avgDailyExcess < 0
                ? 'text-anchor-negative'
                : 'text-anchor-text'
            }`}>
              {formatPct(metrics.relativeToIndustry.avgDailyExcess)}
            </span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="text-sm text-anchor-textMuted">跑赢行业占比</span>
            <span className="text-sm font-mono text-anchor-text">
              {formatRatio(metrics.relativeToIndustry.outperformRatio)}
            </span>
          </div>
        </div>
      </div>

      {/* 场景质量 */}
      <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
        <h3 className="text-sm font-medium text-anchor-textSecondary uppercase tracking-wide mb-3">
          场景质量
        </h3>
        <div className="space-y-2">
          <div className="flex justify-between items-baseline">
            <span className="text-sm text-anchor-textMuted">最佳象限</span>
            <span className="text-sm font-mono text-anchor-positive">
              {metrics.scenarioQuality.bestQuadrant
                ? quadrantDisplayName[metrics.scenarioQuality.bestQuadrant.quadrant]?.slice(0, 6) || metrics.scenarioQuality.bestQuadrant.quadrant
                : '--'}
            </span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="text-sm text-anchor-textMuted">最差象限</span>
            <span className="text-sm font-mono text-anchor-negative">
              {metrics.scenarioQuality.worstQuadrant
                ? quadrantDisplayName[metrics.scenarioQuality.worstQuadrant.quadrant]?.slice(0, 6) || metrics.scenarioQuality.worstQuadrant.quadrant
                : '--'}
            </span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="text-sm text-anchor-textMuted">有效象限</span>
            <span className="text-sm font-mono text-anchor-text">
              {metrics.scenarioQuality.validQuadrantCount}/9
            </span>
          </div>
        </div>
      </div>

      {/* 事件风险 */}
      <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
        <h3 className="text-sm font-medium text-anchor-textSecondary uppercase tracking-wide mb-3">
          事件风险
        </h3>
        <div className="space-y-2">
          <div className="flex justify-between items-baseline">
            <span className="text-sm text-anchor-textMuted">极端背离次数</span>
            <span className="text-lg font-mono font-medium text-anchor-text">
              {metrics.eventRisk.divergenceCount}
            </span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="text-sm text-anchor-textMuted">最大正背离</span>
            <span className="text-sm font-mono text-anchor-positive">
              {formatPct(metrics.eventRisk.maxPositiveDivergence)}
            </span>
          </div>
          <div className="flex justify-between items-baseline">
            <span className="text-sm text-anchor-textMuted">最大负背离</span>
            <span className="text-sm font-mono text-anchor-negative">
              {formatPct(metrics.eventRisk.maxNegativeDivergence)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
