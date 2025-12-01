import asyncio

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright

import MyPage
from BrowserContextManager import browser_context_manager
from my_exceptions.MyBaseException import MyBaseException
from utils import os_util
from utils.logger_util import logger

load_dotenv()

mcp = FastMCP("Chrome_Browser Server")


@mcp.tool(
    name="open_browser",
    description="用于启动一个浏览器,通常只需要执行一次该工具",
)
async def open_browser() -> str:
    """
    用于启动一个浏览器,通常只需要执行一次该工具
    """
    if browser_context_manager.browser_contexts:
        browser_context = await browser_context_manager.get_browser_context()
        if browser_context:
            logger.info(f'浏览器上下文已启动成功,无需重复启动,浏览器上下文对象ID为：{browser_context.id}')
            return f'浏览器上下文已启动成功,无需重复启动'

    playwright = await async_playwright().start()
    if os.getenv("USER_DATA_DIR"):
        logger.info(f'使用用户数据目录:{os.getenv("USER_DATA_DIR")}')
        # 此时直接返回的就是浏览器上下文对象,而不是浏览器对象
        browser_context = await playwright.chromium.launch_persistent_context(
            user_data_dir=os.getenv("USER_DATA_DIR"),
            headless=False,
            executable_path=os.getenv("CHROME_PATH"),
        )
        browser_context_obj = await browser_context_manager.add_browser_context(browser_context)
    else:
        browser = await playwright.chromium.launch(headless=False)
        await browser_context_manager.set_browser(browser)
        browser_context_obj = await browser_context_manager.add_browser_context()

    if not browser_context_obj:
        logger.info(f'浏览器上下文对象未创建')
        return f'浏览器上下文对象未创建，流程终止'
    logger.info(f'浏览器上下文对象创建成功-{browser_context_obj.id}')
    return f'浏览器上下文启动成功'


@mcp.tool(
    name="close_browser",
    description="Close the browser.",
)
async def close_browser() -> str:
    """
    关闭浏览器
    """
    if browser_context_manager:
        await browser_context_manager.close_browser()
        return '浏览器关闭成功'
    else:
        logger.info(f'浏览器关闭失败')
        return '浏览器关闭失败'


# @mcp.tool(
#     name="do_operation_on_page",
#     description="对被操作元素执行对应操作, 操作类型只支持:[点击,输入,清空]"
# )
async def do_operation(page_name: str, element_desc: str, operation: str, params: dict = None) -> str:
    """
    对页面的指定元素执行对应操作
    :param element_desc: 被操作元素的名称或描述,应该是文字
    :param page_name: 页面名称
    :param operation: 对元素执行的操作,分别有[点击,输入,清空]
    :param params: 此次操作可能需要的参数
    """
    if not check_status():
        return f'浏览器未启动,请先启动浏览器'

    browser_context = await browser_context_manager.get_browser_context()
    page = await browser_context.get_page_by_name(page_name)

    # 获取元素在页面中的位置信息
    locator = await page.get_locator(element_desc)

    if operation == '点击':
        await locator.click()
        return f'点击元素成功'

    return f'操作元素失败'


@mcp.tool(
    name="click_element",
    description="执行点击工具前先获取所有页面的名字,然后再执行点击工具, 如果点击2次后依然没有效果,那请将detail赋值为1,通常情况保持0即可"
)
async def click_element(page_name: str, element_desc: str, detail: int = 0) -> str:
    """
    对页面的指定元素执行点击操作
    :param detail: 点击的精确程度, 默认是0为标准程度, 如果点击2次后依然没有达到要求,可以将detail赋值为1表示高精度点击
    :param element_desc: 被操作元素的名称或描述,应该是文字
    :param page_name: 如果点击后打开新页面,则返回新页面名字,否则返回空
    """
    if not check_status():
        return f'浏览器未启动,请先启动浏览器'

    browser_context = await browser_context_manager.get_browser_context()
    page = await browser_context.get_page_by_name(page_name)
    if not page:
        logger.info(f'未获取到{page_name}页面对象')
        return f'未获取到{page_name}页面对象,请先获取所有页面名称确认是否有你需要的页面'
    try:
        new_page = await page.mouse_click(element_desc, detail)
        logger.info(f'已完成{element_desc}元素点击,精度为{'高' if detail else '标准'}')
        if new_page:
            return f'已完成{element_desc}元素点击,点击后打开的新页面名称为:{new_page.page_name}.采用的点击精度为{'高' if detail else '标准'}'
        else:
            # 返回None的情况,未打开新页面,但是点击成功
            return f'点击{element_desc}元素成功'
    except MyBaseException as be:
        return f'{be.message}'
    except Exception as e:
        return f'点击元素失败,请检查元素描述是否正确,错误信息为:{type(e).__name__}'


