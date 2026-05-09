// ============================================================
// Anchor Position 层 - 第5层：锚定位置计算逻辑
// ============================================================

import { getLatestSnapshot } from '@/lib/data-reader';
import { FormulaDisplay, ThresholdBar } from '@/components/common/layers/shared-components';

const FORMULAS = [
  {
    name: 'relative_strength',
    formula: 'anchor_return - pool_median',
    description: '锚定标的相对核心池的强弱',
  },
  {
    name: 'position',
    formula: 'relative_strength > 0.5% → outperform\nrelative_strength < -0.5% → underperform\notherwise → neutral',
    description: '相对强弱位置判定',
  },
];

const THRESHOLDS = [
  { param: 'OUTPERFORM_THRESHOLD', value: '+0.5%', meaning: '跑赢阈值' },
  { param: 'UNDERPERFORM_THRESHOLD', value: '-0.5%', meaning: '跑输阈值' },
  { param: 'NEUTRAL_BAND', value: '±0.5%', meaning: '中性区间' },
];

const RANKING_RULES = [
  { dimension: 'return', field: 'pct_chg', order: 'desc', description: '涨幅排名（值最大=rank 1）' },
  { dimension: 'amount', field: 'amount', order: 'desc', description: '成交额排名' },
  { dimension: 'turnover', field: 'turnover_rate', order: 'desc', description: '换手率排名' },
  { dimension: 'fund_flow', field: 'net_mf_amount', order: 'desc', description: '资金净流入排名' },
  { dimension: 'valuation', field: 'valuation_percentile', order: 'desc', description: '估值分位排名（仅direct_peers）' },
];

