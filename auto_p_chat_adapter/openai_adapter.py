from typing import AsyncGenerator

from openai import AsyncOpenAI, AsyncStream
from openai.types.responses import ResponseStreamEvent

from auto_p_utils.logger_util import logger


class OpenAIAdapter:
    def __init__(
            self,
            openai_api_key: str,
            openai_api_base_url: str,
            openai_api_model: str
    ) -> None:
        self.openai_api_key = openai_api_key
        self.openai_api_base_url = openai_api_base_url
        self.openai_api_model = openai_api_model

        logger.info(f"OpenAI API Key: {openai_api_key}")
        logger.info(f"OpenAI API Base URL: {openai_api_base_url}")
        logger.info(f"OpenAI API Model: {openai_api_model}")

        self.openai = AsyncOpenAI(
            api_key=openai_api_key,
            base_url=openai_api_base_url,
        )

        logger.info(f"chat object created...")

    async def _build_stream(
            self,
            messages: list,
            tools: list = None
    ) -> AsyncStream[ResponseStreamEvent]:
        """构建stream对象"""
        return await self.openai.responses.create(
            model=self.openai_api_model,
            input=messages,
            temperature=0.95,
            stream=True,
            extra_body={
                "thinking": {
                    "type": "disabled"  # 不使用深度思考能力
                }
            },
            tools=tools
        )

    async def chat(
            self,
            messages: list,
            tools: list = None
    ) -> AsyncGenerator:
        """对话"""
        stream = await self._build_stream(messages, tools)

        async for event in stream:
            yield event
