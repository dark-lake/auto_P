import json
import time
from typing import List, Any, Callable, AsyncGenerator

import aiofiles
from dotenv import load_dotenv
from gradio.components.chatbot import ChatMessage
from mcp import ClientSession, Tool
from mcp.types import CallToolResult
from openai import AsyncOpenAI
from openai.types.beta.threads.runs import ToolCall
from openai.types.beta.threads.runs.function_tool_call import Function, FunctionToolCall

from auto_p_agents.conversation_manager import ConversationManager
from auto_p_agents.mcp_connector import MCPConnector
from auto_p_gui.message_items.message_models import (
    AutoPMessage, AutoPContentItem, AutoPIMGContentItem,
    AutoPToolCall, AutoPToolCallResult,
)
from auto_p_prompts.prompts import auto_p_prompts as auto_p_prompts
from auto_p_prompts.prompts_manager import fill_prompt
from auto_p_services.McpServiceManager import McpServiceManager
from auto_p_services.auto_p import auto_p_tools
from auto_p_services.chrome_mcp.chrome_tools import ChromeTools
from auto_p_services.mcp_services_config import mcp_service_manager
from auto_p_utils.config import config
from auto_p_utils.logger_util import logger
from auto_p_utils.os_util import convert_tool
from auto_p_vector.vector_processor import ToolSearcher

load_dotenv()

CHROME_DEVTOOLS_SERVICE = "chrome-devtools"


