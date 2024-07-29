import func_about
import func_config
import get_path_of_wechat
import func_path_setting
from func_login import auto_login, manual_login
from func_account_list import AccountManager
from ui_helper import UIHelper
import get_path_of_data
from thread_manager import ThreadManager
import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox


def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def ensure_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def init_app_structure():
    app_dir = get_app_dir()

    # 初始化 account_data.json
    account_data_path = os.path.join(app_dir, "account_data.json")
    if not os.path.exists(account_data_path):
        with open(account_data_path, 'w') as f:
            json.dump({}, f)


def get_account_data_path():
    return os.path.join(get_app_dir(), "account_data.json")


def get_path_ini_path():
    return os.path.join(get_app_dir(), "path.ini")


def get_config_dir():
    data_path = get_path_of_data.get_wechat_data_path()
    if data_path:
        return os.path.join(data_path, "All Users", "config")
    return None  # 或者可以返回一个默认路径，或者抛出一个异常


class LoadingWindow:
    def __init__(self, master):
        self.master = master
        self.window = tk.Toplevel(master)
        self.window.withdraw()  # 初始时隐藏窗口
        self.window.title("加载中")

        window_width = 300
        window_height = 100

        # 计算窗口位置
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.window.resizable(False, False)

        self.label = ttk.Label(self.window, text="正在载入，请稍等……")
        self.label.pack(pady=20)

        self.progress = ttk.Progressbar(self.window, mode="indeterminate", length=200)
        self.progress.pack(pady=10)

        self.window.deiconify()  # 显示窗口
        self.progress.start(10)

    def destroy(self):
        if self.window.winfo_exists():
            self.progress.stop()
            self.window.destroy()


