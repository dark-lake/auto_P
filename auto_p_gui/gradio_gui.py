"""auto_p Gradio GUI -- 极简风格."""

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import gradio as gr

from auto_p_agents.AutoPAgent import AutoProcessAgent

client = AutoProcessAgent()

CUSTOM_CSS = """
footer { display: none !important; }

/* ============================================================
   页面底色
   ============================================================ */
.gradio-container {
    background: #0f1117 !important;
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
   机器人气泡：深灰底，浅灰字（白底黑字的相反方案）
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
   thinking / 工具调用子框：更深底色 + 更暗文字（区别于最终答案）
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
"""


def gradio_interface() -> gr.Blocks:
    with gr.Blocks(
            title="auto_p - 智能浏览器助手",
            fill_height=True,
    ) as demo:

        gr.Markdown("# auto_p\n用自然语言控制浏览器")

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
            height="calc(100vh - 210px)",
        )

        with gr.Row():
            msg = gr.Textbox(
                placeholder="告诉浏览器你想做什么，比如：打开百度搜索 Python",
                show_label=False,
                scale=1,
                lines=2,
                container=False,
            )
            submit_btn = gr.Button(
                "发送", variant="primary", scale=0, min_width=55,
            )
            stop_btn = gr.Button(
                "⏹ 停止", variant="stop", scale=0, min_width=55,
            )

        status = gr.Textbox(
            value="⚫ 未连接",
            interactive=False,
            show_label=False,
            container=False,
        )

        with gr.Row():
            connect_btn = gr.Button("🔌 连接", variant="secondary", size="sm")
            clear_btn = gr.Button("🗑 清空", variant="secondary", size="sm")

        # ── 事件 ──

        async def handle_submit(message: str, history: list):
            if not message or not message.strip():
                yield history + [{
                    "role": "assistant",
                    "content": "❓ 请输入你想让我做的事情。"
                }], ""
                return

            async for result in client.process_message(message, history):
                yield result

        def handle_stop():
            """中断正在执行的任务。"""
            return client.cancel_execution()

        connect_btn.click(fn=client.connect_by_config, outputs=[status])

        msg.submit(
            fn=handle_submit,
            inputs=[msg, chatbot],
            outputs=[chatbot, msg],
            concurrency_limit=3,
        )
        submit_btn.click(
            fn=handle_submit,
            inputs=[msg, chatbot],
            outputs=[chatbot, msg],
            concurrency_limit=3,
        )
        stop_btn.click(
            fn=handle_stop,
            outputs=[status],
        )

        clear_btn.click(
            fn=client.clear_chat_history,
            inputs=[chatbot],
            outputs=[chatbot],
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
