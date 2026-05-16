#!/bin/bash
# 数据定时更新脚本
# 功能：完整四步管道 — 行情拉取 → 日报生成 → 历史分析 → 前端数据构建 + 校验 + 备份
# 使用方法：
# 1. 给脚本添加可执行权限: chmod +x cron_update_data.sh
# 2. 添加到crontab定时任务，例如每天18点运行:
#    0 18 * * 1-5 /path/to/cron_update_data.sh >> /path/to/cron_update.log 2>&1

# 配置
PROJECT_ROOT="/Users/pan/Desktop/research/0workspace/AnchorLink"
SCRIPTS_DIR="${PROJECT_ROOT}/scripts"
LOG_FILE="${PROJECT_ROOT}/logs/cron_update_$(date +%Y%m%d).log"
LOOKBACK_DAYS=120

# 创建日志目录
mkdir -p "${PROJECT_ROOT}/logs"

echo "========================================" >> "${LOG_FILE}"
echo "数据更新开始: $(date)" >> "${LOG_FILE}"
echo "========================================" >> "${LOG_FILE}"

cd "${PROJECT_ROOT}"

# Step 1: 拉取行情数据
echo "Step 1/4: 拉取行情数据 (--days ${LOOKBACK_DAYS})..." >> "${LOG_FILE}"
uv run python -m src.price.run --days ${LOOKBACK_DAYS} >> "${LOG_FILE}" 2>&1
if [ $? -ne 0 ]; then
    echo "Step 1/4 FAILED: 行情拉取失败" >> "${LOG_FILE}"
    exit 1
fi
echo "Step 1/4 OK: 行情数据已更新" >> "${LOG_FILE}"

# Step 2: 生成日报快照
echo "Step 2/4: 生成日报快照..." >> "${LOG_FILE}"
uv run python -m src.dailyreport.run >> "${LOG_FILE}" 2>&1
if [ $? -ne 0 ]; then
    echo "Step 2/4 FAILED: 日报生成失败" >> "${LOG_FILE}"
    exit 2
fi
echo "Step 2/4 OK: 日报快照已生成" >> "${LOG_FILE}"

# Step 3: 全量历史分析
echo "Step 3/4: 构建历史分析..." >> "${LOG_FILE}"
uv run python "${SCRIPTS_DIR}/build_history_analysis.py" >> "${LOG_FILE}" 2>&1
if [ $? -ne 0 ]; then
    echo "Step 3/4 FAILED: 历史分析失败" >> "${LOG_FILE}"
    exit 3
fi
echo "Step 3/4 OK: 历史分析完成" >> "${LOG_FILE}"

# Step 4: 构建前端数据
echo "Step 4/4: 构建dashboard_view.json..." >> "${LOG_FILE}"
uv run python "${SCRIPTS_DIR}/build_dashboard_view.py" >> "${LOG_FILE}" 2>&1
if [ $? -ne 0 ]; then
    echo "Step 4/4 FAILED: 前端数据构建失败" >> "${LOG_FILE}"
    exit 4
fi
echo "Step 4/4 OK: dashboard_view.json 已生成" >> "${LOG_FILE}"

# 运行数据校验
echo "校验数据..." >> "${LOG_FILE}"
uv run python "${SCRIPTS_DIR}/validate_data.py" >> "${LOG_FILE}" 2>&1
if [ $? -ne 0 ]; then
    echo "VALIDATE FAILED: 数据校验失败" >> "${LOG_FILE}"
    exit 5
fi
echo "VALIDATE OK: 数据校验通过" >> "${LOG_FILE}"

# 备份
BACKUP_FILE="${PROJECT_ROOT}/data/output/backup/dashboard_view_$(date +%Y%m%d%H%M%S).json"
mkdir -p "${PROJECT_ROOT}/data/output/backup"
cp "${PROJECT_ROOT}/data/output/dashboard_view.json" "${BACKUP_FILE}" >> "${LOG_FILE}" 2>&1
echo "已备份到: ${BACKUP_FILE}" >> "${LOG_FILE}"

# 清理7天前的备份
find "${PROJECT_ROOT}/data/output/backup" -name "*.json" -mtime +7 -delete >> "${LOG_FILE}" 2>&1

echo "========================================" >> "${LOG_FILE}"
echo "数据更新完成: $(date)" >> "${LOG_FILE}"
echo "========================================" >> "${LOG_FILE}"

exit 0
