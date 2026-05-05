// ============================================================
// Reports 页面 - 每日复盘报告列表
// ============================================================

import Link from 'next/link';
import { getReportDates, formatDate } from '@/lib/data-reader';

export default async function ReportsPage() {
  const dates = await getReportDates();

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-lg font-medium text-anchor-text">每日复盘报告</h1>
        <p className="text-sm text-anchor-textMuted mt-1">
          查看历史每日复盘报告
        </p>
      </div>

      {/* 报告列表 */}
      <div className="bg-anchor-bgSecondary rounded-sm border border-anchor-border">
        {dates.length > 0 ? (
          <div className="divide-y divide-anchor-border">
            {dates.map(date => (
              <Link
                key={date}
                href={`/reports/${date}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-anchor-bg transition-colors"
              >
                <div>
                  <div className="text-sm text-anchor-text">{formatDate(date)}</div>
                  <div className="text-xs text-anchor-textMuted mt-0.5">每日复盘报告</div>
                </div>
                <span className="text-anchor-accent">→</span>
              </Link>
            ))}
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