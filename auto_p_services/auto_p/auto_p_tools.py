import json
import os
from datetime import datetime

from mcp.server.fastmcp.tools import Tool
from mcp.types import CallToolResult
from openai.types.beta.threads.runs import ToolCall

from auto_p_utils.logger_util import logger
from auto_p_utils.os_util import convert_tool


async def build_tool_result(result: str | list, tool_call: ToolCall) -> CallToolResult:
    # 工具名称
    return CallToolResult(
        content=[],
        structuredContent={
            "type": "text" if isinstance(result, str) else "list",
            "tool_name": tool_call.function.name,
            "result": result
        }
    )


async def do_get_tool_schema(agent: 'AutoProcessAgent', tool_call: ToolCall) -> CallToolResult:
    """
    获取tool_names各工具的json schema
    :param tool_call: 模型返回的工具调用对象
    :param agent: auto_p_agent对象, 字典格式
    :return: 工具的json schema
    """
    # 参数
    tool_args = json.loads(tool_call.function.arguments)
    # 所需工具列表
    need_tool_names: list[str] = tool_args.get('tool_names', '')
    # 获取所需工具对象
    need_tools: list[Tool] = await agent.get_tool_from_session(set(need_tool_names))
    if not need_tools:
        logger.info(f'未找到工具:{need_tool_names}')
        result = f'未找到工具:{need_tool_names}'
    else:
        logger.info(f'模型成功获取到工具:{need_tool_names}的json schema')
        result = [convert_tool(tool, fmt="chat") for tool in need_tools]
    return await build_tool_result(result, tool_call)


async def do_wait_for_user_input(agent: 'AutoProcessAgent', tool_call: ToolCall) -> CallToolResult:
    """向用户提问并结束当前轮对话。

    不再阻塞等待——直接返回 pause_reason 作为工具结果，
    模型收到后会输出文本回复给用户，本轮对话自然结束。
    用户下次输入时开启新一轮对话。

    :param tool_call: 模型返回的工具调用对象
    :param agent: AutoProcessAgent 实例
    :return: pause_reason 作为工具结果
    """
    tool_args = json.loads(tool_call.function.arguments)
    pause_reason = tool_args.get('pause_reason', '未知原因')
    logger.info(f"Agent 向用户提问: {pause_reason}")
    return await build_tool_result(
        f"已向用户提问: {pause_reason}。请直接用文字回复用户的问题，然后结束本轮对话。",
        tool_call,
    )


async def do_tool_search(agent: 'AutoProcessAgent', tool_call: ToolCall) -> CallToolResult:
    """
    实际的搜索工具方法, 通过向量匹配的方式
    :param tool_call: 模型返回的工具调用对象
    :param agent: auto_p_agent对象, 字典格式
    :return: 工具的schema
    """

    # 检查是否开启工具搜索
    if not os.getenv('ENABLE_TOOL_SEARCH', 'false') == 'true':
        return await build_tool_result("用户未开启工具搜索模式,请先让用户开启工具搜索模式", tool_call)

    # 参数
    tool_args = json.loads(tool_call.function.arguments)
    tool_description = tool_args.get('tool_description', None)

    if not tool_description:
        result = f'参数tool_description不能为空,tool_description={tool_description}'
        return await build_tool_result(result, tool_call)

    if not agent.tool_searcher:
        logger.exception(f'tool_searcher未初始化,无法进行工具搜索')
        return await build_tool_result(f'tool_searcher未初始化,无法进行工具搜索,请尝试别的方式或请求用户操作',
                                       tool_call)
    # 小于等于3个匹配到的工具对象
    tools = await agent.tool_searcher.search(
        query=tool_description,
    )
    logger.info(f'搜索到如下工具: {[t.name for t in tools]}')
    tool_json_schema: list[dict] = [convert_tool(tool, fmt="chat") for tool in tools]
    if not tool_json_schema:
        return await build_tool_result(f'未搜索到任何工具,请检查工具描述是否正确,tool_description={tool_description}',
                                       tool_call)
    return await build_tool_result(tool_json_schema, tool_call)


async def do_get_time_now(agent: 'AutoProcessAgent', tool_call: ToolCall) -> CallToolResult:
    """
    获取当前系统时间
    :param tool_call: 模型返回的工具调用对象
    :param agent: auto_p_agent对象, 字典格式
    :return: 当前系统时间
    """
    now = datetime.now()
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    # 2026-07-10 23:15:42
    return await build_tool_result(f'当前系统时间为:{time_str}', tool_call)

# 方法,方法名,描述
special_methods = {
    "get_tool_schema": do_get_tool_schema,
    "wait_for_user_input": do_wait_for_user_input,
    "tool_search": do_tool_search,
    "get_time_now": do_get_time_now,
}

if __name__ == "__main__":
    pass
