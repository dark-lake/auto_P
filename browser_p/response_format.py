from pydantic import BaseModel


class Bbox(BaseModel):
    """
    x_min x坐标最小值
    y_min y坐标最小值
    x_max x坐标最大值
    y_max y坐标最大值
    """
    x_min: int  # x坐标最小值
    y_min: int  # y坐标最小值
    x_max: int  # x坐标最大值
    y_max: int  # y坐标最大值


class XpathStr(BaseModel):
    xpath: str
