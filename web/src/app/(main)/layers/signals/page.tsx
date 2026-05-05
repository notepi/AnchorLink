// ============================================================
// Signals 层 - 第7层：信号标签计算逻辑（核心页面）
// ============================================================

import { getLatestSnapshot } from '@/lib/data-reader';
import { HitIndicator } from '@/components/common/layers/shared-components';
import { SignalCategory, ConfidenceLevel } from '@/types';

// 信号规则定义
const SIGNAL_RULES = {
  beta: [
    { label: '行业Beta为正', formula: 'median_return > 0.5%', threshold: '0.5%', source: 'direct_peers' },
    { label: '行业Beta为负', formula: 'median_return < -0.5%', threshold: '-0.5%', source: 'direct_peers' },
    { label: '行业Beta中性', formula: '-0.5% ≤ median_return ≤ 0.5%', threshold: '±0.5%', source: 'direct_peers' },
    { label: '行业扩散增强', formula: 'up_ratio > 0.70', threshold: '0.70', source: 'direct_peers' },
    { label: '行业扩散不足', formula: 'up_ratio < 0.30', threshold: '0.30', source: 'direct_peers' },
    { label: '行业退潮', formula: '(未实现)', threshold: '--', source: '--' },
    { label: '行业分化', formula: 'strong_count ≥ 3 OR weak_count ≥ 3', threshold: '3', source: 'direct_peers' },
  ],
  alpha: [
    { label: '个股Alpha为正', formula: 'relative_strength > 0.5%', threshold: '0.5%' },
    { label: '个股Alpha为负', formula: 'relative_strength < -0.5%', threshold: '-0.5%' },
    { label: '个股Alpha中性', formula: '|relative_strength| ≤ 0.5%', threshold: '±0.5%' },
    { label: '跑赢核心同类', formula: 'position="outperform" AND relative_strength > 0.5%', threshold: '0.5%' },
    { label: '跑输核心同类', formula: 'position="underperform" AND relative_strength < -0.5%', threshold: '-0.5%' },
    { label: '处于行业前排', formula: 'rank_percentile ≤ 30%', threshold: '30%' },
    { label: '处于行业后排', formula: 'rank_percentile ≥ 70%', threshold: '70%' },
    { label: '独立走强', formula: '(未实现)', threshold: '--' },
    { label: '独立走弱', formula: '(未实现)', threshold: '--' },
  ],
  volume: [
    { label: '放量上涨', formula: 'volume_multiplier > 1.5 AND anchor_return > 0', threshold: '1.5' },
    { label: '放量下跌', formula: 'volume_multiplier > 1.5 AND anchor_return < 0', threshold: '1.5' },
    { label: '缩量调整', formula: 'volume_multiplier < 0.7', threshold: '0.7' },
    { label: '放量滞涨', formula: 'volume_multiplier > 1.5 AND 0 < anchor_return < 0.5%', threshold: '1.5, 0.5%' },
    { label: '资金价格共振', formula: 'fund_positive_ratio > 0.60 AND anchor_return > 0', threshold: '0.60' },
    { label: '资金价格背离', formula: 'fund_positive_ratio < 0.40 AND anchor_return > 0', threshold: '0.40' },
    { label: '主力资金领先', formula: 'fund_positive_ratio > 0.60', threshold: '0.60' },
    { label: '主力资金拖累', formula: 'fund_positive_ratio < 0.40', threshold: '0.40' },
  ],
  rotation: [
    { label: '核心同类强于主题扩散', formula: 'core_vs_theme_spread > 1.0%', threshold: '1.0%' },
    { label: '主题扩散强于核心同类', formula: 'core_vs_theme_spread < -1.0%', threshold: '-1.0%' },
    { label: '产业链强于情绪池', formula: 'core_vs_trading_spread > 1.0%', threshold: '1.0%' },
    { label: '情绪池强于产业链', formula: 'core_vs_trading_spread < -1.0%', threshold: '-1.0%' },
    { label: '交易观察池升温', formula: 'trading_pool.median_return > 0.5%', threshold: '0.5%' },
    { label: '交易观察池降温', formula: 'trading_pool.median_return < -0.5%', threshold: '-0.5%' },
  ],
  abnormal: [
    { label: '行业强但个股弱', formula: 'median_return > 0.5% AND relative_strength < -0.5%', threshold: '2.0% spread' },
    { label: '行业弱但个股强', formula: 'median_return < -0.5% AND relative_strength > 0.5%', threshold: '2.0% spread' },
    { label: '核心同类强但锚定标的弱', formula: '(未实现)', threshold: '--' },
    { label: '主题池强但核心池弱', formula: '|core_vs_theme_spread| > 2.0% AND spread < 0', threshold: '2.0%' },
    { label: '核心池强但主题池弱', formula: '|core_vs_theme_spread| > 2.0% AND spread > 0', threshold: '2.0%' },
  ],
};

