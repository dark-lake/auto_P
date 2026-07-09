import asyncio
import json
import os
import re
import uuid
from datetime import datetime

import aiofiles
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.types import CallToolResult
from openai.types.beta.threads.runs import ToolCall

from auto_p_llm.doubao_file import doubao_upload_file
from auto_p_services.chrome_mcp.page_tools import PageTools
from auto_p_utils.config import config
from auto_p_utils.logger_util import logger
from auto_p_utils.os_util import save_file

load_dotenv()


class ChromeTools:
    def __init__(self, server: ClientSession):
        self.server = server  # mcp 服务
        self.page_tools = None  # 页面工具

    async def invoke_tool(
            self,
            tool_call: ToolCall
    ) -> CallToolResult:
        """
        实际调用mcp工具
        :param tool_call: 工具调用对象
        :return: 工具调用结果对象
        """

        # 初始化页面工具
        if not self.page_tools:
            self.page_tools = PageTools(self.server)

        # 获取工具调用数据
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)

        print(f'tool_arags: {type(tool_args)}\n{tool_args}')

        # 特殊类型的工具单独处理,例如截图
        if tool_name in ['take_screenshot']:
            tool_call_result = await self.take_screenshot_process(tool_name, tool_args)
        else:
            tool_call_result = await self.server.call_tool(tool_name, tool_args)

        tool_call_result_content = tool_call_result.content[0] if tool_call_result.content else None

        if not tool_call_result_content:
            return tool_call_result

        # 移除A11Y中的所有URL
        if tool_call_result_content.type == 'text':
            tool_call_result_content.text = await remove_urls(tool_call_result_content.text)

        # 添加当前页面列表
        if tool_name not in ['list_pages', 'new_page', 'navigate_page', 'select_page', 'close_page']:
            tool_call_result_content.text = await self.append_page_list(tool_call_result_content.text)

        return tool_call_result

    async def take_screenshot_process(self, tool_name, tool_args) -> CallToolResult:
        """处理截图工具调用,需要特殊处理, 1.保存图片,2.重构"""

        new_tool_args = {}
        # 设置截图保存的默认参数
        file_path = os.path.join(config.img_path, str(uuid.uuid4().hex))
        format = "jpeg"
        full_page = False
        quality = 65
        # uid 忽略

        new_tool_args['filePath'] = file_path
        new_tool_args['format'] = format
        new_tool_args['fullPage'] = full_page
        new_tool_args['quality'] = quality
        tool_invoke_result = await self.server.call_tool(tool_name, new_tool_args)
        print(f'截图调用结果:{tool_invoke_result}')

        # 上传云平台
        file_id = await doubao_upload_file(file_path + '.' + format)
        print(f'上传后ID为:{file_id}')

        # 修改call_result中的值
        tool_invoke_result.content[0].text = file_id
        print(f'截图调用结果:{tool_invoke_result}')
        return tool_invoke_result

    async def append_page_list(
            self,
            text_content: str
    ) -> str:
        """
        拼接当前页面列表到工具结果末尾
        :param text_content: 工具调用结果的文本内容
        :return: 工具调用结果+当前页面列表
        """
        # 如果有新页面打开,把当前所有页面列表也发给大模型
        if await self.page_tools.has_new_page():
            # 直接构建JSON数组而不是使用model_dump_json后再json.dumps
            page_list = [page.model_dump_json() for page in self.page_tools.pages]
            text_content += f'\n## 当前已打开的页面列表\n{','.join(page_list)}'
        return text_content


async def remove_urls(
        a11y_text: str
) -> str:
    """
    移除A11Y中的所有URL
    :param a11y_text: 具有a11y结构的字符串
    :return: 工具调用结果对象
    """

    origin_length = len(a11y_text)
    resp_and_a11y_text = a11y_text.split("\n## Latest page snapshot\n")
    if len(resp_and_a11y_text) > 1:
        # 对a11y文本进行移除URL
        logger.info(f'移除URL前长度:{origin_length}')
        resp_and_a11y_text[1] = lightweight_ally(resp_and_a11y_text[1])
        a11y_text = '\n## Latest page snapshot\n'.join(resp_and_a11y_text)
        curr_length = len(a11y_text)
        logger.info(
            f'移除URL后长度:{curr_length},缩减了{str(round(((origin_length - curr_length) / origin_length) * 100, 2))}%')
    return a11y_text


def remove_urls_from_text(
        text: str
) -> str:
    """从文本中移除所有URL"""
    # 匹配URL的正则表达式
    url_pattern = r'url="[^"]*"'
    return re.sub(url_pattern, '', text)


async def remove_urls_from_snapshot_file(
        file_path: str
) -> None:
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


def to_parent_uid_format(
        lines: list[str]
) -> list[str]:
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


def lightweight_ally(
        ally_text: str
) -> str:
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
