'use client';

import { useEffect, useState } from 'react';

export default function AlertTest() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Try to detect if JS is running
    console.log('JS is running! useEffect fired!');
    window.alert('Client JS executed!');
    setReady(true);
  }, []);

  return <div>Alert test - ready: {ready ? 'yes' : 'no'}</div>;
}