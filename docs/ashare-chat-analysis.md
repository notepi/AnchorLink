# ashare.chat 前端技术架构深度分析报告

> 分析日期: 2026-05-17
> 目标网站: http://ashare.chat/ (StockStory Monitor)

---

## 一、技术栈总览

### 1.1 核心框架

| 层级 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 前端框架 | React | 19.2.4 | 最新版本，使用 JSX Runtime |
| 构建工具 | Vite | - | 从 hash 文件名推断 |
| CSS 框架 | Tailwind CSS | 3.x | 原子化 CSS |
| 状态管理 | Zustand | - | 轻量级状态管理 |
| 路由 | React Router | - | 声明式路由 |

### 1.2 图表与可视化

| 库 | 用途 | 说明 |
|---|------|------|
| ECharts | 主图表库 | K 线图、折线图、面积图等 |
| D3.js | 辅助可视化 | 自定义 SVG 图形 |
| 自定义 SVG | 图标系统 | 内联 SVG 组件 |

**注意**: 没有使用 TradingView，K 线图完全由 ECharts 实现。

### 1.3 第三方依赖

| 库 | 版本 | 用途 |
|---|------|------|
| @google/genai | 1.38.0 | Google AI SDK，AI 对话功能 |
| marked | 15.0.0 | Markdown 解析器 |

### 1.4 模块加载方式

```html
<script type="importmap">
{
  "imports": {
    "react/": "https://esm.sh/react@^19.2.4/",
    "react": "https://esm.sh/react@^19.2.4",
    "react-dom/": "https://esm.sh/react-dom@^19.2.4/",
    "@google/genai": "https://esm.sh/@google/genai@^1.38.0",
    "marked": "https://esm.sh/marked@^15.0.0"
  }
}
</script>
```

使用 ES Modules + importmap，通过 esm.sh CDN 加载部分依赖。

---

## 二、设计风格深度拆解

### 2.1 整体风格定位

**风格名称**: 战术/科幻风格 (Tactical/Sci-Fi / Ark Style)

**设计语言特征**:
- 网格背景营造"指挥中心"氛围
- 毛玻璃效果增强层次感
- 黄色/琥珀色强调色（军事仪表风格）
- 微光文字效果（科幻感）
- 动画带有"扫描"和"闪烁"效果

### 2.2 字体方案

```css
/* 代码/数字字体 - 用于价格、涨跌幅、代码 */
font-family: 'JetBrains Mono', monospace;

/* 中文正文字体 */
font-family: 'Noto Sans SC', sans-serif;
```

**JetBrains Mono 特点**:
- 等宽字体，数字对齐
- 连字符支持
- 高可读性，适合金融数据展示

**Noto Sans SC 特点**:
- Google 出品的中文字体
- 多字重支持 (300/400/500/700)
- 覆盖中日韩字符

### 2.3 配色方案

| 用途 | 颜色值 | 说明 |
|------|--------|------|
| 主强调色 | `#FFCF00` | 黄色 (战术风格) |
| 琥珀强调 | `#f59e0b` | amber-500 |
| 深色背景 | `rgba(15, 15, 18, 0.88)` | 半透明深灰 |
| 边框色 | `rgba(255, 255, 255, 0.08)` | 半透明白 |
| 文字主色 | `#fafafa` / `#171717` | 亮/暗模式 |
| 文字次色 | `#a3a3a3` / `#404040` | 次级文字 |
| 链接色 | `#60a5fa` | 蓝色链接 |
| 代码背景 | `#262626` | 深灰代码块 |

### 2.4 毛玻璃效果

```css
.agent-glass-panel {
  /* 半透明深色背景 */
  background: rgba(15, 15, 18, 0.88);

  /* 毛玻璃模糊 + 饱和度增强 */
  backdrop-filter: blur(32px) saturate(1.6);
  -webkit-backdrop-filter: blur(32px) saturate(1.6);

  /* 微弱边框 */
  border: 1px solid rgba(255, 255, 255, 0.08);

  /* 多层阴影 */
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.3),
    inset 0 0 0 1px rgba(255, 255, 255, 0.04);
}
```

**技术要点**:
- `blur(32px)` - 32px 模糊半径
- `saturate(1.6)` - 饱和度提升 60%
- `inset box-shadow` - 内发光边框效果

### 2.5 文字发光效果

```css
/* 主发光效果 */
.agent-text-glow {
  text-shadow:
    0 0 12px rgba(255, 255, 255, 0.245),
    0 0 4px rgba(255, 255, 255, 0.14),
    0 0 1px rgba(255, 255, 255, 0.35);
}

/* 微弱发光 */
.agent-text-glow-subtle {
  text-shadow:
    0 0 10px rgba(255, 255, 255, 0.14),
    0 0 3px rgba(255, 255, 255, 0.105);
}
```

**技术要点**: 多层 text-shadow 叠加，由外到内渐弱的发光层次。

---

## 三、CSS 动画系统

### 3.1 弹窗入场动画 (Ark Modal)

