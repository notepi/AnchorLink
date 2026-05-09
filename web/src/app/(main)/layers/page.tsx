// ============================================================
// Layers 页面 - 八层架构总览
// ============================================================

import Link from 'next/link';
import { getLatestSnapshot, getConfig } from '@/lib/data-reader';
import { PoolType } from '@/types';

// 层信息定义
const LAYERS = [
  {
    id: 'pool-state',
    layer: 4,
    name: 'Pool State',
    nameCn: '池子状态',
    description: '计算各池子中位数涨跌幅、上涨比例、资金流向等指标',
    input: 'Market Data',
    output: 'PoolState',
    rulesCount: 6,
    href: '/layers/pool-state',
  },
  {
    id: 'anchor-position',
    layer: 5,
    name: 'Anchor Position',
    nameCn: '锚定位置',
    description: '计算锚定标的相对强弱和五维排名',
    input: 'PoolState',
    output: 'AnchorPosition',
    rulesCount: 5,
    href: '/layers/anchor-position',
  },
  {
    id: 'group-rotation',
    layer: 6,
    name: 'Group Rotation',
    nameCn: '组间轮动',
    description: '比较四类池子之间谁强谁弱，计算spread',
    input: 'PoolState',
    output: 'GroupRotation',
    rulesCount: 3,
    href: '/layers/group-rotation',
  },
  {
    id: 'signals',
    layer: 7,
    name: 'Signals',
    nameCn: '信号标签',
    description: '根据规则匹配35+信号标签，计算置信度',
    input: 'PoolState + AnchorPosition',
    output: 'Signal[]',
    rulesCount: 35,
    href: '/layers/signals',
  },
  {
    id: 'conclusion',
    layer: 8,
    name: 'Conclusion',
    nameCn: '结论生成',
    description: '根据信号组合生成最终判定（Beta/Alpha/Risk/Summary）',
    input: 'Signals',
    output: 'Conclusion',
    rulesCount: 4,
    href: '/layers/conclusion',
  },
];

const POOL_NAMES: Record<PoolType, string> = {
  direct_peers: '增材制造本业确认池',
  industry_chain: '商业航天硬科技主池',
  theme_pool: '商业航天主题温度计',
  trading_watchlist: '交易联动与风险映射池',
};

