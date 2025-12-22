import asyncio
import json
import os
import time
import uuid
from collections.abc import Iterable
from contextlib import AsyncExitStack
from typing import List, Dict, Any, Union, Callable, Generator, AsyncGenerator

import aiofiles
from dotenv import load_dotenv
from gradio.components.chatbot import ChatMessage
from mcp import ClientSession, StdioServerParameters, Tool
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult
from openai import AsyncOpenAI
from openai.types.beta.threads.runs import ToolCall
from openai.types.beta.threads.runs.function_tool_call import Function, FunctionToolCall
from openai.types.responses import ResponseStreamEvent

from auto_p_gui.message_items.message_models import AutoPModel, AutoPMessage, AutoPContentItem, AutoPToolCall, \
    AutoPToolCallResult
from auto_p_prompts.prompts import auto_p_prompts as auto_p_prompts
from auto_p_prompts.prompts_manager import PromptsManager
from auto_p_services.McpServiceManager import McpServiceManager
from auto_p_services.auto_p import auto_p_tools
from auto_p_services.chrome_mcp.chrome_tools import ChromeTools
from auto_p_services.mcp_services_config import mcp_service_manager
from auto_p_utils.logger_util import logger
from auto_p_utils.os_util import response_convert_tool
from auto_p_vector.vector_processor import ToolSearcher

load_dotenv()

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


