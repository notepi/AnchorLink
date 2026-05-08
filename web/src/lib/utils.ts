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
      return 'text-anchor-positive'; // 红色
    case 'medium':
      return 'text-anchor-accent';   // accent色
    case 'low':
      return 'text-anchor-negative'; // 绿色
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
 * 获取信号本身的颜色类名（根据利好/利空含义）
 * 红色 = 利好信号，灰色 = 中性信号，绿色 = 利空信号
 */
export function getSignalColorClass(label: string): string {
  const signalColors: Record<string, string> = {
    // 利好信号 - 红色
    '行业Beta为正': 'text-anchor-positive',
    '行业扩散增强': 'text-anchor-positive',
    '个股Alpha为正': 'text-anchor-positive',
    '跑赢主线池': 'text-anchor-positive',
    '处于行业前排': 'text-anchor-positive',
    '资金价格共振': 'text-anchor-positive',
    '主力资金领先': 'text-anchor-positive',
    '放量上涨': 'text-anchor-positive',
    '缩量下跌': 'text-anchor-positive', // 缩量下跌可能是洗盘
    // 中性信号 - 灰色
    '交易观察池升温': 'text-anchor-textSecondary',
    '板块轻微轮动': 'text-anchor-textSecondary',
    // 利空信号 - 绿色
    '行业Beta为负': 'text-anchor-negative',
    '行业扩散不足': 'text-anchor-negative',
    '个股Alpha为负': 'text-anchor-negative',
    '跑输主线池': 'text-anchor-negative',
    '处于行业后排': 'text-anchor-negative',
    '主力资金拖累': 'text-anchor-negative',
  };
  return signalColors[label] || 'text-anchor-textSecondary';
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
 * 计算置信度边际比率
 * margin_ratio = (value - threshold) / abs(threshold)
 */
export function calculateMarginRatio(value: number, threshold: number): number {
  if (threshold === 0) return value > 0 ? Infinity : 0;
  return (value - threshold) / Math.abs(threshold);
}

/**
 * 格式化置信度展示（量化边际比率）
 */
export function formatConfidenceQuantified(
  value: number,
  threshold: number,
  confidence: 'high' | 'medium' | 'low',
  percentile?: number
): string {
  // 排名类信号显示分位
  if (percentile !== undefined) {
    const percentileStr = `${percentile.toFixed(0)}%分位`;
    return `${percentileStr} [${confidence}]`;
  }

  // 数值类信号显示边际比率
  const marginRatio = calculateMarginRatio(value, threshold);
  const ratioStr = marginRatio >= 10
    ? `${marginRatio.toFixed(0)}倍`
    : marginRatio >= 1
      ? `${marginRatio.toFixed(1)}倍`
      : `${marginRatio.toFixed(2)}倍`;

  return `超阈值${ratioStr} [${confidence}]`;
}

/**
 * 获取置信度量化颜色类名（基于边际比率）
 */
export function getConfidenceQuantifiedColorClass(
  value: number,
  threshold: number,
  percentile?: number
): string {
  // 排名类信号：分位越小越强
  if (percentile !== undefined) {
    if (percentile <= 15) return 'text-anchor-positive';  // 高置信
    if (percentile <= 30) return 'text-anchor-accent';    // 中等
    return 'text-anchor-textSecondary';                   // 低置信
  }

  // 数值类信号：边际比率越大越强
  const marginRatio = calculateMarginRatio(value, threshold);
  if (marginRatio >= 2.0) return 'text-anchor-positive';  // 高置信
  if (marginRatio >= 1.0) return 'text-anchor-accent';    // 中等
  return 'text-anchor-textSecondary';                     // 低置信
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