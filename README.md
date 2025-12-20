# auto_p 助手

> [!important]
>
> 目标：通过聊天的方式，实现自动化操作。

## 项目简介

auto_p 助手是一个基于大语言模型的自动化操作工具，通过自然语言交互实现各种自动化任务。该项目集成了多种 MCP (Model Control
Protocol) 服务，目前主要专注于浏览器自动化功能。

![image-20251220201455763](./README.assets/image-20251220201455763.png)

## 架构

- **UI**: Gradio
- **语言**: Python
- **数据库**: ChromaDB
- **核心协议**: MCP (Model Control Protocol)

### MCP 服务

- [chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp/releases/tag/chrome-devtools-mcp-v0.12.1) -
  浏览器自动化工具

## 功能介绍

1. 目前已具备浏览器自动化的能力
2. 支持通过自然语言控制浏览器操作（打开页面、点击元素、填写表单等）
3. 集成向量数据库实现智能工具搜索

## 技术栈

- **后端**: Python 3.12+
- **前端**: Gradio 6.1.0
- **AI 模型**:
    - 对话模型: DeepSeek v3.2
    - 视觉模型: Doubao Seed 1.6 Flash
    - 向量模型: Doubao Embedding Vision
- **数据库**: ChromaDB 1.3.5+

## 安装与配置

### 环境要求

- Python 3.12 或更高版本
- Google Chrome 浏览器（用于浏览器自动化）
- Node.js（用于chrome-devtools-mcp 服务, 需参考其Github中的内容手动安装）

### 安装步骤

1. 克隆项目：
   ```bash
   git clone <repository-url>
   cd auto_p
   ```

2. 安装依赖：
   ```bash
   pip install -e .
   ```

3. 配置环境变量：
    - 复制 [.env.example](file:///Users/macbook0000/PycharmProjects/auto_P/.env) 文件为 .env
    - 根据需要修改其中的配置项，特别是 API 密钥和路径配置

### 环境变量配置

主要配置项包括：

- `CHAT_API_KEY`, `CHAT_OPEN_MODEL`, `CHAT_BASE_URL` - 对话模型配置
- `VIS_API_KEY`, `VIS_OPEN_MODEL`, `VIS_BASE_URL` - 视觉模型配置
- `EMBEDDING_API_KEY`, `EMBEDDING_OPEN_MODEL`, `EMBEDDING_BASE_URL` - 向量模型配置
- `BASE_PATH` - 项目基础路径
- `CHROME_PATH` - Chrome 浏览器路径（可选）
- `USER_DATA_DIR` - Chrome 用户数据目录（可选）

## 使用方法

1. 启动服务：
   ```bash
   python -m auto_p_gui.gradio_gui
   ```

2. 在浏览器中打开提供的地址（通常是 http://localhost:7860）

3. 在聊天界面中通过自然语言描述您想要执行的操作

### 示例操作

- "打开百度网站"
- "在搜索框中输入'人工智能'"
- "点击搜索按钮"
- "截取当前页面截图并分析内容"

## 项目结构

```
auto_p/
├── auto_p_agents/          # 代理逻辑
├── auto_p_clients/         # 客户端实现
├── auto_p_gui/             # 图形界面
├── auto_p_services/        # MCP 服务实现
├── auto_p_utils/           # 工具类
├── auto_p_vector/          # 向量处理相关
├── auto_p_prompts/         # 提示词管理
├── auto_p_exceptions/      # 自定义异常
├── auto_p_script/          # 脚本工具
└── auto_p_doc/             # 文档相关
```

## 开发指南

### 添加新的 MCP 服务

1. 在 [mcp_services_config.py](file:///Users/macbook0000/PycharmProjects/auto_P/auto_p_services/mcp_services_config.py)
   中添加服务配置
2. 实现相应的服务端逻辑
3. 重启应用使配置生效

### 扩展功能

1. 可以通过实现新的 MCP 工具来扩展功能
2. 修改提示词模板以优化模型行为
3. 添加新的向量处理逻辑以增强工具搜索能力

## 注意事项

- 浏览器自动化功能需要本地安装 Google Chrome
- 某些功能可能需要网络连接以访问 AI 模型 API
- 向量数据库会自动持久化到本地文件系统

## 许可证

[待补充许可证信息]

## 联系方式

[待补充联系方式]