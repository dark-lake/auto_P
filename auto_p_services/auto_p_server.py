from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult

load_dotenv()

mcp = FastMCP("Auto_P Server")


@mcp.tool(
    name="pause_and_wait",
    description=(
            "当前任务无法继续、需要用户提供额外信息或确认某个操作时调用。本工具会暂停程序执行，"
            "等待用户输入或确认后再继续。如果模型在执行步骤时遇到不确定情况，例如："
            "需要用户提供参数、需要人工检查某个元素是否存在、需要确认下一步是否继续，"
            "或任务本身要求用户做出选择时，应调用本工具。"
    )
)
async def pause_and_wait(pause_reason: str, input_required: bool = True) -> str:
    """
    暂停当前流程以等待用户参与。例如需要用户手动检查页面内容、确认某个行为是否执行、
    或提供继续下一步所需的输入。在 pause_reason 中清晰描述暂停原因或需要的用户操作。

    :param pause_reason: 说明暂停目的，例如“请告诉我要搜索的关键词”或“请确认是否继续点击按钮”。
    :param input_required: 如果需要用户输入内容则为 True；如果只需要用户点击确认继续，则为 False。
    :return: 用户输入的内容，或空字符串（当 input_required=False 时）。
    """
    pass


@mcp.tool(
    name="tool_search",
    description="根据工具描述搜索工具,获取该工具的具体json schema"
)
async def tool_search(tool_description: str) -> str:
    """
    更具对工具的描述去搜索具体的工具
    :param tool_description: 工具描述
    :return: 该工具的json schema
    """
    pass


@mcp.tool(
    name="get_tool_schema",
    description="根据工具名称检索并获取对应工具的完整 JSON Schema，且工具名称必须严格来源于轻量化工具列表"
)
async def get_tool_schema(tool_name: str) -> str:
    """
    获取工具json schema
    :param tool_name: 工具名称
    :return: 工具json schema
    """
    pass


async def unified_output_func(tool_name: str, args: list[Any], output: CallToolResult) -> dict:
    """
    统一处理工具返回格式
    :param tool_name: 工具名称
    :param args: 入参
    :param output: 输出
    :return: 统一后返回格式
    """
    pass


async def test():
    pass


if __name__ == "__main__":
    # 设置环境变量标识这是 MCP server 模式
    import os

    os.environ['MCP_SERVER_MODE'] = '1'

    # Initialize and run the server
    mcp.run(transport='stdio')

    # asyncio.run(test())
