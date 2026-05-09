import {
  getHistorySummary,
  getQuadrantStats,
  getSignalLifts,
  getExtremeDivergences,
  getRollingMetrics,
  getStateTransitions,
  getEventStudy,
  getHistoryOperatorPlaybook,
} from '@/lib/data-reader';
import { HistoryDashboard } from '@/components/history/history-dashboard';

export default async function HistoryPage() {
  const [
    summary,
    quadrants,
    signals,
    divergences,
    rolling,
    transitions,
    events,
    operatorView,
  ] = await Promise.all([
    getHistorySummary(),
    getQuadrantStats(),
    getSignalLifts(),
    getExtremeDivergences(),
    getRollingMetrics(),
    getStateTransitions(),
    getEventStudy(),
    getHistoryOperatorPlaybook(),
  ]);

  return (
    <HistoryDashboard
      initialSummary={summary}
      initialQuadrants={quadrants}
      initialSignals={signals}
      initialDivergences={divergences}
      initialRolling={rolling}
      initialTransitions={transitions}
      initialEvents={events}
      initialOperatorView={operatorView}
    />
  );
}
