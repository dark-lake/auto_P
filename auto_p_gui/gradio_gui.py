import os

import gradio as gr
from dotenv import load_dotenv

from auto_p_agents.AutoPAgent import AutoProcessAgent

load_dotenv()

client = AutoProcessAgent()


def gradio_interface():
    with gr.Blocks(title="Auto_P 助手") as demo:
        gr.Markdown("# AUTO_P 自动化助手")
        gr.Markdown("连接到你的MCP服务并开始对话")

        with gr.Row(equal_height=True):
            with gr.Column(scale=4):
                # server_path = gr.Textbox(
                #     label="MCP 服务脚本路径",
                #     placeholder="",
                #     value=""
                # )
                status = gr.Textbox(label="服务连接状态", interactive=False)
            with gr.Column(scale=1):
                connect_btn = gr.Button("连接")

        chatbot = gr.Chatbot(
            value=[],
            height=500,
            # show_copy_button=True,
            avatar_images=(
                os.path.join(os.getenv("AVATAR_PATH"), "user.png"),
                os.path.join(os.getenv("AVATAR_PATH"), "robot.png"),
            )
        )

        with gr.Row(equal_height=True):
            msg = gr.Textbox(
                label="你的任务",
                placeholder="请下达任务...",
                scale=4
            )
            clear_btn = gr.Button("清空聊天记录", scale=1)

        connect_btn.click(client.connect_by_config, outputs=[status])
        msg.submit(client.process_message, [msg, chatbot], [chatbot, msg])
        clear_btn.click(client.clear_chat_history, chatbot, chatbot)

    return demo


if __name__ == "__main__":
    interface = gradio_interface()
    interface.launch(debug=True, theme=gr.themes.Soft())
