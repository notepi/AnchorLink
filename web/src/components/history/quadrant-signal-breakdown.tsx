import type { ConditionalSignalEffect, HistorySummaryRow } from '@/types';

interface QuadrantSignalBreakdownProps {
  effects: ConditionalSignalEffect[];
  summary: HistorySummaryRow[];
}

const QUADRANTS = [
  '行业强+个股强', '行业强+个股中', '行业强+个股弱',
  '行业中+个股强', '行业中+个股中', '行业中+个股弱',
  '行业弱+个股强', '行业弱+个股中', '行业弱+个股弱',
];

function latestQuadrant(summary: HistorySummaryRow[]): string | null {
  const valid = [...summary]
    .filter((r) => r.industry_beta && r.anchor_alpha)
    .sort((a, b) => String(a.date).localeCompare(String(b.date)));
  const latest = valid[valid.length - 1];
  if (!latest) return null;
  const betaMap: Record<string, string> = { positive: '行业强', neutral: '行业中', negative: '行业弱' };
  const alphaMap: Record<string, string> = { positive: '个股强', neutral: '个股中', negative: '个股弱' };
  return `${betaMap[latest.industry_beta || ''] || latest.industry_beta}+${alphaMap[latest.anchor_alpha || ''] || latest.anchor_alpha}`;
}

function formatDelta(value: number | null): string {
  if (value === null) return '--';
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}pp`;
}

export function QuadrantSignalBreakdown({ effects, summary }: QuadrantSignalBreakdownProps) {
  const current = latestQuadrant(summary);

  return (
    <section className="bg-anchor-bgSecondary rounded-sm border border-anchor-border p-4">
      <div className="flex items-baseline justify-between mb-4">
        <div>
          <h2 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide">
            象限条件效果
          </h2>
          <p className="text-xs text-anchor-textMuted mt-1">用条件效果替代暴力组合列表，当前象限高亮。</p>
        </div>
        {current && <span className="text-xs text-anchor-accent">当前：{current}</span>}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {QUADRANTS.map((quadrant) => {
          const works = effects
            .filter((e) => e.quadrant === quadrant && e.verdict === 'works_in_condition')
            .sort((a, b) => (b.avg_next_1d_delta_pp_vs_quadrant ?? 0) - (a.avg_next_1d_delta_pp_vs_quadrant ?? 0))
            .slice(0, 2);
          const fails = effects
            .filter((e) => e.quadrant === quadrant && e.verdict === 'fails_in_condition')
            .sort((a, b) => (a.avg_next_1d_delta_pp_vs_quadrant ?? 0) - (b.avg_next_1d_delta_pp_vs_quadrant ?? 0))
            .slice(0, 1);
          const active = quadrant === current;
          return (
            <div
              key={quadrant}
              className={`rounded-sm border p-3 ${active ? 'border-anchor-accent bg-anchor-accent/10' : 'border-anchor-border bg-anchor-bgTertiary'}`}
            >
              <div className="text-xs font-medium text-anchor-text mb-2">{quadrant}</div>
              <div className="space-y-1">
                {works.map((e) => (
                  <div key={`w-${quadrant}-${e.label}`} className="flex items-center justify-between gap-2 text-[11px]">
                    <span className="text-anchor-textSecondary truncate">{e.display_label}</span>
                    <span className="font-mono text-anchor-positive shrink-0">{formatDelta(e.avg_next_1d_delta_pp_vs_quadrant)}</span>
                  </div>
                ))}
                {fails.map((e) => (
                  <div key={`f-${quadrant}-${e.label}`} className="flex items-center justify-between gap-2 text-[11px]">
                    <span className="text-anchor-textMuted truncate">{e.display_label}</span>
                    <span className="font-mono text-anchor-negative shrink-0">{formatDelta(e.avg_next_1d_delta_pp_vs_quadrant)}</span>
                  </div>
                ))}
                {works.length === 0 && fails.length === 0 && (
                  <div className="text-[11px] text-anchor-textMuted">样本不足</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
