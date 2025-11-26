import uuid
from logger_util import logger
from playwright.async_api import Browser, Page, Response



class MyPage:
    def __init__(self, page_id: str, page_name: str, page: Page) -> None:
        self.page_id = page_id
        self.page_name = page_name
        self.page = page

    async def goto(self, url: str) -> Response:
        return await self.page.goto(url)

    async def close(self):
        try:
            await self.page.close()
            logger.info(f'{self.page_id}-{self.page_name} 页面已关闭')
        except Exception as e:
            logger.exception(f'{self.page_id}-{self.page_name} 页面关闭异常', e)


class BrowserSession:
    """
    浏览器会话类，负责整个浏览器的生命周期
    """

    def __init__(self, browser: Browser, browser_id: str):
        self.browser = browser
        self.browser_id = browser_id
        self.pages: list[MyPage] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.exception(exc_type, exc_val, exc_tb)
        logger.info(f'浏览器ID为：{self.browser_id} 已关闭')
        # True 表示抑制异常，False表示传播异常
        return False

    async def close(self):
        try:
            if self.browser.is_connected():
                await self.browser.close()
            logger.info(f'浏览器ID为：{self.browser_id} 已关闭')
        except Exception as e:
            logger.exception(f'浏览器关闭异常', e)

    async def create_page(self, page_name: str) -> MyPage:
        """
        创建一个page页面，必须传入当前页面的名字，用于更好的标识这个页面
        :param page_name: 页面名称
        :return:
        """
        page = await self.browser.new_page()
        my_page = MyPage(str(uuid.uuid4()), page_name, page)
        self.pages.append(my_page)
        return my_page






if __name__ == '__main__':
    a = BrowserSession(browser=None, browser_id='chrome')
    a.close()
