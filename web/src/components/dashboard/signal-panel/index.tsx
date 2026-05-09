'use client';

import { useMemo } from 'react';
import { Signal, GroupRotation, SignalCategory } from '@/types';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import {
  cn,
  getSignalCategoryColorClass,
  getSignalColorClass,
  getPoolDisplayName,
  formatConfidenceQuantified,
  getConfidenceQuantifiedColorClass,
  formatPct,
} from '@/lib/utils';
import {
  interpretSignals,
  getRiskLevelColorClass,
  getRiskLevelLabel,
} from '@/lib/signal-interpretation';

interface SignalPanelProps {
  signals: Signal[];
  groupRotation?: GroupRotation | null;
}

// 类型化的映射对象
const categoryNames: Record<SignalCategory, string> = {
  beta: '行业环境',
  alpha: '个股Alpha',
  volume: '资金成交',
  rotation: '板块轮动',
  abnormal: '异常联动',
};

const categoryJudge: Record<SignalCategory, string> = {
  beta: '判断行业整体走势',
  alpha: '判断个股相对强弱',
  volume: '判断资金活跃度',
  rotation: '判断板块间流动',
  abnormal: '识别异常联动',
};

const signalMeanings: Record<string, string> = {
  '行业Beta为正': '行业上涨，顺势概率高',
  '行业扩散增强': '上涨扩散，趋势确认',
  '个股Alpha为正': '跑赢行业，有独立Alpha',
  '跑赢核心池': '相对核心池强势',
  '处于行业前排': '涨幅排名前30%',
  '资金价格共振': '资金股价方向一致',
  '主力资金领先': '主力资金看好',
  '交易池升温': '资金转向交易池',
};

const abnormalRiskMeanings: Record<string, string> = {
  '行业强但个股弱': '行业上涨但个股跑输，异常背离',
  '主题强但产业弱': '资金转向情绪炒作，主线松动',
  '产业强但主题弱': '产业扎实但主题未起',
  '行业弱但个股强': '行业下跌但个股上涨，警惕补跌',
  '资金价格背离': '资金流出但股价涨，警惕风险',
};

const fieldNames: Record<string, string> = {
  median_return: '中位数涨幅',
  up_ratio: '上涨比例',
  relative_strength: '相对强度',
  position: '相对位置',
  rank_return: '涨幅排名',
  fund_positive_ratio: '资金正向比例',
  volume_multiplier: '成交倍数',
};

// 提取到组件外部，避免每次渲染重建
function formatValue(value: number, threshold: number, sourceField?: string): string {
  const sign = value >= 0 ? '+' : '';

  // 比例类字段显示为百分比
  if (sourceField === 'up_ratio' || sourceField === 'fund_positive_ratio') {
    return `${(value * 100).toFixed(0)}% (阈值 ${(threshold * 100).toFixed(0)}%)`;
  }

  // 排名类字段显示分位
  if (sourceField === 'rank_return') {
    return `${(value * 100).toFixed(0)}%分位`;
  }

  // 默认百分比
  return `${sign}${value.toFixed(2)}% (阈值 ${threshold.toFixed(1)}%)`;
}

