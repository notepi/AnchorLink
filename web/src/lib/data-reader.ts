import { readFile, readdir } from 'fs/promises';
import { join } from 'path';
import { cache } from 'react';
import YAML from 'yaml';
import Papa from 'papaparse';
import type {
  IndustrySnapshot,
  PeerMatrixRow,
  PoolConfig,
  DateInfo,
  HistorySummaryRow,
  QuadrantStat,
  SignalLiftRow,
  ExtremeDivergence,
  RollingMetricRow,
  StateTransition,
  EventPathRow,
  CounterIntuitiveSignal,
  ConditionalSignalEffect,
  OperatorHistoryView,
} from '@/types';

// ============================================================
// 数据目录配置
// ============================================================

// Next.js 的 process.cwd() 返回 web 目录，数据在父目录
const PROJECT_ROOT = join(process.cwd(), '..');
const DATA_DIR = join(PROJECT_ROOT, 'data');
const OUTPUT_DIR = join(DATA_DIR, 'output');
const CONFIG_DIR = join(PROJECT_ROOT, 'config');

// ============================================================
// 行业快照读取（industry_snapshot.json）
// ============================================================

/**
 * 获取指定日期的行业快照
 * 使用 React cache 实现请求去重
 */
export const getSnapshot = cache(async (date: string): Promise<IndustrySnapshot | null> => {
  try {
    const filePath = join(OUTPUT_DIR, date, 'industry_snapshot.json');
    const content = await readFile(filePath, 'utf-8');
    return JSON.parse(content) as IndustrySnapshot;
  } catch (error) {
    console.error(`Failed to read snapshot for ${date}:`, error);
    return null;
  }
});

/**
 * 获取最新日期的行业快照
 */
export async function getLatestSnapshot(): Promise<IndustrySnapshot | null> {
  const dates = await getAvailableDates();
  if (dates.length === 0) return null;

  const latestDate = dates[0];
  return getSnapshot(latestDate);
}

// ============================================================
// Peer Matrix 读取（peer_matrix.csv）
// ============================================================

/**
 * 获取指定日期的 Peer Matrix
 */
export async function getMatrix(date: string): Promise<PeerMatrixRow[]> {
  try {
    const filePath = join(OUTPUT_DIR, date, 'peer_matrix.csv');
    const content = await readFile(filePath, 'utf-8');

    const result = Papa.parse<PeerMatrixRow>(content, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: true, // 自动转换数字类型
    });

    return result.data;
  } catch (error) {
    console.error(`Failed to read matrix for ${date}:`, error);
    return [];
  }
}

// ============================================================
// 池子配置读取（pools.yaml）
// ============================================================

/**
 * 获取池子配置
 */
export const getConfig = cache(async (): Promise<PoolConfig | null> => {
  try {
    const filePath = join(CONFIG_DIR, 'pools.yaml');
    const content = await readFile(filePath, 'utf-8');
    return YAML.parse(content) as PoolConfig;
  } catch (error) {
    console.error('Failed to read pools config:', error);
    return null;
  }
});

// ============================================================
// 可用日期列表
// ============================================================

/**
 * 获取所有可用日期（降序排列）
 */
export async function getAvailableDates(): Promise<string[]> {
  try {
    const entries = await readdir(OUTPUT_DIR, { withFileTypes: true });

    const directories = entries
      .filter(entry => entry.isDirectory())
      .map(entry => entry.name)
      .filter(name => /^\d{8}$/.test(name)) // 只保留 YYYYMMDD 格式
      .sort((a, b) => b.localeCompare(a)); // 降序排列（最新在前）

    return directories;
  } catch (error) {
    console.error('Failed to read available dates:', error);
    return [];
  }
}

/**
 * 获取日期详细信息
 */
export async function getDateInfos(): Promise<DateInfo[]> {
  const dates = await getAvailableDates();

  return dates.map(date => ({
    date,
    hasSnapshot: true, // 假设所有日期都有 snapshot
    hasMatrix: true,   // 假设所有日期都有 matrix
  }));
}

// ============================================================
// 辅助函数
// ============================================================

/**
 * 格式化日期（YYYYMMDD -> YYYY-MM-DD）
 */
