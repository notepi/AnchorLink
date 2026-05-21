"use client";

import { useMemo, useState } from 'react';
import type { DashboardView, PathPatternPoint } from '@/types/dashboard-view';
import { formatPercent, formatPp, formatNumber, formatWinRate, formatStars, formatRelationType, getValueColorClass, formatSignificance } from '@/lib/history-v2/formatters';
import { POOL } from '@/lib/glossary';

interface PersonalityProfileProps {
  personalityData: DashboardView['personality'];
  profile: DashboardView['summary']['profile'];
}

function pathPoints(points: PathPatternPoint[], key: keyof PathPatternPoint): string {
  return pathCoords(points, key).map(({ x, y }) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
}

function pathCoords(points: PathPatternPoint[], key: keyof PathPatternPoint): Array<{ x: number; y: number }> {
  if (!points?.length) return [];
  const seriesKeys: Array<keyof PathPatternPoint> = ['anchorReturn', 'chainMedian', 'excess'];
  const values: number[] = [];
  points.forEach((point) => {
    seriesKeys.forEach((seriesKey) => {
      const value = point[seriesKey];
      if (typeof value === 'number' && Number.isFinite(value)) {
        values.push(value);
      }
    });
  });
  if (!values.length) return [];

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const sorted = [...points].sort((a, b) => a.offset - b.offset);
  const denominator = Math.max(sorted.length - 1, 1);

  return sorted.map((point, index) => {
    const value = typeof point[key] === 'number' ? point[key] as number : 0;
    return { x: 30 + (index / denominator) * 700, y: 210 - ((value - min) / range) * 150 };
  });
}

export default function PersonalityProfile({ personalityData, profile }: PersonalityProfileProps) {
  const { summaryMetrics, summary, habitPatterns, counterIntuitivePatterns, trapPatterns, relationshipProfile, pathPatterns, sampleDays, validSampleDays } = personalityData;
  const [activePatternIndex, setActivePatternIndex] = useState(0);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const toggleExpand = (key: string) => setExpandedKey(prev => prev === key ? null : key);
  const activePattern = pathPatterns?.[activePatternIndex] ?? pathPatterns?.[0];
  const activePath = activePattern?.avgPath ?? [];
  const offsetLabels = useMemo(() => (
    [...activePath].sort((a, b) => a.offset - b.offset)
  ), [activePath]);

  // 构建度量条数据
  const metrics = [
    {
      label: '胜率',
      value: formatWinRate(summaryMetrics.baselineWinRate1d, 1),
      valueClass: getValueColorClass(summaryMetrics.baselineWinRate1d),
      explain: `历史上约 ${formatWinRate(summaryMetrics.baselineWinRate1d, 0)} 的样本日，后续收益为正。`
    },
    {
      label: '期望值',
      value: summaryMetrics.expectancy1d != null ? `${(summaryMetrics.expectancy1d > 0 ? '+' : '')}${(summaryMetrics.expectancy1d * 100).toFixed(2)}%` : '--',
      valueClass: getValueColorClass(summaryMetrics.expectancy1d),
      explain: summaryMetrics.expectancy1d != null
        ? `每次交易的数学期望：${(summaryMetrics.expectancy1d * 100).toFixed(2)}%。${summaryMetrics.expectancy1d > 0 ? '正值意味着长期可盈利。' : '负值意味着长期会亏损。'}`
        : '胜率×平均赚 - 败率×平均亏，>0 才值得做。'
    },
    {
      label: '信息比率',
      value: formatNumber(summaryMetrics.informationRatio, 2),
      valueClass: getValueColorClass(summaryMetrics.informationRatio),
      explain: summaryMetrics.informationRatio != null
        ? `相对产业链超额收益的稳定性。${summaryMetrics.informationRatio > 0.5 ? '好于一般' : summaryMetrics.informationRatio > 0.2 ? '中等水平' : '跑赢板块不够稳定'}。`
        : '超额收益均值/标准差×√252，>0.5好，>1.0优。'
    },
    {
      label: 'T+3 超额',
      value: `${formatPp(summaryMetrics.medianExcess3d, 2)}`,
      valueClass: getValueColorClass(summaryMetrics.medianExcess3d),
      explain: `平均三天后比产业链${summaryMetrics.medianExcess3d && summaryMetrics.medianExcess3d > 0 ? '多' : '少'} ${Math.abs(summaryMetrics.medianExcess3d || 0).toFixed(2)} 个百分点。`
    },
    {
      label: 'T+3 不利',
      value: `${formatPp(summaryMetrics.medianAdverse3dProxy, 2)}`,
      valueClass: getValueColorClass(summaryMetrics.medianAdverse3dProxy),
      explain: '不利样本里，三天后通常明显跑输。'
    },
    {
      label: '盈亏比',
      value: formatNumber(summaryMetrics.payoffRatio, 2),
      valueUnit: 'x',
      valueClass: getValueColorClass(summaryMetrics.payoffRatio),
      explain: `赚钱日平均涨幅约为亏损日跌幅的 ${formatNumber(summaryMetrics.payoffRatio, 2)} 倍。`
    },
    {
      label: '夏普',
      value: formatNumber(summaryMetrics.sharpeLikeRatio, 2),
      valueClass: getValueColorClass(summaryMetrics.sharpeLikeRatio),
      explain: '绝对收益的风险调整指标，未减无风险利率。>1 好，>2 优。'
    },
    {
      label: '信号覆盖',
      value: formatPercent((summaryMetrics.signalCoverageRatio ?? 0) * 100, 0),
      valueClass: getValueColorClass(summaryMetrics.signalCoverageRatio),
      explain: '这批历史样本都能归入当前档案。'
    }
  ];

  // 筛选不同类型的模式
  const preferencePatterns = habitPatterns.filter(p => p.habitType === 'likes').slice(0, 5);
  const avoidPatterns = habitPatterns.filter(p => p.habitType === 'dislikes').slice(0, 5);
  const counterPatterns = counterIntuitivePatterns.slice(0, 4);
  const trapPatternsList = trapPatterns.slice(0, 4);

  return (
    <details className="collapsible-section" open>
      <summary>
        <div className="section-title-wrap">
          <h2 className="section-title">历史性格档案</h2>
          <p className="section-note" style={{ marginTop: '6px' }}>这块作为成熟模块保留，承担"长期是什么性格"的主叙事。</p>
        </div>
        <span className="section-meta">{validSampleDays ?? '--'}/{sampleDays ?? '--'} 样本{' · '}{summary?.confidence === 'high' ? '高置信' : summary?.confidence === 'medium' ? '中置信' : '低置信'}</span>
      </summary>

      <div className="profile-top">
        <div className="donut-area">
          <svg className="donut" viewBox="0 0 120 120" role="img" aria-label="性格环形图">
            <circle cx="60" cy="60" r="42" fill="none" stroke="#2b2b2b" strokeWidth="14"/>
            {(() => {
              const d = profile?.donutData ?? {};
              const total = (d.likes ?? 0) + (d.dislikes ?? 0) + (d.counter_intuitive ?? 0) + (d.trap ?? 0) + (d.context ?? 0);
              const C = 264;
              const r = (v: number) => total > 0 ? (v / total) * C : 0;
              const likesArc = r(d.likes ?? 0);
              const dislikesArc = r(d.dislikes ?? 0);
              const contraArc = r(d.counter_intuitive ?? 0);
              const trapArc = r(d.trap ?? 0);
              return <>
                <circle cx="60" cy="60" r="42" fill="none" stroke="#ff4d4f" strokeWidth="14" strokeLinecap="round"
                  strokeDasharray={`${likesArc} ${C - likesArc}`}
                  transform="rotate(-90 60 60)"/>
                <circle cx="60" cy="60" r="42" fill="none" stroke="#20d477" strokeWidth="14" strokeLinecap="round"
                  strokeDasharray={`${dislikesArc} ${C - dislikesArc}`}
                  strokeDashoffset={`${-likesArc}`}
                  transform="rotate(-90 60 60)"/>
                <circle cx="60" cy="60" r="42" fill="none" stroke="#a855f7" strokeWidth="14" strokeLinecap="round"
                  strokeDasharray={`${contraArc} ${C - contraArc}`}
                  strokeDashoffset={`${-(likesArc + dislikesArc)}`}
                  transform="rotate(-90 60 60)"/>
                <circle cx="60" cy="60" r="42" fill="none" stroke="#f97316" strokeWidth="14" strokeLinecap="round"
                  strokeDasharray={`${trapArc} ${C - trapArc}`}
                  strokeDashoffset={`${-(likesArc + dislikesArc + contraArc)}`}
                  transform="rotate(-90 60 60)"/>
              </>;
            })()}
            <text x="60" y="64" textAnchor="middle" fill="#777" fontSize="12">性格</text>
          </svg>
          <div className="chips">
            {profile?.tags?.map?.((tag, index) => (
              <span key={index} className="chip">{tag}</span>
            )) ?? null}
          </div>
        </div>

        <div className="profile-summary">
          <h2>{profile?.title ?? '历史性格档案'}</h2>
          <p>{profile?.description ?? '暂无性格描述'}</p>
        </div>

        <div className="profile-side">
          <div>
            <div className="label">样本</div>
            <div className="value mono">{validSampleDays ?? '--'}<span className="muted" style={{ fontSize: '12px' }}>/{sampleDays ?? '--'}</span></div>
          </div>
          <div>
            <div className="label">置信度</div>
            <div className={`value ${summary?.confidence === 'high' ? 'green' : summary?.confidence === 'medium' ? 'orange' : 'muted'}`} style={{ fontSize: '16px' }}>
              {summary?.confidence === 'high' ? '高' : summary?.confidence === 'medium' ? '中' : '低'}
            </div>
          </div>
          <div>
            <div className="label">基线胜率</div>
            <div className={`value ${getValueColorClass(summaryMetrics?.baselineWinRate1d)} mono`}>{formatWinRate(summaryMetrics?.baselineWinRate1d, 0)}</div>
          </div>
        </div>
      </div>

      <div className="metric-strip">
        {metrics.map((metric, index) => (
          <div key={index} className="metric">
            <div className="label">{metric.label}</div>
            <div className={`value ${metric.valueClass} mono`}>
              {metric.value}{metric.valueUnit && <span style={{ fontSize: '12px', color: 'var(--muted)' }}>{metric.valueUnit}</span>}
            </div>
            <div className="explain">{metric.explain}</div>
          </div>
        ))}
      </div>

      <div className="profile-grid">
        <div className="stack">
          <div className="list-card">
            <h3>偏好环境 <span className="muted">({preferencePatterns?.length ?? 0})</span></h3>
            {preferencePatterns?.map((pattern, index) => {
              const sig = formatSignificance(pattern?.significance);
              const key = `pref-${index}`;
              const isExpanded = expandedKey === key;
              return (
                <div key={key} className="row" onClick={() => toggleExpand(key)}>
                  <span className="name">{pattern?.displayLabel || pattern?.label || '未知信号'}</span>
                  <span className={sig?.class}>{sig?.text}</span>
                  <span className="n">n={pattern?.count ?? 0}</span>
                  <span className={`score ${getValueColorClass(pattern?.avgNext1dDeltaPp)}`}>
                    {pattern?.avgNext1dDeltaPp != null
                      ? `${pattern.avgNext1dDeltaPp > 0 ? '+' : ''}${pattern.avgNext1dDeltaPp.toFixed(2)}`
                      : '--'}
                  </span>
                  <span className="stars">{formatStars(pattern?.effectScore ?? 0)}</span>
                  {isExpanded && (
                    <div className="row-detail" style={{ gridColumn: '1 / -1' }}>
                      {pattern?.avgNext1dExcess != null && <><span className="dl">超额</span> <span className={getValueColorClass(pattern.avgNext1dExcess)}>{formatPp(pattern.avgNext1dExcess)}</span><span className="sep">|</span></>}
                      {pattern?.winRate1d != null && <><span className="dl">胜率</span> {formatWinRate(pattern.winRate1d, 0)}<span className="sep">|</span></>}
                      {pattern?.avgNext3d != null && <><span className="dl">T+3</span> <span className={getValueColorClass(pattern.avgNext3d)}>{formatPp(pattern.avgNext3d)}</span><span className="sep">|</span></>}
                      {pattern?.avgNext5d != null && <><span className="dl">T+5</span> <span className={getValueColorClass(pattern.avgNext5d)}>{formatPp(pattern.avgNext5d)}</span></>}
                      {pattern?.bestCondition && <><br/><span className="dl">最佳</span> {pattern.bestCondition.quadrant} <span className={getValueColorClass(pattern.bestCondition.avgNext1d)}>{formatPp(pattern.bestCondition.avgNext1d)}</span></>}
                      {pattern?.worstCondition && <><span className="sep">|</span><span className="dl">最差</span> {pattern.worstCondition.quadrant} <span className={getValueColorClass(pattern.worstCondition.avgNext1d)}>{formatPp(pattern.worstCondition.avgNext1d)}</span></>}
                      {pattern?.explanation && <><br/>{pattern.explanation}</>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="list-card">
            <h3>规避环境 <span className="muted">({avoidPatterns?.length ?? 0})</span></h3>
            {avoidPatterns?.map((pattern, index) => {
              const sig = formatSignificance(pattern?.significance);
              const key = `avoid-${index}`;
              const isExpanded = expandedKey === key;
              return (
                <div key={key} className="row green-line" onClick={() => toggleExpand(key)}>
                  <span className="name">{pattern?.displayLabel || pattern?.label || '未知信号'}</span>
                  <span className={sig?.class}>{sig?.text}</span>
                  <span className="n">n={pattern?.count ?? 0}</span>
                  <span className={`score ${getValueColorClass(pattern?.avgNext1dDeltaPp)}`}>
                    {pattern?.avgNext1dDeltaPp != null
                      ? `${pattern.avgNext1dDeltaPp > 0 ? '+' : ''}${pattern.avgNext1dDeltaPp.toFixed(2)}`
                      : '--'}
                  </span>
                  <span className="stars">{formatStars(pattern?.effectScore ?? 0)}</span>
                  {isExpanded && (
                    <div className="row-detail" style={{ gridColumn: '1 / -1' }}>
                      {pattern?.avgNext1dExcess != null && <><span className="dl">超额</span> <span className={getValueColorClass(pattern.avgNext1dExcess)}>{formatPp(pattern.avgNext1dExcess)}</span><span className="sep">|</span></>}
                      {pattern?.winRate1d != null && <><span className="dl">胜率</span> {formatWinRate(pattern.winRate1d, 0)}<span className="sep">|</span></>}
                      {pattern?.avgNext3d != null && <><span className="dl">T+3</span> <span className={getValueColorClass(pattern.avgNext3d)}>{formatPp(pattern.avgNext3d)}</span><span className="sep">|</span></>}
                      {pattern?.avgNext5d != null && <><span className="dl">T+5</span> <span className={getValueColorClass(pattern.avgNext5d)}>{formatPp(pattern.avgNext5d)}</span></>}
                      {pattern?.bestCondition && <><br/><span className="dl">最佳</span> {pattern.bestCondition.quadrant} <span className={getValueColorClass(pattern.bestCondition.avgNext1d)}>{formatPp(pattern.bestCondition.avgNext1d)}</span></>}
                      {pattern?.worstCondition && <><span className="sep">|</span><span className="dl">最差</span> {pattern.worstCondition.quadrant} <span className={getValueColorClass(pattern.worstCondition.avgNext1d)}>{formatPp(pattern.worstCondition.avgNext1d)}</span></>}
                      {pattern?.explanation && <><br/>{pattern.explanation}</>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="list-card">
            <h3>产业联动关系</h3>
            <div className="relation-row">
              <span>{POOL.industry_chain.short}</span>
              <span className="badge blue">{formatRelationType(relationshipProfile?.anchorVsChain?.relation)}</span>
              <span className={`${getValueColorClass(relationshipProfile?.anchorVsChain?.avgRelativeStrength)} mono`}>
                {formatPp(relationshipProfile?.anchorVsChain?.avgRelativeStrength, 2)}
              </span>
              <span className="muted">r={relationshipProfile?.anchorVsChain?.sameDayCorr?.toFixed(2) ?? '--'}</span>
            </div>
            <div className="relation-row">
              <span>{POOL.theme_pool.short}</span>
              <span className="badge blue">{formatRelationType(relationshipProfile?.anchorVsTheme?.relation)}</span>
              <span className={`${getValueColorClass(relationshipProfile?.anchorVsTheme?.avgRelativeStrength)} mono`}>
                {formatPp(relationshipProfile?.anchorVsTheme?.avgRelativeStrength, 2)}
              </span>
              <span className="muted">r={relationshipProfile?.anchorVsTheme?.sameDayCorr?.toFixed(2) ?? '--'}</span>
            </div>
            <div className="relation-row">
              <span>{POOL.direct_peers.short}</span>
              <span className="badge blue">{formatRelationType(relationshipProfile?.anchorVsCore?.relation)}</span>
              <span className={`${getValueColorClass(relationshipProfile?.anchorVsCore?.avgRelativeStrength)} mono`}>
                {formatPp(relationshipProfile?.anchorVsCore?.avgRelativeStrength, 2)}
              </span>
              <span className="muted">r={relationshipProfile?.anchorVsCore?.sameDayCorr?.toFixed(2) ?? '--'}</span>
            </div>
            <div className="relation-row">
              <span>{POOL.trading_watchlist.short}</span>
              <span className="badge blue">{formatRelationType(relationshipProfile?.anchorVsTradingWatchlist?.relation)}</span>
              <span className={`${getValueColorClass(relationshipProfile?.anchorVsTradingWatchlist?.avgRelativeStrength)} mono`}>
                {formatPp(relationshipProfile?.anchorVsTradingWatchlist?.avgRelativeStrength, 2)}
              </span>
              <span className="muted">r={relationshipProfile?.anchorVsTradingWatchlist?.sameDayCorr?.toFixed(2) ?? '--'}</span>
            </div>
          </div>
        </div>

        <div className="stack">
          <div className="list-card">
            <h3>反直觉机会 <span className="muted">({counterPatterns?.length ?? 0})</span></h3>
            {counterPatterns?.map((pattern, index) => {
              const key = `contra-${index}`;
              const isExpanded = expandedKey === key;
              return (
                <div key={key} className="row purple-line" onClick={() => toggleExpand(key)}>
                  <span className="name">{pattern?.displayLabel || pattern?.label || '未知信号'}</span>
                  <span className="badge purple">反直觉</span>
                  <span className="n">n={pattern?.appearanceCount ?? 0}</span>
                  <span className={`score ${getValueColorClass(pattern?.avgNext1dDeltaPp)}`}>
                    {pattern?.avgNext1dDeltaPp != null
                      ? `${pattern.avgNext1dDeltaPp > 0 ? '+' : ''}${pattern.avgNext1dDeltaPp.toFixed(2)}`
                      : '--'}
                  </span>
                  <span className="stars">{formatStars(pattern?.degree ? Math.min(Math.round(pattern.degree / 2), 5) : 0)}</span>
                  {isExpanded && (
                    <div className="row-detail" style={{ gridColumn: '1 / -1' }}>
                      {pattern?.winRate1d != null && <><span className="dl">胜率</span> {formatWinRate(pattern.winRate1d, 0)}<span className="sep">|</span></>}
                      <><span className="dl">直觉</span> {pattern?.intuitiveDirection === 'positive' ? '正面' : pattern?.intuitiveDirection === 'negative' ? '负面' : '中性'}<span className="sep">|</span></>
                      <><span className="dl">实际</span> {pattern?.actualDirection === 'positive' ? '正面' : pattern?.actualDirection === 'negative' ? '负面' : '中性'}<span className="sep">|</span></>
                      {pattern?.degree != null && <><span className="dl">偏差</span> {pattern.degree.toFixed(2)}</>}
                      {pattern?.explanation && <><br/>{pattern.explanation}</>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="list-card">
            <h3>信号陷阱 <span className="muted">({trapPatternsList?.length ?? 0})</span></h3>
            {trapPatternsList?.map((pattern, index) => {
              const key = `trap-${index}`;
              const isExpanded = expandedKey === key;
              return (
                <div key={key} className="row orange-line" onClick={() => toggleExpand(key)}>
                  <span className="name">{pattern?.displayLabel || pattern?.label || '未知信号'}</span>
                  <span className="badge amber">陷阱</span>
                  <span className="n">n={pattern?.appearanceCount ?? 0}</span>
                  <span className={`score ${getValueColorClass(pattern?.avgNext1dDeltaPp)}`}>
                    {pattern?.avgNext1dDeltaPp != null
                      ? `${pattern.avgNext1dDeltaPp > 0 ? '+' : ''}${pattern.avgNext1dDeltaPp.toFixed(2)}`
                      : '--'}
                  </span>
                  <span className="stars">{formatStars(pattern?.degree ? Math.min(Math.round(pattern.degree / 2), 5) : 0)}</span>
                  {isExpanded && (
                    <div className="row-detail" style={{ gridColumn: '1 / -1' }}>
                      {pattern?.winRate1d != null && <><span className="dl">胜率</span> {formatWinRate(pattern.winRate1d, 0)}<span className="sep">|</span></>}
                      <><span className="dl">直觉</span> {pattern?.intuitiveDirection === 'positive' ? '正面' : pattern?.intuitiveDirection === 'negative' ? '负面' : '中性'}<span className="sep">|</span></>
                      <><span className="dl">实际</span> {pattern?.actualDirection === 'positive' ? '正面' : pattern?.actualDirection === 'negative' ? '负面' : '中性'}<span className="sep">|</span></>
                      {pattern?.degree != null && <><span className="dl">偏差</span> {pattern.degree.toFixed(2)}</>}
                      {pattern?.explanation && <><br/>{pattern.explanation}</>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="path-pattern-card">
            <h3>历史路径特征</h3>
            <div className="path-pattern-tabs">
              {pathPatterns?.slice(0, 6).map((pattern, index) => (
                <button
                  key={pattern.eventLabel}
                  type="button"
                  className={`path-pattern-tab ${index === activePatternIndex ? 'active' : ''}`}
                  onClick={() => setActivePatternIndex(index)}
                >
                  {pattern.eventLabel} <span>{pattern.count}</span>
                </button>
              ))}
            </div>
            <div className="path-pattern-box">
              <svg className="path-pattern-svg" viewBox="0 0 760 260" role="img" aria-label="历史路径特征">
                <rect x="0" y="0" width="760" height="260" fill="#111111"/>
                <line x1="30" y1="135" x2="730" y2="135" stroke="#282828" />
                <path d={`M ${pathPoints(activePath, 'anchorReturn')}`} fill="none" stroke="#ff4d4f" strokeWidth={2} strokeLinecap="round"/>
                <path d={`M ${pathPoints(activePath, 'chainMedian')}`} fill="none" stroke="#6b7280" strokeWidth={2} strokeLinecap="round" strokeDasharray="4 3"/>
                <path d={`M ${pathPoints(activePath, 'excess')}`} fill="none" stroke="#20d477" strokeWidth={2} strokeLinecap="round" strokeDasharray="5 3"/>
                {pathCoords(activePath, 'anchorReturn').map((c, i) => <circle key={`a${i}`} cx={c.x} cy={c.y} r={3} fill="#ff4d4f"/>)}
                {pathCoords(activePath, 'chainMedian').map((c, i) => <circle key={`c${i}`} cx={c.x} cy={c.y} r={2.2} fill="#6b7280"/>)}
                {pathCoords(activePath, 'excess').map((c, i) => <circle key={`e${i}`} cx={c.x} cy={c.y} r={2.2} fill="#20d477"/>)}
                <g fill="#666" fontSize={11} textAnchor="middle">
                  {offsetLabels.map((point, index) => (
                    <text key={point.offset} x={30 + (index / Math.max(offsetLabels.length - 1, 1)) * 700} y="245">
                      {point.offset > 0 ? `+${point.offset}` : point.offset}
                    </text>
                  ))}
                </g>
              </svg>
              <div className="path-pattern-footer">
                <div className="path-pattern-legend">
                  <span><i style={{background:'#ff4d4f'}}></i>个股</span>
                  <span><i style={{background:'repeating-linear-gradient(90deg,#6b7280 0,#6b7280 4px,transparent 4px,transparent 7px)'}}></i>板块</span>
                  <span><i style={{background:'repeating-linear-gradient(90deg,#20d477 0,#20d477 5px,transparent 5px,transparent 8px)'}}></i>超额</span>
                </div>
                <div className="path-pattern-summary">{activePattern?.summary || `${activePattern?.eventLabel ?? '暂无事件'} · n=${activePattern?.count ?? 0}`}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </details>
  );
}
