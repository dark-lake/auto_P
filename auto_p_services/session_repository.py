"""会话持久化存储 —— 基于 MySQL + pymysql（同步，无 event loop 依赖）。

表结构:
  - sessions: id (UUID), title, created_at, updated_at
  - messages: id (自增), session_id (FK), role, content (JSON),
              tool_calls (JSON), tool_call_id, name, created_at, seq
"""

from __future__ import annotations

import json
import uuid
from threading import Lock
from typing import Any, Optional

import pymysql
from pymysql.cursors import DictCursor

from auto_p_gui.message_items.message_models import (
    AutoPModel,
    AutoPMessage,
    AutoPContentItem,
    AutoPIMGContentItem,
    AutoPToolCall,
    AutoPToolCallResult,
    AutoPThinking,
)
from auto_p_utils.config import config
from auto_p_utils.logger_util import logger

# ─── DB 连接（线程安全单连接） ──────────────────────────────────

_conn: pymysql.Connection | None = None
_conn_lock = Lock()


def _get_conn() -> pymysql.Connection:
    """获取或创建 MySQL 连接（线程安全的惰性单例）。"""
    global _conn
    if _conn is None or not _conn.open:
        with _conn_lock:
            if _conn is None or not _conn.open:
                _conn = pymysql.connect(
                    host=config.mysql_host,
                    port=config.mysql_port,
                    user=config.mysql_user,
                    password=config.mysql_password,
                    database=config.mysql_db,
                    charset="utf8mb4",
                    autocommit=True,
                    cursorclass=DictCursor,
                )
                logger.info("MySQL 连接已建立 (host=127.0.0.1, db=auto_p)")
    return _conn


def close_conn() -> None:
    """关闭 MySQL 连接。"""
    global _conn
    with _conn_lock:
        if _conn and _conn.open:
            _conn.close()
            _conn = None
            logger.info("MySQL 连接已关闭")


# ─── 消息序列化 / 反序列化 ────────────────────────────────────


def _serialize_content(content: list) -> list:
    """将 Pydantic 模型的 content 列表转为 JSON-safe dict 列表。"""
    result = []
    for c in content:
        if hasattr(c, "model_dump"):
            result.append(c.model_dump(mode="json"))
        else:
            result.append(c)
    return result


def _serialize_message(msg: AutoPModel) -> dict:
    """将 AutoPModel 序列化为 DB 行字段。"""
    row: dict[str, Any] = {}

    if isinstance(msg, AutoPMessage):
        row["role"] = "user" if msg.role == "user" else msg.role
        row["content"] = json.dumps(_serialize_content(msg.content), ensure_ascii=False)
    elif isinstance(msg, AutoPToolCall):
        row["role"] = "function_call"
        row["content"] = json.dumps({
            "name": msg.name,
            "arguments": msg.arguments,
            "call_id": msg.call_id,
            "status": msg.status,
        }, ensure_ascii=False)
        row["name"] = msg.name
        row["tool_call_id"] = msg.call_id
    elif isinstance(msg, AutoPToolCallResult):
        row["role"] = "function_call_output"
        row["content"] = json.dumps({
            "name": msg.name,
            "output": msg.output,
            "call_id": msg.call_id,
            "status": msg.status,
        }, ensure_ascii=False)
        row["name"] = msg.name
        row["tool_call_id"] = msg.call_id

    elif isinstance(msg, AutoPThinking):
        row["role"] = "thinking"
        row["content"] = json.dumps({
            "content": msg.content,
            "status": msg.status,
        }, ensure_ascii=False)

    return row


def _deserialize_message(role: str, content_str: str,
                         name: str | None = None,
                         tool_call_id: str | None = None) -> AutoPModel:
    """从 DB 行字段反序列化为 AutoPModel。"""
    data = json.loads(content_str)

    if role in ("user", "assistant", "system"):
        items = []
        for c in data:
            t = c.get("type", "")
            if t == "input_image":
                items.append(AutoPIMGContentItem(**c))
            else:
                items.append(AutoPContentItem(**c))
        return AutoPMessage(role=role, content=items)

    elif role == "function_call":
        return AutoPToolCall(
            type="function_call",
            name=data.get("name", name or ""),
            arguments=data.get("arguments", ""),
            call_id=data.get("call_id", tool_call_id or ""),
            status=data.get("status", "completed"),
        )

    elif role == "function_call_output":
        return AutoPToolCallResult(
            type="function_call_output",
            name=data.get("name", name or ""),
            output=data.get("output", ""),
            call_id=data.get("call_id", tool_call_id or ""),
            status=data.get("status", "completed"),
        )

    elif role == "thinking":
        return AutoPThinking(
            type="thinking",
            content=data.get("content", ""),
            status=data.get("status", "completed"),
        )

    raise ValueError(f"未知消息角色: {role}")


