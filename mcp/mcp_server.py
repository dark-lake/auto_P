from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base

#  mcp = FastMCP(name="demo",host="127.0.0.1",port=8256,sse_path="/sse")   ### 启动方式为sse时使用
mcp = FastMCP("testserver")


@mcp.tool()
def  add_2_numbers(a:

 int, b: int) -> int:
 """两个数字相加"""
 return a + b


@mcp.resource("config://app")
def  get_config() -> str:
    """Static configuration data"""
    return "App configuration here"


@mcp.prompt()
def  debug_error(error:str) -> list[base.Message]:
    return [
        base.UserMessage("I'm seeing this error:"),
        base.UserMessage(error),
        base.AssistantMessage("I'll help debug that. What have you tried so far?"),
        ]


@mcp.tool()
def  multiply_2_numbers(a:int, b: int):
    """两个数字相乘"""
    return a  *  b

if  __name__  ==  "__main__":
       #  mcp.run(transport='sse')   ## 启动方式为sse
     mcp.run(transport='stdio')     ## 启动方式为stdio