'use client';

import { create } from 'zustand';

interface AppState {
  // 当前选中的日期 (YYYYMMDD)
  selectedDate: string;
  // 当前选中的股票代码
  selectedStock: string | null;
  // 当前筛选的股票池
  poolFilter: string;
  // 可用日期列表
  availableDates: string[];
  // 数据加载状态
  isLoading: boolean;

  // Actions
  setDate: (date: string) => void;
  setStock: (symbol: string | null) => void;
  setPoolFilter: (pool: string) => void;
  setAvailableDates: (dates: string[]) => void;
  setLoading: (loading: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // 初始值
  selectedDate: '',
  selectedStock: null,
  poolFilter: 'all',
  availableDates: [],
  isLoading: false,

  // Actions
  setDate: (date) => set({ selectedDate: date }),
  setStock: (symbol) => set({ selectedStock: symbol }),
  setPoolFilter: (pool) => set({ poolFilter: pool }),
  setAvailableDates: (dates) => set({ availableDates: dates }),
  setLoading: (loading) => set({ isLoading: loading }),
}));