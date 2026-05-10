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
  HistoryPersonalityProfile,
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
import { TodayHistoryMappingPanel } from './today-history-mapping-panel';
import { OperatorSignalInsights } from './operator-signal-insights';
import { QuadrantSignalBreakdown } from './quadrant-signal-breakdown';
import { OperatorCombinationSummary } from './operator-combination-summary';
import { PersonalitySummaryCard } from './personality-summary-card';
import { MetricsBar } from './metrics-bar';
import { HabitPatternList } from './habit-pattern-list';
import { RelationshipProfilePanel } from './relationship-profile-panel';
import { PathPatternPanel } from './path-pattern-panel';

interface HistoryDashboardProps {
  initialSummary: HistorySummaryRow[];
  initialQuadrants: QuadrantStat[];
  initialSignals: SignalLiftRow[];
  initialDivergences: ExtremeDivergence[];
  initialRolling: RollingMetricRow[];
  initialTransitions: StateTransition[];
  initialEvents: EventPathRow[];
  initialOperatorView: OperatorHistoryView | null;
  initialPersonalityProfile: HistoryPersonalityProfile | null;
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
  initialPersonalityProfile,
}: HistoryDashboardProps) {
  // 日期范围
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

  const signalTrends = useMemo(() => {
    return deriveSignalTrends(filteredSignals, filteredSummary);
  }, [filteredSignals, filteredSummary]);

  const combinations = useMemo(() => {
    return analyzeSignalCombinations(filteredSummary);
  }, [filteredSummary]);

  const combinationSynergies = useMemo(() => {
    return deriveCombinationSynergy(combinations, filteredSignals, { minCount: 8 });
  }, [combinations, filteredSignals]);

  const trendMap = useMemo(() => {
    const map = new Map<string, typeof signalTrends[number]>();
    for (const t of signalTrends) map.set(t.label, t);
    return map;
  }, [signalTrends]);

  // 从 personality profile 分离模式
  const likesPatterns = useMemo(() => {
    return initialPersonalityProfile?.habit_patterns.filter(p => p.habit_type === 'likes') || [];
  }, [initialPersonalityProfile]);

  const dislikesPatterns = useMemo(() => {
    return initialPersonalityProfile?.habit_patterns.filter(p => p.habit_type === 'dislikes') || [];
  }, [initialPersonalityProfile]);

  return (
    <div className="space-y-4 p-4 max-w-[1600px] mx-auto">
      {/* 主标题 */}
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold text-anchor-text tracking-wide">
          历史性格档案
        </h1>
        {/* 筛选器弱化 */}
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
      </div>

      {/* 历史性格画像区 */}
      {initialPersonalityProfile ? (
        <>
          {/* 顶部档案摘要 */}
          <PersonalitySummaryCard
            summary={initialPersonalityProfile.personality_summary}
            summaryMetrics={initialPersonalityProfile.summary_metrics}
            sampleDays={initialPersonalityProfile.sample_days}
            validSampleDays={initialPersonalityProfile.valid_sample_days}
            sampleWarnings={initialPersonalityProfile.sample_warnings}
            likesCount={likesPatterns.length}
            dislikesCount={dislikesPatterns.length}
            counterIntuitiveCount={initialPersonalityProfile.counter_intuitive_patterns.length}
            trapCount={initialPersonalityProfile.trap_patterns.length}
          />

          {/* 横排指标 */}
          <MetricsBar
            metrics={initialPersonalityProfile.summary_metrics}
            sampleDays={initialPersonalityProfile.valid_sample_days}
          />

          {/* 左右两列主体 */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {/* 左列 */}
            <div className="space-y-4">
              <div className="bg-anchor-bgSecondary border border-anchor-border p-3">
                <HabitPatternList patterns={likesPatterns} type="likes" />
              </div>
              <div className="bg-anchor-bgSecondary border border-anchor-border p-3">
                <HabitPatternList patterns={dislikesPatterns} type="dislikes" />
              </div>
              <div className="bg-anchor-bgSecondary border border-anchor-border p-3">
                <RelationshipProfilePanel profile={initialPersonalityProfile.relationship_profile} />
              </div>
            </div>

            {/* 右列 */}
            <div className="space-y-4">
              <div className="bg-anchor-bgSecondary border border-anchor-border p-3">
                <HabitPatternList
                  patterns={initialPersonalityProfile.counter_intuitive_patterns}
                  type="counter_intuitive"
                />
              </div>
              <div className="bg-anchor-bgSecondary border border-anchor-border p-3">
                <HabitPatternList
                  patterns={initialPersonalityProfile.trap_patterns}
                  type="trap"
                />
              </div>
              <div className="bg-anchor-bgSecondary border border-anchor-border p-3">
                <PathPatternPanel patterns={initialPersonalityProfile.path_patterns} />
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
          <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-2">
            历史性格画像未生成
          </h2>
          <p className="text-xs text-anchor-textMuted">
            请先运行历史分析脚本生成 history_personality_profile.json。
          </p>
        </div>
      )}

      {/* 折叠区：今日判断 */}
      <details className="bg-anchor-bgSecondary border border-anchor-border">
        <summary className="cursor-pointer p-3 text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
          今日操盘视图
        </summary>
        <div className="p-3 pt-0 space-y-4">
          {initialOperatorView ? (
            <>
              <OperatorDecisionPanel view={initialOperatorView} />
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <RollingMetricsChart data={filteredRolling} />
                <HistoryTrendChart data={filteredSummary} />
              </div>
              <OperatorPlaybookPanel view={initialOperatorView} />
              <TodayHistoryMappingPanel summary={filteredSummary} />
              <OperatorSignalInsights
                opportunities={initialOperatorView.counter_intuitive_signals}
                traps={initialOperatorView.signal_traps}
                roles={initialOperatorView.signal_roles}
                sampleDays={initialOperatorView.sample_days}
                dateRangeStart={initialOperatorView.date_range_start}
                dateRangeEnd={initialOperatorView.date_range_end}
              />
              <QuadrantSignalBreakdown
                effects={initialOperatorView.conditional_effects}
                summary={filteredSummary}
              />
              <OperatorCombinationSummary pairs={initialOperatorView.confirmation_pairs} />
            </>
          ) : (
            <div className="bg-anchor-bgSecondary p-4 border border-anchor-border">
              <p className="text-xs text-anchor-textMuted">操盘视图未生成</p>
            </div>
          )}
        </div>
      </details>

      {/* 折叠区：完整统计明细 */}
      <details className="bg-anchor-bgSecondary border border-anchor-border">
        <summary className="cursor-pointer p-3 text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
          完整统计明细
        </summary>
        <div className="p-3 pt-0 space-y-4">
          <ConclusionCard conclusion={conclusion} />
          <CoreMetrics metrics={coreMetrics} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-anchor-bgSecondary p-3 border border-anchor-border">
              <QuadrantGrid
                data={filteredQuadrants}
                bestQuadrant={conclusion.bestQuadrant}
                worstQuadrant={conclusion.worstQuadrant}
              />
            </div>
            <div className="bg-anchor-bgSecondary p-3 border border-anchor-border">
              <SignalLiftTable data={filteredSignals} trendMap={trendMap} />
            </div>
          </div>
          <SignalCombinations combinations={combinations} />
          <div className="bg-anchor-bgSecondary p-3 border border-anchor-border">
            <DivergenceTimeline
              divergences={divergencesWithFollowThrough}
              events={filteredEvents}
            />
          </div>
          <div className="bg-anchor-bgSecondary p-3 border border-anchor-border">
            <TransitionHeatmap
              data={filteredTransitions}
              summaries={transitionSummaries}
            />
          </div>
        </div>
      </details>
    </div>
  );
}
