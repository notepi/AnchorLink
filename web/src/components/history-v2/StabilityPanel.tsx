"use client";

import type { DashboardView } from '@/types/dashboard-view';
import { POOL } from '@/lib/glossary';

interface RelationshipPattern {
  relation: 'follows' | 'leads' | 'lags' | 'mean_reverts' | 'diverges' | 'unstable';
  confidence: 'high' | 'medium' | 'low';
  sampleCount: number;
  evidence: string[];
  sameDayCorr: number | null;
  anchorLeadsCorr: number | null;
  anchorLagsCorr: number | null;
  avgRelativeStrength: number | null;
  outperformRatio: number | null;
  repairAfterUnderperformRatio: number | null;
  continuationAfterOutperformRatio: number | null;
  stability: 'stable' | 'changed' | 'unstable' | 'insufficient';
}

interface RelationshipProfile {
  anchorVsChain: RelationshipPattern;
  anchorVsTheme: RelationshipPattern;
  anchorVsCore: RelationshipPattern;
  anchorVsTradingWatchlist: RelationshipPattern;
}

interface StabilityPanelProps {
  stabilityData: DashboardView['personality']['stability'];
  excessReturnData: DashboardView['trends']['excessReturn'];
  followDeviationData: DashboardView['trends']['followDeviation'];
  relationshipProfile?: RelationshipProfile;
}

function latest<T>(items: T[] | undefined): T | undefined {
  return items?.[items.length - 1];
}

