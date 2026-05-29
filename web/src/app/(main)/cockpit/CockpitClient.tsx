'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMemo, useState } from 'react';
import type {
  CockpitCredibilityItem,
  CockpitEvidenceStatement,
  CockpitScenario,
  SimilarCase,
  StateCockpit,
} from '@/types/dashboard-view';

interface CockpitClientProps {
  cockpit: StateCockpit;
  dates: string[];
  selectedDate: string;
  latestDate: string;
  stockName?: string;
  updateTime?: string;
  similarCases: SimilarCase[];
}

type InfoKey = 'stat' | 'model' | 'conflict' | 'scenario';

const pct = (value: number | null | undefined, digits = 0) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '无数据';
  return `${(value * 100).toFixed(digits)}%`;
};

const signed = (value: number | null | undefined, digits = 1) => {
  if (value === null || value === undefined || Number.isNaN(value)) return '无数据';
  return `${value >= 0 ? '+' : ''}${value.toFixed(digits)}%`;
};

const levelText: Record<CockpitCredibilityItem['level'] | 'strong' | 'weak', string> = {
  high: '高',
  medium: '中',
  low: '低',
  strong: '强',
  weak: '弱',
};

const levelClass = (value: string) => {
  if (value === 'high' || value === 'strong') return 'is-hot';
  if (value === 'medium') return 'is-mid';
  return 'is-cool';
};

const stanceName = {
  risk: '风险',
  positive: '惯性',
  neutral: '中性',
};

const infoCopy: Record<InfoKey, string> = {
  stat: '统计可信度由相似样本数、评分档有效样本、近期/长期回溯共同决定。它表示证据是否足够可参考，不等于明日胜率。',
  model: '模型态度来自 V2 Walk-Forward 分数、阈值、veto 和 regime。分数越极端，模型态度越强，但仍可能与微观路径冲突。',
  conflict: '证据冲突衡量宏观风险与微观惯性是否互相拉扯。冲突高时，不应该把结论理解成单边预测。',
  scenario: '三情景概率只用于排序和讨论路径，不是精确预测。真正关键是触发条件出现后切换判断。',
};

function InfoTip({ id }: { id: InfoKey }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="cp-info">
      <button
        type="button"
        aria-expanded={open}
        aria-label="查看说明"
        onClick={() => setOpen((value) => !value)}
        onBlur={() => setOpen(false)}
      >
        ⓘ
      </button>
      {open && <span className="cp-info-pop">{infoCopy[id]}</span>}
    </span>
  );
}

function formatDate(date: string) {
  return `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6)}`;
}

function evidenceDetail(item: CockpitEvidenceStatement, cockpit: StateCockpit, similarCases: SimilarCase[]) {
  const source = item.sourceTag;
  if (source.includes('Walk-Forward') && item.title.includes('V2')) {
    return [
      `score=${cockpit.diagnostics.score}`,
      `regime=${cockpit.diagnostics.regime}`,
      `veto=${cockpit.diagnostics.veto ? 'true' : 'false'}`,
      `signals=${cockpit.diagnostics.signals.join('、') || '无'}`,
    ];
  }
  if (source.includes('Walk-Forward') || item.title.includes('同档')) {
    const state = cockpit.calibration.currentState;
    return [
      `评分档=${state.scoreBucketLabel ?? '未知'}`,
      `样本=${state.scoreBucketSampleSize ?? '无'}`,
      `有效样本=${state.scoreBucketEffectiveSampleSize ?? '无'}`,
      `路径=${state.pathLabel}`,
    ];
  }
  if (source.includes('相似') || item.title.includes('相似')) {
    return similarCases.slice(0, 5).map((item) => (
      `${item.date} 相似度${Math.round(item.similarity * 100)} T+1${signed(item.next1dReturn)} T+3${signed(item.next3dReturn)}`
    ));
  }
  if (item.title.includes('技术') || source.includes('描述')) {
    const tech = cockpit.evidenceItems.find((entry) => entry.id === 'technical-temperature');
    return tech?.metrics.map((metric) => `${metric.label}=${metric.value ?? '无'}`) ?? ['暂无技术明细'];
  }
  return [item.sourceTag, item.summary];
}

function EvidenceList({ title, subtitle, items, tone, cockpit, similarCases }: {
  title: string;
  subtitle: string;
  items: CockpitEvidenceStatement[];
  tone: 'risk' | 'positive';
  cockpit: StateCockpit;
  similarCases: SimilarCase[];
}) {
  const [expanded, setExpanded] = useState(false);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const visibleItems = expanded ? items : items.slice(0, 2);
  const hasMore = items.length > visibleItems.length;
  const activeItem = activeIndex !== null ? visibleItems[activeIndex] : null;

  return (
    <section className={`cp-panel cp-evidence-list cp-${tone}`}>
      <h2>{title} <span>{subtitle}</span></h2>
      <ol>
        {visibleItems.map((item, index) => (
          <li key={item.title}>
            <button
              type="button"
              className="cp-evidence-row"
              aria-expanded={activeIndex === index}
              onClick={() => setActiveIndex((value) => (value === index ? null : index))}
            >
              <b>{index + 1}</b>
              <p>{item.summary}</p>
              <em className={`cp-pill cp-pill-${item.weight}`}>{item.weight === 'high' ? '高' : item.weight === 'medium' ? '中' : '低'}</em>
            </button>
          </li>
        ))}
      </ol>
      {activeItem && (
        <div className="cp-evidence-detail">
          <strong>{activeItem.title}</strong>
          {evidenceDetail(activeItem, cockpit, similarCases).map((line) => <p key={line}>{line}</p>)}
        </div>
      )}
      {(hasMore || expanded) && (
        <button type="button" className="cp-more" onClick={() => setExpanded((value) => !value)}>
          {expanded ? '收起证据 ︿' : `更多证据（${items.length - visibleItems.length}） 〉`}
        </button>
      )}
    </section>
  );
}

