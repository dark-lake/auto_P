"""auto_p 统一配置模块。

所有硬编码的配置项集中在此，通过环境变量读取，提供合理的默认值。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    """应用级配置，从环境变量读取。"""

    # -- 对话模型 --
    chat_api_key: str = field(default_factory=lambda: os.getenv("CHAT_API_KEY", ""))
    chat_model: str = field(default_factory=lambda: os.getenv("CHAT_OPEN_MODEL", "doubao-seed-1-6-flash-250828"))
    chat_base_url: str = field(
        default_factory=lambda: os.getenv("CHAT_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"))
    chat_timeout: int = field(default_factory=lambda: int(os.getenv("CHAT_TIMEOUT", "120")))
    chat_max_retries: int = field(default_factory=lambda: int(os.getenv("CHAT_MAX_RETRIES", "2")))

    # -- 视觉模型 --
    vis_api_key: str = field(default_factory=lambda: os.getenv("VIS_API_KEY", ""))
    vis_model: str = field(default_factory=lambda: os.getenv("VIS_OPEN_MODEL", "doubao-seed-2-0-mini-260428"))
    vis_base_url: str = field(
        default_factory=lambda: os.getenv("VIS_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"))

    # -- 向量模型 --
    embedding_api_key: str = field(default_factory=lambda: os.getenv("EMBEDDING_API_KEY", ""))
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_OPEN_MODEL", "doubao-embedding-vision-250615"))
    embedding_base_url: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3/embeddings"))

    # -- 路径 --
    base_path: Path = field(default_factory=lambda: Path(os.getenv("BASE_PATH", str(Path.cwd()))))
    persist_path: Path = field(
        default_factory=lambda: Path(os.getenv("PERSIST_PATH", str(Path.cwd() / "auto_p_vector" / "tool_search_db"))))
    img_path: Path = field(default_factory=lambda: Path(os.getenv("IMG_PATH", str(Path.cwd() / "img"))))
    log_path: Path = field(default_factory=lambda: Path(os.getenv("LOG_PATH", str(Path.cwd() / "logs"))))
    stream_log_path: Path = field(
        default_factory=lambda: Path(os.getenv("STREAM_LOG_PATH", str(Path.cwd() / "stream_log"))))
    a11y_txt_path: Path = field(default_factory=lambda: Path(os.getenv("A11Y_TXT_PATH", str(Path.cwd() / "a11y_txt"))))
    avatar_path: Path = field(default_factory=lambda: Path(os.getenv("AVATAR_PATH", str(Path.cwd() / "avatar"))))

    # -- MCP 服务 --
    official_service_names: str = field(default_factory=lambda: os.getenv("OFFICIAL_SERVICE_NAMES", "auto_p-tools"))

    # -- 工具搜索 --
    enable_tool_search: bool = field(default_factory=lambda: os.getenv("ENABLE_TOOL_SEARCH", "true").lower() == "true")
    tool_search_k: int = field(default_factory=lambda: int(os.getenv("TOOL_SEARCH_K", "4")))
    collection_name: str = field(default_factory=lambda: os.getenv("CHROMA_COLLECTION", "mcp_tools"))

    # -- 对话历史 --
    history_trim_threshold: int = field(default_factory=lambda: int(os.getenv("HISTORY_TRIM_THRESHOLD", "5")))
    screenshot_truncate_length: int = field(default_factory=lambda: int(os.getenv("SCREENSHOT_TRUNCATE_LENGTH", "512")))

    # -- LLM 参数 --
    llm_temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.7")))
    llm_top_p: float = field(default_factory=lambda: float(os.getenv("LLM_TOP_P", "1.0")))
    # 推理模式: auto(模型自决) | enabled(强制推理) | disabled(关闭推理)
    thinking_type: str = field(default_factory=lambda: os.getenv("THINKING_TYPE", "auto"))

    # -- 视觉模型参数 --
    vis_top_p: float = field(default_factory=lambda: float(os.getenv("VIS_TOP_P", "0.3")))

    # -- 会话存储 (MySQL) --
    mysql_host: str = field(default_factory=lambda: os.getenv("MYSQL_HOST", "127.0.0.1"))
    mysql_port: int = field(default_factory=lambda: int(os.getenv("MYSQL_PORT", "3306")))
    mysql_user: str = field(default_factory=lambda: os.getenv("MYSQL_USER", "root"))
    mysql_password: str = field(default_factory=lambda: os.getenv("MYSQL_PASSWORD", ""))
    mysql_db: str = field(default_factory=lambda: os.getenv("MYSQL_DB", "auto_p"))
    session_auto_title: bool = field(default_factory=lambda: os.getenv("SESSION_AUTO_TITLE", "true").lower() == "true")

    # -- 浏览器 --
    chrome_path: str = field(default_factory=lambda: os.getenv("CHROME_PATH", ""))
    user_data_dir: str = field(default_factory=lambda: os.getenv("USER_DATA_DIR", ""))

    @property
    def chat_model_for_api(self) -> str:
        """返回用于 API 调用的模型全名。"""
        return self.chat_model

    @property
    def vis_model_for_api(self) -> str:
        return self.vis_model

    @property
    def embedding_model_for_api(self) -> str:
        return self.embedding_model


# 全局单例
config = AppConfig()
