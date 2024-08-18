# main_ui.py
import os
import queue
import sys
import time
import tkinter as tk
from io import BytesIO
from tkinter import messagebox
from tkinter import ttk

import psutil
import requests
from PIL import Image, ImageTk
from PIL import ImageDraw

from functions import func_config, func_path, func_wechat_dll
from functions.func_account_list import AccountManager, get_config_status
from functions.func_login import manual_login, auto_login
from functions.func_path import get_wechat_data_path
from resources.strings import Strings
from resources.config import Config
from thread_manager import ThreadManager
from ui import about_ui, path_setting_ui, detail_ui
from utils.window_utils import center_window, Tooltip


def get_avatar_from_files(account):
    # 获取WeChat数据路径
    wechat_data_path = get_wechat_data_path()

    # 构建头像文件路径
    avatar_path = os.path.join(wechat_data_path, "All Users", f"{account}.jpg")

    # 检查是否存在对应account的头像
    if os.path.exists(avatar_path):
        return Image.open(avatar_path)

    # 如果没有，检查default.jpg
    default_path = os.path.join(wechat_data_path, "All Users", "default.jpg")
    if os.path.exists(default_path):
        return Image.open(default_path)

    # 如果default.jpg也不存在，尝试从URL获取
    try:
        url = Strings.DEFAULT_AVATAR_URL
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))
        img.save(default_path)  # 保存到default.jpg
        return img
    except Exception():
        print("所有方法都失败，创建空白头像")
        return Image.new('RGB', (44, 44), color='white')


class RedirectText:
    def __init__(self, text_var, message_queue):
        self.text_var = text_var
        self.message_queue = message_queue
        self.original_stdout = sys.stdout

    def write(self, text):
        self.message_queue.put(text)  # 将文本放入队列
        self.original_stdout.write(text)  # 继续在控制台显示

    def flush(self):
        self.original_stdout.flush()


def create_round_corner_image(img, radius):
    circle = Image.new('L', (radius * 2, radius * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, radius * 2, radius * 2), fill=255)
    alpha = Image.new('L', img.size, 255)
    w, h = img.size

    # 计算使图像居中的偏移量
    offset_x = (w - radius * 2) // 2
    offset_y = (h - radius * 2) // 2

    # 调整左上角圆角（radius-1）
    alpha.paste(circle.crop((0, 0, radius - 1, radius - 1)), (offset_x, offset_y))  # 左上角
    # 左下角保持原样
    alpha.paste(circle.crop((0, radius, radius, radius * 2)), (offset_x, h - radius - offset_y))  # 左下角
    # 右上角保持原样
    alpha.paste(circle.crop((radius, 0, radius * 2, radius)), (w - radius - offset_x, offset_y))  # 右上角
    # 调整右下角圆角（radius+1）
    alpha.paste(circle.crop((radius, radius, radius * 2 + 1, radius * 2 + 1)),
                (w - radius - offset_x, h - radius - offset_y))  # 右下角

    img.putalpha(alpha)
    return img


def avatar_on_leave(event):
    event.widget.config(cursor="")  # 恢复默认光标


def avatar_on_enter(event):
    event.widget.config(cursor="hand2")  # 将光标改为手型


