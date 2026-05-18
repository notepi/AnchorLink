"use client";

import { useRef, useEffect, useState } from 'react';
import { createChart, ColorType, LineSeries } from 'lightweight-charts';
import type { DashboardView } from '@/types/dashboard-view';
import { formatPercent, formatWinRate, formatSimilarity, getValueColorClass, formatPathLabel, formatDate, formatNumber } from '@/lib/history-v2/formatters';

interface HistoryMappingProps {
  currentMapping: DashboardView['summary']['currentMapping'];
  pathLabel: DashboardView['summary']['pathLabel'];
  similarCases: DashboardView['tableData']['similarCases'];
  windowStats: DashboardView['tableData']['windowStats'];
  priceHistory: DashboardView['trends']['excessReturn'];
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

export default function HistoryMapping({ currentMapping, pathLabel, similarCases, windowStats, priceHistory }: HistoryMappingProps) {
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
        mode: 0,
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

    // 相似度散点（右轴）- 每个 case 独立 series，无连线
    allCases.forEach(c => {
      if (!c?.date) return;
      const radius = (c.similarity ?? 0) >= 0.82 ? 8 : (c.similarity ?? 0) >= 0.68 ? 5 : 3;
      const simSeries = chart.addSeries(LineSeries, {
        color: '#3b82f6',
        lineWidth: 0,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerRadius: radius,
        crosshairMarkerBorderColor: '#3b82f6',
        crosshairMarkerBackgroundColor: '#3b82f6',
        priceScaleId: 'right',
        pointMarkersVisible: true,
        pointMarkersRadius: radius,
      });
      simSeries.setData([{
        time: `${c.date.slice(0, 4)}-${c.date.slice(4, 6)}-${c.date.slice(6, 8)}`,
        value: c.similarity,
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

      {(() => {
        const pathInfo = formatPathLabel(pathLabel);
        return (
          <span className="path-label">{pathInfo.text}</span>
        );
      })()}

      <table className="mini-table" aria-label="历史路径统计">
        <thead>
          <tr><th>窗口</th><th>平均收益</th><th>胜率</th><th>平均超额</th></tr>
        </thead>
        <tbody>
          {windowStats?.length > 0 ? (
            windowStats.map((stat) => (
              <tr key={stat.window}>
                <td>T+{stat?.window === '1d' ? '1' : stat?.window === '3d' ? '3' : '5'}</td>
                <td className={getValueColorClass(stat?.avgReturn)}>
                  {formatPercent(stat?.avgReturn)}
                  {stat?.avgReturn != null && (stat.avgReturn > 0 ? ' ↑' : stat.avgReturn < 0 ? ' ↓' : '')}
                </td>
                <td>{formatWinRate(stat?.winRate)}</td>
                <td className={getValueColorClass(stat?.avgExcess)}>
                  {formatPercent(stat?.avgExcess)}
                  {stat?.avgExcess != null && (stat.avgExcess > 0 ? ' ↑' : stat.avgExcess < 0 ? ' ↓' : '')}
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={4} style={{ textAlign: 'center', color: 'var(--muted)', padding: '20px' }}>
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
