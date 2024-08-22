# func_login.py
import ctypes
import os
import shutil
import subprocess
import time
from ctypes import wintypes

import pyautogui
from pywinauto import Application, Desktop

from functions import func_setting
from functions.func_setting import is_valid_wechat_install_path, is_valid_wechat_data_path
from utils.window_utils import wait_for_window_open, wait_for_window_close
from resources.config import Config

import win32gui


def move_window(window_title, x, y):
    hwnd = win32gui.FindWindow(None, window_title)
    if hwnd:
        print("存在窗口")
        win32gui.MoveWindow(hwnd, x, y, 300, 200, True)


def manual_login(status):
    wechat_path = func_setting.get_wechat_install_path()
    if status == "已开启":
        subprocess.Popen(wechat_path, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        multi_wechat_process = subprocess.Popen(Config.MULTI_SUBPROCESS, creationflags=subprocess.CREATE_NO_WINDOW)
    # 等待窗口打开
    time.sleep(2)

    wechat_window = pyautogui.getWindowsWithTitle("微信")[0]
    # wechat_window.moveTo(100, 100)
    (width, height) = wechat_window.size

    print(f"窗口宽度: {width}, 窗口高度: {height}")

    if wait_for_window_open("WeChatLoginWndForPC", timeout=3):
        print("登录窗口已打开")

        if wait_for_window_close("WeChatLoginWndForPC", timeout=60):
            print("登录窗口已关闭")
            return True
    else:
        print("打开失败，请重试！")
        return False


def auto_login(account, status):
    # 获取数据路径
    data_path = func_setting.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY_DATA_PATH,
        is_valid_wechat_data_path
    )
    wechat_path = func_setting.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY_INSTALL_PATH,
        is_valid_wechat_install_path
    )
    if not data_path:
        return False

    # 构建源文件和目标文件路径
    source_file = os.path.join(data_path, "All Users", "config", f"{account}.data")
    target_file = os.path.join(data_path, "All Users", "config", "config.data")

    # 确保目标目录存在
    os.makedirs(os.path.dirname(target_file), exist_ok=True)

    # 复制配置文件
    try:
        shutil.copy2(source_file, target_file)
    except Exception as e:
        print(f"复制配置文件失败: {e}")
        return False

    print("复制配置文件成功")
    if status == "已开启":
        subprocess.Popen(wechat_path)
    else:
        multi_wechat_process = subprocess.Popen(Config.MULTI_SUBPROCESS, creationflags=subprocess.CREATE_NO_WINDOW)
    if wait_for_window_open("WeChatLoginWndForPC", timeout=3):
        print("打开了登录窗口")
        time.sleep(1)
        pyautogui.press('space')
        print("点击了按钮")
        # 等待登录窗口关闭
        if wait_for_window_close("WeChatLoginWndForPC", timeout=60):
            print("登录窗口已关闭")
            return True
        else:
            print("登录超时")
            return False
    return False


if __name__ == '__main__':
    # 连接到WeChat进程
    app = Application(backend="uia").connect(process=33552)

    # 找到主窗口
    main_window = app.window(class_name="WeChatLoginWndForPC")

    # 找到并点击按钮
    main_window.child_window(title="进入微信", control_type="Button").click()
