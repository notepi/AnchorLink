'use client';

interface ActionCardProps {
  score: number;
  veto: boolean;
  thresholdBuy: number;
  thresholdSell: number;
  kellyPosition: number | null;
  holdPeriodDays: number;
}

export function ActionCard({
  score,
  veto,
  thresholdBuy,
  thresholdSell,
  kellyPosition,
  holdPeriodDays,
}: ActionCardProps) {
  let action: 'buy' | 'sell' | 'hold' = 'hold';
  let label = '观望';
  if (veto || score <= thresholdSell) {
    action = 'sell';
    label = veto ? '不做多 (Veto)' : '减仓';
  } else if (score >= thresholdBuy) {
    action = 'buy';
    label = '做多';
  }

  const actionClass = `v2-action v2-action--${action}`;
  const posPct = kellyPosition !== null ? (kellyPosition * 100).toFixed(0) : '—';

  return (
    <div className={actionClass}>
      <div className="v2-action-label">{label}</div>
      <div className="v2-action-detail">
        仓位 {posPct}% | 持仓 {holdPeriodDays} 天
      </div>
    </div>
  );
}
