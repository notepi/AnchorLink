'use client';

import { LinkageAnalysis, PoolLinkage, LinkageMember } from '@/types';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { cn, getPoolDisplayName } from '@/lib/utils';

interface LinkagePanelProps {
  data: LinkageAnalysis | null;
}

const poolNames: Record<string, string> = {
  direct_peers: '核心',
  industry_chain: '产业',
  theme_pool: '主题',
  trading_watchlist: '交易',
};

// 格式化相关性系数
function formatCorr(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return value.toFixed(2);
}

// 格式化 Beta
function formatBeta(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return value.toFixed(2);
}

// 格式化方向一致性
function formatConsistency(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return `${(value * 100).toFixed(0)}%`;
}

// 相关性颜色（越高越好，绿色；低则红色）
function getCorrColorClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'text-anchor-textSecondary';
  if (value >= 0.6) return 'text-anchor-positive';
  if (value >= 0.3) return 'text-anchor-accent';
  return 'text-anchor-negative';
}

// 方向一致性颜色
function getConsistencyColorClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'text-anchor-textSecondary';
  if (value >= 0.7) return 'text-anchor-positive';
  if (value >= 0.5) return 'text-anchor-accent';
  return 'text-anchor-negative';
}

// Beta 颜色（高 Beta 表示高弹性）
function getBetaColorClass(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'text-anchor-textSecondary';
  if (value >= 1.5) return 'text-anchor-positive';
  if (value >= 0.8) return 'text-anchor-accent';
  return 'text-anchor-textSecondary';
}

export function LinkagePanel({ data }: LinkagePanelProps) {
  if (!data || !data.pools) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>联动分析</CardTitle>
          <CardDescription>暂无数据</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const pools = Object.entries(data.pools);

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>联动分析</CardTitle>
        <CardDescription>
          回看窗口：{data.windows?.join('/')} 日 | 状态：{data.status}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 池级联动指标卡片 */}
        <div className="grid grid-cols-4 gap-3">
          {pools.map(([universeId, pool]) => (
            <div
              key={universeId}
              className="p-3 rounded-lg bg-anchor-bgSecondary border border-anchor-border"
            >
              <div className="text-xs font-medium text-anchor-text mb-2">
                {poolNames[universeId] || universeId}
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-anchor-textSecondary">相关性</span>
                  <span className={cn('font-mono', getCorrColorClass(pool.avg_corr_20d))}>
                    {formatCorr(pool.avg_corr_20d)}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-anchor-textSecondary">Beta</span>
                  <span className={cn('font-mono', getBetaColorClass(pool.avg_beta_20d))}>
                    {formatBeta(pool.avg_beta_20d)}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-anchor-textSecondary">方向一致</span>
                  <span className={cn('font-mono', getConsistencyColorClass(pool.avg_direction_consistency_20d))}>
                    {formatConsistency(pool.avg_direction_consistency_20d)}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* 成员联动详情 */}
        {pools.map(([universeId, pool]) => (
          <div key={`detail-${universeId}`} className="space-y-2">
            <div className="text-sm font-medium text-anchor-text">
              {poolNames[universeId] || universeId} - 成员联动
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[800px]">
                <thead className="bg-anchor-bg border-b border-anchor-border">
                  <tr>
                    <th className="px-2 py-1 text-left text-xs font-medium text-anchor-textSecondary">代码</th>
                    <th className="px-2 py-1 text-left text-xs font-medium text-anchor-textSecondary">名称</th>
                    <th className="px-2 py-1 text-left text-xs font-medium text-anchor-textSecondary">5日相关性</th>
                    <th className="px-2 py-1 text-left text-xs font-medium text-anchor-textSecondary">20日相关性</th>
                    <th className="px-2 py-1 text-left text-xs font-medium text-anchor-textSecondary">20日Beta</th>
                    <th className="px-2 py-1 text-left text-xs font-medium text-anchor-textSecondary">20日方向一致</th>
                    <th className="px-2 py-1 text-left text-xs font-medium text-anchor-textSecondary">观察天数</th>
                  </tr>
                </thead>
                <tbody>
                  {pool.members?.slice(0, 10).map((member, i) => (
                    <tr
                      key={`${member.symbol}-${i}`}
                      className="border-b border-anchor-border/50 hover:bg-anchor-bgSecondary/50"
                    >
                      <td className="px-2 py-1 text-xs font-mono text-anchor-text">{member.symbol}</td>
                      <td className="px-2 py-1 text-xs text-anchor-text">{member.name || '--'}</td>
                      <td className={cn('px-2 py-1 text-xs font-mono', getCorrColorClass(member.corr_5d))}>
                        {formatCorr(member.corr_5d)}
                      </td>
                      <td className={cn('px-2 py-1 text-xs font-mono', getCorrColorClass(member.corr_20d))}>
                        {formatCorr(member.corr_20d)}
                      </td>
                      <td className={cn('px-2 py-1 text-xs font-mono', getBetaColorClass(member.beta_20d))}>
                        {formatBeta(member.beta_20d)}
                      </td>
                      <td className={cn('px-2 py-1 text-xs font-mono', getConsistencyColorClass(member.direction_consistency_20d))}>
                        {formatConsistency(member.direction_consistency_20d)}
                      </td>
                      <td className="px-2 py-1 text-xs font-mono text-anchor-textSecondary">
                        {member.observations || '--'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}