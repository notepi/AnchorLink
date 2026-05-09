'use client';

import { Conclusion, IndustryState } from '@/types';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';

interface ConclusionPanelProps {
  conclusion: Conclusion;
  industryState?: IndustryState;
}

/**
 * 结论面板 - 三核心指标 + 综合判断 + 次日观察
 */
export function ConclusionPanel({ conclusion, industryState }: ConclusionPanelProps) {
  // 计算行业环境描述
  const getIndustryEnvironmentDesc = () => {
    const median = industryState?.direct_peers_return_median;
    if (median === null || median === undefined) return '数据缺失';

    if (median > 0.5) {
      return `核心池中位数 +${median.toFixed(2)}%，行业整体上涨，跟涨概率高`;
    } else if (median < -0.5) {
      return `核心池中位数 ${median.toFixed(2)}%，行业整体下跌，防守为主`;
    } else {
      return `核心池中位数 ${median.toFixed(2)}%，行业震荡，观望为主`;
    }
  };

  // 计算个股Alpha描述
  const getAnchorAlphaDesc = () => {
    const beta = conclusion.industry_beta;
    const alpha = conclusion.anchor_alpha;

    if (alpha === 'positive') {
      return beta === 'positive' ? '跑赢行业，顺势上涨' : '逆势上涨，独立行情';
    } else if (alpha === 'negative') {
      return beta === 'negative' ? '跑输行业，顺势下跌' : '逆势下跌，需警惕';
    } else {
      return '与行业同步，无明显Alpha';
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>综合结论</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {/* 行业环境 - 增强展示 */}
          <div className="bg-anchor-bgSecondary rounded-sm p-3 border border-anchor-border">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-anchor-text">行业环境</span>
              <Badge
                variant={conclusion.industry_beta === 'positive' ? 'positive' : conclusion.industry_beta === 'negative' ? 'negative' : 'neutral'}
              >
                {conclusion.industry_beta === 'positive' ? '正面' : conclusion.industry_beta === 'negative' ? '负面' : '中性'}
              </Badge>
            </div>
            <div className="text-xs text-anchor-text leading-relaxed">
              {getIndustryEnvironmentDesc()}
            </div>
            <div className="text-xs text-anchor-textMuted mt-1">
              来源: 核心池（direct_peers）涨跌幅中位数
            </div>
          </div>

          {/* 个股Alpha & 风险等级 */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-anchor-bgSecondary rounded-sm p-3 border border-anchor-border">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-anchor-text">个股Alpha</span>
                <Badge
                  variant={conclusion.anchor_alpha === 'positive' ? 'positive' : conclusion.anchor_alpha === 'negative' ? 'negative' : 'neutral'}
                >
                  {conclusion.anchor_alpha === 'positive' ? '正面' : conclusion.anchor_alpha === 'negative' ? '负面' : '中性'}
                </Badge>
              </div>
              <div className="text-xs text-anchor-text">
                {getAnchorAlphaDesc()}
              </div>
            </div>
            <div className="bg-anchor-bgSecondary rounded-sm p-3 border border-anchor-border">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-anchor-text">风险等级</span>
                <Badge
                  variant={conclusion.risk_level === 'low' ? 'positive' : conclusion.risk_level === 'high' ? 'negative' : 'accent'}
                >
                  {conclusion.risk_level === 'low' ? '低' : conclusion.risk_level === 'high' ? '高' : '中'}
                </Badge>
              </div>
              <div className="text-xs text-anchor-text">
                {conclusion.risk_level === 'low' ? '市场环境稳定，可积极操作' :
                 conclusion.risk_level === 'high' ? '风险较高，建议谨慎' : '风险适中，正常操作'}
              </div>
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