import type { Alert } from '@/types/dashboard-view';

interface AlertBarProps {
  alerts?: Alert[];
}

export default function AlertBar({ alerts }: AlertBarProps) {
  if (!alerts || alerts.length === 0) return null;

  return (
    <section className="tc-alerts">
      <h3>极端位置警报 · 今天有 {alerts.length} 条</h3>
      {alerts.map((a, i) => (
        <div key={i} className={`tc-alert-item tc-alert-${a.level}`}>
          <span className="tc-alert-icon">{a.icon}</span>
          <span>{a.text}</span>
        </div>
      ))}
    </section>
  );
}
