# main_ui.py
import base64
import glob
import os
import queue
import shutil
import subprocess
import sys
import time
import tkinter as tk
import webbrowser
from functools import partial
from tkinter import messagebox
from tkinter import ttk

import psutil
import win32api
import win32com
import win32con
import win32gui
import win32ui
import winshell
from PIL import Image, ImageTk
from PIL import ImageDraw
from win32com.client import Dispatch

from functions import func_config, func_setting, func_wechat_dll, func_login, func_file, func_account
from functions.func_login import manual_login, auto_login
from functions.func_setting import get_wechat_data_path
from resources import Strings
from resources.config import Config
from thread_manager import ThreadManager
from ui import about_ui, setting_ui, detail_ui, rewards_ui
from utils import handle_utils
from utils.handle_utils import center_window, Tooltip


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
        if self.original_stdout:
            self.original_stdout.write(text)  # 继续在控制台显示

    def flush(self):
        self.original_stdout.flush()


class AccountRow:
    """
    为每一个账号创建其行布局的类
    """

    def __init__(self, parent_frame, account, status, display_name, is_logged_in, config_status, callbacks,
                 update_top_checkbox_callback):
        self.status = status
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
                command=lambda: callbacks['config'](account, self.status)
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
            img = func_account.get_acc_avatar_from_files(account)
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
    """构建主窗口的类"""

    def __init__(self, master, loading_window):
        self.settings_button = None
        self.sub_executable_menu = None
        self.config_file_menu = None
        self.user_file_menu = None
        self.file_menu = None
        self.help_menu = None
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
        self.thread_manager = ThreadManager(master)
        style = ttk.Style()
        style.configure('Custom.TButton', padding=(5, 5))  # 水平方向20像素，垂直方向10像素的内边距

        self.window_width = 420
        self.window_height = 540

        self.master.withdraw()  # 初始化时隐藏主窗口
        self.setup_main_window()
        # self.create_menu_bar()
        self.create_status_bar()

        # 创建消息队列
        self.message_queue = queue.Queue()
        # 重定向 stdout
        sys.stdout = RedirectText(self.status_var, self.message_queue)
        # 定期检查队列中的消息
        self.update_status()

        # 底部框架=手动登录
        self.bottom_frame = ttk.Frame(master, padding="10")
        self.bottom_frame.pack(side=tk.BOTTOM)
        self.manual_login_button = ttk.Button(self.bottom_frame, text="手动登录", width=8,
                                              command=self.manual_login_account, style='Custom.TButton')
        self.manual_login_button.pack(side=tk.LEFT)

        # 创建canvas和滚动条区域，注意要先pack滚动条区域，这样能保证滚动条区域优先级更高
        self.scrollbar_frame = tk.Frame(master)
        self.scrollbar_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas = tk.Canvas(master, highlightthickness=0)
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
        """创建主窗口"""
        self.master.title("微信多开管理器")
        self.master.iconbitmap(Config.PROJ_ICO_PATH)

    def create_menu_bar(self):
        """创建菜单栏"""
        self.menu_bar = tk.Menu(self.master)
        self.master.config(menu=self.menu_bar)

        # ————————————————————————————文件菜单————————————————————————————
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="文件", menu=self.file_menu)
        # >用户文件
        self.user_file_menu = tk.Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label="用户文件", menu=self.user_file_menu)
        self.user_file_menu.add_command(label="打开", command=func_file.open_user_file)
        self.user_file_menu.add_command(label="清除",
                                        command=partial(func_file.clear_user_file, self.create_main_frame_and_menu))
        # >配置文件
        self.config_file_menu = tk.Menu(self.file_menu, tearoff=0)
        if not self.data_path:
            self.file_menu.add_command(label="配置文件  未获取")
            self.file_menu.entryconfig(f"配置文件  未获取", state="disable")
        else:
            self.file_menu.add_cascade(label="配置文件", menu=self.config_file_menu)
            self.config_file_menu.add_command(label="打开", command=func_file.open_config_file)
            self.config_file_menu.add_command(label="清除", command=partial(func_file.clear_config_file,
                                                                            self.create_main_frame_and_menu))
        # -打开主dll所在文件夹
        self.file_menu.add_command(label="查看DLL", command=func_file.open_dll_dir_path)
        # -创建软件快捷方式
        self.file_menu.add_command(label="创建程序快捷方式", command=func_file.create_app_lnk)
        # -创建快捷启动
        self.file_menu.add_command(label="创建快捷启动", command=partial(
            func_file.create_multiple_lnk, self.status, self.create_main_frame_and_menu))

        # ————————————————————————————编辑菜单————————————————————————————
        self.edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="编辑", menu=self.edit_menu)
        # -刷新
        self.edit_menu.add_command(label="刷新", command=self.create_main_frame_and_menu)

        # ————————————————————————————设置菜单————————————————————————————
        self.settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        # -应用设置
        login_size = func_setting.get_login_size_from_ini()
        if not login_size or login_size == "" or login_size == "None":
            self.menu_bar.add_cascade(label="!!!设置", menu=self.settings_menu)
            self.settings_menu.add_command(label="!!!应用设置", command=self.open_settings, foreground='red')
        else:
            self.menu_bar.add_cascade(label="设置", menu=self.settings_menu)
            self.settings_menu.add_command(label="应用设置", command=self.open_settings)
        self.settings_menu.add_separator()  # ————————————————分割线————————————————
        # -全局多开
        self.status = func_wechat_dll.check_dll()
        self.settings_menu.add_command(label=f"全局多开 {self.status}", command=self.toggle_patch_mode)
        if self.status == "不可用":
            self.settings_menu.entryconfig(f"全局多开 {self.status}", state="disable")
        # >多开子程序选择
        self.sub_executable_menu = tk.Menu(self.settings_menu, tearoff=0)
        if self.status == "已开启":
            self.settings_menu.add_cascade(label=f"子程序   不需要", menu=self.sub_executable_menu)
            self.settings_menu.entryconfig(f"子程序   不需要", state="disable")
        else:
            # 检查选择的子程序，若没有则添加默认
            chosen_sub_exe = func_setting.fetch_sub_exe()
            self.settings_menu.add_cascade(label=f"子程序     选择", menu=self.sub_executable_menu)
            # 是否选择了原生
            if chosen_sub_exe == "原生":
                self.sub_executable_menu.add_command(label=f'√ 原生')
            else:
                self.sub_executable_menu.add_command(
                    label=f'    原生',
                    command=partial(func_setting.toggle_sub_executable, '原生', self.delayed_initialization)
                )
            self.sub_executable_menu.add_separator()  # ————————————————分割线————————————————
            # 渲染子程序列表菜单
            external_res_path = Config.PROJ_EXTERNAL_RES_PATH
            exe_files = glob.glob(
                os.path.join(external_res_path, "WeChatMultiple_*.exe"))  # 使用glob匹配 WeChatMultiple_*.exe 的文件列表
            for exe_file in exe_files:
                file_name = os.path.basename(exe_file)
                right_part = file_name.split('_', 1)[1].rsplit('.exe', 1)[0]  # 提取 `*` 部分
                if file_name == chosen_sub_exe:
                    self.sub_executable_menu.add_command(
                        label=f'√ {right_part}'
                    )
                else:
                    self.sub_executable_menu.add_command(
                        label=f'    {right_part}',
                        command=partial(func_setting.toggle_sub_executable, file_name, self.delayed_initialization)
                    )
        self.settings_menu.add_separator()  # ————————————————分割线————————————————
        self.settings_menu.add_command(label="重置", command=partial(func_file.reset, self.delayed_initialization))

        # ————————————————————————————帮助菜单————————————————————————————
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="帮助", menu=self.help_menu)
        self.help_menu.add_command(label="我来赏你！", command=self.open_rewards)
        self.help_menu.add_command(label="视频教程",
                                   command=lambda: webbrowser.open_new(Strings.VIDEO_TUTORIAL_LINK))
        self.help_menu.add_command(label="关于", command=self.open_about)

        # ————————————————————————————作者标签————————————————————————————
        self.menu_bar.add_command(label="by 吾峰起浪", state="disabled")
        self.menu_bar.entryconfigure("by 吾峰起浪", foreground="grey")

    def create_status_bar(self):
        """创建状态栏"""
        self.status_var = tk.StringVar()
        self.status_bar = tk.Label(self.master, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W,
                                   height=1)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def update_status(self):
        """即时更新状态栏"""
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

        # 设定一个默认的尺寸和默认的子程序
        func_setting.save_login_size_to_ini("347*471")

        install_path = func_setting.get_wechat_install_path()
        data_path = func_setting.get_wechat_data_path()
        dll_dir_path = func_setting.get_wechat_dll_dir_path()

        if not install_path or not data_path or not dll_dir_path:
            self.show_setting_error()
        else:
            self.install_path = install_path
            self.data_path = data_path
            self.last_version_path = dll_dir_path

            screen_size = func_setting.get_screen_size_from_ini()

            if not screen_size or screen_size == "":
                # 获取屏幕和登录窗口尺寸
                screen_width = self.master.winfo_screenwidth()
                screen_height = self.master.winfo_screenheight()
                # 保存屏幕尺寸
                func_setting.save_screen_size_to_ini(f"{screen_width}*{screen_height}")

            # 开始创建列表
            self.create_main_frame_and_menu()

    def show_setting_error(self):
        """路径错误提醒"""
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        error_label = ttk.Label(self.main_frame, text="路径设置错误，请点击按钮修改", foreground="red")
        error_label.pack(pady=20)
        self.settings_button = ttk.Button(self.main_frame, text="设置", width=8,
                                          command=self.open_settings, style='Custom.TButton')
        self.settings_button.pack()
        # 检查选择的子程序，若没有则添加默认
        func_setting.fetch_sub_exe()

    def create_main_frame_and_menu(self):
        """加载或刷新主界面和菜单栏"""
        print("刷新...")
        # 菜单也刷新
        self.create_menu_bar()
        self.start_time = time.time()
        self.edit_menu.entryconfig("刷新", state="disabled")
        print(f"初始化，已用时：{time.time() - self.start_time:.4f}秒")

        # 使用ThreadManager异步获取账户列表
        try:
            self.thread_manager.get_account_list_thread(self.create_account_ui)
        finally:
            # 恢复刷新可用性
            self.edit_menu.entryconfig("刷新", state="normal")

        # 直接调用 on_canvas_configure 方法
        self.canvas.update_idletasks()

    def create_account_ui(self, result):
        """渲染主界面账号列表"""
        logged_in, not_logged_in, wechat_processes = result
        self.wechat_processes = wechat_processes

        # 清除所有子部件
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        if logged_in is None or not_logged_in is None or wechat_processes is None:
            error_label = ttk.Label(self.main_frame, text="无法获取账户列表，请检查路径设置", foreground="red")
            error_label.pack(pady=20)
            self.settings_button = ttk.Button(self.main_frame, text="设置", width=8,
                                              command=self.open_settings, style='Custom.TButton')
            self.settings_button.pack()
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
                                             command=self.auto_login_selected_accounts, style='Custom.TButton')
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
        """渲染账号所在行"""
        display_name = func_account.get_account_display_name(account)
        config_status = func_account.get_config_status(account)

        callbacks = {
            'detail': self.open_detail,
            'config': self.create_config,
            'login': self.auto_login_account
        }

        # 创建列表实例
        row = AccountRow(parent_frame, account, self.status, display_name, is_logged_in, config_status, callbacks,
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

    def open_settings(self):
        """打开设置窗口"""
        settings_window = tk.Toplevel(self.master)
        setting_ui.SettingWindow(settings_window, self.status, self.delayed_initialization)
        center_window(settings_window)
        settings_window.focus_set()

    def toggle_patch_mode(self):
        """切换是否全局多开"""
        logged_in, _, _ = func_account.get_account_list()
        if logged_in:
            answer = messagebox.askokcancel(
                "警告",
                "检测到正在使用微信。切换模式需要修改 WechatWin.dll 文件，请先手动退出所有微信后再进行，否则将会强制关闭微信进程。"
            )
            if not answer:
                self.create_menu_bar()
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
            self.create_main_frame_and_menu()  # 无论成功与否，最后更新按钮状态

    def open_about(self):
        """打开关于窗口"""
        about_window = tk.Toplevel(self.master)
        about_ui.AboutWindow(about_window)
        center_window(about_window)

    def open_rewards(self):
        """打开支持窗口"""
        rewards_window = tk.Toplevel(self.master)
        rewards_ui.RewardsWindow(rewards_window, Config.REWARDS_PNG_PATH)
        center_window(rewards_window)

    def open_detail(self, account):
        """打开详情窗口"""
        detail_window = tk.Toplevel(self.master)
        detail_ui.DetailWindow(detail_window, account, self.create_main_frame_and_menu)
        center_window(detail_window)
        detail_window.focus_set()

    def create_config(self, account, status):
        """按钮：创建或重新配置"""
        self.thread_manager.create_config_thread(
            account,
            func_config.test,
            status,
            self.create_main_frame_and_menu
        )

    def manual_login_account(self):
        """按钮：手动登录"""
        self.thread_manager.manual_login_account(manual_login, self.status, self.create_main_frame_and_menu,
                                                 partial(handle_utils.bring_window_to_front, self=self))

    def auto_login_account(self, account):
        """按钮：自动登录某个账号"""
        accounts = [account]
        try:
            self.thread_manager.login_accounts_thread(
                func_login.auto_login_accounts,
                accounts,
                self.status,
                self.create_main_frame_and_menu
            )

        finally:
            # 恢复刷新可用性
            self.edit_menu.entryconfig("刷新", state="normal")

    def quit_selected_accounts(self):
        """退出所选账号"""
        messagebox.showinfo("待修复", "测试中发现重大bug，先不给点，略~")
        # account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
        # accounts = [
        #     account
        #     for account, row in self.logged_in_rows.items()
        #     if row.is_checked()
        # ]
        # quited_accounts = []
        # for account in accounts:
        #     try:
        #         pid = account_data.get(account, {}).get("pid", None)
        #         nickname = account_data.get(account, {}).get("nickname", None)
        #         process = psutil.Process(pid)
        #         if process_utils.process_exists(pid) and process.name() == "WeChat.exe":
        #             startupinfo = None
        #             if sys.platform == 'win32':
        #                 startupinfo = subprocess.STARTUPINFO()
        #                 startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        #             result = subprocess.run(
        #                 ['taskkill', '/T', '/F', '/PID', f'{pid}'],
        #                 startupinfo=startupinfo,
        #                 capture_output=True,
        #                 text=True
        #             )
        #             if result.returncode == 0:
        #                 print(f"结束了 {pid} 的进程树")
        #                 quited_accounts.append((nickname, pid))
        #             else:
        #                 print(f"无法结束 PID {pid} 的进程树，错误：{result.stderr.strip()}")
        #         else:
        #             print(f"进程 {pid} 已经不存在。")
        #     except (psutil.NoSuchProcess, psutil.AccessDenied):
        #         pass
        # json_utils.save_json_data(Config.ACC_DATA_JSON_PATH, account_data)
        self.create_main_frame_and_menu()

    def auto_login_selected_accounts(self):
        """登录所选账号"""
        accounts = [
            account
            for account, row in self.not_logged_in_rows.items()
            if row.is_checked()
        ]
        self.master.iconify()  # 最小化主窗口
        try:
            self.thread_manager.login_accounts_thread(
                func_login.auto_login_accounts,
                accounts,
                self.status,
                self.create_main_frame_and_menu
            )

        finally:
            # 恢复刷新可用性
            self.edit_menu.entryconfig("刷新", state="normal")

