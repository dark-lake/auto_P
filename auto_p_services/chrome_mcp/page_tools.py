from dotenv import load_dotenv
from mcp import ClientSession
from mcp.types import CallToolResult
from pydantic import BaseModel, Field

from auto_p_utils.logger_util import logger

load_dotenv()


class AutoPPage(BaseModel):
    index: str = Field(..., description="页面索引")
    title: str = Field(..., description="页面标题")
    url: str = Field(..., description="页面url")
    is_selected: bool = Field(False, description="是否被选中")


class PageTools:
    """
    负责处理chrome mcp中页面相关的一些处理
    """

    def __init__(
            self,
            session: ClientSession
    ):
        self.pages: list[AutoPPage] = []
        self.session = session

    async def has_new_page(self) -> bool:
        """
        检查是否有新的页面增加
        :return: 1.是否新增,2.当前页面列表
        """
        all_pages = await self.session.call_tool("list_pages", {})
        build_pages_res = build_page(all_pages)
        logger.info(f'新加入了{len(build_pages_res) - len(self.pages)}个页面')
        for page in build_pages_res:
            logger.info(f"页面URL:{page.url},是否选中{page.is_selected}")
        if len(build_pages_res) > len(self.pages):
            self.pages = build_pages_res
            return True
        return False

    async def get_page_title(self):
        """
        获取当前页面的标题
        :return:
        """
        arg = {
            "function": "() => { return document.title }"
        }
        title_res = await self.session.call_tool("evaluate_script", arg)
        if title_res.content:
            title = title_res.content[0].text
            logger.info(f'页面标题为: {title}')


def build_page(
        list_pages_result: CallToolResult
) -> list[AutoPPage]:
    """
    将工具调用结果转为page对象
    :param list_pages_result:
    :return: Page对象
    """
    logger.info(f'开始转换页面结果...')
    build_pages = []
    if list_pages_result.content:
        # text='# list_pages response\n## Pages\n0: https://www.bilibili.com/\n1: https://www.baidu.com/ [selected]
        str_res = list_pages_result.content[0].text
        page_list = str_res.split('\n')[2:]  # 排除掉前两个标题部分
        for page in page_list:
            # 1: https://www.baidu.com/ [selected]
            split_page = page.split(' ')
            index = split_page[0][0]
            url = split_page[1].strip()
            is_selected = False
            if len(split_page) > 2 and split_page[2].strip() == '[selected]':
                is_selected = True
            # 添加page对象
            build_pages.append(AutoPPage(index=index, title=url, url=url, is_selected=is_selected))
    return build_pages


def parse_a11y_line(
        line: str
) -> dict:
    """
    解析A11Y的每一行,获取指定的值
    :param line:
    :return:
    """
    import re
    m = re.search(
        r'uid=(\S+)\s+(\w+)\s+"([^"]+)"(?:\s+url="([^"]+)")?',
        line
    )
    if not m:
        return {}

    return {
        "uid": m.group(1),
        "role": m.group(2),
        "name": m.group(3),
        "url": m.group(4) or ""
    }


if __name__ == '__main__':
    a = AutoPPage(
        index='1',
        title='1',
        url='1',
        is_selected=True
    )

    print(a.model_dump_json())
