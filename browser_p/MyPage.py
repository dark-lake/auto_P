import base64
import asyncio
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from playwright.async_api import Page, Response, Locator
from pydantic import BaseModel
from bs4 import BeautifulSoup
import uuid

if TYPE_CHECKING:
    from BrowserContextManager import MyBrowserContext

from logger_util import logger
from openai import AsyncOpenAI
import json
import os

load_dotenv()


class MyWebpage:
    def __init__(self, page_id: str, page_name: str, page: Page, my_browser_context: 'MyBrowserContext') -> None:
        self.page_id = page_id
        self.page_name = page_name
        self.page = page
        self.my_browser_context = my_browser_context

    async def goto(self, url: str) -> Response:
        return await self.page.goto(url)

    async def get_html(self) -> str:
        return await self.page.content()

    async def mouse_click(self, element_name: str) -> str:
        """
        模拟鼠标点击行为
        :param element_name: 要点击的元素名称或描述
        :return:
        """
        # 获取截图
        page_snapshot_base64 = await get_snapshot_base64(self, element_name)
        # 构造提问
        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        # 需注意：传入Base64编码遵循格式 data:image/<IMAGE_FORMAT>;base64,{base64_image}：
                        # PNG图片："url":  f"data:image/png;base64,{base64_image}"
                        "url": page_snapshot_base64
                    },
                    "detail": "low",
                },
                {
                    "type": "text",
                    "text": '上面是一张网页截图。请帮我找出截图中“' + element_name + '”的位置,要求输出bounding box 的坐标：既x_min,y_min,x_max,y_max。若元素不存在,请返回 {}. 处理过程要快速',
                },
            ],
        }]
        # 获取位置信息[x_min, y_min, x_max, y_max]
        position = await get_element_position_by_model(messages)
        if not position:
            return f'未在页面上找到{element_name}'

        # 获取相对位置
        relative_position = await get_relative_position(self, position)
        if not relative_position:
            logger.info(f'相对位置获取失败:{relative_position}')
            return f'未在页面上找到{element_name}'

        # 如果打开了新的页面,应该将该页面加入到页面列表中
        popup = None
        
        # 异步显示圆点标记（自动消失，不阻塞点击）
        asyncio.create_task(self._show_click_indicator(relative_position, element_name))

        try:
            async with self.page.expect_popup(timeout=3000) as popup_info:
                # 执行点击操作
                await self.page.mouse.click(relative_position[0], relative_position[1])
                popup = await popup_info.value
                logger.info(f'{element_name}点击后,打开了新页面')
        except Exception as e:
            logger.info(f'{element_name}点击后,没有打开新页面')

        if popup:
            new_page = MyWebpage(
                page_id=str(uuid.uuid4()),
                page_name=f'{self.page_name}-{element_name}',
                page=popup,
                my_browser_context=self.my_browser_context
            )
            # 将新打开的页面加入到浏览器上下文对象中
            logger.info(f'成功打开新页面:{new_page.page_name}')
            await self.my_browser_context.add_page(new_page)

        return 'click_ok'

    async def _show_click_indicator(self, position: list[int], element_name: str):
        """
        异步显示点击指示器，3秒后自动消失
        :param position: 点击位置 [x, y]
        :return:
        """
        await self.show_box_selection(position)
        await snapshot(self, element_name)
        await asyncio.sleep(1.5)  # 显示时长
        await self.hide_box_selection()

    async def show_box_selection(self, position: list[int]):
        """
        在网页上标注出指定位置的圆点
        :param position: 点的坐标 [x, y]
        :return:
        """
        await self.page.evaluate(f"""
            // 如果不存在 canvas，就创建一个
            let canvas = document.getElementById('debug_canvas');
            if (!canvas) {{
                canvas = document.createElement('canvas');
                canvas.id = 'debug_canvas';
                canvas.width = window.innerWidth;
                canvas.height = window.innerHeight;
                canvas.style.position = 'fixed';
                canvas.style.top = '0';
                canvas.style.left = '0';
                canvas.style.zIndex = 999999;
                canvas.style.pointerEvents = 'none';  // 不影响点击
                document.body.appendChild(canvas);
            }}

            const ctx = canvas.getContext('2d');
            
            const x = {position[0]};
            const y = {position[1]};
            const radius = 15;  // 圆的半径

            // 清除之前的绘制（如果你想保留历史绘图，可以注释掉）
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // 绘制实心红色半透明圆
            ctx.fillStyle = 'rgba(255, 0, 0, 0.6)';  // 红色半透明
            ctx.beginPath();
            ctx.arc(x, y, radius, 0, 2 * Math.PI);
            ctx.fill();
        """)

    async def hide_box_selection(self):
        """
        隐藏框选功能
        :return:
        """
        await self.page.evaluate("""
            let canvas = document.getElementById('debug_canvas');
            if (canvas) {
                canvas.remove();
            }
        """)

    async def get_locator(self, element_name: str) -> Locator | None:
        # 获取当前页面截图的base64数据
        page_snapshot_base64 = await get_snapshot_base64(self)
        # 构造提问
        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        # 需注意：传入Base64编码遵循格式 data:image/<IMAGE_FORMAT>;base64,{base64_image}：
                        # PNG图片："url":  f"data:image/png;base64,{base64_image}"
                        "url": page_snapshot_base64
                    },
                    "detail": "low",
                },
                {
                    "type": "text",
                    "text": '上面是一张网页截图。请帮我找出截图中“' + element_name + '”的位置,要求输出bounding box 的坐标：既x_min,y_min,x_max,y_max。若元素不存在,请返回 {}. 处理过程要快速',
                },
            ],
        }]
        # 获取位置信息[x, y, width, height]
        print(messages)
        position = await get_element_position_by_model(messages)
        # 获取局部html
        html = await get_html_by_position(self, position)
        logger.info(f'html:{html}')

        messages = [
            {
                "role": "user",
                "content": (
                    f"{html}\n\n"
                    "请从以上 局部的HTML 片段中找到名为「{element_name}」的元素，并返回其 XPath。最好使用//开头,因为局部HTML无法确定其父层级的具体情况"
                    "只返回 JSON，不要附加任何说明。"
                    "未找到则返回 {{}}：\n\n"
                )
                ,
            }
        ]
        # 获取元素xpath
        xpath = await get_element_xpath_by_model(messages)
        if not xpath:
            return None

        return self.page.locator(f'xpath={xpath}')

    async def close(self):
        try:
            await self.page.close()
            if await self.my_browser_context.remove_page(self.page_id):
                logger.info(f'{self.page_id}-{self.page_name} 页面已关闭')
        except Exception as e:
            logger.exception(f'{self.page_id}-{self.page_name} 页面关闭异常', e)


