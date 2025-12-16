import asyncio
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

tools = [
    {
        "type": "function",
        "name": "search_docs",
        "description": "在本地或远程文档库中搜索相关内容",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或问题"
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "type": "function",
        "name": "run_browser_task",
        "description": "执行一次浏览器自动化任务，例如打开页面、点击或抓取信息",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "目标网页 URL"
                },
                "actions": {
                    "type": "array",
                    "description": "需要执行的浏览器动作列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["click", "input", "wait", "scroll"],
                                "description": "动作类型"
                            },
                            "selector": {
                                "type": "string",
                                "description": "页面元素选择器"
                            },
                            "value": {
                                "type": "string",
                                "description": "输入值或附加参数"
                            }
                        },
                        "required": ["type"]
                    }
                }
            },
            "required": ["url", "actions"]
        }
    },
    {
        "type": "function",
        "name": "llm_summarize",
        "description": "对给定文本进行总结或提炼关键信息",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "需要总结的原始文本"
                },
                "style": {
                    "type": "string",
                    "description": "总结风格",
                    "enum": ["brief", "bullet", "detailed"],
                    "default": "brief"
                }
            },
            "required": ["text"]
        }
    }
]


async def chat(message: str):
    client = AsyncOpenAI(
        api_key=os.getenv('CHAT_API_KEY'),
        base_url=os.getenv('CHAT_BASE_URL'),
    )
    stream = await client.responses.create(
        model=os.getenv("CHAT_OPEN_MODEL"),
        input=[{"role": "user", "content": message}],
        temperature=0.6,
        top_p=0.95,
        stream=True,
        stream_options={
            "include_usage": True,
            "chunk_include_usage": True,
        },
        extra_body={
            "thinking": {
                "type": "disabled"  # 不使用深度思考能力
                # "type": "enabled" # 使用深度思考能力
            }
        },
        tools=tools
    )

    tool_calls = {}
    arg_buffers = {}

    async for event in stream:
        if event.type == "response.output_text.delta":
            handle_text(event.delta)

        elif event.type == "response.output_item.added":
            if event.item.type == "function_call":
                tool_calls[event.item.id] = event.item
                arg_buffers[event.item.id] = ""

        elif event.type == "response.function_call_arguments.delta":
            arg_buffers[event.item_id] += event.delta

        elif event.type == "response.function_call_arguments.done":
            args = json.loads(event.arguments)
            dispatch_tool(event.item_id, args)

        elif event.type == "response.completed":
            finalize()
        # if event.type == "response.output_text.delta":
        #     print(event.delta, end="", flush=True)
        #
        # elif event.type == "response.completed":
        #     print("\n--- done ---")


asyncio.run(chat("请总结一下 '今天天气非常好,你开心吗' 这句话"))
