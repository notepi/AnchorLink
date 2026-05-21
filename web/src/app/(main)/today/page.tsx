import { Suspense } from 'react';
import { getDashboardView } from '@/lib/dashboard-view-reader';
import TodayTopBar from '@/components/today/TodayTopBar';
import AlertBar from '@/components/today/AlertBar';
import AttributionCard from '@/components/today/AttributionCard';
import ExcessCards from '@/components/today/ExcessCards';
import LinkageTable from '@/components/today/LinkageTable';
import TodayQuadrantGrid from '@/components/today/TodayQuadrantGrid';
import TransitionFlow from '@/components/today/TransitionFlow';
import SimilarCases from '@/components/today/SimilarCases';
import QuadrantDistribution from '@/components/today/QuadrantDistribution';
import SignalLiftQuickRef from '@/components/today/SignalLiftQuickRef';
import ResearchDetails from '@/components/today/ResearchDetails';
import type { DateEntry } from '@/types/dashboard-view';
import '../../../styles/today.css';

interface PageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default async function TodayPage({ searchParams }: PageProps) {
  const dashboard = await getDashboardView();
  const params = await searchParams;

  if (!dashboard) {
    return (
      <div className="today-cockpit" style={{ padding: '40px', textAlign: 'center' }}>
        数据加载失败，请稍后重试
      </div>
    );
  }

  // 所有可用日期
  const sortedDates = dashboard.dateIndex
    ? Object.keys(dashboard.dateIndex).sort()
    : (dashboard.trends?.excessReturn ?? []).map((e: { date: string }) => e.date).sort();
  const latestDate = sortedDates[sortedDates.length - 1] ?? '';

  // 当前选中日期
  const selectedDate =
    (typeof params.date === 'string' ? params.date : '') || latestDate;

  // dateIndex 条目（包含该日全部动态数据）
  const dateEntry: DateEntry | undefined = dashboard.dateIndex?.[selectedDate];

  // ── 随日期变化的字段（优先读 dateEntry，回退全局最新）──

  const currentMapping = dateEntry?.currentMapping ?? dashboard.summary.currentMapping;
  const todaySignals: string[] = currentMapping?.signalLabels ?? [];

  // 归因卡片
  const attribution =
    dateEntry?.todayAttribution ?? dashboard.summary?.todayAttribution ?? null;

  // 极端警报
  const alerts = dateEntry?.alerts ?? dashboard.summary?.alerts;

  // 状态迁移 top5
  const transitionTop5 = dateEntry?.transitionTop5 ?? dashboard.summary?.transitionTop5;

  // 联动状态：先从 dateEntry.poolCorrSnapshot 取，否则从 trends 数组里找
  const poolCorrelations = dashboard.trends?.poolCorrelations ?? [];
  const todayCorr =
    dateEntry?.poolCorrSnapshot ??
    poolCorrelations.find((c: { date: string }) => c.date === selectedDate) ??
    poolCorrelations[poolCorrelations.length - 1] ??
    null;

  // 相似案例
  const similarCases = dateEntry?.similarCases ?? dashboard.tableData?.similarCases ?? [];

  // ── 全局统计字段（不随日期变化）──

  const quadrantStats = dashboard.tableData?.quadrantStats ?? [];
  const allLifts = dashboard.tableData?.signalLifts ?? dashboard.tableData?.signalDetail ?? [];

  // 当前象限 key（用于 9 格高亮）
  const currentQuadrant =
    (dateEntry?.todayAttribution?.currentQuadrant
      ?? attribution?.currentQuadrant
      ?? currentMapping?.quadrantState) as string | undefined;

  const currentQuadrantLabel =
    dateEntry?.todayAttribution?.currentQuadrantLabel ??
    attribution?.currentQuadrantLabel ??
    currentMapping?.quadrantLabel ??
    '-';

  const currentQuadrantStat = quadrantStats.find(
    (q: { quadrant: string }) => q.quadrant === currentQuadrant
  );
  const currentGuidance =
    dashboard.summary?.currentQuadrantGuidance ?? currentQuadrantStat?.guidance;
  const currentWinRate = currentQuadrantStat?.winRate1d;

  // 超额收益（ExcessCards 内部按 selectedDate 查找）
  const excessReturn = dashboard.trends?.excessReturn ?? [];

  return (
    <div className="today-cockpit">
      {/* 日期选择器 */}
      <Suspense fallback={<div className="tc-topbar" style={{ height: 80 }} />}>
        <TodayTopBar
          sortedDates={sortedDates}
          selectedDate={selectedDate}
          latestDate={latestDate}
          stockName={dashboard.meta?.stockName}
          dataUpdateTime={dashboard.meta?.dataUpdateTime}
        />
      </Suspense>

      {/* Tier 4: 极端警报条 */}
      <AlertBar alerts={alerts} />

      {/* Tier 1: 首屏核心信息 */}
      <AttributionCard attribution={attribution} />
      <ExcessCards
        excessReturn={excessReturn}
        selectedDate={selectedDate}
        todayDeviation={attribution?.alphaVsIndustryChain}
      />
      <LinkageTable todayCorr={todayCorr} />

      {/* 当前象限 9 格定位 */}
      <TodayQuadrantGrid quadrants={quadrantStats} currentQuadrant={currentQuadrant} />

      {/* 状态迁移 */}
      <TransitionFlow
        transitions={transitionTop5}
        currentQuadrantLabel={currentQuadrantLabel}
        currentGuidance={currentGuidance}
        currentWinRate={currentWinRate}
      />

      {/* Tier 2: 历史参照 */}
      <SimilarCases cases={similarCases} />
      <QuadrantDistribution quadrants={quadrantStats} currentQuadrant={currentQuadrant} />
      <SignalLiftQuickRef todaySignals={todaySignals} allLifts={allLifts} />

      {/* Tier 3: 折叠研究明细 */}
      <ResearchDetails />

      {/* 页脚免责 */}
      <footer className="tc-footer">
        <p>
          ⚠️ 本页面为历史统计描述，<strong>不构成投资建议</strong>。
          T+1 方向命中率 48.3%（242 天回测），低于随机基准。
          所有数据基于历史规律，未来表现不保证重现。
        </p>
      </footer>
    </div>
  );
}
