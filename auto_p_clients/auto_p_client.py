import asyncio

from dotenv import load_dotenv

from auto_p_agents.AutoPAgent import AutoProcessAgent
from auto_p_services.McpServiceManager import McpServiceManager
from auto_p_services.mcp_services_config import mcp_service_manager
from auto_p_utils.logger_util import logger

load_dotenv()


async def connect_by_config(client: AutoProcessAgent):
    """
    通过mcp_service_config.py中配置的mcp服务进行链接
    :return:
    """
    mcp_service_list: list[McpServiceManager.McpService] = mcp_service_manager.get_mcp_services()
    for service in mcp_service_list:
        logger.info(f"开始链接服务: {service.name}")
        await client.connect_to_server(mcp_service=service)
        logger.info(f"成功链接到 {service.name} 服务!")


async def main():
    client = AutoProcessAgent()
    try:
        await connect_by_config(client)
        # 初始化工具搜索器
        await client.init_tool_searcher()
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
