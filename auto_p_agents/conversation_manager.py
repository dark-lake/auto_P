"""对话历史管理器 — 负责消息的存储、事件处理和页面渲染。

支持两种模式:
  1. 无 session_id: 纯内存模式（向后兼容）
  2. 有 session_id: 内存 + MySQL 持久化模式
"""

from __future__ import annotations

import uuid

from gradio.components.chatbot import ChatMessage
from openai.types.responses import ResponseStreamEvent

from auto_p_gui.message_items.message_models import (
    AutoPModel,
    AutoPMessage,
    AutoPContentItem,
    AutoPToolCall,
    AutoPToolCallResult,
    AutoPThinking,
)
from auto_p_services.session_repository import SessionRepository, get_session_repository
from auto_p_utils.config import config
from auto_p_utils.logger_util import logger


class ConversationManager:
    """管理单次对话轮次中的所有消息、事件和页面渲染容器。

    当设置了 session_id 且 repo 可用时，commit_turn() 会自动持久化到 MySQL。
    """

    def __init__(
            self,
            session_id: str | None = None,
            repo: SessionRepository | None = None,
    ):
        self.chat_history: list[AutoPModel] = []
        self.current_turn: dict[str, AutoPModel] = {}
        self.page_containers: dict[str, ChatMessage] = {}
        self.page_response: list = []

        # 会话持久化
        self.session_id: str | None = session_id
        self._repo: SessionRepository | None = repo or get_session_repository()

    # ── 会话加载 ──────────────────────────────────────────────

    def load_session(self, session_id: str) -> int:
        """从数据库加载指定会话的消息历史。返回加载的消息数。"""
        self.session_id = session_id
        self.clear()
        if self._repo:
            messages = self._repo.load_messages(session_id)
            self.chat_history = messages
            logger.info(f"已加载会话 {session_id}: {len(messages)} 条消息")
        return len(self.chat_history)

    def save_session(self) -> None:
        """将当前完整历史持久化到数据库。"""
        if not self.session_id or not self._repo:
            return
        self._repo.save_messages(self.session_id, self.chat_history)

    def save_in_progress(self) -> int:
        """保存进行中的对话（chat_history + current_turn）到数据库。
        
        用于会话切换时保留未提交的进行中消息。返回保存的消息总数。
        """
        if not self.session_id or not self._repo:
            return 0
        all_messages = self.chat_history + list(self.current_turn.values())
        if all_messages:
            self._repo.save_messages(self.session_id, all_messages)
            logger.info(
                f"保存进行中会话 {self.session_id}: "
                f"{len(self.chat_history)} 历史 + {len(self.current_turn)} 当前 = {len(all_messages)} 条"
            )
        return len(all_messages)

    def auto_title(self, first_message: str) -> None:
        """基于首条用户消息自动生成会话标题。"""
        if self.session_id and self._repo and config.session_auto_title:
            self._repo.auto_generate_title(self.session_id, first_message)

    # ── 消息管理 ──────────────────────────────────────────────

    def add_user_message(self, text: str):
        """添加用户消息，返回页面渲染结果列表。"""
        self.page_response.clear()
        msg = AutoPMessage(
            role="user",
            content=[AutoPContentItem(type="input_text", text=text)],
        )
        msg_id = str(uuid.uuid4())
        self.page_containers[f"user_{msg_id}"] = ChatMessage(
            role=msg.role, content=msg.content[0].text
        )
        self.page_response.append(self.page_containers[f"user_{msg_id}"])
        self._record(msg)

    def add_system_message(self, text: str):
        """添加系统提示词，不渲染到页面。"""
        msg = AutoPMessage(
            role="system",
            content=[AutoPContentItem(type="input_text", text=text)],
        )
        self._record(msg, key="system")

    def handle_event(
            self,
            item: AutoPModel,
            event: ResponseStreamEvent | None,
    ):
        """处理流式事件，更新页面和历史。

        event 可能为 None（用户消息）或流式事件对象。
        """
        if isinstance(item, AutoPMessage):
            return self._handle_message(item, event)
        if isinstance(item, AutoPToolCall):
            self._handle_tool_call(item, event)
        elif isinstance(item, AutoPToolCallResult):
            self._handle_tool_result(item, event)

    def _handle_message(self, item: AutoPMessage, event):
        if item.role == "assistant" and event and event.item.id not in self.current_turn:
            assist_msg = ChatMessage(role=item.role, content=item.content[0].text)
            self.page_containers[event.item.id] = assist_msg
            self.page_response.append(assist_msg)
            self.current_turn[event.item.id] = item
        elif item.role == "user":
            self.current_turn["user"] = item

    def _handle_tool_call(self, item: AutoPToolCall, event):
        if event and event.item.id not in self.current_turn:
            chat_msg = ChatMessage(
                role="assistant",
                content=f"- 调用工具: {event.item.name}\n- 工具参数为:",
                metadata={
                    "title": f"开始处理 {event.item.name} 工具",
                    "id": "tool running",
                    "status": "pending",
                },
            )
            self.page_containers[event.item.id] = chat_msg
            self.page_response.append(chat_msg)
            self.current_turn[event.item.id] = item

    def _handle_tool_result(self, item: AutoPToolCallResult, event):
        if not event:
            return
        event_id = getattr(event, "item_id", None)
        if event_id and event_id in self.current_turn:
            chat_msg = self.page_containers.get(event_id)
            if chat_msg:
                chat_msg.content += f"- 工具调用结果:{item.output[:64]}..."
                chat_msg.metadata["status"] = "done"
            self.current_turn[f"{event_id}_result"] = item
        else:
            logger.error(f"未找到对应的工具调用结果 event_id={event_id}")

    def _record(self, item: AutoPModel, key: str | None = None):
        self.current_turn[key or str(uuid.uuid4())] = item

    async def commit_turn(self):
        """提交这轮对话到全局历史，并持久化到数据库。"""
        self.chat_history.extend(self.current_turn.values())
        self.current_turn.clear()
        self._trim_history()

        # 持久化到 MySQL
        if self.session_id and self._repo:
            try:
                self._repo.save_messages(self.session_id, self.chat_history)
            except Exception as e:
                logger.error(f"保存会话到数据库失败: {e}")

    def _trim_history(self):
        """将历史中较旧的快照结果替换为简洁摘要。

        不做轮数限制，只对最旧（超出 threshold 范围）的 take_snapshot
        和 take_screenshot 结果做轻量压缩，保留关键上下文的同时控制 token 量。
        """
        threshold = config.history_trim_threshold
        truncate_len = config.screenshot_truncate_length
        heavy_tools = {"take_snapshot", "take_screenshot"}
        for item in self.chat_history[: max(0, len(self.chat_history) - threshold)]:
            if isinstance(item, AutoPToolCallResult) and item.name in heavy_tools:
                raw = str(item.output)
                if len(raw) > truncate_len:
                    item.output = (
                        f"[旧快照 — 原 {len(raw)} 字符] ...{raw[-truncate_len:]}"
                    )

    def clear(self):
        self.chat_history = []
        self.current_turn.clear()
        self.page_response.clear()

    def build_payload(self) -> list[dict]:
        """构建发给 LLM 的消息载荷。

        API 限制：function_call_output 不支持 name 字段，需剔除。
        function_call 只在流式上下文中出现，不需要额外过滤。
        thinking 内容不发送给 LLM。
        """
        payload: list[dict] = []
        for x in self.chat_history + list(self.current_turn.values()):
            if isinstance(x, AutoPThinking):
                continue  # 思考过程不发送给 LLM
            d = x.model_dump(mode="json")
            if d.get("type") == "function_call_output":
                d.pop("name", None)
            payload.append(d)
        return payload
