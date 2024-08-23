# main_ui.py
import base64
import os
import queue
import shutil
import subprocess
import sys
import time
import tkinter as tk
from functools import partial
from tkinter import messagebox
from tkinter import ttk

import psutil
import pyautogui
import winshell
from PIL import Image, ImageTk
from PIL import ImageDraw

from functions import func_config, func_setting, func_wechat_dll, func_login
from functions.func_account_list import AccountManager, get_config_status
from functions.func_login import manual_login, auto_login
from functions.func_setting import get_wechat_data_path
from resources.config import Config
from resources.strings import Strings
from thread_manager import ThreadManager
from ui import about_ui, setting_ui, detail_ui
from utils import json_utils
from utils.window_utils import center_window, Tooltip


def get_avatar_from_files(account):
    """
    从本地缓存获取头像
    :param account: 原始微信号
    :return: 头像文件 -> ImageFile
    """
    # 获取WeChat数据路径
    wechat_data_path = get_wechat_data_path()

    # 构建头像文件路径
    avatar_path = os.path.join(Config.PROJ_USER_PATH, f"{account}", f"{account}.jpg")

    # 检查是否存在对应account的头像
    if os.path.exists(avatar_path):
        return Image.open(avatar_path)

    # 如果没有，检查default.jpg
    default_path = os.path.join(Config.PROJ_USER_PATH, "default.jpg")
    if os.path.exists(default_path):
        return Image.open(default_path)

    # 如果default.jpg也不存在，尝试从URL获取
    try:
        base64_string = Strings.DEFAULT_AVATAR_BASE64
        image_data = base64.b64decode(base64_string)
        with open(default_path, "wb") as f:
            f.write(image_data)
        return Image.open(default_path)
    except FileNotFoundError as e:
        print("文件路径无效或无法创建文件:", e)
    except IOError as e:
        print("图像文件读取失败:", e)
    except Exception as e:
        print("所有方法都失败，创建空白头像:", e)
        return Image.new('RGB', (44, 44), color='white')


class RedirectText:
    """
    用以传送打印到窗口状态栏的类
    """

    def __init__(self, text_var, message_queue):
        self.text_var = text_var
        self.message_queue = message_queue
        self.original_stdout = sys.stdout

    def write(self, text):
        self.message_queue.put(" " + text)  # 将文本放入队列
        self.original_stdout.write(text)  # 继续在控制台显示

    def flush(self):
        self.original_stdout.flush()


