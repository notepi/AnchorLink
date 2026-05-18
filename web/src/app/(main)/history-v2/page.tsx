import { Suspense } from 'react';
import { getDashboardView } from '@/lib/dashboard-view-reader';
import TopBar from '@/components/history-v2/TopBar';
import TradingView from '@/components/history-v2/TradingView';
import HistoryMapping from '@/components/history-v2/HistoryMapping';
import TransitionHeatmap from '@/components/history-v2/TransitionHeatmap';
import StabilityPanel from '@/components/history-v2/StabilityPanelClient';
import PersonalityProfile from '@/components/history-v2/PersonalityProfile';
import SignalTimeline from '@/components/history-v2/SignalTimeline';
import '../../../styles/history-v2.css';

export default async function HistoryV2Page() {
  const dashboard = await getDashboardView();

  if (!dashboard) {
    return <div className="page" style={{ padding: '40px', textAlign: 'center', color: 'var(--muted)' }}>数据加载失败，请稍后重试</div>;
  }

  const sortedDates = [...new Set(
    dashboard.trends.signalTimeline.map((item: { date: string }) => item.date)
  )].sort();

  return (
    <div className="history-v2-page">
      <main className="page">
        <Suspense fallback={<div className="topbar" />}>
          <TopBar meta={dashboard.meta} filter={dashboard.filter} sortedDates={sortedDates} />
        </Suspense>
        <TradingView cards={dashboard.cards} advice={dashboard.aiInsight.advice} />
        <HistoryMapping
          currentMapping={dashboard.summary.currentMapping}
          pathLabel={dashboard.summary.pathLabel}
          similarCases={dashboard.tableData.similarCases}
          windowStats={dashboard.tableData.windowStats}
        />
        <TransitionHeatmap
          transitionData={dashboard.tableData.stateTransitions}
          pathRanking={dashboard.tableData.rankedTransitionPaths}
          pathStats={dashboard.tableData.pathStats}
          currentMapping={dashboard.summary.currentMapping}
          transitionVerdict={dashboard.summary.transitionVerdict}
        />
        <StabilityPanel
          stabilityData={dashboard.personality.stability}
          excessReturnData={dashboard.trends.excessReturn}
          followDeviationData={dashboard.trends.followDeviation}
        />
        <PersonalityProfile personalityData={dashboard.personality} profile={dashboard.summary.profile} />
        <SignalTimeline signalData={dashboard.trends.signalTimeline} />
        <details className="research">
          <summary>
            <span>研究明细</span>
            <span className="muted">九宫格统计 / 信号排行 / 组合效应 / 极端背离事件</span>
          </summary>
          <div className="research-content">
            这里保留原始统计视图作为研究入口，默认折叠，避免主页面重新变成统计表集合。
          </div>
        </details>
      </main>
    </div>
  );
}

