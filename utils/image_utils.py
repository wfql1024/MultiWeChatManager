import os

import requests
import win32api
import win32con
import win32gui
import win32ui
from PIL import Image, ImageDraw

from utils.logger_utils import mylogger as logger


def create_round_corner_image(img, radius):
    """
    创建圆角的头像
    :param img:
    :param radius:
    :return:
    """
    circle = Image.new('L', (radius * 2, radius * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, radius * 2, radius * 2), fill=255)
    alpha = Image.new('L', img.size, 255)
    w, h = img.size

    # 计算使图像居中的偏移量
    offset_x = (w - radius * 2) // 2
    offset_y = (h - radius * 2) // 2

    # 调整左上角圆角（radius-1）
    alpha.paste(circle.crop((0, 0, radius - 1, radius - 1)), (offset_x, offset_y))  # 左上角
    # 左下角保持原样
    alpha.paste(circle.crop((0, radius, radius, radius * 2)), (offset_x, h - radius - offset_y))  # 左下角
    # 右上角保持原样
    alpha.paste(circle.crop((radius, 0, radius * 2, radius)), (w - radius - offset_x, offset_y))  # 右上角
    # 调整右下角圆角（radius+1）
    alpha.paste(circle.crop((radius, radius, radius * 2 + 1, radius * 2 + 1)),
                (w - radius - offset_x, h - radius - offset_y))  # 右下角

    img.putalpha(alpha)
    return img


def download_image(img_url, path):
    """
    将网址中的图像保存到路径上
    :param img_url: 网址
    :param path: 路径
    :return: 是否成功
    """
    try:
        response = requests.get(img_url.rstrip(r'/0') + r'/132', stream=True)
        response.raise_for_status()  # 确保请求成功

        acc_dir = os.path.dirname(path)
        if not os.path.exists(acc_dir):
            os.makedirs(acc_dir)

        with open(path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        logger.info(f"图像已成功保存到 {path}")
        return True
    except requests.RequestException as re:
        return download_origin_image(img_url, path)


def download_origin_image(img_url, path):
    """
    将网址中的图像保存到路径上
    :param img_url: 网址
    :param path: 路径
    :return: 是否成功
    """
    try:
        response = requests.get(img_url, stream=True)
        response.raise_for_status()  # 确保请求成功

        acc_dir = os.path.dirname(path)
        if not os.path.exists(acc_dir):
            os.makedirs(acc_dir)

        with open(path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        logger.info(f"图像已成功保存到 {path}")
        return True
    except requests.RequestException as re:
        logger.error(f"下载图像时出错: {re}")
        return False


def png_to_ico(png_path, ico_path):
    """将png文件转格式为ico文件"""
    img = Image.open(png_path)
    img.save(ico_path, format='ICO', sizes=[(132, 132)])


def extract_icon_to_png(exe_path, output_png_path=None):
    """提取可执行文件的图标并保存为png格式"""
    ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
    ico_y = win32api.GetSystemMetrics(win32con.SM_CYICON)

    large, small = win32gui.ExtractIconEx(exe_path, 0)
    if small:
        win32gui.DestroyIcon(small[0])

    hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
    hbmp = win32ui.CreateBitmap()
    hbmp.CreateCompatibleBitmap(hdc, ico_x, ico_y)
    hdc = hdc.CreateCompatibleDC()

    hdc.SelectObject(hbmp)
    if not large:
        # 返回一个透明图像
        transparent_img = Image.new('RGBA', (ico_x, ico_y), (0, 0, 0, 0))
        if output_png_path is not None:
            transparent_img.save(output_png_path, format='PNG')
        return None
        # return ImageTk.PhotoImage(transparent_img)
    hdc.DrawIcon((0, 0), large[0])

    bmp_str = hbmp.GetBitmapBits(True)
    icon = Image.frombuffer(
        'RGBA',
        (ico_x, ico_y),
        bmp_str, 'raw', 'BGRA', 0, 1
    )

    win32gui.DestroyIcon(large[0])

    if output_png_path is not None:
        icon.save(output_png_path, format='PNG')
    else:
        pass
    # return ImageTk.PhotoImage(icon)


def add_diminished_se_corner_mark_to_image(image_path, mark_path, output_path, diminish_time=3):
    """
    为图像创建一个n倍缩小的角标（se右下角）
    :param image_path: 原图像地址
    :param mark_path: 角标图地址
    :param output_path: 输出地址
    :param diminish_time: 缩小倍数
    :return: 输出地址
    """
    image = Image.open(image_path).convert("RGBA")
    mark = Image.open(mark_path).convert("RGBA")

    # 计算叠加图像的大小为 background 大小的 1/3
    new_size = (int(image.width // diminish_time), int(image.height // diminish_time))
    mark = mark.resize(new_size, Image.Resampling.NEAREST)

    # 计算粘贴位置（右下角）
    paste_position = (image.width - mark.width, image.height - mark.height)

    # 创建一个新的图像用于合成
    combined = Image.new("RGBA", image.size)
    combined.paste(image, (0, 0))
    combined.paste(mark, paste_position, mark)

    combined.save(output_path, format='PNG')
    return output_path
