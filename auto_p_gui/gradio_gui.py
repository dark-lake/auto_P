"""auto_p Gradio GUI -- 极简风格 + 左侧会话栏."""

import asyncio
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import gradio as gr

from auto_p_agents.AutoPAgent import AutoProcessAgent
from auto_p_services.session_repository import get_session_repository

client = AutoProcessAgent()

CUSTOM_CSS = """
footer { display: none !important; }

/* ============================================================
   页面底色
   ============================================================ */
.gradio-container {
    background: #0f1117 !important;
    max-width: 100% !important;
    height: 100vh !important;
    max-height: 100vh !important;
    overflow: hidden !important;
}

/* ============================================================
   整体布局 — 左侧栏 + 右侧主区域
   ============================================================ */
.main-row {
    gap: 0 !important;
    height: 100vh !important;
    max-height: 100vh !important;
    overflow: hidden !important;
}
.main-row > .column:first-child {
    max-width: 260px !important;
    min-width: 240px !important;
}
.main-row > .column:last-child {
    flex: 1 !important;
}

/* ============================================================
   左侧会话栏
   ============================================================ */
#sidebar {
    background: #0d1117 !important;
    border-right: 1px solid #21262d !important;
    padding: 12px !important;
    height: 100vh !important;
    overflow-y: auto !important;
}

#sidebar h3 {
    color: #e1e4e8 !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    margin: 0 0 10px 0 !important;
    padding: 0 !important;
}

#sidebar button {
    background: #21262d !important;
    color: #c9d1d9 !important;
    border: 1px solid #30363d !important;
    font-size: 13px !important;
    padding: 6px 12px !important;
    border-radius: 6px !important;
    cursor: pointer !important;
}
#sidebar button:hover {
    background: #30363d !important;
}
#sidebar button.primary {
    background: #238636 !important;
    color: #ffffff !important;
    border-color: #238636 !important;
}
#sidebar button.danger {
    background: transparent !important;
    color: #f85149 !important;
    border-color: #f8514950 !important;
}
#sidebar button.danger:hover {
    background: #da363320 !important;
}

/* 会话列表（HTML 渲染，按日期分组） */
#session_list {
    flex: 1;
    overflow-y: auto;
}
.session-date-group {
    margin-bottom: 8px;
}
.session-date-header {
    color: #6e7681 !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    padding: 8px 6px 4px 6px !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    position: sticky;
    top: 0;
    background: #0d1117;
    z-index: 1;
}
.session-item {
    display: flex !important;
    align-items: center !important;
    padding: 8px 10px !important;
    border-radius: 6px !important;
    margin: 2px 0 !important;
    cursor: pointer !important;
    color: #8b949e !important;
    font-size: 13px !important;
    background: transparent !important;
    transition: background 0.15s !important;
    white-space: nowrap !important;
    overflow: hidden !important;
}
.session-item:hover {
    background: #1c2128 !important;
    color: #c9d1d9 !important;
}
.session-item.active {
    background: #1c2128 !important;
    color: #e1e4e8 !important;
    border-left: 3px solid #58a6ff !important;
}
.session-item .session-title {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
}
.session-item .session-time {
    color: #484f58 !important;
    font-size: 11px !important;
    margin-left: 6px;
    flex-shrink: 0;
}
.session-item.active .session-time {
    color: #6e7681 !important;
}

/* HTML 容器：去除 Gradio 默认 padding */
#session_list_container {
    padding: 0 !important;
    flex: 1;
    overflow-y: auto;
}

/* 隐藏的 session_click Textbox */
#session_click_hidden {
    display: none !important;
}

/* ============================================================
   标题 / Markdown 文字
   ============================================================ */
.gradio-container .prose,
.gradio-container .prose p,
.gradio-container .prose h1,
.gradio-container .prose h2,
.gradio-container .prose h3 {
    color: #e1e4e8 !important;
}

/* ============================================================
   聊天区
   ============================================================ */
#chatbot {
    flex: 1 !important;
    border: none !important;
    background: #0f1117 !important;
}
#chatbot .wrap { padding: 16px 20px !important; }

/* ============================================================
   用户气泡：蓝底白字
   ============================================================ */
#chatbot .user {
    background: #2563eb !important;
    border-radius: 12px 12px 4px 12px !important;
}
#chatbot .user p,
#chatbot .user span,
#chatbot .user li {
    color: #ffffff !important;
}

/* ============================================================
   机器人气泡：深灰底，浅灰字
   ============================================================ */
#chatbot .bot {
    background: #1c1f26 !important;
    border-radius: 12px 12px 12px 4px !important;
    border: 1px solid #30363d !important;
}
#chatbot .bot p,
#chatbot .bot span,
#chatbot .bot li,
#chatbot .bot h1,
#chatbot .bot h2,
#chatbot .bot h3,
#chatbot .bot h4 {
    color: #e1e4e8 !important;
}

/* ============================================================
   thinking / 工具调用子框
   ============================================================ */
#chatbot .bot .thinking-block,
#chatbot .bot details.plan-block {
    background: #0d1117 !important;
    border: 1px solid #21262d !important;
    border-radius: 8px !important;
    margin: 8px 0 !important;
}
#chatbot .bot .thinking-block .thinking-summary,
#chatbot .bot details.plan-block > summary {
    color: #8b949e !important;
}
#chatbot .bot .thinking-block .thinking-content,
#chatbot .bot details.plan-block .plan-content {
    color: #6e7681 !important;
}

/* ============================================================
   代码块
   ============================================================ */
#chatbot .bot pre {
    background: #0d1117 !important;
    color: #c9d1d9 !important;
    border: 1px solid #21262d !important;
}
#chatbot .bot code {
    color: #c9d1d9 !important;
}

/* ============================================================
   输入框
   ============================================================ */
.gradio-container textarea {
    background: #16181d !important;
    color: #e1e4e8 !important;
    border: 1px solid #30363d !important;
}
.gradio-container textarea::placeholder {
    color: #484f58 !important;
}

/* ============================================================
   按钮
   ============================================================ */
.gradio-container button {
    background: #21262d !important;
    color: #c9d1d9 !important;
    border: 1px solid #30363d !important;
}
.gradio-container button.primary {
    background: #238636 !important;
    color: #ffffff !important;
    border-color: #238636 !important;
}
.gradio-container button.stop {
    background: #da3633 !important;
    color: #ffffff !important;
    border-color: #da3633 !important;
}

/* ============================================================
   加载动画（打字气泡）
   ============================================================ */
.typing-indicator {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 0;
}
.typing-indicator span {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #8b949e;
    animation: typing-bounce 1.4s infinite ease-in-out both;
}
.typing-indicator span:nth-child(1) { animation-delay: 0s; }
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing-bounce {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
    40% { transform: scale(1); opacity: 1; }
}

/* ============================================================
   右侧主区域：flex 布局，chatbot 弹性填充，底部固定
   ============================================================ */
#main_area {
    display: flex !important;
    flex-direction: column !important;
    height: 100vh !important;
    max-height: 100vh !important;
    overflow: hidden !important;
}

/* 标题不收缩 */
#main_area > .markdown,
#main_area > .prose,
#main_area > .html {
    flex-shrink: 0 !important;
}

/* 连接状态行（标题下方，不收缩） */
#conn_bar {
    flex-shrink: 0 !important;
    padding: 4px 16px 8px 16px !important;
}
#conn_bar .row {
    gap: 8px !important;
    align-items: stretch !important;
}
#connect_btn {
    height: 100% !important;
}

/* Chatbot 弹性填充剩余空间，内部滚动 */
#chatbot {
    flex: 1 1 0 !important;
    min-height: 0 !important;
    height: auto !important;
}

/* 如果 chatbot 被 Gradio 包裹在 wrapper div 中，让 wrapper 也弹性填充 */
#main_area > div:has(> #chatbot) {
    flex: 1 1 0 !important;
    min-height: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
}
#main_area > div:has(> #chatbot) > #chatbot {
    flex: 1 1 0 !important;
    min-height: 0 !important;
}

/* 底部输入区域：固定在底部，不伸缩不增长 */
#bottom_bar {
    flex: 0 0 auto !important;
    padding: 8px 16px 28px 16px !important;
    border-top: 1px solid #21262d !important;
    background: #0f1117 !important;
}
#bottom_bar .row {
    gap: 8px !important;
}

/* 发送/停止按钮高度与输入框一致 */
#bottom_bar > .row:first-child {
    align-items: stretch !important;
}
#send_btn, #stop_btn {
    height: 100% !important;
}

/* 侧边栏底部也留白，删除按钮不贴底 */
#sidebar {
    padding-bottom: 28px !important;
}
"""