def create_round_corner_image(img, radius):
    """
    创建圆角的头像
    :param img:
    :param radius:
    :return:
    """
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
    """
    为每一个账号创建其行布局的类
    """

    def __init__(self, parent_frame, account, display_name, is_logged_in, config_status, callbacks,
                 update_top_checkbox_callback):
        self.start_time = time.time()
        self.tooltip = None
        self.toggle_avatar_label = None
        self.size = None
        self.update_top_checkbox_callback = update_top_checkbox_callback
        self.is_logged_in = is_logged_in
        style = ttk.Style()
        style.configure('Custom.TButton', padding=(5, 5))  # 水平方向20像素，垂直方向10像素的内边距

        # 行框架=复选框+头像标签+账号标签+按钮区域+配置标签
        self.row_frame = ttk.Frame(parent_frame)
        self.row_frame.pack(fill=tk.X, pady=2)

        # 复选框
        self.checkbox_var = tk.BooleanVar(value=False)
        if is_logged_in:
            self.checkbox = tk.Checkbutton(
                self.row_frame,
                # command=self.update_logged_in_top_checkbox_callback,
                variable=self.checkbox_var
            )
        else:
            self.checkbox = tk.Checkbutton(
                self.row_frame,
                # command=self.update_not_logged_in_top_checkbox_callback,
                variable=self.checkbox_var
            )
        self.checkbox.pack(side=tk.LEFT)

        # 头像标签
        self.avatar_label = self.create_avatar_label(account)
        self.avatar_label.pack(side=tk.LEFT)
        self.avatar_label.bind("<Enter>", lambda event: event.widget.config(cursor="hand2"))
        self.avatar_label.bind("<Leave>", lambda event: event.widget.config(cursor=""))

        # 账号标签
        self.account_label = ttk.Label(self.row_frame, text=display_name)
        self.account_label.pack(side=tk.LEFT, fill=tk.X, padx=(0, 10))

        # 按钮区域=配置或登录按钮
        self.button_frame = ttk.Frame(self.row_frame)
        self.button_frame.pack(side=tk.RIGHT)

        # 配置标签
        self.config_status_label = ttk.Label(self.row_frame, text=config_status, anchor='e')
        self.config_status_label.pack(side=tk.RIGHT, padx=5, fill=tk.X, expand=True)

        if is_logged_in:
            # 配置按钮
            self.config_button_text = "重新配置" if config_status != "无配置" else "添加配置"
            self.config_button = ttk.Button(
                self.button_frame,
                text=self.config_button_text,
                style='Custom.TButton',
                width=8,
                command=lambda: callbacks['config'](account)
            )
            self.config_button.pack(side=tk.RIGHT, padx=0)
            self.row_frame.bind("<Button-1>", self.toggle_checkbox, add="+")
            for child in self.row_frame.winfo_children():
                child.bind("<Button-1>", self.toggle_checkbox, add="+")
        else:
            # 登录按钮
            self.login_button = ttk.Button(self.button_frame, text="自动登录", style='Custom.TButton', width=8,
                                           command=lambda: callbacks['login'](account))
            self.login_button.pack(side=tk.RIGHT, padx=0)

            if config_status == "无配置":
                # 无配置禁用按钮且置底
                self.disable_button_and_add_tip(self.login_button, "请先手动登录后配置")
                self.checkbox.config(state='disabled')
                self.row_frame.pack(side=tk.BOTTOM)
            else:
                # 启用按钮且为行区域添加复选框绑定
                self.enable_button_and_unbind_tip(self.login_button)
                self.row_frame.bind("<Button-1>", self.toggle_checkbox, add="+")
                for child in self.row_frame.winfo_children():
                    child.bind("<Button-1>", self.toggle_checkbox, add="+")

        # 头像绑定详情事件
        self.avatar_label.bind("<Button-1>", lambda event: callbacks['detail'](account))
        print(f"内部：加载{account}界面用时{time.time() - self.start_time:.4f}秒")

    def disable_button_and_add_tip(self, button, text):
        """
        禁用按钮，启用提示
        :return: None
        """
        button.state(['disabled'])
        if not self.tooltip:
            self.tooltip = Tooltip(button, text)

    def enable_button_and_unbind_tip(self, button):
        """
        启用按钮，去除提示
        :return: None
        """
        button.state(['!disabled'])
        if self.tooltip:
            self.tooltip.widget.unbind("<Enter>")
            self.tooltip.widget.unbind("<Leave>")
            self.tooltip = None

    def toggle_checkbox(self, event):
        """
        切换复选框状态
        :param event: 点击复选框
        :return: 阻断继续切换
        """
        self.checkbox_var.set(not self.checkbox_var.get())
        self.update_top_checkbox_callback(self.is_logged_in)
        return "break"

    def set_checkbox(self, value):
        """设置当前复选框的状态"""
        self.checkbox_var.set(value)

    def is_checked(self):
        """
        获取复选框状态
        :return: 复选框状态 -> bool
        """
        return self.checkbox_var.get()

    def create_avatar_label(self, account):
        """
        创建头像标签
        :param account: 原始微信号
        :return: 头像标签 -> Label
        """
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


