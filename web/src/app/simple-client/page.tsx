'use client';

import { useEffect, useState } from 'react';

export default function SimpleClient() {
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setIsLoading(false);
  }, []);

  return (
    <div>
      <h1>Simple Client Page</h1>
      <p>Loading: {isLoading ? 'yes' : 'no'}</p>
    </div>
  );
}