# ─── 会话 CRUD ────────────────────────────────────────────────


class SessionRepository:
    """会话与消息的数据库访问层（同步，pymysql）。"""

    # ── 会话操作 ──

    def create_session(self, title: str = "新会话") -> str:
        """创建新会话，返回 session_id。"""
        sid = str(uuid.uuid4())
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (id, title) VALUES (%s, %s)",
                (sid, title),
            )
        logger.info(f"创建会话: id={sid}, title={title}")
        return sid

    def get_session(self, session_id: str) -> dict | None:
        """获取单个会话信息。"""
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, created_at, updated_at FROM sessions WHERE id=%s",
                (session_id,),
            )
            return cur.fetchone()

    def list_sessions(self, limit: int = 100) -> list[dict]:
        """列出所有会话，按创建时间倒序。"""
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, created_at, updated_at "
                "FROM sessions ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            return cur.fetchall()

    def delete_session(self, session_id: str) -> bool:
        """删除会话及其所有消息（CASCADE）。"""
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM sessions WHERE id=%s", (session_id,)
            )
            deleted = cur.rowcount
        logger.info(f"删除会话: id={session_id}, rows={deleted}")
        return deleted > 0

    def update_title(self, session_id: str, title: str) -> None:
        """更新会话标题。"""
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sessions SET title=%s WHERE id=%s",
                (title, session_id),
            )

    def update_updated_at(self, session_id: str) -> None:
        """触发 updated_at 自动更新。"""
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sessions SET updated_at=NOW() WHERE id=%s",
                (session_id,),
            )

    # ── 消息操作 ──

    def save_messages(self, session_id: str, messages: list[AutoPModel]) -> None:
        """批量保存消息（先删旧消息再插入，事务包裹）。"""
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM messages WHERE session_id=%s", (session_id,)
            )
            for seq, msg in enumerate(messages):
                row = _serialize_message(msg)
                cur.execute(
                    "INSERT INTO messages "
                    "(session_id, role, content, name, tool_call_id, seq) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        session_id,
                        row.get("role", ""),
                        row.get("content", ""),
                        row.get("name"),
                        row.get("tool_call_id"),
                        seq,
                    ),
                )
            cur.execute(
                "UPDATE sessions SET updated_at=NOW() WHERE id=%s",
                (session_id,),
            )
        logger.info(f"保存消息: session={session_id}, count={len(messages)}")

    def load_messages(self, session_id: str) -> list[AutoPModel]:
        """加载会话的全部消息。"""
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content, name, tool_call_id "
                "FROM messages WHERE session_id=%s ORDER BY seq ASC",
                (session_id,),
            )
            rows = cur.fetchall()

        result: list[AutoPModel] = []
        for row in rows:
            try:
                msg = _deserialize_message(
                    role=row["role"],
                    content_str=row["content"],
                    name=row.get("name"),
                    tool_call_id=row.get("tool_call_id"),
                )
                result.append(msg)
            except Exception as e:
                logger.warning(f"跳过损坏的消息: {e}, row={row}")
        logger.info(f"加载消息: session={session_id}, count={len(result)}")
        return result

    def get_message_count(self, session_id: str) -> int:
        """获取会话的消息数量。"""
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id=%s",
                (session_id,),
            )
            row = cur.fetchone()
            return row["COUNT(*)"] if row else 0

    def auto_generate_title(self, session_id: str,
                            first_message: str) -> str:
        """基于首条消息自动生成标题（截断）。"""
        title = first_message.strip()[:30]
        if len(first_message.strip()) > 30:
            title += "..."
        if not title:
            title = "新会话"
        self.update_title(session_id, title)
        return title

    def delete_all(self) -> int:
        """⚠️ 危险操作：删除所有会话和消息。返回删除的会话数。"""
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM messages")
            cur.execute("DELETE FROM sessions")
            return cur.rowcount


# ─── 全局单例 ──────────────────────────────────────────────────

_repo_instance: Optional[SessionRepository] = None


def get_session_repository() -> SessionRepository:
    """获取 SessionRepository 全局单例。"""
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = SessionRepository()
    return _repo_instance
