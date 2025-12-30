from auto_p_chat_adapter.openai_adapter import OpenAIAdapter


class SeedAdapter(OpenAIAdapter):
    """
    字节的response api适配器
    """

    def __init__(
            self,
            seed_api_key: str,
            seed_api_base_url: str,
            seed_api_model: str
    ) -> None:
        super().__init__(
            seed_api_key,
            seed_api_base_url,
            seed_api_model
        )

    async def process_chat(
            self,
            messages: list,
            tools: list = None
            
    ) -> None:
        pass
