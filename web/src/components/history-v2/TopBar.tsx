'use client';

import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import type { DashboardView } from '@/types/dashboard-view';
import { formatDate } from '@/lib/history-v2/formatters';

interface TopBarProps {
  meta: DashboardView['meta'];
  filter: DashboardView['filter'];
  sortedDates: string[];
}

const PAGE_SIZE = 7;

function SelectDropdown({ value, options, formatOption, onChange }: {
  value: string;
  options: string[];
  formatOption: (v: string) => string;
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div className="select" ref={ref} onClick={() => setOpen(v => !v)}>
      {formatOption(value)} <span>⌄</span>
      {open && (
        <div className="select-dropdown" onClick={e => e.stopPropagation()}>
          {options.map(opt => (
            <div
              key={opt}
              className={`select-option ${opt === value ? 'active' : ''}`}
              onClick={() => { onChange(opt); setOpen(false); }}
            >
              {formatOption(opt)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function TopBar({ meta, filter, sortedDates }: TopBarProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const urlDate = searchParams.get('date') ?? '';
  const currentStart = searchParams.get('startDate') ?? '';
  const currentEnd = searchParams.get('endDate') ?? '';
  const isRangeMode = searchParams.get('range') === '1';

  const latestDate = sortedDates[sortedDates.length - 1] ?? '';
  const earliestDate = sortedDates[0] ?? '';
  const activeDate = urlDate || latestDate;

  // 本地选中状态：点击日期按钮只改本地，点查询才跳转
  const [pendingDate, setPendingDate] = useState(activeDate);
  useEffect(() => { setPendingDate(activeDate); }, [activeDate]);

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
  const goRight = useCallback(() => setPageOffset(o => o - PAGE_SIZE), []);

  const applyDate = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    if (pendingDate === latestDate) {
      params.delete('date');
    } else {
      params.set('date', pendingDate);
    }
    router.push(`/history-v2?${params.toString()}`);
  }, [router, searchParams, pendingDate, latestDate]);

  const switchToRange = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('range', '1');
    params.set('startDate', currentStart || earliestDate);
    params.set('endDate', currentEnd || latestDate);
    params.delete('date');
    router.push(`/history-v2?${params.toString()}`);
  }, [router, searchParams, currentStart, currentEnd, earliestDate, latestDate]);

  const switchToDate = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete('range');
    params.delete('startDate');
    params.delete('endDate');
    params.delete('date');
    router.push(`/history-v2?${params.toString()}`);
  }, [router, searchParams]);

  const rangeText = `${meta?.sampleDays ?? 0} 个交易日 · ${formatDate(earliestDate)} ~ ${formatDate(latestDate)} · 数据更新于 ${meta?.dataUpdateTime ?? ''}`;

  const hasChanged = pendingDate !== activeDate;

  return (
    <header className="topbar">
      <div className="title">
        <h1>历史分析</h1>
        <p>{rangeText} · {meta?.stockName ?? ''}({meta?.stockCode ?? ''})</p>
      </div>
      <div className="filters">
        {!isRangeMode ? (
          <div className="date-bar">
            <button disabled={!canGoLeft} onClick={goLeft} title="更早">‹</button>
            {visibleDates.map(d => (
              <button
                key={d}
                className={d === pendingDate ? 'active' : ''}
                onClick={() => setPendingDate(d)}
              >
                {formatDate(d, 'MM/DD')}
              </button>
            ))}
            <button disabled={!canGoRight} onClick={goRight} title="更近">›</button>
            <button
              className={`filter-apply${hasChanged ? ' has-change' : ''}`}
              onClick={applyDate}
              disabled={!hasChanged}
            >查询</button>
            <button className="filter-toggle" onClick={switchToRange}>范围</button>
          </div>
        ) : (
          <>
            <div className="filter">起始
              <SelectDropdown
                value={currentStart || earliestDate}
                options={sortedDates}
                formatOption={v => formatDate(v)}
                onChange={v => {
                  const params = new URLSearchParams(searchParams.toString());
                  params.set('startDate', v);
                  router.push(`/history-v2?${params.toString()}`);
                }}
              />
            </div>
            <div className="filter">结束
              <SelectDropdown
                value={currentEnd || latestDate}
                options={sortedDates}
                formatOption={v => formatDate(v)}
                onChange={v => {
                  const params = new URLSearchParams(searchParams.toString());
                  params.set('endDate', v);
                  router.push(`/history-v2?${params.toString()}`);
                }}
              />
            </div>
            <button className="filter-toggle" onClick={switchToDate}>单日</button>
          </>
        )}
      </div>
    </header>
  );
}