class AutoProcessAgent:
    def __init__(self):
        self.session = None
        self.openai = AsyncOpenAI(
            api_key=os.getenv("CHAT_API_KEY"),
            base_url=os.getenv("CHAT_BASE_URL"),
            timeout=120,
        )
        self.chrome_tools: ChromeTools | None = None  # 浏览器工具
        self.chat_history: list[AutoPModel] = []  # 全局对话历史
        self.servers = {}  # 存所有 server session server_name -> server_session
        self.servers_McpService: dict[str, McpServiceManager.McpService] = {}  # mcp服务列表 server_name -> McpService
        self.tool_service_map = {}  # tool_name → server_name 映射
        self.tools = []  # 处理后的工具,可直接发送给大模型
        self.exit_stack = AsyncExitStack()
        self.prompts_manager = PromptsManager()  # 提示词管理器,负责提示词的构建
        self.tool_searcher: ToolSearcher | None = None

    async def _connect_to_server(
            self,
            mcp_service: 'McpServiceManager.McpService'
    ) -> None:
        """
        链接到具体的mcp server
        :param mcp_service: mcp_service 配置对象,需要具体connect才能使用
        """
        if not mcp_service.args:
            raise ValueError("服务脚本py/js必须指定其绝对路径")
        is_python = mcp_service.args[0].endswith('.py')
        is_js = mcp_service.args[0].endswith('.js')
        if not (is_python or is_js):
            raise ValueError("服务脚本必须是python或js文件")

        # 准备环境变量
        env_vars = {"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        if mcp_service.env:
            env_vars.update(mcp_service.env)

        server_params = StdioServerParameters(
            command=mcp_service.command,
            args=(mcp_service.args or []),
            env=env_vars
        )
        if mcp_service.transport == 'stdio':
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))

            await session.initialize()
            list_tools_result = await session.list_tools()
            tools = list_tools_result.tools
            # 保存mcp服务
            self.servers[mcp_service.name] = session
            # 保存每个工具与其服务名的映射, 并将转换后的工具保存
            for tool in tools:
                self.tool_service_map[tool.name] = mcp_service.name
                self.tools.append(tool)
            logger.info(f"{mcp_service.name}服务中工具列表(共{len(tools)}个)为:{[tool.name for tool in tools]}")
        # 将当前服务的McpService对象保存
        self.servers_McpService[mcp_service.name] = mcp_service

        # 初始化工具搜索器
        await self.init_tool_searcher()

    async def init_tool_searcher(
            self
    ) -> None:
        """构建工具搜索器"""
        if not self.tool_searcher and os.getenv("ENABLE_TOOL_SEARCH", "false") == "true":
            logger.info(f'开始构建工具搜索器...')
            # 构建工具搜索器
            all_tools: list[Tool] = []
            for service_name, session in self.servers.items():
                # auto_p-tools 属于官方工具,不需要添加
                if os.getenv('OFFICIAL_SERVICE_NAMES') == service_name:
                    continue
                list_tools_result = await session.list_tools()
                all_tools.extend(list_tools_result.tools)

            self.tool_searcher = ToolSearcher(all_tools)
            # 增量更新:检测工具的新增、修改、删除
            await self.tool_searcher.sync_tools()

    def connect_by_config(
            self
    ) -> str:
        """
        通过mcp_service_config.py中配置的mcp服务进行链接
        :return:
        """
        mcp_service_list: list[McpServiceManager.McpService] = mcp_service_manager.get_mcp_services()
        for service in mcp_service_list:
            logger.info(f"开始链接服务: {service.name}")
            loop.run_until_complete(self._connect_to_server(mcp_service=service))
            logger.info(f"成功链接到 {service.name} 服务!")
        return f'MCP 服务连接成功, {', '.join(service.name for service in mcp_service_list)}, 共{len(mcp_service_list)}个服务.'

    def process_message(
            self,
            message: str,
            history: List[Union[Dict[str, Any], ChatMessage]]
    ) -> Generator[tuple[list[dict[str, Any] | ChatMessage], str], Any, None]:
        # 添加用户输入
        async_gen = self._process_query(message, history)
        while True:
            try:
                msg = loop.run_until_complete(async_gen.__anext__())
                yield history + msg, ""
            except StopAsyncIteration:
                break

    async def _process_query(
            self,
            message: str,
            history: List[Union[Dict[str, Any], ChatMessage]]
    ) -> AsyncGenerator[list[Any], Any]:

        # 返回的消息数组, 第一个chat message是用于content输出,后面的内容都是用来tool输出
        response = []
        # 用于记录所有assistant的content, 单次对话的对话历史
        chat_history: dict[str, AutoPModel] = {}  # chat_history dict[event.item.id, item]
        # 用于页面展示
        chat_messages_container: dict[str, ChatMessage] = {}  # chat_messages_container
        # 构建工具的json schema
        tools = await self.build_tools_schema()
        # 标记聊天是否结束
        chat_stop = False

        # 插入用户
        user_message = AutoPMessage(
            role="user",
            content=[AutoPContentItem(
                type="text",
                text=message
            )]
        )
        # 展示到页面上
        id = str(uuid.uuid4())
        chat_messages_container['user_' + id] = ChatMessage(
            role=user_message.role,
            content=user_message.content[0].text
        )
        response.append(chat_messages_container['user_' + id])
        yield response
        # 添加一个assistant的页面展示
        response.append(ChatMessage(role="assistant", content="", ))
        yield response
        await self._process_event(user_message, None, chat_history, chat_messages_container, response)

        logger.info(f"用户输入为: {self.chat_history + list(chat_history.values())}")

        # 插入系统提示词
        if not self.chat_history and self.tool_searcher and os.getenv('ENABLE_TOOL_SEARCH') == 'true':
            # 构建全部工具的schema,只保留name和desc
            build_system_prompt = await self.build_tool_search_system_prompt()
            system_prompt = AutoPMessage(
                role="system",
                content=[AutoPContentItem(
                    type="text",
                    text=build_system_prompt
                )]
            )
            chat_history = {"system": system_prompt, **chat_history}

        # 处理历史记录, history是页面上的历史,暂时未做处理
        asyncio.create_task(self._process_chat_history(history))
        logger.info(f"对话历史为: \n{self.chat_history}")

        while not chat_stop:

            final_text = ""
            call_id = ""
            tool_name = ""

            stream = await self.openai.responses.create(
                model=os.getenv("CHAT_OPEN_MODEL"),
                input=self.chat_history + list(chat_history.values()),
                temperature=0.95,
                stream=True,
                stream_options={
                    "include_usage": True,
                    "chunk_include_usage": True,
                },
                extra_body={
                    "thinking": {
                        "type": "disabled"  # 不使用深度思考能力
                        # "type": "enabled" # 使用深度思考能力
                    }
                },
                tools=tools
            )

            async with aiofiles.open(
                    f"/Users/macbook0000/PycharmProjects/auto_P/stream_log/{time.strftime('%Y%m%d-%H%M%S')}.log",
                    mode="w") as f:

                async for event in stream:
                    await f.write(f'{event.type}-{event}\n')
                    if event.type == "response.output_text.delta":
                        # 加入历史
                        chat_history[event.item_id].content[0].text += event.delta
                        # 页面展示
                        chat_messages_container[event.item_id].content += event.delta
                        final_text += event.delta
                        yield response

                    # ---- 工具调用开始（示例）----
                    elif event.type == "response.output_item.added":
                        if event.item.type == "message":
                            # 记录assistant content
                            auto_p_message = AutoPMessage(
                                role="assistant",
                                content=[
                                    AutoPContentItem(
                                        type="text",
                                        text=""
                                    )
                                ]
                            )
                            await self._process_event(auto_p_message, event, chat_history, chat_messages_container,
                                                      response)
                            # 添加到聊天记录中
                            yield response
                        elif event.item.type == "function_call":
                            auto_p_tool_call = AutoPToolCall(
                                type="function_call",
                                arguments="",
                                name=event.item.name,
                                call_id=event.item.call_id,
                            )
                            # 处理消息
                            await self._process_event(auto_p_tool_call, event, chat_history, chat_messages_container,
                                                      response)
                            yield response
                            call_id = event.item.call_id
                            tool_name = event.item.name


                    elif event.type == "response.content_part.done":
                        # content 结束
                        pass

                    elif event.type == "response.output_text.done":
                        chat_messages_container[event.item_id].metadata["status"] = "done"

                    elif event.type == "response.function_call_arguments.delta":
                        # 添加到页面上
                        chat_messages_container[event.item_id].content += f"{event.delta}"
                        yield response
                        # 记录添加历史中
                        chat_history[event.item_id].arguments += event.delta

                    # ---- 工具参数完成（示例）----
                    elif event.type == "response.function_call_arguments.done":
                        # 结束的部分只展示到页面上,chat message不需要添加
                        chat_messages_container[event.item_id].content += f"\n- 工具参数完成, 开始执行...\n"
                        yield response
                        # 检查参数是否正确
                        try:
                            tool_args = json.loads(event.arguments)
                        except Exception as e:
                            logger.info(f'工具{tool_name}参数解析异常: {e}')
                            auto_p_tool_call_result = AutoPToolCallResult(
                                type="function_call_output",
                                output=f'工具{tool_name}参数解析异常: {e}, 请检查参数是否正确',
                                call_id=call_id
                            )
                            await self._process_event(auto_p_tool_call_result, event, chat_history,
                                                      chat_messages_container, response)
                            yield response
                            break

                        # 开始执行工具
                        tool_call = FunctionToolCall(
                            id=call_id,
                            function=Function(
                                name=tool_name,
                                arguments=json.dumps(tool_args, ensure_ascii=False),
                            ),
                            type='function',
                        )
                        result = await self.execute_tool(tool_call)
                        if result.content:
                            output = result.content[0]
                            if output.type == 'text':
                                output = output.text
                            elif hasattr(output, 'model_dump'):
                                output = output.model_dump_json()
                        else:
                            output = json.dumps(result.structuredContent, ensure_ascii=False)

                        logger.info(f'工具{tool_name}执行结果: {output}')

                        auto_p_tool_call_result = AutoPToolCallResult(
                            type="function_call_output",
                            name=tool_name,
                            output=output,
                            call_id=call_id
                        )
                        await self._process_event(auto_p_tool_call_result, event, chat_history, chat_messages_container,
                                                  response)
                        yield response
                        break

                    # ---- 最终文本 ----
                    elif event.type == "response.output_item.done":
                        pass

                    # ---- 整个 response 完成 ----
                    elif event.type == "response.completed":
                        chat_stop = True
        self.chat_history.extend(chat_history.values())

    @staticmethod
    async def _process_event(
            item: AutoPModel,
            event: ResponseStreamEvent | None,
            chat_history: dict,
            chat_messages_container: dict, response: list
    ) -> None:
        """负责消息的处理"""
        if isinstance(item, AutoPMessage):
            if item.role == "assistant":
                if not chat_history.get(event.item.id):
                    # 展示到页面上
                    assist_msg = ChatMessage(role=item.role, content=item.content[0].text)
                    chat_messages_container[event.item.id] = assist_msg
                    response.append(assist_msg)
                    # 加入到历史记录
                    chat_history[event.item.id] = item
            elif item.role == "user":
                # 加入到历史记录
                chat_history['user'] = item
            elif item.role == "system":
                if not chat_history.get('system'):
                    # 添加到历史记录
                    pass
        elif isinstance(item, AutoPToolCall):
            if not chat_history.get(event.item.id):
                chat_message = ChatMessage(
                    role='assistant',
                    content=f"- 调用工具: {event.item.name}\n- 工具参数为:",
                    metadata={
                        "title": f"开始处理 {event.item.name} 工具",
                        "id": "tool running",
                        "status": "pending",
                    },
                )
                # 加入到页面展示
                chat_messages_container[event.item.id] = chat_message
                response.append(chat_message)
                # 加入到历史记录
                chat_history[event.item.id] = item
                logger.info(f'成功加入到历史中: {chat_history[event.item.id]}')
        elif isinstance(item, AutoPToolCallResult):
            # 这里一定能获取到之前添加的 AutoPCallTool,因为它的id和AutoPToolCallResult所用的event.item.id/event.item_id是一样的,所以会覆盖,这里就需要新建一个
            if chat_history.get(event.item_id):
                # 渲染到页面
                chat_message = chat_messages_container[event.item_id]
                chat_message.content += f'- 工具调用结果:{item.output[:64]}...'
                # 修改结果
                chat_messages_container[event.item_id].metadata["status"] = "done"
                # 加入到历史记录
                chat_history[event.item_id + "_result"] = item
            else:
                logger.error(f"未找到对应的工具调用结果: {event.item_id}")

    async def get_tool_from_session(
            self,
            tool_names: set[str],
            session: ClientSession = None
    ) -> list[Tool]:
        """获取指定session中的指定Tool"""
        need_tools = []
        if session:
            all_tools = await session.list_tools()
            for tool in all_tools.tools:
                if tool.name in tool_names:
                    need_tools.append(tool)
        else:
            for tool in self.tools:
                if tool.name in tool_names:
                    need_tools.append(tool)
                    tool_names -= {tool.name}
        return need_tools

    async def execute_tool(
            self,
            tool_call: ToolCall
    ) -> CallToolResult:
        """
        实际执行tool的方法
        :return: 方法执行的结果
        """
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        server_name = self.tool_service_map.get(tool_name, '')
        server: ClientSession = self.servers.get(server_name, None)
        if not server:
            return await auto_p_tools.build_tool_result(f'未找到{tool_name}工具对应的MCP服务', tool_call)
        logger.info(f"正在执行 {server_name} 服务的 {tool_name} 工具, 参数为: {tool_args}")
        special_method: Callable = auto_p_tools.special_methods.get(tool_name)
        if special_method:
            logger.info(f'正在执行特殊方法 {tool_name}')
            return await special_method(self, tool_call)
        elif server_name == 'chrome-devtools':
            if not self.chrome_tools:
                self.chrome_tools = ChromeTools(server)
            return await self.chrome_tools.invoke_tool(tool_call)
        try:
            return await server.call_tool(tool_name, tool_args)
        except Exception as e:
            return await auto_p_tools.build_tool_result(f'调用{tool_name}工具异常,请分析异常后再进行下一步: {e}',
                                                        tool_call)

    async def build_tool_search_system_prompt(
            self
    ) -> str:
        """
        构建开启工具搜索后的系统提示词
        :return: 工具
        """
        lightweight_tools = []
        # server为ClientSession对象
        for server_name, server in self.servers.items():
            if server_name == os.getenv('OFFICIAL_SERVICE_NAMES'):
                continue
            list_tools_result = await server.list_tools()
            for tool in list_tools_result.tools:
                lightweight_tool = {
                    "name": tool.name,
                    "description": tool.description
                }
                lightweight_tools.append(lightweight_tool)
        logger.info(f"轻量化可用工具(已启用工具搜索模式): {len(lightweight_tools)}")
        # 构建工具描述
        mcp_tool_descriptions = [f'- {mcp_service.description}' for mcp_service in self.servers_McpService.values()]
        res = self.prompts_manager.build_prompt(
            auto_p_prompts.system_prompts_lightweight_V3,
            mcp_tool_descriptions='\n'.join(mcp_tool_descriptions),
            lightweight_tools=json.dumps(lightweight_tools)
        )
        return res

    async def build_tools_schema(
            self,
            tool_name: str = None
    ) -> Iterable:
        # 当指定要调用的工具时,只返回该工具的schema
        if tool_name:
            server = self.servers.get(tool_name, None)
            if server is None:
                return []
            list_tools_result = await server.list_tools()
            return [response_convert_tool(tool) for tool in list_tools_result.tools if tool.name == tool_name]

        # 如果开启了工具搜索只返回官方工具
        if self.tool_searcher and os.getenv("ENABLE_TOOL_SEARCH", "false") == "true":
            list_tools_result = await self.servers.get(os.getenv('OFFICIAL_SERVICE_NAMES')).list_tools()
            tools = list_tools_result.tools
            logger.info(f"可用工具(已启用工具搜索模式): {len(tools)}")
            return [response_convert_tool(tool) for tool in tools]
        else:
            # server为ClientSession对象
            logger.info(f"可用工具(未启用工具搜索模式): {len(self.tools)}")
            return [response_convert_tool(tool) for tool in self.tools]

    def clear_chat_history(
            self,
            history: List[Union[Dict[str, Any], ChatMessage]]
    ) -> List[Union[Dict[str, Any], ChatMessage]]:
        """清空历史记录"""
        self.chat_history = []
        logger.info(f'已清空历史记录:{len(history)}')
        return []

    async def _process_chat_history(
            self,
            history: List[Union[Dict[str, Any], ChatMessage]]
    ) -> None:
        """
        处理历史记录
        1.将其中的tool_call_result中超长的文本进行缩减
        :param history: 历史记录
        :return: chat_history
        """
        for item in self.chat_history[:len(self.chat_history) - 5]:
            if isinstance(item, AutoPToolCallResult) and item.name == 'take_snapshot':
                # 如果是take_snapshot那就缩减一下超长文本
                item.output = item.output[:512] + "..."
