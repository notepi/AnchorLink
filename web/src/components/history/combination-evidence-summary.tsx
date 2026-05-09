'use client';

import { useState } from 'react';
import type { CombinationSynergy, Combination } from '@/types';
import { cn, formatSignalLabel } from '@/lib/utils';
import { SignalCombinations } from './signal-combinations';

interface CombinationEvidenceSummaryProps {
  synergies: CombinationSynergy[];
  fullCombinations: Combination[];
}

// 组合卡片组件
function CombinationCard({ synergy }: { synergy: CombinationSynergy }) {
  return (
    <div className="bg-anchor-bgTertiary rounded p-3 border border-anchor-border">
      {/* 头部：组合名称 */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1 flex-wrap">
          {synergy.labels.map((label, i) => (
            <span key={i} className="text-xs">
              <span className="text-anchor-text font-medium">
                {formatSignalLabel(label)}
              </span>
              {i < synergy.labels.length - 1 && (
                <span className="text-anchor-accent mx-1">+</span>
              )}
            </span>
          ))}
        </div>
        <span className="text-xs text-anchor-textMuted">样本{synergy.count}</span>
      </div>

      {/* 核心指标 */}
      <div className="grid grid-cols-3 gap-2 mb-2 text-center">
        <div>
          <div className="text-xs text-anchor-textMuted">组合次日均值</div>
          <div
            className={cn(
              'text-xs font-mono',
              synergy.avgNext1d >= 0 ? 'text-anchor-positive' : 'text-anchor-negative'
            )}
          >
            {synergy.avgNext1d >= 0 ? '+' : ''}
            {synergy.avgNext1d.toFixed(2)}pp
          </div>
        </div>
        <div>
          <div className="text-xs text-anchor-textMuted">胜率</div>
          <div
            className={cn(
              'text-xs font-mono',
              synergy.winRate && synergy.winRate >= 0.5
                ? 'text-anchor-positive'
                : 'text-anchor-negative'
            )}
          >
            {synergy.winRate ? `${(synergy.winRate * 100).toFixed(0)}%` : '—'}
          </div>
        </div>
        <div>
          <div className="text-xs text-anchor-textMuted">协同增量</div>
          <div
            className={cn(
              'text-xs font-mono',
              synergy.synergy > 0 ? 'text-anchor-positive' : 'text-anchor-textMuted'
            )}
          >
            {synergy.synergy >= 0 ? '+' : ''}
            {synergy.synergy.toFixed(2)}pp
          </div>
        </div>
      </div>

      {/* 业务解释 */}
      <p className="text-xs text-anchor-textSecondary">
        较「{formatSignalLabel(synergy.bestSingleLabel)}」单独出现时
        {synergy.synergy > 0 ? '增强' : '减弱'}
        {Math.abs(synergy.synergy).toFixed(2)}pp
      </p>
    </div>
  );
}

export function CombinationEvidenceSummary({
  synergies,
  fullCombinations,
}: CombinationEvidenceSummaryProps) {
  const [showFullCombinations, setShowFullCombinations] = useState(false);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-medium text-anchor-textSecondary uppercase">
          信号组合效应
        </h2>
        {synergies.length > 0 && (
          <span className="text-xs text-anchor-textMuted">
            合格组合 {synergies.length} 个
          </span>
        )}
      </div>

      {/* 有合格组合时展示 TOP3 */}
      {synergies.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
          {synergies.slice(0, 3).map((s) => (
            <CombinationCard key={s.labels.join('+')} synergy={s} />
          ))}
        </div>
      ) : (
        /* 无合格组合时给出明确结论 */
        <div className="bg-anchor-bgTertiary rounded p-4 text-center mb-4">
          <p className="text-sm text-anchor-textSecondary">
            当前没有比单信号更有解释力的组合
          </p>
          <p className="text-xs text-anchor-textMuted mt-1">
            信号两两组合后，表现均未超过组合内最强单信号
          </p>
        </div>
      )}

      {/* 折叠区：完整组合列表（调试用途） */}
      <div className="border-t border-anchor-border pt-3">
        <button
          onClick={() => setShowFullCombinations(!showFullCombinations)}
          className="text-xs text-anchor-textMuted hover:text-anchor-text flex items-center gap-1"
        >
          {showFullCombinations ? '▲' : '▼'}{' '}
          {showFullCombinations
            ? '收起全部组合'
            : '查看全部组合（调试）'}
        </button>

        {showFullCombinations && (
          <div className="mt-3">
            <SignalCombinations combinations={fullCombinations} />
          </div>
        )}
      </div>
    </div>
  );
}
