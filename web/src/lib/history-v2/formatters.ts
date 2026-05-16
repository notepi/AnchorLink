/**
 * 历史v2页面格式化工具函数
 * 所有格式化逻辑完全对齐旧历史页面的显示规则
 */

/**
 * 日期格式化
 * @param value 原始日期字符串，格式为YYYYMMDD
 * @param format 目标格式：'YYYY-MM-DD' | 'YYYYMMDD' | 'MM/DD'
 * @returns 格式化后的日期字符串
 */
export function formatDate(value: string | number | null | undefined, format: 'YYYY-MM-DD' | 'YYYYMMDD' | 'MM/DD' = 'YYYY-MM-DD'): string {
  const text = value == null ? '' : String(value);
  if (!text || text.length !== 8) return text;

  const year = text.slice(0, 4);
  const month = text.slice(4, 6);
  const day = text.slice(6, 8);

  switch (format) {
    case 'YYYY-MM-DD':
      return `${year}-${month}-${day}`;
    case 'MM/DD':
      return `${month}/${day}`;
    case 'YYYYMMDD':
    default:
      return text;
  }
}

/**
 * 百分比格式化
 * @param value 原始数值
 * @param decimals 保留小数位数，默认2位
 * @param showSign 是否显示+/-号，默认true
 * @param showPercent 是否显示%号，默认true
 * @returns 格式化后的百分比字符串
 */
export function formatPercent(
  value: number | null | undefined,
  decimals: number = 2,
  showSign: boolean = true,
  showPercent: boolean = true
): string {
  if (value === null || value === undefined || isNaN(value)) return '--';

  const formatted = value.toFixed(decimals);
  const sign = showSign ? (value > 0 ? '+' : value < 0 ? '-' : '') : '';
  const percent = showPercent ? '%' : '';

  return `${sign}${Math.abs(Number(formatted))}${percent}`;
}

/**
 * 百分点（pp）格式化
 * @param value 原始数值
 * @param decimals 保留小数位数，默认2位
 * @param showSign 是否显示+/-号，默认true
 * @returns 格式化后的pp字符串
 */
export function formatPp(
  value: number | null | undefined,
  decimals: number = 2,
  showSign: boolean = true
): string {
  if (value === null || value === undefined || isNaN(value)) return '--';

  const formatted = value.toFixed(decimals);
  const sign = showSign ? (value > 0 ? '+' : value < 0 ? '-' : '') : '';

  return `${sign}${Math.abs(Number(formatted))}pp`;
}

/**
 * 数值格式化（千分位）
 * @param value 原始数值
 * @param decimals 保留小数位数，默认0位
 * @returns 格式化后的数值字符串
 */
export function formatNumber(value: number | null | undefined, decimals: number = 0): string {
  if (value === null || value === undefined || isNaN(value)) return '--';

  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

/**
 * 胜率格式化
 * @param value 原始胜率值，0~1之间
 * @param decimals 保留小数位数，默认0位
 * @returns 格式化后的胜率字符串，带%号
 */
export function formatWinRate(value: number | null | undefined, decimals: number = 0): string {
  if (value === null || value === undefined || isNaN(value)) return '--%';

  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * 置信度映射为中文
 * @param value 原始置信度值：'high' | 'medium' | 'low'
 * @returns 中文显示文本
 */
export function formatConfidence(value: string | null | undefined): string {
  if (!value) return '--';

  const map: Record<string, string> = {
    high: '高',
    medium: '中',
    low: '低'
  };

  return map[value] || value;
}

/**
 * 路径标签映射为中文和对应颜色
 * @param value 原始路径标签值
 * @returns 包含文本和颜色类的对象
 */
export function formatPathLabel(value: string | null | undefined): { text: string; class: string } {
  if (!value) return { text: '未知', class: '' };

  const map: Record<string, { text: string; class: string }> = {
    strong_rise: { text: '强势延续', class: '' },
    pullback_after_rise: { text: '冲高回落', class: '' },
    continue_fall: { text: '继续走弱', class: '' },
    weak_repair: { text: '弱势修复', class: '' },
    range_bound: { text: '区间震荡', class: '' },
    disagreement: { text: '样本分歧', class: '' },
    unknown: { text: '未知', class: '' },
    强势延续: { text: '强势延续', class: '' },
    冲高回落: { text: '冲高回落', class: '' },
    继续走弱: { text: '继续走弱', class: '' },
    弱势修复: { text: '弱势修复', class: '' },
    分化震荡: { text: '分化震荡', class: '' },
    样本分歧: { text: '样本分歧', class: '' },
    未知: { text: '未知', class: '' }
  };

  return map[value] || { text: value, class: '' };
}

/**
 * 信号类型对应的badge样式
 * @param type 信号类型：'pref' | 'avoid' | 'contra' | 'trap' | 'beta' | 'alpha' | 'risk'
 * @returns 样式类名
 */
export function formatSignalBadge(type: string | null | undefined): string {
  if (!type) return 'muted';

  const map: Record<string, string> = {
    pref: 'badge red',
    avoid: 'badge green',
    contra: 'badge purple',
    trap: 'badge amber',
    beta: 'badge blue',
    alpha: 'badge blue',
    risk: 'badge blue'
  };

  return map[type] || 'muted';
}

/**
 * 显著性标签格式化
 * @param value 显著性值：'strong' | 'suggestive' | 'weak' | 'insufficient'
 * @returns 中文标签和样式类
 */
export function formatSignificance(value: string | null | undefined): { text: string; class: string } {
  if (!value) return { text: '-', class: 'muted' };

  const map: Record<string, { text: string; class: string }> = {
    strong: { text: '强', class: 'badge red' },
    suggestive: { text: '提示', class: 'badge amber' },
    weak: { text: '弱', class: 'badge blue' },
    insufficient: { text: '不足', class: 'muted' }
  };

  return map[value] || { text: value, class: 'muted' };
}

/**
 * 星级评分格式化
 * @param value 星级值 1-5
 * @returns 星级字符串，如★★★☆☆
 */
export function formatStars(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value) || value < 1 || value > 5) return '★☆☆☆☆';

  const fullStars = Math.floor(value);
  const emptyStars = 5 - fullStars;

  return '★'.repeat(fullStars) + '☆'.repeat(emptyStars);
}

