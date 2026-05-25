'use client';

import { useEffect, useRef } from 'react';
import type { V2DailyResult } from '@/types/v2-scoring';

interface ScoreTimelineProps {
  dailyResults: V2DailyResult[];
  selectedDate?: string;
}

const CHART_HEIGHT = 200;
const PADDING = { top: 20, right: 20, bottom: 30, left: 40 };

export function ScoreTimeline({ dailyResults, selectedDate }: ScoreTimelineProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !dailyResults.length) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = CHART_HEIGHT * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = CHART_HEIGHT;
    const plotW = w - PADDING.left - PADDING.right;
    const plotH = h - PADDING.top - PADDING.bottom;

    ctx.clearRect(0, 0, w, h);

    const scores = dailyResults.map(d => d.score);
    const minScore = Math.min(...scores, -3);
    const maxScore = Math.max(...scores, 3);
    const scoreRange = maxScore - minScore || 1;

    const toX = (i: number) => PADDING.left + (i / (dailyResults.length - 1)) * plotW;
    const toY = (s: number) => PADDING.top + plotH - ((s - minScore) / scoreRange) * plotH;

    // Regime 背景色
    let i = 0;
    while (i < dailyResults.length) {
      const regime = dailyResults[i].regime;
      let j = i;
      while (j < dailyResults.length && dailyResults[j].regime === regime) j++;

      const colors: Record<string, string> = {
        mean_reverting: 'rgba(34, 197, 94, 0.06)',
        trending: 'rgba(239, 68, 68, 0.06)',
        transition: 'rgba(234, 179, 8, 0.06)',
      };
      ctx.fillStyle = colors[regime] || 'transparent';
      ctx.fillRect(toX(i), PADDING.top, toX(j - 1) - toX(i) + 2, plotH);

      i = j;
    }

    // Zero line
    const zeroY = toY(0);
    ctx.strokeStyle = '#d1d5db';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(PADDING.left, zeroY);
    ctx.lineTo(w - PADDING.right, zeroY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Score line
    ctx.strokeStyle = '#3b82f6';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    dailyResults.forEach((d, idx) => {
      const x = toX(idx);
      const y = toY(d.score);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Positive/negative dots
    dailyResults.forEach((d, idx) => {
      const x = toX(idx);
      const y = toY(d.score);
      if (d.date === selectedDate) {
        ctx.fillStyle = '#3b82f6';
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fill();
      }
    });

    // Y axis labels
    ctx.fillStyle = '#9ca3af';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'right';
    for (const s of [minScore, 0, maxScore]) {
      ctx.fillText(s.toString(), PADDING.left - 6, toY(s) + 3);
    }

    // X axis dates (show first, last, and selected)
    ctx.textAlign = 'center';
    if (dailyResults.length > 0) {
      ctx.fillText(dailyResults[0].date.slice(4), toX(0), h - 6);
      ctx.fillText(dailyResults[dailyResults.length - 1].date.slice(4), toX(dailyResults.length - 1), h - 6);
    }
  }, [dailyResults, selectedDate]);

  return (
    <div className="v2-card">
      <div className="v2-card-title">评分时间线</div>
      <div className="v2-timeline-container">
        <canvas ref={canvasRef} className="v2-timeline-canvas" />
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 11, color: '#9ca3af' }}>
        <span><span style={{ color: '#22c55e' }}>■</span> 均值回归</span>
        <span><span style={{ color: '#ef4444' }}>■</span> 趋势市</span>
        <span><span style={{ color: '#eab308' }}>■</span> 过渡期</span>
      </div>
    </div>
  );
}
