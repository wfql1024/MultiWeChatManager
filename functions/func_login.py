# func_login.py
import os
import shutil
import subprocess
import time

import pyautogui

from functions import func_path
from functions.func_path import is_valid_wechat_install_path, is_valid_wechat_data_path
from utils.window_utils import wait_for_window_open, wait_for_window_close
from resources.config import Config


def manual_login(status):
    wechat_path = func_path.get_wechat_install_path()
    if status == "已开启":
        subprocess.Popen(wechat_path)
        if wait_for_window_open("WeChatLoginWndForPC", timeout=3):
            print("登录窗口已打开")
            if wait_for_window_close("WeChatLoginWndForPC", timeout=60):
                print("登录窗口已关闭")
                return True
        else:
            print("打开失败，请重试！")
            return False
    else:
        multi_wechat_process = subprocess.Popen("./multiWechat.exe")
        if wait_for_window_open("WTWindow", timeout=3):
            time.sleep(2)
            pyautogui.press('space')
            if wait_for_window_open("WeChatLoginWndForPC", timeout=3):
                print("打开了登录窗口")
                # 等待登录窗口关闭
                if wait_for_window_close("WeChatLoginWndForPC", timeout=60):
                    print("登录窗口已关闭")
                    multi_wechat_process.terminate()
                    return True
                else:
                    print("登录超时")
                    multi_wechat_process.terminate()
                    return False
        multi_wechat_process.terminate()
        return False


def auto_login(account):
    # 获取数据路径
    data_path = func_path.get_path_from_ini(Config.PATH_INI_PATH, Config.INI_SECTION, Config.INI_KEY_DATA_PATH, is_valid_wechat_data_path)
    wechat_path = func_path.get_path_from_ini(Config.PATH_INI_PATH, Config.INI_SECTION, Config.INI_KEY_INSTALL_PATH, is_valid_wechat_install_path)
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
    multi_wechat_process = subprocess.Popen("./multiWechat.exe")
    if wait_for_window_open("WTWindow", timeout=3):
        time.sleep(2)
        pyautogui.press('space')
        if wait_for_window_open("WeChatLoginWndForPC", timeout=3):
            print("打开了登录窗口")
            time.sleep(2)
            pyautogui.press('space')

            # 等待登录窗口关闭
            if wait_for_window_close("WeChatLoginWndForPC", timeout=60):
                print("登录窗口已关闭")
                multi_wechat_process.terminate()
                return True
            else:
                print("登录超时")
                multi_wechat_process.terminate()
                return False

    multi_wechat_process.terminate()
    return False
