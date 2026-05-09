'use client';

import { useState, useMemo } from 'react';
import type {
  HistorySummaryRow,
  QuadrantStat,
  SignalLiftRow,
  ExtremeDivergence,
  RollingMetricRow,
  StateTransition,
  EventPathRow,
  OperatorHistoryView,
} from '@/types';
import {
  filterSummaryByDateRange,
  deriveQuadrantsFromSummary,
  deriveSignalLiftsFromSummary,
  deriveTransitionsFromSummary,
  deriveCoreMetrics,
  deriveConclusion,
  deriveTransitionSummary,
  deriveDivergenceFollowThrough,
  deriveSignalTrends,
  analyzeSignalCombinations,
  deriveCombinationSynergy,
  type CoreMetrics as CoreMetricsType,
  type Conclusion,
} from '@/lib/history-analysis';
import { FilterBar } from './filter-bar';
import { ConclusionCard } from './conclusion-card';
import { CoreMetrics } from './core-metrics';
import { HistoryTrendChart } from './history-trend-chart';
import { QuadrantGrid } from './quadrant-grid';
import { SignalLiftTable } from './signal-lift-table';
import { SignalCombinations } from './signal-combinations';
import { RollingMetricsChart } from './rolling-metrics-chart';
import { DivergenceTimeline } from './divergence-timeline';
import { TransitionHeatmap } from './transition-heatmap';
import { OperatorDecisionPanel } from './operator-decision-panel';
import { OperatorPlaybookPanel } from './operator-playbook-panel';
import { OperatorSignalInsights } from './operator-signal-insights';
import { QuadrantSignalBreakdown } from './quadrant-signal-breakdown';
import { OperatorCombinationSummary } from './operator-combination-summary';

interface HistoryDashboardProps {
  initialSummary: HistorySummaryRow[];
  initialQuadrants: QuadrantStat[];
  initialSignals: SignalLiftRow[];
  initialDivergences: ExtremeDivergence[];
  initialRolling: RollingMetricRow[];
  initialTransitions: StateTransition[];
  initialEvents: EventPathRow[];
  initialOperatorView: OperatorHistoryView | null;
}

