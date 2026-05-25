'use client';

import { useEffect, useRef } from 'react';
import type { V2DailyResult } from '@/types/v2-scoring';

interface ScoreExcessScatterProps {
  dailyResults: V2DailyResult[];
}

const CHART_HEIGHT = 180;
const PAD = { top: 15, right: 15, bottom: 30, left: 45 };

export function ScoreExcessScatter({ dailyResults }: ScoreExcessScatterProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const valid = dailyResults.filter(d => d.next1dExcess !== null);
    if (!valid.length) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = CHART_HEIGHT * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = CHART_HEIGHT;
    const plotW = w - PAD.left - PAD.right;
    const plotH = h - PAD.top - PAD.bottom;

    ctx.clearRect(0, 0, w, h);

    const scores = valid.map(d => d.score);
    const excs = valid.map(d => d.next1dExcess!);
    const minS = Math.min(...scores);
    const maxS = Math.max(...scores);
    const minE = Math.min(...excs, 0);
    const maxE = Math.max(...excs, 0);
    const rangeS = maxS - minS || 1;
    const rangeE = maxE - minE || 1;

    const toX = (s: number) => PAD.left + ((s - minS) / rangeS) * plotW;
    const toY = (e: number) => PAD.top + plotH - ((e - minE) / rangeE) * plotH;

    // Zero line (excess)
    const zeroY = toY(0);
    ctx.strokeStyle = '#e5e7eb';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(PAD.left, zeroY);
    ctx.lineTo(w - PAD.right, zeroY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Dots
    valid.forEach(d => {
      const x = toX(d.score);
      const y = toY(d.next1dExcess!);
      const color = d.next1dExcess! > 0 ? '#dc2626' : '#16a34a';
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.5;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;

    // Axes labels
    ctx.fillStyle = '#9ca3af';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('评分', w / 2, h - 4);
    ctx.textAlign = 'right';
    ctx.fillText(minE.toFixed(1) + '%', PAD.left - 4, PAD.top + 10);
    ctx.fillText(maxE.toFixed(1) + '%', PAD.left - 4, h - PAD.bottom);
  }, [dailyResults]);

  return (
    <div className="v2-card">
      <div className="v2-card-title">评分 vs T+1 超额收益</div>
      <div className="v2-timeline-container" style={{ height: CHART_HEIGHT }}>
        <canvas ref={canvasRef} className="v2-timeline-canvas" />
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 11, color: '#9ca3af' }}>
        <span><span style={{ color: '#dc2626' }}>●</span> 正超额</span>
        <span><span style={{ color: '#16a34a' }}>●</span> 负超额</span>
      </div>
    </div>
  );
}
