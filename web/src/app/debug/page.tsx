'use client';

import { useEffect, useState } from 'react';

// 硬编码的测试数据
const TEST_SNAPSHOT = {
  anchor: { symbol: '688333.SH', name: '铂力特', themes: ['金属3D打印'] },
  as_of_date: '2026-04-30',
  signals: [
    { label: '行业Beta为正', category: 'beta', confidence: 'medium' },
    { label: '个股Alpha为正', category: 'alpha', confidence: 'high' },
  ],
  conclusion: {
    industry_beta: 'positive',
    anchor_alpha: 'positive',
    risk_level: 'medium',
    summary: '测试数据 - 行业环境偏正面',
  },
  group_rotation: {
    strongest_group: 'industry_chain',
    weakest_group: 'direct_peers',
    group_ranking: ['industry_chain', 'direct_peers'],
    group_medians: { direct_peers: 1.29, industry_chain: 3.90 },
  },
};

const TEST_MATRIX = [
  { universe: 'direct_peers', symbol: '688433.SH', name: '华曙高科', role: 'direct_comparable', relevance: 0.9, pct_chg: 1.29, amount: 344672, return_rank: 1 },
  { universe: 'industry_chain', symbol: '600343.SH', name: '航天动力', role: 'downstream_demand', relevance: 0.85, pct_chg: 3.79, amount: 1231580, return_rank: 2 },
  { universe: 'industry_chain', symbol: '600879.SH', name: '航天电子', role: 'upstream_supplier', relevance: 0.8, pct_chg: 3.90, amount: 3808479, return_rank: 2 },
];

const TEST_CONFIG = {
  anchor: { symbol: '688333.SH', name: '铂力特' },
  memberships: [
    { universe_id: 'direct_peers', symbol: '688433.SH', enabled: true },
    { universe_id: 'industry_chain', symbol: '600343.SH', enabled: true },
    { universe_id: 'industry_chain', symbol: '600879.SH', enabled: true },
  ],
  instruments: [
    { symbol: '688333.SH', name: '铂力特' },
    { symbol: '688433.SH', name: '华曙高科' },
    { symbol: '600343.SH', name: '航天动力' },
    { symbol: '600879.SH', name: '航天电子' },
  ],
};

export default function DebugPage() {
  const [data, setData] = useState<{
    snapshot: typeof TEST_SNAPSHOT | null;
    matrix: typeof TEST_MATRIX;
    config: typeof TEST_CONFIG | null;
  }>({
    snapshot: null,
    matrix: [],
    config: null,
  });
  const [poolFilter, setPoolFilter] = useState('all');

  useEffect(() => {
    // 模拟加载
    setTimeout(() => {
      setData({
        snapshot: TEST_SNAPSHOT,
        matrix: TEST_MATRIX,
        config: TEST_CONFIG,
      });
    }, 500);
  }, []);

  const filteredMatrix = poolFilter === 'all'
    ? data.matrix
    : data.matrix.filter(row => row.universe === poolFilter);

  const poolFilters = [
    { value: 'all', label: '全部' },
    { value: 'direct_peers', label: '核心' },
    { value: 'industry_chain', label: '产业' },
  ];

  if (!data.snapshot) {
    return <div className="p-8">加载中...</div>;
  }

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-8">
      <h1 className="text-2xl font-bold mb-4">Debug Page - 硬编码数据</h1>

      <div className="mb-4">
        <p>锚点: {data.snapshot.anchor.name} ({data.snapshot.anchor.symbol})</p>
        <p>日期: {data.snapshot.as_of_date}</p>
      </div>

      <div className="mb-4">
        <p className="font-medium mb-2">池子过滤器:</p>
        <div className="flex gap-2">
          {poolFilters.map(filter => (
            <button
              key={filter.value}
              onClick={() => setPoolFilter(filter.value)}
              className={`px-3 py-1 rounded ${
                poolFilter === filter.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-4">
        <p className="font-medium mb-2">同类矩阵 ({filteredMatrix.length} 条):</p>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-400 border-b border-gray-700">
              <th className="pb-2">池子</th>
              <th className="pb-2">代码</th>
              <th className="pb-2">名称</th>
              <th className="pb-2">角色</th>
              <th className="pb-2">涨跌幅</th>
            </tr>
          </thead>
          <tbody>
            {filteredMatrix.map((row, i) => (
              <tr key={i} className="border-b border-gray-800">
                <td className="py-2">{row.universe}</td>
                <td className="py-2 font-mono">{row.symbol}</td>
                <td className="py-2">{row.name}</td>
                <td className="py-2 text-gray-400">{row.role}</td>
                <td className={`py-2 font-mono ${row.pct_chg >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {row.pct_chg >= 0 ? '+' : ''}{row.pct_chg.toFixed(2)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 p-4 bg-gray-800 rounded">
        <p className="font-medium">结论:</p>
        <p className="text-gray-300">{data.snapshot.conclusion.summary}</p>
      </div>

      <div className="mt-4 p-4 bg-blue-900/30 rounded">
        <p className="font-medium">信号:</p>
        <ul className="list-disc list-inside">
          {data.snapshot.signals.map((sig, i) => (
            <li key={i} className="text-gray-300">{sig.label} ({sig.confidence})</li>
          ))}
        </ul>
      </div>
    </div>
  );
}