```css
@keyframes ark-modal-in {
  0% {
    opacity: 0;
    transform: scale(1.05) translateY(10px);
    filter: brightness(2) blur(10px);
  }
  50% {
    opacity: 1;
    transform: scale(0.98) translateY(-2px);
    filter: brightness(1.2) blur(0px);
  }
  100% {
    opacity: 1;
    transform: scale(1) translateY(0);
    filter: brightness(1);
  }
}

.animate-ark-modal {
  animation: ark-modal-in 0.35s cubic-bezier(0.19, 1, 0.22, 1) forwards;
}
```

**效果解析**:
1. 从放大 1.05 倍开始
2. 中间收缩到 0.98 倍（弹性）
3. 亮度从 2 降到 1（扫描效果）
4. 模糊从 10px 到 0

### 3.2 闪烁效果 (Flicker)

```css
@keyframes ark-flicker {
  0% { opacity: 0.8; }
  10% { opacity: 0.4; }
  20% { opacity: 1; }
  30% { opacity: 0.6; }
  40% { opacity: 0.9; }
  100% { opacity: 1; }
}
```

模拟老式显示器的闪烁效果。

### 3.3 虚线动画 (Dash)

```css
@keyframes dash {
  to { stroke-dashoffset: -100; }
}

.animate-dash {
  animation: dash 5s linear infinite;
}
```

SVG 虚线边框流动效果。

### 3.4 脉冲发光 (Pulse Glow)

```css
@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 4px rgba(245, 158, 11, 0.2); }
  50% { box-shadow: 0 0 12px rgba(245, 158, 11, 0.4); }
}

.animate-pulse-glow {
  animation: pulse-glow 2s ease-in-out infinite;
}
```

### 3.5 建议按钮依次浮现

```css
@keyframes suggestion-fade-in {
  0% {
    opacity: 0;
    transform: translateY(6px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-suggestion-in {
  opacity: 0;
  animation: suggestion-fade-in 0.3s ease-out forwards;
}
```

### 3.6 下拉面板动画

```css
@keyframes agent-dropdown-in {
  0% {
    opacity: 0;
    transform: translateY(-12px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}
```

### 3.7 底部面板弹出

```css
@keyframes agent-panel-in {
  0% {
    transform: translateY(100%);
    opacity: 0;
  }
  100% {
    transform: translateY(0);
    opacity: 1;
  }
}
```

### 3.8 动画时长规范

| 动画类型 | 时长 | 缓动函数 |
|---------|------|----------|
| 弹窗入场 | 0.35s | cubic-bezier(0.19, 1, 0.22, 1) |
| 按钮浮现 | 0.3s | ease-out |
| 下拉面板 | 0.2s | cubic-bezier(0.19, 1, 0.22, 1) |
| 底部弹出 | 0.2s | ease-out |
| 虚线流动 | 5s | linear |
| 脉冲发光 | 2s | ease-in-out |

---

## 四、背景与纹理

### 4.1 网格背景

```css
/* 浅色模式网格 */
.ark-grid {
  background-size: 40px 40px;
  background-image:
    linear-gradient(to right, rgba(0, 0, 0, 0.03) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(0, 0, 0, 0.03) 1px, transparent 1px);
}

/* 深色模式网格 */
.ark-grid-dark {
  background-size: 40px 40px;
  background-image:
    linear-gradient(to right, rgba(255, 255, 255, 0.02) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
}
```

### 4.2 斜条纹背景

```css
.diagonal-stripe {
  background: repeating-linear-gradient(
    45deg,
    rgba(0, 0, 0, 0.03),
    rgba(0, 0, 0, 0.03) 10px,
    rgba(0, 0, 0, 0.06) 10px,
    rgba(0, 0, 0, 0.06) 20px
  );
}
```

---

## 五、滚动条定制

### 5.1 浅色主题

```css
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 2px;
}
```

### 5.2 深色主题

```css
.dark-scrollbar::-webkit-scrollbar {
  width: 4px;
  height: 4px;
}

.dark-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.dark-scrollbar::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 2px;
}
```

### 5.3 Agent 专用滚动条

```css
/* 横向滚动条 */
.agent-tab-scrollbar::-webkit-scrollbar {
  height: 2px;
}

.agent-tab-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
  border-radius: 1px;
}

/* 垂直滚动条 */
.agent-session-scrollbar::-webkit-scrollbar {
  width: 2px;
}

.agent-session-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
  border-radius: 1px;
}
```

---

## 六、Markdown 样式系统

### 6.1 浅色模式

```css
.markdown-content h1,
.markdown-content h2,
.markdown-content h3 {
  font-weight: 900;
  color: #171717;
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
  border-left: 4px solid #f59e0b;  /* 琥珀色左边框 */
  padding-left: 0.75rem;
}

.markdown-content p {
  margin-bottom: 1rem;
  line-height: 1.8;
  color: #404040;
  font-weight: 500;
}

.markdown-content blockquote {
  border-left: 4px solid #FFCF00;
  background: #f9fafb;
}

.markdown-content code {
  font-family: 'JetBrains Mono', monospace;
  background: #f5f5f5;
  border: 1px solid #e5e5e5;
  border-radius: 2px;
  padding: 0.125rem 0.25rem;
}
```