class AccountRow:
    def __init__(self, parent_frame, account, display_name, is_logged_in, config_status, callbacks):
        self.tooltip = None
        self.toggle_avatar_label = None
        self.size = None
        style = ttk.Style()
        style.configure('Custom.TButton', padding=(5, 5))  # 水平方向20像素，垂直方向10像素的内边距

        self.row_frame = ttk.Frame(parent_frame)
        self.row_frame.pack(fill=tk.X, pady=2)

        self.checkbox_var = tk.BooleanVar(value=False)
        self.checkbox = tk.Checkbutton(self.row_frame, variable=self.checkbox_var)
        self.checkbox.pack(side=tk.LEFT)

        self.avatar_label = self.create_avatar_label(account)
        self.avatar_label.pack(side=tk.LEFT)

        self.avatar_label.bind("<Enter>", avatar_on_enter)
        self.avatar_label.bind("<Leave>", avatar_on_leave)

        self.account_label = ttk.Label(self.row_frame, text=display_name)
        self.account_label.pack(side=tk.LEFT, fill=tk.X, padx=(0, 10))

        self.button_frame = ttk.Frame(self.row_frame)
        self.button_frame.pack(side=tk.RIGHT)

        self.config_status_label = ttk.Label(self.row_frame, text=config_status, anchor='e')
        self.config_status_label.pack(side=tk.RIGHT, padx=5, fill=tk.X, expand=True)

        if is_logged_in:
            self.config_button_text = "重新配置" if config_status != "无配置" else "添加配置"
            self.config_button = ttk.Button(self.button_frame, text=self.config_button_text, style='Custom.TButton',
                                            width=8,
                                            command=lambda: callbacks['config'](account))
            self.config_button.pack(side=tk.RIGHT, padx=0)
            self.row_frame.bind("<Button-1>", self.toggle_checkbox, add="+")
            for child in self.row_frame.winfo_children():
                child.bind("<Button-1>", self.toggle_checkbox, add="+")
        else:
            self.login_button = ttk.Button(self.button_frame, text="自动登录", style='Custom.TButton', width=8,
                                           command=lambda: callbacks['login'](account))
            self.login_button.pack(side=tk.RIGHT, padx=0)

            if config_status == "无配置":
                self.disable_login_button()
                self.checkbox.config(state='disabled')
                self.row_frame.pack(side=tk.BOTTOM)
            else:
                self.enable_login_button()
                self.row_frame.bind("<Button-1>", self.toggle_checkbox, add="+")
                for child in self.row_frame.winfo_children():
                    child.bind("<Button-1>", self.toggle_checkbox, add="+")

        self.avatar_label.bind("<Button-1>", lambda event: callbacks['detail'](account))
        print(f"完成账号创建：{account}")

    def disable_login_button(self):
        self.login_button.state(['disabled'])
        if not self.tooltip:
            self.tooltip = Tooltip(self.login_button, "请先手动登录后配置")

    def enable_login_button(self):
        self.login_button.state(['!disabled'])
        if self.tooltip:
            self.tooltip.widget.unbind("<Enter>")
            self.tooltip.widget.unbind("<Leave>")
            self.tooltip = None

    def toggle_checkbox(self, event):
        self.checkbox_var.set(not self.checkbox_var.get())
        return "break"

    def is_checked(self):
        return self.checkbox_var.get()

    def create_avatar_label(self, account):
        try:
            img = get_avatar_from_files(account)
            img = img.resize((44, 44))
            photo = ImageTk.PhotoImage(img)
            avatar_label = ttk.Label(self.row_frame, image=photo)
            avatar_label.image = photo  # 保持对图像的引用
        except Exception as e:
            print(f"Error creating avatar label: {e}")
            # 如果加载失败，使用一个空白标签
            avatar_label = ttk.Label(self.row_frame, width=10)
        return avatar_label