@mcp.tool(
    name="open_page",
    description="在打开新页面之前，应先获取所有已打开的页面名称。如果目标页面已存在，则无需重复打开。该工具用于打开指定 URL 对应的页面；如果之前已经执行过 open_browser，则可以直接使用本工具，无需再次调用 open_browser。",
)
async def open_page(url: str, page_name: str) -> str:
    """
    用于打开url所指向的页面,如果已经执行过open_browser操作,那就直接执行该工具即可,无需再次调用open_browser
    :param page_name: 页面的名字，每个页面的名字原则上应不相同,用于更好的标识一个页面
    :param url: 页面url
    :return:
    """

    # 获取浏览器上下文对象,默认只有一个
    if not check_status():
        return f'浏览器未启动,请先启动浏览器'
    browser_context = await browser_context_manager.get_browser_context()
    if not browser_context:
        logger.info(f'未获取到浏览器上下文对象,流程终止')
        return f'未获取到浏览器上下文对象'
    try:
        return await do_open_page(url, browser_context.id, page_name)
    except Exception as e:
        logger.exception(f'访问页面{page_name}-{url}出现异常', e)
        return f'访问页面{page_name}-{url}出现异常, 异常为: {e}'


async def do_open_page(url: str, browser_context_id: str, page_name: str) -> str:
    """
    执行访问页面的实际操作
    :param url: 页面url
    :param browser_context_id: 浏览器上下文id,用于唯一确定一个浏览器
    :param page_name: 页面名称
    :return:
    """

    if not browser_context_manager:
        logger.info(f'浏览器上下文对象为:{browser_context_manager},无法获取所有浏览器会话ID列表')
        return f'浏览器上下文对象异常'

    browser_context = await browser_context_manager.get_browser_context(browser_context_id)
    if not browser_context:
        logger.info(f'未获取到浏览器上下文ID为:{browser_context_id}的对象')
        return f'未获取到浏览器上下文对象, 流程终止'
    page = await browser_context.create_page(page_name=page_name)

    try:
        res = await page.goto(url)
        print(f'页面相应状态为：{res.status}')
        if res.status != 200:
            logger.info(f'{page_name}-{url}页面打开异常：{res.status}')
            return f'{page_name}页面打开失败'
        else:
            logger.info(f'{page_name}-{url}页面打开成功：{res.status}')
            return f'{page_name}页面打开成功'
    except Exception as e:
        logger.error(f'{page_name}-{url}页面访问网络异常', e)
        return f'{page_name}页面打开失败'


@mcp.tool(
    name="get_all_page_name",
    description="获取所有页面的名称",
)
async def get_all_page_name() -> str:
    """
    获取所有页面名称
    :return: 页面名称列表
    """
    if not check_status():
        return f'浏览器未启动,请先启动浏览器'

    browser_context = await browser_context_manager.get_browser_context()
    if not browser_context:
        logger.info(f'未获取到浏览器上下文对象')
        return f'未获取到浏览器上下文对象'

    return f'所有的页面名称列表为: {str(await browser_context.get_all_page_names())}'


