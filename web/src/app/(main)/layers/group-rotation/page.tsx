// ============================================================
// Group Rotation 层 - 第6层：组间轮动计算逻辑
// ============================================================

import { getLatestSnapshot } from '@/lib/data-reader';
import { FormulaDisplay, ThresholdBar } from '@/components/common/layers/shared-components';
import { PoolType } from '@/types';

const POOL_NAMES: Record<PoolType, string> = {
  direct_peers: '核心同类池',
  industry_chain: '产业链池',
  theme_pool: '主题扩散池',
  trading_watchlist: '交易观察池',
};

const VALID_FILTER_RULES = [
  'can_be_benchmark = True',
  'data_status != "insufficient_data"',
  'median_return is not None',
];

const FORMULAS = [
  {
    name: 'spread',
    formula: 'core_pool_median - other_pool_median',
    description: '核心池与其他池的中位数差值',
  },
  {
    name: 'core_vs_theme_spread',
    formula: 'direct_peers_median - theme_pool_median',
    description: '核心同类 vs 主题扩散',
  },
  {
    name: 'core_vs_chain_spread',
    formula: 'direct_peers_median - industry_chain_median',
    description: '核心同类 vs 产业链',
  },
];

const JUDGMENT_RULES = [
  '按 median_return 降序排列',
  'strongest_group = 排名第一',
  'weakest_group = 排名最后',
  'spread > 0: 核心池更强',
  'spread < 0: 其他池更强',
];

