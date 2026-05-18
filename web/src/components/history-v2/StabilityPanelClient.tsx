"use client";

import dynamic from 'next/dynamic';

const StabilityPanel = dynamic(() => import('@/components/history-v2/StabilityPanel'), {
  ssr: false,
  loading: () => <div style={{ height: 210 }} />,
});

export default StabilityPanel;