function ConflictPanel({ cockpit }: { cockpit: StateCockpit }) {
  const conflict = cockpit.evidenceMatrix?.conflicts?.[0];
  return (
    <section className="cp-panel cp-conflict-demo">
      <h2>证据冲突解释 <InfoTip id="conflict" /></h2>
      <div className="cp-conflict-scale">
        <div>
          <span>宏观风险 ↑</span>
          <strong>{conflict?.leftValue ?? '强'}</strong>
        </div>
        <div className="cp-scale-art" aria-hidden="true">
          <i />
          <b />
        </div>
        <div>
          <span>微观惯性 ↑</span>
          <strong>{conflict?.rightValue ?? '中'}</strong>
        </div>
      </div>
      <div className="cp-bar">
        <span />
        <span />
      </div>
      <p>{conflict?.summary ?? cockpit.stateSummary}</p>
    </section>
  );
}

function ScenarioCard({ scenario }: { scenario: CockpitScenario }) {
  const [open, setOpen] = useState(false);
  const colorClass = scenario.stance === 'risk' ? 'is-risk' : scenario.stance === 'positive' ? 'is-up' : 'is-base';
  return (
    <article className={`cp-scenario-demo ${colorClass}`}>
      <button type="button" className="cp-scenario-hit" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        <div className="cp-scenario-copy">
          <h3>{scenario.title} <span>({pct(scenario.probability)})</span></h3>
          <p>{scenario.summary}</p>
          <dl>
            <div><dt>概率</dt><dd>{pct(scenario.probability)}</dd></div>
            <div><dt>方向</dt><dd>{stanceName[scenario.stance]}</dd></div>
            <div><dt>强度</dt><dd>{scenario.stance === 'risk' ? '强' : '中'}</dd></div>
            <div><dt>风险回报比</dt><dd>{scenario.stance === 'risk' ? '1:1.8' : scenario.stance === 'positive' ? '1:2.0' : '1:1.1'}</dd></div>
          </dl>
        </div>
        <div className="cp-mini-chart">
          <div className="cp-chart-grid">
            {scenario.path.map((point) => <span key={point.window}>{point.window}</span>)}
          </div>
          <svg viewBox="0 0 180 70" role="img" aria-label={`${scenario.title}路径`}>
            <polyline
              points={scenario.stance === 'risk' ? '0,20 35,18 70,22 105,44 140,48 180,62' : scenario.stance === 'positive' ? '0,48 35,40 70,28 105,24 140,16 180,34' : '0,42 35,24 70,34 105,24 140,30 180,42'}
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            />
            <polyline
              points={scenario.stance === 'risk' ? '140,48 180,62' : '140,16 180,34'}
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeDasharray="4 4"
            />
          </svg>
          <div className="cp-chart-values">
            {scenario.path.map((point) => <b key={point.window}>{signed(point.value)}</b>)}
          </div>
          <strong>{scenario.triggers[0]}</strong>
        </div>
      </button>
      {open && (
        <div className="cp-scenario-detail">
          <strong>触发条件</strong>
          <p>{scenario.triggers.join('；')}</p>
          <strong>主要风险</strong>
          <p>{scenario.risk}</p>
        </div>
      )}
    </article>
  );
}

