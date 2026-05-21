'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

interface TodayTopBarProps {
  sortedDates: string[];
  selectedDate: string;
  latestDate: string;
  stockName?: string;
  dataUpdateTime?: string;
}

const PAGE_SIZE = 7;

function fmtDate(d: string): string {
  if (!d || d.length !== 8) return d;
  return `${d.slice(4, 6)}/${d.slice(6, 8)}`;
}

function fmtFull(d: string): string {
  if (!d || d.length !== 8) return d;
  return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
}

export default function TodayTopBar({
  sortedDates,
  selectedDate,
  latestDate,
  stockName,
  dataUpdateTime,
}: TodayTopBarProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [pendingDate, setPendingDate] = useState(selectedDate);
  useEffect(() => { setPendingDate(selectedDate); }, [selectedDate]);

  const selectedIndex = useMemo(
    () => sortedDates.indexOf(pendingDate),
    [sortedDates, pendingDate]
  );

  const [pageOffset, setPageOffset] = useState(0);
  useEffect(() => { setPageOffset(0); }, [pendingDate]);

  const pageStart = Math.max(0, selectedIndex - 3 - pageOffset);
  const pageEnd = Math.min(sortedDates.length, pageStart + PAGE_SIZE);
  const actualStart = Math.max(0, pageEnd - PAGE_SIZE);
  const visibleDates = sortedDates.slice(actualStart, pageEnd);

  const canGoLeft = actualStart > 0;
  const canGoRight = pageEnd < sortedDates.length;

  const goLeft = useCallback(() => setPageOffset(o => o + PAGE_SIZE), []);
  const goRight = useCallback(() => setPageOffset(o => Math.max(0, o - PAGE_SIZE)), []);

  const hasChanged = pendingDate !== selectedDate;

  const applyDate = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    if (pendingDate === latestDate) {
      params.delete('date');
    } else {
      params.set('date', pendingDate);
    }
    const qs = params.toString();
    router.push(`/today${qs ? `?${qs}` : ''}`);
  }, [router, searchParams, pendingDate, latestDate]);

  // 也支持键盘左右翻日期
  const containerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') {
        setPendingDate(d => {
          const i = sortedDates.indexOf(d);
          return i > 0 ? sortedDates[i - 1] : d;
        });
      } else if (e.key === 'ArrowRight') {
        setPendingDate(d => {
          const i = sortedDates.indexOf(d);
          return i < sortedDates.length - 1 ? sortedDates[i + 1] : d;
        });
      } else if (e.key === 'Enter') {
        applyDate();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [sortedDates, applyDate]);

  return (
    <header className="tc-topbar" ref={containerRef}>
      <div className="tc-topbar-meta">
        <span className="tc-topbar-stock">{stockName ?? '铂力特'} · 今日看板</span>
        <span className="tc-topbar-update">数据更新 {dataUpdateTime ?? '-'}</span>
      </div>
      <div className="tc-topbar-datebar">
        <button
          className="tc-date-nav"
          disabled={!canGoLeft}
          onClick={goLeft}
          title="更早"
        >‹</button>

        {visibleDates.map(d => (
          <button
            key={d}
            className={`tc-date-btn${d === pendingDate ? ' tc-date-active' : ''}${d === latestDate ? ' tc-date-latest' : ''}`}
            onClick={() => setPendingDate(d)}
            title={fmtFull(d)}
          >
            {fmtDate(d)}
          </button>
        ))}

        <button
          className="tc-date-nav"
          disabled={!canGoRight}
          onClick={goRight}
          title="更近"
        >›</button>

        <button
          className={`tc-date-apply${hasChanged ? ' tc-date-apply-active' : ''}`}
          disabled={!hasChanged}
          onClick={applyDate}
        >
          {hasChanged ? `查看 ${fmtFull(pendingDate)}` : `当前 ${fmtFull(selectedDate)}`}
        </button>
      </div>
      <p className="tc-topbar-hint">← → 键翻日期，Enter 确认 · 点按钮切换后点「查看」跳转</p>
    </header>
  );
}
