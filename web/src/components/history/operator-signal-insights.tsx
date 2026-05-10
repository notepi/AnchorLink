import type { CounterIntuitiveSignal, OperatorSignalRole } from '@/types';

interface HistoricalSignalProfilesProps {
  opportunities: CounterIntuitiveSignal[];
  traps: CounterIntuitiveSignal[];
  roles: OperatorSignalRole[];
  sampleDays: number;
  dateRangeStart: string;
  dateRangeEnd: string;
}

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function formatRate(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return `${(value * 100).toFixed(0)}%`;
}

function formatDate(dateStr: string): string {
  if (!dateStr || dateStr.length !== 8) return dateStr;
  return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`;
}


function MisjudgedSignalCard({ signal }: { signal: CounterIntuitiveSignal }) {
  const isOpportunity = signal.verdict === 'counter_intuitive_opportunity';
  const badgeLabel = isOpportunity ? '看似偏弱，历史表现较强' : '看似偏强，历史表现较弱';
  const badgeClass = isOpportunity
    ? 'text-anchor-positive border-anchor-positive/40 bg-anchor-positive/10'
    : 'text-anchor-negative border-anchor-negative/40 bg-anchor-negative/10';

  return (
    <div className="bg-anchor-bgTertiary border border-anchor-border rounded-sm p-3">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="text-xs font-medium text-anchor-text truncate" title={signal.display_label}>
          {signal.display_label}
        </div>
        <span className={`text-[10px] border rounded px-1.5 py-0.5 shrink-0 ${badgeClass}`}>
          {badgeLabel}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs mb-2">
        <div>
          <div className="text-anchor-textMuted">次日</div>
          <div className={isOpportunity ? 'text-anchor-positive font-mono' : 'text-anchor-negative font-mono'}>
            {formatPct(signal.avg_next_1d)}
          </div>
        </div>
        <div>
          <div className="text-anchor-textMuted">相对基线</div>
          <div className="text-anchor-textSecondary font-mono">{formatPct(signal.avg_next_1d_delta_pp)}</div>
        </div>
        <div>
          <div className="text-anchor-textMuted">胜率</div>
          <div className="text-anchor-textSecondary font-mono">{formatRate(signal.win_rate_1d)}</div>
        </div>
      </div>
      <p className="text-xs text-anchor-textMuted leading-relaxed">
        {signal.explanation}
      </p>
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
            <div className="text-[11px] text-anchor-textMuted mt-1">
              {role.business_tag} · 胜率 {formatRate(role.win_rate)} · {role.reason || role.conclusion}
            </div>
          </li>
        ))}
        {items.length === 0 && <li className="text-xs text-anchor-textMuted">暂无</li>}
      </ul>
    </div>
  );
}

export function OperatorSignalInsights({
  opportunities,
  traps,
  roles,
  sampleDays,
  dateRangeStart,
  dateRangeEnd,
}: HistoricalSignalProfilesProps) {
  const primary = roles.filter((r) => r.role === 'primary_trigger');
  const confirmations = roles.filter((r) => r.role === 'confirmation');
  const invalidators = roles.filter((r) => r.role === 'risk_invalidator');

  const misjudgedSignals = [...opportunities, ...traps].sort(
    (a, b) => Math.abs(b.degree) - Math.abs(a.degree)
  ).slice(0, 4);

  return (
    <section className="bg-anchor-bgSecondary rounded-sm border border-anchor-border p-4">
      <div className="mb-4">
        <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-1">
          历史信号画像
        </h2>
        <p className="text-[11px] text-anchor-textMuted">
          基于 {sampleDays} 个样本（{formatDate(dateRangeStart)} 至 {formatDate(dateRangeEnd)}）总结信号特征，仅用于理解历史规律，不代表当前触发。
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div>
          <div className="text-xs font-medium text-anchor-text mb-2">容易误判的信号</div>
          <div className="space-y-2">
            {misjudgedSignals.slice(0, 2).map((s) => (
              <MisjudgedSignalCard key={s.label} signal={s} />
            ))}
            {misjudgedSignals.length === 0 && <p className="text-xs text-anchor-textMuted">暂无明显误判信号</p>}
          </div>
        </div>

        <div>
          <RoleList title="历史触发型" items={primary} tone="good" />
        </div>

        <div className="grid grid-cols-1 gap-3">
          <RoleList title="历史确认型" items={confirmations} />
          <RoleList title="历史反证型" items={invalidators} tone="bad" />
        </div>
      </div>
    </section>
  );
}
