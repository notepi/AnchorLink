"use client";

import { useRef, useEffect, useState, useCallback } from 'react';
import { createChart, ColorType, LineSeries } from 'lightweight-charts';
import type { RollingMetric } from '@/types/dashboard-view';

// ── Types ──

interface ExcessComparisonChartProps {
  excessReturnData: RollingMetric[];
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

// ── Helpers ──

function formatPct(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? '--' : `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function formatPrice(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? '--' : value.toFixed(2);
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

// ── 固定配置 ──

const SERIES_CONFIGS: SeriesConfig[] = [
  { key: 'price', color: '#f59e0b', lineWidth: 1, dashed: true, priceScaleId: 'left' },
  { key: 'legacyExcess1d', color: '#93c5fd', lineWidth: 1, priceScaleId: 'right' },
  { key: 'legacyExcess5d', color: '#3b82f6', lineWidth: 2, priceScaleId: 'right' },
  { key: 'legacyExcess10d', color: '#1e40af', lineWidth: 2, priceScaleId: 'right' },
  { key: 'indexExcess1d', color: '#c4b5fd', lineWidth: 1, priceScaleId: 'right' },
  { key: 'indexExcess3d', color: '#a78bfa', lineWidth: 1, priceScaleId: 'right' },
  { key: 'indexExcess5d', color: '#8b5cf6', lineWidth: 2, priceScaleId: 'right' },
  { key: 'indexExcess10d', color: '#5b21b6', lineWidth: 2, priceScaleId: 'right' },
];

const ZERO_KEY = '__zero__';

const LEGEND_ITEMS: { key: string; color: string; label: string; dashed?: boolean }[] = [
  { key: 'price', color: '#f59e0b', label: '股价' },
  { key: 'legacyExcess1d', color: '#93c5fd', label: '传统 1D' },
  { key: 'legacyExcess5d', color: '#3b82f6', label: '传统 5D' },
  { key: 'legacyExcess10d', color: '#1e40af', label: '传统 10D' },
  { key: 'indexExcess1d', color: '#c4b5fd', label: 'ETF 1D' },
  { key: 'indexExcess3d', color: '#a78bfa', label: 'ETF 3D' },
  { key: 'indexExcess5d', color: '#8b5cf6', label: 'ETF 5D' },
  { key: 'indexExcess10d', color: '#5b21b6', label: 'ETF 10D' },
  { key: ZERO_KEY, color: '#555', label: '0 轴', dashed: true },
];

// ── Main Component ──

export default function ExcessComparisonChart({ excessReturnData }: ExcessComparisonChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<any>(null);
  const seriesMapRef = useRef<Map<string, any>>(new Map());
  const seriesDataMapRef = useRef<Map<string, any[]>>(new Map());
  const [hover, setHover] = useState<HoverState | null>(null);
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(new Set());

  // 创建图表（只在数据变化时重建）
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

    const newSeriesMap = new Map<string, any>();
    const newDataMap = new Map<string, any[]>();

    // 数据系列
    SERIES_CONFIGS.forEach(cfg => {
      const series = chart.addSeries(LineSeries, {
        color: cfg.color,
        lineWidth: cfg.lineWidth ?? 2,
        lineStyle: cfg.dashed ? 2 : 0,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerRadius: 3,
        priceScaleId: cfg.priceScaleId,
      });
      const sData = toSeriesData(excessReturnData as Row[], cfg.key);
      series.setData(sData);
      newSeriesMap.set(cfg.key, series);
      newDataMap.set(cfg.key, sData);
    });

    // 0 轴线
    const zeroSeries = chart.addSeries(LineSeries, {
      color: '#555',
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerRadius: 0,
      priceScaleId: 'right',
    });
    const zeroData = toSeriesData(excessReturnData as Row[], 'price').map(d => ({ time: d.time, value: 0 }));
    zeroSeries.setData(zeroData);
    newSeriesMap.set(ZERO_KEY, zeroSeries);
    newDataMap.set(ZERO_KEY, zeroData);

    chart.priceScale('left').applyOptions({
      scaleMargins: { top: 0.1, bottom: 0.1 },
      borderColor: '#282828',
    });
    chart.priceScale('right').applyOptions({
      scaleMargins: { top: 0.1, bottom: 0.1 },
      borderColor: '#282828',
    });

    // 悬停回调
    const onHoverRef = (param: any) => {
      if (!param.time || !param.point) {
        setHover(null);
        return;
      }
      const dateStr = typeof param.time === 'string' ? param.time : '';
      const values: Record<string, number | null> = {};
      newSeriesMap.forEach((series, key) => {
        if (key === ZERO_KEY) return;
        const dataPoint = param.seriesData.get(series);
        values[key] = dataPoint && 'value' in dataPoint ? (dataPoint as any).value : null;
      });
      setHover({ date: dateStr, values });
    };
    chart.subscribeCrosshairMove(onHoverRef);

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        chart.applyOptions({ width, height });
      }
    });
    resizeObserver.observe(container);

    chartInstanceRef.current = chart;
    seriesMapRef.current = newSeriesMap;
    seriesDataMapRef.current = newDataMap;

    return () => {
      resizeObserver.disconnect();
      chart.unsubscribeCrosshairMove(onHoverRef);
      chart.remove();
      chartInstanceRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [excessReturnData]);

  // 切换显示/隐藏（不重建图表，只改数据）
  const toggleKey = useCallback((key: string) => {
    setHiddenKeys(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  // hiddenKeys 变化时同步到图表
  useEffect(() => {
    const seriesMap = seriesMapRef.current;
    const dataMap = seriesDataMapRef.current;
    if (!seriesMap.size) return;

    seriesMap.forEach((series, key) => {
      if (hiddenKeys.has(key)) {
        series.setData([]);
      } else {
        series.setData(dataMap.get(key) ?? []);
      }
    });
  }, [hiddenKeys]);

  // 最新数据（分歧判断 + 四池卡片）
  const latest = excessReturnData[excessReturnData.length - 1];
  const latestAsAny = latest as Record<string, any> | undefined;
  const legacy5d = latestAsAny?.legacyExcess5d ?? null;
  const index5d = latestAsAny?.indexExcess5d ?? null;

  const isDiverged = (() => {
    if (legacy5d == null || index5d == null) return null;
    return !((legacy5d > 0 && index5d > 0) || (legacy5d < 0 && index5d < 0) || (legacy5d === 0 && index5d === 0));
  })();

  return (
    <details className="collapsible-section" open>
      <summary>
        <div className="section-title-wrap">
          <h2 className="section-title">传统中位数 vs 类 ETF 标准超额</h2>
          <p className="section-note">蓝色系=传统中位数超额，紫色系=类 ETF 标准超额，深浅区分窗口。点图例切换显示。</p>
        </div>
        <span className="section-meta">5D {formatPct(legacy5d)} / {formatPct(index5d)}</span>
      </summary>

      {/* 主图 */}
      <div className="chart-card">
        <div className="chart-title">
          <span>传统中位数 vs 类 ETF 标准超额</span>
          <span className="muted">1D / 3D / 5D / 10D 全窗口</span>
        </div>
        <div ref={containerRef} className="chart-container" />
        {hover ? (
          <div className="chart-note">
            <strong>{hover.date}</strong>
            {' · '}股价 {formatPrice(hover.values.price)}
            {' · '}传统 1D {formatPct(hover.values.legacyExcess1d)}
            {' · '}传统 5D {formatPct(hover.values.legacyExcess5d)}
            {' · '}传统 10D {formatPct(hover.values.legacyExcess10d)}
            {' · '}ETF 1D {formatPct(hover.values.indexExcess1d)}
            {' · '}ETF 3D {formatPct(hover.values.indexExcess3d)}
            {' · '}ETF 5D {formatPct(hover.values.indexExcess5d)}
            {' · '}ETF 10D {formatPct(hover.values.indexExcess10d)}
          </div>
        ) : (
          <div className="chart-note">
            <strong>读法：</strong>橙色虚线=股价（左轴）；蓝色系=传统中位数超额，紫色系=类ETF标准超额（右轴）；灰虚线=0轴。点下方图例可切换线的显示。滚轮缩放，拖拽平移。
          </div>
        )}
        {/* 可点击图例 */}
        <div className="legend legend-multi legend-interactive">
          {LEGEND_ITEMS.map(item => {
            const isHidden = hiddenKeys.has(item.key);
            return (
              <button
                key={item.key}
                className={`legend-toggle ${isHidden ? 'hidden' : ''}`}
                onClick={() => toggleKey(item.key)}
                title={isHidden ? `显示 ${item.label}` : `隐藏 ${item.label}`}
              >
                <i style={{ background: isHidden ? 'var(--muted)' : item.color }}></i>
                <span className={isHidden ? 'muted' : ''}>{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 分歧状态 */}
      <div className="excess-divergence-status">
        {isDiverged === null ? (
          <span className="muted">数据不足，无法判断口径一致性</span>
        ) : isDiverged ? (
          <span className="divergence-warning">⚠ 口径分歧（5D）：传统 {formatPct(legacy5d)} vs ETF {formatPct(index5d)}</span>
        ) : (
          <span className="divergence-ok">✓ 口径一致（5D）：传统 {formatPct(legacy5d)}，ETF {formatPct(index5d)}</span>
        )}
      </div>
    </details>
  );
}
