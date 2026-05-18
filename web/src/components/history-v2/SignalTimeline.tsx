"use client";

import { useMemo, useState, type CSSProperties, type MouseEvent } from 'react';
import type { DashboardView } from '@/types/dashboard-view';
import { formatDate, formatPercent } from '@/lib/history-v2/formatters';
import { SIGNAL_CATEGORY } from '@/lib/glossary';

interface SignalTimelineProps {
  signalData: DashboardView['trends']['signalTimeline'];
}

type SignalGroupKey = 'pref' | 'avoid' | 'contra' | 'trap';

const SIGNAL_TYPES: Array<{ type: SignalGroupKey; name: string; color: string }> = [
  { type: 'pref', name: SIGNAL_CATEGORY.preference, color: '#ff4d4f' },
  { type: 'avoid', name: SIGNAL_CATEGORY.avoid, color: '#20d477' },
  { type: 'contra', name: SIGNAL_CATEGORY.counter_intuitive, color: '#a855f7' },
  { type: 'trap', name: SIGNAL_CATEGORY.trap, color: '#f97316' }
];

function fallbackGroup(signal: string): SignalGroupKey {
  if (signal.includes('放量') || signal.includes('陷阱')) return 'trap';
  if (signal.includes('背离') || signal.includes('拖累') || signal.includes('反直觉')) return 'contra';
  if (signal.includes('跑输') || signal.includes('后排') || signal.includes('负') || signal.includes('弱')) return 'avoid';
  return 'pref';
}

function groupsForDay(day: DashboardView['trends']['signalTimeline'][number]) {
  if (day.groups) return day.groups;
  const groups: Record<SignalGroupKey, string[]> = { pref: [], avoid: [], contra: [], trap: [] };
  day.signals?.forEach((signal) => groups[fallbackGroup(signal)].push(signal));
  return groups;
}

function positionForIndex(index: number, count: number) {
  return 64 + (index / Math.max(count - 1, 1)) * 840;
}

