'use client';

import { useState } from 'react';
import { PathPattern } from '@/types';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

interface PathPatternPanelProps {
  patterns: PathPattern[];
}

export function PathPatternPanel({ patterns }: PathPatternPanelProps) {
  const [activeIdx, setActiveIdx] = useState(0);

  if (!patterns || patterns.length === 0) {
    return (
      <div>
        <h3 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-2 px-1">
          历史路径特征
        </h3>
        <div className="bg-anchor-bgTertiary px-3 py-4 text-center">
          <p className="text-xs text-anchor-textMuted">暂无路径数据</p>
        </div>
      </div>
    );
  }

  const activePattern = patterns[activeIdx];
  const chartData = (activePattern.avg_path || []).filter(p => p.anchor_return !== null || p.chain_median !== null);

  return (
    <div>
      <h3 className="text-xs font-medium text-anchor-textSecondary uppercase tracking-wide mb-2 px-1">
        历史路径特征
      </h3>

      {/* 标签切换 */}
      <div className="flex gap-1 mb-2 overflow-x-auto">
        {patterns.map((pattern, idx) => (
          <button
            key={idx}
            onClick={() => setActiveIdx(idx)}
            className={`px-2 py-1 text-[10px] rounded-sm whitespace-nowrap transition-colors ${
              idx === activeIdx
                ? 'bg-anchor-text text-anchor-bgSecondary'
                : 'bg-anchor-bgTertiary text-anchor-textMuted hover:text-anchor-text'
            }`}
          >
            {pattern.event_label}
            <span className="ml-1 opacity-60">n={pattern.count}</span>
          </button>
        ))}
      </div>

      {/* 图表区域 */}
      <div className="bg-anchor-bgTertiary border border-anchor-border">
        {chartData.length > 0 ? (
          <>
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 5, left: -10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis
                    dataKey="offset"
                    tick={{ fontSize: 10, fill: '#9ca3af' }}
                    tickFormatter={(value) => value === 0 ? 'T0' : value < 0 ? `T${value}` : `T+${value}`}
                    stroke="#4b5563"
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: '#9ca3af' }}
                    tickFormatter={(value) => `${value}%`}
                    stroke="#4b5563"
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (active && payload && payload.length && payload[0]?.payload) {
                        const data = payload[0].payload;
                        return (
                          <div className="bg-anchor-bgTertiary border border-anchor-border rounded-sm px-3 py-2 text-xs shadow-lg">
                            <div className="text-anchor-textMuted mb-1">
                              {data.offset === 0 ? 'T0' : data.offset < 0 ? `T${data.offset}` : `T+${data.offset}`}
                            </div>
                            {data.anchor_return !== null && data.anchor_return !== undefined && (
                              <div className="flex items-center justify-between gap-4">
                                <span className="text-red-400">● 个股(累计):</span>
                                <span className="font-medium text-anchor-text">
                                  {data.anchor_return >= 0 ? '+' : ''}{data.anchor_return.toFixed(2)}%
                                </span>
                              </div>
                            )}
                            {data.chain_median !== null && data.chain_median !== undefined && (
                              <div className="flex items-center justify-between gap-4">
                                <span className="text-gray-400">● 板块(累计):</span>
                                <span className="font-medium text-anchor-text">
                                  {data.chain_median >= 0 ? '+' : ''}{data.chain_median.toFixed(2)}%
                                </span>
                              </div>
                            )}
                            {data.excess !== null && data.excess !== undefined && (
                              <div className="flex items-center justify-between gap-4">
                                <span className="text-green-400">● 超额:</span>
                                <span className="font-medium text-anchor-text">
                                  {data.excess >= 0 ? '+' : ''}{data.excess.toFixed(2)}pp
                                </span>
                              </div>
                            )}
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <ReferenceLine y={0} stroke="#6b7280" strokeDasharray="3 3" />
                  <ReferenceLine x={0} stroke="#3b82f6" strokeDasharray="3 3" />
                  <Line
                    type="monotone"
                    dataKey="anchor_return"
                    stroke="#ef4444"
                    strokeWidth={2}
                    dot={{ fill: '#ef4444', r: 2 }}
                    activeDot={{ r: 4 }}
                    connectNulls
                  />
                  <Line
                    type="monotone"
                    dataKey="chain_median"
                    stroke="#6b7280"
                    strokeWidth={1.5}
                    strokeDasharray="4 4"
                    dot={{ fill: '#6b7280', r: 1.5 }}
                    connectNulls
                  />
                  <Line
                    type="monotone"
                    dataKey="excess"
                    stroke="#22c55e"
                    strokeWidth={1.5}
                    strokeDasharray="6 2"
                    dot={{ fill: '#22c55e', r: 1.5 }}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* 图例 + summary */}
            <div className="px-3 py-2 border-t border-anchor-border flex items-center justify-between">
              <div className="flex gap-3 text-[10px] text-anchor-textMuted">
                <div className="flex items-center gap-1">
                  <div className="w-3 h-0.5 bg-red-500" />
                  <span>个股</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-0.5 bg-gray-500" style={{ backgroundImage: 'repeating-linear-gradient(90deg, #6b7280 0, #6b7280 3px, transparent 3px, transparent 6px)' }} />
                  <span>板块</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-0.5 bg-green-500" style={{ backgroundImage: 'repeating-linear-gradient(90deg, #22c55e 0, #22c55e 4px, transparent 4px, transparent 6px)' }} />
                  <span>超额</span>
                </div>
              </div>
              <p className="text-[10px] text-anchor-textSecondary">{activePattern.summary}</p>
            </div>
          </>
        ) : (
          <div className="h-40 flex items-center justify-center text-xs text-anchor-textMuted">
            暂无有效路径数据
          </div>
        )}
      </div>
    </div>
  );
}
