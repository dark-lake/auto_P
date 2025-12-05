from typing import Literal

from pydantic import BaseModel

from auto_p_utils.logger_util import logger


class McpServiceManager:
    TRANSPORTS = ["stdio", "sse", "streamable-http"]

    def __init__(self, mcp_config: dict):
        self.mcp_services_list = []
        self.register_mcp_service(mcp_config)

    class McpService(BaseModel):
        name: str
        transport: Literal["stdio", "sse", "streamable-http"]
        command: Literal["python", "node"]
        args: list[str]

        # @field_validator('transport')
        # @classmethod
        # def validate_transport(cls, v: str) -> str:
        #     if v not in McpServiceManager.TRANSPORTS:
        #         raise ValueError(f"MCP TRANSPORT 类型错误, 目前支持类型为{McpServiceManager.TRANSPORTS}")
        #     return v

    def get_mcp_services(self) -> list[McpService] | None:
        return self.mcp_services_list

    def register_mcp_service(self, mcp_service_config: dict) -> None:
        logger.info("开始解析MCP配置")
        for service_name, service_config in mcp_service_config.items():
            service = McpServiceManager.McpService(
                name=service_name,
                transport=service_config["transport"],
                command=service_config["command"],
                args=service_config["args"]
            )
            self.mcp_services_list.append(service)
            logger.info(f"成功解析服务: {service_name}")
        logger.info("MCP配置解析完成")
