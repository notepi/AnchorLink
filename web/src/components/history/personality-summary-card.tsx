'use client';

import { PersonalitySummary, PersonalitySummaryMetrics } from '@/types';

interface PersonalitySummaryCardProps {
  summary: PersonalitySummary;
  summaryMetrics: PersonalitySummaryMetrics;
  sampleDays: number;
  validSampleDays: number;
  sampleWarnings: string[];
  likesCount: number;
  dislikesCount: number;
  counterIntuitiveCount: number;
  trapCount: number;
}

export function PersonalitySummaryCard({
  summary,
  summaryMetrics,
  sampleDays,
  validSampleDays,
  sampleWarnings,
  likesCount,
  dislikesCount,
  counterIntuitiveCount,
  trapCount
}: PersonalitySummaryCardProps) {
  const totalPatterns = likesCount + dislikesCount + counterIntuitiveCount + trapCount;

  // 环形图分段
  const segments = [
    { value: likesCount, color: '#ef4444', label: '偏好' },
    { value: dislikesCount, color: '#22c55e', label: '规避' },
    { value: counterIntuitiveCount, color: '#a855f7', label: '反直觉' },
    { value: trapCount, color: '#f97316', label: '陷阱' },
  ].filter(s => s.value > 0);

  // SVG donut 参数
  const size = 96;
  const strokeWidth = 10;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const cx = size / 2;
  const cy = size / 2;

  // 计算每段弧长和偏移
  let offset = 0;
  const arcs = segments.map(s => {
    const arcLength = totalPatterns > 0 ? (s.value / totalPatterns) * circumference : 0;
    const startOffset = offset;
    offset += arcLength;
    return { ...s, arcLength, startOffset };
  });

  const confidenceColor = {
    high: 'text-green-400',
    medium: 'text-yellow-400',
    low: 'text-orange-400'
  }[summary.confidence];

  return (
    <section className="border border-anchor-border bg-anchor-bgSecondary">
      <div className="flex items-stretch">
        {/* 左侧环形图 */}
        <div className="relative flex-shrink-0 p-4 flex flex-col items-center justify-center border-r border-anchor-border">
          <div className="relative" style={{ width: size, height: size }}>
            <svg width={size} height={size} className="transform -rotate-90">
              {/* 背景环 */}
              <circle
                cx={cx} cy={cy} r={radius}
                fill="none"
                stroke="#374151"
                strokeWidth={strokeWidth}
              />
              {/* 数据段 */}
              {arcs.map((arc, idx) => (
                <circle
                  key={idx}
                  cx={cx} cy={cy} r={radius}
                  fill="none"
                  stroke={arc.color}
                  strokeWidth={strokeWidth}
                  strokeDasharray={`${arc.arcLength} ${circumference - arc.arcLength}`}
                  strokeDashoffset={-arc.startOffset}
                  strokeLinecap="round"
                />
              ))}
            </svg>
            {/* 中心文字 */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span className="text-[10px] text-anchor-textMuted leading-none">性格</span>
            </div>
          </div>
          {/* traits 胶囊标签行 */}
          <div className="flex flex-wrap gap-1 mt-3 justify-center max-w-[140px]">
            {summary.traits.slice(0, 3).map((trait, idx) => (
              <span
                key={idx}
                className="px-1.5 py-0.5 text-[10px] rounded-sm border border-anchor-border text-anchor-text truncate max-w-[120px]"
                title={trait}
              >
                {trait}
              </span>
            ))}
          </div>
        </div>

        {/* 中间 headline + 描述 */}
        <div className="flex-1 p-4 min-w-0">
          <h2 className="text-sm font-semibold text-anchor-text mb-2">
            历史性格档案
          </h2>
          <p className="text-xs text-anchor-textSecondary leading-relaxed">
            {summary.headline}
          </p>
          {sampleWarnings.length > 0 && (
            <div className="mt-3 pt-2 border-t border-anchor-border">
              <div className="flex items-start gap-2">
                <span className="text-yellow-500 text-xs">⚠</span>
                <div className="text-[10px] text-anchor-textMuted space-y-1">
                  {sampleWarnings.map((warning, idx) => (
                    <p key={idx}>{warning}</p>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 右上档案标签区 */}
        <div className="flex-shrink-0 p-4 border-l border-anchor-border min-w-[120px]">
          <div className="space-y-3">
            <div className="text-center">
              <div className="text-[10px] text-anchor-textMuted uppercase tracking-wide">样本</div>
              <div className="text-lg font-semibold text-anchor-text">{validSampleDays}<span className="text-xs text-anchor-textMuted font-normal">/{sampleDays}</span></div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-anchor-textMuted uppercase tracking-wide">置信度</div>
              <div className={`text-sm font-medium ${confidenceColor}`}>
                {summary.confidence === 'high' ? '高' : summary.confidence === 'medium' ? '中' : '低'}
              </div>
            </div>
            {summaryMetrics.baseline_win_rate_1d !== null && (
              <div className="text-center">
                <div className="text-[10px] text-anchor-textMuted uppercase tracking-wide">基线胜率</div>
                <div className={`text-lg font-semibold ${summaryMetrics.baseline_win_rate_1d >= 0.5 ? 'text-red-400' : 'text-green-400'}`}>
                  {(summaryMetrics.baseline_win_rate_1d * 100).toFixed(0)}%
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
