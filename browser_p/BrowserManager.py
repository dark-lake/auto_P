from BrowserSession import BrowserSession
from utils.logger_util import logger


class BrowserManager:
    """
    负责管理所有浏览器实例对象
    """

    def __init__(self):
        self.browser_session_list: list[BrowserSession] = []

    async def add_browser_session(self, browser_session: BrowserSession) -> None:
        """
        新增浏览器会话对象
        :param browser_session:
        :return:
        """
        self.browser_session_list.append(browser_session)

    async def get_browser_session_list(self) -> list[BrowserSession]:
        """
        获取浏览器会话对象列表
        :return:
        """
        return self.browser_session_list

    async def get_browser_session_by_id(self, browser_session_id: str) -> BrowserSession | None:
        """
        通过浏览器会话ID获取指定的浏览器会话对象
        :param browser_session_id: 浏览器会话ID
        :return:
        """
        for browser in self.browser_session_list:
            if browser.browser_id == browser_session_id:
                return browser
        return None

    async def close_browser_session(self, browser_session_ids: list[str] = []) -> None:
        """
        关闭浏览器，若不传入browser_session_ids，则默认关闭所有浏览器
        :param browser_session_ids: 要关闭的浏览器会话ID列表
        :return:
        """
        try:
            if browser_session_ids:
                for browser_session in self.browser_session_list:
                    if browser_session.browser_id in browser_session_ids:
                        await browser_session.browser.close()
            else:
                for browser_session in self.browser_session_list:
                    await browser_session.close()
        except Exception as e:
            logger.exception(e)

    async def get_all_browser_session_id(self) -> list[str]:
        """
        获取所有的浏览器会话ID列表
        :return:
        """
        return [browser.browser_id for browser in self.browser_session_list]




browser_context = BrowserManager()

if __name__ == '__main__':
    b = BrowserManager()