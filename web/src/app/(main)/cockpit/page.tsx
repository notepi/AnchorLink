import { getDashboardView } from '@/lib/dashboard-view-reader';
import CockpitClient from './CockpitClient';
import '../../../styles/cockpit.css';

interface PageProps {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}

export default async function CockpitPage({ searchParams }: PageProps) {
  const dashboard = await getDashboardView();
  const params = await searchParams;

  if (!dashboard) {
    return <div className="cp-page"><div className="cp-empty">数据加载失败，请稍后重试</div></div>;
  }

  const sortedDates = dashboard.dateIndex
    ? Object.keys(dashboard.dateIndex).sort()
    : (dashboard.trends?.excessReturn ?? []).map((item: { date: string }) => item.date).sort();
  const latestDate = sortedDates[sortedDates.length - 1] ?? '';
  const requestedDate = typeof params.date === 'string' ? params.date : '';
  const selectedDate = requestedDate && dashboard.dateIndex?.[requestedDate] ? requestedDate : latestDate;
  const dateEntry = dashboard.dateIndex?.[selectedDate];
  const cockpit = dateEntry?.stateCockpit ?? dashboard.stateCockpit;

  if (!cockpit) {
    return <div className="cp-page"><div className="cp-empty">暂无态势驾驶舱数据，请先重新生成 dashboard_view.json</div></div>;
  }

  return (
    <div className="cp-page">
      <CockpitClient
        cockpit={cockpit}
        dates={sortedDates}
        selectedDate={selectedDate}
        latestDate={latestDate}
        stockName={dashboard.meta?.stockName}
        updateTime={dashboard.meta?.dataUpdateTime}
        similarCases={dateEntry?.similarCases ?? dashboard.tableData?.similarCases ?? []}
      />
    </div>
  );
}
