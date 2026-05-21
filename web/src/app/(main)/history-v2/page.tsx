import { Suspense } from 'react';
import { getDashboardView } from '@/lib/dashboard-view-reader';
import TopBar from '@/components/history-v2/TopBar';
import HistoryMapping from '@/components/history-v2/HistoryMapping';
import TransitionHeatmap from '@/components/history-v2/TransitionHeatmap';
import StabilityPanel from '@/components/history-v2/StabilityPanelClient';
import PersonalityProfile from '@/components/history-v2/PersonalityProfile';
import SignalTimeline from '@/components/history-v2/SignalTimeline';
import SignalLiftTable from '@/components/history-v2/SignalLiftTable';
import QuadrantGrid from '@/components/history-v2/QuadrantGrid';
import SignalCombinations from '@/components/history-v2/SignalCombinations';
import DivergenceTimeline from '@/components/history-v2/DivergenceTimeline';
import PredictionEvaluationPanel from '@/components/history-v2/PredictionEvaluationPanel';
import type { DateEntry } from '@/types/dashboard-view';
import '../../../styles/history-v2.css';

interface PageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default async function HistoryV2Page({ searchParams }: PageProps) {
  const dashboard = await getDashboardView();
  const params = await searchParams;

  if (!dashboard) {
    return <div className="page" style={{ padding: '40px', textAlign: 'center', color: 'var(--muted)' }}>数据加载失败，请稍后重试</div>;
  }

  const sortedDates = [...new Set(
    dashboard.trends.signalTimeline.map((item: { date: string }) => item.date)
  )].sort();

  const latestDate = sortedDates[sortedDates.length - 1] ?? '';

  // 日期选择：?date= 或默认最新
  const selectedDate = (typeof params.date === 'string' ? params.date : '') || latestDate;

  // 范围筛选：?startDate=&endDate=
  const startDate = typeof params.startDate === 'string' ? params.startDate : '';
  const endDate = typeof params.endDate === 'string' ? params.endDate : '';
  const isRangeMode = params.range === '1';

  // 从 dateIndex 获取选中日期的映射数据
  const dateEntry: DateEntry | undefined = dashboard.dateIndex?.[selectedDate];
  const currentMapping = dateEntry?.currentMapping ?? dashboard.summary.currentMapping;
  const similarCases = dateEntry?.similarCases ?? dashboard.tableData.similarCases;
  const windowStats = dateEntry?.windowStats ?? dashboard.tableData.windowStats;
  const pathLabel = dateEntry?.pathLabel ?? dashboard.summary.pathLabel;

  // 合并卡片：用 dateEntry 的按日变化卡片覆盖同名卡片
  const mergedCards = (() => {
    if (!dateEntry?.cards?.length) return dashboard.cards;
    const overrideMap = new Map(dateEntry.cards.map(c => [c.title ?? c.label ?? '', c]));
    return dashboard.cards.map(c => {
      const key = c.title ?? c.label ?? '';
      return overrideMap.get(key) ?? c;
    });
  })();

  // 提取3个按日指标
  const dailyMetricTitles = ['5日超额', '10日超额', '今日偏离'];
  const dailyMetrics = (dateEntry?.cards ?? dashboard.cards).filter(c =>
    dailyMetricTitles.includes(c.title ?? c.label ?? '')
  );

  // 范围筛选趋势数据
  const filterByRange = <T extends { date: string }>(data: T[]): T[] => {
    if (!isRangeMode || !startDate || !endDate) return data;
    return data.filter(item => item.date >= startDate && item.date <= endDate);
  };

  const filteredExcessReturn = filterByRange(dashboard.trends.excessReturn);
  const filteredFollowDeviation = filterByRange(dashboard.trends.followDeviation);
  const filteredSignalTimeline = filterByRange(dashboard.trends.signalTimeline);

  return (
    <div className="history-v2-page">
      <main className="page">
        <Suspense fallback={<header className="topbar" />}>
          <TopBar meta={dashboard.meta} filter={dashboard.filter} sortedDates={sortedDates} />
        </Suspense>
        <HistoryMapping
          currentMapping={currentMapping}
          pathLabel={pathLabel}
          similarCases={similarCases}
          windowStats={windowStats}
          priceHistory={isRangeMode ? filteredExcessReturn : dashboard.trends.excessReturn}
          dailyMetrics={dailyMetrics}
          confidenceIntervals={dashboard.predictionEvaluation?.confidenceIntervals}
        />
        <TransitionHeatmap
          transitionData={dashboard.tableData.stateTransitions}
          pathRanking={dashboard.tableData.rankedTransitionPaths}
          pathStats={dashboard.tableData.pathStats}
          currentMapping={currentMapping}
          transitionVerdict={dashboard.summary.transitionVerdict}
        />
        <StabilityPanel
          stabilityData={dashboard.personality.stability}
          excessReturnData={filteredExcessReturn}
          followDeviationData={filteredFollowDeviation}
          relationshipProfile={dashboard.tableData.relationshipProfile}
        />
        <PredictionEvaluationPanel predictionEvaluation={dashboard.predictionEvaluation} />
        <PersonalityProfile personalityData={dashboard.personality} profile={dashboard.summary.profile} />
        <SignalTimeline signalData={filteredSignalTimeline} />
        <details className="research">
          <summary>
            <span>研究明细</span>
            <span className="muted">九宫格统计 / 信号排行 / 组合效应 / 极端背离事件</span>
          </summary>
          <div className="research-content">
            {dashboard.aiInsight.researchDetails && (
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '12px' }}>{dashboard.aiInsight.researchDetails}</p>
            )}
            <div className="profile-grid">
              <div className="stack">
                <QuadrantGrid
                  data={dashboard.tableData.quadrantStats}
                  bestQuadrant={dashboard.tableData.conclusion.bestQuadrant}
                  worstQuadrant={dashboard.tableData.conclusion.worstQuadrant}
                />
                <SignalLiftTable data={dashboard.tableData.signalDetail} />
              </div>
              <div className="stack">
                <SignalCombinations
                  combinations={dashboard.tableData.signalCombinations}
                  synergies={dashboard.tableData.combinationSynergies}
                />
                <DivergenceTimeline data={dashboard.tableData.extremeDivergences} />
              </div>
            </div>
          </div>
        </details>
      </main>
    </div>
  );
}
