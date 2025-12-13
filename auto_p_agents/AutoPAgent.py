import json
import os
from contextlib import AsyncExitStack

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, Tool
from openai import AsyncOpenAI
from openai.types.beta.threads.runs import ToolCall

from auto_p_prompts.prompts import auto_p_prompts as auto_p_prompts
from auto_p_prompts.prompts_manager import PromptsManager
from auto_p_services.McpServiceManager import McpServiceManager
from auto_p_services.auto_p import auto_p_tools
from auto_p_utils.logger_util import logger
from auto_p_utils.os_util import convert_tool
from auto_p_vector.vector_processor import ToolSearcher

load_dotenv()  # load environment variables from .env


class AutoProcessAgent:
    def __init__(self):
        self.servers = {}  # 存所有 server session server_name -> server_session
        self.servers_McpService: dict[str, McpServiceManager.McpService] = {}  # mcp服务列表 server_name -> McpService
        self.tools = {}  # tool_name → server_name 映射
        self.exit_stack = AsyncExitStack()
        self.prompts_manager = PromptsManager()  # 提示词管理器,负责提示词的构建
        self.tool_searcher: ToolSearcher | None = None
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
        # 将当前服务的McpService对象保存
        self.servers_McpService[mcp_service.name] = mcp_service

    async def init_tool_searcher(self):
        # 构建工具搜索
        if not self.tool_searcher and os.getenv("ENABLE_TOOL_SEARCH", "false") == "true":
            logger.info(f'开始构建工具搜索器...')
            # 构建工具搜索器
            all_tools: list[Tool] = []
            for service_name, session in self.servers.items():
                if 'auto_p-tools' == service_name:
                    continue
                response = await session.list_tools()
                all_tools.extend(response.tools)

            self.tool_searcher = ToolSearcher(all_tools)
            # 增量更新:检测工具的新增、修改、删除
            await self.tool_searcher.sync_tools()

    async def process_query(self, query: str) -> str:
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]
        if os.getenv('ENABLE_TOOL_SEARCH') == 'true':
            # 构建全部工具的schema,只保留name和desc
            tools, lightweight_tools = await self.build_tools_schema_lightweight()
            # 构建工具描述
            mcp_tool_descriptions = [f'- {mcp_service.description}' for mcp_service in self.servers_McpService.values()]
            system_prompt = {
                "role": "system",
                "content": self.prompts_manager.build_prompt(
                    auto_p_prompts.system_prompts_lightweight_V3,
                    mcp_tool_descriptions='\n'.join(mcp_tool_descriptions),
                    lightweight_tools=''.join(json.dumps(lightweight_tools))
                )
            }
            print(f'system_prompt: {system_prompt}')
            messages.insert(0, system_prompt)
        else:
            # 构建全部工具的schema
            tools = await self.build_tools_schema()

        while True:
            msg_len = len(messages)
            response = await self.openai.chat.completions.create(
                model=os.getenv("CHAT_OPEN_MODEL"),
                messages=messages,
                temperature=0.6,
                top_p=0.95,
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
                    # 对工具参数检查,会出现非json的参数
                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except Exception as e:
                        logger.info(f'工具{tool_name}参数解析异常: {e}')
                        messages.append({
                            "role": "tool",
                            "name": tool_name,
                            "content": f'工具{tool_name}参数解析异常: {e}',
                            "tool_call_id": tool_call_id
                        })
                        continue
                    final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")
                    # 执行工具
                    result = await self.execute_tool(tool_call)
                    print(f'result: {result}')
                    final_text.append(f"[Tool {tool_name} result: {result}]")
                    if result.content:
                        output = result.content[0]
                        if hasattr(output, 'model_dump'):
                            output = output.model_dump()
                    else:
                        output = result.structuredContent
                    messages.append({
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(output, ensure_ascii=False),  # 确保写入日志的中文是可读的
                        "tool_call_id": tool_call_id
                    })

                for msg in messages[msg_len:]:
                    logger.info(f'Message: {msg}')

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
        if not server:
            return CallToolResult(
                content=[],
                structuredContent={
                    "result": f'未找到{tool_name}工具',
                }
            )
        logger.info(f"正在执行 {server_name} 服务的 {tool_name} 工具")
        if tool_name == 'wait_for_user_input':
            return await auto_p_tools.do_wait_for_user_input(tool_call)
        elif tool_name == 'get_tool_schema':
            return await auto_p_tools.do_get_tool_schema(self, tool_call)
        elif tool_name == 'tool_search' and os.getenv('ENABLE_TOOL_SEARCH', 'false') == 'true':
            tool_description = tool_args.get('tool_description', None)
            if not tool_description:
                return CallToolResult(
                    content=[],
                    structuredContent={
                        "type": "tool_search",
                        "tool_name": tool_name,
                        "result": '参数tool_description不能为空',
                    }
                )
            # 有可能没找到
            tool_schema = await self.tool_search(tool_description)
            return CallToolResult(
                content=[],
                structuredContent={
                    "type": "tool_search",
                    "tool_name": tool_name,
                    "result": tool_schema if tool_schema else f'未找到该描述对应的工具, 描述:{tool_description}'
                }
            )
        elif server_name == 'chrome-devtools':
            res = await server.call_tool(tool_name, tool_args)
            temp = res.content[0] if res.content else None
            if not temp:
                return res
            if tool_name != 'take_snapshot':
                if temp.type == 'text':
                    temp.text = temp.text.split("\n## Latest page snapshot")[0]
                    logger.info(f'切割快照后结果:{temp.text.replace("\n", " ")}')
                    return res
                return res
            else:
                # take_snapshot
                if temp.type == 'text':
                    print(f'修改前长度:{len(temp.text)}')
                    temp.text = await auto_p_tools.lightweight_ally(temp.text)
                    print(
                        f'修改后长度:{len(temp.text)},缩减了{str(round((len(temp.text) / len(res.content[0].text)) * 100, 2))}%')
                    logger.info(f'已移除所有URL')
                    return res
                return res

        try:
            return await server.call_tool(tool_name, tool_args)
        except Exception as e:
            return CallToolResult(
                content=[],
                structuredContent={"result": str(e)}
            )

    async def get_tool_from_session(self, tool_names: set[str], session: ClientSession = None) -> list[Tool]:
        """获取指定session中的指定Tool"""
        need_tools = []
        if session:
            all_tools = await session.list_tools()
            for tool in all_tools.tools:
                if tool.name in tool_names:
                    need_tools.append(tool)
        else:
            for server in self.servers.values():
                all_tools = await server.list_tools()
                for tool in all_tools.tools:
                    if tool.name in tool_names:
                        need_tools.append(tool)
                        tool_names -= {tool.name}
        return need_tools

    async def build_tools_schema_lightweight(self) -> tuple[list[dict], list[dict]]:
        """
        构造轻量化tools的schema,只保留name和desc
        :return: 工具
        """
        tools = []
        lightweight_tools = []
        # server为ClientSession对象
        for server_name, server in self.servers.items():
            resp = await server.list_tools()
            temp = resp.tools
            if 'auto_p-tools' == server_name:
                # 如果是auto_p-tools的则返回完整的schema
                tools.extend([*temp])
            else:
                for tool in temp:
                    # only_name_desc = Tool(
                    #     name=tool.name,
                    #     description=tool.description,
                    #     inputSchema={}
                    # )
                    lightweight_tool = {
                        "name": tool.name,
                        "description": tool.description
                    }
                    lightweight_tools.append(lightweight_tool)
        logger.info(f"可用工具(已启用工具搜索模式): {len(tools)}")
        logger.info(f"轻量化可用工具(已启用工具搜索模式): {len(lightweight_tools)}")
        available_tools = [convert_tool(tool) for tool in tools]
        return available_tools, lightweight_tools

    async def build_tools_schema(self, tool_name: str = None) -> list[dict]:
        # 当指定要调用的工具时,只返回该工具的schema
        if tool_name:
            server = self.servers.get(tool_name, None)
            if server is None:
                return []
            resp = await server.list_tools()
            tools = [dict(resp).get("tools", [])]
            return [convert_tool(tool) for tool in tools if tool.name == tool_name]
        else:
            tools = []
            # server为ClientSession对象
            for server in self.servers.values():
                # 这里拿到的resp中
                resp = await server.list_tools()
                tools.extend(dict(resp).get("tools", []))
            logger.info(f"可用工具(未启用工具搜索模式): {len(tools)}")
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
                print(e)

    async def cleanup(self):
        await self.exit_stack.aclose()

    async def tool_search(self, tool_desc: str = None) -> list[dict]:
        """
        实际的搜索工具方法, 通过向量匹配的方式
        :param tool_desc: 工具描述
        :return: 工具的schema
        """
        if not self.tool_searcher:
            return []
        # 小于等于3个匹配到的工具对象
        tools = await self.tool_searcher.search(
            query=tool_desc,
            k=3
        )
        logger.info(f'搜索到如下工具: {[t.name for t in tools]}')
        return [convert_tool(tool) for tool in tools]
