// ============================================================
// Industry Report 页面 - 行业分析报告
// ============================================================

import { getIndustryReport } from '@/lib/data-reader';

export default async function IndustryReportPage() {
  const content = await getIndustryReport();

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-lg font-medium text-anchor-text">行业分析报告</h1>
        <p className="text-sm text-anchor-textMuted mt-1">
          行业分析报告查看器
        </p>
      </div>

      {/* 报告内容 */}
      <div className="bg-anchor-bgSecondary rounded-sm p-6 border border-anchor-border">
        {content ? (
          <article
            className="prose prose-invert prose-sm max-w-none whitespace-pre-wrap"
            style={{ whiteSpace: 'pre-wrap' }}
          >
            {content}
          </article>
        ) : (
          <div className="text-center py-8 text-sm text-anchor-textMuted">
            暂无行业分析报告
          </div>
        )}
      </div>
    </div>
  );
}