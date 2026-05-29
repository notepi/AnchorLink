'use client';

import { useMemo } from 'react';
import type { HistorySummaryRow } from '@/types';
import { deriveTodayHistoryMapping } from '@/lib/today-history-mapping';
import { formatDate, formatPct, formatSignalLabel } from '@/lib/utils';

interface TodayHistoryMappingPanelProps {
  summary: HistorySummaryRow[];
  targetDate?: string;
}

function formatRate(value: number | null): string {
  if (value === null) return '--';
  return `${(value * 100).toFixed(0)}%`;
}

function pathLabelColor(label: string): string {
  switch (label) {
    case '强势延续':
      return 'text-anchor-positive border-anchor-positive/40 bg-anchor-positive/10';
    case '冲高回落':
    case '继续走弱':
      return 'text-anchor-negative border-anchor-negative/40 bg-anchor-negative/10';
    case '弱势修复':
      return 'text-anchor-accent border-anchor-accent/40 bg-anchor-accent/10';
    case '窄幅震荡':
      return 'text-anchor-textSecondary border-anchor-border bg-anchor-bgTertiary';
    case '样本分歧':
    default:
      return 'text-anchor-textMuted border-anchor-border bg-anchor-bgTertiary';
  }
}

function fieldNameDisplay(field: string): string {
  const map: Record<string, string> = {
    industry_beta: 'Beta',
    anchor_alpha: 'Alpha',
    risk_level: '风险',
    strongest_group: '最强组',
    weakest_group: '最弱组',
  };
  return map[field] || field;
}

