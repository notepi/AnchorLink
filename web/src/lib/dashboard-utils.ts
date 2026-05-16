/**
 * 数据格式化工具函数
 */

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
 * 格式化星标等级
 */
export function formatStarLevel(level: number | null | undefined): string {
  if (level === null || level === undefined) return '';
  return '⭐'.repeat(level);
}
