'use client';

import { useEffect, useState } from 'react';
import { useAppStore } from '@/lib/store';
import { SignalPanel } from '@/components/dashboard/signal-panel';
import { ConclusionPanel } from '@/components/dashboard/conclusion-panel';
import { RankingTable } from '@/components/dashboard/ranking-table';
import { PoolStrengthDashboard } from '@/components/dashboard/pool-strength-dashboard';
import { LinkagePanel } from '@/components/dashboard/linkage-panel';
import { LeftSidebar } from '@/components/dashboard/left-sidebar';
import { DateSelector } from '@/components/common/date-selector';
import { TooltipProvider } from '@/components/ui/tooltip';
import type { IndustrySnapshot, PeerMatrixRow, PoolConfig } from '@/types';

export default function DashboardPage() {
  const selectedDate = useAppStore((state) => state.selectedDate);

  const [snapshot, setSnapshot] = useState<IndustrySnapshot | null>(null);
  const [matrix, setMatrix] = useState<PeerMatrixRow[]>([]);
  const [config, setConfig] = useState<PoolConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 初始化并获取数据
  useEffect(() => {
    let ignore = false;

    async function init() {
      let targetDate = selectedDate;
      if (!targetDate) {
        try {
          const datesRes = await fetch('/api/dates');
          const datesData = await datesRes.json();
          if (datesData.dates?.length > 0) {
            targetDate = datesData.dates[0];
            useAppStore.getState().setAvailableDates(datesData.dates);
            useAppStore.getState().setDate(targetDate);
          }
        } catch (err) {
          console.error('Failed to fetch dates:', err);
          setIsLoading(false);
          return;
        }
      }

      if (ignore || !targetDate) return;

      try {
        const [snapRes, matRes, cfgRes] = await Promise.all([
          fetch(`/api/snapshot?date=${targetDate}`),
          fetch(`/api/matrix?date=${targetDate}`),
          fetch('/api/config'),
        ]);

        if (ignore) return;

        const [snapData, matData, cfgData] = await Promise.all([
          snapRes.json(),
          matRes.json(),
          cfgRes.json(),
        ]);

        if (ignore) return;

        setSnapshot(snapData);
        setMatrix(matData.matrix || []);
        setConfig(cfgData);
      } catch (err) {
        console.error('Init error:', err);
      } finally {
        if (!ignore) setIsLoading(false);
      }
    }

    init();
    return () => { ignore = true; };
  }, [selectedDate]);

  const memberships = config?.memberships || [];
  const instruments = config?.instruments || [];

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex h-[calc(100vh-3rem)]">
        <LeftSidebar
          memberships={memberships}
          instruments={instruments}
          matrix={matrix}
          snapshot={snapshot}
        />
        <div className="flex-1 overflow-y-auto p-4">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-sm font-medium text-anchor-text">仪表盘</h1>
            <DateSelector />
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-sm text-anchor-textSecondary">加载中...</div>
            </div>
          ) : !snapshot ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-sm text-anchor-textSecondary">
                暂无数据，请先运行分析脚本
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <PoolStrengthDashboard groupRotation={snapshot.group_rotation} />

              <SignalPanel
                signals={snapshot.signals}
                groupRotation={snapshot.group_rotation}
              />
              <ConclusionPanel
                conclusion={snapshot.conclusion}
                industryState={snapshot.industry_state}
              />
              <LinkagePanel data={snapshot.linkage_analysis} />
              <RankingTable data={matrix} />
            </div>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
}