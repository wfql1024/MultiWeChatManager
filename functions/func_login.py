# func_login.py
import os
import shutil
import subprocess
import time
import tkinter as tk

import pyautogui
import win32api
import win32con
import win32gui

import utils
from functions import func_setting
from functions.func_config import ConfigCreator
from resources.config import Config
from utils import window_utils
from utils.window_utils import wait_for_window_open, wait_for_window_close


def doClick(handle, cx, cy):  # 第四种，可后台
    """
    在窗口中的相对位置点击鼠标，可以后台
    :param handle: 句柄
    :param cx: 相对横坐标
    :param cy: 相对纵坐标
    :return: 无
    """
    long_position = win32api.MAKELONG(cx, cy)  # 模拟鼠标指针 传送到指定坐标
    win32api.SendMessage(handle, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, long_position)  # 模拟鼠标按下
    win32api.SendMessage(handle, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON, long_position)  # 模拟鼠标弹起


def open_wechat(status):
    """
    根据状态以不同方式打开微信
    :param status: 状态
    :return: 微信窗口句柄
    """
    multi_wechat_process = None
    wechat_path = func_setting.get_wechat_install_path()
    data_path = func_setting.get_wechat_data_path()
    if not wechat_path or not data_path:
        return None
    sub_exe = func_setting.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY_SUB_EXE,
    )
    if status == "已开启":
        wechat_process = subprocess.Popen(wechat_path, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        if sub_exe == "WeChatMultiple_Anhkgg.exe":
            multi_wechat_process = subprocess.Popen(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}",
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        elif sub_exe == "WeChatMultiple_lyie15.exe" or sub_exe == "WeChatMultiple_pipihan.exe":
            multi_wechat_process = subprocess.Popen(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{sub_exe}",
                # creationflags=subprocess.CREATE_NO_WINDOW
            )
            sub_exe_hwnd = wait_for_window_open("WTWindow", 3)
            if sub_exe_hwnd:
                time.sleep(1.5)
                pyautogui.press('space')
    time.sleep(2)
    wechat_hwnd = wait_for_window_open("WeChatLoginWndForPC", 3)
    if multi_wechat_process:
        multi_wechat_process.terminate()
    if wechat_hwnd:
        return wechat_hwnd
    else:
        return None


def manual_login(status):
    """
    根据状态进行手动登录过程
    :param status: 状态
    :return: 成功与否
    """
    utils.window_utils.close_windows_by_class(["WTWindow", "WeChatLoginWndForPC"])
    wechat_hwnd = open_wechat(status)
    if wechat_hwnd:
        print(f"打开了登录窗口{wechat_hwnd}")
        screen_size = func_setting.get_setting_from_ini(
            Config.SETTING_INI_PATH,
            Config.INI_SECTION,
            Config.INI_KEY_SCREEN_SIZE,
        )
        if not screen_size or screen_size == "":
            login_wnd_details = window_utils.get_window_details_from_hwnd(wechat_hwnd)
            login_wnd = login_wnd_details["window"]
            login_width = login_wnd_details["width"]
            login_height = login_wnd_details["height"]
            if 0.734 < login_width / login_height < 0.740:
                func_setting.save_setting_to_ini(
                    Config.SETTING_INI_PATH,
                    Config.INI_SECTION,
                    Config.INI_KEY_SCREEN_SIZE,
                    f"{login_width}*{login_height}"
                )
        if wait_for_window_close(wechat_hwnd, timeout=60):
            print("登录窗口已关闭")
            return True
    else:
        print("打开失败，请重试！")
        return False
    return True


def auto_login(account, status):
    utils.window_utils.close_windows_by_class(["WTWindow", "WeChatLoginWndForPC"])
    creator = ConfigCreator(account)
    result = creator.use_config()
    if result:
        print("复制配置文件成功")
    else:
        return False
    wechat_hwnd = open_wechat(status)
    if wechat_hwnd:
        print(f"打开了登录窗口{wechat_hwnd}")
        wechat_wnd_details = utils.window_utils.get_window_details_from_hwnd(wechat_hwnd)
        wechat_wnd = wechat_wnd_details["window"]
        wechat_width = wechat_wnd_details["width"]
        wechat_height = wechat_wnd_details["height"]
        end_time = time.time() + 60
        while True:
            doClick(wechat_hwnd, int(wechat_width * 0.5), int(wechat_height * 0.75))
            print("点击了按钮")
            time.sleep(0.2)
            if win32gui.IsWindow(wechat_hwnd) == 0:
                print("登录窗口已关闭")
                return True
            elif time.time() > end_time:
                print("登录超时")
                return False
    return False


def auto_login_accounts(accounts, status, max_gap_width=30):
    def get_wnd_position(n):
        # 实际的间隔设置
        actual_gap_width = int((screen_width - n * login_width) / (n + 1))
        # 去除两边间隔总共的宽度
        all_login_width = int(n * login_width + (n - 1) * actual_gap_width)
        # 计算起始位置x，y
        x = int((screen_width - all_login_width) / 2)
        y = int((screen_height - login_height) / 2) - 25
        # 计算每个窗口的位置
        for i in range(n):
            positions.append((x + i * (login_width + actual_gap_width), y))
        print(positions)

    login_width = 347
    login_height = 471

    # 检测尺寸设置是否完整
    login_size = func_setting.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY_LOGIN_SIZE
    )
    if not login_size or login_size == "":


        return False
    else:
        login_width, login_height = login_size.split('*')
    login_width = int(login_width)
    login_height = int(login_height)
    wechat_path = func_setting.get_wechat_install_path()
    data_path = func_setting.get_wechat_data_path()
    # wechat_window.moveTo(100, 100)
    if len(accounts) == 0:
        return False
    count = len(accounts)

    # 优先自动获取尺寸，若获取不到从配置中获取
    screen_width = tk.Tk().winfo_screenwidth()
    screen_height = tk.Tk().winfo_screenheight()
    if not screen_height or not screen_width:
        screen_width, screen_height = func_setting.get_setting_from_ini(
            Config.SETTING_INI_PATH,
            Config.INI_SECTION,
            Config.INI_KEY_SCREEN_SIZE
        ).split('*')
    screen_width = int(screen_width)
    screen_height = int(screen_height)


    # 计算一行最多可以显示多少个
    max_column = int((screen_width - max_gap_width) / (login_width + max_gap_width))

    # 存放登录窗口的起始位置的列表
    positions = []

    if count > max_column:
        print("不能一行显示")
        get_wnd_position(max_column)
    else:
        print("可以一行显示")
        get_wnd_position(count)

    start_time = time.time()

    for j in range(count):
        source_file = os.path.join(data_path, "All Users", "config", f"{accounts[j]}.data")
        target_file = os.path.join(data_path, "All Users", "config", "config.data")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        try:
            shutil.copy2(source_file, target_file)
        except Exception as e:
            print(f"复制配置文件失败: {e}")
            return False
        print(f"复制配置文件成功，时间：{time.time() - start_time:.4f}秒")

        if status == "已开启":
            subprocess.Popen(wechat_path)
        else:
            multi_wechat_process = subprocess.Popen(Config.MULTI_SUBPROCESS, creationflags=subprocess.CREATE_NO_WINDOW)
        print(f"执行唤起登录窗口，时间：{time.time() - start_time:.4f}秒")
        time.sleep(3)
        wechat_window = pyautogui.getInfo("微信")[0]
        # pyautogui.press('space')
        # 横坐标算出完美的平均位置
        new_left = positions[j % max_column][0]
        # 纵坐标由居中位置稍向上偏移，然后每轮完一行，位置向下移动一个登录窗口宽度的距离
        new_top = positions[j % max_column][1] + int(j / max_column) * login_width - int(login_width / 2)
        print(new_left, new_top)
        wechat_window.moveTo(new_left, new_top)


if __name__ == '__main__':
    auto_login_accounts([1, 2, 3, 4], "已开启")
