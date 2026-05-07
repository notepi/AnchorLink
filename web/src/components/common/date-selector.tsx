'use client';

import { useState, useEffect, useRef } from 'react';
import { useAppStore } from '@/lib/store';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { formatDate } from '@/lib/utils';

export function DateSelector() {
  const selectedDate = useAppStore((state) => state.selectedDate);
  const [localDates, setLocalDates] = useState<string[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);

  // 加载日期列表
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    fetch('/api/dates')
      .then(res => res.json())
      .then(data => {
        if (data.dates && data.dates.length > 0) {
          setLocalDates(data.dates);
          useAppStore.getState().setAvailableDates(data.dates);
          if (!selectedDate) {
            useAppStore.getState().setDate(data.dates[0]);
          }
        }
      });
  }, []);

  // 点击外部关闭
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (localDates.length === 0) {
    return <Badge variant="neutral">暂无数据</Badge>;
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        className="text-xs"
      >
        {selectedDate ? formatDate(selectedDate) : '选择日期'}
      </Button>

      {isOpen && (
        <div className="absolute top-full right-0 mt-1 bg-anchor-bgSecondary border border-anchor-border rounded-sm shadow-md z-50 min-w-[120px]">
          {localDates.slice(0, 10).map(date => (
            <button
              key={date}
              onClick={() => {
                useAppStore.getState().setDate(date);
                setIsOpen(false);
              }}
              className={`w-full px-2 py-1 text-xs text-left hover:bg-anchor-bgTertiary transition-colors ${
                date === selectedDate ? 'text-anchor-accent' : 'text-anchor-textSecondary'
              }`}
            >
              {formatDate(date)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}