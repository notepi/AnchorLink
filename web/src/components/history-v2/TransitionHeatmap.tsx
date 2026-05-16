import React from 'react';
import type { DashboardView, QuadrantState } from '@/types/dashboard-view';
import { formatPercent, formatWinRate } from '@/lib/history-v2/formatters';

interface TransitionHeatmapProps {
  transitionData: DashboardView['tableData']['stateTransitions'];
  pathRanking: DashboardView['tableData']['rankedTransitionPaths'];
  pathStats: DashboardView['tableData']['pathStats'];
  currentMapping: DashboardView['summary']['currentMapping'];
  transitionVerdict: DashboardView['summary']['transitionVerdict'];
}

const STATE_ORDER: Array<{ key: QuadrantState; shortLabel: string; label: string }> = [
  { key: 'positive+positive', shortLabel: '强+强', label: '行业强+个股强' },
  { key: 'positive+neutral', shortLabel: '强+中', label: '行业强+个股中' },
  { key: 'positive+negative', shortLabel: '强+弱', label: '行业强+个股弱' },
  { key: 'neutral+positive', shortLabel: '中+强', label: '行业中+个股强' },
  { key: 'neutral+neutral', shortLabel: '中+中', label: '行业中+个股中' },
  { key: 'neutral+negative', shortLabel: '中+弱', label: '行业中+个股弱' },
  { key: 'negative+positive', shortLabel: '弱+强', label: '行业弱+个股强' },
  { key: 'negative+neutral', shortLabel: '弱+中', label: '行业弱+个股中' },
  { key: 'negative+negative', shortLabel: '弱+弱', label: '行业弱+个股弱' }
];

const STATE_LABEL_BY_KEY = Object.fromEntries(STATE_ORDER.map((state) => [state.key, state.label])) as Record<QuadrantState, string>;
const STATE_SHORT_BY_KEY = Object.fromEntries(STATE_ORDER.map((state) => [state.key, state.shortLabel])) as Record<QuadrantState, string>;

export default function TransitionHeatmap({
  transitionData,
  pathRanking,
  pathStats,
  currentMapping,
  transitionVerdict
}: TransitionHeatmapProps) {
  const currentState = `${currentMapping?.industryBeta ?? 'neutral'}+${currentMapping?.anchorAlpha ?? 'neutral'}` as QuadrantState;

  const matrix = new Map<string, number>();
  transitionData?.forEach?.((transition) => {
    matrix.set(`${transition.fromState}->${transition.toState}`, transition.probability * 100);
  });

  const currentRowTransitions = (transitionData ?? [])
    .filter((transition) => transition.fromState === currentState)
    .sort((a, b) => b.probability - a.probability);
  const maxCurrentProbability = currentRowTransitions[0]?.probability;
  const guidePills = currentRowTransitions.slice(0, 3);

  const getCellClass = (value: number | null | undefined) => {
    if (value == null || value === 0) return 'empty';
    if (value >= 40) return 'strong';
    if (value >= 20) return 'medium';
    return 'low';
  };

  return (
    <section className="section">
      <div className="section-head">
        <h2 className="section-title">状态迁移路径</h2>
        <p className="section-note">先看左侧路径排行；右侧矩阵只保留为证据，橙色行表示当前状态。</p>
      </div>

      <div className="path-layout">
        <div className="card">
          <div className="path-verdict">
            <h3>{transitionVerdict.title}</h3>
            <p>{transitionVerdict.description}</p>
          </div>

          {pathRanking?.slice?.(0, 3)?.map?.((path, index) => {
            const pathStat = pathStats?.find?.((item) => item.path === `${path.fromState}→${path.toState}`);
            return (
              <div key={`${path.fromState}-${path.toState}`} className="path-row">
                <div className="rank">{path.rank ?? index + 1}</div>
                <div>
                  <div className="path-main">转向 {(STATE_SHORT_BY_KEY[path.toState] ?? path.toState).replace('+', ' + ')}</div>
                  <div className="path-explain">
                    {path.fromStateLabel ?? STATE_LABEL_BY_KEY[path.fromState]} → {path.toStateLabel ?? STATE_LABEL_BY_KEY[path.toState]}
                    {' · '}
                    样本数：n={path.count}
                    {path.avgReturn3d != null && <> · T+3：{formatPercent(path.avgReturn3d)}</>}
                    {path.winRate3d != null && <> · 胜率：{formatWinRate(path.winRate3d)}</>}
                    {pathStat?.avgReturn != null && <> · T+1：{formatPercent(pathStat.avgReturn)}</>}
                  </div>
                </div>
                <div className="mono">
                  <span className={path.probability >= 0.4 ? 'red' : path.probability >= 0.2 ? 'amber' : ''}>
                    {Math.round(path.probability * 100)}%
                  </span>
                  {' · '}n={path.count}
                </div>
              </div>
            );
          }) ?? null}

          <div className="watch-points">
            {transitionVerdict?.watchPoints?.map?.((point, index) => (
              <div key={index}>{point}</div>
            )) ?? null}
            <div>样本提醒：低概率路径已弱化显示，仅作参考。</div>
          </div>
        </div>

        <div className="heatmap-wrap">
          <div className="matrix-guide">
            <div>
              <strong>矩阵读法</strong>
              左边是当前状态，顶部是下一交易日状态；状态格式是「主线池 + 个股」。
            </div>
            <div className="matrix-pills">
              {guidePills.length > 0 ? guidePills.map((transition) => (
                <span key={transition.toState} className="matrix-pill">
                  {Math.round(transition.probability * 100)}% → {STATE_LABEL_BY_KEY[transition.toState]}
                </span>
              )) : (
                <span className="matrix-pill">当前状态暂无可用迁移样本</span>
              )}
            </div>
          </div>
          <div className="heatmap" aria-label="状态迁移热力矩阵">
            <div className="hm-head">当前\次日</div>
            {STATE_ORDER.map((state) => (
              <div key={`header-${state.key}`} className="hm-head">{state.shortLabel}</div>
            ))}

            {STATE_ORDER.map((fromState) => {
              const isCurrent = fromState.key === currentState;
              return (
                <React.Fragment key={`row-group-${fromState.key}`}>
                  <div className={`hm-row ${isCurrent ? 'current' : 'dim'}`}>
                    {fromState.shortLabel}
                  </div>
                  {STATE_ORDER.map((toState) => {
                    const value = matrix.get(`${fromState.key}->${toState.key}`) ?? 0;
                    const isBest = isCurrent && maxCurrentProbability != null && value === maxCurrentProbability * 100;
                    return (
                      <div
                        key={`${fromState.key}-${toState.key}`}
                        className={`hm-cell ${getCellClass(value)} ${isCurrent ? 'current-row' : ''} ${isBest ? 'current-best' : ''} ${!isCurrent ? 'dim' : ''}`}
                        title={`${fromState.label} → ${toState.label}: ${Math.round(value)}%`}
                      >
                        {value > 0 ? `${Math.round(value)}%` : '0'}
                      </div>
                    );
                  })}
                </React.Fragment>
              );
            })}
          </div>
          <div className="matrix-caption">这里的“主线池”不是宽泛行业指数，而是商业航天硬科技产业链 benchmark；强/中/弱的顺序是「主线池状态 + 个股状态」。例如“弱+中”表示主线池弱、个股中性。</div>
        </div>
      </div>
    </section>
  );
}
