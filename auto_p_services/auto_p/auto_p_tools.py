import asyncio
import os
import re
from datetime import datetime

import aiofiles

from auto_p_utils.logger_util import logger
from auto_p_utils.os_util import save_file


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


if __name__ == "__main__":
    asyncio.run(remove_urls_from_snapshot_file("../../auto_p_clients/take_snapshot.json"))
