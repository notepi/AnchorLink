'use client';

import { useEffect, useState } from 'react';

export default function JsTest() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    // This runs in the browser
    console.log('useEffect ran, count:', count);
    if (count === 0) {
      setCount(1);
    }
  }, []);

  return (
    <div>
      <p>Count: {count}</p>
      <p>If this shows "Count: 1" in browser, JS is working!</p>
    </div>
  );
}