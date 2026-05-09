import React from 'react';
import type { StateTransition } from '@/types';

interface TransitionHeatmapProps {
  data: StateTransition[];
  summaries?: string[];
}

function probToOpacity(prob: number): number {
  return 0.1 + prob * 0.7;
}

const STATE_ORDER = [
  '行业强+个股强',
  '行业强+个股中',
  '行业强+个股弱',
  '行业中+个股强',
  '行业中+个股中',
  '行业中+个股弱',
  '行业弱+个股强',
  '行业弱+个股中',
  '行业弱+个股弱',
];

// 支持内部格式的映射
const INTERNAL_TO_DISPLAY: Record<string, string> = {
  'positive+positive': '行业强+个股强',
  'positive+neutral': '行业强+个股中',
  'positive+negative': '行业强+个股弱',
  'neutral+positive': '行业中+个股强',
  'neutral+neutral': '行业中+个股中',
  'neutral+negative': '行业中+个股弱',
  'negative+positive': '行业弱+个股强',
  'negative+neutral': '行业弱+个股中',
  'negative+negative': '行业弱+个股弱',
};

function shortLabel(state: string): string {
  const displayState = INTERNAL_TO_DISPLAY[state] || state;
  return displayState.replace('行业', '').replace('个股', '');
}

function normalizeState(state: string): string {
  return INTERNAL_TO_DISPLAY[state] || state;
}

export function TransitionHeatmap({ data, summaries }: TransitionHeatmapProps) {
  // 先规范化所有状态
  const normalizedData = data.map((t) => ({
    ...t,
    from_state: normalizeState(t.from_state),
    to_state: normalizeState(t.to_state),
  }));

  const allStates = new Set<string>();
  for (const t of normalizedData) {
    allStates.add(t.from_state);
    allStates.add(t.to_state);
  }

  // 优先用预定义顺序
  const orderedStates = STATE_ORDER.filter((s) => allStates.has(s));

  const matrix = new Map<string, StateTransition>();
  for (const t of normalizedData) {
    matrix.set(`${t.from_state}|${t.to_state}`, t);
  }

  const maxProb = Math.max(...normalizedData.map((d) => d.probability), 0.01);

  return (
    <div>
      <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-3">
        状态转移矩阵
      </h2>
      {summaries && summaries.length > 0 && (
        <div className="mb-3 bg-anchor-bgSecondary border border-anchor-border rounded-sm p-2">
          <div className="text-xs text-anchor-textMuted mb-1">转移规律:</div>
          <ul className="text-xs text-anchor-text space-y-1">
            {summaries.map((summary, index) => (
              <li key={index} className="flex items-start gap-2">
                <span className="text-anchor-accent mt-0.5">•</span>
                {summary}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="overflow-x-auto">
        <div
          className="inline-grid gap-px bg-anchor-border rounded-sm"
          style={{
            gridTemplateColumns: `auto repeat(${orderedStates.length}, 1fr)`,
          }}
        >
          {/* Top-left corner */}
          <div className="bg-anchor-bgTertiary p-1.5" />
          {/* Column headers */}
          {orderedStates.map((state) => (
            <div
              key={`h-${state}`}
              className="bg-anchor-bgTertiary px-1 py-1.5 text-[9px] text-anchor-textMuted text-center font-mono"
            >
              {shortLabel(state)}
            </div>
          ))}

          {/* Rows */}
          {orderedStates.map((fromState) => (
            <React.Fragment key={fromState}>
              <div
                className="bg-anchor-bgTertiary px-1.5 py-1 text-[9px] text-anchor-textMuted text-right font-mono"
              >
                {shortLabel(fromState)}
              </div>
              {orderedStates.map((toState) => {
                const transition = matrix.get(`${fromState}|${toState}`);
                const prob = transition?.probability ?? 0;
                const count = transition?.count ?? 0;
                const isSelf = fromState === toState;
                const intensity = prob / maxProb;
                const isHighlight = prob >= 0.3 && count >= 3;

                return (
                  <div
                    key={`${fromState}-${toState}`}
                    className="p-1 text-center"
                    style={{
                      backgroundColor:
                        prob > 0
                          ? `rgba(59, 130, 246, ${probToOpacity(intensity)})`
                          : 'transparent',
                      outline: isHighlight ? '1px solid #f59e0b' : undefined,
                    }}
                    title={`${fromState} → ${toState}: ${(prob * 100).toFixed(1)}% (${count}次)`}
                  >
                    <span
                      className={`text-[9px] font-mono ${
                        prob > 0.3
                          ? 'text-white'
                          : prob > 0
                            ? 'text-anchor-textSecondary'
                            : 'text-anchor-textMuted'
                      } ${isSelf ? 'font-medium' : ''}`}
                    >
                      {prob > 0 ? `${(prob * 100).toFixed(0)}%` : ''}
                    </span>
                  </div>
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}
