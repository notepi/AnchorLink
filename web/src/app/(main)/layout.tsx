import { getLatestSnapshot, getConfig, getAvailableDates } from '@/lib/data-reader';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { formatDate } from '@/lib/utils';
import { NavTabs } from '@/components/common/nav-tabs';

export default async function MainLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const snapshot = await getLatestSnapshot();
  const config = await getConfig();
  const dates = await getAvailableDates();

  return (
    <div className="min-h-screen bg-anchor-bg text-anchor-text">
      <header className="flex min-h-12 shrink-0 items-center gap-3 border-b border-anchor-border bg-anchor-bgSecondary px-3 py-2">
        <div className="shrink-0 text-xs text-anchor-textMuted">
          {snapshot ? formatDate(snapshot.as_of_date.replace(/-/g, '')) : dates[0] ? formatDate(dates[0]) : '暂无数据'}
        </div>

        <Separator orientation="vertical" className="h-4" />

        <div className="shrink-0 text-sm font-medium text-anchor-text">
          {snapshot?.anchor.name || config?.anchor.name || '铂力特'}
        </div>
        <Badge variant="outline" className="text-xs font-mono">
          {snapshot?.anchor.symbol || config?.anchor.symbol || '688333.SH'}
        </Badge>

        <NavTabs />

        {snapshot && (
          <div className="ml-auto hidden shrink-0 items-center gap-2 lg:flex">
            <Badge
              variant={snapshot.conclusion.industry_beta === 'positive' ? 'positive' : snapshot.conclusion.industry_beta === 'negative' ? 'negative' : 'neutral'}
              className="text-xs"
            >
              Beta{snapshot.conclusion.industry_beta === 'positive' ? '+' : snapshot.conclusion.industry_beta === 'negative' ? '-' : '0'}
            </Badge>
            <Badge
              variant={snapshot.conclusion.anchor_alpha === 'positive' ? 'positive' : snapshot.conclusion.anchor_alpha === 'negative' ? 'negative' : 'neutral'}
              className="text-xs"
            >
              Alpha{snapshot.conclusion.anchor_alpha === 'positive' ? '+' : snapshot.conclusion.anchor_alpha === 'negative' ? '-' : '0'}
            </Badge>
            <Badge
              variant={snapshot.conclusion.risk_level === 'low' ? 'positive' : snapshot.conclusion.risk_level === 'high' ? 'negative' : 'accent'}
              className="text-xs"
            >
              {snapshot.conclusion.risk_level}
            </Badge>
          </div>
        )}
      </header>

      <main className="flex-1">
        {children}
      </main>
    </div>
  );
}
