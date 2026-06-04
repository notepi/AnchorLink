import type { MLAnalysis, MLModelResult } from '@/types/quant-lab-view';

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}
function fmtR(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${v >= 0 ? '+' : ''}${v.toFixed(4)}`;
}
function fmtAcc(v: number | null | undefined): string {
  if (v == null) return '-';
  return `${(v * 100).toFixed(1)}%`;
}

function ModelCard({ name, model, highlight }: { name: string; model: MLModelResult; highlight?: boolean }) {
  const acc = model.direction_accuracy;
  const accClass = acc >= 0.55 ? 'ql-pos' : acc >= 0.50 ? 'ql-neu' : 'ql-neg';
  return (
    <div className="ql-kpi-card" style={highlight ? { borderColor: 'var(--ql-accent)', borderWidth: 1.5 } : {}}>
      <div className="ql-kpi-label">{name}</div>
      <div className={`ql-kpi-value ${accClass}`}>{fmtAcc(acc)}</div>
      <div className="ql-kpi-sub">
        Pearson r = {fmtR(model.pearson_r)}<br />
        MAE = {model.mae.toFixed(3)} · n = {model.test_samples}
      </div>
    </div>
  );
}

function QuintileBars({ model, name }: { model: MLModelResult; name: string }) {
  const max = Math.max(...model.quintile_test.map((q) => Math.abs(q.actual_exc1d.avg)));
  return (
    <div>
      <h3>{name} 分五档实际 T+1 超额</h3>
      <table className="ql-table">
        <thead>
          <tr>
            <th>档位</th>
            <th>预测区间</th>
            <th>n</th>
            <th>实际 T+1 超额</th>
            <th style={{ width: '40%' }}>可视化</th>
            <th>方向命中</th>
          </tr>
        </thead>
        <tbody>
          {model.quintile_test.map((q) => {
            const val = q.actual_exc1d.avg;
            const pct = (Math.abs(val) / max) * 100;
            const hit = q.direction_hit_rate ?? 0;
            // 不给高命中档着"利好"色：分档样本量小（n≈20+），高命中多为噪声，避免误导
            const highlight = '';
            return (
              <tr key={q.quintile} className={highlight}>
                <td>Q{q.quintile}</td>
                <td style={{ fontSize: 11, color: 'var(--ql-text-muted)' }}>
                  [{q.predRange[0].toFixed(2)}, {q.predRange[1].toFixed(2)}]
                </td>
                <td>{q.n}</td>
                <td className={val >= 0 ? 'ql-pos' : 'ql-neg'}>{fmtPct(val)}</td>
                <td>
                  <div style={{ position: 'relative', height: 14, background: 'var(--ql-bg3)', borderRadius: 2 }}>
                    <div
                      style={{
                        position: 'absolute',
                        left: val < 0 ? `${50 - pct / 2}%` : '50%',
                        width: `${pct / 2}%`,
                        height: '100%',
                        background: val >= 0 ? 'var(--ql-red)' : 'var(--ql-green)',
                        borderRadius: 2,
                      }}
                    />
                    <div
                      style={{
                        position: 'absolute',
                        left: '50%',
                        top: 0,
                        bottom: 0,
                        width: 1,
                        background: 'var(--ql-text-muted)',
                      }}
                    />
                  </div>
                </td>
                <td className={hit >= 0.55 ? 'ql-pos' : hit <= 0.45 ? 'ql-neg' : ''}>{(hit * 100).toFixed(0)}%</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function FeatureBars({ model, name }: { model: MLModelResult; name: string }) {
  const max = Math.max(...model.top_features.map((f) => f.importance));
  return (
    <div>
      <h3>{name} Top 10 特征重要性</h3>
      {model.top_features.slice(0, 10).map((f) => {
        const width = (f.importance / max) * 100;
        return (
          <div key={f.feature} style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '3px 0', fontSize: 11 }}>
            <div style={{ width: 150, color: 'var(--ql-text-mid)', fontFamily: 'ui-monospace, monospace' }}>
              {f.feature}
            </div>
            <div style={{ flex: 1, background: 'var(--ql-bg3)', height: 14, borderRadius: 2, position: 'relative' }}>
              <div
                style={{
                  width: `${width}%`,
                  background: 'var(--ql-accent)',
                  height: '100%',
                  borderRadius: 2,
                }}
              />
            </div>
            <div style={{ width: 60, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
              {f.importance.toFixed(3)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function MLPanel({ data }: { data: MLAnalysis }) {
  const models = Object.entries(data);
  // 找最佳模型（直接命中率最高）
  const bestName = models.reduce<[string, number]>((acc, [n, m]) => (m.direction_accuracy > acc[1] ? [n, m.direction_accuracy] : acc), ['', 0])[0];
  // 默认展示 GradientBoosting 的分位和特征
  const gbr = data['GradientBoosting'];
  const rf = data['RandomForest'];

  return (
    <section id="ml" className="ql-section">
      <h2>机器学习模型评估（P 维）<span className="ql-section-tag">SECTION 6</span></h2>

      <h3>三模型对比（27 维特征 · walk-forward 验证）</h3>
      <div className="ql-grid-3">
        {models.map(([name, m]) => (
          <ModelCard key={name} name={name} model={m} highlight={name === bestName} />
        ))}
      </div>

      <div style={{ marginTop: 16 }}>
        {gbr && <QuintileBars model={gbr} name="GradientBoosting" />}
      </div>

      <div className="ql-grid-2" style={{ marginTop: 16 }}>
        {gbr && <FeatureBars model={gbr} name="GradientBoosting" />}
        {rf && <FeatureBars model={rf} name="RandomForest" />}
      </div>

      <div className="ql-hint">
        ⚠️ <strong>诚实结论：模型没有样本外预测力。</strong>
        三个模型 walk-forward 整体方向命中率仅约 48–53%（50% = 抛硬币），Pearson r ≈ -0.04 ~ -0.08（几乎为零、甚至反向）。
        分档表里某一档（如 GBR Q4）看着命中率高，是 n≈24 的小样本噪声、事后挑桶的结果，<strong>不可作为操作依据</strong>。
        特征重要性（如 excess_5d 排第一）只说明模型在训练集里更看重它，<strong>不等于它能预测未来</strong>。
      </div>
    </section>
  );
}
