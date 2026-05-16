'use client';

import { useMemo } from 'react';
import type { StateTransition } from '@/types';

interface TransitionVerdictProps {
  data: StateTransition[];
}

const STATE_DISPLAY: Record<string, string> = {
  'positive+positive': '主线池强 + 个股强',
  'positive+neutral': '主线池强 + 个股中',
  'positive+negative': '主线池强 + 个股弱',
  'neutral+positive': '主线池中 + 个股强',
  'neutral+neutral': '主线池中 + 个股中',
  'neutral+negative': '主线池中 + 个股弱',
  'negative+positive': '主线池弱 + 个股强',
  'negative+neutral': '主线池弱 + 个股中',
  'negative+negative': '主线池弱 + 个股弱',
};

function displayState(state: string): string {
  return STATE_DISPLAY[state] || state;
}

interface RankedPath {
  rank: number;
  fromState: string;
  toState: string;
  probability: number;
  count: number;
}

function deriveRankedPaths(transitions: StateTransition[]): RankedPath[] {
  const fromMap = new Map<string, StateTransition[]>();
  for (const t of transitions) {
    if (t.count === 0) continue;
    const list = fromMap.get(t.from_state) || [];
    list.push(t);
    fromMap.set(t.from_state, list);
  }

  const paths: RankedPath[] = [];
  for (const [, list] of fromMap) {
    list.sort((a, b) => b.probability - a.probability);
    for (const t of list.slice(0, 2)) {
      if (t.probability >= 0.15 && t.count >= 2) {
        paths.push({
          rank: 0,
          fromState: t.from_state,
          toState: t.to_state,
          probability: t.probability,
          count: t.count,
        });
      }
    }
  }

  paths.sort((a, b) => b.probability - a.probability);
  return paths.slice(0, 5).map((p, i) => ({ ...p, rank: i + 1 }));
}

function deriveVerdict(rankedPaths: RankedPath[]): {
  title: string;
  description: string;
  watchPoints: string[];
} {
  if (rankedPaths.length === 0) {
    return {
      title: '样本不足',
      description: '当前迁移路径样本不足，无法形成有效判断。',
      watchPoints: ['需要更多历史数据来建立路径参考。'],
    };
  }

  const topPath = rankedPaths[0];
  const toState = displayState(topPath.toState);

  const isRepair = topPath.toState.includes('positive') || topPath.toState.includes('neutral');
  const title = isRepair ? '偏修复观察' : '偏弱势延续';

  const description = `当前状态最可能转向「${toState}」，概率 ${(topPath.probability * 100).toFixed(0)}%。${
    topPath.count < 5
      ? '但样本偏少，不作为单独操作依据。'
      : '样本量尚可，可作为参考。'
  }`;

  const watchPoints: string[] = [];
  if (isRepair) {
    watchPoints.push('观察重点：如果修复信号出现但个股未同步，只能视为 Beta 修复。');
    watchPoints.push('确认条件：个股强于行业、核心池止跌、资金背离缓和。');
  } else {
    watchPoints.push('观察重点：弱势延续时，关注是否出现结构性修复信号。');
    watchPoints.push('确认条件：主线池扩散增强、个股 Alpha 转正。');
  }
  if (topPath.count < 5) {
    watchPoints.push('样本提醒：当前路径样本小，颜色强度已降权。');
  }

  return { title, description, watchPoints };
}

export function TransitionVerdict({ data }: TransitionVerdictProps) {
  const rankedPaths = useMemo(() => deriveRankedPaths(data), [data]);
  const verdict = useMemo(() => deriveVerdict(rankedPaths), [rankedPaths]);

  return (
    <div className="space-y-3">
      {/* Verdict card */}
      <div className="border border-anchor-accent/30 bg-anchor-accent/8 p-3">
        <h3 className="text-sm font-semibold text-anchor-text mb-1">
          {verdict.title}
        </h3>
        <p className="text-xs text-anchor-textSecondary leading-relaxed">
          {verdict.description}
        </p>
      </div>

      {/* Ranked paths */}
      {rankedPaths.length > 0 && (
        <div className="space-y-2">
          {rankedPaths.map((path) => (
            <div
              key={`${path.fromState}-${path.toState}`}
              className="grid grid-cols-[24px_1fr_auto] gap-2 items-center bg-anchor-bgTertiary border border-anchor-borderSoft p-2.5"
            >
              <div className="w-6 h-6 border border-anchor-border bg-anchor-bgSecondary grid place-items-center text-xs text-anchor-textSecondary">
                {path.rank}
              </div>
              <div>
                <div className="text-xs font-medium text-anchor-text">
                  转向 {displayState(path.toState)}
                </div>
                <div className="text-[10px] text-anchor-textMuted mt-0.5">
                  来自 {displayState(path.fromState)}
                </div>
              </div>
              <div className="text-xs font-mono text-anchor-textSecondary">
                <span className={path.probability >= 0.4 ? 'text-anchor-negative' : path.probability >= 0.25 ? 'text-anchor-accent' : 'text-anchor-textMuted'}>
                  {(path.probability * 100).toFixed(0)}%
                </span>
                {' · '}n={path.count}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Watch points */}
      {verdict.watchPoints.length > 0 && (
        <div className="space-y-2">
          {verdict.watchPoints.map((point, i) => (
            <div
              key={i}
              className="border-l-2 border-anchor-accent bg-anchor-accent/8 px-3 py-2 text-xs text-anchor-textSecondary"
            >
              {point}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
