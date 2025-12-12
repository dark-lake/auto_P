import datetime
import os
import sys

from loguru import logger

LOG_DIR = "../logs"
os.makedirs(LOG_DIR, exist_ok=True)

TODAY = datetime.datetime.now().strftime("%Y_%m_%d")

LOG_FILE_PATH = os.path.join(LOG_DIR, f"log_{TODAY}.log")

# 移除默认的日志输出
logger.remove()

# 始终添加文件日志
logger.add(
    LOG_FILE_PATH,
    rotation="00:00",
    retention="7 days",
    enqueue=True,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    mode='a',
    encoding='utf-8'
)

# 检查是否作为 MCP server 运行 (通过 stdio 通信)
# 如果不是 MCP server，则添加 stdout 输出
# MCP server 通过 stdio 通信，不能将日志输出到 stdout，否则会干扰 JSON-RPC 消息
if not os.getenv('MCP_SERVER_MODE'):
    logger.add(
        sys.stderr,  # 使用 stderr 而不是 stdout，避免干扰 stdio 通信
        enqueue=True,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )

__all__ = ["logger"]