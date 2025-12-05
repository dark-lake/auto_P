import uuid
from typing import Optional

from playwright.async_api import Browser, BrowserContext

from auto_p_utils.logger_util import logger
from .MyPage import MyWebpage


class MyBrowserContext:
    def __init__(self, browser: Browser, browser_context_id: str, browser_context: BrowserContext) -> None:
        self.browser = browser
        self.id = browser_context_id
        self.browser_context = browser_context
        self.pages: dict[str, 'MyWebpage'] = {}

    async def create_page(self, page_name: str) -> 'MyWebpage':
        """
        通过浏览器上下文对象创建页面
        :param page_name: 页面名称
        :return:
        """
        # from MyPage import MyWebpage  # 运行时导入，避免循环依赖

        page = await self.browser_context.new_page()
        page_id = str(uuid.uuid4())
        my_page = MyWebpage(page_id=page_id, page_name=page_name, page=page, my_browser_context=self)
        self.pages[page_id] = my_page
        logger.info(f'在浏览器会话ID为[{self.id}]的上下文中成功构建了[{page_id}],[{page_name}]页面对象')
        return my_page

    async def add_page(self, page: MyWebpage) -> None:
        """
        添加页面对象
        :param page: 页面对象
        :return:
        """
        self.pages[page.page_id] = page

    async def get_page_by_name(self, page_name: str) -> Optional['MyWebpage']:
        """
        通过页面名称获取页面对象
        :param page_name: 页面名称
        :return: 页面对象
        """
        for page in self.pages.values():
            if page.page_name == page_name:
                return page
        return None

    async def get_page_id_by_name(self, page_name: str) -> str | None:
        """
        通过page_name获取对应的page_id
        :param page_name: 页面名称
        :return: 页面ID
        """
        for page_id, page in self.pages.items():
            if page.page_name == page_name:
                return page_id
        return None

    async def get_page_by_id(self, page_id: str) -> 'MyWebpage':
        """
        获取指定ID的页面对象
        :param page_id: 页面ID
        :return:
        """
        return self.pages.get(page_id, None)

    async def get_all_page_names(self) -> list[str]:
        """
        获取所有页面名称
        :return:
        """
        return [page.page_name for page in self.pages.values()]

    async def remove_page(self, page_id: str) -> Optional['MyWebpage']:
        """
        删除指定ID的页面对象
        :param page_id: 页面ID
        :return:
        """
        return self.pages.pop(page_id, None)

    async def close(self):
        try:
            await self.browser_context.close()
            logger.info(f'{self.id} 浏览器上下文已关闭')
        except Exception as e:
            logger.exception(f'{self.id} 浏览器上下文关闭失败', e)


class BrowserContextManager:
    """
    负责管理浏览器的上下文
    """

    def __init__(self) -> None:
        self.browser = None
        self.browser_contexts: dict[str, MyBrowserContext] = {}

    async def set_browser(self, browser: Browser) -> None:
        self.browser = browser

    async def add_browser_context(self, browser_context: BrowserContext = None) -> MyBrowserContext:
        """
        新增浏览器上下文对象
        :param browser_context: 当使用本地浏览器时传入,默认使用新建浏览器
        :return:
        """
        if browser_context:
            my_browser_context = MyBrowserContext(
                browser=self.browser,
                browser_context_id=str(uuid.uuid4()),
                browser_context=browser_context
            )
        else:
            if not self.browser:
                raise Exception('请先设置浏览器对象')
            browser_context = await self.browser.new_context()
            my_browser_context = MyBrowserContext(
                browser=self.browser,
                browser_context_id=str(uuid.uuid4()),
                browser_context=browser_context
            )
        self.browser_contexts[my_browser_context.id] = my_browser_context

        return my_browser_context

    async def get_browser_context(self, browser_context_id: str | None = None) -> MyBrowserContext | None:
        """
        获取指定ID的浏览器上下文对象,如果不指定ID,则返回第一个上下文对象
        :param browser_context_id: 浏览器上下文ID
        :return:
        """
        if browser_context_id:
            return self.browser_contexts.get(browser_context_id, None)
        else:
            return next(iter(self.browser_contexts.values()), None)

    async def del_browser_context(self, browser_context_id: str) -> None:
        """
        关闭某个浏览器上下文
        :return:
        """
        try:
            browser_context = self.browser_contexts.get(browser_context_id, None)
            if not browser_context:
                await browser_context.close()
        except Exception as e:
            logger.info(f'关闭ID为{browser_context_id}的浏览器上下文过程中出现异常', e)

    async def close_all_context(self):
        """
        关闭所有浏览器上下文对象
        :return:
        """
        try:
            for context in self.browser_contexts.values():
                await context.close()
                logger.info(f'成功关闭浏览器上下文对象-{context.id}')
        except Exception as e:
            logger.exception(f'浏览器上下文关闭过程异常', e)

    async def close_browser(self) -> None:
        """
        关闭浏览器
        :return:
        """
        try:
            await self.close_all_context()
            self.browser_contexts.clear()
            await self.browser.close()
            self.browser = None
            logger.info(f'成功关闭浏览器上下文对象')
        except Exception as e:
            logger.exception(f'浏览器上下文关闭过程异常', e)


browser_context_manager = BrowserContextManager()

__all__ = ['browser_context_manager', 'MyBrowserContext']
