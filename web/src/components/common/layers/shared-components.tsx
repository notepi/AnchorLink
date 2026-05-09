// ============================================================
// 公式展示组件 - 代码风格展示计算公式
// ============================================================

interface FormulaDisplayProps {
  title: string;
  formulas: Array<{
    name: string;
    formula: string;
    description?: string;
  }>;
}

export function FormulaDisplay({ title, formulas }: FormulaDisplayProps) {
  return (
    <div className="space-y-3">
      <h3 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
        {title}
      </h3>
      <div className="space-y-2">
        {formulas.map((f, i) => (
          <div key={i} className="bg-anchor-bg rounded-sm p-3 border border-anchor-border">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-mono text-anchor-accent">{f.name}</span>
            </div>
            <code className="text-xs text-anchor-text font-mono block">{f.formula}</code>
            {f.description && (
              <p className="text-xs text-anchor-textMuted mt-1">{f.description}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// 阈值对比条组件
// ============================================================

interface ThresholdBarProps {
  label: string;
  value: number | null;
  threshold: number;
  unit?: string;
  invertColors?: boolean; // 低值好（如排名）vs 高值好（如涨跌幅）
}

export function ThresholdBar({ label, value, threshold, unit = '%', invertColors = false }: ThresholdBarProps) {
  if (value === null) {
    return (
      <div className="flex items-center justify-between py-1">
        <span className="text-xs text-anchor-textSecondary">{label}</span>
        <span className="text-xs text-anchor-textMuted">--</span>
      </div>
    );
  }

  const isPositive = value >= 0;
  const absValue = Math.abs(value);
  const absThreshold = Math.abs(threshold);

  // 计算条的长度（最大值情况下为100%）
  const ratio = Math.min(absValue / (absThreshold * 2), 1);

  const hitThreshold = invertColors
    ? value <= threshold
    : value >= threshold;

  return (
    <div className="py-1">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-anchor-textSecondary">{label}</span>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-mono ${isPositive ? 'text-anchor-positive' : 'text-anchor-negative'}`}>
            {isPositive ? '+' : ''}{value.toFixed(2)}{unit}
          </span>
          <span className={`text-xs ${hitThreshold ? 'text-anchor-positive' : 'text-anchor-textMuted'}`}>
            {hitThreshold ? '✓' : '阈值:' + threshold}
          </span>
        </div>
      </div>
      <div className="h-1.5 bg-anchor-bg rounded-sm overflow-hidden">
        <div
          className={`h-full rounded-sm transition-all ${
            isPositive ? 'bg-anchor-positive' : 'bg-anchor-negative'
          }`}
          style={{ width: `${ratio * 100}%` }}
        />
      </div>
    </div>
  );
}

// ============================================================
// 决策树展示组件
// ============================================================

interface DecisionNode {
  label: string;
  condition?: string;
  result?: string;
  children?: DecisionNode[];
  isHighlighted?: boolean;
}

interface DecisionTreeProps {
  title: string;
  root: DecisionNode;
}

export function DecisionTree({ title, root }: DecisionTreeProps) {
  return (
    <div className="space-y-3">
      <h3 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
        {title}
      </h3>
      <div className="bg-anchor-bg rounded-sm p-3 border border-anchor-border font-mono text-xs">
        <NodeDisplay node={root} depth={0} />
      </div>
    </div>
  );
}

function NodeDisplay({ node, depth }: { node: DecisionNode; depth: number }) {
  const indent = '  '.repeat(depth);
  return (
    <div className={node.isHighlighted ? 'bg-anchor-accent/10 rounded px-1' : ''}>
      {node.condition ? (
        <div className="text-anchor-text">
          {indent}if ({node.condition}) → <span className="text-anchor-accent">{node.label}</span>
        </div>
      ) : (
        <div className="text-anchor-accent">{indent}{node.label}</div>
      )}
      {node.children?.map((child, i) => (
        <NodeDisplay key={i} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}

// ============================================================
// 命中指示器
// ============================================================

interface HitIndicatorProps {
  hit: boolean;
  label?: string;
}

export function HitIndicator({ hit, label }: HitIndicatorProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-mono px-1.5 py-0.5 rounded ${
        hit
          ? 'bg-anchor-positive/10 text-anchor-positive'
          : 'bg-anchor-negative/10 text-anchor-negative'
      }`}
    >
      {hit ? '✓' : '✗'} {label || ''}
    </span>
  );
}

// ============================================================
// 规则表组件
// ============================================================

interface SignalRule {
  label: string;
  formula: string;
  threshold: string;
  source?: string;
  hit?: boolean;
  currentValue?: number | null;
}

interface RuleTableProps {
  title: string;
  rules: SignalRule[];
}

export function RuleTable({ title, rules }: RuleTableProps) {
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
        {title}
      </h3>
      <div className="space-y-1">
        {rules.map((rule, i) => (
          <div
            key={i}
            className={`flex items-center justify-between px-3 py-2 rounded-sm border ${
              rule.hit
                ? 'bg-anchor-positive/5 border-anchor-up/20'
                : 'bg-anchor-bg border-anchor-border'
            }`}
          >
            <div className="flex items-center gap-3">
              {rule.hit !== undefined && (
                <span className={rule.hit ? 'text-anchor-positive' : 'text-anchor-negative'}>
                  {rule.hit ? '✓' : '✗'}
                </span>
              )}
              <span className="text-xs text-anchor-text">{rule.label}</span>
            </div>
            <div className="flex items-center gap-4 text-xs">
              <code className="text-anchor-textMuted font-mono">{rule.formula}</code>
              <span className="text-anchor-textSecondary">{rule.threshold}</span>
              {rule.currentValue !== undefined && rule.currentValue !== null && (
                <span className={`font-mono ${rule.hit ? 'text-anchor-positive' : 'text-anchor-text'}`}>
                  = {rule.currentValue.toFixed(2)}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// 作用域模型展示
// ============================================================

interface ScopeModelProps {
  scopeName: string;
  description: string;
  filter: string;
  count: number;
}

export function ScopeModel({ scopeName, description, filter, count }: ScopeModelProps) {
  return (
    <div className="bg-anchor-bg rounded-sm p-3 border border-anchor-border">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-anchor-accent">{scopeName}</span>
        <span className="text-xs font-mono text-anchor-textSecondary">{count} members</span>
      </div>
      <p className="text-xs text-anchor-textMuted mb-2">{description}</p>
      <code className="text-xs text-anchor-text font-mono block bg-anchor-bgSecondary px-2 py-1 rounded">
        {filter}
      </code>
    </div>
  );
}