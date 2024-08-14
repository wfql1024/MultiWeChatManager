import os
import shutil
import subprocess
import time
from tkinter import messagebox

import pyautogui

from functions import func_path
from utils.window_utils import wait_for_window_open, close_window


def test_and_create_config(account):
    creator = ConfigCreator(account)
    return creator.test()


class ConfigCreator:
    def __init__(self, account):
        self.account = account

    def test(self):
        if messagebox.askyesno(
                "确认",
                "建议在只登录了一个账号时，或刚刚登录了此账号时进行配置，\n成功率更高。将唤起登录窗口，请勿重复登录。是否继续？"
        ):
            multi_wechat_process = subprocess.Popen("./multiWechat.exe")
            if not wait_for_window_open("WTWindow"):
                messagebox.showerror("错误", "未检测到多开器窗口")
                return False

            time.sleep(2)
            pyautogui.press('space')

            if not wait_for_window_open("WeChatLoginWndForPC"):
                messagebox.showerror("错误", "未检测到微信登录界面")
                multi_wechat_process.terminate()
                return False

            time.sleep(3)
            multi_wechat_process.terminate()

            if messagebox.askyesno("确认", "是否为对应的微信号？"):
                return self.create_config()
            else:
                close_window("WeChatLoginWndForPC")
                return False
        return False

    def create_config(self):
        data_path = func_path.get_wechat_data_path()
        if not data_path:
            messagebox.showerror("错误", "无法获取WeChat数据路径")
            return False

        source_path = os.path.join(data_path, 'All Users', 'config', 'config.data')

        dest_filename = f"{self.account}.data"
        dest_path = os.path.join(data_path, 'All Users', 'config', dest_filename)

        try:
            if os.path.exists(dest_path):
                print("到这了")
                os.remove(dest_path)

            shutil.copy2(source_path, dest_path, follow_symlinks=False)
            close_window("WeChatLoginWndForPC")

            messagebox.showinfo("成功", f"配置文件已生成：{dest_filename}")

            return True

        except Exception as e:
            messagebox.showerror("错误", f"生成配置文件时发生错误：{str(e)}")
            return False