async def snapshot(my_page: MyWebpage, element_name: str) -> bytes:
    """
    获取当前页面的截图
    :param element_name: 对象名称或描述
    :param my_page: 页面对象
    :return: 截图的二进制数据
    """
    await my_page.page.wait_for_load_state("load")
    return await my_page.page.screenshot(path=f'{my_page.page_name}_{element_name}.png', full_page=True)


async def get_snapshot_base64(my_page: MyWebpage, element_name: str) -> str:
    """
    获取当前页面的截图的base64编码
    :param my_page: 页面对象
    :param element_name: 元素对象的名字或描述
    :return: 截图的base64编码
    """
    page_img_bytes = await snapshot(my_page, element_name)
    return f'data:image/png;base64,{base64.b64encode(page_img_bytes).decode('utf-8')}'


async def get_html_by_position(my_page: MyWebpage, position: list[int]) -> str:
    """
    根据坐标获取其局部html代码
    :param my_page: 页面对象
    :param position: 坐标，[x_min,y_min,x_max,y_max]
    :return: 元素的HTML代码
    """
    client = await my_page.page.context.new_cdp_session(my_page.page)

    try:
        # 1. 启用 DOM domain（关键步骤！）
        await client.send("DOM.enable")

        # 2. 获取整个文档（必须在使用 pushNodesByBackendIdsToFrontend 之前调用）
        await client.send("DOM.getDocument", {"depth": -1})

        # 3. 确保页面已加载完成
        await my_page.page.wait_for_load_state("domcontentloaded")

        viewport_x, viewport_y = await get_relative_position(my_page, position)

        # 9. 获取指定坐标的节点
        node = await client.send("DOM.getNodeForLocation", {
            "x": viewport_x,
            "y": viewport_y,
        })

        node_id = node.get('nodeId')
        backend_node_id = node.get('backendNodeId')

        # 10. 如果没有nodeId但有backendNodeId，需要先解析backendNodeId
        if not node_id and backend_node_id:
            logger.info(f'未直接获取到nodeId，尝试通过backendNodeId ({backend_node_id}) 获取')
            # 使用 DOM.pushNodesByBackendIdsToFrontend 将后端节点转换为前端节点
            push_result = await client.send("DOM.pushNodesByBackendIdsToFrontend", {
                "backendNodeIds": [backend_node_id]
            })
            node_ids = push_result.get('nodeIds', [])
            if node_ids and len(node_ids) > 0:
                node_id = node_ids[0]
                logger.info(f'成功转换 backendNodeId -> nodeId: {node_id}')
            else:
                logger.warning(f'无法转换backendNodeId，返回数据: {push_result}')
                return ""

        if not node_id:
            logger.warning(f'未找到节点，返回的node数据: {node}')
            return ""

        logger.info(f'找到节点 - node_id: {node_id}, backend_node_id: {backend_node_id}')

        # 11. 获取节点的 HTML
        html_result = await client.send("DOM.getOuterHTML", {"nodeId": node_id})
        html = html_result.get('outerHTML', '')
        # 12. 去掉非HTML节点
        # html = remove_js_css_with_inline(html)

        logger.info(f'成功获取局部html，长度: {len(html)}')
        return html

    except Exception as e:
        logger.exception(f'获取HTML时出现异常，坐标: {position}', e)
        return ""
    finally:
        # 13. 禁用 DOM domain，释放资源
        try:
            await client.send("DOM.disable")
        except:
            pass


