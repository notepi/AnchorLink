import Link from 'next/link';
import { getReportDates, formatDate } from '@/lib/data-reader';
import { getV2ScoringData } from '@/lib/v2-scoring-reader';
import { REGIME_LABEL } from '@/lib/glossary';

export default async function ReportsPage() {
  const dates = await getReportDates();
  const v2Data = await getV2ScoringData();

  // 构建日期→评分映射
  const scoreMap = new Map<string, { score: number; regime: string; veto: boolean }>();
  if (v2Data) {
    for (const r of v2Data.dailyResults) {
      scoreMap.set(r.date, { score: r.score, regime: r.regime, veto: r.veto });
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-medium text-anchor-text">每日分析报告</h1>
        <p className="text-sm text-anchor-textMuted mt-1">
          V2 评分系统每日分析报告
        </p>
      </div>

      <div className="bg-anchor-bgSecondary rounded-sm border border-anchor-border">
        {dates.length > 0 ? (
          <div className="divide-y divide-anchor-border">
            {dates.map(date => {
              const info = scoreMap.get(date);
              return (
                <Link
                  key={date}
                  href={`/reports/${date}`}
                  className="flex items-center justify-between px-4 py-3 hover:bg-anchor-bg transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div>
                      <div className="text-sm text-anchor-text">{formatDate(date)}</div>
                      <div className="text-xs text-anchor-textMuted mt-0.5">
                        {info ? 'V2 评分报告' : '行业分析报告'}
                      </div>
                    </div>
                    {info && (
                      <>
                        <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded ${
                          info.score > 0 ? 'text-red-500 bg-red-500/10' :
                          info.score < 0 ? 'text-green-500 bg-green-500/10' :
                          'text-gray-400 bg-gray-400/10'
                        }`}>
                          {info.score > 0 ? '+' : ''}{info.score}
                        </span>
                        <span className="text-xs text-anchor-textMuted">
                          {REGIME_LABEL[info.regime] || info.regime}
                        </span>
                        {info.veto && (
                          <span className="text-xs text-red-400 font-semibold">VETO</span>
                        )}
                      </>
                    )}
                  </div>
                  <span className="text-anchor-accent">→</span>
                </Link>
              );
            })}
          </div>
        ) : (
          <div className="px-4 py-8 text-center text-sm text-anchor-textMuted">
            暂无报告数据
          </div>
        )}
      </div>
    </div>
  );
}