LOADING_HTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>'


def _sanitize_thinking(text: str) -> str:
    """对思考内容做 HTML 转义和换行处理，防 XSS 并保留可读性。"""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("\n\n", "</p><p>").replace("\n", "<br>")
    return f"<p>{text}</p>"


def _format_date_label(dt: datetime) -> str:
    """将日期格式化为分组标题：今天 / 昨天 / M月D日 / YYYY年M月D日。"""
    today = date.today()
    d = dt.date() if isinstance(dt, datetime) else dt
    if d == today:
        return "今天"
    elif d == today - timedelta(days=1):
        return "昨天"
    elif d.year == today.year:
        return f"{d.month}月{d.day}日"
    else:
        return f"{d.year}年{d.month}月{d.day}日"


def _build_session_html(sessions: list[dict], current_sid: str = "") -> str:
    """将会话列表按创建日期分组，渲染为 HTML。"""
    if not sessions:
        return '<div id="session_list"><p style="color:#484f58;font-size:13px;padding:12px;">暂无会话</p></div>'

    # 按 created_at 日期分组
    groups: dict[str, list[dict]] = {}
    for s in sessions:
        created = s.get("created_at")
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except Exception:
                created = datetime.now()
        elif not isinstance(created, datetime):
            created = datetime.now()
        key = _format_date_label(created)
        groups.setdefault(key, []).append(s)

    # 构建 HTML
    # inline onclick：不依赖全局函数，避免 innerHTML 插入 <script> 不执行的问题
    _onclick_js = (
        "var e=document.querySelector('#session_click_hidden textarea')"
        "||document.querySelector('#session_click_hidden input');"
        "if(e){e.value=this.getAttribute('data-sid');"
        "e.dispatchEvent(new Event('input',{bubbles:true}));"
        "e.dispatchEvent(new Event('change',{bubbles:true}));}"
    )

    parts = ['<div id="session_list">']
    for date_label, group_sessions in groups.items():
        parts.append(f'<div class="session-date-group">')
        parts.append(f'<div class="session-date-header">{date_label}</div>')
        for s in group_sessions:
            sid = s["id"]
            title = s.get("title", "新会话")
            if len(title) > 20:
                title = title[:20] + "…"
            updated = s.get("updated_at", "")
            if isinstance(updated, datetime):
                time_str = updated.strftime("%H:%M")
            elif isinstance(updated, str) and len(updated) >= 16:
                time_str = updated[11:16]
            else:
                time_str = ""
            active_cls = " active" if sid == current_sid else ""
            parts.append(
                f'<div class="session-item{active_cls}" '
                f'data-sid="{sid}" '
                f'onclick="{_onclick_js}">'
                f'<span class="session-title">{title}</span>'
                f'<span class="session-time">{time_str}</span>'
                f'</div>'
            )
        parts.append('</div>')
    parts.append('</div>')

    return "\n".join(parts)