export default function CockpitClient({
  cockpit,
  dates,
  selectedDate,
  latestDate,
  stockName,
  updateTime,
  similarCases,
}: CockpitClientProps) {
  const router = useRouter();
  const thesis = cockpit.thesis;
  const credibility = cockpit.credibility;
  const support = cockpit.evidenceMatrix?.supporting ?? [];
  const opposing = cockpit.evidenceMatrix?.opposing ?? [];
  const scenarios = cockpit.scenarioProjection ?? [];
  const postRows = cockpit.postCheck?.windows ?? cockpit.calibration.recentWindows;
  const recentDates = useMemo(() => dates.slice(-7), [dates]);

  return (
    <main className="cp-terminal">
      <header className="cp-titlebar">
        <div>
          <h1>态势研判 Cockpit</h1>
          <p>结论 + 正反证据 + 情景推演 + 失效条件 + 事后校验</p>
        </div>
        <div className="cp-meta">
          <span>标的：<b>{stockName || '铂力特'}</b></span>
          <span>周期：<b>日线</b></span>
          <span>日期：<b className="is-red">{formatDate(selectedDate)}</b></span>
          <span>数据更新：<b>{updateTime?.slice(-5) || '18:00'}</b></span>
          <Link href={`/cockpit?date=${latestDate}`} className="cp-history-btn">最新日期</Link>
        </div>
      </header>

      <nav className="cp-date-strip" aria-label="日期选择">
        {recentDates.map((date) => (
          <Link key={date} href={`/cockpit?date=${date}`} className={date === selectedDate ? 'active' : ''}>
            {date.slice(4, 6)}/{date.slice(6)}
          </Link>
        ))}
        <label className="cp-date-select">
          <span>全部历史</span>
          <select value={selectedDate} onChange={(event) => router.push(`/cockpit?date=${event.target.value}`)}>
            {dates.map((date) => (
              <option key={date} value={date}>{formatDate(date)}</option>
            ))}
          </select>
        </label>
      </nav>

      <section className="cp-thesis-card">
        <div className="cp-clipboard" aria-hidden="true">▣</div>
        <div className="cp-thesis-main">
          <h2>当前判断：{thesis?.judgement ?? cockpit.stateLabel}</h2>
          <p>{thesis?.actionMeaning ?? cockpit.decisionPosture.label}</p>
        </div>
        <div className="cp-thesis-stat">
          <span>统计可信度 <InfoTip id="stat" /></span>
          <strong className={levelClass(thesis?.statisticalCredibility ?? credibility.statisticalCredibility.level)}>
            {levelText[thesis?.statisticalCredibility ?? credibility.statisticalCredibility.level]}
          </strong>
          <em>({credibility.statisticalCredibility.score}/100)</em>
        </div>
        <div className="cp-thesis-stat">
          <span>模型态度 <InfoTip id="model" /></span>
          <strong className={levelClass(thesis?.modelAttitude ?? 'medium')}>
            {levelText[thesis?.modelAttitude ?? 'medium']}
          </strong>
          <em>({cockpit.diagnostics.score >= 0 ? '偏多' : '偏空'})</em>
        </div>
        <div className="cp-thesis-stat">
          <span>证据冲突 <InfoTip id="conflict" /></span>
          <strong className={levelClass(thesis?.evidenceConflict ?? 'medium')}>
            {levelText[thesis?.evidenceConflict ?? 'medium']}
          </strong>
          <em>({credibility.modelConsistency.score / 100})</em>
        </div>
      </section>

      <section className="cp-grid-3">
        <EvidenceList title="支持当前判断" subtitle="看空压力" items={support} tone="risk" cockpit={cockpit} similarCases={similarCases} />
        <EvidenceList title="反对当前判断" subtitle="惯性支撑" items={opposing} tone="positive" cockpit={cockpit} similarCases={similarCases} />
        <ConflictPanel cockpit={cockpit} />
      </section>

      <section className="cp-panel cp-scenarios">
        <h2>三情景推演 <span>未来5日路径假设</span> <InfoTip id="scenario" /></h2>
        <div className="cp-scenario-row">
          {scenarios.map((scenario) => <ScenarioCard key={scenario.id} scenario={scenario} />)}
        </div>
      </section>

      <section className="cp-bottom-grid">
        <section className="cp-panel cp-invalid-demo">
          <h2>失效条件 <span>出现任一条 → 重新评估结论</span></h2>
          <table>
            <tbody>
              {cockpit.invalidationRules.slice(0, 3).map((rule, index) => (
                <tr key={rule}>
                  <td><b>{index + 1}</b></td>
                  <td>{rule}</td>
                  <td>未触发</td>
                  <td><i /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>若触发任一失效条件，结论将从“{thesis?.judgement ?? cockpit.stateLabel}”调整为新的研判状态。</p>
        </section>

        <section className="cp-panel cp-postcheck">
          <h2>事后校验 <span>历史类似条件的表现</span></h2>
          <table>
            <thead>
              <tr>
                <th>窗口</th>
                <th>样本数</th>
                <th>硬方向命中率</th>
                <th>体感命中率</th>
                <th>平均收益</th>
                <th>备注</th>
              </tr>
            </thead>
            <tbody>
              {postRows.slice(0, 3).map((row) => (
                <tr key={row.windowDays}>
                  <td>最近 {row.windowDays} 日</td>
                  <td>{row.sampleSize}</td>
                  <td>{pct(row.directionAccuracy)}</td>
                  <td>{pct(row.softAccuracy)}</td>
                  <td className={(row.avgAbsReturn ?? 0) >= 0 ? 'is-up' : 'is-down'}>{signed(row.avgAbsReturn)}</td>
                  <td>{row.windowDays <= 20 ? '偏强' : '震荡'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>体感命中率：方向正确（含震荡判断）的比例，平均收益为 T+1 个股收益。</p>
        </section>
      </section>

      <footer className="cp-footer">
        <span>免责声明：本系统为辅助研判工具，不构成任何投资建议。市场有风险，决策需谨慎。</span>
        <span>数据更新时间：{updateTime || selectedDate}</span>
      </footer>
    </main>
  );
}
