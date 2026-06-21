"use client";

import dynamic from 'next/dynamic';

const ExcessComparisonChart = dynamic(() => import('@/components/history-v2/ExcessComparisonChart'), {
  ssr: false,
  loading: () => <div style={{ height: 210 }} />,
});

export default ExcessComparisonChart;