export default async function GroupRotationPage() {
  const snapshot = await getLatestSnapshot();

  const groupMedians = snapshot?.group_rotation?.group_medians || {};
  const strongestGroup = snapshot?.group_rotation?.strongest_group || '';
  const weakestGroup = snapshot?.group_rotation?.weakest_group || '';
  const groupRanking = snapshot?.group_rotation?.group_ranking || [];
  const coreVsThemeSpread = snapshot?.group_rotation?.core_vs_theme_spread ?? null;
  const coreVsChainSpread = snapshot?.group_rotation?.core_vs_chain_spread ?? null;
  const coreVsTradingSpread = snapshot?.group_rotation?.core_vs_trading_spread ?? null;

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-lg font-medium text-anchor-text">组间轮动计算逻辑</h1>
        <p className="text-sm text-anchor-textMuted mt-1">
          L6 - 比较四类池子之间谁强谁弱，计算 spread
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* 左侧：计算逻辑 */}
        <div className="space-y-6">
          {/* 有效池筛选规则 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
              有效池筛选规则
            </h2>
            <div className="bg-anchor-bg rounded-sm p-3 font-mono text-xs space-y-1">
              {VALID_FILTER_RULES.map((rule, i) => (
                <div key={i} className="text-anchor-accent">• {rule}</div>
              ))}
              <div className="mt-2 pt-2 border-t border-anchor-border">
                <span className="text-anchor-text">MIN_VALID_GROUPS = </span>
                <span className="text-anchor-accent">2</span>
              </div>
              <div className="text-xs text-anchor-textMuted mt-1">
                至少需要 2 个有效池才能计算轮动
              </div>
            </div>
          </div>

          {/* 强弱判定规则 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
              强弱判定规则
            </h2>
            <div className="bg-anchor-bg rounded-sm p-3 font-mono text-xs space-y-1">
              {JUDGMENT_RULES.map((rule, i) => (
                <div key={i} className="text-anchor-text">{rule}</div>
              ))}
            </div>
          </div>

          {/* Spread 公式 */}
          <FormulaDisplay title="Spread 公式" formulas={FORMULAS} />

          {/* 阈值 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
              轮动判定阈值
            </h2>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-anchor-textMuted border-b border-anchor-border">
                  <th className="text-left py-1 font-medium">条件</th>
                  <th className="text-right py-1 font-medium">阈值</th>
                  <th className="text-left py-1 font-medium">判定</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-anchor-border/50">
                  <td className="py-1 text-anchor-text">核心同类强于主题扩散</td>
                  <td className="py-1 text-right font-mono text-anchor-accent">+1.0%</td>
                  <td className="py-1 text-anchor-up">核心更强</td>
                </tr>
                <tr className="border-b border-anchor-border/50">
                  <td className="py-1 text-anchor-text">主题扩散强于核心同类</td>
                  <td className="py-1 text-right font-mono text-anchor-accent">-1.0%</td>
                  <td className="py-1 text-anchor-down">主题更强</td>
                </tr>
                <tr className="border-b border-anchor-border/50">
                  <td className="py-1 text-anchor-text">产业链强于情绪池</td>
                  <td className="py-1 text-right font-mono text-anchor-accent">+1.0%</td>
                  <td className="py-1 text-anchor-up">产业链更强</td>
                </tr>
                <tr className="border-b border-anchor-border/50">
                  <td className="py-1 text-anchor-text">情绪池强于产业链</td>
                  <td className="py-1 text-right font-mono text-anchor-accent">-1.0%</td>
                  <td className="py-1 text-anchor-down">情绪更强</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* 右侧：实时数据 */}
        <div className="space-y-6">
          <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
            实时数据
          </h2>

          {/* 4池中位数 + 强弱排名 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <div className="text-xs text-anchor-textMuted mb-3">四池中位数涨跌幅</div>
            <div className="space-y-2">
              {groupRanking.length > 0 ? groupRanking.map((poolId, i) => {
                const median = groupMedians[poolId];
                const isPositive = median !== null && median !== undefined ? median >= 0 : null;
                const isStrongest = poolId === strongestGroup;
                const isWeakest = poolId === weakestGroup;

                return (
                  <div
                    key={poolId}
                    className={`flex items-center justify-between bg-anchor-bg rounded-sm px-3 py-2 ${
                      isStrongest ? 'border border-anchor-up/30' :
                      isWeakest ? 'border border-anchor-down/30' :
                      'border border-transparent'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-mono text-anchor-textMuted w-4">
                        {i + 1}
                      </span>
                      <span className="text-xs text-anchor-text">{POOL_NAMES[poolId as PoolType] || poolId}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {isStrongest && (
                        <span className="text-xs text-anchor-up">最强</span>
                      )}
                      {isWeakest && (
                        <span className="text-xs text-anchor-down">最弱</span>
                      )}
                      <span className={`text-sm font-mono ${
                        isPositive === null ? 'text-anchor-textMuted' :
                        isPositive ? 'text-anchor-up' : 'text-anchor-down'
                      }`}>
                        {median !== null && median !== undefined
                          ? `${isPositive ? '+' : ''}${median.toFixed(2)}%`
                          : '--'}
                      </span>
                    </div>
                  </div>
                );
              }) : (
                <div className="text-xs text-anchor-textMuted text-center py-4">
                  暂无排名数据
                </div>
              )}
            </div>
          </div>

          {/* Spread 值 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <div className="text-xs text-anchor-textMuted mb-3">Spread 值（核心池 vs 其他池）</div>
            <div className="space-y-3">
              <ThresholdBar
                label="核心 vs 主题"
                value={coreVsThemeSpread}
                threshold={1.0}
              />
              <ThresholdBar
                label="核心 vs 产业链"
                value={coreVsChainSpread}
                threshold={1.0}
              />
              <ThresholdBar
                label="核心 vs 交易观察"
                value={coreVsTradingSpread}
                threshold={1.0}
              />
            </div>
          </div>

          {/* 最强/最弱池标记 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center">
                <div className="text-xs text-anchor-textMuted mb-1">最强池</div>
                <div className="text-lg font-medium text-anchor-up">
                  {strongestGroup ? POOL_NAMES[strongestGroup as PoolType] || strongestGroup : '--'}
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-anchor-textMuted mb-1">最弱池</div>
                <div className="text-lg font-medium text-anchor-down">
                  {weakestGroup ? POOL_NAMES[weakestGroup as PoolType] || weakestGroup : '--'}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}