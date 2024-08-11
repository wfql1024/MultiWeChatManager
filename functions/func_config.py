import os
import shutil
import subprocess
import time
from tkinter import messagebox

import pyautogui
import win32con
import win32gui

from functions import func_get_path


class ConfigCreator:
    def __init__(self, account, save_callback):
        self.account = account
        self.save_callback = save_callback

    def create_and_test(self):
        if self.show_confirm_dialog():
            return self.run_test()
        return False

    def show_confirm_dialog(self):
        result = messagebox.askyesno(
            "确认",
            "建议在只登录了一个账号时，或刚刚登录了此账号时进行配置，\n成功率更高。将唤起登录窗口，请勿重复登录。是否继续？"
        )
        return result

    def run_test(self):
        multi_wechat_process = subprocess.Popen("./multiWechat.exe")
        if not self.wait_for_window("WTWindow"):
            messagebox.showerror("错误", "未检测到多开器窗口")
            return False

        time.sleep(2)
        pyautogui.press('space')

        if not self.wait_for_window("WeChatLoginWndForPC"):
            messagebox.showerror("错误", "未检测到微信登录界面")
            multi_wechat_process.terminate()
            return False

        time.sleep(3)
        multi_wechat_process.terminate()

        if messagebox.askyesno("确认", "是否为对应的微信号？"):
            return self.create_config()
        else:
            self.close_wechat_login_window()
            return False

    def wait_for_window(self, class_name, timeout=30):
        end_time = time.time() + timeout
        while time.time() < end_time:
            if win32gui.FindWindow(class_name, None):
                return True
            time.sleep(0.5)
        return False

    def create_config(self):
        dtpath = func_get_path.get_wechat_data_path()
        if not dtpath:
            messagebox.showerror("错误", "无法获取WeChat数据路径")
            return False

        source_path = os.path.join(dtpath, 'All Users', 'config', 'config.data')

        dest_filename = f"{self.account}.data"
        dest_path = os.path.join(dtpath, 'All Users', 'config', dest_filename)

        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)

            shutil.copy2(source_path, dest_path, follow_symlinks=False)
            self.save_callback()

            messagebox.showinfo("成功", f"配置文件已生成：{dest_filename}")
            self.close_wechat_login_window()
            return True

        except Exception as e:
            messagebox.showerror("错误", f"生成配置文件时发生错误：{str(e)}")
            return False

    def close_wechat_login_window(self):
        login_window = win32gui.FindWindow("WeChatLoginWndForPC", None)
        if login_window:
            win32gui.PostMessage(login_window, win32con.WM_CLOSE, 0, 0)


def create_and_test_config(account, save_callback):
    creator = ConfigCreator(account, save_callback)
    return creator.create_and_test()
