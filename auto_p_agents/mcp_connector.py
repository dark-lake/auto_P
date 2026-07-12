"""MCP 连接管理器 — 负责所有 MCP 服务的连接和生命周期管理。"""

from __future__ import annotations

import os
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from auto_p_utils.logger_util import logger

if TYPE_CHECKING:
    from auto_p_services.McpServiceManager import McpServiceManager


class MCPConnector:
    """管理 MCP 服务的连接、工具注册和生命周期。"""

    def __init__(self):
        self.servers: dict[str, ClientSession] = {}
        self.service_configs: dict[str, "McpServiceManager.McpService"] = {}
        self.tool_service_map: dict[str, str] = {}
        self.all_tools: list = []
        self.exit_stack = AsyncExitStack()

    async def connect(self, mcp_service: "McpServiceManager.McpService") -> list[str]:
        """连接一个 MCP 服务并注册其工具。

        Returns:
            新注册的工具名称列表
        """
        if not mcp_service.args:
            raise ValueError("服务脚本必须指定其绝对路径")
        is_python = mcp_service.args[0].endswith(".py")
        is_js = mcp_service.args[0].endswith(".js")
        if not (is_python or is_js):
            raise ValueError("服务脚本必须是 python 或 js 文件")

        server_params = StdioServerParameters(
            command=mcp_service.command,
            args=(mcp_service.args or []),
            env={"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
        )

        if mcp_service.transport != "stdio":
            raise ValueError(f"不支持的 transport: {mcp_service.transport}")

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport
        session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))

        await session.initialize()
        list_tools_result = await session.list_tools()
        tools = list_tools_result.tools

        self.servers[mcp_service.name] = session
        self.service_configs[mcp_service.name] = mcp_service

        new_tool_names = []
        for tool in tools:
            self.tool_service_map[tool.name] = mcp_service.name
            self.all_tools.append(tool)
            new_tool_names.append(tool.name)

        logger.info(
            f"{mcp_service.name} 服务中工具列表(共{len(tools)}个): "
            f"{[t.name for t in tools]}"
        )
        return new_tool_names

    def get_session(self, server_name: str) -> ClientSession | None:
        return self.servers.get(server_name)

    def get_server_name_for_tool(self, tool_name: str) -> str:
        return self.tool_service_map.get(tool_name, "")

    def get_non_official_tools(self) -> list:
        """获取非官方服务的工具列表。"""
        official_name = os.getenv("OFFICIAL_SERVICE_NAMES")
        result = []
        # 从 sessions 获取完整 tool 对象
        for name, session in self.servers.items():
            if name == official_name:
                continue
            # 这里无法同步获取，调用方需要自己处理
        return result

    async def get_non_official_tools_async(self) -> list:
        """异步获取非官方服务的完整工具列表。"""
        official_name = os.getenv("OFFICIAL_SERVICE_NAMES")
        all_tools = []
        for name, session in self.servers.items():
            if name == official_name:
                continue
            result = await session.list_tools()
            all_tools.extend(result.tools)
        return all_tools

    async def cleanup(self):
        await self.exit_stack.aclose()