def remove_js_css_with_inline(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # 删除 script/style/link
    for tag in soup(["script", "style"]):
        tag.decompose()
    for link in soup.find_all("link", rel="stylesheet"):
        link.decompose()

    # 删除所有内联事件属性
    for tag in soup.find_all(True):
        # 找到以 'on' 开头的属性，例如 onclick/onload
        event_attrs = [attr for attr in tag.attrs if attr.startswith("on")]
        for attr in event_attrs:
            del tag[attr]

    return str(soup)


async def get_element_position_by_model(messages: list[dict]) -> list[int]:
    """
    通过调用视觉大模型来获取元素的bbox属性,既x_min,y_min,x_max,y_max
    :param messages: 大模型的输入
    :return: bbox数组
    """
    client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_URL"),
        timeout=120,
    )

    class Bbox(BaseModel):
        bbox: list[int]

    try:
        response = await client.chat.completions.parse(
            model=os.getenv("OPENAI_MODEL"),
            messages=messages,
            response_format=Bbox,  # 指定响应解析模型
            extra_body={
                "thinking": {
                    "type": "disabled"  # 不使用深度思考能力
                    # "type": "enabled" # 使用深度思考能力
                }
            }
        )
        model_res = response.choices[0].message.parsed
        logger.info(f'视觉模型处理结果: {model_res}')
        return model_res.bbox if model_res.bbox else []
    except Exception as e:
        logger.exception(f'视觉模型处理异常', e)
        return []


async def add_bk(position: list[int], img_path: str) -> None:
    """
    在图片上标出红色半透明实心圆
    :param img_path: 文件路径
    :param position: 圆心坐标 [x, y]
    :return:
    """

    if not position or len(position) < 2:
        logger.info(f'position为空或格式不正确')
        return

    import cv2
    
    # 读取原图
    image = cv2.imread(img_path)
    
    if image is None:
        logger.error(f'无法读取图片: {img_path}')
        return

    # 获取图像尺寸并缩放坐标(模型输出范围为0-1000)
    h, w = image.shape[:2]
    center_x = int(position[0] * w / 1000)
    center_y = int(position[1] * h / 1000)
    
    # 圆的半径
    radius = 20

    # 创建一个遮罩层用于绘制半透明圆
    overlay = image.copy()
    
    # 绘制实心红色圆 (OpenCV的颜色格式是BGR)
    cv2.circle(overlay, (center_x, center_y), radius, (0, 0, 255), -1)  # -1表示填充
    
    # 混合原图和遮罩层，实现半透明效果
    alpha = 0.6  # 透明度 (0-1，0完全透明，1完全不透明)
    image = cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0)

    # 保存结果图片
    output_path = os.path.splitext(img_path)[0] + "_with_circle.png"
    cv2.imwrite(output_path, image)
    print(f"成功保存标注图片: {output_path}")


async def get_element_xpath_by_model(messages: list[dict]) -> str:
    """
    通过调用大模型来获取元素的xpath
    :param messages: 大模型的输入
    :return: xpath
    """
    client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_URL"),
        timeout=120,
    )

    class XpathStr(BaseModel):
        xpath: str

    try:
        response = await client.chat.completions.parse(
            model=os.getenv("OPENAI_MODEL"),
            messages=messages,
            response_format=XpathStr,  # 指定响应解析模型
            extra_body={
                "thinking": {
                    "type": "disabled"  # 不使用深度思考能力
                    # "type": "enabled" # 使用深度思考能力
                }
            }
        )
        model_res = response.choices[0].message.parsed
        logger.info(f'模型处理结果XPATH: {model_res}')
        return model_res.xpath if model_res.xpath else ''
    except Exception as e:
        logger.exception(f'视觉模型处理异常', e)
        return ''