@mcp.tool(
    name="close_page",
    description="需要先获取所有页面名称，然后判断页面名称是否匹配目标，再关闭页面。",
)
async def close_page(page_name: str) -> str:
    """
    关闭指定页面名称的页面
    :param page_name: 页面名称
    :return:
    """
    if not check_status():
        return f'浏览器未启动,请先启动浏览器'

    browser_context = await browser_context_manager.get_browser_context()
    if not browser_context:
        logger.info(f'未获取到浏览器上下文对象')
        return f'未获取到浏览器上下文对象'

    # 通过page_name获取page_id
    page = await browser_context.get_page_by_name(page_name)
    if not page:
        logger.info(f'未获取到{page_name}页面对象')
        return f'未获取到{page_name}页面对象'
    # 关闭页面
    await page.close()
    logger.info(f'{page.page_name}页面已关闭')
    return f'{page.page_name}页面已关闭'


@mcp.tool(
    name="fill_input_element",
    description="需要先获取所有页面的名称,然后对指定页面的输入框进行输入"
)
async def fill_input_element(page_name: str, element_desc: str, value: str) -> str:
    """
    针对所有网页中的input输入文本的情况,比如账号,密码等等
    :param page_name: 页面名称,唯一确定一个页面
    :param element_desc: 被操作的input元素的名称或者描述,应该是文字类型
    :param value: 要输入的值
    :return: 是否输入成功
    """
    if not check_status():
        return f'浏览器未启动,请先启动浏览器'

    browser_context = await browser_context_manager.get_browser_context()
    page = await browser_context.get_page_by_name(page_name)
    if not page:
        logger.info(f'填充{element_desc}-{value}时未获取到页面对象')
        return f'未获取到{page_name}页面对象,请先获取所有页面名称确认是否有你需要的页面'

    try:
        # 填充输入框, 先通过键盘输入,如果不成功再改用locator方式输入
        await page.fill_input_element_by_keyboard(element_desc, value)
        logger.info(f'[键盘方式]已输入{element_desc}元素值为:{value}')
        return f'已输入{element_desc}元素值为:{value}'
        # if await page.fill_input_element_by_locator(element_desc, value):
        #     logger.info(f'[locator方式]已输入{element_desc}元素值为:{value}')
        #     return f'已输入{element_desc}元素值为:{value}'

        # return f'{element_desc}元素填充{value}失败'
    except MyBaseException as e:
        return f'{e.message}'
    except Exception as e:
        return f'填充{element_desc}-{value}时出现异常,异常为:{type(e).__name__}'


@mcp.tool(
    name="press_keyboard",
    description="需要先获取所有页面的名称,然后执行键盘操作"
)
async def press_keyboard(page_name: str, key: str) -> str:
    """
    在网页上执行键盘操作,比如回车,空格等操作
    :param page_name: 页面名称,唯一确定一个页面
    :param key: 要按压的按键名,必须符合大驼峰格式,比如Enter,Shift等
    :return: 是否按压成功,以及是否打开了新页面
    """
    if not check_status():
        return f'浏览器未启动,请先启动浏览器'

    browser_context = await browser_context_manager.get_browser_context()
    page = await browser_context.get_page_by_name(page_name)
    if not page:
        logger.info(f'按键{key}时未获取到{page_name}页面对象')
        return f'未获取到{page_name}页面对象,请先获取所有页面名称确认是否有你需要的页面'
    try:
        new_page = await page.keyboard_press(key)
        if new_page:
            logger.info(f'已按压{key}按键,新打开的页面名称为:{new_page.page_name}')
            return f'已按压{key}按键,新打开的页面名称为:{new_page.page_name}'
        else:
            logger.info(f'已按压{key}按键')
            return f'已按压{key}按键'
    except MyBaseException as e:
        return f'{e.message}'
    except Exception as e:
        return f'按键{key}时出现异常,异常为:{type(e).__name__}'


