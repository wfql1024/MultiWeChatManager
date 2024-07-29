# func_login.py
import os
import shutil
import subprocess
import time
import pyautogui
import win32gui

import get_path_of_data

def wait_for_window(class_name, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        window = win32gui.FindWindow(class_name, None)
        if window != 0:
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

def manual_login():
    multi_wechat_process = subprocess.Popen("multiWechat.exe")
    if wait_for_window("WTWindow", timeout=3):
        time.sleep(2)
        pyautogui.press('space')
        if wait_for_window("WeChatLoginWndForPC", timeout=3):
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
    data_path = get_path_of_data.get_wechat_data_path()
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
    multi_wechat_process = subprocess.Popen("multiWechat.exe")
    if wait_for_window("WTWindow", timeout=3):
        time.sleep(2)
        pyautogui.press('space')
        if wait_for_window("WeChatLoginWndForPC", timeout=3):
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