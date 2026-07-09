"""提示词模板管理 — 轻量级字符串替换。"""


def fill_prompt(template: str, **kwargs) -> str:
    """用 kwargs 替换模板中的 {placeholder} 占位符。"""
    result = template
    for key, value in kwargs.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


# 保持向后兼容
build_prompt = fill_prompt
