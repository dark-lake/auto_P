import asyncio
import aiohttp


async def aiohttp_test():
    timeout = aiohttp.ClientTimeout(total=5)
    timeout1 = aiohttp.ClientTimeout(total=0.1)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get('https://docs.aiohttp.org/en/stable/') as response:
            print(f'Status:{response.status}')
            print(f'Content-type:{response.content_type}')
            html = await response.text()
            print(f'Body:{html[:15]}')

        params = {'key1': '12', 'key2': '456'}
        async with session.get('https://docs.aiohttp.org/en/stable/', timeout=timeout1, params=params) as resp:
            print(f'Status:{resp.status}')
            print(f'URL:{resp.url}')
            print(f'Content-type:{resp.content_type}')
            html = await resp.text(encoding='utf-8')
            print(f'Body:{html[:15]}')

        async with session.get('https://i-blog.csdnimg.cn/blog_migrate/c5868bd8188150fdc5059f5059154e7a.png') as resp:
            with open('test.png', 'wb') as f:
                async for chunk in resp.content.iter_chunked(1024):
                    f.write(chunk)


if __name__ == '__main__':
    asyncio.run(aiohttp_test())