export default function SignalTimeline({ signalData }: SignalTimelineProps) {
  const [activeDate, setActiveDate] = useState<string | null>(null);

  const timeline = signalData ?? [];
  const activeDay = useMemo(() => {
    if (!timeline.length) return null;
    return timeline.find((day) => day.date === activeDate) ?? timeline[timeline.length - 1];
  }, [activeDate, timeline]);

  const chartMeta = useMemo(() => {
    if (!timeline.length) {
      return { pricePoints: '', activeX: 904, activeY: 202, monthTicks: [] as Array<{ x: number; label: string }>, marks: [] as Array<{ x: number; y: number; type: SignalGroupKey }> };
    }

    const prices = timeline.map((day) => day.price ?? 0);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const range = maxPrice - minPrice || 1;
    const dateToPoint = new Map<string, { x: number; y: number }>();
    const points = timeline.map((day, index) => {
      const x = positionForIndex(index, timeline.length);
      const y = 202 - (((day.price ?? 0) - minPrice) / range) * 170;
      dateToPoint.set(day.date, { x, y });
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

    const seenMonths = new Set<string>();
    const monthTicks = timeline.flatMap((day, index) => {
      const month = day.date.slice(0, 6);
      if (seenMonths.has(month)) return [];
      seenMonths.add(month);
      return [{ x: positionForIndex(index, timeline.length), label: `${month.slice(0, 4)}-${month.slice(4, 6)}` }];
    });

    const marks = timeline.flatMap((day, index) => {
      const x = positionForIndex(index, timeline.length) - 2.9;
      const groups = groupsForDay(day);
      return SIGNAL_TYPES.flatMap((config, typeIndex) => (
        groups[config.type]?.length ? [{ x, y: 276 + typeIndex * 13, type: config.type }] : []
      ));
    });

    const activePoint = dateToPoint.get(activeDay?.date ?? '') ?? dateToPoint.get(timeline[timeline.length - 1].date);
    return {
      pricePoints: points.join(' '),
      activeX: activePoint?.x ?? 904,
      activeY: activePoint?.y ?? 202,
      monthTicks,
      marks
    };
  }, [activeDay?.date, timeline]);

  const currentSignalGroups = useMemo(() => {
    const groups = activeDay ? groupsForDay(activeDay) : { pref: [], avoid: [], contra: [], trap: [] };
    return SIGNAL_TYPES.map((config) => ({
      ...config,
      signals: groups[config.type] ?? []
    }));
  }, [activeDay]);

  const signalShiftStats = useMemo(() => {
    const splitIndex = Math.max(1, Math.floor(timeline.length * 0.7));
    const countSignals = (items: typeof timeline) => {
      const counts = new Map<string, { count: number; type: SignalGroupKey }>();
      items.forEach((day) => {
        const groups = groupsForDay(day);
        SIGNAL_TYPES.forEach((config) => {
          groups[config.type]?.forEach((signal) => {
            const current = counts.get(signal) ?? { count: 0, type: config.type };
            counts.set(signal, { count: current.count + 1, type: config.type });
          });
        });
      });
      return Array.from(counts.entries())
        .sort((a, b) => b[1].count - a[1].count)
        .slice(0, 3)
        .map(([name, item]) => ({ name, count: item.count, type: item.type }));
    };

    return {
      early: countSignals(timeline.slice(0, splitIndex)),
      recent: countSignals(timeline.slice(Math.max(0, timeline.length - 20)))
    };
  }, [timeline]);

  const signalLaneData = useMemo(() => {
    const counts = new Map<string, { count: number; type: SignalGroupKey; positions: boolean[] }>();
    timeline.forEach((day, index) => {
      const groups = groupsForDay(day);
      SIGNAL_TYPES.forEach((config) => {
        groups[config.type]?.forEach((signal) => {
          const current = counts.get(signal) ?? { count: 0, type: config.type, positions: Array(timeline.length).fill(false) };
          current.count += 1;
          current.positions[index] = true;
          counts.set(signal, current);
        });
      });
    });

    return Array.from(counts.entries())
      .sort((a, b) => b[1].count - a[1].count)
      .slice(0, 8)
      .map(([name, item]) => ({
        name,
        ...item,
        color: SIGNAL_TYPES.find((config) => config.type === item.type)?.color ?? '#888'
      }));
  }, [timeline]);

  const handleTimelineClick = (event: MouseEvent<SVGRectElement>) => {
    if (!timeline.length) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    const index = Math.round(ratio * (timeline.length - 1));
    setActiveDate(timeline[index]?.date ?? timeline[timeline.length - 1].date);
  };

  const activeGroups = activeDay ? groupsForDay(activeDay) : { pref: [], avoid: [], contra: [], trap: [] };
  const activeGroupCount = SIGNAL_TYPES.filter((config) => activeGroups[config.type]?.length).length;

  return (
    <details className="collapsible-section" open>
      <summary>
        <div className="section-title-wrap">
          <h2 className="section-title">信号时间轴</h2>
          <p className="section-note" style={{ marginTop: '6px' }}>上方看价格和信号密度，下方按具体信号拆成轨道，观察过去到现在的信号切换。</p>
        </div>
        <span className="section-meta">{timeline.length} 交易日</span>
      </summary>
      <div className="signal-timeline-card" style={{ display: 'block' }}>
        <div className="signal-timeline-head">
          <div>
            <h3>股价走势与历史信号时间轴</h3>
            <p>上方看价格和信号密度，下方按具体信号拆成轨道，观察过去到现在的信号切换。</p>
          </div>
          <div className="signal-legend">
            {SIGNAL_TYPES.map((config) => (
              <span key={config.type}><i style={{ background: config.color }}></i>{config.name}</span>
            ))}
          </div>
        </div>
        <svg id="signalTimeline" className="signal-timeline" viewBox="0 0 960 370" role="img" aria-label="股价走势与历史信号时间轴">
          <rect x="0" y="0" width="960" height="370" fill="#111111"/>
          <line x1="64" y1="202" x2="904" y2="202" stroke="#282828"/>
          {chartMeta.monthTicks.map((tick) => (
            <g key={tick.label}>
              <line x1={tick.x} y1="32" x2={tick.x} y2="332" stroke="#1f1f1f"/>
              <text x={tick.x} y="350" fill="#666" fontSize="11" textAnchor="middle">{tick.label}</text>
            </g>
          ))}

          <text x="18" y="205" fill="#666" fontSize="11">股价</text>
          <text x="18" y="285" fill="#666" fontSize="11">4类</text>
          <text x="18" y="311" fill="#666" fontSize="11">2类</text>
          <text x="18" y="330" fill="#666" fontSize="11">0</text>
          <line x1="64" y1="226" x2="904" y2="226" stroke="#282828"/>
          <line x1="64" y1="255" x2="904" y2="255" stroke="#1f1f1f"/>
          <line x1="64" y1="281" x2="904" y2="281" stroke="#1f1f1f"/>
          <line x1="64" y1="307" x2="904" y2="307" stroke="#1f1f1f"/>
          <line x1="64" y1="333" x2="904" y2="333" stroke="#1f1f1f"/>

          <polyline className="price-line" points={chartMeta.pricePoints}/>
          {chartMeta.marks.map((mark, index) => (
            <rect key={index} className={`sig-mark sig-${mark.type}`} x={mark.x} y={mark.y} width="5.8" height="11" />
          ))}
          {activeDay && (
            <g className="signal-active-mark" aria-hidden="true">
              <rect className="active-day-band" x={chartMeta.activeX - 5} y="24" width="10" height="312" />
              <line className="active-day-line" x1={chartMeta.activeX} y1="24" x2={chartMeta.activeX} y2="336" />
              <circle cx={chartMeta.activeX} cy={chartMeta.activeY} r="4" fill="#e5e5e5" />
              <text x={Math.min(chartMeta.activeX + 8, 880)} y={Math.max(chartMeta.activeY - 8, 20)} fill="#b7b7b7" fontSize="11">{activeDay.date === timeline[timeline.length - 1]?.date ? '当前' : formatDate(activeDay.date, 'MM/DD')}</text>
            </g>
          )}
          <rect id="timelineHitArea" className="timeline-hit-area" x="64" y="24" width="840" height="312" fill="transparent" onClick={handleTimelineClick}/>
        </svg>
        <div className="signal-readout">
          <div className="signal-readout-panel">
            <div className="signal-panel-head">
              <div className="signal-panel-title">当前信号组合</div>
              <div id="currentSignalDate" className="signal-panel-sub mono">{activeDay?.date ?? '--'}</div>
            </div>
            <div id="currentSignalGroups" className="current-signal-groups">
              {currentSignalGroups.map((group) => (
                <div key={group.type} className="current-signal-row">
                  <div className="current-signal-label">
                    <i style={{ background: group.color }}></i> {group.name}
                  </div>
                  <div className="current-signal-chips">
                    {group.signals.length > 0 ? (
                      group.signals.slice(0, 6).map((signal) => (
                        <span key={signal} className="signal-chip">{signal}</span>
                      ))
                    ) : (
                      <span className="signal-chip empty">无信号</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="signal-readout-panel">
            <div className="signal-panel-head">
              <div className="signal-panel-title">历史信号变迁</div>
              <div className="signal-panel-sub">早期高频 / 近20日高频</div>
            </div>
            <div className="signal-shift-body">
              <div className="signal-shift-col">
                <h4>早期主导</h4>
                <div id="earlySignalTop">
                  {signalShiftStats.early.map((signal) => {
                    const color = SIGNAL_TYPES.find((config) => config.type === signal.type)?.color ?? '#ff4d4f';
                    return (
                      <div key={signal.name} className="shift-signal">
                        <div className="shift-signal-name">
                          <i style={{ background: color }}></i> {signal.name}
                        </div>
                        <div className="shift-signal-count">{signal.count}次</div>
                      </div>
                    );
                  })}
                </div>
              </div>
              <div className="signal-shift-col">
                <h4>近期主导</h4>
                <div id="recentSignalTop">
                  {signalShiftStats.recent.map((signal) => {
                    const color = SIGNAL_TYPES.find((config) => config.type === signal.type)?.color ?? '#20d477';
                    return (
                      <div key={signal.name} className="shift-signal">
                        <div className="shift-signal-name">
                          <i style={{ background: color }}></i> {signal.name}
                        </div>
                        <div className="shift-signal-count">{signal.count}次</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="signal-lane-panel">
          <div className="signal-lane-head">
            <div className="signal-lane-title">高频信号轨道</div>
            <div className="signal-lane-sub">按时间排列信号出现频率</div>
          </div>
          <div className="signal-lane-map" style={{ '--signal-days': timeline.length } as CSSProperties}>
            {signalLaneData.map((lane) => (
              <div key={lane.name} className="signal-lane-row">
                <div className="signal-lane-name">
                  <i style={{ background: lane.color }}></i> {lane.name}
                </div>
                <div className="signal-lane-track">
                  {lane.positions.map((active, index) => (
                    <button
                      key={`${lane.name}-${index}`}
                      type="button"
                      className={`lane-dot ${active ? `active ${lane.type}` : ''} ${timeline[index]?.date === activeDay?.date ? 'selected' : ''}`}
                      aria-label={`${timeline[index]?.date ?? ''} ${lane.name}`}
                      onClick={() => setActiveDate(timeline[index]?.date ?? null)}
                    />
                  ))}
                </div>
                <div className="signal-lane-meta">{lane.count}次</div>
              </div>
            ))}
          </div>
        </div>
        <div className="chart-note"><strong>读法：</strong>价格线下方是信号密度，轨道区展示每个具体信号在历史中何时出现；点击亮块或日期，可拆解当天具体命中。</div>
        <div className="signal-day-detail" aria-live="polite">
          <div className="signal-day-summary">
            <div>
              <div className="signal-day-label">选中日期</div>
              <div id="signalDayDate" className="signal-day-date mono">{activeDay?.date ?? '--'}</div>
            </div>
            <div className="signal-day-stat">
              <span>收盘价</span>
              <strong id="signalDayPrice" className="mono">{activeDay?.price?.toFixed?.(2) ?? '--'}</strong>
            </div>
            <div className="signal-day-stat">
              <span>当日涨跌</span>
              <strong id="signalDayReturn" className="mono">{formatPercent(activeDay?.return)}</strong>
            </div>
            <div className="signal-day-stat">
              <span>命中组数</span>
              <strong id="signalDayCount" className="mono">{activeGroupCount}</strong>
            </div>
          </div>
          <div id="signalDayGroups" className="signal-day-groups">
            {currentSignalGroups.map((group) => (
              <div key={group.type} className="signal-group-card">
                <div className="signal-group-title">
                  <span><i style={{ background: group.color }}></i>{group.name}</span>
                  <small>{group.signals.length} 个</small>
                </div>
                {group.signals.length ? group.signals.slice(0, 8).map((signal) => (
                  <span key={signal} className="signal-chip">{signal}</span>
                )) : (
                  <span className="signal-chip empty">无信号</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </details>
  );
}
