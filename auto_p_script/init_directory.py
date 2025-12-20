import os

from dotenv import load_dotenv

load_dotenv()


def init_directory() -> None:
    """
    初始化所需文件夹
    :return:
    """
    try:
        # 1.日志文件夹
        if not os.path.exists(os.getenv('LOG_PATH')):
            os.mkdir(os.getenv('LOG_PATH'))
        # 2.img
        if not os.path.exists(os.getenv('IMG_PATH')):
            os.mkdir(os.getenv('IMG_PATH'))
        # 3.avatar
        if not os.path.exists(os.getenv('AVATAR_PATH')):
            os.mkdir(os.getenv('AVATAR_PATH'))

        # 4.stream_log
        if not os.path.exists(os.getenv('STREAM_LOG_PATH')):
            os.mkdir(os.getenv('STREAM_LOG_PATH'))

        # 5.a11y_txt
        if not os.path.exists(os.getenv('A11Y_TXT_PATH')):
            os.mkdir(os.getenv('A11Y_TXT_PATH'))

    except Exception as e:
        print(f"无法初始化路径,请检查,{e}")


if __name__ == '__main__':
    init_directory()