/**
 * 联动关系类型格式化
 * @param value 关系类型：'follows' | 'leads' | 'lags' | 'mean_reverts' | 'diverges' | 'unstable'
 * @returns 中文显示文本
 */
export function formatRelationType(value: string | null | undefined): string {
  if (!value) return '--';

  const map: Record<string, string> = {
    follows: '跟随',
    leads: '领先',
    lags: '滞后',
    mean_reverts: '均值回归',
    diverges: '独立',
    unstable: '不稳定'
  };

  return map[value] || value;
}

/**
 * 象限状态名称格式化，简化显示
 * @param value 完整象限名称，如'行业强+个股强'
 * @param short 是否显示简化版本，如'强+强'，默认true
 * @returns 格式化后的象限名称
 */
export function formatQuadrantName(value: string | null | undefined, short: boolean = true): string {
  if (!value) return '--';

  if (!short) return value;

  // 简化规则："行业X+个股Y" → "X+Y"
  return value.replace(/行业([强中弱])\+个股([强中弱])/, '$1+$2');
}

/**
 * 数值对应的颜色类
 * @param value 数值
 * @param zeroIsGray 零值是否显示灰色，默认true
 * @returns 颜色类名：text-red-500 / text-green-500 / text-gray-500
 */
export function getValueColorClass(value: number | null | undefined, zeroIsGray: boolean = true): string {
  if (value === null || value === undefined || isNaN(value)) return 'muted';

  if (value > 0) return 'red';
  if (value < 0) return 'green';
  return zeroIsGray ? 'muted' : 'text-2';
}

/**
 * 格式化信号标签，截断过长的文本
 * @param value 原始信号标签
 * @param maxLength 最大长度，默认20
 * @returns 截断后的标签，超过部分用...表示
 */
export function formatSignalLabel(value: string | null | undefined, maxLength: number = 20): string {
  if (!value) return '--';

  if (value.length <= maxLength) return value;

  return value.slice(0, maxLength) + '...';
}

/**
 * 格式化样本量显示
 * @param count 样本数量
 * @returns 格式化后的样本量文本，如「n=12」
 */
export function formatSampleCount(count: number | null | undefined): string {
  if (count === null || count === undefined || isNaN(count)) return 'n=--';

  return `n=${count}`;
}

/**
 * 格式化相似度显示
 * @param value 相似度值 0~1
 * @param decimals 保留小数位数，默认2位
 * @returns 格式化后的相似度文本，如「相似度 0.92」
 */
export function formatSimilarity(value: number | null | undefined, decimals: number = 2): string {
  if (value === null || value === undefined || isNaN(value)) return '相似度 --';

  return `相似度 ${value.toFixed(decimals)}`;
}
