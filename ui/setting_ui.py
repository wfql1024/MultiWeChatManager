import re
import time
import tkinter as tk
from functools import partial
from tkinter import ttk, filedialog, messagebox

import win32com
import win32com.client

from functions import func_setting
from resources.config import Config
from utils import handle_utils, wechat_utils


class SettingWindow:
    def __init__(self, master, status, on_close_callback=None):
        self.status = status
        self.master = master
        self.on_close_callback = on_close_callback
        master.title("应用设置")

        window_width = 750
        window_height = 240  # 增加窗口高度以适应新的行
        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        master.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # 移除窗口装饰并设置为工具窗口
        master.overrideredirect(True)
        master.overrideredirect(False)
        master.attributes('-toolwindow', True)

        master.grab_set()

        # 第一行 - 微信安装路径
        self.install_label = tk.Label(master, text="微信程序路径：")
        self.install_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.install_path_var = tk.StringVar()
        self.install_path_entry = tk.Entry(master, textvariable=self.install_path_var, state='readonly', width=70)
        self.install_path_entry.grid(row=0, column=1, padx=5, pady=5, sticky="we")

        self.install_get_button = ttk.Button(master, text="获取", command=self.auto_get_wechat_install_path)
        self.install_get_button.grid(row=0, column=2, padx=5, pady=5)

        self.install_choose_button = ttk.Button(master, text="选择路径", command=self.choose_wechat_install_path)
        self.install_choose_button.grid(row=0, column=3, padx=5, pady=5)

        # 第二行 - 微信数据存储路径
        self.data_label = tk.Label(master, text="数据存储路径：")
        self.data_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        self.data_path_var = tk.StringVar()
        self.data_path_entry = tk.Entry(master, textvariable=self.data_path_var, state='readonly', width=70)
        self.data_path_entry.grid(row=1, column=1, padx=5, pady=5, sticky="we")

        self.data_get_button = ttk.Button(master, text="获取", command=self.auto_get_wechat_data_path)
        self.data_get_button.grid(row=1, column=2, padx=5, pady=5)

        self.data_choose_button = ttk.Button(master, text="选择路径", command=self.choose_wechat_data_path)
        self.data_choose_button.grid(row=1, column=3, padx=5, pady=5)

        # 新增第三行 - WeChatWin.dll 路径
        self.dll_label = tk.Label(master, text="最新版本路径：")
        self.dll_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")

        self.dll_path_var = tk.StringVar()
        self.dll_path_entry = tk.Entry(master, textvariable=self.dll_path_var, state='readonly', width=70)
        self.dll_path_entry.grid(row=2, column=1, padx=5, pady=5, sticky="we")

        self.dll_get_button = ttk.Button(master, text="获取", command=self.auto_get_wechat_latest_version_path)
        self.dll_get_button.grid(row=2, column=2, padx=5, pady=5)

        self.dll_choose_button = ttk.Button(master, text="选择路径", command=self.choose_wechat_latest_version_path)
        self.dll_choose_button.grid(row=2, column=3, padx=5, pady=5)

        # 新增第四行 - 屏幕大小
        self.screen_size_label = tk.Label(master, text="屏幕大小：")
        self.screen_size_label.grid(row=3, column=0, padx=5, pady=5, sticky="w")

        self.screen_size_var = tk.StringVar()
        self.screen_size_entry = tk.Entry(master, textvariable=self.screen_size_var, state='readonly', width=70)
        self.screen_size_entry.grid(row=3, column=1, padx=5, pady=5, sticky="we")

        self.screen_size_get_button = ttk.Button(master, text="获取", command=self.auto_get_screen_size)
        self.screen_size_get_button.grid(row=3, column=2, padx=5, pady=5)

        # 新增第四行 - 登录窗口大小
        self.login_size_label = tk.Label(master, text="登录窗口大小：")
        self.login_size_label.grid(row=4, column=0, padx=5, pady=5, sticky="w")

        self.login_size_var = tk.StringVar()
        self.login_size_entry = tk.Entry(master, textvariable=self.login_size_var, width=70)
        self.login_size_entry.grid(row=4, column=1, padx=5, pady=5, sticky="we")

        self.login_size_get_button = ttk.Button(master, text="获取",
                                                command=partial(self.auto_get_login_size, self.status))
        self.login_size_get_button.grid(row=4, column=2, padx=5, pady=5)

        # 添加确定按钮
        self.ok_button = ttk.Button(master, text="确定", command=self.on_ok)
        self.ok_button.grid(row=3, column=3, rowspan=2, padx=5, pady=5, sticky="nsew")

        # 配置列的权重，使得中间的 Entry 可以自动扩展
        master.grid_columnconfigure(1, weight=1)

        # 初始获取路径
        self.auto_get_wechat_install_path()
        self.auto_get_wechat_data_path()
        self.auto_get_wechat_latest_version_path()
        self.auto_get_screen_size()

        login_size = func_setting.get_setting_from_ini(
            Config.SETTING_INI_PATH,
            Config.INI_SECTION,
            Config.INI_KEY_LOGIN_SIZE,
        )

        self.login_size_var.set(login_size)

    def on_ok(self):
        if self.validate_paths():
            if self.on_close_callback:
                self.on_close_callback()
            self.master.destroy()

    def validate_paths(self):
        install_path = self.install_path_var.get()
        data_path = self.data_path_var.get()
        dll_path = self.dll_path_var.get()

        if "获取失败" in install_path or "获取失败" in data_path or "获取失败" in dll_path:
            messagebox.showerror("错误", "请确保所有路径都已正确设置")
            return False
        elif not bool(re.match(r'^\d+\*\d+$', self.login_size_var.get())):
            messagebox.showerror("错误", f"请确保填入的尺寸符合\"整数*整数\"的形式")
            return False
        func_setting.save_setting_to_ini(
            Config.SETTING_INI_PATH,
            Config.INI_SECTION,
            Config.INI_KEY_LOGIN_SIZE,
            f"{self.login_size_var.get()}"
        )
        return True

    def auto_get_wechat_latest_version_path(self):
        path = func_setting.get_wechat_latest_version_path()
        if path:
            self.dll_path_var.set(path.replace('\\', '/'))
        else:
            self.dll_path_var.set("获取失败，请手动选择安装目录下最新版本号文件夹")

    def choose_wechat_latest_version_path(self):
        while True:
            try:
                # 尝试使用 `filedialog.askdirectory` 方法
                path = filedialog.askdirectory()
                if not path:  # 用户取消选择
                    return
            except Exception as e:
                print(f"filedialog.askdirectory 失败，尝试使用 win32com.client: {e}")
                try:
                    # 异常处理部分，使用 `win32com.client`
                    shell = win32com.client.Dispatch("Shell.Application")
                    folder = shell.BrowseForFolder(0, "Select Folder", 0, 0)
                    if not folder:  # 用户取消选择
                        return
                    path = folder.Self.Path.replace('\\', '/')
                except Exception as e:
                    print(f"win32com.client 也失败了: {e}")
                    return
            if func_setting.is_valid_wechat_latest_version_path(path):
                self.dll_path_var.set(path)
                func_setting.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                                 Config.INI_KEY_VER_PATH, path)
                break
            else:
                messagebox.showerror("错误", "请选择包含WeChatWin.dll的版本号最新的文件夹")

    def auto_get_wechat_install_path(self):
        path = func_setting.get_wechat_install_path()
        if path:
            self.install_path_var.set(path.replace('\\', '/'))
        else:
            self.install_path_var.set("获取失败，请登录微信后获取或手动选择路径")

    def choose_wechat_install_path(self):
        while True:
            path = filedialog.askopenfilename(filetypes=[("Executable files", "*.exe"), ("All files", "*.*")])
            if not path:  # 用户取消选择
                return
            path = path.replace('\\', '/')
            if func_setting.is_valid_wechat_install_path(path):
                self.install_path_var.set(path)
                func_setting.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                                 Config.INI_KEY_INSTALL_PATH, path)
                break
            else:
                messagebox.showerror("错误", "请选择WeChat.exe文件")

    def auto_get_wechat_data_path(self):
        path = func_setting.get_wechat_data_path()
        if path:
            self.data_path_var.set(path.replace('\\', '/'))
        else:
            self.data_path_var.set("获取失败，请手动选择包含All Users文件夹的父文件夹（通常为Wechat Files）")

    def choose_wechat_data_path(self):
        while True:
            try:
                # 尝试使用 `filedialog.askdirectory` 方法
                path = filedialog.askdirectory()
                if not path:  # 用户取消选择
                    return
            except Exception as e:
                print(f"filedialog.askdirectory 失败，尝试使用 win32com.client: {e}")
                try:
                    # 异常处理部分，使用 `win32com.client`
                    shell = win32com.client.Dispatch("Shell.Application")
                    folder = shell.BrowseForFolder(0, "Select Folder", 0, 0)
                    if not folder:  # 用户取消选择
                        return
                    path = folder.Self.Path.replace('\\', '/')
                except Exception as e:
                    print(f"win32com.client 也失败了: {e}")
                    return
            if func_setting.is_valid_wechat_data_path(path):
                self.data_path_var.set(path)
                func_setting.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                                 Config.INI_KEY_DATA_PATH, path)
                break
            else:
                messagebox.showerror("错误", "该路径不是有效的存储路径，可以在微信设置中查看存储路径")

    def auto_get_screen_size(self):
        # 获取屏幕和登录窗口尺寸
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        self.screen_size_var.set(f"{screen_width}*{screen_height}")
        func_setting.save_setting_to_ini(
            Config.SETTING_INI_PATH,
            Config.INI_SECTION,
            Config.INI_KEY_SCREEN_SIZE,
            f"{screen_width}*{screen_height}"
        )

    def auto_get_login_size(self, status):
        wechat_utils.clear_idle_wnd_and_process()
        wechat_hwnd = wechat_utils.open_wechat(status)
        if wechat_hwnd:
            print(f"打开了登录窗口{wechat_hwnd}")
            time.sleep(2)
            login_wnd_details = handle_utils.get_window_details_from_hwnd(wechat_hwnd)
            login_wnd = login_wnd_details["window"]
            login_width = login_wnd_details["width"]
            login_height = login_wnd_details["height"]
            print(login_width, login_height)
            if 0.734 < login_width / login_height < 0.740:
                func_setting.save_setting_to_ini(
                    Config.SETTING_INI_PATH,
                    Config.INI_SECTION,
                    Config.INI_KEY_LOGIN_SIZE,
                    f"{login_width}*{login_height}",
                )
                self.login_size_var.set(f"{login_width}*{login_height}")
            login_wnd.close()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # 隐藏根窗口
    filedialog.askopenfilename(filetypes=[("Executable files", "*.exe"), ("All files", "*.*")])
