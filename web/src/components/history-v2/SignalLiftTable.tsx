import type { DashboardView } from '@/types/dashboard-view';
import { formatPp, getValueColorClass } from '@/lib/history-v2/formatters';

interface SignalLiftTableProps {
  data: DashboardView['tableData']['signalDetail'];
}

export default function SignalLiftTable({ data }: SignalLiftTableProps) {
  const valid = (data ?? [])
    .filter(s => !!s.minCountPassed)
    .sort((a, b) => (b.avgNext1dDeltaPp ?? 0) - (a.avgNext1dDeltaPp ?? 0));

  return (
    <div className="list-card">
      <h3>信号表现排行 <span className="muted">({valid.length})</span></h3>
      {valid.length > 0 ? (
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className="text-left py-1 pr-3">信号</th>
              <th className="text-right py-1 px-2">样本</th>
              <th className="text-right py-1 px-2">次日均值</th>
              <th className="text-right py-1 px-2">相对基线</th>
              <th className="text-right py-1 px-2">胜率</th>
            </tr>
          </thead>
          <tbody>
            {valid.map((row, i) => (
              <tr key={row.label} className={i < 3 && (row.avgNext1dDeltaPp ?? 0) > 0 ? 'row-highlight' : i >= valid.length - 3 && (row.avgNext1dDeltaPp ?? 0) < 0 ? 'row-warn' : ''}>
                <td className="py-1 pr-3 max-w-[180px] truncate" title={row.label}>{row.displayLabel || row.label}</td>
                <td className="text-right py-1 px-2 mono muted">{row.appearanceCount}</td>
                <td className={`text-right py-1 px-2 mono ${getValueColorClass(row.avgNext1d)}`}>{formatPp(row.avgNext1d)}</td>
                <td className={`text-right py-1 px-2 mono ${getValueColorClass(row.avgNext1dDeltaPp)}`}>
                  {row.avgNext1dDeltaPp != null ? `${row.avgNext1dDeltaPp >= 0 ? '+' : ''}${row.avgNext1dDeltaPp.toFixed(2)}pp` : '--'}
                </td>
                <td className={`text-right py-1 px-2 mono ${getValueColorClass(row.winRate1d)}`}>
                  {row.winRate1d != null ? `${(row.winRate1d * 100).toFixed(0)}%` : '--'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="muted text-center py-3">暂无满足条件的信号</p>
      )}
      <p className="muted" style={{ fontSize: '11px', marginTop: '4px' }}>* 样本不足 5 次的信号不展示</p>
    </div>
  );
}
