export default function QuantLabTopBar({
  generatedAt,
}: {
  generatedAt: string;
}) {
  const dateStr = generatedAt
    ? `${generatedAt.slice(0, 4)}-${generatedAt.slice(4, 6)}-${generatedAt.slice(6, 8)}`
    : '—';

  const anchors = [
    { id: 'hero', label: '① 总览' },
    { id: 'engine', label: '② 评分引擎' },
    { id: 'curve', label: '③ 累计曲线' },
    { id: 'mean-reversion', label: '④ 均值回归' },
    { id: 'alpha-scatter', label: '⑤ 信号 Alpha/Beta' },
    { id: 'ml', label: '⑥ 机器学习' },
    { id: 'pool', label: '⑦ 行业联动' },
    { id: 'calendar', label: '⑧ 信号日历' },
    { id: 'weights', label: '⑨ 权重表' },
  ];

  return (
    <header className="ql-topbar">
      <h1>量化策略实验室 · Quant Lab</h1>
      <div className="ql-subtitle">
        铂力特 (688333.SH) · 16 维信号 · 243 天回测 · 累计 Alpha +112.88% · 数据截至 {dateStr}
      </div>
      <nav className="ql-anchors">
        {anchors.map((a) => (
          <a key={a.id} href={`#${a.id}`}>{a.label}</a>
        ))}
      </nav>
    </header>
  );
}
