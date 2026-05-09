// ============================================================
// Pool State 层 - 第4层：池子状态计算逻辑
// ============================================================

import { getLatestSnapshot, getConfig } from '@/lib/data-reader';
import { FormulaDisplay, ThresholdBar } from '@/components/common/layers/shared-components';
import { PoolType } from '@/types';

const POOL_NAMES: Record<PoolType, string> = {
  direct_peers: '增材制造本业确认池',
  industry_chain: '商业航天硬科技主池',
  theme_pool: '商业航天主题温度计',
  trading_watchlist: '交易联动与风险映射池',
};

// 核心公式
const FORMULAS = [
  {
    name: 'median_return',
    formula: 'pd.Series(returns).median()',
    description: '池子成员涨跌幅的中位数',
  },
  {
    name: 'up_ratio',
    formula: 'count(pct_chg > 0) / count(valid)',
    description: '上涨成员占比',
  },
  {
    name: 'volume_multiplier',
    formula: 'sum(today_amount) / sum(member_avg_amount_20d)',
    description: '成交额放大倍数',
  },
  {
    name: 'fund_positive_ratio',
    formula: 'count(net_mf_amount > 0) / count(has_fund_data)',
    description: '资金净流入成员占比',
  },
  {
    name: 'strong_count',
    formula: 'count(pct_chg > 3.0%)',
    description: '强势股数量（>3%）',
  },
  {
    name: 'weak_count',
    formula: 'count(pct_chg < -3.0%)',
    description: '弱势股数量（<-3%）',
  },
];

// 阈值表
const THRESHOLDS = [
  { param: 'STRONG_THRESHOLD', value: '3.0%', meaning: 'pct_chg > 3% 为强势' },
  { param: 'WEAK_THRESHOLD', value: '-3.0%', meaning: 'pct_chg < -3% 为弱势' },
  { param: 'VOLUME_LOOKBACK_DAYS', value: '20', meaning: '成交额历史回溯天数' },
  { param: 'COVERAGE_THRESHOLD', value: '0.8', meaning: '覆盖率 < 80% 降级为 partial' },
];

// 数据质量决策树
const QUALITY_DECISION_TREE = [
  { condition: 'valid_count < min_size', result: 'insufficient_data', label: '成员数不足' },
  { condition: 'no price data', result: 'insufficient_data', label: '无价格数据' },
  { condition: 'no fund data', result: 'partial', label: '无资金数据' },
  { condition: 'coverage < 80%', result: 'partial', label: '覆盖率不足' },
  { condition: 'otherwise', result: 'ok', label: '正常' },
];

