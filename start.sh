#!/bin/bash
# AnchorLink 启动脚本

set -e

echo "=== AnchorLink 启动 ==="

# 检查 .env 配置
if [ ! -f .env ]; then
    echo "⚠️  .env 不存在，请先配置："
    echo "   cp .env.example .env"
    echo "   编辑 .env 填入 API Token"
    exit 1
fi

# 检查数据目录
if [ ! -d "data/output" ]; then
    echo "⚠️  data/output 目录不存在"
    echo "   如需更新数据，运行："
    echo "   uv run python scripts/run_all.py"
fi

# 启动前端
echo "启动前端..."
cd web

if [ ! -d node_modules ]; then
    echo "安装前端依赖..."
    npm install
fi

echo "启动开发服务..."
npm run dev