export default async function LayersPage() {
  const snapshot = await getLatestSnapshot();
  const config = await getConfig();

  const dataStatus = snapshot?.data_quality?.status || 'unknown';
  const groupMedians = snapshot?.group_rotation?.group_medians || {};

  // 计算各池成员数
  const poolCounts = config?.memberships
    ? config.memberships.reduce((acc, m) => {
        if (m.enabled) {
          acc[m.universe_id] = (acc[m.universe_id] || 0) + 1;
        }
        return acc;
      }, {} as Record<string, number>)
    : {};

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-lg font-medium text-anchor-text">八层架构总览</h1>
        <p className="text-sm text-anchor-textMuted mt-1">
          展示 AnchorLink 完整数据流：从行情数据到最终结论
        </p>
      </div>

      {/* 架构流程图 */}
      <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
        <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
          数据流架构
        </h2>
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {/* Anchor */}
          <div className="flex flex-col items-center">
            <div className="bg-anchor-accent/10 border border-anchor-accent/30 rounded-sm px-3 py-2">
              <span className="text-xs font-mono text-anchor-accent">Anchor</span>
            </div>
            <span className="text-xs text-anchor-textMuted mt-1">铂力特</span>
          </div>

          <span className="text-anchor-textMuted mx-1">→</span>

          {/* Pool Membership */}
          <div className="flex flex-col items-center">
            <div className="bg-anchor-bg border border-anchor-border rounded-sm px-3 py-2">
              <span className="text-xs text-anchor-text">Pool Membership</span>
            </div>
            <span className="text-xs text-anchor-textMuted mt-1">股票池</span>
          </div>

          <span className="text-anchor-textMuted mx-1">→</span>

          {/* Market Data */}
          <div className="flex flex-col items-center">
            <div className="bg-anchor-bg border border-anchor-border rounded-sm px-3 py-2">
              <span className="text-xs text-anchor-text">Market Data</span>
            </div>
            <span className="text-xs text-anchor-textMuted mt-1">行情数据</span>
          </div>

          <span className="text-anchor-textMuted mx-1">→</span>

          {/* Layers */}
          {LAYERS.map((layer, i) => (
            <div key={layer.id} className="flex items-center">
              <div className="flex flex-col items-center">
                <div className={`border rounded-sm px-3 py-2 ${
                  layer.id === 'signals'
                    ? 'bg-anchor-accent/10 border-anchor-accent/30'
                    : 'bg-anchor-bg border-anchor-border'
                }`}>
                  <span className="text-xs text-anchor-text">L{layer.layer}</span>
                </div>
                <span className="text-xs text-anchor-textMuted mt-1">{layer.nameCn}</span>
              </div>
              {i < LAYERS.length - 1 && (
                <span className="text-anchor-textMuted mx-1">→</span>
              )}
            </div>
          ))}

          <span className="text-anchor-textMuted mx-1">→</span>

          {/* Output */}
          <div className="flex flex-col items-center">
            <div className="bg-anchor-bg border border-anchor-border rounded-sm px-3 py-2">
              <span className="text-xs text-anchor-text">JSON Report</span>
            </div>
            <span className="text-xs text-anchor-textMuted mt-1">输出</span>
          </div>
        </div>
      </div>

      {/* 层摘要卡片 */}
      <div className="grid grid-cols-5 gap-3">
        {LAYERS.map(layer => (
          <Link
            key={layer.id}
            href={layer.href}
            className="bg-anchor-bgSecondary rounded-sm p-3 border border-anchor-border hover:border-anchor-accent/50 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-anchor-accent font-mono">L{layer.layer}</span>
              <span className="text-xs text-anchor-textMuted">{layer.rulesCount} rules</span>
            </div>
            <h3 className="text-sm font-medium text-anchor-text mb-1">{layer.nameCn}</h3>
            <p className="text-xs text-anchor-textMuted">{layer.description}</p>
          </Link>
        ))}
      </div>

      {/* 数据质量降级链 */}
      <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
        <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
          数据质量降级链
        </h2>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm bg-anchor-positive/30" />
            <span className="text-xs text-anchor-text">OK</span>
          </div>
          <span className="text-anchor-textMuted">→</span>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm bg-yellow-500/30" />
            <span className="text-xs text-anchor-text">Partial</span>
          </div>
          <span className="text-anchor-textMuted">→</span>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm bg-anchor-negative/30" />
            <span className="text-xs text-anchor-text">Insufficient</span>
          </div>
          <span className="text-anchor-textMuted mx-4">|</span>
          <span className="text-xs text-anchor-textMuted">
            当前状态: <span className={
              dataStatus === 'ok' ? 'text-anchor-positive' :
              dataStatus === 'partial' ? 'text-yellow-500' :
              'text-anchor-negative'
            }>{dataStatus === 'ok' ? '正常' : dataStatus === 'partial' ? '部分缺失' : '数据不足'}</span>
          </span>
        </div>
        {snapshot?.data_quality?.missing_fields && snapshot.data_quality.missing_fields.length > 0 && (
          <div className="mt-2 text-xs text-anchor-textMuted">
            缺失字段: {snapshot.data_quality.missing_fields.join(', ')}
          </div>
        )}
      </div>

      {/* 三Scope模型 */}
      <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
        <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
          三Scope模型
        </h2>
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-anchor-bg rounded-sm p-3 border border-anchor-border">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-anchor-accent">benchmark_scope</span>
            </div>
            <p className="text-xs text-anchor-textMuted mb-2">用于计算池子指标的成员范围</p>
            <code className="text-xs text-anchor-text font-mono block bg-anchor-bgSecondary px-2 py-1 rounded">
              enabled=True AND include_in_benchmark=True
            </code>
          </div>
          <div className="bg-anchor-bg rounded-sm p-3 border border-anchor-border">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-anchor-accent">ranking_scope</span>
            </div>
            <p className="text-xs text-anchor-textMuted mb-2">用于计算锚定标的排名的成员范围</p>
            <code className="text-xs text-anchor-text font-mono block bg-anchor-bgSecondary px-2 py-1 rounded">
              enabled=True AND include_in_ranking=True
            </code>
          </div>
          <div className="bg-anchor-bg rounded-sm p-3 border border-anchor-border">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-anchor-accent">report_scope</span>
            </div>
            <p className="text-xs text-anchor-textMuted mb-2">包含在每日报告中的成员范围</p>
            <code className="text-xs text-anchor-text font-mono block bg-anchor-bgSecondary px-2 py-1 rounded">
              enabled=True AND include_in_report=True
            </code>
          </div>
        </div>

        {/* 各池成员数量 */}
        <div className="mt-4 grid grid-cols-4 gap-3">
          {(Object.keys(POOL_NAMES) as PoolType[]).map(poolId => (
            <div key={poolId} className="text-center">
              <div className="text-xs text-anchor-textMuted mb-1">{POOL_NAMES[poolId]}</div>
              <div className="text-lg font-mono text-anchor-text">
                {poolCounts[poolId] || 0}
                <span className="text-xs text-anchor-textMuted ml-1">members</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 各池当前数据 */}
      <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
        <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
          各池中位数涨跌幅（实时）
        </h2>
        <div className="grid grid-cols-4 gap-3">
          {(Object.keys(POOL_NAMES) as PoolType[]).map(poolId => {
            const median = groupMedians[poolId];
            const isPositive = median !== null && median !== undefined ? median >= 0 : null;
            return (
              <div key={poolId} className="bg-anchor-bg rounded-sm p-3 border border-anchor-border">
                <div className="text-xs text-anchor-textMuted mb-1">{POOL_NAMES[poolId]}</div>
                <div className={`text-lg font-mono ${
                  isPositive === null ? 'text-anchor-textMuted' :
                  isPositive ? 'text-anchor-positive' : 'text-anchor-negative'
                }`}>
                  {median !== null && median !== undefined
                    ? `${isPositive ? '+' : ''}${median.toFixed(2)}%`
                    : '--'}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}