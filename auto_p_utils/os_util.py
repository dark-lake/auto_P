import json
import os
import sys
from typing import Dict, Any

from mcp.types import Tool

from auto_p_exceptions.MyBaseException import MyBaseException, MyBaseExceptionCode
from auto_p_utils.logger_util import logger


def get_os() -> int:
    """
    获取系统类型, 0-macos, 1-linux, 2-windows, -1-识别失败
    """
    if sys.platform.startswith('darwin'):
        return 0
    elif sys.platform.startswith('linux'):
        return 1
    elif sys.platform.startswith('win'):
        return 2
    return -1


def format_keyboard_key(key: str) -> str:
    """
    格式化键盘按键, 使得返回的都是符合playwright要求的格式
    :param key: 按键名称, 可以用+来构建快键键,比如 Shift+1 即为 !
    :return: 格式化后的按键名称
    """
    if '+' not in key:
        # 如果开头第一个是字母,就转成大写
        key = do_format_key(key)
    else:
        key1, key2 = key.split('+')
        key1 = do_format_key(key1)
        key2 = do_format_key(key2)
        key = key1 + '+' + key2

    return key


def do_format_key(key: str) -> str:
    """
    处理单个键盘key,变为大驼峰,以及四个特殊情况
    :param key:
    :return:
    """
    special_keys = ['arrowup', 'arrowdown', 'arrowleft', 'arrowright']
    os_type = get_os()  # 获取系统类型
    if key.lower() in special_keys:
        key = (key[:5]).capitalize() + (key[5:]).capitalize()
    else:
        key = key.capitalize()

    if key == 'Command' and os_type == 0:
        key = 'Meta'
    elif key == 'Option' and os_type == 0:
        key = 'Alt'

    return key


async def get_config(file_path: str) -> dict:
    """
    获取.json格式的配置文件内容
    :param file_path: .json配置文件路径
    :return:
    """
    import aiofiles
    if not os.path.exists(file_path):
        logger.info(f'配置文件不存在: {file_path}')
        raise MyBaseException(MyBaseExceptionCode.CONFIG_NOT_EXIST, f'配置文件{file_path}不存在')
    async with aiofiles.open(file_path, 'r') as f:
        config = await f.read()
        return json.loads(config)


def convert_tool(tool: Tool, fmt: str = "responses") -> Dict[str, Any]:
    """将 MCP Tool 转换为 OpenAI function schema。

    Args:
        tool: MCP 工具对象
        fmt: 输出格式
            - "responses": 用于 OpenAI Responses API (平铺格式)
            - "chat": 用于 chat.completions API (嵌套格式)

    Returns:
        转换后的 function schema 字典
    """
    name = getattr(tool, "name", "")
    description = getattr(tool, "description", "")
    input_schema = getattr(tool, "inputSchema", {}) or {}

    schema_type = input_schema.get("type", "object")
    properties = {}
    for k, v in input_schema.get("properties", {}).items():
        v_type = v.get("type", "string") if isinstance(v, dict) else "string"
        v_desc = v.get("title", "") if isinstance(v, dict) else ""
        properties[k] = {"type": v_type, "description": v_desc}
    required = input_schema.get("required", [])

    params = {
        "type": schema_type,
        "properties": properties,
        "required": required,
    }

    if fmt == "chat":
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": params,
            },
        }
    # 默认 Responses API 平铺格式
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": params,
    }


async def save_file(file_path: str, content: str) -> None:
    """
    保存文件
    :param file_path: 文件路径
    :param content: 文件内容
    :return:
    """
    import aiofiles
    import os
    # 确保目录存在
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    
    async with aiofiles.open(file_path, "w", encoding='utf-8') as f_in:
        await f_in.write(content)
