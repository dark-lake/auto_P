from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright, Browser
from BrowserSession import BrowserSession
import asyncio
from logger_util import logger
import uuid
from BrowserContext import browser_context

mcp = FastMCP("Chrome_Browser Server")

@mcp.tool(
    name="open_browser",
    description="Open a browser and return a session ID",
)
async def open_browser() -> str:
    """
    Open a browser and return a session ID.
    """
    # Start Playwright
    playwright = await async_playwright().start()

    # Launch browser
    browser = await playwright.chromium.launch(headless=False)
    browser_id = str(uuid.uuid4())
    browser_session = BrowserSession(browser, browser_id)
    if not browser_session:
        logger.info(f'浏览器上下午对象未创建')
        return f'浏览器上下文对象未创建，流程终止'
    logger.info(f'浏览器上下文对象创建成功')
    await browser_context.add_browser_session(browser_session)
    logger.info(f'浏览器会话对象创建成功')
    return f'浏览器会话启动成功,会话id为：{browser_id}'


@mcp.tool(
    name="close_browser",
    description="Close the browser. If browser_session_ids is not passed in, all browsers will be closed by default",
)
async def close_browser(browser_id_list: list[str] = []) -> str:
    """
    关闭浏览器
    """
    if browser_context:
        await browser_context.close_browser_session(browser_id_list)
        return '关闭成功'
    else:
        logger.info(f'浏览器上下文对象为:{browser_context},无法关闭浏览器会话:{browser_id_list}')
        return '关闭失败'


@mcp.tool(
    name="get_browser_session_id",
    description="Get all browser session ID",
)
async def get_all_browser_session_id() -> list[str]:
    """
    获取所有的浏览器会话ID
    :return:
    """
    if not browser_context:
        logger.info(f'浏览器上下文对象为:{browser_context},无法获取所有浏览器会话ID列表')
        return []

    return await browser_context.get_all_browser_session_id()


@mcp.tool(
    name="goto_page",
    description="Let the browser session access the given url",
)
async def goto_page(url: str, browser_session_id: str, page_name: str) -> str:
    """
    打开指定页面
    :param page_name: 页面的名字，用于更好的标识一个页面
    :param browser_session_id: 浏览器会话ID，用于唯一确定一个浏览器会话
    :param url: 页面url
    :return:
    """
    if not browser_context:
        logger.info(f'浏览器上下文对象为:{browser_context},无法获取所有浏览器会话ID列表')
        return f'浏览器上下文对象异常'

    browser_session = await browser_context.get_browser_session_by_id(browser_session_id)
    if not browser_session:
        logger.info(f'未获取到browser_session_id为:{browser_session_id}的会话')
        return f'未获取到browser_session_id为:{browser_session_id}的会话'

    page = await browser_session.create_page(page_name=page_name)
    try:
        res = await page.goto(url)
        print(f'页面相应状态为：{res.status}')
        if res.status != 200:
            logger.info(f'{page_name}-{url}页面打开异常：{res.status}')
            return f'{page_name}-{url}页面打开失败'
        else:
            logger.info(f'{page_name}-{url}页面打开成功：{res.status}')
            return f'{page_name}-{url} 页面打开成功'
    except Exception as e:
        logger.error(f'{page_name}-{url}页面访问网络异常',e)
        return f'{page_name}-{url}页面打开失败'


@mcp.tool(
    name="get_page",
    description="Get a page by page id",
)
async def get_page(page_id: str) -> str:
    """
    通过page_id获取到对应的页面
    :param page_id:
    :return:
    """
    pass



if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
    # asyncio.run(open_browser())