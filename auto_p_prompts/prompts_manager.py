import re

from pydantic.v1 import BaseModel, Field, validator


class PromptsManager:
    def __init__(self):
        pass

    class Prompt(BaseModel):
        prompt: str = Field(..., description="提示词,可以是携带{}的提示词模版", min_length=1)
        is_template: bool = False
        position_params: dict[str, str] = Field(
            default_factory=dict,
            description="提示词中的参数占位符,key为参数名,value为参数值"
        )

        @validator('is_template', pre=True, always=True)
        def set_is_template(cls, v, values):
            prompt = values.get('prompt', '')
            # 检查prompt中是否包含{xxxx}格式的占位符
            has_placeholder = bool(re.search(r'\{[^}]+\}', prompt))
            return has_placeholder

        def get_filled_prompt(self) -> str:
            """根据position_params自动填充prompt中的占位符"""
            if not self.is_template:
                return self.prompt

            filled_prompt = self.prompt
            for param_name, param_value in self.position_params.items():
                placeholder = f"{{{param_name}}}"
                filled_prompt = filled_prompt.replace(placeholder, str(param_value))

            return filled_prompt

    def build_prompt(self, prompt_template: str, **kwargs) -> str:
        """构建并返回填充好的提示词"""
        prompt = self.Prompt(
            prompt=prompt_template,
            position_params=kwargs
        )
        return prompt.get_filled_prompt()


if __name__ == '__main__':
    a = PromptsManager()
    print(a.build_prompt(prompt_template="hello {name}! my name is {name1}!", **{"name": "lihua", "name1": "fengtao"}))
