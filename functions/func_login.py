# func_login.py
import os
import shutil
import subprocess
import time

import pyautogui

from functions import func_setting
from functions.func_setting import is_valid_wechat_install_path, is_valid_wechat_data_path
from resources.config import Config
from utils.window_utils import wait_for_window_open, wait_for_window_close


def manual_login(status):
    wechat_path = func_setting.get_wechat_install_path()
    if status == "已开启":
        subprocess.Popen(wechat_path, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        multi_wechat_process = subprocess.Popen(Config.MULTI_SUBPROCESS, creationflags=subprocess.CREATE_NO_WINDOW)
    # 等待窗口打开
    time.sleep(2)
    wechat_window = pyautogui.getWindowsWithTitle("微信")[0]
    (width, height) = wechat_window.size
    wechat_window.moveTo(100, 100)
    print(f"窗口宽度: {width}, 窗口高度: {height}")
    if wait_for_window_open("WeChatLoginWndForPC", timeout=3):
        print("登录窗口已打开")
        if wait_for_window_close("WeChatLoginWndForPC", timeout=60):
            print("登录窗口已关闭")
            return True
    else:
        print("打开失败，请重试！")
        return False
    return True


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

    wechat_path = func_setting.get_wechat_install_path()
    data_path = func_setting.get_wechat_data_path()
    # wechat_window.moveTo(100, 100)
    if len(accounts) == 0:
        return False
    # if len(accounts) == 1:
    #     auto_login(accounts[0], status)
    count = len(accounts)

    screen_width, screen_height = func_setting.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY_SCREEN_SIZE
    ).split('*')
    screen_width = int(screen_width)
    screen_height = int(screen_height)
    login_width, login_height = func_setting.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY_LOGIN_SIZE
    ).split('*')
    login_width = int(login_width)
    login_height = int(login_height)
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

    for j in range(count):
        source_file = os.path.join(data_path, "All Users", "config", f"{accounts[j]}.data")
        target_file = os.path.join(data_path, "All Users", "config", "config.data")
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
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
        time.sleep(2.7)
        wechat_window = pyautogui.getWindowsWithTitle("微信")[0]
        pyautogui.press('space')
        wechat_window.moveTo(positions[j][0], positions[j][1])


if __name__ == '__main__':
    auto_login_accounts([1, 2, 3, 4], "已开启")
