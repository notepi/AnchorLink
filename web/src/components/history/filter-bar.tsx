'use client';

interface FilterBarProps {
  sortedDates: string[];
  startDate: string;
  endDate: string;
  signalCategory: string;
  onStartDateChange: (date: string) => void;
  onEndDateChange: (date: string) => void;
  onSignalCategoryChange: (category: string) => void;
  sampleDays: number;
}

function formatDateDisplay(dateStr: string): string {
  const s = String(dateStr);
  if (s.length !== 8) return s;
  return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
}

export function FilterBar({
  sortedDates,
  startDate,
  endDate,
  signalCategory,
  onStartDateChange,
  onEndDateChange,
  onSignalCategoryChange,
  sampleDays,
}: FilterBarProps) {
  return (
    <div className="bg-anchor-bgSecondary rounded-sm p-4 border border-anchor-border">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        {/* 标题和样本数 */}
        <div>
          <h1 className="text-lg font-medium text-anchor-text">历史分析</h1>
          <p className="text-sm text-anchor-textMuted mt-1">
            {sampleDays} 个交易日
            {sortedDates[0] && sortedDates[sortedDates.length - 1] && (
              <>
                {' '}
                &middot;{' '}
                {formatDateDisplay(startDate)}
                {' ~ '}
                {formatDateDisplay(endDate)}
              </>
            )}
          </p>
        </div>

        {/* 筛选控件 */}
        <div className="flex flex-wrap items-center gap-4">
          {/* 日期范围 */}
          <div className="flex items-center gap-2">
            <label className="text-sm text-anchor-textMuted">起始日期</label>
            <select
              value={startDate}
              onChange={(e) => onStartDateChange(e.target.value)}
              className="bg-anchor-bgTertiary border border-anchor-border text-anchor-text text-sm rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-anchor-accent"
            >
              {sortedDates.map((date) => (
                <option key={date} value={date}>
                  {formatDateDisplay(date)}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm text-anchor-textMuted">结束日期</label>
            <select
              value={endDate}
              onChange={(e) => onEndDateChange(e.target.value)}
              className="bg-anchor-bgTertiary border border-anchor-border text-anchor-text text-sm rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-anchor-accent"
            >
              {sortedDates.map((date) => (
                <option key={date} value={date}>
                  {formatDateDisplay(date)}
                </option>
              ))}
            </select>
          </div>

          {/* 信号类别 */}
          <div className="flex items-center gap-2">
            <label className="text-sm text-anchor-textMuted">信号类别</label>
            <select
              value={signalCategory}
              onChange={(e) => onSignalCategoryChange(e.target.value)}
              className="bg-anchor-bgTertiary border border-anchor-border text-anchor-text text-sm rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-anchor-accent"
            >
              <option value="all">全部</option>
              <option value="beta">Beta</option>
              <option value="alpha">Alpha</option>
              <option value="volume">Volume</option>
              <option value="rotation">Rotation</option>
              <option value="abnormal">Abnormal</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}
