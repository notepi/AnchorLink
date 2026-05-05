'use client';

import { useEffect, useState } from 'react';

export default function Minimal() {
  const [v, setV] = useState('a');
  useEffect(() => {
    setV('b');
    console.log('effect ran');
  }, []);
  return <p id="result">{v}</p>;
}