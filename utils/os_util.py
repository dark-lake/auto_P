import json
import os
import sys

from utils.logger_util import logger


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
        return {}
    async with aiofiles.open(file_path, 'r') as f:
        config = await f.read()
        return json.loads(config)
