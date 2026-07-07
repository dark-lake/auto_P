from typing import List, Union, Any

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self


class AutoPContentItem(BaseModel):
    """消息内容项"""
    type: str = Field(default="input_text", description="内容类型")
    text: str = Field(default="", description="内容文本")


class AutoPIMGContentItem(BaseModel):
    """图片内容项目"""
    type: str = Field(default="input_image", description="内容类型")
    file_id: str = Field(default="", description="文件ID")
    detail: str = Field(default="high", description="取值范围：low、high、xhigh")


class AutoPMessage(BaseModel):
    """消息模型"""
    type: str = Field(default="message", description="消息类型")
    role: str = Field(default="", description="角色")
    content: List[AutoPContentItem, AutoPIMGContentItem] = Field(default_factory=list, description="消息内容列表")
    status: str = Field(default="in_progress", description="项目状态")

    @model_validator(mode='after')
    def set_type_based_on_role(self) -> Self:
        if self.role in ["user", "system"]:
            self.content[0].type = "input_text"
        elif self.role == "assistant":
            self.content[0].type = "output_text"
        else:
            # function
            pass
        return self


class AutoPToolCall(BaseModel):
    """工具调用模型"""
    type: str = Field(default="function_call", description="调用类型")
    arguments: str = Field(default="", description="调用参数")
    name: str = Field(default="", description="工具名称")
    call_id: str = Field(default="", description="调用ID")
    status: str = Field(default="in_progress", description="状态")


class AutoPToolCallResult(BaseModel):
    """工具调用结果模型"""
    type: str = Field(default="function_call_output", description="结果类型")
    # name: str = Field(default="", description="工具名称")
    output: Any = Field(default="", description="工具输出")
    call_id: str = Field(default="", description="调用ID")
    status: str = Field(default="completed", description="状态")


AutoPModel = Union[AutoPMessage, AutoPToolCall, AutoPToolCallResult, AutoPContentItem, AutoPIMGContentItem]

if __name__ == '__main__':
    system_prompt = {
        "role": "system",
        "content": [{
            "type": "input_text",
            "text": "12341",
        }]
    }
    a = AutoPMessage.model_validate(system_prompt)
    print(a.model_dump_json())
