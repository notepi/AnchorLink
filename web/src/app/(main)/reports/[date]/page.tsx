// ============================================================
// Report Detail 页面 - 单篇报告查看器
// ============================================================

import { notFound } from 'next/navigation';
import Link from 'next/link';
import { getReport, getReportDates, formatDate } from '@/lib/data-reader';

interface ReportPageProps {
  params: Promise<{ date: string }>;
}

export default async function ReportPage({ params }: ReportPageProps) {
  const { date } = await params;
  const dates = await getReportDates();

  // 如果日期不在列表中，返回404
  if (!dates.includes(date)) {
    notFound();
  }

  const content = await getReport(date);

  if (!content) {
    notFound();
  }

  return (
    <div className="space-y-6">
      {/* 返回链接 */}
      <Link
        href="/reports"
        className="text-xs text-anchor-textMuted hover:text-anchor-accent transition-colors"
      >
        ← 返回报告列表
      </Link>

      {/* 报告标题 */}
      <div>
        <h1 className="text-lg font-medium text-anchor-text">每日复盘报告</h1>
        <p className="text-sm text-anchor-textMuted mt-1">{formatDate(date)}</p>
      </div>

      {/* 报告内容 */}
      <div className="bg-anchor-bgSecondary rounded-sm p-6 border border-anchor-border">
        <article className="prose prose-invert prose-sm max-w-none whitespace-pre-wrap">
          {content}
        </article>
      </div>
    </div>
  );
}