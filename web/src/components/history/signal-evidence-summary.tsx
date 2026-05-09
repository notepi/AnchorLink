'use client';

import { useState } from 'react';
import type { SignalInsight, SignalTrend, BusinessGroup, SignalLiftRow } from '@/types';
import { cn, formatSignalLabel } from '@/lib/utils';
import { deriveSignalCardConclusion, getSignalBusinessGroup } from '@/lib/history-analysis';
import { SignalTrendIndicator } from './signal-trend-indicator';
import { SignalLiftTable } from './signal-lift-table';

interface SignalEvidenceSummaryProps {
  highValueSignals: SignalInsight[];
  lowValueSignals: SignalInsight[];
  signalTrends: SignalTrend[];
  businessGroups: BusinessGroup[];
  fullSignalTable: SignalLiftRow[];
  trendMap: Map<string, SignalTrend>;
}

// 信号卡片组件
function SignalCard({
  signal,
  trend,
  businessGroup,
  kind,
}: {
  signal: SignalInsight;
  trend: SignalTrend | null;
  businessGroup: string | null;
  kind: 'high_value' | 'caution';
}) {
  // 获取一句话结论
  const conclusion = deriveSignalCardConclusion({ signal, kind, trend });

  return (
    <div
      className={cn(
        'bg-anchor-bgTertiary rounded p-3 border',
        kind === 'high_value'
          ? 'border-l-2 border-l-anchor-positive border-anchor-border'
          : 'border-l-2 border-l-anchor-negative border-anchor-border'
      )}
    >
      {/* 头部：信号名 + 业务分组标签 */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-medium text-anchor-text">
            {formatSignalLabel(signal.label)}
          </span>
          {businessGroup && (
            <span className="text-[10px] px-1.5 py-0.5 bg-anchor-bg rounded text-anchor-textMuted">
              {businessGroup}
            </span>
          )}
        </div>
        {trend && <SignalTrendIndicator trend={trend} compact />}
      </div>

      {/* 核心指标一行 */}
      <div className="grid grid-cols-4 gap-2 mb-2 text-center">
        <div>
          <div className="text-[10px] text-anchor-textMuted">样本</div>
          <div className="text-xs font-mono text-anchor-text">{signal.count}</div>
        </div>
        <div>
          <div className="text-[10px] text-anchor-textMuted">次日均值</div>
          <div
            className={cn(
              'text-xs font-mono',
              signal.deltaPp >= 0 ? 'text-anchor-positive' : 'text-anchor-negative'
            )}
          >
            {signal.deltaPp >= 0 ? '+' : ''}
            {signal.deltaPp.toFixed(2)}pp
          </div>
        </div>
        <div>
          <div className="text-[10px] text-anchor-textMuted">胜率</div>
          <div
            className={cn(
              'text-xs font-mono',
              signal.winRate >= 0.5 ? 'text-anchor-positive' : 'text-anchor-negative'
            )}
          >
            {(signal.winRate * 100).toFixed(0)}%
          </div>
        </div>
        <div>
          <div className="text-[10px] text-anchor-textMuted">稳定分</div>
          <div className="text-xs font-mono text-anchor-text">{signal.stabilityScore}</div>
        </div>
      </div>

      {/* 一句话结论 */}
      <p
        className={cn(
          'text-xs',
          kind === 'high_value' ? 'text-anchor-positive' : 'text-anchor-negative'
        )}
      >
        {conclusion}
      </p>
    </div>
  );
}

export function SignalEvidenceSummary({
  highValueSignals,
  lowValueSignals,
  signalTrends,
  businessGroups,
  fullSignalTable,
  trendMap,
}: SignalEvidenceSummaryProps) {
  const [showFullTable, setShowFullTable] = useState(false);

  const top3High = highValueSignals.slice(0, 3);
  const top3Low = lowValueSignals.slice(0, 3);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-medium text-anchor-textSecondary uppercase">
          信号证据
        </h2>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-anchor-positive">高价值 {highValueSignals.length}</span>
          <span className="text-anchor-negative">需警惕 {lowValueSignals.length}</span>
        </div>
      </div>

      {/* 高价值信号区 */}
      {top3High.length > 0 && (
        <div className="mb-4">
          <div className="text-xs text-anchor-textMuted mb-2">最值得信</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {top3High.map((s) => (
              <SignalCard
                key={s.label}
                signal={s}
                trend={trendMap.get(s.label) || null}
                businessGroup={getSignalBusinessGroup(s.label, businessGroups)}
                kind="high_value"
              />
            ))}
          </div>
        </div>
      )}

      {/* 警惕信号区 */}
      {top3Low.length > 0 && (
        <div className="mb-4">
          <div className="text-xs text-anchor-textMuted mb-2">最应该警惕</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {top3Low.map((s) => (
              <SignalCard
                key={s.label}
                signal={s}
                trend={trendMap.get(s.label) || null}
                businessGroup={getSignalBusinessGroup(s.label, businessGroups)}
                kind="caution"
              />
            ))}
          </div>
        </div>
      )}

      {/* 折叠区：完整信号明细 */}
      <div className="border-t border-anchor-border pt-3">
        <button
          onClick={() => setShowFullTable(!showFullTable)}
          className="text-xs text-anchor-textMuted hover:text-anchor-text flex items-center gap-1"
        >
          {showFullTable ? '▲' : '▼'} {showFullTable ? '收起' : '查看完整信号明细'}
        </button>

        {showFullTable && (
          <div className="mt-3">
            <SignalLiftTable data={fullSignalTable} trendMap={trendMap} />
          </div>
        )}
      </div>
    </div>
  );
}