async def _init_session() -> tuple[str, str, list, list[dict]]:
    """页面首次加载：确保至少有一个会话，返回当前 session_id 和 HTML 列表。"""
    repo = get_session_repository()
    sessions = repo.list_sessions()
    if not sessions:
        sid = repo.create_session("新会话")
        sessions = repo.list_sessions()
    else:
        sid = sessions[0]["id"]

    # 切换到最新会话
    await client.switch_session(sid)

    html = _build_session_html(sessions, sid)
    # 加载消息到 chatbot
    chatbot_value = await _load_chatbot_from_history()
    return sid, html, chatbot_value, sessions


async def _load_chatbot_from_history() -> list:
    """从当前 ConversationManager 的内存历史构建 Chatbot 显示列表。

    完整还原：思考过程、用户消息、助手消息、工具调用（含参数）、工具结果。
    """
    from auto_p_gui.message_items.message_models import (
        AutoPMessage, AutoPToolCall, AutoPToolCallResult, AutoPThinking,
    )
    result = []
    for msg in client.conv.chat_history:
        if isinstance(msg, AutoPThinking):
            # 还原思考过程折叠块
            think_html = (
                '<details class="thinking-block">'
                '<summary class="thinking-summary">🧠 思考完成 ✓</summary>'
                f'<div class="thinking-content">{_sanitize_thinking(msg.content)}</div>'
                '</details>'
            )
            result.append({
                "role": "assistant",
                "content": think_html,
                "metadata": {"title": "思考过程", "id": "think_loaded", "status": "done"},
            })
        elif isinstance(msg, AutoPMessage) and msg.role == "user":
            text = msg.content[0].text if msg.content else ""
            result.append({"role": "user", "content": text})
        elif isinstance(msg, AutoPMessage) and msg.role == "assistant":
            text = msg.content[0].text if msg.content else ""
            if text:
                result.append({"role": "assistant", "content": text})
        elif isinstance(msg, AutoPToolCall):
            # 还原工具调用（含参数）
            args_display = msg.arguments if msg.arguments else "无参数"
            if len(args_display) > 500:
                args_display = args_display[:500] + "…"
            result.append({
                "role": "assistant",
                "content": f"🔧 调用工具: {msg.name}\n参数: {args_display}",
                "metadata": {"title": f"工具: {msg.name}", "id": "tool done", "status": "done"},
            })
        elif isinstance(msg, AutoPToolCallResult):
            # 还原工具结果
            output_str = str(msg.output) if msg.output else ""
            if len(output_str) > 500:
                output_str = output_str[:500] + "…"
            result.append({
                "role": "assistant",
                "content": f"📋 工具结果 ({msg.name}):\n{output_str}",
                "metadata": {"title": f"结果: {msg.name}", "id": "result done", "status": "done"},
            })
    return result


