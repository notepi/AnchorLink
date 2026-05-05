'use client';
import { useState } from 'react';
export default function MinState() {
  const [v, setV] = useState('a');
  return (
    <div>
      <p>Value: {v}</p>
      <button onClick={() => setV('b')}>Change</button>
    </div>
  );
}