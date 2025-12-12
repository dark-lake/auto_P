import asyncio
import json
import os
import re
from datetime import datetime

import aiofiles
from mcp.server.fastmcp.tools import Tool
from mcp.types import CallToolResult
from openai.types.beta.threads.runs import ToolCall

from auto_p_utils.logger_util import logger
from auto_p_utils.os_util import save_file, convert_tool


def remove_urls_from_text(text: str) -> str:
    """从文本中移除所有URL"""
    # 匹配URL的正则表达式
    url_pattern = r'url="[^"]*"'
    return re.sub(url_pattern, '', text)


async def remove_urls_from_snapshot_file(file_path: str) -> None:
    """异步方法：从take_snapshot.json文件中移除所有URL"""
    try:
        # 异步读取文件
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
            content = await file.read()

        # 移除所有URL
        cleaned_content = remove_urls_from_text(content)

        # 异步写回文件
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as file:
            await file.write(cleaned_content)

        print(f"成功从 {file_path} 中移除所有URL")
    except Exception as e:
        print(f"处理文件时出错: {e}")
        raise


def to_parent_uid_format(lines):
    """转为parent id 模式"""
    pattern = re.compile(r'^\s*')  # leading spaces
    node_pattern = re.compile(r'uid=(\S+)\s+(\S+)(?:\s+"([^"]*)")?')
    stack = {}
    output = []

    for line in lines:
        if not line.strip():
            continue
        indent = len(pattern.match(line).group(0))
        depth = indent // 2
        m = node_pattern.search(line)
        if not m:
            continue
        uid, role, text = m.group(1), m.group(2), m.group(3) or ""
        parent_uid = stack.get(depth - 1) if depth > 0 else None
        stack[depth] = uid
        output.append(f"{uid} {role} {text} parent={parent_uid}")

    return output


async def lightweight_ally(ally_text: str) -> str:
    """轻量级Ally，将 ally_text 中的 URL 移除"""
    try:
        timestamp = int(datetime.now().timestamp())
        file_in = os.path.join(os.getenv("A11Y_TXT_PATH"), str(timestamp) + "_in.json")
        file_out = os.path.join(os.getenv("A11Y_TXT_PATH"), str(timestamp) + "_out.json")
        # 移除所有URL
        cleaned_content = remove_urls_from_text(ally_text)
        # 转换为parent_uid格式
        res = '\n'.join(to_parent_uid_format(cleaned_content.split("\n")))

        # 保存两个修改前后的a11y文本内容
        asyncio.create_task(save_file(file_in, ally_text))
        asyncio.create_task(save_file(file_out, res))

        return res
    except Exception as e:
        logger.error(f'处理ally_text时出错: {e}')
        raise


async def do_get_tool_schema(agent: 'AutoProcessAgent', tool_call: ToolCall) -> CallToolResult:
    """
    获取tool_names各工具的json schema
    :param tool_call: 模型返回的工具调用对象
    :param agent: auto_p_agent对象, 字典格式
    :return: 工具的json schema
    """
    # 工具名称
    tool_name = tool_call.function.name
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
        result = [convert_tool(tool) for tool in need_tools]
    return CallToolResult(
        content=[],
        structuredContent={
            "type": "get_tool_schema",
            "tool_name": tool_name,
            "result": result
        }
    )


if __name__ == "__main__":
    asyncio.run(remove_urls_from_snapshot_file("../../auto_p_clients/take_snapshot.json"))
