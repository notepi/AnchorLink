'use client';

import { useEffect, useState } from 'react';
import { useAppStore } from '@/lib/store';

export default function SimplePage() {
  const setDate = useAppStore((state) => state.setDate);
  const setAvailableDates = useAppStore((state) => state.setAvailableDates);
  const poolFilter = useAppStore((state) => state.poolFilter);
  const setPoolFilter = useAppStore((state) => state.setPoolFilter);

  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // 直接设置日期
    setAvailableDates(['20260430']);
    setDate('20260430');
    setIsLoading(false);
  }, [setDate, setAvailableDates]);

  return (
    <div>
      <h1>Simple Page</h1>
      <p>Loading: {isLoading ? 'yes' : 'no'}</p>
      <p>Pool Filter: {poolFilter}</p>
      <button onClick={() => setPoolFilter('direct_peers')}>
        Set to direct_peers
      </button>
    </div>
  );
}