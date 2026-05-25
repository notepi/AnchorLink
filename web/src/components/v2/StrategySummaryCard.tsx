'use client';

interface StrategySummaryCardProps {
  strategyResults: Record<string, any>;
}

export function StrategySummaryCard({ strategyResults }: StrategySummaryCardProps) {
  const pm3 = strategyResults['±3'];
  const pm5 = strategyResults['±5'];

  const ld3 = pm3?.longDays;
  const ld5 = pm5?.longDays;

  // 硬编码 V2 保守策略核心指标（来自 analysis_framework.md 4.3 节）
  const metrics = [
    { label: '做多胜率', value: '61.3%' },
    { label: '平均 T+1 超额', value: '+1.042%' },
    { label: '累计超额', value: '+36.6%' },
    { label: '最大回撤', value: '-4.2%' },
    { label: '夏普比率', value: '6.58' },
    { label: 'Monte Carlo P(wr>50%)', value: '97.4%' },
  ];

  return (
    <div className="v2-card">
      <div className="v2-card-title">V2 保守策略表现</div>
      <div className="v2-grid v2-grid-3">
        {metrics.map(m => (
          <div key={m.label} className="v2-ti-item">
            <div className="v2-ti-label">{m.label}</div>
            <div className="v2-ti-value">{m.value}</div>
          </div>
        ))}
      </div>
      {ld3 && ld3.n > 0 && (
        <div style={{ marginTop: 10, fontSize: 12, color: '#6b7280' }}>
          Walk-Forward ±3: n={ld3.n}, wr={((ld3.winRateExc || 0) * 100).toFixed(1)}%,
          cum={ld3.cumLogExc > 0 ? '+' : ''}{(ld3.cumLogExc || 0).toFixed(1)}%
        </div>
      )}
    </div>
  );
}