async def handle_new_session(current_sid: str, current_status: str) -> tuple[str, str, list, list[dict], str]:
    """新建会话。"""
    sid = await client.create_session("新会话")
    repo = get_session_repository()
    sessions = repo.list_sessions()
    html = _build_session_html(sessions, sid)
    return sid, html, [], sessions, current_status


async def handle_delete_session(current_sid: str, current_status: str) -> tuple[str, str, list, list[dict], str]:
    """删除当前会话。"""
    if not current_sid:
        return current_sid, "", [], [], current_status

    repo = get_session_repository()
    await client.delete_session(current_sid)

    sessions = repo.list_sessions()
    if sessions:
        new_sid = sessions[0]["id"]
        await client.switch_session(new_sid)
        chatbot_value = await _load_chatbot_from_history()
    else:
        # 所有会话都被删了，创建一个新的
        new_sid = await client.create_session("新会话")
        sessions = repo.list_sessions()
        chatbot_value = []

    html = _build_session_html(sessions, new_sid)
    return new_sid, html, chatbot_value, sessions, current_status


async def handle_select_session(new_sid: str, current_status: str) -> tuple[list, str, str]:
    """切换到选中的会话。连接状态保持不变。"""
    if not new_sid:
        return [], "", current_status
    await client.switch_session(new_sid)
    chatbot_value = await _load_chatbot_from_history()
    return chatbot_value, new_sid, current_status


async def handle_submit(message: str, history: list):
    """处理用户消息提交。"""
    if not message or not message.strip():
        yield history + [{
            "role": "assistant",
            "content": "❓ 请输入你想让我做的事情。"
        }], ""
        return

    try:
        async for result in client.process_message(message, history):
            new_history, cleared_msg = result
            base_len = len(history)

            filtered = list(new_history[:base_len])
            has_assistant_content = False
            for i in range(base_len, len(new_history)):
                item = new_history[i]
                role = (item.get("role") if isinstance(item, dict)
                        else getattr(item, "role", None))
                content = str(item.get("content", "") if isinstance(item, dict)
                              else getattr(item, "content", ""))
                if role == "assistant" and not content.strip():
                    continue
                if role == "assistant":
                    has_assistant_content = True
                filtered.append(item)

            if not has_assistant_content:
                filtered.append({"role": "assistant", "content": LOADING_HTML})

            yield filtered, cleared_msg
    except Exception as e:
        yield history + [{
            "role": "assistant",
            "content": f"⚠️ **处理请求时发生异常**\n\n{type(e).__name__}: {e}",
        }], ""


