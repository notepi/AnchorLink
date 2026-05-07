import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * 合并 Tailwind 类名（避免冲突）
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * 判断涨跌状态
 */
export function getPctStatus(value: number | null | undefined): 'positive' | 'negative' | 'neutral' {
  if (value === null || value === undefined) return 'neutral';
  if (value > 0.01) return 'positive';  // 涨幅 > 0.01%
  if (value < -0.01) return 'negative'; // 跌幅 < -0.01%
  return 'neutral';
}

/**
 * 获取涨跌颜色类名
 */
export function getPctColorClass(value: number | null | undefined): string {
  const status = getPctStatus(value);
  switch (status) {
    case 'positive':
      return 'text-anchor-positive';
    case 'negative':
      return 'text-anchor-negative';
    default:
      return 'text-anchor-textSecondary';
  }
}

/**
 * 获取置信度颜色类名
 */
export function getConfidenceColorClass(confidence: 'high' | 'medium' | 'low'): string {
  switch (confidence) {
    case 'high':
      return 'text-anchor-positive';
    case 'medium':
      return 'text-anchor-accent'; // 使用 accent 色代替橙色
    case 'low':
      return 'text-anchor-textMuted';
  }
}

/**
 * 获取信号类别颜色类名
 */
export function getSignalCategoryColorClass(category: 'beta' | 'alpha' | 'volume' | 'rotation' | 'abnormal'): string {
  switch (category) {
    case 'beta':
      return 'text-signal-beta';
    case 'alpha':
      return 'text-signal-alpha';
    case 'volume':
      return 'text-signal-volume';
    case 'rotation':
      return 'text-signal-rotation';
    case 'abnormal':
      return 'text-signal-abnormal';
  }
}

/**
 * 获取 Beta/Alpha 状态颜色类名
 */
export function getBetaAlphaColorClass(status: 'positive' | 'neutral' | 'negative'): string {
  switch (status) {
    case 'positive':
      return 'text-anchor-positive';
    case 'negative':
      return 'text-anchor-negative';
    default:
      return 'text-anchor-textSecondary';
  }
}

/**
 * 获取风险等级颜色类名
 */
export function getRiskColorClass(level: 'low' | 'medium' | 'high'): string {
  switch (level) {
    case 'low':
      return 'text-anchor-positive';
    case 'medium':
      return 'text-anchor-accent';
    case 'high':
      return 'text-anchor-negative';
  }
}

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
 * 格式化排名（分位数显示）
 */
export function formatRank(rank: number | null | undefined, total: number | null | undefined): string {
  if (rank === null || rank === undefined || total === null || total === undefined) return '--';
  return `${rank}/${total}`;
}

/**
 * 获取池子显示名称
 */
export function getPoolDisplayName(universeId: string): string {
  const poolNames: Record<string, string> = {
    direct_peers: '核心同类',
    industry_chain: '产业链',
    theme_pool: '主题情绪',
    trading_watchlist: '交易观察',
  };
  return poolNames[universeId] || universeId;
}

/**
 * 获取池子简称（用于仪表盘卡片）
 * 与显示名称保持一致
 */
export function getPoolShortName(universeId: string): string {
  return getPoolDisplayName(universeId);
}