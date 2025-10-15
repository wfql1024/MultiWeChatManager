import ctypes
from ctypes import wintypes

# 定义常量：窗口显示状态
SW_HIDE = 0  # 隐藏窗口
SW_SHOWNORMAL = 1  # 恢复窗口（普通显示）
SW_SHOWMINIMIZED = 2  # 最小化窗口
SW_SHOWMAXIMIZED = 3  # 最大化窗口

# 加载 user32.dll 动态库
user32 = ctypes.WinDLL("user32", use_last_error=True)

# 定义 Windows API 函数
FindWindow = user32.FindWindowW
FindWindow.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
FindWindow.restype = wintypes.HWND

ShowWindow = user32.ShowWindow
ShowWindow.argtypes = [wintypes.HWND, wintypes.INT]
ShowWindow.restype = wintypes.BOOL

IsWindowVisible = user32.IsWindowVisible
IsWindowVisible.argtypes = [wintypes.HWND]
IsWindowVisible.restype = wintypes.BOOL


# 定义辅助函数
def get_window_handle(window_title):
    """
    根据窗口标题查找窗口句柄。
    :param window_title: 窗口标题
    :return: 窗口句柄 (HWND)
    """
    hwnd = FindWindow(None, window_title)
    if hwnd == 0:
        raise ValueError(f"窗口 '{window_title}' 未找到。")
    return hwnd


def minimize_window(hwnd):
    """
    最小化窗口。
    :param hwnd: 窗口句柄
    """
    ShowWindow(hwnd, SW_SHOWMINIMIZED)


def maximize_window(hwnd):
    """
    最大化窗口。
    :param hwnd: 窗口句柄
    """
    ShowWindow(hwnd, SW_SHOWMAXIMIZED)


def restore_window(hwnd):
    """
    恢复窗口。
    :param hwnd: 窗口句柄
    """
    ShowWindow(hwnd, SW_SHOWNORMAL)


def hide_window(hwnd):
    """
    隐藏窗口。
    :param hwnd: 窗口句柄
    """
    ShowWindow(hwnd, SW_HIDE)


def is_window_visible(hwnd):
    """
    检查窗口是否可见。
    :param hwnd: 窗口句柄
    :return: True/False
    """
    return bool(IsWindowVisible(hwnd))


# 测试函数
if __name__ == "__main__":
    try:
        # 修改为你想操作的窗口标题
        window_title = "微信"

        # 获取窗口句柄
        hwnd = get_window_handle(window_title)
        print(f"窗口句柄: {hwnd}")

        # 执行操作
        print("最小化窗口...")
        minimize_window(hwnd)

        input("按回车键恢复窗口...")
        restore_window(hwnd)

        input("按回车键最大化窗口...")
        maximize_window(hwnd)

        input("按回车键隐藏窗口...")
        hide_window(hwnd)

        print(f"窗口是否可见: {is_window_visible(hwnd)}")
    except ValueError as e:
        print(e)
