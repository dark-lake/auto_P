import asyncio
import json
import os
from contextlib import AsyncExitStack

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult
from openai import AsyncOpenAI
from openai.types.beta.threads.runs import ToolCall

from auto_p_services.McpServiceManager import McpServiceManager
from auto_p_utils.logger_util import logger
from auto_p_utils.os_util import convert_tool

load_dotenv()  # load environment variables from .env


class AutoProcessAgent:
    def __init__(self):
        self.servers = {}  # 存所有 server session server_name -> server_session
        self.tools = {}  # tool_name → server_name 映射
        self.exit_stack = AsyncExitStack()
        self.openai = AsyncOpenAI(
            api_key=os.getenv("CHAT_API_KEY"),
            base_url=os.getenv("CHAT_BASE_URL"),
            timeout=120,
        )

    async def connect_to_server(self, mcp_service: McpServiceManager.McpService):
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

        server_params = StdioServerParameters(
            command=mcp_service.command,
            args=(mcp_service.args or []),
            env=None
        )
        if mcp_service.transport == 'stdio':
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))

            await session.initialize()
            response = await session.list_tools()
            tools = response.tools
            # 保存mcp服务
            self.servers[mcp_service.name] = session
            # 保存每个工具与其服务名的映射
            for tool in tools:
                self.tools[tool.name] = mcp_service.name
            logger.info(f"{mcp_service.name}服务中工具列表(共{len(tools)}个)为:{[tool.name for tool in tools]}")

    async def process_query(self, query: str) -> str:
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        # 构建工具schema
        tools = await self.build_tools_schema()

        while True:
            msg_len = len(messages)
            response = await self.openai.chat.completions.create(
                model=os.getenv("CHAT_OPEN_MODEL"),
                messages=messages,
                extra_body={
                    "thinking": {
                        "type": "disabled"  # 不使用深度思考能力
                        # "type": "enabled" # 使用深度思考能力
                    }
                },
                tools=tools
            )

            final_text = []
            message = response.choices[0].message
            if len(message.content) > 0:
                final_text.append(message.content)

            if hasattr(message, "tool_calls") and message.tool_calls:
                print('-' * 20)
                for i in message.tool_calls:
                    print(f'\tID:{i.id}\n\tFUNCTION:{i.function}')
                print('-' * 20)

                # 将工具输出追加到 messages，让模型知道工具结果
                if hasattr(message, 'reasoning_content') and message.reasoning_content:
                    msg = message.model_dump()
                    msg.pop("reasoning_content", None)  # 移除大模型思考的部分
                    messages.append(msg)
                else:
                    # 不是深度思考的,直接将调用工具的assistant追加到messages
                    messages.append(message.model_dump())

                for tool_call in message.tool_calls:
                    tool_call_id = tool_call.id
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")
                    # 执行工具
                    result = await self.execute_tool(tool_call)
                    print(f'result: {result}')
                    # tool_output = result.structuredContent if result.structuredContent else result.content
                    final_text.append(f"[Tool {tool_name} result: {result}]")

                    # 对于图片类型,message需要特殊处理一下
                    # if tool_output and tool_output.get('result', False) and tool_output.get('result').startswith(''):
                    #     messages.append({
                    #         "role": "tool",
                    #         "name": tool_name,
                    #         "content": [
                    #             {
                    #                 "type": "image_url",
                    #                 "image_url": {
                    #                     "url": tool_output.get('result', )
                    #                 }
                    #             }
                    #         ],
                    #         "tool_call_id": tool_call_id
                    #     })
                    # else:
                    #     messages.append({
                    #         "role": "tool",
                    #         "name": tool_name,
                    #         "content": str(tool_output.get('result', 'No result')),
                    #         "tool_call_id": tool_call_id
                    #     })
                    output = result.content[0] if result.content else result.structuredContent
                    if hasattr(output, 'model_dump'):
                        output = output.model_dump()
                    messages.append({
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(output),
                        "tool_call_id": tool_call_id
                    })

                for msg in messages[msg_len:]:
                    # if msg.get("name") != "get_page_snapshot":
                    #     logger.info(f'Message: {msg}')
                    # else:
                    #     copy_msg = deepcopy(msg)
                    #     img_data = copy_msg.get('content')
                    #     if isinstance(img_data, list):
                    #         img_data[0]['image_url'][
                    #             'url'] = f'图片base64长度为:{str(len(img_data[0]['image_url'].get('url', '')))}'
                    #         logger.info(f'Message: {copy_msg}')
                    #     else:
                    #         logger.info(f'Message: {msg}')
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

    async def execute_tool(self, tool_call: ToolCall) -> CallToolResult:
        """
        实际执行tool的方法
        :return: 方法执行的结果
        """
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)

        server_name = self.tools.get(tool_name, '')
        server: ClientSession = self.servers.get(server_name, None)
        if server is None:
            return CallToolResult(
                content=[],
                structuredContent={
                    "result": f'未找到{tool_name}工具',
                }
            )
        logger.info(f"正在执行 {server_name} 服务的 {tool_name} 工具")
        if tool_name == 'pause_and_wait':
            pause_reason = tool_args.get('pause_reason', None)
            print("模型要求暂停 → 等待你的操作")
            print(f"暂停原因:{pause_reason}")
            if tool_args.get('input_required', False):
                # 这里暂停，让你操作
                loop = asyncio.get_event_loop()
                user_input = await loop.run_in_executor(None, input, "请输入你的操作指令后继续:")

                return CallToolResult(
                    content=[],
                    structuredContent={
                        "type": "pause",
                        "reason": pause_reason,
                        "result": user_input if isinstance(user_input, str) else "no input",
                    }
                )
        try:
            return await server.call_tool(tool_name, tool_args)
        except Exception as e:
            return CallToolResult(
                content=[],
                structuredContent={"result": str(e)}
            )

    async def build_tools_schema(self) -> list[dict]:
        tools = []
        # server为ClientSession对象
        for server in self.servers.values():
            # 这里拿到的resp中
            resp = await server.list_tools()
            tools.extend(dict(resp).get("tools", []))
        logger.info(f"可用工具: {len(tools)}")
        available_tools = [convert_tool(tool) for tool in tools]
        return available_tools

    async def chat_loop(self):
        print("\nAutoPAgent Started!")
        print("提问或输入quit退出!")

        while True:
            try:
                query = input("\n提问: ").strip()

                if query.lower() == 'quit':
                    break

                response = await self.process_query(query)
                print("\n" + response)
            except Exception as e:
                raise e

    async def cleanup(self):
        await self.exit_stack.aclose()
