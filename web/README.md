# AnchorLink Web

AnchorLink 的前端可视化界面，基于 Next.js 15 构建。

## 功能

- 仪表盘：展示锚定标的与板块对比数据
- 分层分析：行业分层、个股分层可视化
- 报告查看：查看生成的日报

## 数据依赖

前端依赖 `data/output/YYYYMMDD/` 目录的数据文件：

| 文件 | 用途 |
|------|------|
| `industry_snapshot.json` | 行业快照数据 |
| `peer_matrix.csv` | 个股对比矩阵 |
| `industry_report.md` | 行业日报 |

**数据来源**：运行后端 Python 脚本生成

```bash
# 在项目根目录运行
uv run python scripts/run_all.py
```

## 开发

```bash
# 安装依赖
npm install

# 启动开发服务
npm run dev
# 访问 http://localhost:3000

# 构建
npm run build

# 生产模式
npm run start
```

## 技术栈

- Next.js 15 (App Router)
- React 19
- TypeScript
- TailwindCSS
- Radix UI
- Recharts
- Zustand