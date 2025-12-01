import asyncio
import json
import os
from contextlib import AsyncExitStack
from copy import deepcopy
from typing import Optional

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

from utils.logger_util import logger

load_dotenv()  # load environment variables from .env


async def reduce_messages(messages: list[dict], max_length: int = 4) -> list[dict]:
    """
    保持messages的长度始终小于等于max_length
    :param messages: 对话列表
    :param max_length: 限定的最长上下文
    :return: 优化后的messages
    """
    if len(messages) <= max_length:
        return messages

    new_messages = []
    # 超过max_length, 则删除最老几条的tool
    first_msg = messages[0]
    new_messages.append(first_msg)
    new_messages.extend(messages[len(messages) - max_length + 1:])
    return new_messages


class Agent:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.openai = OpenAI()

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """

        assert logger is not None, "Logger not initialized"

        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        """Process a query using LLM and available tools"""
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]
        # Initial LLM API call

        tools = await self.build_tools_schema()

        while True:
            msg_len = len(messages)
            response = self.openai.chat.completions.create(
                model=os.getenv("OPENAI_MODEL"),
                messages=messages,
                extra_body={
                    "thinking": {
                        "type": "disabled"  # 不使用深度思考能力
                        # "type": "enabled" # 使用深度思考能力
                    }
                },
                tools=tools
            )
            # Process response and handle tool calls
            final_text = []
            message = response.choices[0].message
            logger.info(f'Message: {response}')
            if len(message.content) > 0:
                final_text.append(message.content)

            if hasattr(message, "tool_calls") and message.tool_calls:
                print('-' * 20)
                for i in message.tool_calls:
                    print(f'\tID:{i.id}\n\tFUNCTION:{i.function}')
                print('-' * 20)

                # 将工具输出追加到 messages，让模型知道工具结果
                if hasattr(message, 'reasoning_content') and message.reasoning_content:
                    messages.append({
                        "role": "assistant",
                        "content": message.reasoning_content
                    })

                for tool_call in message.tool_calls:
                    tool_call_id = tool_call.id
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")
                    # 执行工具
                    result = await self.session.call_tool(tool_name, tool_args)
                    tool_output = result.structuredContent
                    final_text.append(f"[Tool {tool_name} result: {tool_output}]")

                    # 对于图片类型,message需要特殊处理一下
                    if tool_output and tool_output.get('result').startswith('data:image/'):
                        messages.append({
                            "role": "tool",
                            "name": tool_name,
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": tool_output.get('result')
                                    }
                                }
                            ],
                            "tool_call_id": tool_call_id
                        })
                    else:
                        messages.append({
                            "role": "tool",
                            "name": tool_name,
                            "content": str(tool_output.get('result', 'No result')),
                            "tool_call_id": tool_call_id
                        })

                for msg in messages[msg_len:]:
                    if msg.get("name") != "get_page_snapshot":
                        logger.info(f'Message: {msg}')
                    else:
                        copy_msg = deepcopy(msg)
                        img_data = copy_msg.get('content')
                        if isinstance(img_data, list):
                            img_data[0]['image_url'][
                                'url'] = f'图片base64长度为:{str(len(img_data[0]['image_url'].get('url', '')))}'
                            logger.info(f'Message: {copy_msg}')
                        else:
                            logger.info(f'Message: {msg}')

                # 减少无用token,当messages的长度达到4轮的时候,就只保留user和其他的tool_result,始终保持在4轮会话
                # messages = await reduce_messages(messages)
                logger.info(f'Messages轮数: {str(len(messages))}')
                # 继续下一轮 LLM 推理
                continue
            else:
                # 没有 tool_calls，结束循环
                break

        return "\n".join(final_text)

    async def build_tools_schema(self) -> list[dict]:
        response = await self.session.list_tools()
        available_tools = [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": tool.inputSchema['type'],
                    "properties": {
                        k: {
                            "type": v['type'],
                            "description": v['title']
                        } for k, v in tool.inputSchema['properties'].items()
                    },
                    "required": tool.inputSchema.get('required', [])
                }
            }
        } for tool in response.tools]
        return available_tools

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMac Agent Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    # 关闭日志
                    await logger.complete()
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
    client = Agent()
    try:
        print("Connecting to server: ", "browser_tools.py")
        await client.connect_to_server("browser_tools.py")
        print("Connected to server!")
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    import sys

    print(sys.path)
    asyncio.run(main())