export default async function AnchorPositionPage() {
  const snapshot = await getLatestSnapshot();

  const anchorReturn = snapshot?.anchor_position?.anchor_return ?? null;
  const relativeStrengths = {
    direct_peers: snapshot?.anchor_position?.relative_strength_vs_direct_peers ?? null,
    industry_chain: snapshot?.anchor_position?.relative_strength_vs_industry_chain ?? null,
    theme_pool: snapshot?.anchor_position?.relative_strength_vs_theme_pool ?? null,
  };
  const ranks = {
    return: snapshot?.anchor_position?.return_rank ?? null,
    amount: snapshot?.anchor_position?.amount_rank ?? null,
    turnover: snapshot?.anchor_position?.turnover_rank ?? null,
    moneyflow: snapshot?.anchor_position?.moneyflow_rank ?? null,
  };
  const totalCount = snapshot?.anchor_position?.total_count ?? null;
  const valuationPercentile = snapshot?.anchor_position?.valuation_percentile ?? null;

  // 计算 position 判定
  const position = relativeStrengths.direct_peers !== null
    ? relativeStrengths.direct_peers > 0.5
      ? 'outperform'
      : relativeStrengths.direct_peers < -0.5
        ? 'underperform'
        : 'neutral'
    : null;

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-lg font-medium text-anchor-text">锚定位置计算逻辑</h1>
        <p className="text-sm text-anchor-textMuted mt-1">
          L5 - 计算锚定标的相对强弱和五维排名
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* 左侧：计算逻辑 */}
        <div className="space-y-6">
          {/* 相对强弱公式 */}
          <FormulaDisplay title="相对强弱公式" formulas={FORMULAS} />

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

          {/* 5维排名规则 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
              5维排名规则
            </h2>
            <div className="space-y-2">
              {RANKING_RULES.map((rule, i) => (
                <div key={i} className="flex items-center justify-between bg-anchor-bg rounded-sm px-3 py-2">
                  <span className="text-xs font-mono text-anchor-accent">{rule.dimension}</span>
                  <span className="text-xs text-anchor-textMuted">{rule.description}</span>
                </div>
              ))}
            </div>
            <div className="mt-3 text-xs text-anchor-textMuted">
              <p>排名规则：</p>
              <ul className="list-disc list-inside mt-1 space-y-0.5">
                <li>所有排名降序排列（值最大 = rank 1）</li>
                <li>ranking_scope: enabled=True AND include_in_ranking=True</li>
                <li>锚定标的本身包含在 ranking_scope 中</li>
                <li>同值取首次出现排名</li>
                <li>缺值 → rank = 0</li>
              </ul>
            </div>
          </div>
        </div>

        {/* 右侧：实时数据 */}
        <div className="space-y-6">
          <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
            实时数据
          </h2>

          {/* 锚定标的涨跌幅 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <div className="text-xs text-anchor-textMuted mb-1">锚定标的涨跌幅</div>
            <div className={`text-2xl font-mono ${
              anchorReturn !== null
                ? anchorReturn >= 0 ? 'text-anchor-positive' : 'text-anchor-negative'
                : 'text-anchor-textMuted'
            }`}>
              {anchorReturn !== null
                ? `${anchorReturn >= 0 ? '+' : ''}${anchorReturn.toFixed(2)}%`
                : '--'}
            </div>
          </div>

          {/* 相对强弱 vs 各池 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <div className="text-xs text-anchor-textMuted mb-3">相对强弱（vs 各池中位数）</div>
            <div className="space-y-3">
              <ThresholdBar
                label="vs 核心池"
                value={relativeStrengths.direct_peers}
                threshold={0.5}
              />
              <ThresholdBar
                label="vs 产业池"
                value={relativeStrengths.industry_chain}
                threshold={0.5}
              />
              <ThresholdBar
                label="vs 主题池"
                value={relativeStrengths.theme_pool}
                threshold={0.5}
              />
            </div>

            {/* Position 判定 */}
            <div className="mt-4 pt-3 border-t border-anchor-border">
              <div className="flex items-center justify-between">
                <span className="text-xs text-anchor-textMuted">Position 判定</span>
                {position && (
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    position === 'outperform'
                      ? 'bg-anchor-positive/10 text-anchor-positive'
                      : position === 'underperform'
                      ? 'bg-anchor-negative/10 text-anchor-negative'
                      : 'bg-anchor-textMuted/10 text-anchor-textMuted'
                  }`}>
                    {position === 'outperform' ? '跑赢' : position === 'underperform' ? '跑输' : '中性'}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* 5维排名 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <div className="text-xs text-anchor-textMuted mb-3">
              5维排名 {totalCount !== null && <span className="ml-2">（共 {totalCount} 个成员）</span>}
            </div>
            <div className="space-y-2">
              {RANKING_RULES.map((rule, i) => {
                const rankValue = rule.dimension === 'return'
                  ? ranks.return
                  : rule.dimension === 'amount'
                  ? ranks.amount
                  : rule.dimension === 'turnover'
                  ? ranks.turnover
                  : rule.dimension === 'fund_flow'
                  ? ranks.moneyflow
                  : null;

                return (
                  <div key={i} className="flex items-center justify-between bg-anchor-bg rounded-sm px-3 py-2">
                    <span className="text-xs font-mono text-anchor-accent">{rule.dimension}</span>
                    <div className="flex items-center gap-2">
                      {rankValue !== null && rankValue > 0 ? (
                        <>
                          <span className="text-sm font-mono text-anchor-text">
                            {rankValue}
                          </span>
                          <span className="text-xs text-anchor-textMuted">/</span>
                          <span className="text-xs font-mono text-anchor-textMuted">
                            {totalCount}
                          </span>
                          {totalCount && (
                            <span className={`text-xs ml-2 ${
                              rankValue / totalCount <= 0.3 ? 'text-anchor-positive' :
                              rankValue / totalCount >= 0.7 ? 'text-anchor-negative' :
                              'text-anchor-textMuted'
                            }`}>
                              {rankValue / totalCount <= 0.3 ? '前排' :
                               rankValue / totalCount >= 0.7 ? '后排' : '中等'}
                            </span>
                          )}
                        </>
                      ) : (
                        <span className="text-xs text-anchor-textMuted">--</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 估值分位 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <div className="text-xs text-anchor-textMuted mb-1">估值分位（仅核心池）</div>
            <div className="flex items-center gap-3">
              <div className={`text-2xl font-mono ${
                valuationPercentile !== null
                  ? valuationPercentile <= 30 ? 'text-anchor-positive' :
                    valuationPercentile >= 70 ? 'text-anchor-negative' :
                    'text-anchor-text'
                  : 'text-anchor-textMuted'
              }`}>
                {valuationPercentile !== null
                  ? `${valuationPercentile.toFixed(0)}%`
                  : '--'}
              </div>
              <div className="text-xs text-anchor-textMuted">
                {valuationPercentile !== null && (
                  valuationPercentile <= 30 ? '估值偏低' :
                  valuationPercentile >= 70 ? '估值偏高' :
                  '估值适中'
                )}
              </div>
            </div>
            <div className="mt-2 text-xs text-anchor-textMuted">
              估值分位越低越便宜，越高越贵（基于 PE_TTM 或 PB）
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}