export function SignalPanel({ signals, groupRotation }: SignalPanelProps) {
  const signalsByCategory = {
    beta: signals.filter(s => s.category === 'beta'),
    alpha: signals.filter(s => s.category === 'alpha'),
    volume: signals.filter(s => s.category === 'volume'),
    rotation: signals.filter(s => s.category === 'rotation'),
    abnormal: signals.filter(s => s.category === 'abnormal'),
  };

  // 缓存组合解读计算
  const interpretation = useMemo(
    () => interpretSignals(signals, groupRotation),
    [signals, groupRotation]
  );

  // 缓存池子对比摘要
  const poolSummary = useMemo(() => {
    if (!groupRotation) return null;
    return {
      strongest: {
        name: getPoolDisplayName(groupRotation.strongest_group),
        value: groupRotation.group_medians[groupRotation.strongest_group] ?? 0,
      },
      weakest: {
        name: getPoolDisplayName(groupRotation.weakest_group),
        value: groupRotation.group_medians[groupRotation.weakest_group] ?? 0,
      },
    };
  }, [groupRotation]);

  // 渲染单个信号
  const renderSignal = (signal: Signal) => {
    const { evidence, label, confidence } = signal;
    const poolName = evidence.source_pool ? getPoolDisplayName(evidence.source_pool) : '';
    const fieldName = evidence.source_field ? (fieldNames[evidence.source_field] || evidence.source_field) : '';

    // 置信度量化展示
    const confidenceDisplay = formatConfidenceQuantified(
      evidence.value,
      evidence.threshold,
      confidence,
      evidence.percentile
    );
    const confidenceColor = getConfidenceQuantifiedColorClass(
      evidence.value,
      evidence.threshold,
      evidence.percentile
    );

    // 辅助数值（anchor_return）
    const anchorReturn = evidence.anchor_return;
    const hasAnchorReturn = anchorReturn !== undefined && anchorReturn !== null;
    const anchorReturnDisplay = hasAnchorReturn
      ? `锚定涨${anchorReturn >= 0 ? '+' : ''}${anchorReturn.toFixed(2)}%`
      : '';

    return (
      <div key={label} className="flex flex-col gap-0.5 py-1.5 border-b border-anchor-border last:border-b-0">
        {/* 第一行：标签 + 含义 */}
        <div className="flex items-center gap-1.5 text-xs">
          <span className={cn('shrink-0', getSignalColorClass(label))}>●</span>
          <span className="text-anchor-text font-medium shrink-0">{label}</span>
          <span className="text-anchor-textMuted truncate">{signalMeanings[label]}</span>
        </div>

        {/* 第二行：置信度量化 + 数值 */}
        <div className="flex items-center gap-2 text-xs pl-4">
          <span className={cn('font-mono shrink-0', confidenceColor)}>
            {confidenceDisplay}
          </span>
          <span className="font-mono text-anchor-textTertiary shrink-0">
            {formatValue(evidence.value, evidence.threshold, evidence.source_field)}
          </span>
          {anchorReturnDisplay && (
            <span className="font-mono text-anchor-accent shrink-0">
              {anchorReturnDisplay}
            </span>
          )}
        </div>

        {/* 第三行：数据来源 */}
        {poolName && (
          <div className="text-xs text-anchor-textMuted pl-4">
            来源: {poolName}{fieldName && ` (${fieldName})`}
          </div>
        )}
      </div>
    );
  };

  // 渲染单个类别信号块
  const renderCategoryBlock = (category: SignalCategory, categorySignals: Signal[]) => {
    if (categorySignals.length === 0) return null;

    const isAbnormal = category === 'abnormal';

    return (
      <div className={cn(
        'bg-anchor-bgSecondary rounded-sm p-1.5 border',
        isAbnormal ? 'border-signal-abnormal bg-opacity-50' : 'border-anchor-border'
      )}>
        {/* 类别标题 */}
        <div className="flex items-center gap-1 mb-1">
          <span className={cn('text-xs font-medium', getSignalCategoryColorClass(category))}>
            {isAbnormal && '⚠ '}{categoryNames[category]}
          </span>
          <Badge variant={isAbnormal ? 'negative' : 'neutral'} className="text-xs px-1">
            {categorySignals.length}
          </Badge>
        </div>

        {/* 判断说明 */}
        <div className="text-xs text-anchor-textMuted mb-1.5">
          {categoryJudge[category]}
        </div>

        {/* 信号列表 */}
        <div className="space-y-0">
          {categorySignals.map(signal => renderSignal(signal))}
        </div>

        {/* 异常信号风险提示 */}
        {isAbnormal && categorySignals.length > 0 && (
          <div className="mt-1.5 pt-1.5 border-t border-anchor-border">
            <div className="text-xs text-anchor-negative font-medium">
              风险提示: {categorySignals.map(s => abnormalRiskMeanings[s.label] || s.label).join('；')}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <Card>
      <CardHeader className="py-1 px-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">信号面板</span>
          <span className="text-xs text-anchor-textSecondary">
            {signals.length}个信号
          </span>
        </div>
      </CardHeader>
      <CardContent className="py-1.5 px-3">
        {/* 顶部摘要区：组合解读 + 风险等级 */}
        <div className="bg-anchor-bgSecondary rounded-sm p-2 mb-2 border border-anchor-border">
          <div className="flex flex-col gap-1.5">
            {/* 组合解读摘要 */}
            <div className="flex items-center gap-2 text-xs">
              <span className="font-medium text-anchor-text">组合解读:</span>
              <span className="text-anchor-textSecondary">{interpretation.summary}</span>
            </div>

            {/* 风险等级 */}
            <div className="flex items-center gap-2 text-xs">
              <span className="font-medium text-anchor-text">风险等级:</span>
              <span className={cn('font-medium', getRiskLevelColorClass(interpretation.riskLevel))}>
                {getRiskLevelLabel(interpretation.riskLevel)}
              </span>
              {interpretation.riskReason && (
                <span className="text-anchor-textMuted">({interpretation.riskReason})</span>
              )}
            </div>

            {/* 池子对比摘要 */}
            {poolSummary && (
              <div className="flex items-center gap-2 text-xs">
                <span className="font-medium text-anchor-text">池子对比:</span>
                <span className="text-anchor-positive">
                  {poolSummary.strongest.name}最强({formatPct(poolSummary.strongest.value)})
                </span>
                <span className="text-anchor-textMuted">vs</span>
                <span className="text-anchor-textSecondary">
                  {poolSummary.weakest.name}最弱({formatPct(poolSummary.weakest.value)})
                </span>
              </div>
            )}
          </div>
        </div>

        {/* 异常联动优先展示（如有） */}
        {signalsByCategory.abnormal.length > 0 && (
          <div className="mb-1.5">
            {renderCategoryBlock('abnormal', signalsByCategory.abnormal)}
          </div>
        )}

        {/* 第一行：行业环境 + 个股Alpha */}
        <div className="grid grid-cols-2 gap-1.5 mb-1.5">
          {renderCategoryBlock('beta', signalsByCategory.beta)}
          {renderCategoryBlock('alpha', signalsByCategory.alpha)}
        </div>

        {/* 第二行：资金成交 + 板块轮动 */}
        <div className="grid grid-cols-2 gap-1.5">
          {renderCategoryBlock('volume', signalsByCategory.volume)}
          {renderCategoryBlock('rotation', signalsByCategory.rotation)}
        </div>
      </CardContent>
    </Card>
  );
}