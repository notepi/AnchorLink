// ============================================================
// AnchorLink 术语表 — 展示文本的 single source of truth
// 修改术语前先更新 docs/glossary.md，再同步到本文件
// ============================================================

import type { PoolType } from '@/types';

// ── 池名称 ──

export const POOL: Record<PoolType, { short: string; full: string }> = {
  direct_peers:       { short: '增材确认池',  full: '增材制造本业确认池' },
  industry_chain:     { short: '航天主池',    full: '商业航天硬科技产业链主池' },
  theme_pool:         { short: '航天主题池',  full: '商业航天主题情绪池' },
  trading_watchlist:  { short: '交易观察池',  full: '交易联动与风险映射池' },
} as const;

// ── 状态标签 ──

export const BETA_LABEL: Record<string, string> = {
  positive: '产业链强',
  neutral:  '产业链中',
  negative: '产业链弱',
} as const;

export const ALPHA_LABEL: Record<string, string> = {
  positive: '个股强',
  neutral:  '个股中',
  negative: '个股弱',
} as const;

export const RISK_LABEL: Record<string, string> = {
  low:    '低风险',
  medium: '中风险',
  high:   '高风险',
} as const;

// ── 路径标签 ──

export const PATH_LABEL: Record<string, string> = {
  strong_rise:         '强势延续',
  pullback_after_rise: '冲高回落',
  continue_fall:       '继续走弱',
  weak_repair:         '弱势修复',
  range_bound:         '分化震荡',
  disagreement:        '样本分歧',
  // 中文 key 兼容（后端可能输出中文）
  强势延续: '强势延续',
  冲高回落: '冲高回落',
  继续走弱: '继续走弱',
  弱势修复: '弱势修复',
  分化震荡: '分化震荡',
  样本分歧: '样本分歧',
} as const;

// ── 联动关系 ──

export const RELATION_LABEL: Record<string, string> = {
  strong_follow: '强跟随',
  weak_follow:   '弱跟随',
  independent:   '独立',
  inverse:       '反向',
} as const;

// ── 置信度 / badge ──

export const CONFIDENCE_LABEL: Record<string, string> = {
  high:          '高',
  medium:        '中',
  low:           '低',
  stable:        '稳定',
  deteriorating: '下降',
  concerning:    '警告',
  insufficient:  '不足',
} as const;

// ── 信号类别 ──

export const SIGNAL_CATEGORY: Record<string, string> = {
  all:                '全部',
  preference:         '偏好环境',
  avoid:              '规避环境',
  counter_intuitive:  '反直觉机会',
  trap:               '信号陷阱',
} as const;