export default async function PoolStatePage() {
  const snapshot = await getLatestSnapshot();
  const config = await getConfig();

  // 从 snapshot 提取池子状态数据
  const groupMedians = snapshot?.group_rotation?.group_medians || {};
  const industryState = snapshot?.industry_state;

  // 计算各池成员数
  const poolCounts = config?.memberships
    ? config.memberships.reduce((acc, m) => {
        if (m.enabled) {
          acc[m.universe_id] = (acc[m.universe_id] || 0) + 1;
        }
        return acc;
      }, {} as Record<string, number>)
    : {};

  // 池子状态数据
  const poolStates: Record<PoolType, {
    configured_count: number;
    enabled_count: number;
    benchmark_count: number;
    median_return: number | null;
    up_ratio: number | null;
    volume_multiplier: number | null;
    fund_positive_ratio: number | null;
    strong_count: number;
    weak_count: number;
    data_status: 'ok' | 'partial' | 'insufficient_data';
  }> = {
    direct_peers: {
      configured_count: poolCounts['direct_peers'] || 0,
      enabled_count: poolCounts['direct_peers'] || 0,
      benchmark_count: config?.memberships?.filter(m => m.universe_id === 'direct_peers' && m.include_in_benchmark).length || 0,
      median_return: groupMedians['direct_peers'] ?? null,
      up_ratio: industryState?.up_ratio ?? null,
      volume_multiplier: industryState?.amount_expansion_ratio ?? null,
      fund_positive_ratio: industryState?.moneyflow_positive_ratio ?? null,
      strong_count: 0,
      weak_count: 0,
      data_status: 'ok',
    },
    industry_chain: {
      configured_count: poolCounts['industry_chain'] || 0,
      enabled_count: poolCounts['industry_chain'] || 0,
      benchmark_count: config?.memberships?.filter(m => m.universe_id === 'industry_chain' && m.include_in_benchmark).length || 0,
      median_return: groupMedians['industry_chain'] ?? null,
      up_ratio: null,
      volume_multiplier: null,
      fund_positive_ratio: null,
      strong_count: 0,
      weak_count: 0,
      data_status: groupMedians['industry_chain'] !== undefined ? 'ok' : 'insufficient_data',
    },
    theme_pool: {
      configured_count: poolCounts['theme_pool'] || 0,
      enabled_count: poolCounts['theme_pool'] || 0,
      benchmark_count: config?.memberships?.filter(m => m.universe_id === 'theme_pool' && m.include_in_benchmark).length || 0,
      median_return: groupMedians['theme_pool'] ?? null,
      up_ratio: null,
      volume_multiplier: null,
      fund_positive_ratio: null,
      strong_count: 0,
      weak_count: 0,
      data_status: groupMedians['theme_pool'] !== undefined ? 'ok' : 'insufficient_data',
    },
    trading_watchlist: {
      configured_count: poolCounts['trading_watchlist'] || 0,
      enabled_count: poolCounts['trading_watchlist'] || 0,
      benchmark_count: config?.memberships?.filter(m => m.universe_id === 'trading_watchlist' && m.include_in_benchmark).length || 0,
      median_return: groupMedians['trading_watchlist'] ?? null,
      up_ratio: null,
      volume_multiplier: null,
      fund_positive_ratio: null,
      strong_count: 0,
      weak_count: 0,
      data_status: groupMedians['trading_watchlist'] !== undefined ? 'ok' : 'insufficient_data',
    },
  };

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-lg font-medium text-anchor-text">池子状态计算逻辑</h1>
        <p className="text-sm text-anchor-textMuted mt-1">
          L4 - 计算各池子的核心指标：中位数涨跌幅、上涨比例、成交放大倍数、资金流向
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* 左侧：计算逻辑 */}
        <div className="space-y-6">
          {/* 计算流程 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
              池子状态计算流程
            </h2>
            <div className="bg-anchor-bg rounded-sm p-3 font-mono text-xs space-y-1">
              <div className="text-anchor-text">benchmark_scope 筛选:</div>
              <div className="text-anchor-accent pl-4">enabled=True AND include_in_benchmark=True</div>
              <div className="text-anchor-text mt-2">↓</div>
              <div className="text-anchor-text">四个口径计数:</div>
              <div className="text-anchor-accent pl-4">configured_count / enabled_count / benchmark_count / valid_count</div>
              <div className="text-anchor-text mt-2">↓</div>
              <div className="text-anchor-text">计算六个指标:</div>
              <div className="text-anchor-accent pl-4">median_return, up_ratio, volume_multiplier,</div>
              <div className="text-anchor-accent pl-4">fund_positive_ratio, strong_count, weak_count</div>
              <div className="text-anchor-text mt-2">↓</div>
              <div className="text-anchor-text">数据质量判定</div>
            </div>
          </div>

          {/* 核心公式 */}
          <FormulaDisplay title="核心公式（6个）" formulas={FORMULAS} />

          {/* 数据质量决策树 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
              数据质量决策树
            </h2>
            <div className="bg-anchor-bg rounded-sm p-3 font-mono text-xs space-y-1">
              {QUALITY_DECISION_TREE.map((node, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-anchor-textMuted">if</span>
                  <span className="text-anchor-text">{node.condition}</span>
                  <span className="text-anchor-textMuted">→</span>
                  <span className={
                    node.result === 'ok' ? 'text-anchor-positive' :
                    node.result === 'partial' ? 'text-yellow-500' :
                    'text-anchor-negative'
                  }>{node.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 阈值表 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
              阈值参数
            </h2>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-anchor-textMuted border-b border-anchor-border">
                  <th className="text-left py-1 font-medium">参数</th>
                  <th className="text-right py-1 font-medium">值</th>
                  <th className="text-left py-1 font-medium">含义</th>
                </tr>
              </thead>
              <tbody>
                {THRESHOLDS.map((t, i) => (
                  <tr key={i} className="border-b border-anchor-border/50">
                    <td className="py-1 font-mono text-anchor-accent">{t.param}</td>
                    <td className="py-1 text-right font-mono text-anchor-text">{t.value}</td>
                    <td className="py-1 text-anchor-textMuted">{t.meaning}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* 右侧：实时数据 */}
        <div className="space-y-6">
          <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
            实时数据（4池）
          </h2>

          {(Object.keys(POOL_NAMES) as PoolType[]).map(poolId => {
            const state = poolStates[poolId];
            return (
              <div
                key={poolId}
                className={`bg-anchor-bgSecondary rounded-sm p-4 border ${
                  state.data_status === 'insufficient_data'
                    ? 'border-anchor-down/30'
                    : state.data_status === 'partial'
                    ? 'border-yellow-500/30'
                    : 'border-anchor-border'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-medium text-anchor-text">{POOL_NAMES[poolId]}</h3>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    state.data_status === 'ok' ? 'bg-anchor-positive/10 text-anchor-positive' :
                    state.data_status === 'partial' ? 'bg-yellow-500/10 text-yellow-500' :
                    'bg-anchor-negative/10 text-anchor-negative'
                  }`}>
                    {state.data_status === 'ok' ? 'OK' : state.data_status === 'partial' ? 'Partial' : 'Insufficient'}
                  </span>
                </div>

                {state.data_status === 'insufficient_data' ? (
                  <div className="text-xs text-anchor-textMuted py-2">数据不足，无法计算</div>
                ) : (
                  <>
                    {/* 四个口径计数 */}
                    <div className="grid grid-cols-4 gap-2 mb-4">
                      <div className="text-center">
                        <div className="text-lg font-mono text-anchor-text">{state.configured_count}</div>
                        <div className="text-xs text-anchor-textMuted">configured</div>
                      </div>
                      <div className="text-center">
                        <div className="text-lg font-mono text-anchor-text">{state.enabled_count}</div>
                        <div className="text-xs text-anchor-textMuted">enabled</div>
                      </div>
                      <div className="text-center">
                        <div className="text-lg font-mono text-anchor-text">{state.benchmark_count}</div>
                        <div className="text-xs text-anchor-textMuted">benchmark</div>
                      </div>
                      <div className="text-center">
                        <div className="text-lg font-mono text-anchor-text">
                          {state.benchmark_count > 0 ? state.benchmark_count : '--'}
                        </div>
                        <div className="text-xs text-anchor-textMuted">valid</div>
                      </div>
                    </div>

                    {/* 指标阈值条 */}
                    <div className="space-y-2">
                      <ThresholdBar
                        label="中位数涨跌幅"
                        value={state.median_return}
                        threshold={0}
                      />
                      <ThresholdBar
                        label="上涨比例"
                        value={state.up_ratio}
                        threshold={0.7}
                        unit=""
                      />
                      <ThresholdBar
                        label="成交额倍数"
                        value={state.volume_multiplier}
                        threshold={1.5}
                        unit="x"
                      />
                      <ThresholdBar
                        label="资金净流入占比"
                        value={state.fund_positive_ratio}
                        threshold={0.6}
                        unit=""
                      />
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}