'use client';

import { REGIME_LABEL, REGIME_DESCRIPTION } from '@/lib/glossary';
import type { Regime } from '@/types/v2-scoring';

interface RegimeCardProps {
  regime: Regime;
  adx: number | null;
  thresholdBuy: number;
  thresholdSell: number;
}

export function RegimeCard({ regime, adx, thresholdBuy, thresholdSell }: RegimeCardProps) {
  const label = REGIME_LABEL[regime] || regime;
  const desc = REGIME_DESCRIPTION[regime] || '';
  const tagClass = regime === 'mean_reverting'
    ? 'v2-regime-tag--mr'
    : regime === 'trending'
    ? 'v2-regime-tag--tr'
    : 'v2-regime-tag--ts';

  return (
    <div className="v2-card">
      <div className="v2-card-title">市场状态</div>
      <span className={`v2-regime-tag ${tagClass}`}>{label}</span>
      <div style={{ marginTop: 8 }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: '#374151' }}>
          ADX = {adx !== null ? adx.toFixed(1) : 'N/A'}
        </span>
      </div>
      <div className="v2-card-detail">{desc}</div>
      <div className="v2-card-detail" style={{ marginTop: 4 }}>
        做多 ≥{thresholdBuy} / 做空 ≤{thresholdSell}
      </div>
    </div>
  );
}