const CATEGORY_LABELS: Record<SignalCategory, string> = {
  beta: 'Beta 类（行业环境）',
  alpha: 'Alpha 类（个股相对强弱）',
  volume: 'Volume 类（资金成交）',
  rotation: 'Rotation 类（组间轮动）',
  abnormal: 'Abnormal 类（联动背离）',
};

const CATEGORY_COLORS: Record<SignalCategory, string> = {
  beta: 'text-blue-400',
  alpha: 'text-green-400',
  volume: 'text-yellow-400',
  rotation: 'text-purple-400',
  abnormal: 'text-red-400',
};

interface SignalRuleItem {
  label: string;
  formula: string;
  threshold: string;
  source?: string;
  hit?: boolean;
  value?: number | null;
}

export default async function SignalsPage() {
  const snapshot = await getLatestSnapshot();

  const signals = snapshot?.signals || [];
  const groupMedians = snapshot?.group_rotation?.group_medians || {};
  const anchorPosition = snapshot?.anchor_position;
  const groupRotation = snapshot?.group_rotation;
  const industryState = snapshot?.industry_state;

  // 构建当前信号命中映射
  const signalHitMap = signals.reduce((acc, s) => {
    acc[s.label] = s;
    return acc;
  }, {} as Record<string, typeof signals[0]>);

  // 辅助函数：判断信号是否命中
  const checkHit = (label: string): boolean => signalHitMap[label] !== undefined;

  // 渲染规则表
  const renderRuleTable = (category: SignalCategory, rules: SignalRuleItem[]) => {
    const activeSignals = signals.filter(s => s.category === category);

    return (
      <div className="space-y-2">
        {rules.map((rule, i) => {
          const signal = signalHitMap[rule.label];
          const hit = checkHit(rule.label);

          return (
            <div
              key={i}
              className={`flex items-center justify-between px-3 py-2 rounded-sm border ${
                hit
                  ? 'bg-anchor-up/5 border-anchor-up/20'
                  : 'bg-anchor-bg border-anchor-border'
              }`}
            >
              <div className="flex items-center gap-3">
                <span className={`text-xs ${hit ? 'text-anchor-up' : 'text-anchor-textMuted'}`}>
                  {hit ? '✓' : '✗'}
                </span>
                <span className="text-xs text-anchor-text">{rule.label}</span>
              </div>
              <div className="flex items-center gap-4 text-xs">
                <code className="text-anchor-textMuted font-mono">{rule.formula}</code>
                <span className="text-anchor-textSecondary">{rule.threshold}</span>
                {signal && (
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-anchor-text">
                      = {signal.evidence.value?.toFixed(2)}
                    </span>
                    <span className={`px-1.5 py-0.5 rounded text-xs ${
                      signal.confidence === 'high' ? 'bg-anchor-up/20 text-anchor-up' :
                      signal.confidence === 'medium' ? 'bg-yellow-500/20 text-yellow-500' :
                      'bg-anchor-textMuted/20 text-anchor-textMuted'
                    }`}>
                      {signal.confidence}
                    </span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-lg font-medium text-anchor-text">信号标签计算逻辑</h1>
        <p className="text-sm text-anchor-textMuted mt-1">
          L7 - 35+ 信号标签规则、置信度算法、数据质量门控
        </p>
      </div>

      {/* 当前命中信号统计 */}
      <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-xs text-anchor-textMuted">当前命中信号: </span>
            <span className="text-lg font-mono text-anchor-accent">{signals.length}</span>
            <span className="text-xs text-anchor-textMuted ml-1">/ 35+</span>
          </div>
          <div className="flex items-center gap-4 text-xs">
            {(Object.keys(CATEGORY_LABELS) as SignalCategory[]).map(cat => {
              const count = signals.filter(s => s.category === cat).length;
              return (
                <span key={cat} className={CATEGORY_COLORS[cat]}>
                  {CATEGORY_LABELS[cat].split('（')[0]}: {count}
                </span>
              );
            })}
          </div>
        </div>
      </div>

      {/* 置信度算法 */}
      <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
        <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
          置信度算法
        </h2>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-anchor-bg rounded-sm p-3">
            <div className="text-xs font-mono text-anchor-accent mb-2">边际置信度</div>
            <code className="text-xs text-anchor-text font-mono block">
              margin_ratio = margin / abs(threshold)
            </code>
            <div className="mt-2 space-y-1 text-xs">
              <div><span className="text-anchor-textMuted">margin_ratio ≥ 2.0</span> → <span className="text-anchor-up">high</span></div>
              <div><span className="text-anchor-textMuted">margin_ratio ≥ 1.0</span> → <span className="text-yellow-500">medium</span></div>
              <div><span className="text-anchor-textMuted">otherwise</span> → <span className="text-anchor-textMuted">low</span></div>
            </div>
          </div>
          <div className="bg-anchor-bg rounded-sm p-3">
            <div className="text-xs font-mono text-anchor-accent mb-2">排名置信度</div>
            <code className="text-xs text-anchor-text font-mono block">
              percentile = rank / total_count
            </code>
            <div className="mt-2 space-y-1 text-xs">
              <div><span className="text-anchor-textMuted">percentile ≤ threshold/2</span> → <span className="text-anchor-up">high</span></div>
              <div><span className="text-anchor-textMuted">percentile ≤ threshold</span> → <span className="text-yellow-500">medium</span></div>
              <div><span className="text-anchor-textMuted">otherwise</span> → <span className="text-anchor-textMuted">low</span></div>
            </div>
          </div>
        </div>
      </div>

      {/* 数据质量门控 */}
      <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
        <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
          数据质量门控
        </h2>
        <div className="bg-anchor-bg rounded-sm p-3 font-mono text-xs space-y-1">
          <div className="text-anchor-text">
            <span className="text-anchor-textMuted">if</span> data_status == "insufficient_data"
            <span className="text-anchor-textMuted"> → </span>
            <span className="text-anchor-down">返回空结果（不产生信号）</span>
          </div>
          <div className="text-anchor-text">
            <span className="text-anchor-textMuted">if</span> missing_data ≥ 3
            <span className="text-anchor-textMuted"> → </span>
            <span className="text-anchor-down">insufficient_data</span>
          </div>
          <div className="text-anchor-text">
            <span className="text-anchor-textMuted">if</span> missing_data 1-2
            <span className="text-anchor-textMuted"> → </span>
            <span className="text-yellow-500">partial（信号抑制）</span>
          </div>
        </div>
      </div>

      {/* 35标签规则 - 按类别展示 */}
      <div className="space-y-6">
        {(Object.keys(SIGNAL_RULES) as SignalCategory[]).map(category => (
          <div key={category} className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <h3 className={`text-sm font-medium ${CATEGORY_COLORS[category]} mb-4`}>
              {CATEGORY_LABELS[category]}
            </h3>
            {renderRuleTable(category, SIGNAL_RULES[category])}
          </div>
        ))}
      </div>
    </div>
  );
}