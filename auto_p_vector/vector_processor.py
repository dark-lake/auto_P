import asyncio
import json
import os
from typing import List

import chromadb
from dotenv import load_dotenv
from mcp import Tool

import auto_p_vector.embedding_service.HuoShan_embedding as HuoShan_embedding
from auto_p_utils.logger_util import logger

load_dotenv()


class ToolSearcher:
    def __init__(self, tools: list[Tool], persist_path="./tool_search_db"):
        """
        tools: List[Tool]
            Tool 必须包含 name/description/params 或等价字段
        persist_path: str
            Chroma 本地向量库持久化路径
        """

        self.tools: list[Tool] = tools
        self.persist_path = os.getenv("PERSIST_PATH") if os.getenv("PERSIST_PATH") else persist_path

        # 确保持久化路径存在
        if not os.path.exists(self.persist_path):
            os.makedirs(self.persist_path)
            logger.info(f"创建持久化目录: {self.persist_path}")

        # 创建/加载本地 Chroma 实例(持久化)
        self.chroma_client = chromadb.PersistentClient(path=self.persist_path)

        # 创建或加载集合
        self.collection = self.chroma_client.get_or_create_collection(
            name="mcp_tools",
            metadata={"hnsw:space": "cosine"},  # 余弦相似度
        )

    # 同步工具:检测新增、修改、删除
    async def sync_tools(self):
        # 获取数据库中现有的所有工具
        existing_data = self.collection.get()
        existing_ids = set(existing_data["ids"]) if existing_data["ids"] else set()
        existing_metadatas = {id: meta for id, meta in zip(existing_data["ids"], existing_data["metadatas"])} if \
            existing_data["ids"] else {}

        # 当前传入的工具
        current_ids = {t.name for t in self.tools}
        current_tools_map = {t.name: t for t in self.tools}

        # 1. 检测需要删除的工具(在数据库中但不在当前工具列表中)
        to_delete = existing_ids - current_ids
        if to_delete:
            self.collection.delete(ids=list(to_delete))
            logger.info(f"删除了 {len(to_delete)} 个工具: {to_delete}")

        # 2. 检测需要新增的工具(在当前工具列表中但不在数据库中)
        to_add = current_ids - existing_ids

        # 3. 检测需要更新的工具(在两者中都存在,但内容有变化)
        to_update = set()
        for tool_name in current_ids & existing_ids:
            tool = current_tools_map[tool_name]
            old_meta = existing_metadatas[tool_name]

            # 比较描述和参数是否有变化
            if (old_meta.get("description") != tool.description or
                    old_meta.get("params") != json.dumps(tool.inputSchema, ensure_ascii=False)):
                to_update.add(tool_name)

        # 处理新增的工具
        if to_add:
            add_ids = []
            add_embeddings = []
            add_metadatas = []

            for tool_name in to_add:
                tool = current_tools_map[tool_name]
                text = self._make_tool_text(tool)
                vec = await self.embed(text)

                add_ids.append(tool.name)
                add_embeddings.append(vec)
                add_metadatas.append({
                    "name": tool.name,
                    "description": tool.description,
                    "params": json.dumps(tool.inputSchema, ensure_ascii=False)
                })

            self.collection.add(
                ids=add_ids,
                embeddings=add_embeddings,
                metadatas=add_metadatas,
            )
            logger.info(f"新增了 {len(to_add)} 个工具: {to_add}")

        # 处理需要更新的工具
        if to_update:
            # ChromaDB 的更新策略:先删除再添加
            self.collection.delete(ids=list(to_update))

            update_ids = []
            update_embeddings = []
            update_metadatas = []

            for tool_name in to_update:
                tool = current_tools_map[tool_name]
                text = self._make_tool_text(tool)
                vec = await self.embed(text)

                update_ids.append(tool.name)
                update_embeddings.append(vec)
                update_metadatas.append({
                    "name": tool.name,
                    "description": tool.description,
                    "params": json.dumps(tool.inputSchema, ensure_ascii=False)
                })

            self.collection.add(
                ids=update_ids,
                embeddings=update_embeddings,
                metadatas=update_metadatas,
            )
            logger.info(f"更新了 {len(to_update)} 个工具: {to_update}")

        # 如果没有任何变化
        if not to_add and not to_update and not to_delete:
            logger.info("工具库无变化,跳过同步")

    # 构造工具描述文本
    def _make_tool_text(self, tool: Tool):
        return (
            f"工具名称: {tool.name}\n"
            f"工具描述: {tool.description}\n"
            f"工具入参: {json.dumps(tool.inputSchema, ensure_ascii=False)}"
        )

    # 生成 embedding
    async def embed(self, text: str) -> List[float]:
        if not text:
            raise ValueError("向量化的文本不能为空")
        vec = await self.do_embed(text)
        logger.info(f'使用{os.getenv("EMBEDDING_OPEN_MODEL")}模型向量化文本:{text},结果为: {len(vec)}')
        return vec

    async def do_embed(self, text: str) -> List[float]:
        if os.getenv("EMBEDDING_PLATFORM") == "火山引擎":
            vect = await HuoShan_embedding.embedding(text)
            return vect

        # 使用默认embedding服务
        return await HuoShan_embedding.embedding(text)

    # 搜索工具
    async def search(self, query: str, k: int = 3) -> list[Tool]:
        # 同步调用 embed,使用 asyncio.run
        q_vec = await self.embed(query)

        results = self.collection.query(
            query_embeddings=[q_vec],
            n_results=k,
        )

        ids = results["ids"][0]  # 第一条 query 的结果

        # 根据 id 返回 Tool 对象
        return [self._find_tool_by_name(tid) for tid in ids]

    # 从原始 tool 列表中查找对象
    def _find_tool_by_name(self, name) -> Tool | None:
        for t in self.tools:
            if t.name == name:
                return t
        return None


async def test():
    a = ToolSearcher([
        Tool(
            name="test",
            description="测试工具,通常用于测试,新增修改",
            inputSchema={
                "a": {
                    "type": "string",
                    "description": "b"
                }
            }
        )
    ])

    print(a.search("测试工具,通常用于测试"))


if __name__ == '__main__':
    asyncio.run(test())