async def get_relative_position(my_page: MyWebpage, position: list[int]) -> list[int]:
    """
    获取相对位置
    :param my_page:
    :param position:
    :return:
    """
    client = await my_page.page.context.new_cdp_session(my_page.page)

    try:
        # 1. 启用 DOM domain（关键步骤！）
        await client.send("DOM.enable")

        # 2. 获取整个文档（必须在使用 pushNodesByBackendIdsToFrontend 之前调用）
        await client.send("DOM.getDocument", {"depth": -1})

        # 3. 确保页面已加载完成
        await my_page.page.wait_for_load_state("domcontentloaded")

        # 4. 获取页面实际尺寸（用于坐标转换）
        page_size = await my_page.page.evaluate('''
                () => ({
                    width: Math.max(
                        document.body.scrollWidth,
                        document.documentElement.scrollWidth,
                        document.body.offsetWidth,
                        document.documentElement.offsetWidth,
                        document.documentElement.clientWidth
                    ),
                    height: Math.max(
                        document.body.scrollHeight,
                        document.documentElement.scrollHeight,
                        document.body.offsetHeight,
                        document.documentElement.offsetHeight,
                        document.documentElement.clientHeight
                    )
                })
            ''')
        page_width = page_size['width']
        page_height = page_size['height']

        logger.info(f'页面实际尺寸: {page_width}x{page_height}')

        # 5. 将模型返回的归一化坐标(0-1000)转换为真实像素坐标
        if len(position) == 4:
            # 模型返回的是 0-1000 范围的归一化坐标，需要转换为真实像素
            x_min_real = int(position[0] * page_width / 1000)
            y_min_real = int(position[1] * page_height / 1000)
            x_max_real = int(position[2] * page_width / 1000)
            y_max_real = int(position[3] * page_height / 1000)

            logger.info(
                f'归一化坐标: {position} -> 真实像素坐标: [{x_min_real}, {y_min_real}, {x_max_real}, {y_max_real}]')

            # 计算中心点
            center_x = int((x_min_real + x_max_real) / 2)
            center_y = int((y_min_real + y_max_real) / 2)
        else:
            logger.error(f'position格式错误: {position}')
            return []

        # 6. 获取页面的滚动偏移量（关键修复！）
        scroll_position = await my_page.page.evaluate('''
                () => ({
                    scrollX: window.pageXOffset || document.documentElement.scrollLeft,
                    scrollY: window.pageYOffset || document.documentElement.scrollTop
                })
            ''')
        scroll_x = scroll_position['scrollX']
        scroll_y = scroll_position['scrollY']

        logger.info(f'页面滚动偏移量: scrollX={scroll_x}, scrollY={scroll_y}')

        # 7. 转换为视口坐标（全页坐标 - 滚动偏移 = 视口坐标）
        viewport_x = center_x - scroll_x
        viewport_y = center_y - scroll_y

        logger.info(f'全页中心点: ({center_x}, {center_y}) -> 视口坐标: ({viewport_x}, {viewport_y})')

        # 8. 检查坐标是否在视口内
        viewport_size = my_page.page.viewport_size
        if viewport_size:
            if viewport_x < 0 or viewport_y < 0 or viewport_x > viewport_size['width'] or viewport_y > viewport_size[
                'height']:
                logger.warning(f'元素不在当前视口内，尝试滚动到元素位置')
                # 滚动到元素位置
                await my_page.page.evaluate(f'''
                        window.scrollTo({{
                            left: {center_x - viewport_size['width'] // 2},
                            top: {center_y - viewport_size['height'] // 2},
                            behavior: 'instant'
                        }})
                    ''')
                # 等待滚动完成
                await asyncio.sleep(0.5)
                # 重新计算视口坐标
                scroll_position = await my_page.page.evaluate('''
                        () => ({
                            scrollX: window.pageXOffset || document.documentElement.scrollLeft,
                            scrollY: window.pageYOffset || document.documentElement.scrollTop
                        })
                    ''')
                scroll_x = scroll_position['scrollX']
                scroll_y = scroll_position['scrollY']
                viewport_x = center_x - scroll_x
                viewport_y = center_y - scroll_y
                logger.info(f'滚动后新视口坐标: ({viewport_x}, {viewport_y})')
        return [viewport_x, viewport_y]
    except Exception as e:
        logger.exception(f'获取相对位置异常', e)
        return []
    finally:
        # 13. 禁用 DOM domain，释放资源
        try:
            await client.send("DOM.disable")
        except:
            pass
