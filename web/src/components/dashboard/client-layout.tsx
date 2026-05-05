'use client';

import { TooltipProvider } from '@/components/ui/tooltip';
import { LeftSidebar } from '@/components/dashboard/left-sidebar';
import { IndustrySnapshot, PeerMatrixRow, PoolConfig } from '@/types';

interface ClientLayoutProps {
  children: React.ReactNode;
  snapshot: IndustrySnapshot | null;
  matrix: PeerMatrixRow[];
  config: PoolConfig | null;
}

/**
 * 客户端布局包装器 - 包含所有交互组件
 */
export function ClientLayout({ children, snapshot, matrix, config }: ClientLayoutProps) {
  // 数据缺失时的默认值
  const memberships = config?.memberships || [];
  const instruments = config?.instruments || [];

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex flex-col h-screen">
        {/* 顶部状态栏（静态，由 Server Layout 渲染） */}

        {/* 主体区域 */}
        <div className="flex flex-1 overflow-hidden">
          {/* 左侧 Sidebar（交互组件） */}
          <LeftSidebar
            memberships={memberships}
            instruments={instruments}
            matrix={matrix}
            snapshot={snapshot}
          />

          {/* 主内容区 */}
          <main className="flex-1 overflow-y-auto p-4">
            {children}
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}