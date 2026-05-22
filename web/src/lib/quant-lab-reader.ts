import { readFile } from 'fs/promises';
import { join } from 'path';
import { cache } from 'react';
import type {
  QuantLabView,
  CompositeBacktest,
  DeepQuantAnalysis,
  SecondOrderAnalysis,
} from '@/types/quant-lab-view';

// 数据目录与 dashboard-view-reader 一致
const PROJECT_ROOT = join(process.cwd(), '..');
const OUTPUT_DIR = join(PROJECT_ROOT, 'data', 'output');

const BACKTEST_PATH    = join(OUTPUT_DIR, 'composite_signal_backtest.json');
const DEEP_QUANT_PATH  = join(OUTPUT_DIR, 'history_deep_quant_analysis.json');
const SECOND_ORDER_PATH = join(OUTPUT_DIR, 'history_2nd_order_analysis.json');

/**
 * 读取量化实验室所需的 3 个 JSON 文件，并合成统一视图
 * 用 React cache 实现请求去重（同一渲染周期内只读一次）
 */
export const getQuantLabView = cache(async (): Promise<QuantLabView | null> => {
  try {
    const [backtestRaw, deepQuantRaw, secondOrderRaw] = await Promise.all([
      readFile(BACKTEST_PATH, 'utf-8'),
      readFile(DEEP_QUANT_PATH, 'utf-8'),
      readFile(SECOND_ORDER_PATH, 'utf-8'),
    ]);

    const backtest    = JSON.parse(backtestRaw)    as CompositeBacktest;
    const deepQuant   = JSON.parse(deepQuantRaw)   as DeepQuantAnalysis;
    const secondOrder = JSON.parse(secondOrderRaw) as SecondOrderAnalysis;

    return { backtest, deepQuant, secondOrder };
  } catch (error) {
    console.error('Failed to read quant-lab data:', error);
    return null;
  }
});
