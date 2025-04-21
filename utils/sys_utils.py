import ctypes
import os
import platform
import winreg
from ctypes import wintypes
from pathlib import Path
from contextlib import contextmanager

# 定义常量
MDT_EFFECTIVE_DPI = 0  # 有效 DPI（当前缩放）
PROCESS_PER_MONITOR_DPI_AWARE = 2  # 进程 DPI 感知模式

# 定义常量
SPI_GETICONTITLELOGFONT = 0x001F


@contextmanager
def disable_proxy_temporarily():
    # 保存原始环境变量
    old_http = os.environ.get('http_proxy')
    old_https = os.environ.get('https_proxy')
    old_noproxy = os.environ.get('no_proxy')

    try:
        os.environ['http_proxy'] = ''
        os.environ['https_proxy'] = ''
        os.environ['no_proxy'] = '*'
        yield
    finally:
        # 恢复原始代理设置
        if old_http is not None:
            os.environ['http_proxy'] = old_http
        else:
            os.environ.pop('http_proxy', None)

        if old_https is not None:
            os.environ['https_proxy'] = old_https
        else:
            os.environ.pop('https_proxy', None)

        if old_noproxy is not None:
            os.environ['no_proxy'] = old_noproxy
        else:
            os.environ.pop('no_proxy', None)



def get_win7_scaling_from_registry():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as key:
            log_pixels, _ = winreg.QueryValueEx(key, "LogPixels")
            scaling_percentage = log_pixels / 96 * 100  # 96 DPI 是标准 100%
            return scaling_percentage
    except FileNotFoundError:
        return None


def get_font_size_from_registry():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop\WindowMetrics") as key:
            value, _ = winreg.QueryValueEx(key, "IconTitleSize")
            return int(value)
    except FileNotFoundError:
        return None


def get_system_dpi_by_device_caps():
    hdc = ctypes.windll.user32.GetDC(0)  # 获取设备上下文
    dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX = 88
    ctypes.windll.user32.ReleaseDC(0, hdc)
    return dpi


def get_startup_folder():
    # 定义常量：Startup 文件夹的 CSIDL 值
    CSIDL_STARTUP = 7
    MAX_PATH = 260

    # 创建缓冲区存储路径
    buf = ctypes.create_unicode_buffer(MAX_PATH)

    # 调用 SHGetFolderPath 获取路径
    ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_STARTUP, None, 0, buf)

    return Path(buf.value)


# def get_main_monitor_scale_factor_by_ctypes():
#     scale_factor = ctypes.windll.shcore.GetScaleFactorForDevice(0)
#     return scale_factor


class LOGFONT(ctypes.Structure):
    _fields_ = [
        ("lfHeight", wintypes.LONG),
        ("lfWidth", wintypes.LONG),
        ("lfEscapement", wintypes.LONG),
        ("lfOrientation", wintypes.LONG),
        ("lfWeight", wintypes.LONG),
        ("lfItalic", wintypes.BYTE),
        ("lfUnderline", wintypes.BYTE),
        ("lfStrikeOut", wintypes.BYTE),
        ("lfCharSet", wintypes.BYTE),
        ("lfOutPrecision", wintypes.BYTE),
        ("lfClipPrecision", wintypes.BYTE),
        ("lfQuality", wintypes.BYTE),
        ("lfPitchAndFamily", wintypes.BYTE),
        ("lfFaceName", wintypes.WCHAR * 32),  # 字体名
    ]


def get_system_font_size():
    logfont = LOGFONT()
    result = ctypes.windll.user32.SystemParametersInfoW(SPI_GETICONTITLELOGFONT, ctypes.sizeof(logfont),
                                                        ctypes.byref(logfont), 0)
    if result:
        return abs(logfont.lfHeight)  # 返回字体高度
    return None


def get_sys_major_version_name():
    major_version = platform.release()
    if major_version == "7":
        print("当前系统是 Windows 7")
        return "win7"
    elif major_version == "10":
        print("当前系统是 Windows 10")
        return "win10"
    elif major_version == "11":
        print("当前系统是 Windows 11")
        return "win11"
    else:
        print("当前不是 Windows 7、10 或 11")
        return "default"


if __name__ == "__main__":
    font_size = get_font_size_from_registry()
    print(f"系统字体大小 (注册表): {font_size}")

    font_size = get_system_font_size()
    print(f"系统字体大小: {font_size}")

    dpi = get_system_dpi_by_device_caps()
    scaling_percentage = dpi / 96 * 100  # 96 DPI 是标准 100%
    print(f"当前系统缩放比例: {scaling_percentage}%")

    # scaling_percentage = get_main_monitor_scale_factor_by_ctypes()
    # print(f"当前主屏幕缩放比例: {scaling_percentage}%")

    scaling_percentage = get_win7_scaling_from_registry()
    print(f"当前系统缩放比例 (注册表): {scaling_percentage}%")
