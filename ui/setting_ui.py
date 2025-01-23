import re
import tkinter as tk
from functools import partial
from tkinter import ttk, filedialog, messagebox
from typing import Dict

import win32com
import win32com.client

from functions import func_setting, subfunc_sw, subfunc_file, func_sw_dll
from resources import Constants, Config
from utils import sw_utils, hwnd_utils, ini_utils
from utils.logger_utils import mylogger as logger


# TODO:修改下获取程序路径，程序版本以及程序版本文件夹的逻辑


class SettingWindow:
    def __init__(self, wnd, sw, status, after):
        self.changed: Dict[str, bool] = {
            "inst_path": False,
            "data_dir": False,
            "dll_dir": False,
            "login_size": False
        }
        self.origin_values = {
            "inst_path": ini_utils.get_setting_from_ini(Config.SETTING_INI_PATH, sw, "inst_path"),
            "data_dir": ini_utils.get_setting_from_ini(Config.SETTING_INI_PATH, sw, "data_dir"),
            "dll_dir": ini_utils.get_setting_from_ini(Config.SETTING_INI_PATH, sw, "dll_dir"),
            "login_size": ini_utils.get_setting_from_ini(Config.SETTING_INI_PATH, sw, "login_size")
        }
        self.ver = None
        self.inst_path = None
        self.data_dir = None
        self.dll_dir = None

        self.status = status
        self.after = after
        self.wnd = wnd
        self.sw = sw
        self.need_to_clear_acc = False

        wnd.title(f"{sw}设置")
        window_width, window_height = Constants.SETTING_WND_SIZE
        hwnd_utils.bring_tk_wnd_to_center(self.wnd, window_width, window_height)
        # 移除窗口装饰并设置为工具窗口
        wnd.attributes('-toolwindow', True)
        wnd.grab_set()
        self.wnd.protocol("WM_DELETE_WINDOW", self.on_close)

        # 第一行 - 微信安装路径
        self.install_label = tk.Label(wnd, text="程序路径：")
        self.install_label.grid(row=0, column=0, **Constants.W_GRID_PACK)

        self.inst_path_var = tk.StringVar()
        self.install_path_entry = tk.Entry(wnd, textvariable=self.inst_path_var, state='readonly', width=70)
        self.install_path_entry.grid(row=0, column=1, **Constants.WE_GRID_PACK)

        self.install_get_button = ttk.Button(wnd, text="获取",
                                             command=partial(self.load_or_get_sw_inst_path, self.sw, True))
        self.install_get_button.grid(row=0, column=2, **Constants.WE_GRID_PACK)

        self.install_choose_button = ttk.Button(wnd, text="选择路径",
                                                command=partial(self.choose_sw_inst_path, self.sw))
        self.install_choose_button.grid(row=0, column=3, **Constants.WE_GRID_PACK)

        # 第二行 - 微信数据存储路径
        self.data_label = tk.Label(wnd, text="存储路径：")
        self.data_label.grid(row=1, column=0, **Constants.W_GRID_PACK)

        self.data_dir_var = tk.StringVar()
        self.data_path_entry = tk.Entry(wnd, textvariable=self.data_dir_var, state='readonly', width=70)
        self.data_path_entry.grid(row=1, column=1, **Constants.WE_GRID_PACK)

        self.data_get_button = ttk.Button(wnd, text="获取",
                                          command=partial(self.load_or_get_sw_data_dir, self.sw, True))
        self.data_get_button.grid(row=1, column=2, **Constants.WE_GRID_PACK)

        self.data_choose_button = ttk.Button(wnd, text="选择路径",
                                             command=partial(self.choose_sw_data_dir, self.sw))
        self.data_choose_button.grid(row=1, column=3, **Constants.WE_GRID_PACK)

        # 新增第三行 - WeChatWin.dll 路径
        self.dll_label = tk.Label(wnd, text="DLL所在路径：")
        self.dll_label.grid(row=2, column=0, **Constants.W_GRID_PACK)

        self.dll_dir_var = tk.StringVar()
        self.dll_path_entry = tk.Entry(wnd, textvariable=self.dll_dir_var, state='readonly', width=70)
        self.dll_path_entry.grid(row=2, column=1, **Constants.WE_GRID_PACK)

        self.dll_get_button = ttk.Button(wnd, text="获取",
                                         command=partial(self.load_or_get_sw_dll_dir, self.sw, True))
        self.dll_get_button.grid(row=2, column=2, **Constants.WE_GRID_PACK)

        self.dll_choose_button = ttk.Button(wnd, text="选择路径",
                                            command=partial(self.choose_sw_dll_dir, self.sw))
        self.dll_choose_button.grid(row=2, column=3, **Constants.WE_GRID_PACK)

        # 新增第四行 - 当前版本
        self.version_label = tk.Label(wnd, text="应用版本：")
        self.version_label.grid(row=3, column=0, **Constants.W_GRID_PACK)

        self.version_var = tk.StringVar()
        self.version_entry = tk.Entry(wnd, textvariable=self.version_var, state='readonly', width=70)
        self.version_entry.grid(row=3, column=1, **Constants.WE_GRID_PACK)

        self.screen_size_get_button = ttk.Button(wnd, text="获取",
                                                 command=partial(self.get_cur_sw_ver, self.sw))
        self.screen_size_get_button.grid(row=3, column=2, **Constants.WE_GRID_PACK)

        # 新增第五行 - 屏幕大小
        self.screen_size_label = tk.Label(wnd, text="屏幕大小：")
        self.screen_size_label.grid(row=4, column=0, **Constants.W_GRID_PACK)

        self.screen_size_var = tk.StringVar()
        self.screen_size_entry = tk.Entry(wnd, textvariable=self.screen_size_var, state='readonly', width=70)
        self.screen_size_entry.grid(row=4, column=1, **Constants.WE_GRID_PACK)

        self.screen_size_get_button = ttk.Button(wnd, text="获取", command=self.get_screen_size)
        self.screen_size_get_button.grid(row=4, column=2, **Constants.WE_GRID_PACK)

        # 新增第六行 - 登录窗口大小
        self.login_size_label = tk.Label(wnd, text="登录尺寸：")
        self.login_size_label.grid(row=5, column=0, **Constants.W_GRID_PACK)

        self.login_size_var = tk.StringVar()
        self.login_size_entry = tk.Entry(wnd, textvariable=self.login_size_var, state='readonly', width=70)
        self.login_size_entry.grid(row=5, column=1, **Constants.WE_GRID_PACK)

        self.login_size_get_button = ttk.Button(wnd, text="获取",
                                                command=partial(self.to_get_login_size, self.status))
        self.login_size_get_button.grid(row=5, column=2, **Constants.WE_GRID_PACK)

        # 修改确定按钮，从第4行到第6行
        self.ok_button = ttk.Button(wnd, text="确定", command=self.on_ok)
        self.ok_button.grid(row=3, column=3, rowspan=3, **Constants.NEWS_GRID_PACK)

        # 配置列的权重，使得中间的 Entry 可以自动扩展
        wnd.grid_columnconfigure(1, weight=1)

        # 初始加载已经配置的，或是没有配置的话自动获取
        self.load_or_get_sw_inst_path(self.sw, False)
        self.load_or_get_sw_data_dir(self.sw, False)
        self.load_or_get_sw_dll_dir(self.sw, False)
        self.get_cur_sw_ver(self.sw, False)
        self.get_screen_size()
        login_size = subfunc_file.fetch_sw_setting_or_set_default(self.sw, 'login_size')
        self.login_size_var.set(login_size)

    def check_bools(self):
        keys_to_check = ["data_dir"]
        self.need_to_clear_acc = any(self.changed[key] for key in keys_to_check)

    def on_ok(self):
        self.check_bools()
        if self.validate_paths():
            # 检查是否需要清空账号信息
            if self.need_to_clear_acc:
                subfunc_file.clear_acc_info_of_sw(self.sw)
            self.after()
            self.wnd.destroy()

    def on_close(self):
        self.check_bools()
        if self.need_to_clear_acc:
            subfunc_file.clear_acc_info_of_sw(self.sw)
        self.after()
        self.wnd.destroy()

    def validate_paths(self):
        self.inst_path = self.inst_path_var.get()
        self.data_dir = self.data_dir_var.get()
        self.dll_dir = self.dll_dir_var.get()

        if "获取失败" in self.inst_path or "获取失败" in self.data_dir or "获取失败" in self.dll_dir:
            messagebox.showerror("错误", "请确保所有路径都已正确设置")
            return False
        elif not bool(re.match(r'^\d+\*\d+$', self.login_size_var.get())):
            messagebox.showerror("错误", f"请确保填入的尺寸符合\"整数*整数\"的形式")
            return False
        return True

    def load_or_get_sw_inst_path(self, sw, click=False):
        """获取路径，若成功会进行保存"""
        path = func_setting.get_sw_install_path(sw, click)  # 此函数会保存路径
        if path:
            self.inst_path_var.set(path.replace('\\', '/'))
            self.inst_path = path
            if self.inst_path != self.origin_values["inst_path"]:
                self.changed["inst_path"] = True
        else:
            self.inst_path_var.set("获取失败，请登录微信后获取或手动选择路径")

    def choose_sw_inst_path(self, sw):
        """选择路径，若检验成功会进行保存"""
        while True:
            path = filedialog.askopenfilename(filetypes=[("Executable files", "*.exe"), ("All files", "*.*")])
            if not path:  # 用户取消选择
                return
            path = path.replace('\\', '/')
            if sw_utils.is_valid_sw_install_path(sw, path):
                self.inst_path_var.set(path)
                self.inst_path = path
                subfunc_file.save_sw_setting(self.sw, 'inst_path', self.inst_path)
                if self.inst_path != self.origin_values["inst_path"]:
                    self.changed["inst_path"] = True
                break
            else:
                messagebox.showerror("错误", "请选择WeChat.exe文件")

    def load_or_get_sw_data_dir(self, sw, click=False):
        """获取路径，若成功会进行保存"""
        path = func_setting.get_sw_data_dir(sw, click)  # 此函数会保存路径
        if path:
            self.data_dir_var.set(path.replace('\\', '/'))
            self.data_dir = path
            if self.data_dir != self.origin_values["data_dir"]:
                self.changed["data_dir"] = True
        else:
            self.data_dir_var.set("获取失败，请手动选择包含All Users文件夹的父文件夹（通常为Wechat Files）")

    def choose_sw_data_dir(self, sw):
        """选择路径，若检验成功会进行保存"""
        while True:
            try:
                # 尝试使用 `filedialog.askdirectory` 方法
                path = filedialog.askdirectory()
                if not path:  # 用户取消选择
                    return
            except Exception as e:
                logger.error(f"filedialog.askdirectory 失败，尝试使用 win32com.client: {e}")
                try:
                    # 异常处理部分，使用 `win32com.client`
                    shell = win32com.client.Dispatch("Shell.Application")
                    folder = shell.BrowseForFolder(0, "Select Folder", 0, 0)
                    if not folder:  # 用户取消选择
                        return
                    path = folder.Self.Path.replace('\\', '/')
                except Exception as e:
                    logger.error(f"win32com.client 也失败了: {e}")
                    return
            if sw_utils.is_valid_sw_data_dir(sw, path):
                self.data_dir_var.set(path)
                self.data_dir = path
                subfunc_file.save_sw_setting(self.sw, 'data_dir', self.data_dir)
                if self.data_dir != self.origin_values["data_dir"]:
                    self.changed["data_dir"] = True
                break
            else:
                messagebox.showerror("错误", "该路径不是有效的存储路径，可以在微信设置中查看存储路径")

    def load_or_get_sw_dll_dir(self, sw, click=False):
        """获取路径，若成功会进行保存"""
        path = func_setting.get_sw_dll_dir(sw, click)  # 此函数会保存路径
        if path:
            self.dll_dir_var.set(path.replace('\\', '/'))
            self.dll_dir = path
            if self.dll_dir != self.origin_values["dll_dir"]:
                self.changed["dll_dir"] = True
        else:
            self.dll_dir_var.set("获取失败，请手动选择安装目录下最新版本号文件夹")

    def choose_sw_dll_dir(self, sw):
        """选择路径，若检验成功会进行保存"""
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
            if sw_utils.is_valid_sw_dll_dir(sw, path):
                self.dll_dir_var.set(path)
                self.dll_dir = path
                subfunc_file.save_sw_setting(self.sw, 'dll_dir', self.dll_dir)
                if self.dll_dir != self.origin_values["dll_dir"]:
                    self.changed["dll_dir"] = True
                break
            else:
                messagebox.showerror("错误", "请选择包含WeChatWin.dll的版本号最新的文件夹")

    def get_cur_sw_ver(self, sw, click):
        print("获取版本号")
        _, version = func_setting.get_sw_inst_path_and_ver(sw, click)
        if version is not None:
            self.version_var.set(version)
            self.ver = version

    def get_screen_size(self):
        # 获取屏幕和登录窗口尺寸
        screen_width = self.wnd.winfo_screenwidth()
        screen_height = self.wnd.winfo_screenheight()
        self.screen_size_var.set(f"{screen_width}*{screen_height}")
        subfunc_file.save_global_setting('screen_size', f"{screen_width}*{screen_height}")

    def to_get_login_size(self, status):
        if status is None:
            status, _, _ = func_sw_dll.check_dll(self.sw, "multiple", self.dll_dir)
        result = subfunc_sw.get_login_size(self.sw, status)
        if result:
            login_width, login_height = result
            if 0.734 < login_width / login_height < 0.740:
                subfunc_file.save_sw_setting(self.sw, 'login_size', f"{login_width}*{login_height}")
                self.login_size_var.set(f"{login_width}*{login_height}")
            else:
                self.login_size_var.set(f"350*475")


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # 隐藏根窗口
    filedialog.askopenfilename(filetypes=[("Executable files", "*.exe"), ("All files", "*.*")])
