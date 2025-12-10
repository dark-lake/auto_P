import asyncio
import os

from dotenv import load_dotenv
from volcenginesdkarkruntime import AsyncArk

load_dotenv()

client = AsyncArk(
    # 从环境变量中获取您的 API Key。此为默认方式，您可根据需要进行修改
    api_key=os.getenv("EMBEDDING_API_KEY"),
)


async def embedding(text: str) -> list[float]:
    resp = await client.multimodal_embeddings.create(
        model="doubao-embedding-vision-250615",
        input=[
            {
                "type": "text",
                "text": text
            },
        ]
    )
    # 返回的是list[float]
    return resp.data.embedding


if __name__ == '__main__':
    asyncio.run(embedding("测试工具,通常用于测试"))