def create_lnk_for_account(account, status):
    # 获取数据路径
    data_path = func_setting.get_wechat_data_path()
    wechat_path = func_setting.get_wechat_install_path()
    if not data_path:
        return False

    # 构建源文件和目标文件路径
    source_file = os.path.join(data_path, "All Users", "config", f"{account}.data")
    target_file = os.path.join(data_path, "All Users", "config", "config.data")
    if status == "已开启":
        process_path_text = f"\"{wechat_path}\""
    else:
        process_path_text = f"cscript //B //Nologo \"{Config.MULTI_SUBPROCESS}\""

    bat_content = f"""
    @echo off
    REM 复制配置文件
    copy "{source_file}" "{target_file}"
    if errorlevel 1 (
        echo 复制配置文件失败
        exit /b 1
    )
    echo 复制配置文件成功

    REM 根据状态启动微信
    start "" /B {process_path_text}
        """

    # 保存为批处理文件
    bat_file_path = os.path.join(Config.PROJ_USER_PATH, f'{account}', f'{status} - {account}.bat')
    with open(bat_file_path, 'w', encoding='utf-8') as bat_file:
        bat_file.write(bat_content.strip())

    print(f"批处理文件已生成: {bat_file_path}")

    # 获取桌面路径
    desktop = winshell.desktop()

    # 获取批处理文件名并去除后缀
    bat_file_name = os.path.splitext(os.path.basename(bat_file_path))[0]

    # 构建快捷方式路径
    shortcut_path = os.path.join(desktop, f"{bat_file_name}.lnk")

    # 图标文件路径
    icon_path = os.path.join(Config.PROJ_USER_PATH, f"{account}", f"{account}.jpg")
    ico_path = os.path.join(Config.PROJ_USER_PATH, f"{account}", f"{account}.ico")

    # 将JPG转换为ICO
    image = Image.open(icon_path)
    image.save(ico_path, format='ICO')

    # 创建快捷方式
    with winshell.shortcut(shortcut_path) as shortcut:
        shortcut.path = bat_file_path
        shortcut.working_directory = os.path.dirname(bat_file_path)
        # 修正icon_location的传递方式，传入一个包含路径和索引的元组
        shortcut.icon_location = (ico_path, 0)

    print(f"桌面快捷方式已生成: {os.path.basename(shortcut_path)}")