def handle_stop():
    """中断正在执行的任务。"""
    return client.cancel_execution()


def _show_stop_btn():
    """隐藏发送按钮，显示停止按钮。"""
    return gr.update(visible=False), gr.update(visible=True)


def _show_send_btn():
    """显示发送按钮，隐藏停止按钮。"""
    return gr.update(visible=True), gr.update(visible=False)


import threading

# ── 持久化 event loop（aiomysql 连接池绑定，不能每次新建） ──

_ASYNC_LOOP: asyncio.AbstractEventLoop | None = None
_ASYNC_LOOP_LOCK = threading.Lock()


def _get_async_loop() -> asyncio.AbstractEventLoop:
    """获取或创建持久化 event loop，在后台线程中运行。"""
    global _ASYNC_LOOP
    with _ASYNC_LOOP_LOCK:
        if _ASYNC_LOOP is None or _ASYNC_LOOP.is_closed():
            _ASYNC_LOOP = asyncio.new_event_loop()
            threading.Thread(target=_ASYNC_LOOP.run_forever, daemon=True).start()
        return _ASYNC_LOOP


def _run_async(fn, *args, **kwargs):
    """在持久化 event loop 中运行异步函数（线程安全）。"""
    loop = _get_async_loop()
    coro = fn(*args, **kwargs)
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


def init_session_sync():
    return _run_async(_init_session)


def new_session_sync(current_sid, current_status):
    return _run_async(handle_new_session, current_sid, current_status)


def delete_session_sync(current_sid, current_status):
    return _run_async(handle_delete_session, current_sid, current_status)


def select_session_sync(new_sid, current_status):
    return _run_async(handle_select_session, new_sid, current_status)


async def refresh_sidebar(current_sid: str):
    """刷新左侧会话栏。"""
    repo = get_session_repository()
    sessions = repo.list_sessions()
    html = _build_session_html(sessions, current_sid)
    return html, current_sid, sessions


def refresh_sidebar_sync(current_sid):
    return _run_async(refresh_sidebar, current_sid)


