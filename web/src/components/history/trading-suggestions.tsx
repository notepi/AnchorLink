import type { TradingRule } from '@/types';

interface TradingSuggestionsProps {
  rules: TradingRule[];
}

function RuleCard({ rule, type }: { rule: TradingRule; type: 'long' | 'caution' }) {
  const isLong = type === 'long';
  const title = isLong ? '历史条件提示：考虑做多' : '历史条件提示：谨慎或反向';
  const titleColor = isLong ? 'text-anchor-positive' : 'text-anchor-negative';
  const borderColor = isLong ? 'border-l-2 border-anchor-positive' : 'border-l-2 border-anchor-negative';

  return (
    <div className={`bg-anchor-bgSecondary rounded-sm border border-anchor-border p-4 ${borderColor}`}>
      <h3 className={`text-xs font-medium ${titleColor} mb-2`}>{title}</h3>
      <ul className="space-y-1 text-xs">
        {rule.conditions.map((c, i) => (
          <li key={i} className="text-anchor-text">
            <span className="text-anchor-textSecondary">{i + 1}. </span>
            {c}
          </li>
        ))}
      </ul>
      <div className="mt-2 pt-2 border-t border-anchor-borderSubtle">
        <p className="text-xs text-anchor-textSecondary">
          历史表现：样本 {rule.stats.count} 次，次日平均
          <span className={`font-mono ${rule.stats.avg >= 0 ? 'text-anchor-positive' : 'text-anchor-negative'}`}>
            {rule.stats.avg >= 0 ? '+' : ''}{rule.stats.avg.toFixed(2)}%
          </span>
          ，胜率
          <span className={`font-mono ${rule.stats.winRate >= 0.5 ? 'text-anchor-positive' : 'text-anchor-negative'}`}>
            {(rule.stats.winRate * 100).toFixed(0)}%
          </span>
        </p>
        <p className="text-xs text-anchor-textMuted mt-1">
          * 日期范围：{rule.dateRange.start} ~ {rule.dateRange.end}，仅供参考，不构成投资建议
        </p>
      </div>
    </div>
  );
}

export function TradingSuggestions({ rules }: TradingSuggestionsProps) {
  if (rules.length === 0) return null;

  const longRules = rules.filter((r) => r.type === 'long');
  const cautionRules = rules.filter((r) => r.type === 'caution');

  return (
    <div>
      <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-3">
        交易建议
      </h2>
      <div className="space-y-3">
        {longRules.map((r, i) => (
          <RuleCard key={`long-${i}`} rule={r} type="long" />
        ))}
        {cautionRules.map((r, i) => (
          <RuleCard key={`caution-${i}`} rule={r} type="caution" />
        ))}
      </div>
    </div>
  );
}
