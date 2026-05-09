import { NextResponse } from 'next/server';
import {
  getHistorySummary,
  getQuadrantStats,
  getSignalLifts,
  getExtremeDivergences,
  getRollingMetrics,
  getStateTransitions,
  getEventStudy,
} from '@/lib/data-reader';

export async function GET() {
  try {
    const [
      summary,
      quadrants,
      signals,
      divergences,
      rolling,
      transitions,
      events,
    ] = await Promise.all([
      getHistorySummary(),
      getQuadrantStats(),
      getSignalLifts(),
      getExtremeDivergences(),
      getRollingMetrics(),
      getStateTransitions(),
      getEventStudy(),
    ]);

    return NextResponse.json({
      summary,
      quadrants,
      signals,
      divergences,
      rolling,
      transitions,
      events,
    });
  } catch (error) {
    console.error('Failed to fetch history data:', error);
    return NextResponse.json({ error: 'Failed to fetch history data' }, { status: 500 });
  }
}
