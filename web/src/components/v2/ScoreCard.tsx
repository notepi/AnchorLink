'use client';

interface ScoreCardProps {
  score: number;
  veto: boolean;
  thresholdBuy: number;
  thresholdSell: number;
}

export function ScoreCard({ score, veto, thresholdBuy, thresholdSell }: ScoreCardProps) {
  const valueClass = score > 0
    ? 'v2-card-value--pos'
    : score < 0
    ? 'v2-card-value--neg'
    : 'v2-card-value--neu';

  let direction = '中性';
  if (veto || score <= thresholdSell) direction = '偏空';
  else if (score >= thresholdBuy) direction = '偏多';

  return (
    <div className="v2-card">
      <div className="v2-card-title">综合评分</div>
      <div className={`v2-card-value ${valueClass}`}>
        {score > 0 ? '+' : ''}{score}
      </div>
      {veto && <span className="v2-veto">VETO</span>}
      <div className="v2-card-detail">
        方向: {direction} (阈值: +{thresholdBuy} / {thresholdSell})
      </div>
    </div>
  );
}
