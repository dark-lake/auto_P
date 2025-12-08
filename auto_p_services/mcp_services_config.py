from dotenv import load_dotenv

from auto_p_services.McpServiceManager import McpServiceManager

load_dotenv()
"""
args 第一个必须是.py/.js文件的绝对路径, 所有参数添加到其后面
"""
mcp_service_manager = McpServiceManager(
    mcp_config={
        # 浏览器
        "chrome-devtools": {
            "transport": "stdio",
            "command": "node",
            # "unified_output_func": "",
            "args": [
                "/Users/macbook0000/Downloads/chrome-devtools-mcp-chrome-devtools-mcp-v0.11.0/chrome-devtools-mcp-chrome-devtools-mcp-v0.11.0/build/src/index.js",
                # f"--user-data-dir={os.getenv("USER_DATA_DIR")}",
            ]
        },
        # "chrome-tools": {
        #     "transport": "stdio",
        #     "command": "python",
        #     "args": ["/Users/macbook0000/PycharmProjects/auto_P/auto_p_services/browser_p_server.py"],
        # },
        "auto_p-tools": {
            "transport": "stdio",
            "command": "python",
            "args": ["/Users/macbook0000/PycharmProjects/auto_P/auto_p_services/auto_p_server.py"],
        },
    }
)
