import asyncio
import json
import re
from contextlib import AsyncExitStack
from typing import Optional
 
from lxml import etree
from mcp import ClientSession, StdioServerParameters, stdio_client
from mcp.client.sse import sse_client
from openai import AsyncOpenAI
 
class Stdio_MCPClient():
 
    def __init__(self,api_key, base_url, model):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.message = []
        with open("MCP_Prompt.txt", "r", encoding="utf-8") as f:
            self.system_prompt = f.read()
 
    async def connect_to_stdio_server(self, mcp_name, command, args, env=None):
        if env is None:
            env = {}
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio,self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()
        response = await self.session.list_tools()
        tools = response.tools
        print(f"成功链接到{mcp_name}服务，对应的tools：",[tool.name for tool in tools])
        self.available_tools = [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        } for tool in response.tools]
 
    async def process_query(self, query: str, stream: bool = False):
        # self.message.append({"role": "system", "content": self.system_prompt})
        self.message.append({"role": "user", "content": query})
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=self.message,
            tools=self.available_tools
        )
        final_text = []
        assistant_message = response.choices[0].message
        while assistant_message.tool_calls:
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
 
                result = await self.session.call_tool(tool_name, tool_args)
                print(f"calling tools {tool_name},wirh args {tool_args}")
                print("Result:", result.content[0].text)
                self.message.extend([
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call]
                    },
                    {
                        "role": "tool",
                        "content": result.content[0].text,
                        "tool_call_id": tool_call.id
                    }
                ])
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self.message,
                tools=self.available_tools,
                max_tokens=8048
 
            )
            assistant_message = response.choices[0].message
        content = assistant_message.content
        final_text.append(content)
 
        return "\n".join(final_text)
 
    async def chat_loop(self,stream_mode=True):
        self.message = []
        while True:
            try:
                query = input("\nQuery: ").strip()
                if query.lower() == 'quit':
                    break
                if query.strip() == '':
                    continue
                response = await self.process_query(query, stream=stream_mode)
                print("\nAI:", response)
            except Exception as e:
                print(f"\nError: {str(e)}")
 
    async def cleanup(self):
        await self.exit_stack.aclose()
 
async def main():
    with open("config.json", "r") as f:
        config = json.load(f)
    client = Stdio_MCPClient(config["llm"]["api_key"], config["llm"]["base_url"], config["llm"]["model"])
    try:
        env = {}
        await client.connect_to_stdio_server("testserver","python",["mcp_server.py",],{})
        await client.chat_loop()
    except  Exception as e:
        print(e)
    finally:
        await client.cleanup()
 
if __name__ == '__main__':
    asyncio.run(main())