def gradio_interface() -> gr.Blocks:
    with gr.Blocks(
            title="auto_p - 智能浏览器助手",
            fill_height=True,
    ) as demo:
        # 隐藏状态：当前会话 ID
        current_sid = gr.State("")
        sessions_state = gr.State([])

        with gr.Row(elem_classes="main-row"):
            # ── 左侧会话栏 ──
            with gr.Column(scale=0, elem_id="sidebar"):
                gr.Markdown("### 💬 会话")

                # 会话列表（HTML 渲染，按日期分组）
                session_html = gr.HTML(
                    value='<div id="session_list"></div>',
                    elem_id="session_list_container",
                )

                # 隐藏 Textbox：JavaScript 点击会话项后设置其值，触发 change 事件
                # 注意：不能用 visible=False，Gradio 6.1 会完全移除元素，JS 找不到。
                # 用 CSS display:none 隐藏，确保元素在 DOM 中。
                session_click = gr.Textbox(
                    elem_id="session_click_hidden",
                    container=False,
                    show_label=False,
                )

                with gr.Row():
                    new_btn = gr.Button("＋ 新建", scale=1, size="sm")
                    delete_btn = gr.Button("🗑 删除", scale=1, size="sm",
                                           elem_classes="danger")

            # ── 右侧主区域 ──
            with gr.Column(scale=1, elem_id="main_area"):
                gr.Markdown("# auto_p\n用自然语言控制浏览器")

                # 连接状态（左） + 连接按钮（右），标题下方同一行
                with gr.Row(elem_id="conn_bar"):
                    status = gr.Textbox(
                        value="⚫ 未连接",
                        interactive=False,
                        show_label=False,
                        container=False,
                        scale=85,
                    )
                    connect_btn = gr.Button(
                        "🔌 连接", variant="secondary", scale=15,
                        elem_id="connect_btn",
                    )

                chatbot = gr.Chatbot(
                    value=[],
                    elem_id="chatbot",
                    avatar_images=(
                        str(_project_root / "avatar" / "user.png"),
                        str(_project_root / "avatar" / "robot.png"),
                    ),
                    layout="bubble",
                    show_label=False,
                    sanitize_html=False,
                )

                # ── 底部固定区域：输入框 + 发送/停止按钮 ──
                with gr.Column(elem_id="bottom_bar"):
                    with gr.Row():
                        msg = gr.Textbox(
                            placeholder="告诉浏览器你想做什么…（回车发送，Shift+回车换行）",
                            show_label=False,
                            scale=85,
                            lines=2,
                            container=False,
                        )
                        # 发送/停止 同位交替：同一时刻只显示一个，视觉上是"一个按钮变形"
                        send_btn = gr.Button(
                            "发送", variant="primary", scale=15,
                            elem_id="send_btn",
                        )
                        stop_btn = gr.Button(
                            "停止", variant="stop", scale=15,
                            elem_id="stop_btn", visible=False,
                        )

        # ── 事件绑定 ──

        # 页面加载：初始化会话 + 注入回车发送 JS
        _enter_submit_js = """() => {
            document.addEventListener('keydown', (e) => {
                if (e.key !== 'Enter') return;
                const ta = e.target;
                if (!ta || ta.tagName !== 'TEXTAREA' || !ta.closest('#bottom_bar')) return;

                if (e.shiftKey) {
                    // Shift+Enter: 手动插入换行符，彻底绕过 Gradio 拦截
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    const s = ta.selectionStart, en = ta.selectionEnd;
                    ta.value = ta.value.substring(0, s) + '\\n' + ta.value.substring(en);
                    ta.selectionStart = ta.selectionEnd = s + 1;
                    ta.dispatchEvent(new Event('input', {bubbles: true}));
                    return;
                }
                if (e.ctrlKey || e.metaKey || e.altKey) return;
                // 纯 Enter: 发送
                e.preventDefault();
                e.stopImmediatePropagation();
                const sendContainer = document.querySelector('#send_btn');
                if (!sendContainer) return;
                const btn = sendContainer.querySelector('button') || sendContainer;
                if (!btn) return;
                btn.click();
            }, true);
            return [];
        }"""
        demo.load(
            fn=init_session_sync,
            outputs=[current_sid, session_html, chatbot, sessions_state],
            js=_enter_submit_js,
        )

        # ── 发送/停止 按钮交替逻辑 ──
        # 点击发送 → 隐藏发送、显示停止 → 执行 handle_submit 生成器 → 完成后切回发送 → 刷新侧栏
        # 点击停止 → 调用 cancel_execution → 生成器检测到取消后结束 → .then() 自动切回发送

        # send_btn.click (点击发送 / 回车发送均触发此链路)
        send_btn.click(
            fn=_show_stop_btn,
            outputs=[send_btn, stop_btn],
        ).then(
            fn=handle_submit,
            inputs=[msg, chatbot],
            outputs=[chatbot, msg],
            concurrency_limit=1,
        ).then(
            fn=_show_send_btn,
            outputs=[send_btn, stop_btn],
        ).then(
            fn=refresh_sidebar_sync,
            inputs=[current_sid],
            outputs=[session_html, current_sid, sessions_state],
        )

        # stop_btn.click (点击停止)
        stop_btn.click(
            fn=handle_stop,
            outputs=[status],
        ).then(
            fn=_show_send_btn,
            outputs=[send_btn, stop_btn],
        )

        connect_btn.click(fn=client.connect_by_config, outputs=[status])

        # 新建会话（传入 status 保持连接状态不变）
        new_btn.click(
            fn=new_session_sync,
            inputs=[current_sid, status],
            outputs=[current_sid, session_html, chatbot, sessions_state, status],
        )

        # 删除会话（传入 status 保持连接状态不变）
        delete_btn.click(
            fn=delete_session_sync,
            inputs=[current_sid, status],
            outputs=[current_sid, session_html, chatbot, sessions_state, status],
        )

        # 切换会话（通过隐藏 Textbox 的 change 事件触发，传入 status 保持连接状态不变）
        session_click.change(
            fn=select_session_sync,
            inputs=[session_click, status],
            outputs=[chatbot, current_sid, status],
        ).then(
            fn=refresh_sidebar_sync,
            inputs=[current_sid],
            outputs=[session_html, current_sid, sessions_state],
        )

    demo.queue(default_concurrency_limit=3)
    return demo


if __name__ == "__main__":
    interface = gradio_interface()
    interface.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        css=CUSTOM_CSS,
    )