export function HistoryDashboard({
  initialSummary,
  initialQuadrants,
  initialSignals,
  initialDivergences,
  initialRolling,
  initialTransitions,
  initialEvents,
  initialOperatorView,
}: HistoryDashboardProps) {
  // 日期范围（YYYYMMDD 格式）
  const sortedDates = useMemo(() => {
    return [...initialSummary].map((r) => r.date).sort();
  }, [initialSummary]);

  const [startDate, setStartDate] = useState<string>(sortedDates[0] || '');
  const [endDate, setEndDate] = useState<string>(sortedDates[sortedDates.length - 1] || '');
  const [signalCategory, setSignalCategory] = useState<string>('all');

  // 筛选后的数据
  const filteredSummary = useMemo(() => {
    return filterSummaryByDateRange(initialSummary, startDate, endDate);
  }, [initialSummary, startDate, endDate]);

  // 重算聚合数据
  const filteredQuadrants = useMemo(() => {
    return deriveQuadrantsFromSummary(filteredSummary);
  }, [filteredSummary]);

  const filteredSignals = useMemo(() => {
    return deriveSignalLiftsFromSummary(filteredSummary, signalCategory);
  }, [filteredSummary, signalCategory]);

  const filteredTransitions = useMemo(() => {
    return deriveTransitionsFromSummary(filteredSummary);
  }, [filteredSummary]);

  const filteredDivergences = useMemo(() => {
    return initialDivergences.filter((d) => d.date >= startDate && d.date <= endDate);
  }, [initialDivergences, startDate, endDate]);

  const filteredRolling = useMemo(() => {
    return initialRolling.filter((r) => r.date >= startDate && r.date <= endDate);
  }, [initialRolling, startDate, endDate]);

  const filteredEvents = useMemo(() => {
    return initialEvents.filter((e) => e.event_date >= startDate && e.event_date <= endDate);
  }, [initialEvents, startDate, endDate]);

  // 派生指标和结论
  const coreMetrics: CoreMetricsType = useMemo(() => {
    return deriveCoreMetrics(filteredSummary, filteredDivergences);
  }, [filteredSummary, filteredDivergences]);

  const conclusion: Conclusion = useMemo(() => {
    return deriveConclusion(filteredSummary, filteredQuadrants);
  }, [filteredSummary, filteredQuadrants]);

  const transitionSummaries = useMemo(() => {
    return deriveTransitionSummary(filteredTransitions);
  }, [filteredTransitions]);

  const divergencesWithFollowThrough = useMemo(() => {
    return deriveDivergenceFollowThrough(filteredDivergences, filteredEvents);
  }, [filteredDivergences, filteredEvents]);

  // 新增：信号趋势
  const signalTrends = useMemo(() => {
    return deriveSignalTrends(filteredSignals, filteredSummary);
  }, [filteredSignals, filteredSummary]);

  // 新增：信号组合
  const combinations = useMemo(() => {
    return analyzeSignalCombinations(filteredSummary);
  }, [filteredSummary]);

  // 新增：组合协同
  const combinationSynergies = useMemo(() => {
    return deriveCombinationSynergy(combinations, filteredSignals, { minCount: 8 });
  }, [combinations, filteredSignals]);

  // 趋势指标按 label 索引，方便组件查找
  const trendMap = useMemo(() => {
    const map = new Map<string, typeof signalTrends[number]>();
    for (const t of signalTrends) map.set(t.label, t);
    return map;
  }, [signalTrends]);

  return (
    <div className="space-y-6 p-4">
      {/* 筛选栏 */}
      <FilterBar
        sortedDates={sortedDates}
        startDate={startDate}
        endDate={endDate}
        signalCategory={signalCategory}
        onStartDateChange={setStartDate}
        onEndDateChange={setEndDate}
        onSignalCategoryChange={setSignalCategory}
        sampleDays={filteredSummary.filter((r) => r.data_quality_status !== 'insufficient_data').length}
      />

      {initialOperatorView ? (
        <>
          <OperatorDecisionPanel view={initialOperatorView} />

          <section className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <RollingMetricsChart data={filteredRolling} />
              <HistoryTrendChart data={filteredSummary} />
            </div>
          </section>

          <OperatorPlaybookPanel view={initialOperatorView} />
          <OperatorSignalInsights
            opportunities={initialOperatorView.counter_intuitive_signals}
            traps={initialOperatorView.signal_traps}
            roles={initialOperatorView.signal_roles}
          />
          <QuadrantSignalBreakdown
            effects={initialOperatorView.conditional_effects}
            summary={filteredSummary}
          />
          <OperatorCombinationSummary pairs={initialOperatorView.confirmation_pairs} />
        </>
      ) : (
        <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
          <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-2">
            操盘视图未生成
          </h2>
          <p className="text-xs text-anchor-textMuted">
            请先运行历史分析脚本生成 history_operator_playbook.json。
          </p>
        </div>
      )}

      {/* 结论卡片 */}
      <ConclusionCard conclusion={conclusion} />

      {/* 核心指标 */}
      <CoreMetrics metrics={coreMetrics} />

      {/* 四象限 + 信号明细 */}
      <details className="bg-anchor-bgSecondary rounded-sm border border-anchor-border">
        <summary className="cursor-pointer p-4 text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
          查看完整信号排行 / 组合明细 / 四象限
        </summary>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 p-4 pt-0">
        <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
          <QuadrantGrid
            data={filteredQuadrants}
            bestQuadrant={conclusion.bestQuadrant}
            worstQuadrant={conclusion.worstQuadrant}
          />
        </div>
        <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
          <SignalLiftTable data={filteredSignals} trendMap={trendMap} />
        </div>
        </div>

        <div className="p-4 pt-0">
          <SignalCombinations combinations={combinations} />
        </div>
      </details>

      {/* 极端背离 */}
      <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
        <DivergenceTimeline
          divergences={divergencesWithFollowThrough}
          events={filteredEvents}
        />
      </div>

      {/* 状态转移 */}
      <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
        <TransitionHeatmap
          data={filteredTransitions}
          summaries={transitionSummaries}
        />
      </div>
    </div>
  );
}
