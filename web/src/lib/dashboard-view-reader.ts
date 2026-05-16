import { readFile } from 'fs/promises';
import { join } from 'path';
import { cache } from 'react';
import type { DashboardView } from '@/types/dashboard-view';

// Next.js 的 process.cwd() 返回 web 目录，数据在父目录
const PROJECT_ROOT = join(process.cwd(), '..');
const DATA_DIR = join(PROJECT_ROOT, 'data');
const OUTPUT_DIR = join(DATA_DIR, 'output');
const DASHBOARD_VIEW_PATH = join(OUTPUT_DIR, 'dashboard_view.json');

/**
 * 获取统一历史分析视图数据
 * 新页面必须通过此函数获取数据，禁止直接调用旧数据接口
 * 使用 React cache 实现请求去重
 */
export const getDashboardView = cache(async (): Promise<DashboardView | null> => {
  try {
    const content = await readFile(DASHBOARD_VIEW_PATH, 'utf-8');
    return JSON.parse(content) as DashboardView;
  } catch (error) {
    console.error('Failed to read dashboard_view.json:', error);
    return null;
  }
});
