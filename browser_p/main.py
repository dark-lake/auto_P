import asyncio
import aiohttp
from playwright.async_api import async_playwright as ap
from lxml import etree
import aiofiles
from typing import Optional, Dict, Any
import os


async def aiohttp_test():
    timeout = aiohttp.ClientTimeout(total=5)
    timeout_short = aiohttp.ClientTimeout(total=0.1)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get('https://docs.aiohttp.org/en/stable/') as resp:
                html = await resp.text()
                print(f'Status: {resp.status}, Content-Type: {resp.content_type}, Body: {html[:15]}')

            params = {'key1': '12', 'key2': '456'}
            async with session.get('https://docs.aiohttp.org/en/stable/', params=params, timeout=timeout_short) as resp:
                html = await resp.text(encoding='utf-8')
                print(f'Status: {resp.status}, URL: {resp.url}, Content-Type: {resp.content_type}, Body: {html[:15]}')

            # 下载图片
            async with session.get(
                    'https://i-blog.csdnimg.cn/blog_migrate/c5868bd8188150fdc5059f5059154e7a.png') as resp:
                async with aiofiles.open('test.png', 'wb') as f:
                    async for chunk in resp.content.iter_chunked(1024):
                        await f.write(chunk)
        except Exception as e:
            print(f"Request error: {e}")


def generate_cookies_str(cookies: list[dict]) -> str:
    return ';'.join(f"{c['name']}={c['value']}" for c in cookies)


def get_sid(cookies: list[dict]) -> Optional[str]:
    for c in cookies:
        if c.get('name') == 'Coremail.sid':
            return c.get('value')
    return None


async def auto_login():
    url = 'https://email.163.com/'
    email = '15510616055'
    passwd = 'Ft2015871115!'
    try:
        async with ap() as p:
            browser = await p.chromium.launch(headless=True)
            state_path = os.getcwd() + '/' + 'state.json'
            # 若本地没有登录状态则新建上下文并存储state,否则加载上下文
            has_state = os.path.exists(state_path)
            print(has_state)
            if not has_state:
                context = await browser.new_context(ignore_https_errors=True)
                page = await context.new_page()
                resp = await page.goto(url)
                print(f'【{await page.title()}】页面响应状态: {resp.status}')
                frame = page.locator('xpath=//div[@id="urs163Area"]/iframe').content_frame
                await frame.locator('xpath=//input[@data-loginname="loginEmail"]').fill(email)
                await frame.locator('xpath=//input[@id="pwdtext"]').fill(passwd)

                async with page.expect_navigation():
                    await frame.locator('xpath=//a[@id="dologin"]').click()

                # 存储state
                await context.storage_state(path=state_path)
            else:
                context = await browser.new_context(storage_state=state_path, ignore_https_errors=True)

            # 处理请求参数
            cookies = await context.cookies()
            cookies_str = generate_cookies_str(cookies)
            print(f'Cookies: {cookies_str}')

            get_mail_list_url = 'https://mail.163.com/js6/s'
            sid = get_sid(cookies)
            if not sid:
                print("未获取到邮箱【sid】参数")
                return

            xml_data = """<?xml version="1.0"?>
                <object>
                    <int name="fid">1</int>
                    <string name="order">date</string>
                    <boolean name="desc">true</boolean>
                    <int name="limit">20</int>
                    <int name="start">20</int>
                    <boolean name="skipLockedFolders">false</boolean>
                    <string name="topFlag">top</string>
                    <boolean name="returnTag">true</boolean>
                    <boolean name="returnTotal">true</boolean>
                    <string name="mrcid">3bfbd512a222718880e7b010dea68899_v1</string>
                </object>
                """
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Cookie": cookies_str
            }
            await goto_url(get_mail_list_url, {"sid": sid}, xml_data, headers, cookies_str)
    except Exception as e:
        print(f"Playwright error: {e}")
    finally:
        if 'browser' in locals():
            await browser.close()


async def goto_url(url: str, params: dict, data: str, headers: dict, cookies: str):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, params=params, data=data, headers=headers) as resp:
                print(f'Status: {resp.status}')
                if resp.status == 200:
                    print("获取邮件列表成功")
                async with aiofiles.open("a.txt", 'w', encoding='utf-8') as f:
                    await f.write(await resp.text())
                    await f.flush()
            mid = await get_mail_list_data()
            if not mid:
                print("未获取到指定邮件ID")
                return

            download_url = 'https://mail.163.com/js6/read/readdata.jsp'
            data = {
                'sid': params.get('sid'),
                'mid': mid,
                'part': '2',
                'mode': 'download',
                'l': 'read',
                'action': 'download_attach'
            }
            headers = {"Cookie": cookies}
            async with session.get(download_url, params=data, headers=headers) as resp:
                async with aiofiles.open('temp.pdf', 'wb') as f:
                    async for chunk in resp.content.iter_chunked(1024):
                        await f.write(chunk)
                        await f.flush()
                print("附件下载完成")
        except Exception as e:
            print(f"HTTP request error: {e}")


async def get_mail_list_data() -> Optional[str]:
    try:
        tree = etree.parse('a.xml')
        objs = tree.xpath('//result//array/object')
        for o in objs:
            subject_elem = o.xpath('string[@name="subject"]')
            if subject_elem and 'GBase' in subject_elem[0].text:
                id_elem = o.xpath('string[@name="id"]')
                if id_elem:
                    print(f'id: {id_elem[0].text}')
                    return id_elem[0].text
    except Exception as e:
        print(f"XML parse error: {e}")
    return None


if __name__ == '__main__':
    import time
    st = time.time()
    asyncio.run(auto_login())
    et = time.time()
    print(f'总耗时:{str((et-st))[:4]}s')
    # asyncio.run(get_mail_list_data())
