'use client';

import { useEffect, useState } from 'react';

export default function TestPage() {
  const [test, setTest] = useState('初始');

  useEffect(() => {
    console.log('[Test] useEffect 执行');
    // 使用 setTimeout 测试 setState 是否工作
    setTimeout(() => {
      console.log('[Test] setTimeout 回调执行');
      setTest('setTimeout 更新');
    }, 1000);
  }, []);

  return <div>状态: {test}</div>;
}