@mcp.tool(
    name="get_page_snapshot",
    description="获取指定页面的快照,当你想知道当前页面上有什么时,你可以调用该工具!"
)
async def get_page_snapshot(page_name: str) -> str:
    """
    获取页面快照,当你完成任务的时候遇到问题,你可以通过获取页面的快照来看看这个页面目前是怎么样子,然后再决定该如何解决遇到的问题!
    :param page_name: 页面名称
    :return: 截图base64
    """
    if not check_status():
        return f'浏览器未启动,请先启动浏览器'
    browser_context = await browser_context_manager.get_browser_context()
    page = await browser_context.get_page_by_name(page_name)
    if not page:
        logger.info(f'获取{page_name}页面快照时未获取到页面对象')
        return f'未获取到{page_name}页面对象,请先获取所有页面名称确认是否有你需要的页面'
    else:
        logger.info(f'已获取{page.page_name}页面快照')
    try:
        return await page.get_snapshot_base64('快照')
    except MyBaseException as e:
        return f'{e.message}'


@mcp.tool(
    name="scroll_page",
    description="滚动页面"
)
async def scroll_page(page_name: str, x: int, y: int) -> str:
    """
    滚动页面
    :param page_name: 页面名称
    :param x: 滚动的x轴距离
    :param y: 滚动的y轴距离
    :return: 滚动结果
    """
    if not check_status():
        return f'浏览器未启动,请先启动浏览器'
    browser_context = await browser_context_manager.get_browser_context()
    page = await browser_context.get_page_by_name(page_name)
    if not page:
        logger.info(f'滚动{page_name}页面时未获取到页面对象')
        return f'未获取到{page_name}页面对象,请先获取所有页面名称确认是否有你需要的页面'
    try:
        await page.scroll_page(x, y)
        logger.info(f'已滚动{page.page_name}页面,x轴距离为:{x},y轴距离为:{y}')
        return f'已滚动{page.page_name}页面,x轴距离为:{x},y轴距离为:{y}'
    except MyBaseException as e:
        return f'{e.message}'


@mcp.tool(
    name="get_account_info",
    description="当你要登录某个网站时,该工具可以告诉你所有网站的账号和密码"
)
async def get_account_info() -> str:
    """
    当你需要某个网站的用户信息时,该工具可以告诉你目前所有配置的网站的用户名与密码
    :return: 已配置的所有账户名和密码
    """
    try:
        config = await os_util.get_config(os.getenv('ACCOUNT_INFO'))
        return f'已配置的账户信息为:{config}'
    except MyBaseException as e:
        return f'{e.message}'
    except Exception as e:
        return f'获取账户信息时出现异常,异常为:{type(e).__name__}'


def check_status() -> bool:
    """
    检查浏览器上下文管理以及浏览器上下文对象是否存在
    :return:
    """
    if not browser_context_manager:
        logger.info(f'浏览器上下文管理器异常:{browser_context_manager}')
        return False
    return True


async def test():
    # 构建一个浏览器
    from playwright.async_api import async_playwright

    a = await async_playwright().start()
    browser = await a.chromium.launch(
        headless=False,
        args=["--start-maximized"]
    )
    browser_context = await browser.new_context(no_viewport=True)

    # 访问谷歌页面
    google_page = await browser_context.new_page()
    await google_page.goto('https://www.google.com')

    # 构建一个MyPage
    my_page = MyPage.MyPage(page_id='1', page_name='google', page=google_page, browser_context=browser_context)

    # locator = await my_page.get_locator("登录按钮")
    #
    # elements = await locator.all()
    # print(len(elements))
    # for element in elements:
    #     try:
    #         async with my_page.page.expect_navigation():
    #             print(element)
    #             await element.click()
    #     except:
    #         pass

    res = await my_page.mouse_click("谷歌搜索的输入框")
    print(res)
    await asyncio.sleep(10)


if __name__ == "__main__":
    # 设置环境变量标识这是 MCP server 模式
    import os

    os.environ['MCP_SERVER_MODE'] = '1'

    # Initialize and run the server
    mcp.run(transport='stdio')

    # asyncio.run(test())
