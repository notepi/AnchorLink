import { getV2ScoringData } from '@/lib/v2-scoring-reader';
import '@/styles/v2-scoring.css';

import { RegimeCard } from '@/components/v2/RegimeCard';
import { ScoreCard } from '@/components/v2/ScoreCard';
import { SignalBreakdown } from '@/components/v2/SignalBreakdown';
import { TechnicalIndicators } from '@/components/v2/TechnicalIndicators';
import { ActionCard } from '@/components/v2/ActionCard';
import { ScoreTimeline } from '@/components/v2/ScoreTimeline';
import { ScoreExcessScatter } from '@/components/v2/ScoreExcessScatter';
import { SignalEfficacyTable } from '@/components/v2/SignalEfficacyTable';
import { StrategySummaryCard } from '@/components/v2/StrategySummaryCard';
import { ForbiddenList } from '@/components/v2/ForbiddenList';
import { StatisticalHonesty } from '@/components/v2/StatisticalHonesty';
import { REGIME_LABEL } from '@/lib/glossary';

export default async function V2Page() {
  const data = await getV2ScoringData();

  if (!data) {
    return (
      <div className="v2-scoring">
        <div className="v2-empty">
          暂无 V2 评分数据，请先运行 <code>uv run python -m scripts.build_v2_scoring</code>
        </div>
      </div>
    );
  }

  const latest = data.dailyResults[data.dailyResults.length - 1];
  const regime = data.latestRegime;

  return (
    <div className="v2-scoring">
      {/* Header */}
      <div className="v2-header">
        <h1>V2 评分系统</h1>
        <div className="v2-subtitle">
          铂力特 688333.SH | 数据截止 {latest?.date || data.generatedAt} | Walk-Forward {data.trainWindow} 天
        </div>
        <span className={`v2-regime-tag ${
          regime.regime === 'mean_reverting' ? 'v2-regime-tag--mr'
          : regime.regime === 'trending' ? 'v2-regime-tag--tr'
          : 'v2-regime-tag--ts'
        }`}>
          {REGIME_LABEL[regime.regime] || regime.regime}
        </span>
      </div>

      {/* 区块1: 每日决策 */}
      <div className="v2-section">
        <div className="v2-section-title">每日决策</div>
        <div className="v2-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))' }}>
          <RegimeCard
            regime={latest.regime}
            adx={latest.technicalIndicators.adx14}
            thresholdBuy={latest.thresholdBuy}
            thresholdSell={latest.thresholdSell}
          />
          <ScoreCard
            score={latest.score}
            veto={latest.veto}
            thresholdBuy={latest.thresholdBuy}
            thresholdSell={latest.thresholdSell}
          />
          <ActionCard
            score={latest.score}
            veto={latest.veto}
            thresholdBuy={latest.thresholdBuy}
            thresholdSell={latest.thresholdSell}
            kellyPosition={latest.kellyPosition}
            holdPeriodDays={latest.holdPeriodDays}
          />
        </div>
        <div style={{ marginTop: 12 }}>
          <SignalBreakdown breakdown={latest.signalBreakdown} />
        </div>
        <div style={{ marginTop: 12 }}>
          <TechnicalIndicators ti={latest.technicalIndicators} />
        </div>
      </div>

      {/* 区块2: 评分历史 */}
      <div className="v2-section">
        <div className="v2-section-title">评分历史</div>
        <ScoreTimeline dailyResults={data.dailyResults} selectedDate={latest.date} />
        <div style={{ marginTop: 12 }}>
          <ScoreExcessScatter dailyResults={data.dailyResults} />
        </div>
      </div>

      {/* 区块3: 研究仪表盘 */}
      <div className="v2-section">
        <div className="v2-section-title">研究仪表盘</div>
        <StrategySummaryCard strategyResults={data.strategyResults} />
        <div style={{ marginTop: 12 }}>
          <SignalEfficacyTable strategyResults={data.strategyResults} />
        </div>
        <div className="v2-grid v2-grid-2" style={{ marginTop: 12 }}>
          <ForbiddenList />
          <StatisticalHonesty />
        </div>
      </div>

      {/* 底部说明 */}
      <div style={{
        marginTop: 24,
        padding: '12px 16px',
        background: '#f9fafb',
        borderRadius: 6,
        fontSize: 11,
        color: '#9ca3af',
        lineHeight: 1.6,
      }}>
        V2 保守评分策略：MR±3 / TR±4 / TS±4。所有结论基于 247 天数据，方向一致但统计力度不足。
        评分仅供参考，不构成投资建议。
      </div>
    </div>
  );
}
