'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import type { DailyResult } from '@/types/quant-lab-view';

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

function scoreColor(score: number, veto: boolean): string {
  if (veto) return '#4b5563';
  if (score >= 8) return '#991b1b';
  if (score >= 5) return '#ef4444';
  if (score >= 3) return '#f87171';
  if (score >= 1) return '#fca5a5';
  if (score === 0) return '#374151';
  if (score >= -2) return '#a7f3d0';
  if (score >= -4) return '#6ee7b7';
  if (score >= -7) return '#10b981';
  return '#047857';
}

interface Tip {
  x: number; y: number;
  date: string;
  score: number;
  veto: boolean;
  signalsCount: number;
  next_1d: number | null;
  next_1d_exc: number | null;
}

export default function ScoreCalendar({ daily }: { daily: DailyResult[] }) {
  const router = useRouter();
  const [tip, setTip] = useState<Tip | null>(null);

  // 按月份分组
  const monthGroups = useMemo(() => {
    const groups: Record<string, DailyResult[]> = {};
    daily.forEach((d) => {
      const ym = d.date.slice(0, 6);
      if (!groups[ym]) groups[ym] = [];
      groups[ym].push(d);
    });
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [daily]);

  return (
    <section id="calendar" className="ql-section">
      <h2>信号日历热力图 · 243 天 <span className="ql-section-tag">SECTION 8</span></h2>

      <div className="ql-calendar">
        {monthGroups.map(([ym, days]) => {
          const monthLabel = `${ym.slice(0, 4)}-${ym.slice(4, 6)}`;
          return (
            <div key={ym} className="ql-calendar-row">
              <span className="ql-cal-month">{monthLabel}</span>
              {days.map((d) => (
                <div
                  key={d.date}
                  className="ql-cal-cell"
                  style={{ background: scoreColor(d.score, d.veto) }}
                  onMouseEnter={(e) =>
                    setTip({
                      x: e.clientX + 10,
                      y: e.clientY + 10,
                      date: d.date,
                      score: d.score,
                      veto: d.veto,
                      signalsCount: d.signals.length,
                      next_1d: d.next_1d_return,
                      next_1d_exc: d.next_1d_excess,
                    })
                  }
                  onMouseLeave={() => setTip(null)}
                  onClick={() => router.push(`/today?date=${d.date}`)}
                />
              ))}
              {/* 补齐方格到 35 (5 周 × 7 日) */}
              {Array.from({ length: Math.max(0, 35 - days.length) }).map((_, i) => (
                <div key={`empty-${i}`} className="ql-cal-cell empty" />
              ))}
            </div>
          );
        })}
      </div>

      <div className="ql-curve-legend" style={{ marginTop: 12 }}>
        <span style={{ fontSize: 11 }}>评分颜色：</span>
        <span><span className="ql-swatch" style={{ background: '#047857', height: 12, width: 12 }} /> ≤-8</span>
        <span><span className="ql-swatch" style={{ background: '#10b981', height: 12, width: 12 }} /> -7~-5</span>
        <span><span className="ql-swatch" style={{ background: '#6ee7b7', height: 12, width: 12 }} /> -4~-3</span>
        <span><span className="ql-swatch" style={{ background: '#a7f3d0', height: 12, width: 12 }} /> -2~-1</span>
        <span><span className="ql-swatch" style={{ background: '#374151', height: 12, width: 12 }} /> 0</span>
        <span><span className="ql-swatch" style={{ background: '#fca5a5', height: 12, width: 12 }} /> +1~+2</span>
        <span><span className="ql-swatch" style={{ background: '#f87171', height: 12, width: 12 }} /> +3~+4</span>
        <span><span className="ql-swatch" style={{ background: '#ef4444', height: 12, width: 12 }} /> +5~+7</span>
        <span><span className="ql-swatch" style={{ background: '#991b1b', height: 12, width: 12 }} /> ≥+8</span>
      </div>

      {tip && (
        <div className="ql-tooltip" style={{ left: tip.x, top: tip.y }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>{tip.date}</div>
          {tip.veto && <div style={{ color: '#ef4444' }}>⛔ 一票否决</div>}
          <div>综合分: <strong style={{ color: tip.score >= 0 ? '#ef4444' : '#10b981' }}>{tip.score >= 0 ? '+' : ''}{tip.score}</strong></div>
          <div>激活信号: {tip.signalsCount} 个</div>
          {tip.next_1d != null && <div>实际 T+1: {fmtPct(tip.next_1d)}</div>}
          {tip.next_1d_exc != null && <div>T+1 超额: {fmtPct(tip.next_1d_exc)}</div>}
          <div style={{ marginTop: 4, fontSize: 10, color: 'var(--ql-text-muted)' }}>
            点击跳转 /today
          </div>
        </div>
      )}

      <div className="ql-hint">
        每个方格 = 一个交易日，颜色映射综合分。点击任一方格跳转到当日「今日看板」查看完整信号详情。
      </div>
    </section>
  );
}
