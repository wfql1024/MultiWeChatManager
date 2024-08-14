import time

import win32con
import win32gui


def wait_for_window_open(class_name, timeout=30):
    end_time = time.time() + timeout
    while time.time() < end_time:
        if win32gui.FindWindow(class_name, None):
            return True
        time.sleep(0.5)
    return False


def wait_for_window_close(class_name, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        window = win32gui.FindWindow(class_name, None)
        if window == 0:
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