class MainWindow:
    def __init__(self, master, loading_window):
        self.master = master
        self.loading_window = loading_window
        self.account_manager = AccountManager("account_data.json")
        self.ui_helper = UIHelper()
        self.thread_manager = ThreadManager(master, self.ui_helper, self.account_manager)

        self.window_width = 700
        self.window_height = 450

        self.setup_main_window()
        self.create_menu_bar()

        self.main_frame = ttk.Frame(master, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.master.after(100, self.delayed_initialization)

    def delayed_initialization(self):
        self.check_paths()
        self.master.after(3000, self.finalize_initialization)

    def finalize_initialization(self):
        if hasattr(self, 'loading_window') and self.loading_window:
            self.loading_window.destroy()
            self.loading_window = None

        # 设置主窗口位置
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = (screen_width - self.window_width) // 2
        y = (screen_height - self.window_height) // 2
        self.master.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")

        self.master.deiconify()  # 显示主窗口
        self.start_auto_refresh()

    def setup_main_window(self):
        self.master.title("微信多开管理器")
        self.master.iconbitmap('SunnyMultiWxMng.ico')

    def create_menu_bar(self):
        self.menu_bar = tk.Menu(self.master)
        self.master.config(menu=self.menu_bar)

        self.edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="编辑", menu=self.edit_menu)
        self.edit_menu.add_command(label="刷新", command=self.create_account_list)

        self.settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="设置", menu=self.settings_menu)
        self.settings_menu.add_command(label="路径", command=self.open_path_settings)
        self.settings_menu.add_command(label="关于", command=self.open_about)

        self.menu_bar.add_command(label="by 吾峰起浪", state="disabled")
        self.menu_bar.entryconfigure("by 吾峰起浪", foreground="gray")

    def create_account_list(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        self.account_frame = ttk.Frame(self.main_frame)
        self.account_frame.pack(fill=tk.BOTH, expand=True)

        logged_in, not_logged_in = self.account_manager.get_account_list()

        if logged_in is None or not_logged_in is None:
            error_label = ttk.Label(self.account_frame, text="无法获取账户列表，请检查路径设置", foreground="red")
            error_label.pack(pady=20)
            return

        self.logged_in_label = ttk.Label(self.account_frame, text="已登录账号：", font=("", 12, "bold"))
        self.logged_in_label.pack(anchor="w", pady=(10, 5))

        for account in logged_in:
            self.add_account_row(self.account_frame, account, True)

        self.not_logged_in_label = ttk.Label(self.account_frame, text="未登录账号：", font=("", 12, "bold"))
        self.not_logged_in_label.pack(anchor="w", pady=(20, 5))

        self.create_manual_login_button()

        for account in not_logged_in:
            self.add_account_row(self.account_frame, account, False)

    def create_manual_login_button(self):
        manual_login_button = ttk.Button(self.account_frame, text="手动登录", command=self.manual_login_account)
        manual_login_button.pack(side=tk.BOTTOM, pady=10)

    def start_auto_refresh(self):
        self.create_account_list()
        self.master.after(60000, self.start_auto_refresh)

    def open_path_settings(self):
        path_settings_window = tk.Toplevel(self.master)
        func_path_setting.PathSettingWindow(path_settings_window, self.on_path_setting_close)
        self.ui_helper.center_window(path_settings_window)
        path_settings_window.focus_set()

    def open_about(self):
        about_window = tk.Toplevel(self.master)
        func_about.AboutWindow(about_window)
        self.ui_helper.center_window(about_window)

    def check_paths(self):
        install_path = get_path_of_wechat.get_wechat_path()
        data_path = get_path_of_data.get_wechat_data_path()

        if not install_path or not data_path:
            self.show_path_error()
        else:
            self.create_account_list()

    def show_path_error(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        error_label = ttk.Label(self.main_frame, text="路径设置错误，请进入设置-路径中修改", foreground="red")
        error_label.pack(pady=20)

    def on_path_setting_close(self):
        print("路径已更新")
        self.check_paths()
        self.master.after(3000, self.finalize_initialization)

    def add_account_row(self, parent_frame, account, is_logged_in):
        display_name = self.account_manager.get_account_display_name(account)
        config_status = self.account_manager.get_config_status(account)

        callbacks = {
            'note': self.open_note_dialog,
            'config': self.create_and_test,
            'login': self.auto_login_account
        }

        self.ui_helper.create_account_row(parent_frame, account, display_name, is_logged_in, config_status, callbacks)

    def open_note_dialog(self, account):
        dialog_width = 300
        dialog_height = 100
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2

        dialog = tk.Toplevel(self.master)
        dialog.title(f"备注 - {account}")
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # 移除窗口装饰并设置为工具窗口
        dialog.overrideredirect(True)
        dialog.overrideredirect(False)
        dialog.attributes('-toolwindow', True)

        dialog.grab_set()

        note_var = tk.StringVar(value=self.account_manager.get_account_note(account))
        note_entry = ttk.Entry(dialog, textvariable=note_var, width=40)
        note_entry.pack(pady=10)
        note_entry.focus_set()

        def save_note(event=None):
            new_note = note_var.get().strip()
            self.account_manager.update_account_note(account, new_note)
            self.create_account_list()
            dialog.destroy()

        save_button = ttk.Button(dialog, text="确定", command=save_note)
        save_button.pack()

        dialog.bind('<Return>', save_note)
        note_entry.bind('<Return>', save_note)

    def create_and_test(self, account):
        config_dir = get_config_dir()
        if not config_dir:
            messagebox.showerror("错误", "无法获取配置目录")
            return

        self.thread_manager.create_and_test_config(
            account,
            func_config.create_and_test_config,
            self.account_manager.save_account_data,
            self.create_account_list
        )

    def get_not_logged_in_accounts(self):
        logged_in, not_logged_in = self.account_manager.get_account_list()
        return not_logged_in

    def manual_login_account(self):
        self.thread_manager.manual_login_account(manual_login, self.create_account_list,
                                                 self.bring_window_to_front)

    def auto_login_account(self, account):
        self.thread_manager.auto_login_account(account, auto_login, self.create_account_list,
                                               self.bring_window_to_front)

    def bring_window_to_front(self):
        self.master.after(200, lambda: self.master.lift())
        self.master.after(300, lambda: self.master.attributes('-topmost', True))
        self.master.after(400, lambda: self.master.attributes('-topmost', False))
        self.master.after(500, lambda: self.master.focus_force())


def main():
    root = tk.Tk()
    root.withdraw()  # 初始时隐藏主窗口

    loading_window = LoadingWindow(root)
    root.update()

    init_app_structure()

    app = MainWindow(root, loading_window)
    root.mainloop()


if __name__ == "__main__":
    main()