class AutoProcessAgent:
    """基于 LLM 的浏览器自动化 Agent。

    委托 MCPConnector 管理 MCP 连接，ConversationManager 管理对话历史，
    自身负责 LLM 调用、工具路由和 ReAct 循环。
    """

    def __init__(self):
        self.openai = AsyncOpenAI(
            api_key=config.chat_api_key,
            base_url=config.chat_base_url,
            timeout=config.chat_timeout,
        )
        self.mcp = MCPConnector()
        self.conv = ConversationManager()
        self.chrome_tools: ChromeTools | None = None
        self.tool_searcher: ToolSearcher | None = None
        self._processing: bool = False  # 防重入

    # -- 连接管理 (代理到 MCPConnector) --

    async def _connect_to_server(self, mcp_service: "McpServiceManager.McpService") -> None:
        await self.mcp.connect(mcp_service)
        await self._init_tool_searcher()

    async def _init_tool_searcher(self) -> None:
        if not config.enable_tool_search or self.tool_searcher:
            return
        logger.info("开始构建工具搜索器...")
        all_tools = await self.mcp.get_non_official_tools_async()
        self.tool_searcher = ToolSearcher(all_tools)
        await self.tool_searcher.sync_tools()

    async def connect_by_config(self) -> str:
        services = mcp_service_manager.get_mcp_services()
        for service in services:
            logger.info(f"开始链接服务: {service.name}")
            await self._connect_to_server(mcp_service=service)
            logger.info(f"成功链接到 {service.name} 服务!")
        return (
            f"MCP 服务连接成功, {', '.join(s.name for s in services)}, "
            f"共{len(services)}个服务."
        )

    # -- 消息入口 -- 

    async def process_message(
            self, message: str, history: List[Any]
    ) -> AsyncGenerator[tuple, Any]:
        # 空输入拦截：提示用户输入内容
        if not message or not message.strip():
            if history:
                history.append({
                    "role": "assistant",
                    "content": "❓ 你想让我做什么？比如：\"打开百度搜索 Python\"。",
                })
                yield history, ""
            return

        # 防重入：正在处理上一个请求时拒绝新请求
        if self._processing:
            history.append({
                "role": "assistant",
                "content": "⏳ 正在处理中，请稍候...",
            })
            yield history, ""
            return

        self._processing = True
        try:
            async for msg in self._process_query(message, history):
                yield history + msg, ""
        finally:
            self._processing = False

    async def _process_query(
            self, message: str, history: List[Any]
    ) -> AsyncGenerator[list, Any]:
        tools_schema = await self._build_tools_schema()
        chat_stop = False

        self.conv.add_user_message(message)
        response_view = self.conv.page_response
        yield response_view

        logger.info(f"用户输入为: {self.conv.build_payload()}")

        # 插入系统提示词
        if not self.conv.chat_history and self.tool_searcher and config.enable_tool_search:
            system_text = await self._build_tool_search_system_prompt()
            self.conv.add_system_message(system_text)

        logger.info(f"对话历史为: \n{self.conv.chat_history}")

        while not chat_stop:
            pending_executions = []  # [(item_id, call_id, tool_name, tool_args, event)]
            thinking_text = ""
            thinking_eid: str | None = None

            payload = self.conv.build_payload()

            # 动态推理：doubao-seed-1-6-flash 只支持 enabled/disabled
            # 简单任务（短消息、单步操作）→ disabled 快速响应
            # 复杂任务（长消息、多步骤、搜索/查找/对比等关键词）→ enabled 深度推理
            thinking_type = self._decide_thinking(message, len(self.conv.chat_history))

            stream = await self.openai.responses.create(
                model=config.chat_model_for_api,
                input=payload,
                temperature=config.llm_temperature,
                stream=True,
                extra_body={"thinking": {"type": thinking_type}},
                tools=tools_schema,
            )

            log_path = str(config.stream_log_path / f"{time.strftime('%Y%m%d-%H%M%S')}.log")
            async with aiofiles.open(log_path, mode="w") as f:
                async for event in stream:
                    await f.write(f"{event.type}-{event}\n")

                    if event.type == "response.output_text.delta":
                        self.conv.current_turn[event.item_id].content[0].text += event.delta
                        self.conv.page_containers[event.item_id].content += event.delta
                        yield response_view

                    elif event.type == "response.output_item.added":
                        if event.item.type == "message":
                            item = AutoPMessage(
                                role="assistant",
                                content=[AutoPContentItem(type="input_text", text="")],
                            )
                            self.conv.handle_event(item, event)
                            yield response_view
                        elif event.item.type == "function_call":
                            item = AutoPToolCall(
                                type="function_call", arguments="",
                                name=event.item.name, call_id=event.item.call_id,
                            )
                            self.conv.handle_event(item, event)
                            yield response_view

                    elif event.type == "response.reasoning_summary_text.delta":
                        # 模型思考过程 — 以可折叠块展示在 chatbot 中
                        thinking_text += event.delta
                        if thinking_eid is None:
                            thinking_eid = f"think_{int(time.time() * 1000)}"
                            think_html = (
                                '<details class="thinking-block" open>'
                                '<summary class="thinking-summary">🧠 思考中...</summary>'
                                '<div class="thinking-content">'
                                f'{_sanitize_thinking(thinking_text)}'
                                '</div></details>'
                            )
                            think_msg = ChatMessage(
                                role="assistant",
                                content=think_html,
                                metadata={"title": "思考过程", "id": thinking_eid, "status": "pending"},
                            )
                            self.conv.page_containers[thinking_eid] = think_msg
                            self.conv.page_response.append(think_msg)
                        else:
                            container = self.conv.page_containers[thinking_eid]
                            container.content = (
                                '<details class="thinking-block" open>'
                                '<summary class="thinking-summary">🧠 思考中...</summary>'
                                '<div class="thinking-content">'
                                f'{_sanitize_thinking(thinking_text)}'
                                '</div></details>'
                            )
                        yield response_view

                    elif event.type == "response.reasoning_summary_text.done":
                        if thinking_eid and thinking_eid in self.conv.page_containers:
                            container = self.conv.page_containers[thinking_eid]
                            container.content = (
                                '<details class="thinking-block">'
                                '<summary class="thinking-summary">🧠 思考完成 ✓</summary>'
                                '<div class="thinking-content">'
                                f'{_sanitize_thinking(thinking_text)}'
                                '</div></details>'
                            )
                            container.metadata["status"] = "done"
                        yield response_view

                    elif event.type == "response.output_text.done":
                        self.conv.page_containers[event.item_id].metadata["status"] = "done"

                    elif event.type == "response.function_call_arguments.delta":
                        self.conv.page_containers[event.item_id].content += f"{event.delta}"
                        yield response_view
                        self.conv.current_turn[event.item_id].arguments += event.delta

                    elif event.type == "response.function_call_arguments.done":
                        self.conv.page_containers[event.item_id].content += "\n- 工具参数完成, 开始执行...\n"
                        yield response_view

                        try:
                            tool_args = json.loads(event.arguments)
                        except Exception as e:
                            logger.info(f"工具参数解析异常: {e}")
                            tool_item = self.conv.current_turn.get(event.item_id)
                            failed_call_id = tool_item.call_id if tool_item else ""
                            result_item = AutoPToolCallResult(
                                type="function_call_output",
                                name=tool_item.name if tool_item else "",
                                output=f"工具参数解析异常: {e}",
                                call_id=failed_call_id, status="failed",
                            )
                            self.conv.handle_event(result_item, event)
                            yield response_view
                            continue

                        tool_item = self.conv.current_turn.get(event.item_id)
                        if not tool_item:
                            logger.error(f"未找到工具调用 item: {event.item_id}")
                            continue

                        pending_executions.append((
                            event.item_id,
                            tool_item.call_id,
                            tool_item.name,
                            tool_args,
                            event,
                        ))

                    elif event.type == "response.output_item.done":
                        if event.item.id in self.conv.current_turn:
                            self.conv.current_turn[event.item.id].status = "completed"

            # ---- 流结束后：批量执行本轮收集的所有工具调用 ----
            for item_id, call_id, tool_name, tool_args, event in pending_executions:
                tool_call = FunctionToolCall(
                    id=call_id,
                    function=Function(
                        name=tool_name,
                        arguments=json.dumps(tool_args, ensure_ascii=False),
                    ),
                    type="function",
                )

                exec_result = await self.execute_tool(tool_call)
                output = self._extract_tool_output(exec_result)
                result_item = AutoPToolCallResult(
                    type="function_call_output", name=tool_name,
                    output=output, call_id=call_id, status="completed",
                )
                self.conv.handle_event(result_item, event)

                # 截图工具：将图片注入对话，让模型下一轮能直接进行视觉分析
                raw_file_id = output.split('\n')[0].strip()
                if tool_name == 'take_screenshot' and raw_file_id.startswith('file-'):
                    img_msg = AutoPMessage(
                        role="user",
                        content=[
                            AutoPContentItem(type="input_text",
                                             text="截图已完成，以下是当前页面的截图，请基于截图内容进行视觉分析："),
                            AutoPIMGContentItem(type="input_image", file_id=raw_file_id, detail="high"),
                        ],
                    )
                    self.conv.current_turn[f"img_{call_id}"] = img_msg
                    logger.info(f"已将截图 {raw_file_id} 注入对话历史，供模型视觉分析")

                yield response_view

            # 无工具调用时，任务完成
            if not pending_executions:
                chat_stop = True

        self.conv.commit_turn()

    # -- 工具执行 --

    async def get_tool_from_session(
            self, tool_names: set[str], session: ClientSession | None = None
    ) -> list[Tool]:
        need_tools = []
        if session:
            all_tools = await session.list_tools()
            for tool in all_tools.tools:
                if tool.name in tool_names:
                    need_tools.append(tool)
        else:
            for tool in self.mcp.all_tools:
                if tool.name in tool_names:
                    need_tools.append(tool)
                    tool_names -= {tool.name}
        return need_tools

    async def execute_tool(self, tool_call: ToolCall) -> CallToolResult:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        server_name = self.mcp.get_server_name_for_tool(tool_name)
        server = self.mcp.get_session(server_name)
        if not server:
            return await auto_p_tools.build_tool_result(
                f"未找到{tool_name}工具对应的MCP服务", tool_call
            )
        logger.info(f"正在执行 {server_name} 服务的 {tool_name} 工具, 参数为: {tool_args}")

        special_method: Callable = auto_p_tools.special_methods.get(tool_name)
        if special_method:
            logger.info(f"正在执行特殊方法 {tool_name}")
            return await special_method(self, tool_call)

        if server_name == CHROME_DEVTOOLS_SERVICE:
            if not self.chrome_tools:
                self.chrome_tools = ChromeTools(server)
            return await self.chrome_tools.invoke_tool(tool_call)

        try:
            return await server.call_tool(tool_name, tool_args)
        except TimeoutError:
            logger.error(f"工具 {tool_name} 执行超时")
            return await auto_p_tools.build_tool_result(
                f"工具 {tool_name} 执行超时，请尝试简化操作或重试", tool_call
            )
        except Exception as e:
            logger.error(f"工具 {tool_name} 执行异常: {type(e).__name__}: {e}")
            return await auto_p_tools.build_tool_result(
                f"调用 {tool_name} 工具异常: {e}", tool_call
            )

    # -- 工具 Schema 构建 --

    async def _build_tool_search_system_prompt(self) -> str:
        lightweight_tools = []
        official_name = config.official_service_names
        for server_name, session in self.mcp.servers.items():
            if server_name == official_name:
                continue
            result = await session.list_tools()
            for tool in result.tools:
                lightweight_tools.append({"name": tool.name, "description": tool.description})

        logger.info(f"轻量化可用工具(已启用工具搜索模式): {len(lightweight_tools)}")
        descriptions = [
            f"- {cfg.description}" for cfg in self.mcp.service_configs.values()
        ]
        return fill_prompt(
            auto_p_prompts.system_prompts_lightweight_V3,
            mcp_tool_descriptions="\n".join(descriptions),
            lightweight_tools=json.dumps(lightweight_tools),
        )

    async def _build_tools_schema(self, tool_name: str | None = None) -> list[dict]:
        if tool_name:
            server = self.mcp.servers.get(tool_name)
            if server is None:
                return []
            result = await server.list_tools()
            return [convert_tool(t) for t in result.tools if t.name == tool_name]

        if self.tool_searcher and config.enable_tool_search:
            official_name = config.official_service_names
            session = self.mcp.servers.get(official_name)
            if session:
                result = await session.list_tools()
                logger.info(f"可用工具(已启用工具搜索模式): {len(result.tools)}")
                return [convert_tool(t) for t in result.tools]
            return []

        logger.info(f"可用工具(未启用工具搜索模式): {len(self.mcp.all_tools)}")
        return [convert_tool(t) for t in self.mcp.all_tools]

    @staticmethod
    def _decide_thinking(message: str, history_len: int) -> str:
        """根据任务复杂度动态决定是否启用推理。

        doubao-seed-1-6-flash 只支持 enabled / disabled（不支持 auto）。
        规则：
          - 第一个工具调用后的后续轮次 → disabled（执行阶段，不需要再思考）
          - 用户消息很短（≤8字）且不含多步关键词 → disabled
          - 否则 → enabled
        """
        # 后续 ReAct 轮次：工具已执行完，模型只需看结果决定下一步，不需要深度推理
        if history_len > 0:
            return "disabled"

        # 首轮：根据用户消息复杂度判断
        complex_keywords = {"然后", "并且", "之后", "接着", "搜索", "搜", "查找",
                            "对比", "比较", "分析", "总结", "提取", "告诉我",
                            "检查", "确认", "验证", "填写", "登录", "注册",
                            "并", "再", "又", "第一"}
        if len(message) <= 8 and not any(kw in message for kw in complex_keywords):
            return "disabled"
        return "enabled"

    # -- 工具方法 --

    def clear_chat_history(self, history: List[Any]) -> list:
        self.conv.clear()
        logger.info(f"已清空历史记录")
        return []

    @staticmethod
    def _extract_tool_output(result: CallToolResult) -> str:
        if result.content:
            content = result.content[0]
            if content.type == "text":
                return content.text
            if hasattr(content, "model_dump"):
                return content.model_dump_json()
        return json.dumps(result.structuredContent or {}, ensure_ascii=False)


def _sanitize_thinking(text: str) -> str:
    """对思考内容做 HTML 转义和换行处理，防 XSS 并保留可读性。"""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("\n\n", "</p><p>").replace("\n", "<br>")
    return f"<p>{text}</p>"
