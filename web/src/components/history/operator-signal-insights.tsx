import type { CounterIntuitiveSignal, OperatorSignalRole } from '@/types';

interface OperatorSignalInsightsProps {
  opportunities: CounterIntuitiveSignal[];
  traps: CounterIntuitiveSignal[];
  roles: OperatorSignalRole[];
}

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function formatRate(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return `${(value * 100).toFixed(0)}%`;
}

function InsightCard({ signal, tone }: { signal: CounterIntuitiveSignal; tone: 'good' | 'bad' }) {
  const badge = tone === 'good'
    ? 'text-anchor-positive border-anchor-positive/40 bg-anchor-positive/10'
    : 'text-anchor-negative border-anchor-negative/40 bg-anchor-negative/10';
  return (
    <div className="bg-anchor-bgTertiary border border-anchor-border rounded-sm p-3">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="text-xs font-medium text-anchor-text truncate" title={signal.display_label}>
          {signal.display_label}
        </div>
        <span className={`text-[10px] border rounded px-1.5 py-0.5 shrink-0 ${badge}`}>
          {tone === 'good' ? '反直觉机会' : '信号陷阱'}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs mb-2">
        <div>
          <div className="text-anchor-textMuted">次日</div>
          <div className={tone === 'good' ? 'text-anchor-positive font-mono' : 'text-anchor-negative font-mono'}>
            {formatPct(signal.avg_next_1d)}
          </div>
        </div>
        <div>
          <div className="text-anchor-textMuted">相对</div>
          <div className="text-anchor-textSecondary font-mono">{formatPct(signal.avg_next_1d_delta_pp)}</div>
        </div>
        <div>
          <div className="text-anchor-textMuted">胜率</div>
          <div className="text-anchor-textSecondary font-mono">{formatRate(signal.win_rate_1d)}</div>
        </div>
      </div>
      <p className="text-xs text-anchor-textMuted leading-relaxed">{signal.explanation}</p>
    </div>
  );
}

function RoleList({ title, items, tone }: { title: string; items: OperatorSignalRole[]; tone?: 'good' | 'bad' }) {
  const color = tone === 'good' ? 'text-anchor-positive' : tone === 'bad' ? 'text-anchor-negative' : 'text-anchor-accent';
  return (
    <div>
      <div className="text-xs font-medium text-anchor-textSecondary mb-2">{title}</div>
      <ul className="space-y-1.5">
        {items.slice(0, 3).map((role) => (
          <li key={`${role.role}-${role.label}`} className="bg-anchor-bgTertiary border border-anchor-border rounded-sm px-3 py-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-anchor-text truncate" title={role.display_label}>{role.display_label}</span>
              <span className={`text-xs font-mono ${color}`}>{formatPct(role.delta_pp)}</span>
            </div>
            <div className="text-[11px] text-anchor-textMuted mt-1 truncate">
              {role.business_tag} · 胜率 {formatRate(role.win_rate)} · {role.conclusion}
            </div>
          </li>
        ))}
        {items.length === 0 && <li className="text-xs text-anchor-textMuted">暂无</li>}
      </ul>
    </div>
  );
}

export function OperatorSignalInsights({ opportunities, traps, roles }: OperatorSignalInsightsProps) {
  const primary = roles.filter((r) => r.role === 'primary_trigger');
  const confirmations = roles.filter((r) => r.role === 'confirmation');
  const invalidators = roles.filter((r) => r.role === 'risk_invalidator');

  return (
    <section className="bg-anchor-bgSecondary rounded-sm border border-anchor-border p-4">
      <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-4">
        信号洞察
      </h2>
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div>
          <div className="text-xs font-medium text-anchor-positive mb-2">反直觉机会</div>
          <div className="space-y-2">
            {opportunities.slice(0, 2).map((s) => <InsightCard key={s.label} signal={s} tone="good" />)}
            {opportunities.length === 0 && <p className="text-xs text-anchor-textMuted">暂无反直觉机会</p>}
          </div>
        </div>
        <div>
          <div className="text-xs font-medium text-anchor-negative mb-2">信号陷阱</div>
          <div className="space-y-2">
            {traps.slice(0, 2).map((s) => <InsightCard key={s.label} signal={s} tone="bad" />)}
            {traps.length === 0 && <p className="text-xs text-anchor-textMuted">暂无明显信号陷阱</p>}
          </div>
        </div>
        <div className="grid grid-cols-1 gap-3">
          <RoleList title="主触发" items={primary} tone="good" />
          <RoleList title="确认" items={confirmations} />
          <RoleList title="反证" items={invalidators} tone="bad" />
        </div>
      </div>
    </section>
  );
}
