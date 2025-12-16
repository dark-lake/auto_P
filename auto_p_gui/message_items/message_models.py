from typing import List, Union

from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self


class AutoPContentItem(BaseModel):
    """消息内容项"""
    type: str = Field(default="", description="内容类型")
    text: str = Field(default="", description="内容文本")


class AutoPMessage(BaseModel):
    """消息模型"""
    type: str = Field(default="message", description="消息类型")
    role: str = Field(default="", description="角色")
    content: List[AutoPContentItem] = Field(default_factory=list, description="消息内容列表")

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
    type: str = Field(default="", description="调用类型")
    arguments: str = Field(default="", description="调用参数")
    name: str = Field(default="", description="工具名称")
    call_id: str = Field(default="", description="调用ID")


class AutoPToolCallResult(BaseModel):
    """工具调用结果模型"""
    type: str = Field(default="function_call_output", description="结果类型")
    name: str = Field(default="", description="工具名称")
    output: str = Field(default="", description="工具输出")
    call_id: str = Field(default="", description="调用ID")


AutoPModel = Union[AutoPMessage, AutoPToolCall, AutoPToolCallResult, AutoPContentItem]

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
