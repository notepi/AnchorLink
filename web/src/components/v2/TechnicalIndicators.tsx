'use client';

import type { V2TechnicalIndicators } from '@/types/v2-scoring';

interface TechnicalIndicatorsProps {
  ti: V2TechnicalIndicators;
}

function fmt(v: number | null, decimals = 1): string {
  return v !== null ? v.toFixed(decimals) : '—';
}

export function TechnicalIndicators({ ti }: TechnicalIndicatorsProps) {
  const items = [
    { label: 'RSI', value: fmt(ti.rsi14) },
    { label: 'MACD', value: fmt(ti.macdHist, 3) },
    { label: 'Stoch K', value: fmt(ti.stochK) },
    { label: 'BB %b', value: fmt(ti.bbPctb, 2) },
    { label: 'ADX', value: fmt(ti.adx14) },
    { label: 'ATR', value: fmt(ti.atr14) },
    { label: 'Squeeze', value: ti.squeezeOn === null ? '—' : ti.squeezeOn ? 'On' : 'Off' },
  ];

  return (
    <div className="v2-card">
      <div className="v2-card-title">技术指标</div>
      <div className="v2-ti-grid">
        {items.map((item) => (
          <div key={item.label} className="v2-ti-item">
            <div className="v2-ti-label">{item.label}</div>
            <div className="v2-ti-value">{item.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
