'use client';

import { TooltipProvider } from '@/components/ui/tooltip';
import { LeftSidebar } from '@/components/dashboard/left-sidebar';
import { IndustrySnapshot, PeerMatrixRow, PoolConfig } from '@/types';

interface DashboardShellProps {
  children: React.ReactNode;
  snapshot: IndustrySnapshot | null;
  matrix: PeerMatrixRow[];
  config: PoolConfig | null;
}

export function DashboardShell({ children, snapshot, matrix, config }: DashboardShellProps) {
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
          {children}
        </div>
      </div>
    </TooltipProvider>
  );
}
