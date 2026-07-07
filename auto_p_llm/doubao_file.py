import os

from dotenv import load_dotenv
from openai import OpenAI

from auto_p_utils.logger_util import logger

load_dotenv()

client = OpenAI(
    base_url='https://ark.cn-beijing.volces.com/api/v3',
    api_key=os.getenv("CHAT_API_KEY"),
)


async def doubao_upload_file(file_path: str) -> str:
    if not os.path.exists(file_path):
        logger.info(f'截图不存在:{file_path}')
        return ''

    try:
        file = client.files.create(
            file=open(file_path, "rb"),
            purpose="user_data"
        )

        logger.info(f'截图上传完毕:{file}')
        return file.id

    except Exception as e:
        logger.exception(e)
        return ''
#
# asyncio.run(doubao_upload_file("/Users/macbook0000/PycharmProjects/auto_P/img/take_screensho.png"))