class MainWindow:
    """构建主窗口的类"""

    def __init__(self, master, loading_window):
        self.logged_in_checkbox = None
        self.logged_in_checkbox_var = None
        self.logged_in_bottom_frame = None
        self.one_key_quit = None
        self.not_logged_in_title = None
        self.not_logged_in_checkbox = None
        self.not_logged_in_checkbox_var = None
        self.one_key_auto_login = None
        self.not_logged_in_bottom_frame = None
        self.logged_in_title = None
        self.tooltips = {}
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
        style = ttk.Style()
        style.configure('Custom.TButton', padding=(5, 5))  # 水平方向20像素，垂直方向10像素的内边距

        self.window_width = 420
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

        # 底部框架=创建lnk+手动登录
        self.bottom_frame = ttk.Frame(master, padding="10")
        self.bottom_frame.pack(side=tk.BOTTOM)

        manual_login_button = ttk.Button(self.bottom_frame, text="手动登录", width=8,
                                         command=self.manual_login_account, style='Custom.TButton')
        manual_login_button.pack(side=tk.LEFT)

        # 创建lnk
        self.create_lnk_button = ttk.Button(self.bottom_frame, text="创建lnk", width=8,
                                            command=self.create_lnk, style='Custom.TButton')
        self.create_lnk_button.pack(side=tk.RIGHT)

        # 创建canvas和滚动条区域，注意要先pack滚动条区域，这样能保证滚动条区域优先级更高
        self.canvas = tk.Canvas(master, highlightthickness=0)
        self.scrollbar_frame = tk.Frame(master)
        self.scrollbar_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(fill=tk.BOTH, side=tk.LEFT, expand=True)

        # 创建滚动条
        self.scrollbar = ttk.Scrollbar(self.scrollbar_frame, orient="vertical", command=self.canvas.yview)
        self.scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        # 创建一个Frame在Canvas中
        self.main_frame = ttk.Frame(self.canvas)

        # 将main_frame放置到Canvas的窗口中，并禁用Canvas的宽高跟随调整
        self.canvas_window = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")

        # 将滚动条连接到Canvas
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # 配置Canvas的滚动区域
        self.canvas.bind('<Configure>', self.on_canvas_configure)

        self.logged_in_rows = {}
        self.not_logged_in_rows = {}

        self.master.after(200, self.delayed_initialization)

    def delayed_initialization(self):
        """延迟加载，等待路径检查"""
        self.master.after(200, self.finalize_initialization)
        self.check_and_init()

    def finalize_initialization(self):
        """路径检查完毕后进入，销毁等待窗口，居中显示主窗口"""
        if hasattr(self, 'loading_window') and self.loading_window:
            self.loading_window.destroy()
            self.loading_window = None

        # 设置主窗口位置
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = (screen_width - self.window_width) // 2
        y = int((screen_height - 50 - self.window_height - 60) // 2)
        self.master.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")

        self.master.deiconify()  # 显示主窗口

        # time.sleep(500)
        # self.ui_helper.center_window(self.master)

    def setup_main_window(self):
        self.master.title("微信多开管理器")
        self.master.iconbitmap(Config.PROJ_ICO_PATH)

    def bring_window_to_front(self):
        self.master.after(200, lambda: self.master.lift())
        self.master.after(300, lambda: self.master.attributes('-topmost', True))
        self.master.after(400, lambda: self.master.attributes('-topmost', False))
        self.master.after(500, lambda: self.master.focus_force())

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
        self.settings_menu.add_command(label="应用设置", command=self.open_settings)
        self.settings_menu.add_command(label="重置", command=self.reset)
        self.settings_menu.add_command(label="关于", command=self.open_about)

        self.menu_bar.add_command(label="by 吾峰起浪", state="disabled")
        self.menu_bar.entryconfigure("by 吾峰起浪", foreground="gray")

    def create_status_bar(self):
        self.status_var = tk.StringVar()
        self.status_bar = tk.Label(self.master, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W,
                                   height=1)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

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

    def check_and_init(self):
        """路径检查"""
        # 检查项目根目录中是否有 user_files 这个文件夹，没有则创建
        if not os.path.exists(Config.PROJ_USER_PATH):  # 如果路径不存在
            os.makedirs(Config.PROJ_USER_PATH)  # 创建 user_files 文件夹
            print(f"已创建文件夹: {Config.PROJ_USER_PATH}")

        install_path = func_setting.get_wechat_install_path()
        data_path = func_setting.get_wechat_data_path()
        last_version_path = func_setting.get_wechat_latest_version_path()

        if not install_path or not data_path or not last_version_path:
            self.show_setting_error()
        else:
            self.install_path = install_path
            self.data_path = data_path
            self.last_version_path = last_version_path

            screen_size = func_setting.get_setting_from_ini(
                Config.SETTING_INI_PATH,
                Config.INI_SECTION,
                Config.INI_KEY_SCREEN_SIZE,
            )
            login_size = func_setting.get_setting_from_ini(
                Config.SETTING_INI_PATH,
                Config.INI_SECTION,
                Config.INI_KEY_LOGIN_SIZE,
            )

            if not screen_size or not login_size:
                # 获取屏幕和登录窗口尺寸
                screen_width = self.master.winfo_screenwidth()
                screen_height = self.master.winfo_screenheight()
                subprocess.Popen(Config.MULTI_SUBPROCESS,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
                time.sleep(3)
                wechat_window = pyautogui.getWindowsWithTitle("微信")[0]
                login_width, login_height = wechat_window.size

                # 保存
                func_setting.save_setting_to_ini(
                    Config.SETTING_INI_PATH,
                    Config.INI_SECTION,
                    Config.INI_KEY_SCREEN_SIZE,
                    f"{screen_width}*{screen_height}"
                )
                func_setting.save_setting_to_ini(
                    Config.SETTING_INI_PATH,
                    Config.INI_SECTION,
                    Config.INI_KEY_LOGIN_SIZE,
                    f"{login_width}*{login_height}"
                )
                wechat_window.close()

            # 开始创建列表
            self.create_main_frame()

    def show_setting_error(self):
        """路径错误提醒"""
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        error_label = ttk.Label(self.main_frame, text="路径设置错误，请进入设置-路径中修改", foreground="red")
        error_label.pack(pady=20)

    def create_main_frame(self):
        print("刷新...")
        self.start_time = time.time()
        self.edit_menu.entryconfig("刷新", state="disabled")
        print(f"初始化，已用时：{time.time() - self.start_time:.4f}秒")

        # 使用ThreadManager异步获取账户列表
        try:
            self.thread_manager.get_account_list_thread(self.account_manager, self.create_account_ui)
        finally:
            # 恢复刷新可用性
            self.edit_menu.entryconfig("刷新", state="normal")

        # 直接调用 on_canvas_configure 方法
        self.canvas.update_idletasks()

    def create_account_ui(self, result):
        logged_in, not_logged_in, wechat_processes = result
        self.wechat_processes = wechat_processes

        # 清除所有子部件
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        if logged_in is None or not_logged_in is None or wechat_processes is None:
            error_label = ttk.Label(self.main_frame, text="无法获取账户列表，请检查路径设置", foreground="red")
            error_label.pack(pady=20)
            return

        self.logged_in_rows.clear()
        self.not_logged_in_rows.clear()

        # 已登录框架=已登录标题+已登录列表
        self.logged_in_frame = ttk.Frame(self.main_frame)
        self.logged_in_frame.pack(side=tk.TOP, fill=tk.X, pady=15, padx=10)

        # 已登录标题=已登录复选框+已登录标签+已登录按钮区域
        self.logged_in_title = ttk.Frame(self.logged_in_frame)
        self.logged_in_title.pack(side=tk.TOP, fill=tk.X)

        # 已登录复选框
        self.logged_in_checkbox_var = tk.IntVar(value=0)
        self.logged_in_checkbox = tk.Checkbutton(
            self.logged_in_title,
            variable=self.logged_in_checkbox_var,
            tristatevalue=-1
        )
        self.logged_in_checkbox.pack(side=tk.LEFT)

        # 已登录标签
        self.logged_in_label = ttk.Label(self.logged_in_title, text="已登录账号：", font=("", 10, "bold"))
        self.logged_in_label.pack(side=tk.LEFT, fill=tk.X, anchor="w", pady=10)

        # 已登录按钮区域=一键退出
        self.logged_in_bottom_frame = ttk.Frame(self.logged_in_title)
        self.logged_in_bottom_frame.pack(side=tk.RIGHT)

        # 一键退出
        self.one_key_quit = ttk.Button(self.logged_in_bottom_frame, text="一键退出", width=8,
                                       command=self.quit_selected_accounts, style='Custom.TButton')
        self.one_key_quit.pack(side=tk.RIGHT, pady=0)

        # 加载已登录列表
        for account in logged_in:
            self.add_account_row(self.logged_in_frame, account, True)

        # 未登录框架=未登录标题+未登录列表
        self.not_logged_in_frame = ttk.Frame(self.main_frame)
        self.not_logged_in_frame.pack(side=tk.TOP, fill=tk.X, pady=15, padx=10)

        # 未登录标题=未登录复选框+未登录标签+未登录按钮区域
        self.not_logged_in_title = ttk.Frame(self.not_logged_in_frame)
        self.not_logged_in_title.pack(side=tk.TOP, fill=tk.X)

        # 未登录复选框
        self.not_logged_in_checkbox_var = tk.IntVar(value=0)
        self.not_logged_in_checkbox = tk.Checkbutton(
            self.not_logged_in_title,
            variable=self.not_logged_in_checkbox_var,
            tristatevalue=-1
        )
        self.not_logged_in_checkbox.pack(side=tk.LEFT)

        # 未登录标签
        self.not_logged_in_label = ttk.Label(self.not_logged_in_title, text="未登录账号：", font=("", 10, "bold"))
        self.not_logged_in_label.pack(side=tk.LEFT, fill=tk.X, anchor="w", pady=10)

        # 未登录按钮区域=一键登录
        self.not_logged_in_bottom_frame = ttk.Frame(self.not_logged_in_title)
        self.not_logged_in_bottom_frame.pack(side=tk.RIGHT)

        # 一键登录
        self.one_key_auto_login = ttk.Button(self.not_logged_in_bottom_frame, text="一键登录", width=8,
                                             command=self.login_selected_accounts, style='Custom.TButton')
        self.one_key_auto_login.pack(side=tk.RIGHT, pady=0)

        # 加载未登录列表
        for account in not_logged_in:
            self.add_account_row(self.not_logged_in_frame, account, False)

        # 更新顶部复选框状态
        self.update_top_title(True)
        self.update_top_title(False)

        print(f"加载完成！用时：{time.time() - self.start_time:.4f}秒")

        # 恢复刷新可用性
        self.edit_menu.entryconfig("刷新", state="normal")

        # 加载完成后更新一下界面并且触发事件以此更新绑定
        self.canvas.update_idletasks()
        event = tk.Event()
        event.width = self.canvas.winfo_width()
        self.on_canvas_configure(event)

    def add_account_row(self, parent_frame, account, is_logged_in):
        display_name = self.account_manager.get_account_display_name(account)
        config_status = get_config_status(account)

        callbacks = {
            'detail': self.open_detail,
            'config': self.create_config,
            'login': self.auto_login_account
        }

        # 创建列表实例
        row = AccountRow(parent_frame, account, display_name, is_logged_in, config_status, callbacks,
                         self.update_top_title)

        # 将已登录、未登录但已配置实例存入字典
        if is_logged_in:
            self.logged_in_rows[account] = row
        else:
            if config_status == "无配置":
                pass
            else:
                self.not_logged_in_rows[account] = row

    def bind_mouse_wheel(self, widget):
        """递归地为widget及其所有子控件绑定鼠标滚轮事件"""
        widget.bind("<MouseWheel>", self.on_mousewheel, add='+')
        widget.bind("<Button-4>", self.on_mousewheel, add='+')
        widget.bind("<Button-5>", self.on_mousewheel, add='+')

        for child in widget.winfo_children():
            self.bind_mouse_wheel(child)

    def unbind_mouse_wheel(self, widget):
        """递归地为widget及其所有子控件绑定鼠标滚轮事件"""
        widget.unbind("<MouseWheel>")
        widget.unbind("<Button-4>")
        widget.unbind("<Button-5>")

        for child in widget.winfo_children():
            self.unbind_mouse_wheel(child)

    def on_mousewheel(self, event):
        """鼠标滚轮触发动作"""
        # 对于Windows和MacOS
        if event.delta:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        # 对于Linux
        else:
            if event.num == 5:
                self.canvas.yview_scroll(1, "units")
            elif event.num == 4:
                self.canvas.yview_scroll(-1, "units")

    def on_canvas_configure(self, event):
        """动态调整canvas中窗口的宽度，并根据父子间高度关系进行滚轮事件绑定与解绑"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        width = event.width
        self.canvas.itemconfig(self.canvas_window, width=width)

        if self.main_frame.winfo_height() > self.canvas.winfo_height():
            self.bind_mouse_wheel(self.canvas)
            self.scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        else:
            self.unbind_mouse_wheel(self.canvas)
            self.scrollbar.pack_forget()

    def disable_button_and_add_tip(self, button, text):
        """
        禁用按钮，启用提示
        :return: None
        """
        button.state(['disabled'])
        if button not in self.tooltips:
            self.tooltips[button] = Tooltip(button, text)

    def enable_button_and_unbind_tip(self, button):
        """
        启用按钮，去除提示
        :return: None
        """
        button.state(['!disabled'])
        if button in self.tooltips:
            self.tooltips[button].widget.unbind("<Enter>")
            self.tooltips[button].widget.unbind("<Leave>")
            del self.tooltips[button]

    def toggle_top_checkbox(self, event, is_logged_in):
        """
        切换顶部复选框状态，更新子列表
        :param is_logged_in: 是否登录
        :param event: 点击复选框
        :return: 阻断继续切换
        """
        if is_logged_in:
            checkbox_var = self.logged_in_checkbox_var
            rows = self.logged_in_rows
            button = self.one_key_quit
            tip = "请选择要退出的账号"
        else:
            checkbox_var = self.not_logged_in_checkbox_var
            rows = self.not_logged_in_rows
            button = self.one_key_auto_login
            tip = "请选择要登录的账号"
        checkbox_var.set(not checkbox_var.get())
        value = checkbox_var.get()
        if value:
            self.enable_button_and_unbind_tip(button)
        else:
            self.disable_button_and_add_tip(button, tip)
        for row in rows.values():
            row.set_checkbox(value)
        return "break"

    def update_top_title(self, is_logged_in):
        """根据AccountRow实例的复选框状态更新顶行复选框状态"""
        # toggle方法
        toggle = partial(self.toggle_top_checkbox, is_logged_in=is_logged_in)

        # 判断是要更新哪一个顶行
        if is_logged_in:
            all_rows = list(self.logged_in_rows.values())
            checkbox = self.logged_in_checkbox
            title = self.logged_in_title
            checkbox_var = self.logged_in_checkbox_var
            button = self.one_key_quit
            tip = "请选择要退出的账号"
        else:
            all_rows = list(self.not_logged_in_rows.values())
            checkbox = self.not_logged_in_checkbox
            title = self.not_logged_in_title
            checkbox_var = self.not_logged_in_checkbox_var
            button = self.one_key_auto_login
            tip = "请选择要登录的账号"

        if len(all_rows) == 0:
            # 列表为空时解绑复选框相关事件，禁用复选框和按钮
            title.unbind("<Button-1>")
            for child in title.winfo_children():
                child.unbind("<Button-1>")
            checkbox.config(state="disabled")
            self.disable_button_and_add_tip(button, tip)
        else:
            # 列表不为空则绑定和复用
            title.bind("<Button-1>", toggle, add="+")
            for child in title.winfo_children():
                child.bind("<Button-1>", toggle, add="+")
            checkbox.config(state="normal")

            # 从子列表的状态来更新顶部复选框
            states = [row.checkbox_var.get() for row in all_rows]
            if all(states):
                checkbox_var.set(1)
                self.enable_button_and_unbind_tip(button)
            elif any(states):
                checkbox_var.set(-1)
                self.enable_button_and_unbind_tip(button)
            else:
                checkbox_var.set(0)
                self.disable_button_and_add_tip(button, tip)

    def quit_selected_accounts(self):
        account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
        accounts = [
            account
            for account, row in self.logged_in_rows.items()
            if row.is_checked()
        ]
        quited_accounts = []
        for account in accounts:
            try:
                pid = account_data.get(account, {}).get("pid", None)
                nickname = account_data.get(account, {}).get("nickname", None)
                process = psutil.Process(pid)
                if process.name() == "WeChat.exe":
                    process.terminate()
                    os.system(f"taskkill /F /PID {pid}")
                    print(f"结束了{pid}")
                    quited_accounts.append((nickname, pid))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        json_utils.save_json_data(Config.ACC_DATA_JSON_PATH, account_data)
        self.create_main_frame()

    def login_selected_accounts(self):
        accounts = [
            account
            for account, row in self.not_logged_in_rows.items()
            if row.is_checked()
        ]
        self.master.iconify()  # 最小化主窗口
        try:
            self.thread_manager.login_accounts(func_login.auto_login_accounts, accounts, self.status, self.create_main_frame)
        finally:
            # 恢复刷新可用性
            self.edit_menu.entryconfig("刷新", state="normal")

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

    def open_settings(self):
        settings_window = tk.Toplevel(self.master)
        setting_ui.SettingWindow(settings_window, self.delayed_initialization)
        center_window(settings_window)
        settings_window.focus_set()

    def reset(self):
        # 显示确认对话框
        confirm = messagebox.askokcancel(
            "确认重置",
            "该操作将会清空该软件的数据，请确认是否需要重置？"
        )
        directory_path = Config.PROJ_USER_PATH
        if confirm:
            # 确认后删除目录的所有内容
            for item in os.listdir(directory_path):
                item_path = os.path.join(directory_path, item)
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

            messagebox.showinfo("重置完成", "目录已成功重置。")
            self.delayed_initialization()
        else:
            messagebox.showinfo("操作取消", "重置操作已取消。")

    def open_about(self):
        about_window = tk.Toplevel(self.master)
        about_ui.AboutWindow(about_window)
        center_window(about_window)

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
        self.thread_manager.auto_login_account(auto_login, account, self.status, self.create_main_frame,
                                               self.bring_window_to_front)

    def create_lnk(self):
        target_path = os.path.join(func_setting.get_wechat_data_path(), 'All Users', 'config')
        # 初始化一个空列表，用于存储文件名
        configured_accounts = []

        # 遍历目标目录中的所有文件
        for file_name in os.listdir(target_path):
            # 只处理以 .data 结尾的文件
            if file_name.endswith('.data') and file_name != 'config.data':
                # 获取不含扩展名的文件名
                file_name_without_ext = os.path.splitext(file_name)[0]
                # 添加到列表中
                configured_accounts.append(file_name_without_ext)

        for account in configured_accounts:
            create_lnk_for_account(account, self.status)
