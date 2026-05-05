'use client';

import { Signal } from '@/types';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn, getSignalCategoryColorClass, getConfidenceColorClass } from '@/lib/utils';

interface SignalPanelProps {
  signals: Signal[];
}

const categoryNames: Record<string, string> = {
  beta: '行业Beta',
  alpha: '个股Alpha',
  volume: '资金成交',
  rotation: '组间轮动',
  abnormal: '异常联动',
};

/**
 * 信号面板 - 展示全部信号
 */
export function SignalPanel({ signals }: SignalPanelProps) {
  // 按类别分组
  const signalsByCategory = {
    beta: signals.filter(s => s.category === 'beta'),
    alpha: signals.filter(s => s.category === 'alpha'),
    volume: signals.filter(s => s.category === 'volume'),
    rotation: signals.filter(s => s.category === 'rotation'),
    abnormal: signals.filter(s => s.category === 'abnormal'),
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>信号标签</CardTitle>
        <CardDescription>
          共 {signals.length} 个信号（高置信度 {signals.filter(s => s.confidence === 'high').length} 个）
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {Object.entries(signalsByCategory).map(([category, categorySignals]) => (
            categorySignals.length > 0 && (
              <div key={category}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={cn('text-xs font-medium', getSignalCategoryColorClass(category as any))}>
                    {categoryNames[category]}
                  </span>
                  <Badge variant="neutral" className="text-xs">{categorySignals.length}</Badge>
                </div>
                <div className="flex flex-wrap gap-1">
                  {categorySignals.map((signal, index) => (
                    <Tooltip key={index}>
                      <TooltipTrigger asChild>
                        <Badge
                          variant="outline"
                          className={cn(
                            'cursor-pointer text-xs',
                            signal.confidence === 'high' && 'border-anchor-positive/30 bg-anchor-positive/10',
                            signal.confidence === 'medium' && 'border-anchor-accent/30 bg-anchor-accent/10',
                            signal.confidence === 'low' && 'border-anchor-border bg-anchor-bgSecondary',
                          )}
                        >
                          <span className={cn('mr-1', getConfidenceColorClass(signal.confidence))}>●</span>
                          {signal.label}
                        </Badge>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        <div className="space-y-1 text-xs">
                          <div className="font-medium">{signal.label}</div>
                          <Separator className="my-1" />
                          <div className="text-anchor-textSecondary space-y-0.5">
                            <div>数值: {signal.evidence.value.toFixed(2)}%</div>
                            <div>阈值: {signal.evidence.threshold.toFixed(2)}%</div>
                            {signal.evidence.source_pool && <div>来源池: {signal.evidence.source_pool}</div>}
                            {signal.evidence.source_field && <div>字段: {signal.evidence.source_field}</div>}
                          </div>
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  ))}
                </div>
                <Separator className="my-2" />
              </div>
            )
          ))}
        </div>
      </CardContent>
    </Card>
  );
}