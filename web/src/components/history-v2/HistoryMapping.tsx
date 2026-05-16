import type { DashboardView } from '@/types/dashboard-view';
import { formatPercent, formatWinRate, formatSimilarity, getValueColorClass, formatPathLabel } from '@/lib/history-v2/formatters';

interface HistoryMappingProps {
  currentMapping: DashboardView['summary']['currentMapping'];
  pathLabel: DashboardView['summary']['pathLabel'];
  similarCases: DashboardView['tableData']['similarCases'];
  windowStats: DashboardView['tableData']['windowStats'];
}

export default function HistoryMapping({ currentMapping, pathLabel, similarCases, windowStats }: HistoryMappingProps) {
  const mappingTags = currentMapping?.tags ?? currentMapping?.signalLabels ?? [];
  const casesToShow = similarCases?.slice?.(0, 5) ?? [];

  return (
    <details className="mapping-section" open>
      <summary>
        <div className="mapping-title-wrap">
          <h2 className="section-title">今日历史映射</h2>
          <p className="section-note" style={{ marginTop: '6px' }}>把选定日期的整体状态放回历史样本中，观察相似状态后的路径分布，不代表预测。</p>
        </div>
        <span className="mapping-meta">相似样本 {currentMapping?.similarSampleCount ?? 0} 个</span>
      </summary>

      <div className="mapping-current">
        <div className="mapping-current-head">
          <span className="mapping-date mono">{currentMapping?.date}</span>
          <span className="mapping-state">{currentMapping?.state}</span>
        </div>
        <div className="mapping-tags">
          {mappingTags.map((tag, index) => (
            <span key={index} className="mapping-tag">{tag}</span>
          ))}
        </div>
      </div>

      {(() => {
        const pathInfo = formatPathLabel(pathLabel);
        return (
          <span className="path-label">{pathInfo.text}</span>
        );
      })()}

      <table className="mini-table" aria-label="历史路径统计">
        <thead>
          <tr><th>窗口</th><th>平均收益</th><th>胜率</th><th>平均超额</th></tr>
        </thead>
        <tbody>
          {windowStats?.length > 0 ? (
            windowStats.map((stat) => (
              <tr key={stat.window}>
                <td>T+{stat?.window === '1d' ? '1' : stat?.window === '3d' ? '3' : '5'}</td>
                <td className={getValueColorClass(stat?.avgReturn)}>
                  {formatPercent(stat?.avgReturn)}
                  {stat?.avgReturn != null && (stat.avgReturn > 0 ? ' ↑' : stat.avgReturn < 0 ? ' ↓' : '')}
                </td>
                <td>{formatWinRate(stat?.winRate)}</td>
                <td className={getValueColorClass(stat?.avgExcess)}>
                  {formatPercent(stat?.avgExcess)}
                  {stat?.avgExcess != null && (stat.avgExcess > 0 ? ' ↑' : stat.avgExcess < 0 ? ' ↓' : '')}
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={4} style={{ textAlign: 'center', color: 'var(--muted)', padding: '20px' }}>
                暂无统计数据
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <div className="case-list-title">最相似历史案例</div>
      {casesToShow.length > 0 ? (
        casesToShow.map((caseItem, index) => (
          <div key={index} className="mapping-case">
            <div className="mapping-case-head">
              <span className="mapping-case-date mono">{caseItem?.date}</span>
              <span className="mapping-similarity mono">{formatSimilarity(caseItem?.similarity)}</span>
            </div>
            <div className="mapping-tags">
              {caseItem?.matchingStates?.slice?.(0, 5)?.map?.((label: string, i: number) => (
                <span key={`s-${i}`} className="badge blue">{label}</span>
              )) ?? null}
              {caseItem?.matchingSignals?.slice?.(0, 4)?.map?.((label: string, i: number) => (
                <span key={`sig-${i}`} className="mapping-tag">{label}</span>
              ))}
              {(caseItem?.matchingSignals?.length ?? 0) > 4 && (
                <span className="muted">+{caseItem.matchingSignals.length - 4}</span>
              )}
            </div>
            <div className="mapping-case-values">
              <div>
                <span className="muted">T+1</span>
                <span className={`${getValueColorClass(caseItem?.next1dReturn)} mono`} style={{ marginLeft: '8px' }}>
                  {formatPercent(caseItem?.next1dReturn)}
                </span>
              </div>
              <div>
                <span className="muted">T+3</span>
                <span className={`${getValueColorClass(caseItem?.next3dReturn)} mono`} style={{ marginLeft: '8px' }}>
                  {formatPercent(caseItem?.next3dReturn)}
                </span>
              </div>
              <div>
                <span className="muted">T+5</span>
                <span className={`${getValueColorClass(caseItem?.next5dReturn)} mono`} style={{ marginLeft: '8px' }}>
                  {formatPercent(caseItem?.next5dReturn)}
                </span>
              </div>
            </div>
          </div>
        ))
      ) : (
        <div style={{ textAlign: 'center', color: 'var(--muted)', padding: '40px' }}>
          暂无相似案例
        </div>
      )}
    </details>
  );
}
