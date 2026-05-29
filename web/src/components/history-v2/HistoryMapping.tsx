"use client";

import { useRef, useEffect, useState, Fragment } from 'react';
import { createChart, ColorType, LineSeries, createSeriesMarkers, CrosshairMode } from 'lightweight-charts';
import type { DashboardView } from '@/types/dashboard-view';
import { formatPercent, formatWinRate, formatSimilarity, getValueColorClass, formatPathLabel, formatDate, formatNumber } from '@/lib/history-v2/formatters';

interface DailyMetric {
  title?: string;
  label?: string;
  value: string | number;
  description: string;
}

interface HistoryMappingProps {
  currentMapping: DashboardView['summary']['currentMapping'];
  pathLabel: DashboardView['summary']['pathLabel'];
  similarCases: DashboardView['tableData']['similarCases'];
  windowStats: DashboardView['tableData']['windowStats'];
  priceHistory: DashboardView['trends']['excessReturn'];
  dailyMetrics: DailyMetric[];
  confidenceIntervals?: DashboardView['predictionEvaluation']['confidenceIntervals'];
  scoreBucketStats?: DashboardView['scoreBucketStats'];
}

interface HoverState {
  date: string;
  price: number | null;
  similarity: number | null;
  next1dReturn: number | null;
  next3dReturn: number | null;
  next5dReturn: number | null;
}

