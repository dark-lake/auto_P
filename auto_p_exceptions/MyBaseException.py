class MyBaseExceptionCode:
    PAGE_NOT_FOUND = 401  # 页面未找到
    ELEMENT_NOT_FOUND = 402  # 元素未找到
    HTML_NOT_FOUND = 403  # HTML未找到
    KEYBOARD_NOT_FOUND = 404  # 键盘未找到
    FILE_NOT_EXIST = 405  # 文件不存在

    CLICK_FAILED = 500  # 点击失败
    FILL_FAILED = 501  # 填写失败
    RELATIVE_POSITION_NOT_FOUND = 502  # 元素相对位置处理失败
    SCROLL_FAILED = 503  # 滚动失败
    SNAPSHOT_FAILED = 504  # 截图失败
    MODEL_FAILED = 505  # 大模型处理失败
    KEYBOARD_PRESS_FAILED = 506  # 键盘按键失败
    FILE_READ_FAILED = 507  # 文件读取失败
    FILE_WRITE_FAILED = 508  # 文件写入失败

    CONFIG_NOT_EXIST = 600  # 配置文件不存在


class MyBaseException(Exception):
    def __init__(self, code: int, message: str):
        self.message = message
        self.code = code
        super().__init__(self.message)
