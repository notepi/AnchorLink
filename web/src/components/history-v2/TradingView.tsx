import type { DashboardView } from '@/types/dashboard-view';
import { formatPercent, formatPp, formatNumber, formatConfidence } from '@/lib/history-v2/formatters';
import { CONFIDENCE_LABEL } from '@/lib/glossary';

interface TradingViewProps {
  cards: DashboardView['cards'];
  advice: DashboardView['aiInsight']['advice'];
}

// Badge值映射：英文→中文（复用 glossary 置信度标签）
const badgeMap: Record<string, string> = { ...CONFIDENCE_LABEL };

// 格式化卡片值
const formatCardValue = (card?: DashboardView['cards'][number]) => {
  if (!card) return '--';
  // 特殊字段处理
  if (card.label === '置信度' || card.title === '历史规律可信度') {
    return formatConfidence(card.value as string);
  }
  if (card.label === '胜率') {
    return formatPercent(card.value as number, 0, false);
  }
  if (card.label === 'T+3 超额' || card.label === 'T+3 不利') {
    return formatPp(card.value as number);
  }
  if (card.label === '盈亏比' || card.label === '夏普') {
    return formatNumber(card.value as number, 2);
  }
  if (card.label === '信号覆盖') {
    return formatPercent(card.value as number, 0, false);
  }
  // 其他情况直接返回
  return card.value ?? '--';
};

export default function TradingView({ cards, advice }: TradingViewProps) {
  return (
    <details className="collapsible-section" open>
      <summary>
        <div className="section-title-wrap">
          <h2 className="section-title">今日操盘视图</h2>
          <p className="section-note" style={{ marginTop: '6px' }}>保留现有判断卡结构，只把它放到页面主线最前面。</p>
        </div>
        <span className="section-meta">{cards?.length ?? 0} 项指标</span>
      </summary>

      <div className="grid-3">
        {cards?.slice?.(0, 3)?.map?.((card, index) => (
          <div key={index} className="card">
            <div className="card-title">{card?.title || card?.label || ''}</div>
            <div className="card-value-row">
              <div className="big">{formatCardValue(card)}</div>
              {card?.badge && <span className={`badge ${card.badge === 'stable' ? 'red' : card.badge === 'high' ? 'green' : 'blue'}`}>{badgeMap[card.badge] || card.badge}</span>}
            </div>
            <div className="text-2">{card?.description || '暂无描述'}</div>
          </div>
        )) ?? null}
      </div>

      <div className="advice">
        <div className="advice-item">
          <h3>看什么</h3>
          <p>{advice?.watch ?? '暂无数据'}</p>
        </div>
        <div className="advice-item">
          <h3>用什么确认</h3>
          <p>{advice?.confirm ?? '暂无数据'}</p>
        </div>
        <div className="advice-item">
          <h3>什么会失效</h3>
          <p>{advice?.failure ?? '暂无数据'}</p>
        </div>
        <div className="advice-item">
          <h3>样本约束</h3>
          <p>{advice?.constraint ?? '暂无约束'}</p>
        </div>
      </div>
    </details>
  );
}