function formatPct(value: number | null | undefined): string {
  return value == null || Number.isNaN(value) ? '--' : `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function getTrend(value: number | null | undefined) {
  if (value == null) return { text: '无数据', class: 'muted' };
  if (value > 2) return { text: '偏强', class: 'red' };
  if (value < -2) return { text: '偏弱', class: 'green' };
  return { text: '震荡', class: '' };
}

const RELATION_LABELS: Record<string, string> = {
  follows: '跟随',
  leads: '领先',
  lags: '滞后',
  mean_reverts: '均值回归',
  diverges: '背离',
  unstable: '不稳定',
};

const STABILITY_LABELS: Record<string, string> = {
  stable: '稳定',
  changed: '变化中',
  unstable: '不稳定',
  insufficient: '不足',
};

export default function StabilityPanel({
  stabilityData,
  excessReturnData,
  followDeviationData,
  relationshipProfile,
}: StabilityPanelProps) {
  const latestExcess = latest(excessReturnData);
  const latestDeviation = latest(followDeviationData);

  const anchorVsChain = relationshipProfile?.anchorVsChain;

  const statusMap: Record<string, { text: string; class: string }> = {
    stable: { text: '稳定', class: 'green' },
    changed: { text: '变化中', class: 'amber' },
    insufficient: { text: '样本不足', class: 'muted' }
  };

  const excess5dTrend = getTrend(latestExcess?.excess5d);
  const excess10dTrend = getTrend(latestExcess?.excess10d);
  const deviationTrend = getTrend(latestDeviation?.deviation);

  // 状态速览卡片计算
  const todayExcess = latestDeviation?.excess;
  const isOutperform = todayExcess != null && todayExcess > 0;
  const todayDeviationAbs = todayExcess != null ? Math.abs(todayExcess) : null;
  const isAbnormal = todayDeviationAbs != null && todayDeviationAbs > 1;
  const streak = latestExcess?.outperformStreak ?? 0;

  // 操作提示逻辑
  const generateActionTip = () => {
    const tips: string[] = [];

    if (streak <= -3) {
      tips.push(`连输 ${Math.abs(streak)} 天，历史数据显示跑输后次日修复概率 ${((anchorVsChain?.repairAfterUnderperformRatio ?? 0.5) * 100).toFixed(1)}%，建议关注反弹机会`);
    } else if (streak >= 3) {
      tips.push(`连胜 ${streak} 天，注意均值回归风险，跑赢后延续概率仅 ${((anchorVsChain?.continuationAfterOutperformRatio ?? 0.45) * 100).toFixed(1)}%`);
    }

    if (isAbnormal && todayExcess != null) {
      tips.push(`今日偏离 ${formatPct(todayExcess)} 属于异常波动，需关注是否有独立利好/利空`);
    }

    if (anchorVsChain?.stability === 'unstable') {
      tips.push('关系模式不稳定，历史规律参考价值降低');
    }

    const corr = anchorVsChain?.sameDayCorr;
    if (corr != null) {
      if (corr > 0.7) {
        tips.push(`相关系数 ${corr.toFixed(2)}，高度跟随池子，池子方向是核心参考`);
      } else if (corr < 0.4) {
        tips.push(`相关系数 ${corr.toFixed(2)}，个股独立性较强，需更多关注个股自身逻辑`);
      }
    }

    return tips;
  };

  const actionTips = generateActionTip();

  return (
    <details className="collapsible-section" open>
      <summary>
        <div className="section-title-wrap">
          <h2 className="section-title">近期稳定性</h2>
          <p className="section-note" style={{ marginTop: '6px' }}>不用读每个波峰波谷，只看判断是否连续跑赢{POOL.industry_chain.short}，以及今天是不是异常偏离。</p>
        </div>
        <span className="section-meta">稳定性{statusMap[stabilityData?.status]?.text ?? '未知'}</span>
      </summary>

      {/* 状态速览卡片 */}
      <div className="status-cards">
        <div className={`status-card ${isOutperform ? 'green' : 'red'}`}>
          <div className="status-card-label">跑赢状态</div>
          <div className="status-card-value">{isOutperform ? '跑赢' : '跑输'}</div>
          <div className="status-card-detail">今日 {formatPct(todayExcess)}</div>
        </div>
        <div className="status-card">
          <div className="status-card-label">关系类型</div>
          <div className="status-card-value">{RELATION_LABELS[anchorVsChain?.relation ?? 'unstable'] ?? '未知'}</div>
          <div className="status-card-detail">相关 {anchorVsChain?.sameDayCorr?.toFixed(2) ?? '--'}</div>
        </div>
        <div className={`status-card ${isAbnormal ? 'amber' : ''}`}>
          <div className="status-card-label">异常程度</div>
          <div className="status-card-value">{isAbnormal ? '异常' : '正常'}</div>
          <div className="status-card-detail">偏离 ±{todayDeviationAbs?.toFixed(2) ?? '--'}%</div>
        </div>
        <div className={`status-card ${streak >= 3 ? 'green' : streak <= -3 ? 'red' : ''}`}>
          <div className="status-card-label">连胜连败</div>
          <div className="status-card-value">{streak > 0 ? `连胜 ${streak} 天` : streak < 0 ? `连输 ${Math.abs(streak)} 天` : '无连胜'}</div>
          <div className="status-card-detail">近10日 {formatPct(latestExcess?.excess10d)}</div>
        </div>
      </div>

      {/* 操作提示 */}
      {actionTips.length > 0 && (
        <div className="action-tips">
          <h3>操作提示</h3>
          <ul>
            {actionTips.map((tip, i) => (
              <li key={i}>{tip}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="stability-summary">
        <div className="stability-verdict">
          <h3>当前结论</h3>
          <p>
            稳定性{statusMap[stabilityData?.status]?.text ?? '未知'}：
            {stabilityData?.earlyVsRecentNotes?.[0] ??
              '近 5/10 日超额没有持续抬升，今天仍更像跟随主线波动，而不是独立走强。'}
          </p>
        </div>
        <div className="stability-metric">
          <h3>5日超额</h3>
          <div className={`value ${excess5dTrend.class}`}>{excess5dTrend.text}</div>
          <p>当前值：{formatPct(latestExcess?.excess5d)}</p>
        </div>
        <div className="stability-metric">
          <h3>10日超额</h3>
          <div className={`value ${excess10dTrend.class}`}>{excess10dTrend.text}</div>
          <p>当前值：{formatPct(latestExcess?.excess10d)}</p>
        </div>
        <div className="stability-metric">
          <h3>今日偏离</h3>
          <div className={`value ${deviationTrend.class}`}>{deviationTrend.text}</div>
          <p>当前值：{formatPct(latestDeviation?.deviation)}</p>
        </div>
      </div>
    </details>
  );
}
