from typing import Literal, Optional, Dict

from pydantic import BaseModel, Field, field_validator

from auto_p_utils.logger_util import logger


class McpServiceManager:
    TRANSPORTS = ["stdio", "sse", "streamable-http"]

    def __init__(self, mcp_config: dict):
        self.mcp_services_list = []
        self.register_mcp_service(mcp_config)

    class McpService(BaseModel):
        name: str = Field(..., min_length=1)
        description: str = Field(..., min_length=1)
        transport: Literal["stdio", "sse", "streamable-http"] = Field(...)
        command: str = Field(...)
        args: list[str] = Field(..., min_items=1)
        env: Optional[Dict[str, str]] = Field(default=None)

        @field_validator('command')
        def validate_command(cls, v):
            """验证command，支持node或者以'python'结尾的python命令"""
            # 支持node命令
            if v == "node":
                return v
            # 验证python命令以'python'结尾
            if not v.endswith('python'):
                raise ValueError('command必须是"node"或者以"python"结尾的python路径')
            return v

        model_config = {
            'validate_assignment': True
        }

    def get_mcp_services(self) -> list[McpService] | None:
        return self.mcp_services_list

    def register_mcp_service(self, mcp_service_config: dict) -> None:
        logger.info("开始解析MCP配置")
        for service_name, service_config in mcp_service_config.items():
            service = McpServiceManager.McpService(
                name=service_name,
                description=service_config["description"],
                transport=service_config["transport"],
                command=service_config["command"],
                args=service_config["args"],
                env=service_config.get("env")
            )
            self.mcp_services_list.append(service)
            logger.info(f"成功解析服务: {service_name}")
        logger.info("MCP配置解析完成")