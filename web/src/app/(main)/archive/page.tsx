// ============================================================
// Archive 页面 - 归档时间线
// ============================================================

import { getArchiveEntries, formatDate } from '@/lib/data-reader';

export default async function ArchivePage() {
  const entries = await getArchiveEntries();

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-lg font-medium text-anchor-text">归档时间线</h1>
        <p className="text-sm text-anchor-textMuted mt-1">
          历史指标归档和事件归档
        </p>
      </div>

      {/* 归档列表 */}
      <div className="bg-anchor-bgSecondary rounded-sm border border-anchor-border">
        {entries.length > 0 ? (
          <div className="divide-y divide-anchor-border">
            {entries.map((entry, i) => (
              <div
                key={i}
                className="flex items-center gap-4 px-4 py-3"
              >
                <div className="w-24 text-sm font-mono text-anchor-text">
                  {formatDate(entry.date)}
                </div>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  entry.type === 'metrics'
                    ? 'bg-anchor-accent/10 text-anchor-accent'
                    : 'bg-anchor-positive/10 text-anchor-positive'
                }`}>
                  {entry.type === 'metrics' ? '指标' : '事件'}
                </span>
                <span className="text-sm text-anchor-text">{entry.description}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="px-4 py-8 text-center text-sm text-anchor-textMuted">
            暂无归档数据
          </div>
        )}
      </div>
    </div>
  );
}