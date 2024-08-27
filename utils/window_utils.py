import ctypes
import time
import tkinter as tk

import win32con
import win32gui
import pygetwindow as gw
from pywinauto import Desktop


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


class RECT(ctypes.Structure):
    _fields_ = [
        ('left', ctypes.c_long),
        ('top', ctypes.c_long),
        ('right', ctypes.c_long),
        ('bottom', ctypes.c_long),
    ]


def wait_for_window_open(class_name, timeout=30):
    """等待指定类名的窗口打开，并返回窗口句柄"""
    end_time = time.time() + timeout
    while time.time() < end_time:
        hwnd = win32gui.FindWindow(class_name, None)
        if hwnd:
            return hwnd  # 返回窗口句柄
        time.sleep(0.5)
    return None  # 未找到窗口，返回 None


def get_window_details_from_hwnd(hwnd):
    """通过句柄获取窗口的尺寸和位置"""
    desktop = Desktop(backend="win32")
    windows = desktop.windows()

    for w in windows:
        if w.handle == hwnd:
            return {
                "window": w,
                "handle": w.handle,
                "title": w.window_text(),
                "top": w.rectangle().top,
                "left": w.rectangle().left,
                "width": w.rectangle().width(),
                "height": w.rectangle().height()
            }


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


def close_window(window_name):
    login_window = win32gui.FindWindow(window_name, None)
    if login_window:
        win32gui.PostMessage(login_window, win32con.WM_CLOSE, 0, 0)
