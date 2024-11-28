import ctypes
import sys
import time
from ctypes import wintypes

import win32api
import win32con
import win32gui
from utils.logger_utils import mylogger as logger

# set coinit_flags (there will be a warning message printed in console by pywinauto, you may ignore that)
sys.coinit_flags = 2  # COINIT_APARTMENTTHREADED
from pywinauto.controls.hwndwrapper import HwndWrapper
from pywinauto import Application

# 定义一些必要的 Windows API 函数和结构
EnumWindows = ctypes.windll.user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
GetClassName = ctypes.windll.user32.GetClassNameW
GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId


def center_wnd(window, width=None, height=None):
    if width is None:
        width = window.winfo_width()
    if height is None:
        height = window.winfo_height()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = int(window.winfo_screenheight() // 2.15) - int(height // 2.15)
    window.geometry('{}x{}+{}+{}'.format(width, height, x, y))


def bring_wnd_to_front(window_class, root):
    root.after(200, lambda: root.lift())
    root.after(300, lambda: root.attributes('-topmost', True))
    root.after(400, lambda: root.attributes('-topmost', False))
    root.after(500, lambda: root.focus_force())


def find_all_wnd_by_class_and_title(class_name, window_title=None):
    def enum_wnd_callback(hwnd, results):
        # 获取窗口的类名和标题
        if win32gui.IsWindowVisible(hwnd):
            curr_class_name = win32gui.GetClassName(hwnd)
            curr_window_title = win32gui.GetWindowText(hwnd)
            # 仅匹配类名，若window_title不为空则继续匹配标题
            if curr_class_name == class_name and (window_title is None or curr_window_title == window_title):
                results.append(hwnd)

    results = []
    win32gui.EnumWindows(enum_wnd_callback, results)
    return results


def find_hwnd_by_pid_and_class(pid, target_class_name):
    hwnd_list = []

    def enum_windows_callback(hwnd, lParam):
        # 获取窗口所属的进程 ID
        process_id = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))

        # 检查是否是目标进程的窗口
        if process_id.value == pid:
            class_name = ctypes.create_unicode_buffer(256)
            GetClassName(hwnd, class_name, 256)

            # 检查窗口类名是否匹配
            if class_name.value == target_class_name:
                hwnd_list.append(hwnd)
        return True

    # 枚举所有窗口
    EnumWindows(EnumWindowsProc(enum_windows_callback), 0)

    return hwnd_list


def wait_for_wnd_open(class_name, timeout=30, name=None):
    """等待指定类名的窗口打开，并返回窗口句柄"""
    end_time = time.time() + timeout
    while time.time() < end_time:
        hwnd = win32gui.FindWindow(class_name, name)
        if hwnd:
            return hwnd  # 返回窗口句柄
        time.sleep(0.5)
    return None  # 未找到窗口，返回 None


def get_center_pos_by_hwnd_and_title(handle, title, control_type="Button"):
    """获取指定控件中点的相对位置"""
    try:
        # 连接到应用程序窗口
        app = Application(backend="uia").connect(handle=handle)
        # 获取主窗口对象
        main_window = app.window(handle=handle)
        # 查找 "进入微信" 按钮
        wechat_button = main_window.child_window(title=title, control_type=control_type)
        if wechat_button.exists():
            # 获取主窗口的矩形区域（绝对位置）
            main_window_rect = main_window.rectangle()

            # 获取按钮的矩形区域（绝对位置）
            button_rect = wechat_button.rectangle()

            # 计算按钮相对于主窗口的相对位置
            relative_x = button_rect.left - main_window_rect.left
            relative_y = button_rect.top - main_window_rect.top
            relative_center_x = button_rect.mid_point().x - main_window_rect.left
            relative_center_y = button_rect.mid_point().y - main_window_rect.top

            print(f"相对于主窗口的左上角位置: ({relative_x}, {relative_y})")
            print(f"相对于主窗口的中心位置: ({relative_center_x}, {relative_center_y})")
            return relative_center_x, relative_center_y
        else:
            print(f"Button '{title}' not found!")
            return None, None
    except Exception as ex:
        logger.error(ex)


def get_wnd_details_from_hwnd(hwnd):
    """通过句柄获取窗口的尺寸和位置"""
    w = HwndWrapper(hwnd)
    if w.handle == hwnd:
        # print(f"{w.handle}")
        return {
            "window": w,
            "handle": w.handle,
            "title": w.window_text(),
            "top": w.rectangle().top,
            "left": w.rectangle().left,
            "width": w.rectangle().width(),
            "height": w.rectangle().height()
        }

    return None  # 如果没有找到匹配的窗口句柄，返回 None


def get_all_child_hwnd(parent_handle):
    """
    获取指定父窗口句柄下的所有子窗口句柄。

    :param parent_handle: 父窗口句柄
    :return: 子窗口句柄列表
    """
    child_handles = []

    def enum_child_windows_proc(hwnd, lParam):
        child_handles.append(hwnd)
        return True

    # 定义回调函数类型
    EnumChildWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    enum_proc = EnumChildWindowsProc(enum_child_windows_proc)

    # 调用 EnumChildWindows 来获取所有子窗口
    ctypes.windll.user32.EnumChildWindows(parent_handle, enum_proc, 0)

    return child_handles


def do_click_in_wnd(handle, cx, cy):
    """
    在窗口中的相对位置点击鼠标，可以后台
    :param handle: 句柄
    :param cx: 相对横坐标
    :param cy: 相对纵坐标
    :return: 无
    """
    long_position = win32api.MAKELONG(cx, cy)  # 模拟鼠标指针 传送到指定坐标
    print(f"要点击的handle：{handle}")
    win32api.SendMessage(handle, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, long_position)  # 模拟鼠标按下
    win32api.SendMessage(handle, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON, long_position)  # 模拟鼠标弹起
    print(f"模拟点击按钮")


def close_wnd_by_name(window_name):
    login_window = win32gui.FindWindow(window_name, None)
    if login_window:
        win32gui.PostMessage(login_window, win32con.WM_CLOSE, 0, 0)


def close_all_wnd_by_classes(class_names):
    """
    根据窗口类名关闭所有匹配的窗口
    :param class_names: 窗口类名列表
    :return: 无
    """
    for class_name in class_names:
        while True:
            hwnd = win32gui.FindWindow(class_name, None)
            if hwnd:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                time.sleep(0.5)  # 等待窗口关闭
            else:
                break


def wait_for_wnd_close(hwnd, timeout=30):
    """等待指定窗口句柄的窗口关闭"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if win32gui.IsWindow(hwnd) == 0:  # 检查窗口是否存在
            return True
        time.sleep(0.5)
    return False

if __name__ == '__main__':
    # 示例使用
    pid = 20468  # 替换为目标进程的 PID
    target_class = "WeChatMainWndForPC"  # 替换为目标窗口类名
    hwnd = find_hwnd_by_pid_and_class(pid, target_class)
    print("Found HWNDs:", hwnd)
# 示例用法
# if __name__ == "__main__":
#     import tkinter as tk
#     import pystray
#     from tkinter import ttk
#     from PIL import Image
#     from resources import Config
#
#     root = tk.Tk()
#     root.overrideredirect(True)  # 隐藏标题栏
#
#
#     def exit_action(icon, item):
#         icon.stop()
#
#
#     def show_window(icon, item):
#         root.update_idletasks()
#         root.deiconify()
#
#
#     def hide_window(icon, item):
#         root.withdraw()
#
#
#     image = Image.open(Config.PROJ_ICO_PATH)  # 使用自定义图标
#     icon = pystray.Icon("name", image, "Title")
#     icon.run()
