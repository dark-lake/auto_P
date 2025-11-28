import uuid
from logger_util import logger
from playwright.async_api import Browser
from MyPage import MyWebpage

class BrowserSession:
    """
    浏览器会话类，负责整个浏览器的生命周期
    """

    def __init__(self, browser: Browser, browser_id: str):
        self.browser = browser
        self.browser_id = browser_id
        self.pages: dict[str, MyWebpage] = {}

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

    async def create_page(self, page_name: str) -> MyWebpage:
        """
        创建一个page页面，必须传入当前页面的名字，用于更好的标识这个页面
        :param page_name: 页面名称
        :return:
        """
        page = await self.browser.new_page()
        my_page = MyWebpage(str(uuid.uuid4()), page_name, page)
        self.pages[my_page.page_id]  = my_page
        logger.info(f'创建于浏览器会话ID为{self.browser_id}的页面{my_page.page_id}成功')
        return my_page


    async def get_page_by_id(self, page_id: str) -> MyWebpage|None:
        """
        通过page_id来返回指定的页面对象
        :param page_id: 页面id
        :return:
        """
        return self.pages.get(page_id, None)




if __name__ == '__main__':
    a = BrowserSession(browser=None, browser_id='chrome')
    a.close()