export function TodayHistoryMappingPanel({ summary, targetDate }: TodayHistoryMappingPanelProps) {
  const mapping = useMemo(
    () => deriveTodayHistoryMapping(summary, targetDate),
    [summary, targetDate]
  );

  if (!mapping) {
    return (
      <section className="bg-anchor-bgSecondary rounded-sm border border-anchor-border p-4">
        <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-1">
          今日历史映射
        </h2>
        <p className="text-[11px] text-anchor-textMuted mb-3">
          把选定日期的整体状态放回历史样本中，观察相似状态后的路径分布，不代表预测。
        </p>
        <p className="text-xs text-anchor-textMuted">
          相似历史样本不足，暂不生成路径参考。
        </p>
      </section>
    );
  }

  return (
    <section className="bg-anchor-bgSecondary rounded-sm border border-anchor-border p-4">
      <div className="mb-4">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
            今日历史映射
          </h2>
          <span className="text-[11px] text-anchor-textMuted">
            相似样本 {mapping.sampleCount} 个
          </span>
        </div>
        <p className="text-[11px] text-anchor-textMuted mt-1">
          把选定日期的整体状态放回历史样本中，观察相似状态后的路径分布，不代表预测。
        </p>
      </div>

      {/* 当前状态摘要 */}
      <div className="bg-anchor-bgTertiary border border-anchor-border rounded-sm p-3 mb-4">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-xs font-medium text-anchor-text">
            {formatDate(mapping.targetDate)}
          </span>
          <span className="text-xs text-anchor-textSecondary">
            {mapping.stateSummary}
          </span>
        </div>
        {mapping.coreSignals.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {mapping.coreSignals.map((s) => (
              <span
                key={s}
                className="text-[10px] text-anchor-textSecondary border border-anchor-border rounded px-1.5 py-0.5"
              >
                {formatSignalLabel(s)}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 路径标签 */}
      <div className="mb-4">
        <span className={`text-xs border rounded px-2 py-1 ${pathLabelColor(mapping.pathLabel)}`}>
          {mapping.pathLabel}
        </span>
      </div>

      {/* 路径统计 */}
      <div className="mb-4 overflow-x-auto">
        <table className="w-full text-xs" aria-label="历史路径统计">
          <thead>
            <tr className="text-anchor-textMuted">
              <th className="text-left py-1.5 pr-3 font-medium">窗口</th>
              <th className="text-right py-1.5 px-3 font-medium">平均收益</th>
              <th className="text-right py-1.5 px-3 font-medium">胜率</th>
              <th className="text-right py-1.5 pl-3 font-medium">平均超额</th>
            </tr>
          </thead>
          <tbody>
            {mapping.pathStats.map((stat) => (
              <tr key={stat.window} className="border-t border-anchor-border">
                <td className="py-1.5 pr-3 text-anchor-text font-mono">T+{stat.window === '1d' ? '1' : stat.window === '3d' ? '3' : '5'}</td>
                <td className={`py-1.5 px-3 text-right font-mono ${stat.avgReturn !== null && stat.avgReturn > 0 ? 'text-anchor-positive' : stat.avgReturn !== null && stat.avgReturn < 0 ? 'text-anchor-negative' : 'text-anchor-textSecondary'}`}>
                  {formatPct(stat.avgReturn)}
                  {stat.avgReturn !== null && (stat.avgReturn > 0 ? ' ↑' : stat.avgReturn < 0 ? ' ↓' : '')}
                </td>
                <td className="py-1.5 px-3 text-right font-mono text-anchor-textSecondary">
                  {formatRate(stat.winRate)}
                </td>
                <td className={`py-1.5 pl-3 text-right font-mono ${stat.avgExcess !== null && stat.avgExcess > 0 ? 'text-anchor-positive' : stat.avgExcess !== null && stat.avgExcess < 0 ? 'text-anchor-negative' : 'text-anchor-textSecondary'}`}>
                  {formatPct(stat.avgExcess)}
                  {stat.avgExcess !== null && (stat.avgExcess > 0 ? ' ↑' : stat.avgExcess < 0 ? ' ↓' : '')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 相似历史案例 */}
      <div>
        <div className="text-xs font-medium text-anchor-textSecondary mb-2">
          最相似历史案例
        </div>
        <div className="space-y-2">
          {mapping.similarCases.map((c) => (
            <div
              key={c.date}
              className="bg-anchor-bgTertiary border border-anchor-border rounded-sm p-3"
            >
              <div className="flex items-center justify-between gap-3 mb-1.5">
                <span className="text-xs font-medium text-anchor-text font-mono">
                  {formatDate(c.date)}
                </span>
                <span className="text-xs font-mono text-anchor-textMuted">
                  相似度 {c.similarity.toFixed(2)}
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5 mb-2">
                {c.matchedStateFields.map((f) => (
                  <span
                    key={f}
                    className="text-[10px] text-anchor-accent border border-anchor-accent/30 bg-anchor-accent/10 rounded px-1.5 py-0.5"
                  >
                    {fieldNameDisplay(f)}
                  </span>
                ))}
                {c.matchedSignals.slice(0, 3).map((s) => (
                  <span
                    key={`${s.category}-${s.label}`}
                    className="text-[10px] text-anchor-textSecondary border border-anchor-border rounded px-1.5 py-0.5"
                  >
                    {formatSignalLabel(s.label)}
                  </span>
                ))}
                {c.matchedSignals.length > 3 && (
                  <span className="text-[10px] text-anchor-textMuted">
                    +{c.matchedSignals.length - 3}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div>
                  <span className="text-anchor-textMuted">T+1</span>
                  <span className={`ml-1.5 font-mono ${c.next1d !== null && c.next1d > 0 ? 'text-anchor-positive' : c.next1d !== null && c.next1d < 0 ? 'text-anchor-negative' : 'text-anchor-textSecondary'}`}>
                    {formatPct(c.next1d)}
                  </span>
                </div>
                <div>
                  <span className="text-anchor-textMuted">T+3</span>
                  <span className={`ml-1.5 font-mono ${c.next3d !== null && c.next3d > 0 ? 'text-anchor-positive' : c.next3d !== null && c.next3d < 0 ? 'text-anchor-negative' : 'text-anchor-textSecondary'}`}>
                    {formatPct(c.next3d)}
                  </span>
                </div>
                <div>
                  <span className="text-anchor-textMuted">T+5</span>
                  <span className={`ml-1.5 font-mono ${c.next5d !== null && c.next5d > 0 ? 'text-anchor-positive' : c.next5d !== null && c.next5d < 0 ? 'text-anchor-negative' : 'text-anchor-textSecondary'}`}>
                    {formatPct(c.next5d)}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 备注 */}
      {mapping.notes.length > 0 && (
        <div className="mt-3 pt-3 border-t border-anchor-border">
          {mapping.notes.map((note, i) => (
            <p key={i} className="text-[11px] text-anchor-textMuted">{note}</p>
          ))}
        </div>
      )}
    </section>
  );
}
