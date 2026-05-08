/**
 * 信号组合解读逻辑
 * 判断共振/背离组合，生成投研师决策支撑信息
 */

import { Signal, GroupRotation } from '@/types';

// 业务常量阈值
const THEME_STRONGER_THRESHOLD = -0.5; // 主题池相对主线池涨幅差超过 0.5% 视为情绪炒作信号
const TRADING_WARM_THRESHOLD = 0.5;    // 交易观察池涨幅超过 0.5% 视为升温

// 组合解读结果
export interface SignalInterpretation {
  resonances: ResonancePattern[];
  divergences: DivergencePattern[];
  riskLevel: 'low' | 'medium' | 'high';
  riskReason: string;
  summary: string;
}

// 共振模式
export interface ResonancePattern {
  pattern: string;
  signals: string[];
  interpretation: string;
  suggestion: string;
}

// 背离模式
export interface DivergencePattern {
  pattern: string;
  signals: string[];
  interpretation: string;
  suggestion: string;
}

/**
 * 判断信号组合解读
 */
export function interpretSignals(
  signals: Signal[],
  groupRotation?: GroupRotation | null
): SignalInterpretation {
  const resonances: ResonancePattern[] = [];
  const divergences: DivergencePattern[] = [];

  // 提取各类信号
  const betaSignals = signals.filter(s => s.category === 'beta');
  const alphaSignals = signals.filter(s => s.category === 'alpha');
  const volumeSignals = signals.filter(s => s.category === 'volume');
  const rotationSignals = signals.filter(s => s.category === 'rotation');
  const abnormalSignals = signals.filter(s => s.category === 'abnormal');

  // 判断 Beta 和 Alpha 状态
  const betaPositive = betaSignals.some(s => s.label.includes('Beta为正') || s.label.includes('扩散增强'));
  const alphaPositive = alphaSignals.some(s => s.label.includes('Alpha为正') || s.label.includes('跑赢'));
  const volumePositive = volumeSignals.some(s => s.label.includes('共振') || s.label.includes('资金领先'));

  // 共振模式判断
  if (betaPositive && alphaPositive && volumePositive) {
    resonances.push({
      pattern: '强势共振',
      signals: ['行业Beta为正', '个股Alpha为正', '资金共振'],
      interpretation: '行业个股资金三重共振，趋势强势确认',
      suggestion: '可考虑顺势加仓',
    });
  }

  if (betaPositive && betaSignals.some(s => s.label.includes('扩散增强')) && alphaSignals.some(s => s.label.includes('前排'))) {
    resonances.push({
      pattern: '趋势确认',
      signals: ['行业Beta为正', '行业扩散增强', '处于行业前排'],
      interpretation: '行业趋势明确且个股处于前排',
      suggestion: '顺势操作，坚守主线',
    });
  }

  if (alphaPositive && volumePositive) {
    resonances.push({
      pattern: '资金确认',
      signals: ['个股Alpha为正', '资金共振'],
      interpretation: '个股强势且资金认可',
      suggestion: '可跟随主力资金',
    });
  }

  // 背离模式判断
  if (betaPositive && !alphaPositive) {
    divergences.push({
      pattern: '个股背离',
      signals: ['行业Beta为正', '个股Alpha为负'],
      interpretation: '行业上涨但个股跑输',
      suggestion: '需警惕个股风险，检查基本面',
    });
  }

  if (!betaPositive && alphaPositive) {
    divergences.push({
      pattern: '逆势上涨',
      signals: ['行业Beta为负', '个股Alpha为正'],
      interpretation: '行业下跌但个股上涨',
      suggestion: '需警惕补跌风险',
    });
  }

  if (!volumePositive && alphaPositive) {
    divergences.push({
      pattern: '资金背离',
      signals: ['个股Alpha为正', '资金流出'],
      interpretation: '个股上涨但资金流出',
      suggestion: '需警惕资金撤离风险',
    });
  }

  // 轮动模式判断（基于 group_rotation）
  if (groupRotation) {
    const themeStronger = groupRotation.core_vs_theme_spread !== null &&
                          groupRotation.core_vs_theme_spread < THEME_STRONGER_THRESHOLD;
    const tradingWarming = rotationSignals.some(s => s.label.includes('交易观察池升温'));

    if (themeStronger && tradingWarming) {
      divergences.push({
        pattern: '情绪炒作',
        signals: ['主题池强于主线池', '交易观察池升温'],
        interpretation: '资金转向情绪池，主线逻辑松动',
        suggestion: '警惕主线松动，关注短线机会',
      });
    }

    if (!themeStronger && betaPositive) {
      resonances.push({
        pattern: '主线清晰',
        signals: ['产业链强于主题池', '行业Beta为正'],
        interpretation: '产业链领涨且行业上涨，主线逻辑清晰',
        suggestion: '可坚守主线逻辑',
      });
    }
  }

  // 风险等级判断
  let riskLevel: 'low' | 'medium' | 'high' = 'low';
  let riskReason = '';

  if (abnormalSignals.length >= 2) {
    riskLevel = 'high';
    riskReason = `发现${abnormalSignals.length}个异常信号：${abnormalSignals.map(s => s.label).join('、')}`;
  } else if (abnormalSignals.length === 1) {
    riskLevel = 'medium';
    riskReason = `发现1个异常信号：${abnormalSignals[0].label}`;
  } else if (divergences.length >= 2) {
    riskLevel = 'medium';
    riskReason = `发现${divergences.length}个背离组合：${divergences.map(d => d.pattern).join('、')}`;
  } else if (divergences.length === 1) {
    riskLevel = 'medium';
    riskReason = divergences[0].interpretation;
  } else {
    riskLevel = 'low';
    riskReason = resonances.length > 0
      ? '信号整体利好，无异常背离'
      : '信号整体中性';
  }

  // 生成摘要
  let summary = '';
  if (resonances.length > 0) {
    summary = `${resonances[0].pattern}：${resonances[0].interpretation}`;
  } else if (divergences.length > 0) {
    summary = `${divergences[0].pattern}：${divergences[0].interpretation}`;
  } else {
    summary = '信号整体中性，无明显共振或背离';
  }

  return {
    resonances,
    divergences,
    riskLevel,
    riskReason,
    summary,
  };
}

/**
 * 获取风险等级颜色类名
 */
export function getRiskLevelColorClass(level: 'low' | 'medium' | 'high'): string {
  switch (level) {
    case 'high':
      return 'text-anchor-negative';
    case 'medium':
      return 'text-anchor-accent';
    case 'low':
      return 'text-anchor-positive';
  }
}

/**
 * 获取风险等级标签
 */
export function getRiskLevelLabel(level: 'low' | 'medium' | 'high'): string {
  switch (level) {
    case 'high':
      return '高风险';
    case 'medium':
      return '中等风险';
    case 'low':
      return '低风险';
  }
}