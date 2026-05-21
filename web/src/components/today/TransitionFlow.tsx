import type { TransitionTarget, QuadrantGuidance } from '@/types/dashboard-view';

interface TransitionFlowProps {
  transitions?: TransitionTarget[];
  currentQuadrantLabel?: string;
  currentGuidance?: QuadrantGuidance;
  currentWinRate?: number | null;
}

function fmtPct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

function fmtWr(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${(v * 100).toFixed(0)}%`;
}

export default function TransitionFlow({
  transitions,
  currentQuadrantLabel,
  currentGuidance,
  currentWinRate,
}: TransitionFlowProps) {
  if (!transitions || transitions.length === 0) return null;

  const goodPct = transitions
    .filter(t => t.targetWinRate != null && t.targetWinRate >= 0.55)
    .reduce((s, t) => s + t.probability * 100, 0);
  const badPct = transitions
    .filter(t => t.targetWinRate != null && t.targetWinRate < 0.4)
    .reduce((s, t) => s + t.probability * 100, 0);
  const neuPct = 100 - goodPct - badPct;

  const bestGoodTarget = transitions.find(t => t.targetWinRate != null && t.targetWinRate >= 0.55);

  return (
    <section className="tc-card">
      <h2>状态迁移 · 明天最可能去哪格</h2>
      <p className="tc-disclaimer">基于历史「{currentQuadrantLabel ?? '-'}」之后的次日去向</p>
      <div className="tc-trans-flow">
        <div className="tc-trans-from">
          <div className="tc-trans-label">今天</div>
          <div className="tc-trans-state">{currentQuadrantLabel ?? '-'}</div>
          <div className="tc-trans-tag">
            {currentGuidance?.icon ?? '⚪'} {currentGuidance?.label ?? '-'} · 胜率 {fmtWr(currentWinRate)}
          </div>
        </div>
        <div className="tc-trans-arrow">→</div>
        <div className="tc-trans-targets">
          {transitions.map((t, i) => (
            <div key={i} className={`tc-trans-target tc-trans-${t.guidance.tier}`}>
              <div className="tc-trans-prob">
                <strong>{fmtPct(t.probability)}</strong> 概率
              </div>
              <div className="tc-trans-target-state">
                {t.toStateLabel}
                {t.isStay && '（留原地）'}
              </div>
              <div className="tc-trans-target-meta">
                {t.guidance.icon} {t.guidance.label} · T+1 胜率 {fmtWr(t.targetWinRate)}
              </div>
            </div>
          ))}
        </div>
      </div>
      <p className="tc-hint">
        💡 <strong>综合判断</strong>：明天有{' '}
        <strong className="tc-pos">{goodPct.toFixed(0)}%</strong> 概率到「🟢 好买点」格、
        <strong className="tc-neu">{neuPct.toFixed(0)}%</strong> 到中性 / 偏弱格、
        <strong className="tc-neg">{badPct.toFixed(0)}%</strong> 到「🔴 回避」格。
        {bestGoodTarget && (
          <>
            <br />
            <strong>具体策略</strong>：今天观望，
            <strong>
              如果明天真的迁移到「{bestGoodTarget.toStateLabel}」（{fmtPct(bestGoodTarget.probability)}）
            </strong>
            ，是历史最佳买点之一（T+1 胜率 {fmtWr(bestGoodTarget.targetWinRate)}）。其他情况维持观望。
          </>
        )}
      </p>
    </section>
  );
}
