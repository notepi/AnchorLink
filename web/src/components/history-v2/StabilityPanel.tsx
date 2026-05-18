"use client";

import { useRef, useEffect, useState } from 'react';
import { createChart, ColorType, LineSeries } from 'lightweight-charts';
import type { DashboardView } from '@/types/dashboard-view';
import { POOL } from '@/lib/glossary';

interface StabilityPanelProps {
  stabilityData: DashboardView['personality']['stability'];
  excessReturnData: DashboardView['trends']['excessReturn'];
  followDeviationData: DashboardView['trends']['followDeviation'];
}

function latest<T>(items: T[] | undefined): T | undefined {
  return items?.[items.length - 1];
}

function formatPct(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? '--' : `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function formatPrice(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? '--' : value.toFixed(2);
}

function getTrend(value: number | null | undefined) {
  if (value == null) return { text: '无数据', class: 'muted' };
  if (value > 2) return { text: '偏强', class: 'red' };
  if (value < -2) return { text: '偏弱', class: 'green' };
  return { text: '震荡', class: '' };
}

type Row = Record<string, any>;

function toSeriesData(data: Row[] | undefined, key: string) {
  if (!data) return [];
  return data
    .filter(row => row[key] != null && Number.isFinite(row[key]))
    .map(row => ({
      time: `${row.date.slice(0, 4)}-${row.date.slice(4, 6)}-${row.date.slice(6, 8)}` as string,
      value: row[key] as number,
    }));
}

interface HoverState {
  date: string;
  values: Record<string, number | null>;
}

type SeriesConfig = {
  key: string;
  color: string;
  dashed?: boolean;
  lineWidth?: 1 | 2 | 3 | 4;
  priceScaleId?: string;
};

const EXCESS_SERIES: SeriesConfig[] = [
  { key: 'price', color: '#f59e0b', lineWidth: 1, dashed: true, priceScaleId: 'left' },
  { key: 'excess10d', color: '#8b5cf6', dashed: true, priceScaleId: 'right' },
  { key: 'excess5d', color: '#3b82f6', priceScaleId: 'right' },
  { key: 'outperformStreak', color: '#ff4d4f', priceScaleId: 'right' },
];

const DEVIATION_SERIES: SeriesConfig[] = [
  { key: 'price', color: '#f59e0b', lineWidth: 1, dashed: true, priceScaleId: 'left' },
  { key: 'anchor', color: '#ff4d4f', lineWidth: 2, priceScaleId: 'right' },
  { key: 'industry', color: '#3b82f6', dashed: true, lineWidth: 2, priceScaleId: 'right' },
  { key: 'excess', color: '#8b5cf6', priceScaleId: 'right' },
];

function useChart(
  containerRef: React.RefObject<HTMLDivElement | null>,
  seriesConfigs: SeriesConfig[],
  data: Row[] | undefined,
  onHover: (hover: HoverState | null) => void,
) {
  const onHoverRef = useRef(onHover);
  onHoverRef.current = onHover;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

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

    const seriesList = seriesConfigs.map(cfg => {
      const series = chart.addSeries(LineSeries, {
        color: cfg.color,
        lineWidth: cfg.lineWidth ?? 2,
        lineStyle: cfg.dashed ? 2 : 0,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerRadius: 3,
        priceScaleId: cfg.priceScaleId,
      });
      series.setData(toSeriesData(data, cfg.key));
      return { series, key: cfg.key };
    });

    chart.priceScale('left').applyOptions({
      scaleMargins: { top: 0.1, bottom: 0.1 },
      borderColor: '#282828',
    });
    chart.priceScale('right').applyOptions({
      scaleMargins: { top: 0.1, bottom: 0.1 },
      borderColor: '#282828',
    });

    const handler = (param: any) => {
      if (!param.time || !param.point) {
        onHoverRef.current(null);
        return;
      }
      const dateStr = typeof param.time === 'string' ? param.time : '';
      const values: Record<string, number | null> = {};
      seriesList.forEach(({ series, key }) => {
        const dataPoint = param.seriesData.get(series);
        values[key] = dataPoint && 'value' in dataPoint ? (dataPoint as any).value : null;
      });
      onHoverRef.current({ date: dateStr, values });
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);
}

export default function StabilityPanel({
  stabilityData,
  excessReturnData,
  followDeviationData
}: StabilityPanelProps) {
  const latestExcess = latest(excessReturnData);
  const latestDeviation = latest(followDeviationData);

  const statusMap: Record<string, { text: string; class: string }> = {
    stable: { text: '稳定', class: 'green' },
    changed: { text: '变化中', class: 'amber' },
    insufficient: { text: '样本不足', class: 'muted' }
  };

  const excess5dTrend = getTrend(latestExcess?.excess5d);
  const excess10dTrend = getTrend(latestExcess?.excess10d);
  const deviationTrend = getTrend(latestDeviation?.deviation);

  const excessChartRef = useRef<HTMLDivElement>(null);
  const deviationChartRef = useRef<HTMLDivElement>(null);
  const [excessHover, setExcessHover] = useState<HoverState | null>(null);
  const [deviationHover, setDeviationHover] = useState<HoverState | null>(null);

  useChart(excessChartRef, EXCESS_SERIES, excessReturnData, setExcessHover);
  useChart(deviationChartRef, DEVIATION_SERIES, followDeviationData, setDeviationHover);

  return (
    <details className="collapsible-section" open>
      <summary>
        <div className="section-title-wrap">
          <h2 className="section-title">近期稳定性</h2>
          <p className="section-note" style={{ marginTop: '6px' }}>不用读每个波峰波谷，只看判断是否连续跑赢{POOL.industry_chain.short}，以及今天是不是异常偏离。</p>
        </div>
        <span className="section-meta">稳定性{statusMap[stabilityData?.status]?.text ?? '未知'}</span>
      </summary>
      <div className="stability-summary">
        <div className="stability-verdict">
          <h3>当前结论</h3>
          <p>
            稳定性{statusMap[stabilityData?.status]?.text ?? '未知'}：
            {stabilityData?.earlyVsRecentNotes?.[0] ??
              '近 5/10 日超额没有持续抬升，今天仍更像跟随主线波动，而不是独立走强。'}
          </p>
        </div>
        <div className="stability-metric">
          <h3>5日超额</h3>
          <div className={`value ${excess5dTrend.class}`}>{excess5dTrend.text}</div>
          <p>当前值：{formatPct(latestExcess?.excess5d)}</p>
        </div>
        <div className="stability-metric">
          <h3>10日超额</h3>
          <div className={`value ${excess10dTrend.class}`}>{excess10dTrend.text}</div>
          <p>当前值：{formatPct(latestExcess?.excess10d)}</p>
        </div>
        <div className="stability-metric">
          <h3>今日偏离</h3>
          <div className={`value ${deviationTrend.class}`}>{deviationTrend.text}</div>
          <p>当前值：{formatPct(latestDeviation?.deviation)}</p>
        </div>
      </div>
      <div className="grid-2">
        <div className="chart-card">
          <div className="chart-title"><span>是否持续跑赢{POOL.industry_chain.short}</span><span className="muted">滚动 5/10 日</span></div>
          <div ref={excessChartRef} className="chart-container" />
          {excessHover ? (
            <div className="chart-note">
              <strong>{excessHover.date}</strong>
              {' · '}股价 {formatPrice(excessHover.values.price)}
              {' · '}5日超额 {formatPct(excessHover.values.excess5d)}
              {' · '}10日超额 {formatPct(excessHover.values.excess10d)}
              {' · '}连胜 {excessHover.values.outperformStreak != null ? `${excessHover.values.outperformStreak}天` : '--'}
            </div>
          ) : (
            <div className="chart-note"><strong>读法：</strong>琥珀色虚线为股价（左轴）；蓝/紫线持续在中线以上才算稳定跑赢；红线代表跑赢是否连续（右轴）。滚轮缩放，拖拽平移。</div>
          )}
          <div className="legend"><span><i style={{ background: '#8b5cf6' }}></i>10日超额</span><span><i style={{ background: '#3b82f6' }}></i>5日超额</span><span><i style={{ background: '#ff4d4f' }}></i>超额连胜</span><span><i style={{ background: '#f59e0b' }}></i>股价</span></div>
        </div>

        <div className="chart-card">
          <div className="chart-title"><span>今天是跟随还是偏离</span><span className="muted">个股 / {POOL.industry_chain.short} / 超额</span></div>
          <div ref={deviationChartRef} className="chart-container" />
          {deviationHover ? (
            <div className="chart-note">
              <strong>{deviationHover.date}</strong>
              {' · '}股价 {formatPrice(deviationHover.values.price)}
              {' · '}个股 {formatPct(deviationHover.values.anchor)}
              {' · '}{POOL.industry_chain.short} {formatPct(deviationHover.values.industry)}
              {' · '}超额 {formatPct(deviationHover.values.excess)}
            </div>
          ) : (
            <div className="chart-note"><strong>读法：</strong>琥珀色虚线为股价（左轴）；红线贴近蓝线说明个股主要跟随{POOL.industry_chain.short}；紫线离中线越远，说明当天偏离越大（右轴）。滚轮缩放，拖拽平移。</div>
          )}
          <div className="legend"><span><i style={{ background: '#ff4d4f' }}></i>个股收益</span><span><i style={{ background: '#3b82f6' }}></i>{POOL.industry_chain.short}中位数</span><span><i style={{ background: '#8b5cf6' }}></i>当日超额</span><span><i style={{ background: '#f59e0b' }}></i>股价</span></div>
        </div>
      </div>
    </details>
  );
}
