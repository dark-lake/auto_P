import asyncio
import json
import os
import platform
import re
import subprocess
from datetime import datetime

import aiofiles
from mcp.server.fastmcp.tools import Tool
from mcp.types import CallToolResult
from openai.types.beta.threads.runs import ToolCall

from auto_p_utils.logger_util import logger
from auto_p_utils.os_util import save_file, convert_tool


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
    return await build_tool_result(result, tool_call)


async def do_wait_for_user_input(agent: 'AutoProcessAgent', tool_call: ToolCall) -> CallToolResult:
    """
    等待用户输入
    :param tool_call: 模型返回的工具调用对象
    :param agent: auto_p_agent对象, 字典格式
    :return: 用户输入
    """
    # 参数
    tool_args = json.loads(tool_call.function.arguments)
    # 暂停原因
    pause_reason = tool_args.get('pause_reason', None)
    print("模型要求暂停 → 等待你的操作")
    print(f"暂停原因:{pause_reason}")

    # 根据操作系统类型选择合适的GUI方法
    def get_input_with_gui() -> str:
        system = platform.system()

        # macOS系统使用AppleScript
        if system == "Darwin":  # macOS的platform.system()返回"Darwin"
            try:
                # 构造AppleScript命令
                script = f'''
                display dialog "暂停原因: {pause_reason}
请输入你的操作指令:" default answer "" with title "用户输入" with icon note
                '''
                # 执行AppleScript
                result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, check=True)
                # 解析结果，AppleScript返回格式为：button returned:OK, text returned:用户输入的内容
                output = result.stdout.strip()
                if 'text returned:' in output:
                    # 提取用户输入的内容
                    user_input = output.split('text returned:')[-1]
                    return user_input
                return ""
            except subprocess.CalledProcessError as e:
                # AppleScript执行失败，回退到控制台输入
                print(f"AppleScript对话框失败 ({str(e)})，回退到控制台输入")
                return input(f"暂停原因: {pause_reason}\n请输入你的操作指令:")
            except Exception as e:
                # 其他异常，也回退到控制台输入
                print(f"GUI输入失败 ({str(e)})，回退到控制台输入")
                return input(f"暂停原因: {pause_reason}\n请输入你的操作指令:")

        # Windows系统使用PowerShell
        elif system == "Windows":
            try:
                # 使用PowerShell创建输入框
                command = (
                    "Add-Type -AssemblyName Microsoft.VisualBasic; "
                    f"$title = \"用户输入\"; "
                    f"$message = \"暂停原因: {pause_reason}\n请输入你的操作指令:\"; "
                    "$result = [Microsoft.VisualBasic.Interaction]::InputBox($message, $title, \"\"); "
                    "Write-Output $result"
                )

                # 执行PowerShell命令
                result = subprocess.run([
                    'powershell', '-Command', command
                ], capture_output=True, text=True, check=True)

                user_input = result.stdout.strip()
                return user_input
            except subprocess.CalledProcessError as e:
                # PowerShell执行失败，回退到控制台输入
                print(f"PowerShell对话框失败 ({str(e)})，回退到控制台输入")
                return input(f"暂停原因: {pause_reason}\n请输入你的操作指令:")
            except Exception as e:
                # 其他异常，也回退到控制台输入
                print(f"GUI输入失败 ({str(e)})，回退到控制台输入")
                return input(f"暂停原因: {pause_reason}\n请输入你的操作指令:")

        # 其他系统或未识别系统，直接使用控制台输入
        else:
            return input(f"暂停原因: {pause_reason}\n请输入你的操作指令:")

    loop = asyncio.get_event_loop()
    try:
        user_input = await loop.run_in_executor(None, get_input_with_gui)
    except Exception:
        # 最后的回退方案
        user_input = await loop.run_in_executor(None, input, f"暂停原因: {pause_reason}\n请输入你的操作指令:")

    return await build_tool_result(user_input, tool_call)


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
        k=os.getenv('TOOL_SEARCH_K', 3)
    )
    logger.info(f'搜索到如下工具: {[t.name for t in tools]}')
    tool_json_schema: list[dict] = [convert_tool(tool) for tool in tools]
    if not tool_json_schema:
        return await build_tool_result(f'未搜索到任何工具,请检查工具描述是否正确,tool_description={tool_description}',
                                       tool_call)
    return await build_tool_result(tool_json_schema, tool_call)


# 方法,方法名,描述
special_methods = {
    "get_tool_schema": do_get_tool_schema,
    "wait_for_user_input": do_wait_for_user_input,
    "tool_search": do_tool_search,
}

if __name__ == "__main__":
    asyncio.run(remove_urls_from_snapshot_file("../../auto_p_clients/take_snapshot.json"))