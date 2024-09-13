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


def bring_window_to_front(self):
    self.master.after(200, lambda: self.master.lift())
    self.master.after(300, lambda: self.master.attributes('-topmost', True))
    self.master.after(400, lambda: self.master.attributes('-topmost', False))
    self.master.after(500, lambda: self.master.focus_force())

def close_mutex_by_id(process_id):
    # 定义句柄名称
    handle_name = "_WeChat_App_Instance_Identity_Mutex_Name"
    start_time = time.time()
    handle_exe_path = os.path.join(Config.PROJ_EXTERNAL_RES_PATH, 'handle.exe')

    # 获取句柄信息
    handle_info = subprocess.check_output([handle_exe_path, '-a', handle_name, '-p', f"{process_id}"]).decode()
    print("完成获取句柄信息")
    print(time.time() - start_time)

    # 匹配 PID 和句柄
    match = re.search(r"pid:\s*(\d+).*?(\w+):\s*\\Sessions", handle_info)
    if match:
        wechat_pid = match.group(1)
        handle = match.group(2)
    else:
        return True
    print("完成匹配 PID 和句柄")
    print(f"{time.time() - start_time:.4f}秒")

    # 尝试关闭句柄
    try:
        subprocess.run([handle_exe_path, '-c', handle, '-p', wechat_pid, '-y'], check=True)
        print(f"关闭用时：{time.time() - start_time:.4f}秒")
        return True
    except subprocess.CalledProcessError as e:
        print(f"无法关闭句柄 PID: {wechat_pid}，错误信息: {e}\n")
        return False


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


def do_click(handle, cx, cy):  # 第四种，可后台
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
    print("模拟点击按钮")


def find_all_windows(class_name, window_title):
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
        print(w.handle)
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
