# main_ui.py
import glob
import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
from functools import partial
from tkinter import messagebox
from tkinter import ttk

import psutil

from functions import func_setting, func_wechat_dll, func_login, func_file, func_account, subfunc_file, func_update
from resources import Strings
from resources.config import Config
from ui import setting_ui, rewards_ui, debug_ui, statistic_ui, update_log_ui, classic_row_ui, treeview_row_ui, \
    sidebar_ui, about_ui, loading_ui
from utils import hwnd_utils, debug_utils, file_utils
from utils.logger_utils import mylogger as logger


class MainWindow:
    """构建主窗口的类"""

    def __init__(self, root, args=None):
        self.program_file_menu = None
        self.root = root
        self.loading_window = tk.Toplevel(self.root)
        self.loading_class = loading_ui.LoadingWindow(self.loading_window)
        self.root.withdraw()  # 初始化时隐藏主窗口
        self.root.after(1500, self.load_on_startup)
        self.view_options_menu = None
        self.view_var = None
        self.need_to_update = False
        self.chosen_view = None
        self.enable_new_func = func_setting.fetch_setting_or_set_default("enable_new_func") == "true"
        self.current_full_version = subfunc_file.get_app_current_version()
        self.view_menu = None
        self.revoke_err = None
        self.multiple_err = None
        self.revoke_status = None
        self.logo_click_count = 0
        self.statistic_menu = None
        self.chosen_sub_exe_var = None
        self.debug = args.debug
        self.new = args.new
        self.settings_button = None
        self.sub_executable_menu = None
        self.config_file_menu = None
        self.user_file_menu = None
        self.file_menu = None
        self.help_menu = None
        self.multiple_status = None
        self.last_version_path = None
        self.data_dir = None
        self.install_path = None
        self.start_time = None
        self.status_bar = None
        self.status_var = None
        self.main_frame = None
        self.settings_menu = None
        self.edit_menu = None
        self.menu_bar = None
        self.reset_timer = self.root.after(0, lambda: setattr(self, 'logo_click_count', 0))

        subfunc_file.merge_refresh_nodes()
        style = ttk.Style()
        style.configure('Custom.TButton', padding=(5, 5))  # 水平方向20像素，垂直方向10像素的内边距

        self.root.title("微信多开管理器")
        self.root.iconbitmap(Config.PROJ_ICO_PATH)
        self.window_width = 500
        self.window_height = 660
        print(f"初始化检查.........................................................")

        # 创建状态栏
        self.create_status_bar()
        # 创建消息队列
        self.message_queue = queue.Queue()
        # 重定向 stdout
        sys.stdout = debug_utils.RedirectText(self.status_var, self.message_queue, self.debug)
        # 定期检查队列中的消息
        self.update_status()

        # 底部框架=手动登录
        self.bottom_frame = ttk.Frame(root, padding="10")
        self.bottom_frame.pack(side=tk.BOTTOM)
        self.manual_login_button = ttk.Button(self.bottom_frame, text="手动登录", width=8,
                                              command=self.manual_login_account, style='Custom.TButton')
        self.manual_login_button.pack(side=tk.LEFT)

        tab_control = ttk.Notebook(self.root)

        # Settings Tab
        self.settings_tab = ttk.Frame(tab_control)
        tab_control.add(self.settings_tab, text='经典微信')

        # Allocation Tab (Placeholder)
        self.allocation_tab = ttk.Frame(tab_control)
        tab_control.add(self.allocation_tab, text='微信4.0')

        tab_control.pack(expand=1, fill='both')

        # 创建canvas和滚动条区域，注意要先pack滚动条区域，这样能保证滚动条区域优先级更高
        self.scrollbar_frame = tk.Frame(self.settings_tab)
        self.scrollbar_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas = tk.Canvas(self.settings_tab, highlightthickness=0)
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

        self.show_setting_error()

        if self.new is True:
            self.root.after(3000, self.open_update_log)
            self.root.after(3000, lambda: func_file.mov_backup(new=self.new))

    def create_status_bar(self):
        """创建状态栏"""
        print(f"加载状态栏.........................................................")
        self.status_var = tk.StringVar()
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W,
                                   height=1)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        # 绑定点击事件
        if self.debug:
            self.status_bar.bind("<Button-1>", lambda event: self.open_debug_window())

    def update_status(self):
        """即时更新状态栏"""
        try:
            # 从队列中获取消息并更新状态栏
            message = self.message_queue.get_nowait()
            if message.strip():  # 如果消息不为空，更新状态栏
                self.status_var.set(message)
        except queue.Empty:
            pass
        except Exception as e:
            print(e)
            pass
        # 每 1 毫秒检查一次队列
        self.root.after(1, self.update_status)

    def load_on_startup(self):
        """启动时检查载入"""
        print(f"重新检查...")
        def func_thread():
            self.check_and_init()
            if hasattr(self, 'loading_class') and self.loading_class:
                print("主程序关闭等待窗口")
                self.loading_class.destroy()
                self.loading_class = None
            # 设置主窗口位置
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = (screen_width - self.window_width) // 2
            y = int((screen_height - 50 - self.window_height - 60) // 2)
            self.root.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")
            self.root.deiconify()
        try:
            # 线程启动获取登录情况和渲染列表
            threading.Thread(target=func_thread).start()
        except Exception as e:
            logger.error(e)

    def check_and_init_thread(self):
        """更改设置后重新检查载入"""
        print(f"重新检查...")
        try:
            # 线程启动获取登录情况和渲染列表
            threading.Thread(target=self.check_and_init).start()
        except Exception as e:
            logger.error(e)

    def check_and_init(self):
        """检查和初始化"""
        # 检查项目根目录中是否有 user_files 这个文件夹，没有则创建
        if not os.path.exists(Config.PROJ_USER_PATH):  # 如果路径不存在
            os.makedirs(Config.PROJ_USER_PATH)  # 创建 user_files 文件夹
            print(f"已创建文件夹: {Config.PROJ_USER_PATH}")

        install_path = func_setting.get_wechat_install_path()
        data_path = func_setting.get_wechat_data_dir()
        dll_dir_path = func_setting.get_wechat_dll_dir()
        func_setting.fetch_setting_or_set_default("sub_exe")
        func_setting.fetch_setting_or_set_default("view")
        if os.path.exists(Config.VER_ADAPTATION_JSON_PATH):
            result = func_update.split_vers_by_cur_from_local(self.current_full_version)
            if result:
                new_versions, old_versions = result
                if len(new_versions) != 0:
                    self.need_to_update = True

        if not install_path or not data_path or not dll_dir_path:
            self.root.after(0, self.show_setting_error)
            return False
        else:
            self.install_path = install_path
            self.data_dir = data_path
            self.last_version_path = dll_dir_path
            screen_size = subfunc_file.get_screen_size_from_setting_ini()
            if not screen_size or screen_size == "":
                # 获取屏幕和登录窗口尺寸
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                # 保存屏幕尺寸
                subfunc_file.save_screen_size_to_setting_ini(f"{screen_width}*{screen_height}")
            self.root.after(0, self.create_main_frame_and_menu)
            return True

    def show_setting_error(self):
        """路径错误提醒"""
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        error_label = ttk.Label(self.main_frame, text="路径设置错误，请点击按钮修改", foreground="red")
        error_label.pack(pady=20)
        self.settings_button = ttk.Button(self.main_frame, text="设置", width=8,
                                          command=self.open_settings, style='Custom.TButton')
        self.settings_button.pack()

    def center_main_window(self):
        """路径检查完毕后进入，销毁等待窗口，居中显示主窗口"""
        if hasattr(self, 'loading_class') and self.loading_class:
            print("主程序关闭等待窗口")
            self.loading_class.destroy()
            self.loading_class = None
        self.root.deiconify()

        # 设置主窗口位置
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - self.window_width) // 2
        y = int((screen_height - 50 - self.window_height - 60) // 2)
        self.root.geometry(f"{self.window_width}x{self.window_height}+{x}+{y}")


    def create_menu_bar(self):
        """创建菜单栏"""
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)

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
        if not self.data_dir:
            self.file_menu.add_command(label="配置文件  未获取")
            self.file_menu.entryconfig(f"配置文件  未获取", state="disable")
        else:
            self.file_menu.add_cascade(label="配置文件", menu=self.config_file_menu)
            self.config_file_menu.add_command(label="打开", command=func_file.open_config_file)
            self.config_file_menu.add_command(label="清除",
                                              command=partial(func_file.clear_config_file,
                                                              self.create_main_frame_and_menu))
        # >配置文件
        self.program_file_menu = tk.Menu(self.file_menu, tearoff=0)
        if not self.data_dir:
            self.file_menu.add_command(label="程序目录  未获取")
            self.file_menu.entryconfig(f"程序目录  未获取", state="disable")
        else:
            self.file_menu.add_cascade(label="程序目录", menu=self.program_file_menu)
            self.program_file_menu.add_command(label="打开", command=func_file.open_program_file)
            self.program_file_menu.add_command(label="清除",
                                              command=partial(func_file.mov_backup))

        # >统计数据
        self.statistic_menu = tk.Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label="统计", menu=self.statistic_menu)
        self.statistic_menu.add_command(label="查看", command=self.open_statistic)
        self.statistic_menu.add_command(label="清除",
                                        command=partial(func_file.clear_statistic_data,
                                                        self.create_main_frame_and_menu))
        # -打开主dll所在文件夹
        self.file_menu.add_command(label="查看DLL", command=func_file.open_dll_dir)
        # -创建软件快捷方式
        self.file_menu.add_command(label="创建程序快捷方式", command=func_file.create_app_lnk)
        # -创建快捷启动
        self.file_menu.add_command(label="创建快捷启动", command=partial(
            func_file.create_multiple_lnk, self.multiple_status, self.create_main_frame_and_menu))

        # ————————————————————————————编辑菜单————————————————————————————
        self.edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="编辑", menu=self.edit_menu)
        # -刷新
        self.edit_menu.add_command(label="刷新", command=self.create_main_frame_and_menu)

        # ————————————————————————————视图菜单————————————————————————————
        self.chosen_view = func_setting.fetch_setting_or_set_default("view")
        self.view_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="视图", menu=self.view_menu)

        # 添加单选框选项
        self.view_var = tk.StringVar(value=self.chosen_view)
        self.view_menu.add_radiobutton(label="经典", variable=self.view_var, value="classic",
                                       command=self.change_classic_view)
        self.view_menu.add_radiobutton(label="列表", variable=self.view_var, value="tree",
                                       command=self.change_tree_view)
        self.view_menu.add_separator()  # ————————————————分割线————————————————
        # 显示当前选择的视图
        self.view_options_menu = tk.Menu(self.view_menu, tearoff=0)
        self.view_menu.add_cascade(label=f"视图选项", menu=self.view_options_menu)
        if self.chosen_view == "classic":
            # 添加经典视图的菜单项
            pass
        elif self.chosen_view == "tree":
            # 添加列表视图的菜单项
            pass

        # ————————————————————————————设置菜单————————————————————————————
        self.settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        # -应用设置
        login_size = subfunc_file.get_login_size_from_setting_ini()
        if not login_size or login_size == "" or login_size == "None":
            self.menu_bar.add_cascade(label="⚠️设置", menu=self.settings_menu)
            self.settings_menu.add_command(label="⚠️应用设置", command=self.open_settings, foreground='red')
        else:
            self.menu_bar.add_cascade(label="设置", menu=self.settings_menu)
            self.settings_menu.add_command(label="应用设置", command=self.open_settings)
        self.settings_menu.add_separator()  # ————————————————分割线————————————————
        # -防撤回
        self.revoke_status, _, _ = func_wechat_dll.check_dll("revoke")
        if self.revoke_status == "不可用":
            self.settings_menu.add_command(label=f"防撤回   {self.revoke_status}", state="disabled")
        elif self.revoke_status.startswith("错误"):
            self.revoke_err = tk.Menu(self.settings_menu, tearoff=0)
            self.settings_menu.add_cascade(label="防撤回   错误!", menu=self.revoke_err, foreground="red")
            self.revoke_err.add_command(label=f"[点击复制]{self.revoke_status}", foreground="red",
                                        command=lambda: self.root.clipboard_append(self.revoke_status))
        else:
            self.settings_menu.add_command(label=f"防撤回   {self.revoke_status}",
                                           command=partial(self.toggle_patch_mode, mode="revoke"))
        self.settings_menu.add_separator()  # ————————————————分割线————————————————
        # -全局多开
        self.multiple_status, _, _ = func_wechat_dll.check_dll("multiple")
        if self.multiple_status == "不可用":
            self.settings_menu.add_command(label=f"全局多开 {self.multiple_status}", state="disabled")
        elif self.multiple_status.startswith("错误"):
            self.multiple_err = tk.Menu(self.settings_menu, tearoff=0)
            self.settings_menu.add_cascade(label="全局多开 错误!", menu=self.multiple_err, foreground="red")
            self.multiple_err.add_command(label=f"[点击复制]{self.multiple_status}", foreground="red",
                                          command=lambda: self.root.clipboard_append(self.multiple_status))
        else:
            self.settings_menu.add_command(label=f"全局多开 {self.multiple_status}",
                                           command=partial(self.toggle_patch_mode, mode="multiple"))
        # >多开子程序选择
        self.chosen_sub_exe_var = tk.StringVar()  # 用于跟踪当前选中的子程序
        # 检查状态
        if self.multiple_status == "已开启":
            self.settings_menu.add_command(label="子程序   不需要")
            self.settings_menu.entryconfig("子程序   不需要", state="disable")
        else:
            self.sub_executable_menu = tk.Menu(self.settings_menu, tearoff=0)
            # 获取已选择的子程序（假设 func_setting.fetch_sub_exe() 返回 'python', 'handle' 或其他值）
            chosen_sub_exe = func_setting.fetch_setting_or_set_default("sub_exe")
            self.chosen_sub_exe_var.set(chosen_sub_exe)  # 设置初始选中的子程序
            self.settings_menu.add_cascade(label="子程序     选择", menu=self.sub_executable_menu)
            # 添加 Python 的单选按钮
            self.sub_executable_menu.add_radiobutton(
                label='python',
                value='python',
                variable=self.chosen_sub_exe_var,
                command=partial(func_setting.toggle_sub_executable, 'python', self.check_and_init_thread)
            )
            # 添加 强力Python 的单选按钮
            self.sub_executable_menu.add_radiobutton(
                label='python[S]',
                value='python[S]',
                variable=self.chosen_sub_exe_var,
                command=partial(func_setting.toggle_sub_executable, 'python[S]', self.check_and_init_thread)
            )
            self.sub_executable_menu.add_separator()  # ————————————————分割线————————————————
            # 添加 Handle 的单选按钮
            self.sub_executable_menu.add_radiobutton(
                label='handle',
                value='handle',
                variable=self.chosen_sub_exe_var,
                command=partial(func_setting.toggle_sub_executable, 'handle', self.check_and_init_thread)
            )
            self.sub_executable_menu.add_separator()  # ————————————————分割线————————————————
            # 动态添加外部子程序
            external_res_path = Config.PROJ_EXTERNAL_RES_PATH
            exe_files = glob.glob(os.path.join(external_res_path, "WeChatMultiple_*.exe"))
            for exe_file in exe_files:
                file_name = os.path.basename(exe_file)
                right_part = file_name.split('_', 1)[1].rsplit('.exe', 1)[0]
                self.sub_executable_menu.add_radiobutton(
                    label=right_part,
                    value=file_name,
                    variable=self.chosen_sub_exe_var,
                    command=partial(func_setting.toggle_sub_executable, file_name, self.check_and_init_thread)
                )
        self.settings_menu.add_separator()  # ————————————————分割线————————————————
        self.settings_menu.add_command(label="重置", command=partial(func_file.reset, self.check_and_init_thread))

        # ————————————————————————————帮助菜单————————————————————————————
        # 检查版本表是否当天已更新
        if (not os.path.exists(Config.VER_ADAPTATION_JSON_PATH) or
                not file_utils.is_latest_file(Config.VER_ADAPTATION_JSON_PATH)):
            subfunc_file.fetch_config_data_from_remote()
        help_text = "帮助"
        about_text = "关于"
        if self.need_to_update is True:
            help_text = "✨帮助"
            about_text = "✨关于"
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label=help_text, menu=self.help_menu)
        self.help_menu.add_command(label="我来赏你！", command=self.open_rewards)
        self.help_menu.add_command(label="视频教程",
                                   command=lambda: webbrowser.open_new(Strings.VIDEO_TUTORIAL_LINK))
        self.help_menu.add_command(label="更新日志", command=self.open_update_log)
        self.help_menu.add_command(label=about_text, command=partial(self.open_about, self.need_to_update))

        # ————————————————————————————作者标签————————————————————————————
        if self.enable_new_func is True:
            self.menu_bar.add_command(label=Strings.ENABLED_NEW_FUNC)
            self.menu_bar.entryconfigure(Strings.ENABLED_NEW_FUNC, state="disabled")
        else:
            self.menu_bar.add_command(label=Strings.NOT_ENABLED_NEW_FUNC)
            self.menu_bar.entryconfigure(Strings.NOT_ENABLED_NEW_FUNC, command=self.logo_on_click)

    def create_main_frame_and_menu(self):
        """加载或刷新主界面和菜单栏"""
        print(f"刷新.........................................................")
        # 菜单也刷新
        print(f"加载菜单栏.........................................................")
        self.enable_new_func = func_setting.fetch_setting_or_set_default("enable_new_func") == "true"
        self.current_full_version = subfunc_file.get_app_current_version()
        self.create_menu_bar()

        print(f"加载主界面.........................................................")
        self.start_time = time.time()
        self.edit_menu.entryconfig("刷新", state="disabled")
        print(f"初始化，已用时：{time.time() - self.start_time:.4f}秒")

        # 使用ThreadManager异步获取账户列表
        print(f"获取登录状态.........................................................")
        try:
            # 线程启动获取登录情况和渲染列表
            def thread_func():
                success, result = func_account.get_account_list(self.multiple_status)
                self.root.after(0, self.create_account_list_ui, success, result)

            threading.Thread(target=thread_func).start()
        except Exception as e:
            logger.error(e)

    def create_account_list_ui(self, success, result):
        """渲染主界面账号列表"""
        # 清除所有子部件
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        if success is not True:
            error_label = ttk.Label(self.main_frame, text="无法获取账户列表，请检查路径设置", foreground="red")
            error_label.pack(pady=20)
            self.settings_button = ttk.Button(self.main_frame, text="设置", width=8,
                                              command=self.open_settings, style='Custom.TButton')
            self.settings_button.pack()
            self.edit_menu.entryconfig("刷新", state="normal")
            return
        print(f"渲染账号列表.........................................................")

        login, logout, wechat_processes = result

        # 创建账号列表界面
        if self.chosen_view == "classic":
            classic_row_ui.ClassicRowUI(
                self.root, self, self.main_frame, result, self.data_dir, self.multiple_status)
        elif self.chosen_view == "tree":
            treeview_row_ui.TreeviewRowUI(
                self.root, self, self.main_frame, result, self.data_dir, self.multiple_status)
        else:
            pass

        subfunc_file.update_refresh_time_statistic(self.chosen_view, str(len(login)), time.time() - self.start_time)
        print(f"加载完成！用时：{time.time() - self.start_time:.4f}秒")

        # 恢复刷新可用性
        self.edit_menu.entryconfig("刷新", state="normal")

        # 加载完成后更新一下界面并且触发事件以此更新绑定
        self.canvas.update_idletasks()
        event = tk.Event()
        event.width = self.canvas.winfo_width()
        self.on_canvas_configure(event)

        # 获取已登录的窗口hwnd
        func_account.get_main_hwnd_of_accounts(login)

        # 进行静默获取头像及配置
        func_account.silent_get_and_config(login, logout, self.data_dir,
                                           self.create_main_frame_and_menu)

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

    def open_statistic(self):
        """打开统计窗口"""
        statistic_window = tk.Toplevel(self.root)
        statistic_ui.StatisticWindow(statistic_window)

    def change_classic_view(self):
        self.root.unbind("<Configure>")
        func_setting.toggle_view("classic", self.check_and_init_thread)

    def change_tree_view(self):
        func_setting.toggle_view("tree", self.check_and_init_thread)

    def open_settings(self):
        """打开设置窗口"""
        settings_window = tk.Toplevel(self.root)
        setting_ui.SettingWindow(settings_window, self.multiple_status, self.check_and_init_thread)

    def toggle_patch_mode(self, mode):
        """切换是否全局多开或防撤回"""
        if mode == "multiple":
            mode_text = "全局多开"
        elif mode == "revoke":
            mode_text = "防撤回"
        else:
            return
        success, result = func_account.get_account_list(self.multiple_status)
        if success is True:
            logged_in, _, _ = result
            if len(logged_in) > 0:
                answer = messagebox.askokcancel(
                    "警告",
                    "检测到正在使用微信。切换模式需要修改 WechatWin.dll 文件，请先手动退出所有微信后再进行，否则将会强制关闭微信进程。"
                )
                if not answer:
                    self.create_menu_bar()
                    return

        try:
            result = func_wechat_dll.switch_dll(mode)  # 执行切换操作
            if result is True:
                messagebox.showinfo("提示", f"成功开启:{mode_text}")
            elif result is False:
                messagebox.showinfo("提示", f"成功关闭:{mode_text}")
            else:
                messagebox.showinfo("提示", "请重试！")
        except psutil.AccessDenied:
            messagebox.showerror("权限不足", "无法终止微信进程，请以管理员身份运行程序。")
        except Exception as e:
            messagebox.showerror("错误", f"操作失败: {str(e)}")
        finally:
            self.create_main_frame_and_menu()  # 无论成功与否，最后更新按钮状态

    def open_rewards(self):
        """打开支持窗口"""
        rewards_window = tk.Toplevel(self.root)
        rewards_ui.RewardsWindow(rewards_window, Config.REWARDS_PNG_PATH)

    def open_update_log(self):
        """打开版本日志窗口"""
        new_versions, old_versions = func_update.split_vers_by_cur_from_local(self.current_full_version)
        update_log_window = tk.Toplevel(self.root)
        update_log_ui.UpdateLogWindow(update_log_window, old_versions)

    def open_about(self, need_to_update):
        """打开关于窗口"""
        about_window = tk.Toplevel(self.root)
        about_ui.AboutWindow(about_window, need_to_update)

    def logo_on_click(self):
        print("触发了点击")
        self.logo_click_count += 1
        if self.logo_click_count == 3:
            self.to_enable_new_func()
            self.logo_click_count = 0  # 重置计数器
        else:
            self.reset_timer = self.root.after(1000, lambda: setattr(self, 'logo_click_count', 0))  # 1秒后重置

    def to_enable_new_func(self):
        subfunc_file.set_enable_new_func_in_ini("true")
        messagebox.showinfo("发现彩蛋", "解锁新菜单，快去看看吧！")
        self.create_main_frame_and_menu()

    def manual_login_account(self):
        """按钮：手动登录"""
        print("手动登录")
        threading.Thread(
            target=func_login.manual_login,
            args=(
                self,
                self.multiple_status,
                partial(hwnd_utils.bring_wnd_to_front, window_class=self, root=self.root)
            )
        ).start()

    def test(self):
        # 清除窗口中的所有控件
        for widget in self.root.winfo_children():
            widget.destroy()

        sidebar_ui.SidebarUI(self.root)

    def open_debug_window(self):
        """打开调试窗口，显示所有输出日志"""
        debug_window = tk.Toplevel(self.root)
        debug_ui.DebugWindow(debug_window)

