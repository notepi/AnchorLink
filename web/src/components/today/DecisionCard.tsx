import type { DecisionView } from '@/types/dashboard-view';

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '--';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

function fmtWr(v: number | null | undefined): string {
  if (v == null) return '--';
  return `${(v * 100).toFixed(0)}%`;
}

function verdictColor(conclusion: string): string {
  if (conclusion.includes('偏多')) return '#ef4444';
  if (conclusion.includes('偏空') || conclusion.includes('不')) return '#10b981';
  return '#9ca3af';
}

function actionColor(action: string): string {
  if (action === '做多') return '#ef4444';
  if (action === '不操作' || action === '减仓') return '#10b981';
  return '#9ca3af';
}

function alphaTag(type: string): { label: string; cls: string } {
  if (type === '纯Alpha') return { label: '纯Alpha', cls: 'tc-alpha-pure' };
  if (type === '隐藏Alpha') return { label: '隐藏Alpha', cls: 'tc-alpha-hidden' };
  if (type === '负向') return { label: '负向', cls: 'tc-alpha-neg' };
  return { label: '中性', cls: 'tc-alpha-neu' };
}

function dirIcon(pattern: string): string {
  if (pattern === '持续向上') return '↑持续';
  if (pattern === '持续向下') return '↓持续';
  if (pattern === '短线跌后回升') return '↻短线回升';
  if (pattern === '方向不稳定') return '⚡不稳定';
  if (pattern === '中性') return '';
  return '';
}

export default function DecisionCard({ decision }: { decision: DecisionView }) {
  const tv = decision.todayVerdict;
  const ta = decision.tomorrowAction;

  return (
    <div className="tc-decision">
      {/* 今日判定 */}
      <div className="tc-decision-section">
        <div className="tc-decision-header">今日判定</div>
        <div className="tc-decision-verdict" style={{ borderLeftColor: verdictColor(tv.conclusion) }}>
          <div className="tc-decision-conclusion" style={{ color: verdictColor(tv.conclusion) }}>
            {tv.conclusion}
          </div>
          <div className="tc-decision-meta">
            综合分 <strong>{tv.score}</strong>
            {tv.veto && <span className="tc-veto-badge">一票否决</span>}
            {tv.quadrantWinRate != null && (
              <span>象限胜率 {fmtWr(tv.quadrantWinRate)}</span>
            )}
          </div>
        </div>
        <div className="tc-decision-evidence">
          <div className="tc-evidence-label">依据</div>
          <ul>
            <li>
              综合分 = {tv.scoreBreakdown.map(s => `${s.signal}(${s.weight > 0 ? '+' : ''}${s.weight})`).join(' + ')}
            </li>
            {tv.excessReversion.excess10d.bucket && (
              <li>
                10d超额{fmtPct(tv.excessReversion.excess10d.value)} 处于{tv.excessReversion.excess10d.bucket}
                {tv.excessReversion.excess10d.bucketAvgExc1d != null && (
                  <>，同档T+1超额{fmtPct(tv.excessReversion.excess10d.bucketAvgExc1d)}，胜率{fmtWr(tv.excessReversion.excess10d.bucketWr1d)}</>
                )}
              </li>
            )}
            {tv.excessReversion.excess5d.bucket && tv.excessReversion.excess5d.bucket !== 'P30-P70(中性)' && (
              <li>
                5d超额{fmtPct(tv.excessReversion.excess5d.value)} 处于{tv.excessReversion.excess5d.bucket}
                {tv.excessReversion.excess5d.bucketAvgExc1d != null && (
                  <>，同档T+1超额{fmtPct(tv.excessReversion.excess5d.bucketAvgExc1d)}，胜率{fmtWr(tv.excessReversion.excess5d.bucketWr1d)}</>
                )}
              </li>
            )}
          </ul>
        </div>
      </div>

      {/* 明日操作 */}
      <div className="tc-decision-section">
        <div className="tc-decision-header">明日操作</div>
        <div className="tc-decision-verdict" style={{ borderLeftColor: actionColor(ta.action) }}>
          <div className="tc-decision-conclusion" style={{ color: actionColor(ta.action) }}>
            {ta.action}
          </div>
          <div className="tc-decision-meta">
            置信度：<strong>{ta.confidence === 'high' ? '高' : ta.confidence === 'low' ? '低' : '中'}</strong>
          </div>
        </div>
        <div className="tc-decision-evidence">
          <div className="tc-evidence-label">依据</div>
          <ul>
            {ta.bearishSignals.length > 0 && (
              <li>
                负向信号({ta.bearishSignals.length})：{ta.bearishSignals.map(s => {
                  const tag = alphaTag(s.alphaType);
                  const dir = dirIcon(s.directionPattern);
                  return <span key={s.signal} className="tc-signal-chip"><span className={tag.cls}>{tag.label}</span> {s.signal} {fmtPct(s.excLift)} {dir}{s.isNew && <span className="tc-new-badge">NEW</span>}</span>;
                })}
              </li>
            )}
            {ta.bullishSignals.length > 0 && (
              <li>
                支持信号({ta.bullishSignals.length})：{ta.bullishSignals.map(s => {
                  const tag = alphaTag(s.alphaType);
                  const dir = dirIcon(s.directionPattern);
                  return <span key={s.signal} className="tc-signal-chip"><span className={tag.cls}>{tag.label}</span> {s.signal} {fmtPct(s.excLift)} {dir}{s.isNew && <span className="tc-new-badge">NEW</span>}</span>;
                })}
              </li>
            )}
            {ta.bullishSignals.length === 0 && (
              <li>纯Alpha信号：无</li>
            )}
            {ta.keyRisks.length > 0 && (
              <li>风险：{ta.keyRisks.slice(0, 3).join('；')}</li>
            )}
            {ta.historicalAnalogy.similarCount > 0 && (
              <li>
                类比：{ta.historicalAnalogy.similarCount}个相似日
                T+1 {fmtPct(ta.historicalAnalogy.avgT1)}
                T+3 {fmtPct(ta.historicalAnalogy.avgT3)}
                胜率{fmtWr(ta.historicalAnalogy.winRate1d)}
              </li>
            )}
            {ta.flipConditions.length > 0 && (
              <li>翻转条件：{ta.flipConditions.join('；')}</li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}
