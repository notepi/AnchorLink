import type { DashboardView } from '@/types/dashboard-view';

interface StabilityPanelProps {
  stabilityData: DashboardView['personality']['stability'];
  excessReturnData: DashboardView['trends']['excessReturn'];
  followDeviationData: DashboardView['trends']['followDeviation'];
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

function linePoints<T>(
  data: T[] | undefined,
  key: keyof T,
  boundsKeys: Array<keyof T>,
  width = 720,
  height = 230
): string {
  if (!data?.length) return '';
  const values: number[] = [];
  data.forEach((row) => {
    boundsKeys.forEach((boundKey) => {
      const value = row[boundKey];
      if (typeof value === 'number' && Number.isFinite(value)) {
        values.push(value);
      }
    });
  });
  if (!values.length) return '';

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const left = 8;
  const right = width - 8;
  const top = 28;
  const bottom = height - 28;
  const denominator = Math.max(data.length - 1, 1);

  return data.map((row, index) => {
    const value = typeof row[key] === 'number' ? row[key] as number : 0;
    const x = left + (index / denominator) * (right - left);
    const y = bottom - ((value - min) / range) * (bottom - top);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
}

export default function StabilityPanel({
  stabilityData,
  excessReturnData,
  followDeviationData
}: StabilityPanelProps) {
  const latestExcess = latest(excessReturnData);
  const latestDeviation = latest(followDeviationData);

  const statusMap: Record<string, { text: string; class: string }> = {
    stable: { text: '稳定', class: 'green' },
    changed: { text: '变化中', class: 'amber' },
    insufficient: { text: '样本不足', class: 'muted' }
  };

  const excess5dTrend = getTrend(latestExcess?.excess5d);
  const excess10dTrend = getTrend(latestExcess?.excess10d);
  const deviationTrend = getTrend(latestDeviation?.deviation);

  const excessBounds = ['excess5d', 'excess10d', 'outperformStreak'] as const;
  const deviationBounds = ['anchor', 'industry', 'excess'] as const;

  return (
    <section className="section">
      <div className="section-head">
        <h2 className="section-title">近期稳定性</h2>
        <p className="section-note">不用读每个波峰波谷，只看判断是否连续跑赢主线池，以及今天是不是异常偏离。</p>
      </div>
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
      <div className="grid-2">
        <div className="chart-card">
          <div className="chart-title"><span>是否持续跑赢主线池</span><span className="muted">滚动 5/10 日</span></div>
          <svg className="chart" viewBox="0 0 720 230" role="img" aria-label="滚动超额与连胜">
            <defs>
              <pattern id="grid-a" width="72" height="46" patternUnits="userSpaceOnUse">
                <path d="M 72 0 L 0 0 0 46" fill="none" stroke="#252525" strokeWidth="1" strokeDasharray="3 4"/>
              </pattern>
            </defs>
            <rect width="720" height="230" fill="url(#grid-a)" />
            <line x1="0" y1="115" x2="720" y2="115" stroke="#333" />
            <polyline points={linePoints(excessReturnData, 'excess10d', [...excessBounds])} fill="none" stroke="#8b5cf6" strokeWidth="2" strokeDasharray="5 4"/>
            <polyline points={linePoints(excessReturnData, 'excess5d', [...excessBounds])} fill="none" stroke="#3b82f6" strokeWidth="2"/>
            <polyline points={linePoints(excessReturnData, 'outperformStreak', [...excessBounds])} fill="none" stroke="#ff4d4f" strokeWidth="2"/>
          </svg>
          <div className="legend"><span><i style={{ background: '#8b5cf6' }}></i>10日超额</span><span><i style={{ background: '#3b82f6' }}></i>5日超额</span><span><i style={{ background: '#ff4d4f' }}></i>超额连胜</span></div>
          <div className="chart-note"><strong>读法：</strong>蓝/紫线持续在中线以上才算稳定跑赢；红线代表跑赢是否连续。最新 5 日超额 {formatPct(latestExcess?.excess5d)}，10 日超额 {formatPct(latestExcess?.excess10d)}。</div>
        </div>

        <div className="chart-card">
          <div className="chart-title"><span>今天是跟随还是偏离</span><span className="muted">个股 / 主线池 / 超额</span></div>
          <svg className="chart" viewBox="0 0 720 230" role="img" aria-label="当日收益与超额">
            <defs>
              <pattern id="grid-b" width="72" height="46" patternUnits="userSpaceOnUse">
                <path d="M 72 0 L 0 0 0 46" fill="none" stroke="#252525" strokeWidth="1" strokeDasharray="3 4"/>
              </pattern>
            </defs>
            <rect width="720" height="230" fill="url(#grid-b)" />
            <line x1="0" y1="115" x2="720" y2="115" stroke="#333" />
            <polyline points={linePoints(followDeviationData, 'anchor', [...deviationBounds])} fill="none" stroke="#ff4d4f" strokeWidth="2.2"/>
            <polyline points={linePoints(followDeviationData, 'industry', [...deviationBounds])} fill="none" stroke="#3b82f6" strokeWidth="1.8" strokeDasharray="5 4"/>
            <polyline points={linePoints(followDeviationData, 'excess', [...deviationBounds])} fill="none" stroke="#8b5cf6" strokeWidth="2"/>
          </svg>
          <div className="legend"><span><i style={{ background: '#ff4d4f' }}></i>个股收益</span><span><i style={{ background: '#3b82f6' }}></i>主线池中位数</span><span><i style={{ background: '#8b5cf6' }}></i>当日超额</span></div>
          <div className="chart-note"><strong>读法：</strong>红线贴近蓝线说明个股主要跟随主线池；紫线离中线越远，说明当天偏离越大。最新当日超额 {formatPct(latestDeviation?.excess)}。</div>
        </div>
      </div>
    </section>
  );
}
