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

logger.add(
    LOG_FILE_PATH,
    rotation="00:00",
    retention="7 days",
    enqueue=True,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    mode='a'
)

# logger.add(
#     sys.stdout,
#     enqueue=True,
#     format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
# )

__all__ = ["logger"]