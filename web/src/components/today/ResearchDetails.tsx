'use client';

import { useState } from 'react';

export default function ResearchDetails() {
  const [open, setOpen] = useState(false);

  return (
    <section className="tc-card tc-research">
      <button
        className="tc-research-toggle"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
      >
        <span>📂 研究明细</span>
        <span className="tc-research-sub">状态迁移热力图 · 预测准确度 · 性格档案</span>
        <span className="tc-research-chevron">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="tc-research-body">
          <p className="tc-disclaimer">
            ⚠️ 以下内容来自原 History V2 研究模块，供深入研究用。<strong>日常决策不需要看这里</strong>。
          </p>
          <ul className="tc-research-list">
            <li>
              <strong>状态迁移热力图</strong>
              <span className="tc-small">——完整的 9×9 象限转移矩阵，查看任意两格之间的历史转移频率</span>
            </li>
            <li>
              <strong>预测准确度评估</strong>
              <span className="tc-small tc-warn">
                —— ⚠️ 全 242 天回测，T+1 方向命中率 <strong>48.3%</strong>（低于 50% 基准）；
                预测方向不可信，系统定位已调整为「状态监测仪」
              </span>
            </li>
            <li>
              <strong>历史性格档案</strong>
              <span className="tc-small">——铂力特的长期行为特征：偏好 / 陷阱 / 反直觉信号 / 与各池的关系</span>
            </li>
          </ul>
          <p className="tc-hint">
            💡 完整研究详情请前往{' '}
            <a href="/history-v2" className="tc-link">History V2 页面</a>
            ，该页面保留所有原始统计模块。
          </p>
        </div>
      )}
    </section>
  );
}
