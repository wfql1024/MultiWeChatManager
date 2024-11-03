import tkinter as tk
from tkinter import colorchooser

from resources import Constants
from utils import logger_utils

logger = logger_utils.mylogger


def clean_display_name(display_name):
    """
    清理 display_name 中的字符，替换所有 Unicode 码点 > U+FFFF 的字符为 '_'
    并记录其位置和码点。

    Args:
        display_name (str): 原始显示名称字符串。

    Returns:
        str: 清理后的字符串。
    """
    new_display_name = []
    for index, char in enumerate(display_name):
        code_point = ord(char)
        if code_point > 0xFFFF:
            logger.warning(f"警告: 在位置 {index} 发现不支持的字符(U+{code_point:04X})，已替换为 '_'")
            new_display_name.append('_')
        else:
            new_display_name.append(char)
    return ''.join(new_display_name)


def balanced_wrap_text(text, max_width=10) -> str:
    """
    将文本按指定宽度尽量平分两行处理，超过 max_width 的部分尽量让上行更长。
    :param text: 要处理的文本
    :param max_width: 每行最大字符数
    :return: 处理后的文本
    """
    # 如果文本长度小于等于 max_width，直接返回文本
    if len(text) <= max_width:
        return text

    # 计算平分点，使得上行尽量更长
    middle = (len(text) + 1) // 2

    # 将文本平分为两行
    return text[:middle] + "\n" + text[middle:]


def get_color_from_bright_color(color, mode):
    # 定义差值
    diff = Constants.COLOR_DIFF.get(mode, (5, 5, 5))  # 亮蓝色到选中色的差值

    # 将输入的颜色转为 RGB
    if isinstance(color, str):
        if color.startswith('#'):  # HEX格式
            rgb = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
        else:  # Tkinter定义的颜色单词
            raise ValueError("Unsupported color format. Use HEX, RGB tuple or Tkinter color name.")
            # rgb = [int(c * 256) for c in tk.Tk().winfo_rgb(color)]
    elif isinstance(color, tuple) and len(color) == 3:  # RGB格式
        rgb = list(color)
    else:
        raise ValueError("Unsupported color format. Use HEX, RGB tuple or Tkinter color name.")

    # 将输入的亮色转为RGB
    result_color = "#{:02X}{:02X}{:02X}".format(
        min(max(rgb[0] + diff[0], 0), 255),
        min(max(rgb[1] + diff[1], 0), 255),
        min(max(rgb[2] + diff[2], 0), 255)
    )

    return result_color


def choose_color_and_get_variants():
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口

    # 弹出颜色选择器
    color_code = colorchooser.askcolor(title="选择颜色")[1]  # 返回HEX格式
    if color_code:
        selected_color = get_color_from_bright_color(color_code, "selected")
        hover_color = get_color_from_bright_color(color_code, "hover")

        print("选中色:", selected_color)
        print("悬停色:", hover_color)


if __name__ == '__main__':
    choose_color_and_get_variants()
