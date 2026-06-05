#!/bin/bash
# 数据定时更新脚本
# 功能：调用统一入口 run_all.py 完成完整管道（A链 + B链）+ 校验 + 备份
# 使用方法：
# 1. 给脚本添加可执行权限: chmod +x cron_update_data.sh
# 2. 添加到crontab定时任务，例如每天18点运行:
#    0 18 * * 1-5 /path/to/cron_update_data.sh >> /path/to/cron_update.log 2>&1

# 配置
PROJECT_ROOT="/Users/pan/Desktop/research/0workspace/AnchorLink"
LOG_FILE="${PROJECT_ROOT}/logs/cron_update_$(date +%Y%m%d).log"
LOOKBACK_DAYS=120

# 创建日志目录
mkdir -p "${PROJECT_ROOT}/logs"

echo "========================================" >> "${LOG_FILE}"
echo "数据更新开始: $(date)" >> "${LOG_FILE}"
echo "========================================" >> "${LOG_FILE}"

cd "${PROJECT_ROOT}"

# 1. 调用统一入口（A链 + B链）
echo "运行 run_all.py (--days ${LOOKBACK_DAYS})..." >> "${LOG_FILE}"
uv run python scripts/run_all.py --days ${LOOKBACK_DAYS} >> "${LOG_FILE}" 2>&1
pipeline_exit=$?

if [ ${pipeline_exit} -ne 0 ]; then
    echo "FAILED: run_all.py 退出码 ${pipeline_exit}" >> "${LOG_FILE}"
    echo "========================================" >> "${LOG_FILE}"
    echo "数据更新失败（管道失败）: $(date)" >> "${LOG_FILE}"
    echo "========================================" >> "${LOG_FILE}"
    exit ${pipeline_exit}
fi
echo "OK: run_all.py 完成" >> "${LOG_FILE}"

# 2. 数据校验
echo "校验数据..." >> "${LOG_FILE}"
uv run python "${PROJECT_ROOT}/scripts/validate_data.py" >> "${LOG_FILE}" 2>&1
validate_exit=$?

if [ ${validate_exit} -ne 0 ]; then
    echo "FAILED: 数据校验失败（退出码 ${validate_exit}）" >> "${LOG_FILE}"
    echo "========================================" >> "${LOG_FILE}"
    echo "数据更新失败（校验失败）: $(date)" >> "${LOG_FILE}"
    echo "========================================" >> "${LOG_FILE}"
    exit ${validate_exit}
fi
echo "OK: 数据校验通过" >> "${LOG_FILE}"

# 3. 备份（只在管道+校验都成功时才备份）
BACKUP_FILE="${PROJECT_ROOT}/data/output/backup/dashboard_view_$(date +%Y%m%d%H%M%S).json"
mkdir -p "${PROJECT_ROOT}/data/output/backup"
cp "${PROJECT_ROOT}/data/output/dashboard_view.json" "${BACKUP_FILE}" >> "${LOG_FILE}" 2>&1
if [ $? -ne 0 ]; then
    echo "FAILED: 备份失败" >> "${LOG_FILE}"
    echo "========================================" >> "${LOG_FILE}"
    echo "数据更新失败（备份失败）: $(date)" >> "${LOG_FILE}"
    echo "========================================" >> "${LOG_FILE}"
    exit 1
fi
echo "OK: 已备份到 ${BACKUP_FILE}" >> "${LOG_FILE}"

# 清理7天前的备份
find "${PROJECT_ROOT}/data/output/backup" -name "*.json" -mtime +7 -delete >> "${LOG_FILE}" 2>&1

echo "========================================" >> "${LOG_FILE}"
echo "数据更新完成: $(date)" >> "${LOG_FILE}"
echo "========================================" >> "${LOG_FILE}"

exit 0