class MainWindow:
    def __init__(self, master, loading_window):
        self.wechat_processes = None
        self.status = None
        self.last_version_path = None
        self.data_path = None
        self.install_path = None
        self.start_time = None
        self.status_bar = None
        self.status_var = None
        self.logged_in_frame = None
        self.not_logged_in_frame = None
        self.mode_menu = None
        self.not_logged_in_label = None
        self.logged_in_label = None
        self.main_frame = None
        self.settings_menu = None
        self.edit_menu = None
        self.menu_bar = None
        self.master = master
        self.loading_window = loading_window
        self.account_manager = AccountManager(Config.ACC_DATA_JSON_PATH)
        self.thread_manager = ThreadManager(master, self.account_manager)

        self.window_width = 500
        self.window_height = 540

        self.master.withdraw()  # 初始化时隐藏主窗口
        self.setup_main_window()
        self.create_menu_bar()
        self.create_status_bar()

        # 创建消息队列
        self.message_queue = queue.Queue()

        # 重定向 stdout
        sys.stdout = RedirectText(self.status_var, self.message_queue)

        # 定期检查队列中的消息
        self.update_status()

        self.main_frame = ttk.Frame(master, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.master.after(840, self.delayed_initialization)
        self.account_rows = {}  # 用于存储 AccountRow 实例

    def delayed_initialization(self):
        self.check_paths()
        self.master.after(840, self.finalize_initialization)

    def finalize_initialization(self):
        if hasattr(self, 'loading_window') and self.loading_window:
            self.loading_window.destroy()
            self.loading_window = None

        # 设置主窗口位置
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = (screen_width - self.window_width) // 2
        y = int((screen_height - self.window_height) // 2.4)
        self.master.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")

        self.master.deiconify()  # 显示主窗口

        # time.sleep(500)
        # self.ui_helper.center_window(self.master)

    def setup_main_window(self):
        self.master.title("微信多开管理器")
        self.master.iconbitmap('./resources/SunnyMultiWxMng.ico')

    def create_menu_bar(self):
        self.menu_bar = tk.Menu(self.master)
        self.master.config(menu=self.menu_bar)

        self.edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="编辑", menu=self.edit_menu)
        self.edit_menu.add_command(label="刷新", command=self.create_main_frame)

        self.status = func_wechat_dll.check_dll()

        self.settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="设置", menu=self.settings_menu)
        self.settings_menu.add_command(label=f"全局多开 {self.status}", command=self.toggle_patch_mode)
        if self.status == "不可用":
            self.settings_menu.entryconfig(f"全局多开 {self.status}", state="disable")
        self.settings_menu.add_command(label="路径", command=self.open_path_settings)
        self.settings_menu.add_command(label="关于", command=self.open_about)

        self.menu_bar.add_command(label="by 吾峰起浪", state="disabled")
        self.menu_bar.entryconfigure("by 吾峰起浪", foreground="gray")

    def create_status_bar(self):
        self.status_var = tk.StringVar()
        self.status_bar = tk.Label(self.master, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def check_paths(self):
        install_path = func_path.get_wechat_install_path()
        data_path = func_path.get_wechat_data_path()
        last_version_path = func_path.get_wechat_latest_version_path()

        if not install_path or not data_path or not last_version_path:
            self.show_path_error()
        else:
            self.install_path = install_path
            self.data_path = data_path
            self.last_version_path = last_version_path
            self.start_auto_refresh()

    def show_path_error(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        error_label = ttk.Label(self.main_frame, text="路径设置错误，请进入设置-路径中修改", foreground="red")
        error_label.pack(pady=20)

    def create_main_frame(self):
        print("刷新...")
        self.start_time = time.time()
        self.edit_menu.entryconfig("刷新", state="disabled")
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        # 创建一个临时的加载标签
        loading_label = ttk.Label(self.main_frame, text="正在加载账户列表...", font=("", 12, "bold"))
        loading_label.pack(pady=20)

        # 使用ThreadManager异步获取账户列表
        try:
            self.thread_manager.get_account_list_thread(self.account_manager, self._update_account_list)
        finally:
            self.edit_menu.entryconfig("刷新", state="normal")

    def _update_account_list(self, result):
        logged_in, not_logged_in, wechat_processes = result
        self.wechat_processes = wechat_processes

        # 清除所有子部件
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        if logged_in is None or not_logged_in is None or wechat_processes is None:
            error_label = ttk.Label(self.main_frame, text="无法获取账户列表，请检查路径设置", foreground="red")
            error_label.pack(pady=20)
            return

        self.account_rows.clear()

        self.logged_in_frame = ttk.Frame(self.main_frame)
        self.logged_in_frame.pack(fill=tk.X, pady=2)
        self.logged_in_label = ttk.Label(self.logged_in_frame, text="已登录账号：", font=("", 10, "bold"))
        self.logged_in_label.pack(fill=tk.X, anchor="w", pady=(10, 5))
        for account in logged_in:
            self.add_account_row(self.logged_in_frame, account, True)

        self.not_logged_in_frame = ttk.Frame(self.main_frame)
        self.not_logged_in_frame.pack(fill=tk.X, pady=2)
        self.not_logged_in_label = ttk.Label(self.not_logged_in_frame, text="未登录账号：", font=("", 10, "bold"))
        self.not_logged_in_label.pack(fill=tk.X, anchor="w", pady=(20, 5))
        for account in not_logged_in:
            self.add_account_row(self.not_logged_in_frame, account, False)

        manual_login_button = ttk.Button(self.main_frame, text="手动登录", command=self.manual_login_account)
        manual_login_button.pack(side=tk.BOTTOM, pady=0)
        print(f"加载完成！用时：{time.time() - self.start_time}")
        self.edit_menu.entryconfig("刷新", state="normal")

    def add_account_row(self, parent_frame, account, is_logged_in):
        display_name = self.account_manager.get_account_display_name(account)
        config_status = get_config_status(account)

        callbacks = {
            'detail': self.open_detail,
            'config': self.create_config,
            'login': self.auto_login_account
        }

        row = AccountRow(parent_frame, account, display_name, is_logged_in, config_status, callbacks)
        self.account_rows[account] = row

    def get_selected_accounts(self):
        return [account for account, row in self.account_rows.items() if row.is_checked()]

    def start_auto_refresh(self):
        print("自动刷新开始")
        self.create_main_frame()
        self.master.after(300000, self.start_auto_refresh)

    def toggle_patch_mode(self):
        logged_in, _, _ = self.account_manager.get_account_list()
        if logged_in:
            answer = messagebox.askokcancel(
                "警告",
                "检测到正在使用微信。切换模式需要修改 WechatWin.dll 文件，请先手动退出所有微信后再进行，否则将会强制关闭微信进程。"
            )
            if not answer:
                MainWindow.create_menu_bar(self)
                return

        try:
            result = func_wechat_dll.switch_dll()  # 执行切换操作
            print(result)
            if result is True:
                messagebox.showinfo("提示", "成功开启！")
            elif result is False:
                messagebox.showinfo("提示", "成功关闭！")
            else:
                messagebox.showinfo("提示", "请重试！")
        except psutil.AccessDenied:
            messagebox.showerror("权限不足", "无法终止微信进程，请以管理员身份运行程序。")
        except Exception as e:
            messagebox.showerror("错误", f"操作失败: {str(e)}")
        finally:
            MainWindow.create_menu_bar(self)  # 无论成功与否，最后更新按钮状态

    def open_path_settings(self):
        path_settings_window = tk.Toplevel(self.master)
        path_setting_ui.PathSettingWindow(path_settings_window, self.on_path_setting_close)
        center_window(path_settings_window)
        path_settings_window.focus_set()

    def open_about(self):
        about_window = tk.Toplevel(self.master)
        about_ui.AboutWindow(about_window)
        center_window(about_window)

    def on_path_setting_close(self):
        print("路径已更新")
        self.check_paths()
        self.master.after(3000, self.finalize_initialization)

    def open_detail(self, account):
        detail_window = tk.Toplevel(self.master)
        detail_ui.DetailWindow(detail_window, account, self.account_manager, self.create_main_frame)
        center_window(detail_window)
        detail_window.focus_set()

    def create_config(self, account):

        self.thread_manager.create_config(
            account,
            func_config.test_and_create_config,
            self.create_main_frame
        )

    def manual_login_account(self):
        self.thread_manager.manual_login_account(manual_login, self.status, self.create_main_frame,
                                                 self.bring_window_to_front)

    def auto_login_account(self, account):
        self.thread_manager.auto_login_account(account, auto_login, self.create_main_frame,
                                               self.bring_window_to_front)

    def bring_window_to_front(self):
        self.master.after(200, lambda: self.master.lift())
        self.master.after(300, lambda: self.master.attributes('-topmost', True))
        self.master.after(400, lambda: self.master.attributes('-topmost', False))
        self.master.after(500, lambda: self.master.focus_force())

    def update_status(self):
        try:
            # 从队列中获取消息并更新状态栏
            message = self.message_queue.get_nowait()
            if message.strip():  # 如果消息不为空，更新状态栏
                self.status_var.set(message)
        except queue.Empty:
            pass
        # 每 30 毫秒检查一次队列
        self.master.after(1, self.update_status)
