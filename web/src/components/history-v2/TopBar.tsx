'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import type { DashboardView } from '@/types/dashboard-view';
import { formatDate } from '@/lib/history-v2/formatters';

interface TopBarProps {
  meta: DashboardView['meta'];
  filter: DashboardView['filter'];
  sortedDates: string[];
}

const signalCategoryMap: Record<string, string> = {
  all: '全部',
  preference: '偏好环境',
  avoid: '规避环境',
  counter_intuitive: '反直觉机会',
  trap: '信号陷阱'
};

const signalCategoryOptions = Object.entries(signalCategoryMap);

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

  const currentStart = searchParams.get('startDate') ?? filter?.startDate ?? '';
  const currentEnd = searchParams.get('endDate') ?? filter?.endDate ?? '';
  const currentCategory = searchParams.get('signalCategory') ?? filter?.signalCategory ?? 'all';

  const updateFilter = useCallback((key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set(key, value);
    router.push(`/history-v2?${params.toString()}`);
  }, [router, searchParams]);

  const rangeText = `${meta?.sampleDays ?? 0} 个交易日 · ${formatDate(currentStart)} ~ ${formatDate(currentEnd)} · 数据更新于 ${meta?.dataUpdateTime ?? ''}`;

  return (
    <header className="topbar">
      <div className="title">
        <h1>历史分析</h1>
        <p>{rangeText} · {meta?.stockName ?? ''}({meta?.stockCode ?? ''})</p>
      </div>
      <div className="filters">
        <div className="filter">起始日期
          <SelectDropdown
            value={currentStart}
            options={sortedDates}
            formatOption={v => formatDate(v)}
            onChange={v => updateFilter('startDate', v)}
          />
        </div>
        <div className="filter">结束日期
          <SelectDropdown
            value={currentEnd}
            options={sortedDates}
            formatOption={v => formatDate(v)}
            onChange={v => updateFilter('endDate', v)}
          />
        </div>
        <div className="filter">信号类别
          <SelectDropdown
            value={currentCategory}
            options={signalCategoryOptions.map(([k]) => k)}
            formatOption={v => signalCategoryMap[v] ?? v}
            onChange={v => updateFilter('signalCategory', v)}
          />
        </div>
      </div>
    </header>
  );
}
