import asyncio

from dotenv import load_dotenv, dotenv_values

from auto_p_agents.AutoPAgent import AutoProcessAgent
from auto_p_utils.logger_util import logger

load_dotenv()  # load environment variables from .env


async def connect(client: AutoProcessAgent):
    # 读取所有变量（字典）
    env_dict = dotenv_values("/Users/macbook0000/PycharmProjects/auto_P/.env")
    print(env_dict)
    for key, value in env_dict.items():
        if key.endswith('_SERVER'):
            logger.info(f"开始链接服务: {key}")
            await client.connect_to_server(name=key, server_script_path=value)
            logger.info(f"成功链接到 {key} 服务!")


async def main():
    client = AutoProcessAgent()
    try:
        await connect(client)
        # 等待connect日志打印完成
        await asyncio.sleep(1)
        await client.chat_loop()
    except Exception as e:
        logger.error(e)
    finally:
        await client.cleanup()
        # 关闭日志
        await logger.complete()


if __name__ == "__main__":
    import sys

    print(sys.path)
    asyncio.run(main())
