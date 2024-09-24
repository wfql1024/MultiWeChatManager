import ctypes
import os.path
import re
import subprocess
import sys
import time
import tkinter as tk

import win32api
import win32con
import win32gui

from resources import Config

# set coinit_flags (there will be a warning message printed in console by pywinauto, you may ignore that)
sys.coinit_flags = 2  # COINIT_APARTMENTTHREADED
from pywinauto.controls.hwndwrapper import HwndWrapper
from pywinauto import Application


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() - 25

        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tooltip, text=self.text, background="#ffffe0", relief="solid", borderwidth=1)
        label.pack()

    def hide(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


def bring_window_to_front(window_class):
    window_class.master.after(200, lambda: window_class.master.lift())
    window_class.master.after(300, lambda: window_class.master.attributes('-topmost', True))
    window_class.master.after(400, lambda: window_class.master.attributes('-topmost', False))
    window_class.master.after(500, lambda: window_class.master.focus_force())


def close_mutex_of_pids():
    """
    通过微信进程id查找互斥体并关闭
    :return: 是否成功
    """
    print(f"进入了关闭互斥体的方法...")
    # 定义句柄名称
    handle_name = "_WeChat_App_Instance_Identity_Mutex_Name"
    start_time = time.time()
    handle_exe_path = os.path.join(Config.PROJ_EXTERNAL_RES_PATH, 'handle.exe')

    # 获取句柄信息
    handle_info = subprocess.check_output([handle_exe_path, '-a', '-p', f"WeChat", handle_name]).decode()
    print(f"完成获取句柄信息：{handle_info}")
    print(f"{time.time() - start_time}")

    # 匹配所有 PID 和句柄信息
    matches = re.findall(r"pid:\s*(\d+).*?(\w+):\s*\\Sessions", handle_info)
    if matches:
        print(f"找到互斥体：{matches}")
    else:
        print(f"没有找到任何互斥体")
        return []

    # 用于存储成功关闭的句柄
    successful_closes = []

    # 遍历所有匹配项，尝试关闭每个句柄
    for wechat_pid, handle in matches:
        print(f"尝试关闭互斥体句柄: hwnd:{handle}, pid:{wechat_pid}")
        try:
            subprocess.run([handle_exe_path, '-c', handle, '-p', wechat_pid, '-y'], check=True)
            print(f"成功关闭句柄: hwnd:{handle}, pid:{wechat_pid}")
            successful_closes.append((wechat_pid, handle))
        except subprocess.CalledProcessError as e:
            print(f"无法关闭句柄 PID: {wechat_pid}, 错误信息: {e}")

    print(f"成功关闭的句柄列表: {successful_closes}")
    return successful_closes


def get_all_child_handles(parent_handle):
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


def do_click_in_window(handle, cx, cy):  # 第四种，可后台
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


def find_all_windows_by_class_and_title(class_name, window_title):
    def enum_windows_callback(hwnd, results):
        # 获取窗口的类名和标题
        if win32gui.IsWindowVisible(hwnd):
            curr_class_name = win32gui.GetClassName(hwnd)
            curr_window_title = win32gui.GetWindowText(hwnd)
            if curr_class_name == class_name and curr_window_title == window_title:
                results.append(hwnd)

    results = []
    win32gui.EnumWindows(enum_windows_callback, results)
    return results


def wait_for_window_open(class_name, timeout=30, name=None):
    """等待指定类名的窗口打开，并返回窗口句柄"""
    end_time = time.time() + timeout
    while time.time() < end_time:
        hwnd = win32gui.FindWindow(class_name, name)
        if hwnd:
            return hwnd  # 返回窗口句柄
        time.sleep(0.5)
    return None  # 未找到窗口，返回 None


def get_window_details_from_hwnd(hwnd):
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


def close_windows_by_class(class_names):
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


def wait_for_window_close(hwnd, timeout=30):
    """等待指定窗口句柄的窗口关闭"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if win32gui.IsWindow(hwnd) == 0:  # 检查窗口是否存在
            return True
        time.sleep(0.5)
    return False


def center_window(window):
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = int(window.winfo_screenheight() // 2.15) - int(height // 2.15)
    window.geometry('{}x{}+{}+{}'.format(width, height, x, y))


def close_window_by_name(window_name):
    login_window = win32gui.FindWindow(window_name, None)
    if login_window:
        win32gui.PostMessage(login_window, win32con.WM_CLOSE, 0, 0)


def get_center_pos_by_handle_and_title(handle, title, control_type="Button"):
    """获取指定控件中点的相对位置"""
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
        print("Button '进入微信' not found!")


if __name__ == '__main__':
    get_center_pos_by_handle_and_title(662940, "进入微信")
