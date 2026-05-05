// ============================================================
// Pools 页面 - 股票池配置工作台
// ============================================================

import { getConfig } from '@/lib/data-reader';
import { PoolsConfigWorkbench } from '@/components/pools/pools-config-workbench';

export default async function PoolsPage() {
  const config = await getConfig();

  if (!config) {
    return (
      <div className="flex h-[calc(100vh-3rem)] items-center justify-center">
        <div className="text-sm text-anchor-textMuted">暂无配置数据</div>
      </div>
    );
  }

  return <PoolsConfigWorkbench initialConfig={config} />;
}