export function formatDate(dateStr: string): string {
  if (!dateStr || dateStr.length !== 8) return dateStr;
  return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`;
}

/**
 * 格式化涨跌幅（百分比显示）
 */
export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

/**
 * 格式化金额（万元单位）
 */
export function formatAmount(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return `${(value / 10000).toFixed(2)}万`;
}

/**
 格式化排名（分位数显示）
 */
export function formatRank(rank: number | null | undefined, total: number | null | undefined): string {
  if (rank === null || rank === undefined || total === null || total === undefined) return '--';
  return `${rank}/${total}`;
}

// ============================================================
// 报告读取（reports/ 目录）
// ============================================================

/**
 * 获取所有报告日期
 */
export async function getReportDates(): Promise<string[]> {
  try {
    const reportsDir = join(DATA_DIR, '..', 'reports');
    const entries = await readdir(reportsDir, { withFileTypes: true });

    const dates = entries
      .filter(entry => entry.isDirectory())
      .map(entry => entry.name)
      .filter(name => /^\d{8}$/.test(name))
      .sort((a, b) => b.localeCompare(a));

    return dates;
  } catch (error) {
    console.error('Failed to read report dates:', error);
    return [];
  }
}

/**
 * 获取报告列表元数据
 */
export async function getReportList(): Promise<Array<{ date: string; path: string }>> {
  const dates = await getReportDates();
  return dates.map(date => ({
    date,
    path: `/reports/${date}`,
  }));
}

/**
 * 获取单篇报告内容（Markdown）
 */
export async function getReport(date: string): Promise<string | null> {
  try {
    const reportDir = join(DATA_DIR, '..', 'reports', date);
    const files = await readdir(reportDir);

    // 查找 Markdown 文件
    const mdFile = files.find(f => f.endsWith('.md'));
    if (!mdFile) return null;

    const filePath = join(reportDir, mdFile);
    const content = await readFile(filePath, 'utf-8');
    return content;
  } catch (error) {
    console.error(`Failed to read report for ${date}:`, error);
    return null;
  }
}

// ============================================================
// 行业分析报告（industry-report/ 目录）
// ============================================================

/**
 * 获取行业分析报告内容
 */
export async function getIndustryReport(date?: string): Promise<string | null> {
  try {
    const reportDir = join(DATA_DIR, '..', 'reports');
    let targetPath: string;

    if (date) {
      targetPath = join(reportDir, date);
    } else {
      // 查找最新的行业报告
      const entries = await readdir(reportDir, { withFileTypes: true });
      const dirs = entries.filter(e => e.isDirectory()).map(e => e.name);

      // 优先查找 industry 目录
      if (dirs.includes('industry')) {
        targetPath = join(reportDir, 'industry');
      } else if (dirs.length > 0) {
        // 使用最新日期的目录
        dirs.sort((a, b) => b.localeCompare(a));
        targetPath = join(reportDir, dirs[0]);
      } else {
        // 没有可用目录
        return null;
      }
    }

    const files = await readdir(targetPath);
    const mdFile = files.find(f => f.endsWith('.md'));
    if (!mdFile) return null;

    const filePath = join(targetPath, mdFile);
    const content = await readFile(filePath, 'utf-8');
    return content;
  } catch (error) {
    console.error('Failed to read industry report:', error);
    return null;
  }
}

// ============================================================
// 归档时间线（archive/ 目录）
// ============================================================

/**
 * 获取归档条目
 */
export async function getArchiveEntries(): Promise<Array<{
  date: string;
  type: 'metrics' | 'events';
  description: string;
}>> {
  try {
    const archiveDir = join(DATA_DIR, '..', 'archive');

    // 检查目录是否存在
    try {
      await readdir(archiveDir);
    } catch {
      // 目录不存在，返回空数组
      return [];
    }

    const entries = await readdir(archiveDir, { withFileTypes: true });

    const items: Array<{ date: string; type: 'metrics' | 'events'; description: string }> = [];

    for (const entry of entries) {
      if (entry.isDirectory()) {
        if (entry.name.startsWith('metrics_')) {
          items.push({
            date: entry.name.replace('metrics_', ''),
            type: 'metrics',
            description: '指标归档',
          });
        } else if (entry.name.startsWith('events_')) {
          items.push({
            date: entry.name.replace('events_', ''),
            type: 'events',
            description: '事件归档',
          });
        }
      }
    }

    // 按日期降序排列
    return items.sort((a, b) => b.date.localeCompare(a.date));
  } catch (error) {
    console.error('Failed to read archive entries:', error);
    return [];
  }
}

// ============================================================
// 历史分析数据读取（data/output/history_*.csv）
// ============================================================

async function readHistoryCsv<T>(filename: string): Promise<T[]> {
  try {
    const filePath = join(OUTPUT_DIR, filename);
    const content = await readFile(filePath, 'utf-8');
    const result = Papa.parse<T>(content, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: true,
    });
    return result.data;
  } catch (error) {
    console.error(`Failed to read ${filename}:`, error);
    return [];
  }
}

export const getHistorySummary = cache(async (): Promise<HistorySummaryRow[]> => {
  return readHistoryCsv<HistorySummaryRow>('history_summary.csv');
});

export const getQuadrantStats = cache(async (): Promise<QuadrantStat[]> => {
  return readHistoryCsv<QuadrantStat>('history_quadrant_stats.csv');
});

export const getSignalLifts = cache(async (): Promise<SignalLiftRow[]> => {
  return readHistoryCsv<SignalLiftRow>('history_signal_lift.csv');
});

export const getExtremeDivergences = cache(async (): Promise<ExtremeDivergence[]> => {
  return readHistoryCsv<ExtremeDivergence>('history_extreme_divergences.csv');
});

export const getRollingMetrics = cache(async (): Promise<RollingMetricRow[]> => {
  return readHistoryCsv<RollingMetricRow>('history_rolling_metrics.csv');
});

export const getStateTransitions = cache(async (): Promise<StateTransition[]> => {
  return readHistoryCsv<StateTransition>('history_state_transitions.csv');
});

export const getEventStudy = cache(async (): Promise<EventPathRow[]> => {
  return readHistoryCsv<EventPathRow>('history_event_study.csv');
});

export const getCounterIntuitiveSignals = cache(async (): Promise<CounterIntuitiveSignal[]> => {
  return readHistoryCsv<CounterIntuitiveSignal>('history_counter_intuitive_signals.csv');
});

export const getConditionalSignalEffects = cache(async (): Promise<ConditionalSignalEffect[]> => {
  return readHistoryCsv<ConditionalSignalEffect>('history_conditional_signal_effects.csv');
});

export const getHistoryOperatorPlaybook = cache(async (): Promise<OperatorHistoryView | null> => {
  try {
    const filePath = join(OUTPUT_DIR, 'history_operator_playbook.json');
    const content = await readFile(filePath, 'utf-8');
    return JSON.parse(content) as OperatorHistoryView;
  } catch (error) {
    console.error('Failed to read history_operator_playbook.json:', error);
    return null;
  }
});
