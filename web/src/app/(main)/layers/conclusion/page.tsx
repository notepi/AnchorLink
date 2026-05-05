// ============================================================
// Conclusion 层 - 第8层：结论生成决策逻辑
// ============================================================

import { getLatestSnapshot } from '@/lib/data-reader';
import { DecisionTree } from '@/components/common/layers/shared-components';

export default async function ConclusionPage() {
  const snapshot = await getLatestSnapshot();

  const conclusion = snapshot?.conclusion;
  const signals = snapshot?.signals || [];
  const dataStatus = snapshot?.data_quality?.status || 'unknown';

  // 构建触发的信号列表
  const triggeredSignals = signals.map(s => s.label);

  // Decision Tree 结构
  const industryBetaTree = {
    label: 'industry_beta 判定',
    children: [
      { label: '存在"行业Beta为正"信号', condition: '"行业Beta为正" in signals' },
      { label: '"negative"', result: 'positive' },
      { condition: '"行业Beta为负" in signals', label: '"negative"', result: 'negative' },
      { label: '"neutral"', result: 'neutral' },
    ],
  };

  const anchorAlphaTree = {
    label: 'anchor_alpha 判定',
    children: [
      { condition: '"个股Alpha为正" OR "跑赢核心同类" in signals', label: '"positive"', result: 'positive' },
      { condition: '"个股Alpha为负" OR "跑输核心同类" in signals', label: '"negative"', result: 'negative' },
      { label: '"neutral"', result: 'neutral' },
    ],
  };

  const riskLevelTree = {
    label: 'risk_level 决策树（优先级顺序）',
    children: [
      { condition: 'data_status == "insufficient_data"', label: '"high"', result: 'high' },
      { condition: '存在 abnormal 信号', label: '"high"', result: 'high' },
      { condition: 'data_status == "partial"', label: '"medium"', result: 'medium' },
      { condition: '任何池 strong_count ≥ 3 或 weak_count ≥ 3', label: '"medium"', result: 'medium' },
      { label: '"low"', result: 'low' },
    ],
  };

  // Summary 生成模板
  const SUMMARY_TEMPLATE = [
    { part: 1, template: '行业环境{Beta}，核心同类池中位数涨跌幅{X.XX}%' },
    { part: 2, template: '锚定标的{Alpha}，涨跌幅{X.XX}%，相对核心池{X.XX}%' },
    { part: 3, template: '{pool}池最强（中位数{X.XX}%），{pool}池最弱（{X.XX}%）' },
    { part: 4, template: '整体风险等级：{Risk}' },
  ];

  // next_watch 规则
  const NEXT_WATCH_RULES = [
    { trigger: '跑赢核心同类 / 个股Alpha为正', watch: '是否连续跑赢核心同类' },
    { trigger: '放量上涨/下跌 / 主力资金领先', watch: '成交额是否维持放大' },
    { trigger: '主题扩散强于核心同类 / 交易观察池升温', watch: '主题池热度是否传导到核心同类' },
    { trigger: '行业分化', watch: '分化是否继续扩大' },
    { trigger: '任何 abnormal 信号', watch: '异常联动是否持续' },
  ];

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-lg font-medium text-anchor-text">结论生成决策逻辑</h1>
        <p className="text-sm text-anchor-textMuted mt-1">
          L8 - 根据信号组合生成最终判定（Beta/Alpha/Risk/Summary）
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* 左侧：决策树 */}
        <div className="space-y-6">
          {/* industry_beta 判定 */}
          <DecisionTree
            title="industry_beta 判定"
            root={{
              label: 'industry_beta',
              children: [
                {
                  condition: '存在"行业Beta为正"信号',
                  label: '"positive"',
                  isHighlighted: conclusion?.industry_beta === 'positive',
                },
                {
                  condition: '存在"行业Beta为负"信号',
                  label: '"negative"',
                  isHighlighted: conclusion?.industry_beta === 'negative',
                },
                {
                  label: '"neutral"',
                  isHighlighted: conclusion?.industry_beta === 'neutral',
                },
              ],
            }}
          />

          {/* anchor_alpha 判定 */}
          <DecisionTree
            title="anchor_alpha 判定"
            root={{
              label: 'anchor_alpha',
              children: [
                {
                  condition: '"个股Alpha为正" OR "跑赢核心同类"',
                  label: '"positive"',
                  isHighlighted: conclusion?.anchor_alpha === 'positive',
                },
                {
                  condition: '"个股Alpha为负" OR "跑输核心同类"',
                  label: '"negative"',
                  isHighlighted: conclusion?.anchor_alpha === 'negative',
                },
                {
                  label: '"neutral"',
                  isHighlighted: conclusion?.anchor_alpha === 'neutral',
                },
              ],
            }}
          />

          {/* risk_level 决策树 */}
          <DecisionTree
            title="risk_level 决策树（优先级顺序）"
            root={{
              label: 'risk_level',
              children: [
                {
                  condition: 'data_status == "insufficient_data"',
                  label: '"high"',
                  isHighlighted: conclusion?.risk_level === 'high',
                },
                {
                  condition: '存在 abnormal 信号',
                  label: '"high"',
                  isHighlighted: conclusion?.risk_level === 'high',
                },
                {
                  condition: 'data_status == "partial"',
                  label: '"medium"',
                  isHighlighted: conclusion?.risk_level === 'medium',
                },
                {
                  condition: '任何池 strong_count ≥ 3 或 weak_count ≥ 3',
                  label: '"medium"',
                  isHighlighted: conclusion?.risk_level === 'medium',
                },
                {
                  label: '"low"',
                  isHighlighted: conclusion?.risk_level === 'low',
                },
              ],
            }}
          />
        </div>

        {/* 右侧：当前结论 + 决策路径 */}
        <div className="space-y-6">
          {/* 当前结论 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
              当前结论
            </h2>
            <div className="space-y-3">
              {/* Beta */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-anchor-textMuted">industry_beta</span>
                <span className={`text-sm font-mono px-2 py-0.5 rounded ${
                  conclusion?.industry_beta === 'positive' ? 'bg-anchor-up/10 text-anchor-up' :
                  conclusion?.industry_beta === 'negative' ? 'bg-anchor-down/10 text-anchor-down' :
                  'bg-anchor-textMuted/10 text-anchor-textMuted'
                }`}>
                  {conclusion?.industry_beta || '--'}
                </span>
              </div>
              {/* Alpha */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-anchor-textMuted">anchor_alpha</span>
                <span className={`text-sm font-mono px-2 py-0.5 rounded ${
                  conclusion?.anchor_alpha === 'positive' ? 'bg-anchor-up/10 text-anchor-up' :
                  conclusion?.anchor_alpha === 'negative' ? 'bg-anchor-down/10 text-anchor-down' :
                  'bg-anchor-textMuted/10 text-anchor-textMuted'
                }`}>
                  {conclusion?.anchor_alpha || '--'}
                </span>
              </div>
              {/* Risk */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-anchor-textMuted">risk_level</span>
                <span className={`text-sm font-mono px-2 py-0.5 rounded ${
                  conclusion?.risk_level === 'low' ? 'bg-anchor-up/10 text-anchor-up' :
                  conclusion?.risk_level === 'high' ? 'bg-anchor-down/10 text-anchor-down' :
                  'bg-yellow-500/10 text-yellow-500'
                }`}>
                  {conclusion?.risk_level || '--'}
                </span>
              </div>
            </div>
          </div>

          {/* 触发的信号 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
              触发的信号映射
            </h2>
            <div className="space-y-1">
              {signals.length > 0 ? signals.map((signal, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="text-anchor-text">{signal.label}</span>
                  <span className={`px-1.5 py-0.5 rounded ${
                    signal.confidence === 'high' ? 'bg-anchor-up/10 text-anchor-up' :
                    signal.confidence === 'medium' ? 'bg-yellow-500/10 text-yellow-500' :
                    'bg-anchor-textMuted/10 text-anchor-textMuted'
                  }`}>
                    {signal.confidence}
                  </span>
                </div>
              )) : (
                <div className="text-xs text-anchor-textMuted">暂无触发信号</div>
              )}
            </div>
          </div>

          {/* Summary */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
              Summary 模板
            </h2>
            <div className="space-y-2">
              {SUMMARY_TEMPLATE.map(part => (
                <div key={part.part} className="text-xs">
                  <span className="text-anchor-textMuted">{part.part}.</span>
                  <code className="text-anchor-text ml-2">{part.template}</code>
                </div>
              ))}
            </div>
            {conclusion?.summary && (
              <div className="mt-3 pt-3 border-t border-anchor-border">
                <div className="text-xs text-anchor-textMuted mb-1">实际输出：</div>
                <p className="text-sm text-anchor-text">{conclusion.summary}</p>
              </div>
            )}
          </div>

          {/* next_watch */}
          <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
            <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
              next_watch 规则（最多5条）
            </h2>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-anchor-textMuted border-b border-anchor-border">
                  <th className="text-left py-1 font-medium">触发信号</th>
                  <th className="text-left py-1 font-medium">观察点</th>
                </tr>
              </thead>
              <tbody>
                {NEXT_WATCH_RULES.map((rule, i) => (
                  <tr key={i} className="border-b border-anchor-border/50">
                    <td className="py-1.5 text-anchor-textMuted">{rule.trigger}</td>
                    <td className="py-1.5 text-anchor-text">{rule.watch}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {conclusion?.next_watch && conclusion.next_watch.length > 0 && (
              <div className="mt-3 pt-3 border-t border-anchor-border">
                <div className="text-xs text-anchor-textMuted mb-1">实际观察点：</div>
                <ul className="space-y-1">
                  {conclusion.next_watch.map((watch, i) => (
                    <li key={i} className="text-xs text-anchor-text">• {watch}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}