### 6.2 深色模式

```css
.agent-markdown-dark h1,
.agent-markdown-dark h2,
.agent-markdown-dark h3 {
  font-weight: 700;
  color: #fafafa;
  border-left: 4px solid #FFCF00;
}

.agent-markdown-dark p {
  color: #a3a3a3;
}

.agent-markdown-dark pre {
  background: #262626;
  border: 1px solid #333;
}

.agent-markdown-dark code {
  color: #a3a3a3;
}

.agent-markdown-dark a {
  color: #60a5fa;
  border-bottom: 1px dashed rgba(96, 165, 250, 0.5);
}

.agent-markdown-dark a:hover {
  color: #93c5fd;
  border-bottom-style: solid;
  text-shadow: 0 0 8px rgba(96, 165, 250, 0.25);
}

.agent-markdown-dark a::after {
  content: ' ↗';
  font-size: 0.7em;
  opacity: 0.5;
}
```

---

## 七、组件架构分析

### 7.1 React Hooks 使用统计

| Hook | 使用次数 | 用途 |
|------|---------|------|
| useState | 342 | 状态管理 |
| useEffect | 151 | 副作用处理 |
| useMemo | 90 | 计算缓存 |
| useRef | 75 | DOM 引用 |
| useCallback | 62 | 函数缓存 |

### 7.2 估算组件结构

```
src/
├── components/
│   ├── charts/           # ECharts 图表组件
│   │   ├── LineChart     # 折线图
│   │   ├── AreaChart     # 面积图
│   │   ├── CandlestickChart  # K 线图
│   │   └── ...
│   ├── ui/               # 基础 UI 组件
│   │   ├── Button
│   │   ├── Input
│   │   ├── Select
│   │   ├── Tooltip
│   │   └── Tab
│   ├── agent/            # Agent 相关组件
│   │   ├── AgentPanel
│   │   ├── AgentDropdown
│   │   └── AgentGlassPanel
│   └── icons/            # SVG 图标组件
│       ├── ArrowUp
│       ├── ArrowDown
│       ├── ArrowLeft
│       └── ArrowRight
├── hooks/                # 自定义 Hooks
├── stores/               # Zustand stores
├── utils/                # 工具函数
│   └── cn()              # className 合并
└── styles/
    └── animations.css    # 动画定义
```

### 7.3 数据通信方式

| 方式 | 使用场景 |
|------|---------|
| fetch | HTTP 请求 |
| WebSocket | 实时数据推送 |
| localStorage | 本地持久化 |
| sessionStorage | 会话存储 |

---

## 八、与 AnchorLink 的可借鉴点

### 8.1 字体方案

**推荐引入**:
```css
.technical-font {
  font-family: 'JetBrains Mono', monospace;
}
```

**应用场景**: 价格显示、涨跌幅、交易量、时间戳

### 8.2 毛玻璃面板

**推荐用于**: 下拉菜单、模态框、浮动面板、通知提示

### 8.3 动画效果

**优先级排序**:
1. `suggestion-fade-in` - 列表项依次浮现
2. `agent-dropdown-in` - 下拉面板入场
3. `pulse-glow` - 状态指示器发光

### 8.4 配色调整

- 主强调色保持 `#f59e0b` (amber-500)
- 深色面板使用 `rgba(15, 15, 18, 0.88)`
- 边框使用 `rgba(255, 255, 255, 0.08)`

---

## 九、技术选型建议

### 9.1 复刻类似风格的最小依赖

```json
{
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "echarts": "^5.0.0",
    "zustand": "^4.0.0",
    "marked": "^15.0.0"
  },
  "devDependencies": {
    "vite": "^5.0.0",
    "tailwindcss": "^3.4.0"
  }
}
```

### 9.2 核心代码量估算

| 模块 | 代码行数 |
|------|---------|
| 自定义 CSS 动画 | ~300 行 |
| 毛玻璃效果样式 | ~50 行 |
| 网格/纹理背景 | ~30 行 |
| Markdown 样式 | ~100 行 |
| 滚动条样式 | ~50 行 |
| **总计** | **~530 行** |

---

## 十、总结

ashare.chat 是一个精心设计的股票监控应用：

| 维度 | 选择 |
|------|------|
| 框架 | React 19 + Vite + Tailwind CSS |
| 状态管理 | Zustand |
| 图表方案 | ECharts（含 K 线图）+ D3.js |
| 设计风格 | 战术/科幻风格 |
| 字体 | JetBrains Mono + Noto Sans SC |
| 视觉效果 | 毛玻璃、文字发光、网格背景 |

**不是开源框架**，而是基于成熟开源工具定制开发的应用。设计风格的核心在于约 500 行自定义 CSS 动画和样式代码。
