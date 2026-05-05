'use client';

import { Conclusion } from '@/types';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';

interface ConclusionPanelProps {
  conclusion: Conclusion;
}

/**
 * 结论面板 - 三核心指标 + 综合判断 + 次日观察
 */
export function ConclusionPanel({ conclusion }: ConclusionPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>综合结论</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {/* 三核心指标 */}
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-anchor-bgSecondary rounded-sm p-2">
              <div className="text-xs text-anchor-textSecondary mb-1">行业Beta</div>
              <Badge
                variant={conclusion.industry_beta === 'positive' ? 'positive' : conclusion.industry_beta === 'negative' ? 'negative' : 'neutral'}
                className="text-sm"
              >
                {conclusion.industry_beta === 'positive' ? '正面 (+)' : conclusion.industry_beta === 'negative' ? '负面 (-)' : '中性 (0)'}
              </Badge>
            </div>
            <div className="bg-anchor-bgSecondary rounded-sm p-2">
              <div className="text-xs text-anchor-textSecondary mb-1">个股Alpha</div>
              <Badge
                variant={conclusion.anchor_alpha === 'positive' ? 'positive' : conclusion.anchor_alpha === 'negative' ? 'negative' : 'neutral'}
                className="text-sm"
              >
                {conclusion.anchor_alpha === 'positive' ? '正面 (+)' : conclusion.anchor_alpha === 'negative' ? '负面 (-)' : '中性 (0)'}
              </Badge>
            </div>
            <div className="bg-anchor-bgSecondary rounded-sm p-2">
              <div className="text-xs text-anchor-textSecondary mb-1">风险等级</div>
              <Badge
                variant={conclusion.risk_level === 'low' ? 'positive' : conclusion.risk_level === 'high' ? 'negative' : 'accent'}
                className="text-sm"
              >
                {conclusion.risk_level === 'low' ? '低' : conclusion.risk_level === 'high' ? '高' : '中'}
              </Badge>
            </div>
          </div>

          <Separator />

          {/* 综合判断 */}
          <div>
            <div className="text-xs font-medium text-anchor-textSecondary mb-1">综合判断</div>
            <div className="text-xs text-anchor-text leading-relaxed">{conclusion.summary}</div>
          </div>

          {/* 次日观察点 */}
          {conclusion.next_watch && conclusion.next_watch.length > 0 && (
            <div>
              <div className="text-xs font-medium text-anchor-textSecondary mb-1">次日观察点</div>
              <ul className="text-xs text-anchor-text space-y-0.5 list-disc list-inside">
                {conclusion.next_watch.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}