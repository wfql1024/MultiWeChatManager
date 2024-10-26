# main_ui.py
import ctypes
import glob
import os
import queue
import sys
import time
import tkinter as tk
import webbrowser
from functools import partial
from tkinter import messagebox
from tkinter import ttk

import psutil

from functions import func_setting, func_wechat_dll, func_login, func_file, func_account, subfunc_file, \
    func_update
from resources import Strings
from resources.config import Config
from thread_manager import ThreadManager
from ui import about_ui, setting_ui, rewards_ui, debug_ui, statistic_ui, update_log_ui, classic_row_ui
from utils import handle_utils, debug_utils


class MainWindow:
    """构建主窗口的类"""
    def __init__(self, master, loading_window, debug=None):
        self.is_tree_view = None
        self.tree_view_menu = None
        self.view_menu = None
        self.revoke_err = None
        self.multiple_err = None
        self.revoke_status = None
        self.logo_click_count = 0
        self.statistic_menu = None
        self.chosen_sub_exe_var = None
        self.debug = debug
        self.settings_button = None
        self.sub_executable_menu = None
        self.config_file_menu = None
        self.user_file_menu = None
        self.file_menu = None
        self.help_menu = None
        self.multiple_status = None
        self.last_version_path = None
        self.data_path = None
        self.install_path = None
        self.start_time = None
        self.status_bar = None
        self.status_var = None
        self.mode_menu = None
        self.main_frame = None
        self.settings_menu = None
        self.edit_menu = None
        self.menu_bar = None
        self.master = master
        self.reset_timer = self.master.after(0, lambda: setattr(self, 'logo_click_count', 0))
        self.loading_window = loading_window
        self.thread_manager = ThreadManager(master)
        style = ttk.Style()
        style.configure('Custom.TButton', padding=(5, 5))  # 水平方向20像素，垂直方向10像素的内边距

        self.window_width = 420
        self.window_height = 540

        self.master.withdraw()  # 初始化时隐藏主窗口
        self.setup_main_window()

        # 创建状态栏
        self.create_status_bar()
        # 创建消息队列
        self.message_queue = queue.Queue()
        # 重定向 stdout
        sys.stdout = debug_utils.RedirectText(self.status_var, self.message_queue, self.debug)
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

        print(True if ctypes.windll.shell32.IsUserAnAdmin() else False)
        self.show_setting_error()

        self.logged_in_rows = {}
        self.not_logged_in_rows = {}

        self.master.after(200, self.delayed_initialization)

    def setup_main_window(self):
        """创建主窗口"""
        self.master.title("微信多开管理器")
        self.master.iconbitmap(Config.PROJ_ICO_PATH)

    def create_status_bar(self):
        """创建状态栏"""
        print(f"加载状态栏.........................................................")
        self.status_var = tk.StringVar()
        self.status_bar = tk.Label(self.master, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W,
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
        self.master.after(1, self.update_status)

    def delayed_initialization(self):
        """延迟加载，等待路径检查"""
        print(f"初始化检查.........................................................")
        self.master.after(800, self.finalize_initialization)
        self.check_and_init()

    def check_and_init(self):
        """检查和初始化"""
        # 检查项目根目录中是否有 user_files 这个文件夹，没有则创建
        if not os.path.exists(Config.PROJ_USER_PATH):  # 如果路径不存在
            os.makedirs(Config.PROJ_USER_PATH)  # 创建 user_files 文件夹
            print(f"已创建文件夹: {Config.PROJ_USER_PATH}")

        install_path = func_setting.get_wechat_install_path()
        data_path = func_setting.get_wechat_data_path()
        dll_dir_path = func_setting.get_wechat_dll_dir_path()

        if not install_path or not data_path or not dll_dir_path:
            self.show_setting_error()
        else:
            self.install_path = install_path
            self.data_path = data_path
            self.last_version_path = dll_dir_path
            screen_size = subfunc_file.get_screen_size_from_setting_ini()
            if not screen_size or screen_size == "":
                # 获取屏幕和登录窗口尺寸
                screen_width = self.master.winfo_screenwidth()
                screen_height = self.master.winfo_screenheight()
                # 保存屏幕尺寸
                subfunc_file.save_screen_size_to_setting_ini(f"{screen_width}*{screen_height}")
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

        self.master.deiconify()

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
            self.config_file_menu.add_command(label="清除",
                                              command=partial(func_file.clear_config_file,
                                                              self.create_main_frame_and_menu))
        # >统计数据
        self.statistic_menu = tk.Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label="统计", menu=self.statistic_menu)
        self.statistic_menu.add_command(label="查看", command=self.open_statistic)
        self.statistic_menu.add_command(label="清除",
                                        command=partial(func_file.clear_statistic_data,
                                                        self.create_main_frame_and_menu))
        # -打开主dll所在文件夹
        self.file_menu.add_command(label="查看DLL", command=func_file.open_dll_dir_path)
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
        self.view_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="视图", menu=self.view_menu)
        # -经典
        self.view_menu.add_command(label="经典", command=self.change_classic_view)
        # >列表
        self.is_tree_view = tk.BooleanVar()
        self.show_avatar = tk.BooleanVar()
        self.show_origin_acc_id = tk.BooleanVar()
        self.show_now_acc_id = tk.BooleanVar()
        self.show_nickname = tk.BooleanVar()
        self.show_config_status = tk.BooleanVar()
        self.show_pid = tk.BooleanVar()
        self.show_has_mutex = tk.BooleanVar()
        self.tree_view_menu = tk.Menu(self.view_menu, tearoff=0)
        self.view_menu.add_cascade(label="列表", menu=self.tree_view_menu)
        self.tree_view_menu.add_checkbutton(
            label="开启",
            variable=self.is_tree_view,
            command=self.change_tree_view
        )
        self.tree_view_menu.add_separator()  # ————————————————分割线————————————————
        self.tree_view_menu.add_checkbutton(label="显示头像", variable=self.show_avatar,
                                            command=partial(self.toggle_show_or_not_show, view="avatar"))
        self.tree_view_menu.add_checkbutton(label="显示原始微信号", variable=self.show_origin_acc_id,
                                            command=partial(self.toggle_show_or_not_show, view="origin_acc_id"))
        self.tree_view_menu.add_checkbutton(label="显示当前微信号", variable=self.show_now_acc_id,
                                            command=partial(self.toggle_show_or_not_show, view="now_acc_id"))
        self.tree_view_menu.add_checkbutton(label="显示昵称", variable=self.show_nickname,
                                            command=partial(self.toggle_show_or_not_show, view="nickname"))
        self.tree_view_menu.add_checkbutton(label="显示配置", variable=self.show_config_status,
                                            command=partial(self.toggle_show_or_not_show, view="config_status"))
        self.tree_view_menu.add_checkbutton(label="显示pid", variable=self.show_pid,
                                            command=partial(self.toggle_show_or_not_show, view="pid"))
        self.tree_view_menu.add_checkbutton(label="显示互斥体", variable=self.show_has_mutex,
                                            command=partial(self.toggle_show_or_not_show, view="has_mutex"))

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
        unlock_revoke = subfunc_file.get_enable_new_func_from_ini() == "true"
        if unlock_revoke is True:
            # -防撤回
            self.revoke_status, _, _ = func_wechat_dll.check_dll("revoke")
            if self.revoke_status == "不可用":
                self.settings_menu.add_command(label=f"防撤回   {self.revoke_status}", state="disabled")
            elif self.revoke_status.startswith("错误"):
                self.revoke_err = tk.Menu(self.settings_menu, tearoff=0)
                self.settings_menu.add_cascade(label="防撤回   错误!", menu=self.revoke_err, foreground="red")
                self.revoke_err.add_command(label=f"[点击复制]{self.revoke_status}", foreground="red",
                                            command=lambda: self.master.clipboard_append(self.revoke_status))
            else:
                self.settings_menu.add_command(label=f"防撤回   {self.revoke_status}",
                                               command=partial(self.toggle_patch_mode, mode="revoke"))
            self.settings_menu.add_separator()  # ————————————————分割线————————————————
        else:
            pass
        # -全局多开
        self.multiple_status, _, _ = func_wechat_dll.check_dll("multiple")
        if self.multiple_status == "不可用":
            self.settings_menu.add_command(label=f"全局多开 {self.multiple_status}", state="disabled")
        elif self.multiple_status.startswith("错误"):
            self.multiple_err = tk.Menu(self.settings_menu, tearoff=0)
            self.settings_menu.add_cascade(label="全局多开 错误!", menu=self.multiple_err, foreground="red")
            self.multiple_err.add_command(label=f"[点击复制]{self.multiple_status}", foreground="red",
                                          command=lambda: self.master.clipboard_append(self.multiple_status))
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
            chosen_sub_exe = func_setting.fetch_sub_exe()
            self.chosen_sub_exe_var.set(chosen_sub_exe)  # 设置初始选中的子程序
            self.settings_menu.add_cascade(label="子程序     选择", menu=self.sub_executable_menu)
            # 添加 Python 的单选按钮
            self.sub_executable_menu.add_radiobutton(
                label='python',
                value='python',
                variable=self.chosen_sub_exe_var,
                command=partial(func_setting.toggle_sub_executable, 'python', self.delayed_initialization)
            )
            self.sub_executable_menu.add_separator()  # ————————————————分割线————————————————
            # 添加 Handle 的单选按钮
            self.sub_executable_menu.add_radiobutton(
                label='handle',
                value='handle',
                variable=self.chosen_sub_exe_var,
                command=partial(func_setting.toggle_sub_executable, 'handle', self.delayed_initialization)
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
        self.help_menu.add_command(label="更新日志", command=self.open_update_log)
        self.help_menu.add_command(label="关于", command=self.open_about)

        # ————————————————————————————作者标签————————————————————————————
        if unlock_revoke is True:
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
        self.create_menu_bar()

        print(f"加载主界面.........................................................")
        self.start_time = time.time()
        self.edit_menu.entryconfig("刷新", state="disabled")
        print(f"初始化，已用时：{time.time() - self.start_time:.4f}秒")

        # 使用ThreadManager异步获取账户列表
        print(f"获取登录状态.........................................................")
        try:
            self.thread_manager.get_account_list_thread(self.create_account_list_ui)
        finally:
            # 恢复刷新可用性
            self.edit_menu.entryconfig("刷新", state="normal")

        # 直接调用 on_canvas_configure 方法
        self.canvas.update_idletasks()

    def create_account_list_ui(self, result):
        """渲染主界面账号列表"""
        print(f"渲染账号列表.........................................................")
        logged_in, not_logged_in, wechat_processes = result

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

        # 创建账号列表界面
        classic_row_ui.ClassicRowUI(self, self.master, self.main_frame, result, self.data_path, self.multiple_status)

        subfunc_file.update_refresh_time_statistic(str(len(logged_in)), time.time() - self.start_time)
        print(f"加载完成！用时：{time.time() - self.start_time:.4f}秒")

        # 恢复刷新可用性
        self.edit_menu.entryconfig("刷新", state="normal")

        # 加载完成后更新一下界面并且触发事件以此更新绑定
        self.canvas.update_idletasks()
        event = tk.Event()
        event.width = self.canvas.winfo_width()
        self.on_canvas_configure(event)

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
        statistic_window = tk.Toplevel(self.master)
        statistic_ui.StatisticWindow(statistic_window)
        handle_utils.center_window(statistic_window)
        statistic_window.focus_set()

    def change_classic_view(self):
        # TODO
        pass

    def change_tree_view(self):
        # TODO
        pass

    def toggle_show_or_not_show(self, view):
        # TODO
        pass

    def open_settings(self):
        """打开设置窗口"""
        settings_window = tk.Toplevel(self.master)
        setting_ui.SettingWindow(settings_window, self.multiple_status, self.delayed_initialization)
        handle_utils.center_window(settings_window)
        settings_window.focus_set()

    def toggle_patch_mode(self, mode):
        """切换是否全局多开或防撤回"""
        if mode == "multiple":
            mode_text = "全局多开"
        elif mode == "revoke":
            mode_text = "防撤回"
        else:
            return
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
        rewards_window = tk.Toplevel(self.master)
        rewards_ui.RewardsWindow(rewards_window, Config.REWARDS_PNG_PATH)
        handle_utils.center_window(rewards_window)

    def open_update_log(self):
        """打开版本日志窗口"""
        current_full_version = subfunc_file.get_app_current_version()
        new_versions, old_versions = func_update.split_versions_by_current(current_full_version)
        update_log_window = tk.Toplevel(self.master)
        update_log_ui.UpdateLogWindow(update_log_window, old_versions)
        handle_utils.center_window(update_log_window)

    def open_about(self):
        """打开关于窗口"""
        about_window = tk.Toplevel(self.master)
        about_ui.AboutWindow(about_window)
        handle_utils.center_window(about_window)

    def logo_on_click(self):
        print("触发了点击")
        self.logo_click_count += 1
        if self.logo_click_count == 3:
            self.enable_new_func()
            self.logo_click_count = 0  # 重置计数器
        else:
            self.reset_timer = self.master.after(1000, lambda: setattr(self, 'logo_click_count', 0))  # 1秒后重置

    def enable_new_func(self):
        subfunc_file.set_enable_new_func_in_ini("true")
        messagebox.showinfo("发现彩蛋", "解锁新菜单，快去设置菜单下看看吧！")
        self.create_main_frame_and_menu()

    def manual_login_account(self):
        """按钮：手动登录"""
        self.thread_manager.manual_login_account_thread(func_login.manual_login, self.multiple_status,
                                                        self.create_main_frame_and_menu,
                                                        partial(handle_utils.bring_window_to_front, window_class=self))

    def open_debug_window(self):
        """打开调试窗口，显示所有输出日志"""
        debug_window = tk.Toplevel(self.master)
        debug_ui.DebugWindow(debug_window)
        handle_utils.center_window(debug_window)
