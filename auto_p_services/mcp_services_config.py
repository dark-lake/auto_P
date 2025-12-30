import os

from dotenv import load_dotenv

from auto_p_services.McpServiceManager import McpServiceManager

load_dotenv()

"""
args 第一个必须是.py/.js文件的绝对路径, 所有参数添加到其后面
"""
mcp_service_manager = McpServiceManager(
    mcp_config={
        # 官方服务,不要修改
        os.getenv('OFFICIAL_SERVICE_NAMES'): {
            "transport": "stdio",
            "description": "官方提供工具(如工具搜索,暂停和等待)",
            "command": "python",
            "args": ["/Users/macbook0000/PycharmProjects/auto_P/auto_p_services/auto_p_server.py"],
        },
        # 三方服务

        # 浏览器服务
        "chrome-devtools": {
            "transport": "stdio",
            "command": "node",
            "description": "浏览器自动化工具（如打开页面、跳转、输入、点击等）",
            # "unified_output_func": "",
            "args": [
                "/Users/macbook0000/Downloads/chrome-devtools-mcp-chrome-devtools-mcp-v0.11.0/chrome-devtools-mcp-chrome-devtools-mcp-v0.11.0/build/src/index.js",
                # f"--user-data-dir={os.getenv("USER_DATA_DIR")}",
            ]
        },

        # "chrome-tools": {
        #     "transport": "stdio",
        #     "description": "浏览器自动化工具（如打开页面、跳转、输入、点击等）",
        #     "command": "python",
        #     "args": ["/Users/macbook0000/PycharmProjects/auto_P/auto_p_services/browser_p_server.py"],
        # },

        # word 服务
        # "word-document-server": {
        #     "transport": "stdio",
        #     "command": "/Users/macbook0000/PycharmProjects/Office-Word-MCP-Server/.venv/bin/python",
        #     "description": "Microsoft Word文档自动化工具,用于创建、读取和操作Microsoft Word文档",
        #     "args": [
        #         "/Users/macbook0000/PycharmProjects/Office-Word-MCP-Server/word_mcp_server.py"
        #     ],
        #     "env": {
        #         "PYTHONPATH": "/Users/macbook0000/PycharmProjects/Office-Word-MCP-Server",
        #         "MCP_TRANSPORT": "stdio"
        #     }
        # }

    }
)