function formatPct(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? '--' : `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function formatPrice(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? '--' : value.toFixed(2);
}

export default function HistoryMapping({ currentMapping, pathLabel, similarCases, windowStats, priceHistory, dailyMetrics, confidenceIntervals, scoreBucketStats }: HistoryMappingProps) {
  const mappingTags = currentMapping?.tags ?? currentMapping?.signalLabels ?? [];
  const casesToShow = similarCases?.slice?.(0, 5) ?? [];
  const allCases = similarCases ?? [];

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<HoverState | null>(null);

  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container || !priceHistory?.length) return;

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#666',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#1f1f1f' },
        horzLines: { color: '#252525' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#555', width: 1, style: 2, labelBackgroundColor: '#333' },
        horzLine: { color: '#555', width: 1, style: 2, labelBackgroundColor: '#333' },
      },
      leftPriceScale: { borderColor: '#282828', visible: true },
      rightPriceScale: { borderColor: '#282828', visible: true },
      timeScale: {
        borderColor: '#282828',
        timeVisible: false,
        fixLeftEdge: true,
        fixRightEdge: true,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        vertTouchDrag: false,
      },
    });

    // 股价线（左轴）
    const priceSeries = chart.addSeries(LineSeries, {
      color: '#f59e0b',
      lineWidth: 2,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerRadius: 3,
      priceScaleId: 'left',
    });
    const priceLineData = priceHistory
      .filter(row => row.price != null && Number.isFinite(row.price))
      .map(row => ({
        time: `${row.date.slice(0, 4)}-${row.date.slice(4, 6)}-${row.date.slice(6, 8)}`,
        value: row.price as number,
      }));
    priceSeries.setData(priceLineData);

    // 相似度散点（右轴）- 使用 markers 实现默认可见的点
    allCases.forEach(c => {
      if (!c?.date) return;
      const radius = (c.similarity ?? 0) >= 0.82 ? 8 : (c.similarity ?? 0) >= 0.68 ? 5 : 3;
      const simSeries = chart.addSeries(LineSeries, {
        color: 'transparent',
        lineWidth: 0,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerRadius: radius,
        priceScaleId: 'right',
      });
      const timeStr = `${c.date.slice(0, 4)}-${c.date.slice(4, 6)}-${c.date.slice(6, 8)}`;
      simSeries.setData([{ time: timeStr, value: c.similarity }]);
      // 使用 markers 让点默认可见
      createSeriesMarkers(simSeries, [{
        time: timeStr,
        position: 'belowBar',
        color: '#3b82f6',
        shape: 'circle',
        size: radius > 6 ? 3 : radius > 4 ? 2 : 1,
      }]);
    });

    chart.priceScale('left').applyOptions({
      scaleMargins: { top: 0.05, bottom: 0.05 },
      borderColor: '#282828',
    });
    chart.priceScale('right').applyOptions({
      scaleMargins: { top: 0.05, bottom: 0.05 },
      borderColor: '#282828',
    });

    // Hover 交互
    const caseByDate: Record<string, typeof allCases[number]> = {};
    allCases.forEach(c => {
      if (c?.date) {
        const key = `${c.date.slice(0, 4)}-${c.date.slice(4, 6)}-${c.date.slice(6, 8)}`;
        caseByDate[key] = c;
      }
    });

    const handler = (param: any) => {
      if (!param.time || !param.point) {
        setHover(null);
        return;
      }
      const dateStr = typeof param.time === 'string' ? param.time : '';
      const priceVal = param.seriesData.get(priceSeries);
      const pv = priceVal && 'value' in priceVal ? (priceVal as any).value : null;
      const matchedCase = caseByDate[dateStr];
      setHover({
        date: dateStr,
        price: pv,
        similarity: matchedCase?.similarity ?? null,
        next1dReturn: matchedCase?.next1dReturn ?? null,
        next3dReturn: matchedCase?.next3dReturn ?? null,
        next5dReturn: matchedCase?.next5dReturn ?? null,
      });
    };
    chart.subscribeCrosshairMove(handler);

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        chart.applyOptions({ width, height });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.unsubscribeCrosshairMove(handler);
      chart.remove();
    };
  }, [priceHistory, allCases]);

  return (
    <details className="collapsible-section" open>
      <summary>
        <div className="section-title-wrap">
          <h2 className="section-title">今日历史映射</h2>
          <p className="section-note" style={{ marginTop: '6px' }}>把选定日期的整体状态放回历史样本中，观察相似状态后的路径分布，不代表预测。</p>
        </div>
        <span className="section-meta">相似样本 {currentMapping?.similarSampleCount ?? 0} 个</span>
      </summary>

      <div className="mapping-current">
        <div className="mapping-current-head">
          <span className="mapping-date mono">{currentMapping?.date}</span>
          <span className="mapping-state">{currentMapping?.state}</span>
        </div>
        <div className="mapping-tags">
          {mappingTags.map((tag, index) => (
            <span key={index} className="mapping-tag">{tag}</span>
          ))}
        </div>
      </div>

      {dailyMetrics?.length > 0 && (
        <div className="daily-metrics">
          {dailyMetrics.map((metric, index) => (
            <div key={index} className="daily-metric">
              <div className="daily-metric-label">{metric.title ?? metric.label ?? ''}</div>
              <div className={`daily-metric-value ${typeof metric.value === 'string' && (metric.value.includes('弱') || metric.value === '弱') ? 'red' : typeof metric.value === 'string' && (metric.value.includes('强') || metric.value === '强') ? 'green' : ''}`}>{metric.value}</div>
              <div className="daily-metric-desc">{metric.description}</div>
            </div>
          ))}
        </div>
      )}

      {/* 同档历史统计 */}
      {scoreBucketStats && scoreBucketStats.length > 0 && (() => {
        const latest = scoreBucketStats[scoreBucketStats.length - 1];
        const currentBucket = latest.bucketLabel;
        const currentScore = latest.score;
        const sampleSize = latest.sampleSize;
        const t1 = latest.t1;
        const t3 = latest.t3;
        const t5 = latest.t5;
        const sw1 = latest.stateWeightedT1;
        const sw3 = latest.stateWeightedT3;
        const sw5 = latest.stateWeightedT5;
        const hasMismatch = latest.stateMismatch === true && (latest.stateDivergence ?? 0) > 0.5;
        const hasWeightedData = sw1 != null;

        const fmtPct = (v: number | null | undefined) => {
          if (v == null || Number.isNaN(v)) return '--';
          return `${v > 0 ? '+' : ''}${v.toFixed(2)}%`;
        };
        const fmtRate = (v: number | null | undefined) => {
          if (v == null || Number.isNaN(v)) return '--';
          return `${(v * 100).toFixed(0)}%`;
        };
        // A股配色：红涨绿跌
        const cls = (v: number | null | undefined) => {
          if (v == null) return '';
          return v > 0 ? 'red' : v < 0 ? 'green' : '';
        };

        const STATE_ZH: Record<string, string> = {
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

        const directionReversed = hasMismatch && hasWeightedData
          && t1?.avgExcess != null && sw1?.avgExcess != null
          && Math.sign(sw1.avgExcess) !== Math.sign(t1.avgExcess);

        return (
          <div style={{ marginTop: '12px' }}>
            <h3 style={{ fontSize: '13px', marginBottom: '8px', color: 'var(--text-secondary)' }}>
              同档历史统计
              <span style={{ marginLeft: '8px', fontSize: '11px', color: 'var(--muted)' }}>
                当前评分 {currentScore > 0 ? '+' : ''}{currentScore}（{currentBucket}档，n={sampleSize}）
              </span>
            </h3>
            <table className="mini-table" aria-label="同档历史统计">
              <thead>
                <tr><th>窗口</th><th>超额均值</th><th>超额胜率</th><th>个股均值</th><th>个股胜率</th></tr>
              </thead>
              <tbody>
                {[
                  { label: 'T+1', stat: t1, weightedStat: sw1 },
                  { label: 'T+3', stat: t3, weightedStat: sw3 },
                  { label: 'T+5', stat: t5, weightedStat: sw5 },
                ].map(({ label, stat, weightedStat }) => (
                  <Fragment key={label}>
                    <tr>
                      <td>{label}</td>
                      <td className={cls(stat?.avgExcess)}>{fmtPct(stat?.avgExcess)}</td>
                      <td>{fmtRate(stat?.excessPosRate)}</td>
                      <td className={cls(stat?.avgAbsReturn)}>{fmtPct(stat?.avgAbsReturn)}</td>
                      <td>{fmtRate(stat?.absPosRate)}</td>
                    </tr>
                    {hasMismatch && weightedStat && (
                      <tr style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                        <td style={{ paddingLeft: '16px' }}>└ 加权</td>
                        <td className={cls(weightedStat?.avgExcess)}>{fmtPct(weightedStat?.avgExcess)}</td>
                        <td>{fmtRate(weightedStat?.excessPosRate)}</td>
                        <td className={cls(weightedStat?.avgAbsReturn)}>{fmtPct(weightedStat?.avgAbsReturn)}</td>
                        <td>{fmtRate(weightedStat?.absPosRate)}</td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
            <div style={{ fontSize: '11px', color: 'var(--muted)', marginTop: '4px' }}>
              超额 = 个股 vs 行业链，个股 = 绝对涨跌；均值 = 平均幅度，胜率 = 涨的比例。同档所有历史日统计，Walk-Forward 仅用当日之前数据
              {hasMismatch && hasWeightedData && '；加权行按状态相似度调整，有效样本 ' + (latest.effectiveSampleSize?.toFixed(1) ?? '--')}
            </div>
            {hasMismatch && (
              <div style={{
                margin: '8px 0',
                padding: '8px 12px',
                borderRadius: '6px',
                borderLeft: '3px solid var(--amber)',
                background: 'var(--amber-soft)',
                fontSize: '12px',
                lineHeight: '1.6',
              }}>
                <strong>状态偏离提醒</strong>：当前状态为
                <span style={{ color: 'var(--text)' }}>
                  {STATE_ZH[latest.currentState ?? ''] ?? latest.currentState}
                </span>
                ，同档 {sampleSize} 个历史日中
                {STATE_ZH[latest.dominantState ?? ''] ?? latest.dominantState}
                占多数，分档统计已被状态相似度加权调整。偏离度
                {((latest.stateDivergence ?? 0) * 100).toFixed(0)}%，有效样本
                {latest.effectiveSampleSize?.toFixed(1)}。
                {directionReversed && (
                  <span style={{ color: 'var(--amber)' }}>
                    {' '}加权后方向反转：原始 T+1 {fmtPct(t1?.avgExcess)} → 加权 {fmtPct(sw1?.avgExcess)}
                  </span>
                )}
              </div>
            )}
            {directionReversed && (
              <div style={{ fontSize: '11px', color: 'var(--amber)', marginTop: '6px' }}>
                注意：状态加权后 T+1 方向与原始分档统计相反，建议以下方「最相似历史案例」为准
              </div>
            )}
          </div>
        );
      })()}

      {(() => {
        const pathInfo = formatPathLabel(pathLabel);
        return (
          <span className="path-label">{pathInfo.text}</span>
        );
      })()}

      <table className="mini-table" aria-label="历史路径统计">
        <thead>
          <tr><th>窗口</th><th>平均收益</th><th>置信区间</th><th>胜率</th><th>平均超额</th></tr>
        </thead>
        <tbody>
          {windowStats?.length > 0 ? (
            windowStats.map((stat) => {
              const ci = confidenceIntervals?.find(c => c.window === stat.window);
              return (
                <tr key={stat.window}>
                  <td>T+{stat?.window === '1d' ? '1' : stat?.window === '3d' ? '3' : '5'}</td>
                  <td className={getValueColorClass(stat?.avgReturn)}>
                    {formatPercent(stat?.avgReturn)}
                    {stat?.avgReturn != null && (stat.avgReturn > 0 ? ' ↑' : stat.avgReturn < 0 ? ' ↓' : '')}
                  </td>
                  <td style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                    {ci ? `[${formatPct(ci.lowerBound)}, ${formatPct(ci.upperBound)}]` : '--'}
                  </td>
                  <td>{formatWinRate(stat?.winRate)}</td>
                  <td className={getValueColorClass(stat?.avgExcess)}>
                    {formatPercent(stat?.avgExcess)}
                    {stat?.avgExcess != null && (stat.avgExcess > 0 ? ' ↑' : stat.avgExcess < 0 ? ' ↓' : '')}
                  </td>
                </tr>
              );
            })
          ) : (
            <tr>
              <td colSpan={5} style={{ textAlign: 'center', color: 'var(--muted)', padding: '20px' }}>
                暂无统计数据
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {/* 新增：相似案例折线图 */}
      <div className="chart-card" style={{ marginTop: '12px' }}>
        <div className="chart-title">
          <span>相似案例分布</span>
          <span className="muted">蓝点=相似度（右轴，大小=相似度）</span>
        </div>
        <div ref={chartContainerRef} className="chart-container" />
        {hover ? (
          <div className="chart-note">
            <strong>{hover.date}</strong>
            {' · '}股价 {formatPrice(hover.price)}
            {hover.similarity != null && (
              <>
                {' · '}相似度 <span style={{ color: 'var(--blue)' }}>{hover.similarity.toFixed(2)}</span>
                {' · '}T+1 <span className={getValueColorClass(hover.next1dReturn)}>{formatPct(hover.next1dReturn)}</span>
                {' · '}T+3 <span className={getValueColorClass(hover.next3dReturn)}>{formatPct(hover.next3dReturn)}</span>
                {' · '}T+5 <span className={getValueColorClass(hover.next5dReturn)}>{formatPct(hover.next5dReturn)}</span>
              </>
            )}
          </div>
        ) : (
          <div className="chart-note"><strong>读法：</strong>琥珀色虚线为股价（左轴）；蓝色圆点越大概率越高（右轴）；hover 蓝点查看案例后续收益。滚轮缩放，拖拽平移。</div>
        )}
        <div className="legend">
          <span><i style={{ background: '#f59e0b' }}></i>股价</span>
          <span><i style={{ background: '#3b82f6', borderRadius: '50%', width: '6px', height: '6px' }}></i>相似度</span>
        </div>
      </div>

      <div className="case-list-title">最相似历史案例</div>
      {casesToShow.length > 0 ? (
        casesToShow.map((caseItem, index) => (
          <div key={index} className="mapping-case">
            <div className="mapping-case-head">
              <span className="mapping-case-date mono">{caseItem?.date}</span>
              <span className="mapping-similarity mono">{formatSimilarity(caseItem?.similarity)}</span>
            </div>
            <div className="mapping-tags">
              {caseItem?.matchingStates?.slice?.(0, 5)?.map?.((label: string, i: number) => (
                <span key={`s-${i}`} className="badge blue">{label}</span>
              )) ?? null}
              {caseItem?.matchingSignals?.slice?.(0, 4)?.map?.((label: string, i: number) => (
                <span key={`sig-${i}`} className="mapping-tag">{label}</span>
              ))}
              {(caseItem?.matchingSignals?.length ?? 0) > 4 && (
                <span className="muted">+{caseItem.matchingSignals.length - 4}</span>
              )}
            </div>
            <div className="mapping-case-values">
              <div>
                <span className="muted">T+1</span>
                <span className={`${getValueColorClass(caseItem?.next1dReturn)} mono`} style={{ marginLeft: '8px' }}>
                  {formatPercent(caseItem?.next1dReturn)}
                </span>
              </div>
              <div>
                <span className="muted">T+3</span>
                <span className={`${getValueColorClass(caseItem?.next3dReturn)} mono`} style={{ marginLeft: '8px' }}>
                  {formatPercent(caseItem?.next3dReturn)}
                </span>
              </div>
              <div>
                <span className="muted">T+5</span>
                <span className={`${getValueColorClass(caseItem?.next5dReturn)} mono`} style={{ marginLeft: '8px' }}>
                  {formatPercent(caseItem?.next5dReturn)}
                </span>
              </div>
            </div>
          </div>
        ))
      ) : (
        <div style={{ textAlign: 'center', color: 'var(--muted)', padding: '40px' }}>
          暂无相似案例
        </div>
      )}
    </details>
  );
}
