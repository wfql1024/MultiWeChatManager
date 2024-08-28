import time
import tkinter as tk

import win32con
import win32gui
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
