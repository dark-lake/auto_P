import asyncio
import os

from dotenv import load_dotenv

from auto_p_agents.AutoPAgent import AutoProcessAgent
from auto_p_utils.logger_util import logger

load_dotenv()  # load environment variables from .env


async def main():
    client = AutoProcessAgent()
    try:
        browser_p_server = os.getenv("BROWSER_P_SERVER")
        logger.info(f"Connecting to server: {browser_p_server}")
        await client.connect_to_server('chrome_server', browser_p_server)
        logger.info(f"Connected to {browser_p_server} server!")
        await client.chat_loop()
    finally:
        await client.cleanup()
        # 关闭日志
        await logger.complete()


if __name__ == "__main__":
    import sys

    print(sys.path)
    asyncio.run(main())
