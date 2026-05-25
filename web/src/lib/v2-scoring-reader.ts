/**
 * V2 评分数据读取器
 */

import { cache } from 'react';
import { readFile } from 'fs/promises';
import { join } from 'path';
import type { V2ScoringData } from '@/types/v2-scoring';

const PROJECT_ROOT = join(process.cwd(), '..');

export const getV2ScoringData = cache(async (): Promise<V2ScoringData | null> => {
  try {
    const raw = await readFile(join(PROJECT_ROOT, 'data', 'output', 'v2_scoring.json'), 'utf-8');
    return JSON.parse(raw) as V2ScoringData;
  } catch {
    return null;
  }
});
