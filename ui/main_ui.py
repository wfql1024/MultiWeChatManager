# main_ui.py
import glob
import json
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
import webbrowser
from functools import partial
from tkinter import messagebox
from tkinter import ttk

import psutil

from functions import func_setting, func_sw_dll, func_login, func_file, func_account, subfunc_file, func_update
from resources import Strings, Config, Constants
from ui import setting_ui, rewards_ui, debug_ui, statistic_ui, update_log_ui, classic_row_ui, treeview_row_ui, \
    sidebar_ui, about_ui, loading_ui
from utils import hwnd_utils, debug_utils, file_utils
from utils.logger_utils import mylogger as logger


# def read_yaml(file_path):
#     """读取YML文件并解析"""
#     with open(file_path, 'r', encoding='utf-8') as file:
#         return yaml.safe_load(file)
#
#
# def insert_tree_data(tree, data):
#     """将YML数据插入到Treeview中"""
#     for top_key, top_value in data.items():
#         # 插入一级节点（如global, WeChat等）
#         top_node = tree.insert("", "end", text=top_key, values=(top_key, ""))
#
#         # 插入二级节点（name 和 value）
#         for sub_key, sub_value in top_value.items():
#             tree.insert(top_node, "end", text=sub_key, values=(sub_value["name"], sub_value["value"]))


class MainWindow:
    """构建主窗口的类"""

    def __init__(self, root, args=None):
        # 首先确保有默认的标签
        self.tree_ui = None
        self.tree_uis = {
            "WeChat": None,
            "Weixin": None
        }
        self.classic_ui = None
        self.sign_visibility_var = None
        self.sign_visibility = None
        self.scale_var = None
        self.chosen_scale = None
        self.wnd_scale_menu = None
        self.sw = func_setting.fetch_global_setting_or_set_default("tab")
        self.enable_new_func = \
            True if func_setting.fetch_global_setting_or_set_default("enable_new_func") == "True" else False
        self.current_full_version = subfunc_file.get_app_current_version()

        self.root = root
        self.loading_window = tk.Toplevel(self.root)
        self.loading_class = loading_ui.LoadingWindow(self.loading_window)
        self.root.withdraw()  # 初始化时隐藏主窗口
        # 启动自检
        print("稍后自检...")
        self.root.after(2000, self.load_on_startup)

        self.sw_ver = None
        self.error_frame = None
        self.scrollbar = None
        self.canvas_window = None
        self.canvas = None
        self.tab_mng = None
        self.tab_control = None
        self.tab_dict = None
        self.tab_frame = None
        self.chosen_sub_exe = None
        self.program_file_menu = None
        self.view_options_menu = None
        self.view_var = None
        self.need_to_update = False
        self.chosen_view = None
        self.view_menu = None
        self.revoke_err = None
        self.multiple_err = None
        self.revoke_status = None
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
        self.sw_dll_dir = None
        self.sw_data_dir = None
        self.sw_inst_path = None
        self.start_time = None
        self.status_bar = None
        self.status_var = None
        self.main_frame = None
        self.settings_menu = None
        self.edit_menu = None
        self.menu_bar = None
        self.logo_click_count = 0
        self.reset_timer = self.root.after(0, lambda: setattr(self, 'logo_click_count', 0))

        # 版本更新，统计表结构更新，需升级
        subfunc_file.merge_refresh_nodes()
        subfunc_file.move_data_to_wechat()

        style = ttk.Style()
        style.configure('Custom.TButton', padding=Constants.CUS_BTN_PAD,
                        width=Constants.CUS_BTN_WIDTH)  # 水平方向20像素，垂直方向10像素的内边距
        style.configure('Tool.TButton', width=2)  # 水平方向20像素，垂直方向10像素的内边距
        style.configure('FirstTitle.TLabel', font=("", Constants.FIRST_TITLE_FONTSIZE, "bold"))
        style.configure('Link.TLabel', font=("", Constants.LINK_FONTSIZE), foreground="grey")
        style.configure('SecondTitle.TLabel', font=("", Constants.SECOND_TITLE_FONTSIZE))
        style.configure("RedWarning.TLabel", foreground="red", font=("", Constants.LITTLE_FONTSIZE))
        style.configure("LittleText.TLabel", font=("", Constants.LITTLE_FONTSIZE))

        self.root.title("微信多开管理器")
        self.root.iconbitmap(Config.PROJ_ICO_PATH)
        self.window_width, self.window_height = Constants.PROJ_WND_SIZE

        # 创建状态栏
        self.create_status_bar()
        # 创建消息队列
        self.message_queue = queue.Queue()
        # 重定向 stdout
        sys.stdout = debug_utils.RedirectText(self.status_var, self.message_queue, self.debug)
        # 定期检查队列中的消息
        self.update_status()

        # 本地配置不存在的话从远端拉取
        if not os.path.exists(Config.REMOTE_SETTING_JSON_PATH):
            config_data = subfunc_file.fetch_and_decrypt_config_data_from_remote()
        else:
            try:
                with open(Config.REMOTE_SETTING_JSON_PATH, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            except Exception as e1:
                logger.error(e1)
                config_data = subfunc_file.fetch_and_decrypt_config_data_from_remote()
        # 创建选项卡
        self.create_tab(config_data)

        # 初次使用
        if self.new is True:
            self.root.after(3000, self.open_update_log)
            self.root.after(3000, lambda: func_file.mov_backup(new=self.new))

    def create_status_bar(self):
        """创建状态栏"""
        print(f"加载状态栏...")
        self.status_var = tk.StringVar()
        self.status_bar = tk.Label(self.root, textvariable=self.status_var, bd=Constants.STATUS_BAR_BD,
                                   relief=tk.SUNKEN, anchor=tk.W, height=Constants.STATUS_BAR_HEIGHT)
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

    def create_tab(self, config_data):
        """
        创建选项卡
        :param config_data: 获取的远端数据
        :return:
        """
        print("创建选项卡...")
        self.tab_control = ttk.Notebook(self.root)

        # self.tab_mng = ttk.Frame(self.tab_control)
        # self.tab_control.add(self.tab_mng, text='管理')
        # # 读取YML文件并解析
        # data = read_yaml(Config.LOCAL_SETTING_YML_PATH)
        # # 创建Treeview控件
        # tree = ttk.Treeview(self.tab_mng, columns=("name", "value"), show="headings")
        # tree.pack(expand=True, fill=tk.BOTH)
        # # 定义列标题
        # tree.heading("name", text="Name")
        # tree.heading("value", text="Value")
        # # 填充树数据
        # insert_tree_data(tree, data)

        # 本地配置出错的话从远端拉取
        try:
            self.tab_dict = config_data["global"]["all_sw"]
        except KeyError:
            config_data = subfunc_file.fetch_and_decrypt_config_data_from_remote()
            self.tab_dict = config_data["global"]["all_sw"]

        for item in self.tab_dict.keys():
            self.tab_dict[item]['frame'] = ttk.Frame(self.tab_control)
            self.tab_dict[item]['frame'].var = item
            self.tab_control.add(self.tab_dict[item]['frame'], text=self.tab_dict[item]['text'])
        self.tab_control.select(self.tab_dict[self.sw]['frame'])
        self.tab_control.pack(expand=True, fill='both')
        self.on_tab_change(_event=None)

    def load_on_startup(self):
        """启动时关闭等待窗口，并检查配置是否有错误"""
        # print(f"启动自检中...")
        def func_thread():
            self.check_and_init()
            if hasattr(self, 'loading_class') and self.loading_class:
                # print("主程序关闭等待窗口")
                self.loading_class.auto_close()
                self.loading_class = None
            # 设置主窗口位置
            hwnd_utils.bring_wnd_to_center(self.root, self.window_width, self.window_height)
            self.root.deiconify()
            self.tab_control.bind('<<NotebookTabChanged>>', self.on_tab_change)

        try:
            # 线程启动获取登录情况和渲染列表
            threading.Thread(target=func_thread).start()
        except Exception as e:
            logger.error(e)

    def check_and_init(self):
        """检查是否有配置错误"""
        # print(f"初始化检查.........................................................")

        if not os.path.exists(Config.REMOTE_SETTING_JSON_PATH):
            subfunc_file.fetch_and_decrypt_config_data_from_remote()

        # 检查项目根目录中是否有 user_files 这个文件夹，没有则创建
        if not os.path.exists(Config.PROJ_USER_PATH):  # 如果路径不存在
            os.makedirs(Config.PROJ_USER_PATH)  # 创建 user_files 文件夹
            print(f"已创建文件夹: {Config.PROJ_USER_PATH}")

        if os.path.exists(Config.REMOTE_SETTING_JSON_PATH):
            success, result = func_update.split_vers_by_cur_from_local(self.current_full_version)
            if success is True:
                new_versions, old_versions = result
                if len(new_versions) != 0:
                    self.need_to_update = True

        self.chosen_sub_exe = func_setting.fetch_sw_setting_or_set_default("sub_exe", self.sw)
        self.chosen_view = func_setting.fetch_sw_setting_or_set_default("view", self.sw)
        func_setting.fetch_sw_setting_or_set_default("login_size", self.sw)

        if self.sw_inst_path is None or self.sw_data_dir is None or self.sw_dll_dir is None:
            print("路径设置错误，请点击按钮修改")
            self.root.after(0, self.show_setting_error)
            return False
        else:
            screen_size = subfunc_file.get_screen_size_from_setting_ini()
            if not screen_size or screen_size == "":
                # 获取屏幕和登录窗口尺寸
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                # 保存屏幕尺寸
                subfunc_file.save_screen_size_to_setting_ini(f"{screen_width}*{screen_height}")
            return True

    def show_setting_error(self):
        """路径错误提醒"""
        if self.main_frame is not None:
            for widget in self.main_frame.winfo_children():
                widget.destroy()
        if self.error_frame is not None:
            for widget in self.error_frame.winfo_children():
                widget.destroy()
        if self.tab_frame is not None:
            for widget in self.tab_frame.winfo_children():
                widget.destroy()

        # 选择已经存在的框架进行错误信息显示
        if self.tab_frame is not None:
            self.error_frame = ttk.Frame(self.tab_frame, padding=Constants.T_FRM_PAD)
        elif self.main_frame is not None:
            self.error_frame = ttk.Frame(self.main_frame, padding=Constants.T_FRM_PAD)

        self.error_frame.pack(**Constants.T_FRM_PACK)
        error_label = ttk.Label(self.error_frame, text="路径设置错误，请点击按钮修改", foreground="red",
                                anchor=tk.CENTER)
        error_label.pack(**Constants.T_WGT_PACK)
        self.settings_button = ttk.Button(self.error_frame, text="设置", style='Custom.TButton',
                                          command=partial(self.open_settings, self.sw))
        self.settings_button.pack()

    def on_tab_change(self, _event):
        """处理选项卡变化事件，排除特殊选项卡"""
        print("切换选项卡响应中...")
        if self.tab_control.select() == "!disabled":
            return
        selected_frame = self.tab_control.nametowidget(self.tab_control.select())  # 获取当前选中的Frame
        selected_tab = getattr(selected_frame, 'var', None)  # 获取与当前选项卡相关的变量
        if selected_tab:
            func_setting.toggle_tab_record(selected_tab)
            self.recognize_curr_tab_and_refresh()
            print(f"当前选项卡: {selected_tab}")

    def recognize_curr_tab_and_refresh(self):
        """确认选项卡并载入"""
        self.sw = func_setting.fetch_global_setting_or_set_default("tab")
        # print(f"切换前：{self.tab_frame}")
        # print(self.tab_dict)
        self.tab_frame = self.tab_dict[self.sw]['frame']
        # print(f"切换后：{self.tab_frame}")
        self.sw_data_dir = func_setting.get_sw_data_dir(self.sw)
        self.sw_inst_path, self.sw_ver = func_setting.get_sw_inst_path_and_ver(self.sw)
        self.sw_dll_dir = func_setting.get_sw_dll_dir(self.sw)
        # 若标签页为空则创建
        if len(self.tab_frame.winfo_children()) == 0:
            threading.Thread(target=self.check_and_init)
        self.refresh()

    def refresh(self):
        """刷新菜单和界面"""
        print(f"刷新菜单与界面...")

        def reload_func():
            self.root.after(0, self.create_root_menu_bar)
            self.root.after(0, self.refresh_main_frame)

        try:
            # 线程启动获取登录情况和渲染列表
            threading.Thread(target=reload_func).start()
        except Exception as e:
            logger.error(e)

    def create_root_menu_bar(self):
        """创建菜单栏"""
        print("创建菜单栏...")
        # self.chosen_tab = func_setting.fetch_global_setting_or_set_default("tab")
        if hasattr(self, 'menu_bar'):
            # 清空现有菜单栏
            setattr(self, 'menu_bar', None)
        else:
            self.menu_bar = tk.Menu(self.root)
            self.root.config(menu=self.menu_bar)

        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)

        # ————————————————————————————文件菜单————————————————————————————
        self.file_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label="文件", menu=self.file_menu)
        # >用户文件
        self.user_file_menu = tk.Menu(self.file_menu, tearoff=False)
        self.file_menu.add_cascade(label="用户文件", menu=self.user_file_menu)
        self.user_file_menu.add_command(label="打开", command=func_file.open_user_file)
        self.user_file_menu.add_command(label="清除",
                                        command=partial(func_file.clear_user_file, self.refresh_main_frame))
        # >配置文件
        self.config_file_menu = tk.Menu(self.file_menu, tearoff=False)
        if not self.sw_data_dir:
            self.file_menu.add_command(label="配置文件  未获取")
            self.file_menu.entryconfig(f"配置文件  未获取", state="disable")
        else:
            self.file_menu.add_cascade(label="配置文件", menu=self.config_file_menu)
            self.config_file_menu.add_command(label="打开",
                                              command=partial(func_file.open_config_file, self.sw))
            self.config_file_menu.add_command(label="清除",
                                              command=partial(func_file.clear_config_file, self.sw,
                                                              self.refresh_main_frame))
        # >程序目录
        self.program_file_menu = tk.Menu(self.file_menu, tearoff=False)
        self.file_menu.add_cascade(label="程序目录", menu=self.program_file_menu)
        self.program_file_menu.add_command(label="打开", command=func_file.open_program_file)
        self.program_file_menu.add_command(label="删除旧版备份",
                                           command=partial(func_file.mov_backup))

        # >统计数据
        self.statistic_menu = tk.Menu(self.file_menu, tearoff=False)
        self.file_menu.add_cascade(label="统计", menu=self.statistic_menu)
        self.statistic_menu.add_command(label="查看", command=self.open_statistic)
        self.statistic_menu.add_command(label="清除",
                                        command=partial(func_file.clear_statistic_data,
                                                        self.refresh_main_frame))
        # -打开主dll所在文件夹
        self.file_menu.add_command(label="查看DLL", command=partial(func_file.open_dll_dir, self.sw))
        # -创建软件快捷方式
        self.file_menu.add_command(label="创建程序快捷方式", command=func_file.create_app_lnk)
        # -创建快捷启动
        quick_start_sp, = subfunc_file.get_details_from_remote_setting_json(self.sw, support_quick_start=None)
        # print(f"支持快捷启动：{quick_start_sp}")
        self.file_menu.add_command(label="创建快捷启动",
                                   command=partial(func_file.create_multiple_lnk,
                                                   self.sw, self.multiple_status, self.refresh_main_frame),
                                   state="normal" if quick_start_sp is True else "disabled")

        # ————————————————————————————编辑菜单————————————————————————————
        self.edit_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label="编辑", menu=self.edit_menu)
        # -刷新
        self.edit_menu.add_command(label="刷新", command=self.refresh)

        # ————————————————————————————视图菜单————————————————————————————
        self.chosen_view = func_setting.fetch_sw_setting_or_set_default("view", self.sw)
        self.view_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label="视图", menu=self.view_menu)

        # 添加单选框选项
        self.view_var = tk.StringVar(value=self.chosen_view)
        self.view_menu.add_radiobutton(label="经典", variable=self.view_var, value="classic",
                                       command=self.change_classic_view)
        self.view_menu.add_radiobutton(label="列表", variable=self.view_var, value="tree",
                                       command=self.change_tree_view)

        # 显示当前选择的视图
        self.sign_visibility = \
            True if func_setting.fetch_global_setting_or_set_default("sign_visible") == "True" else False
        self.sign_visibility_var = tk.BooleanVar(value=self.sign_visibility)
        self.view_options_menu = tk.Menu(self.view_menu, tearoff=False)
        self.view_menu.add_cascade(label=f"视图选项", menu=self.view_options_menu)
        self.view_options_menu.add_checkbutton(label="显示状态标志", variable=self.sign_visibility_var,
                                               command=partial(func_setting.toggle_sign_visibility,
                                                               not self.sign_visibility, self.refresh))
        if self.chosen_view == "classic":
            # 添加经典视图的菜单项
            pass
        elif self.chosen_view == "tree":
            # 添加列表视图的菜单项
            pass

        self.view_menu.add_separator()  # ————————————————分割线————————————————

        self.chosen_scale = func_setting.fetch_global_setting_or_set_default("scale")
        self.scale_var = tk.StringVar(value=self.chosen_scale)
        self.wnd_scale_menu = tk.Menu(self.view_menu, tearoff=False)
        self.view_menu.add_cascade(label=f"窗口缩放", menu=self.wnd_scale_menu)
        self.wnd_scale_menu.add_radiobutton(label="跟随系统", variable=self.scale_var, value="auto",
                                            command=partial(func_setting.set_wnd_scale,
                                                            self.create_root_menu_bar, "auto"))
        options = ["100", "125", "150", "175", "200"]
        for option in options:
            self.wnd_scale_menu.add_radiobutton(label=f"{option}%", variable=self.scale_var, value=option,
                                                command=partial(func_setting.set_wnd_scale,
                                                                self.create_root_menu_bar, option))
        if self.chosen_scale != "auto" and self.chosen_scale not in options:
            self.wnd_scale_menu.add_radiobutton(label=f"自定义:{self.chosen_scale}%",
                                                variable=self.scale_var, value=self.chosen_scale,
                                                command=partial(func_setting.set_wnd_scale,
                                                                self.create_root_menu_bar))
        else:
            self.wnd_scale_menu.add_radiobutton(label=f"自定义",
                                                variable=self.scale_var, value="0",
                                                command=partial(func_setting.set_wnd_scale,
                                                                self.create_root_menu_bar))

        # ————————————————————————————设置菜单————————————————————————————
        self.settings_menu = tk.Menu(self.menu_bar, tearoff=False)
        # -应用设置
        func_setting.fetch_sw_setting_or_set_default("login_size", self.sw)
        login_size = subfunc_file.get_sw_login_size_from_setting_ini(self.sw)
        warning_sign = Strings.WARNING_SIGN
        if not login_size or not re.match(r"^\d+\*\d+$", login_size):
            self.menu_bar.add_cascade(label=f"{warning_sign}设置", menu=self.settings_menu)
            self.settings_menu.add_command(label=f"{warning_sign}应用设置", foreground='red',
                                           command=partial(self.open_settings, self.sw))
        else:
            self.menu_bar.add_cascade(label="设置", menu=self.settings_menu)
            self.settings_menu.add_command(label="应用设置",
                                           command=partial(self.open_settings, self.sw))
        self.settings_menu.add_separator()  # ————————————————分割线————————————————
        # -防撤回
        self.revoke_status, _, _ = func_sw_dll.check_dll(
            self.sw, "revoke", self.sw_dll_dir, self.sw_ver)
        if self.revoke_status == "不可用":
            self.settings_menu.add_command(label=f"防撤回   {self.revoke_status}", state="disabled")
        elif self.revoke_status.startswith("错误"):
            self.revoke_err = tk.Menu(self.settings_menu, tearoff=False)
            self.settings_menu.add_cascade(label="防撤回   错误!", menu=self.revoke_err, foreground="red")
            self.revoke_err.add_command(label=f"[点击复制]{self.revoke_status}", foreground="red",
                                        command=lambda: self.root.clipboard_append(self.revoke_status))
        else:
            self.settings_menu.add_command(label=f"防撤回   {self.revoke_status}",
                                           command=partial(self.toggle_patch_mode, mode="revoke"))
        self.settings_menu.add_separator()  # ————————————————分割线————————————————
        # -全局多开
        self.multiple_status, _, _ = func_sw_dll.check_dll(
            self.sw, "multiple", self.sw_dll_dir, self.sw_ver)
        if self.multiple_status == "不可用":
            self.settings_menu.add_command(label=f"全局多开 {self.multiple_status}", state="disabled")
        elif self.multiple_status.startswith("错误"):
            self.multiple_err = tk.Menu(self.settings_menu, tearoff=False)
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
            self.sub_executable_menu = tk.Menu(self.settings_menu, tearoff=False)
            # 获取已选择的子程序（假设 func_setting.fetch_sub_exe() 返回 'python', 'handle' 或其他值）
            self.chosen_sub_exe = func_setting.fetch_sw_setting_or_set_default("sub_exe", self.sw)
            self.chosen_sub_exe_var.set(self.chosen_sub_exe)  # 设置初始选中的子程序
            self.settings_menu.add_cascade(label="子程序     选择", menu=self.sub_executable_menu)
            python_sp, python_s_sp, handle_sp = subfunc_file.get_details_from_remote_setting_json(
                self.sw, support_python_mode=None, support_python_s_mode=None, support_handle_mode=None)
            # 添加 Python 的单选按钮
            self.sub_executable_menu.add_radiobutton(
                label='python',
                value='python',
                variable=self.chosen_sub_exe_var,
                command=partial(func_setting.toggle_sub_executable, 'python', self.refresh),
                state='disabled' if not python_sp else 'normal'
            )
            # 添加 强力Python 的单选按钮
            self.sub_executable_menu.add_radiobutton(
                label='python[S]',
                value='python[S]',
                variable=self.chosen_sub_exe_var,
                command=partial(func_setting.toggle_sub_executable, 'python[S]', self.refresh),
                state='disabled' if not python_s_sp else 'normal'
            )
            self.sub_executable_menu.add_separator()  # ————————————————分割线————————————————
            # 添加 Handle 的单选按钮
            self.sub_executable_menu.add_radiobutton(
                label='handle',
                value='handle',
                variable=self.chosen_sub_exe_var,
                command=partial(func_setting.toggle_sub_executable, 'handle', self.refresh),
                state='disabled' if not handle_sp else 'normal'
            )
            self.sub_executable_menu.add_separator()  # ————————————————分割线————————————————
            # 动态添加外部子程序
            external_res_path = Config.PROJ_EXTERNAL_RES_PATH
            exe_files = glob.glob(os.path.join(external_res_path, f"{self.sw}Multiple_*.exe"))
            for exe_file in exe_files:
                file_name = os.path.basename(exe_file)
                right_part = file_name.split('_', 1)[1].rsplit('.exe', 1)[0]
                self.sub_executable_menu.add_radiobutton(
                    label=right_part,
                    value=file_name,
                    variable=self.chosen_sub_exe_var,
                    command=partial(func_setting.toggle_sub_executable, file_name, self.refresh)
                )
        self.settings_menu.add_separator()  # ————————————————分割线————————————————
        self.settings_menu.add_command(label="重置", command=partial(func_file.reset, self.load_on_startup))

        # ————————————————————————————帮助菜单————————————————————————————
        # 检查版本表是否当天已更新
        if (not os.path.exists(Config.REMOTE_SETTING_JSON_PATH) or
                not file_utils.is_latest_file(Config.REMOTE_SETTING_JSON_PATH)):
            subfunc_file.fetch_and_decrypt_config_data_from_remote()
        surprise_sign = Strings.SURPRISE_SIGN
        prefix = surprise_sign if self.need_to_update is True else ""
        self.help_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label=f"{prefix}帮助", menu=self.help_menu)
        self.help_menu.add_command(label="我来赏你！", command=self.open_rewards)
        self.help_menu.add_command(label="视频教程",
                                   command=lambda: webbrowser.open_new(Strings.VIDEO_TUTORIAL_LINK))
        self.help_menu.add_command(label="更新日志", command=self.open_update_log)
        self.help_menu.add_command(label=f"{prefix}关于", command=partial(self.open_about, self.need_to_update))

        # ————————————————————————————作者标签————————————————————————————
        self.enable_new_func = \
            True if func_setting.fetch_global_setting_or_set_default("enable_new_func") == "True" else False
        if self.enable_new_func is True:
            self.menu_bar.add_command(label=Strings.ENABLED_NEW_FUNC)
            self.menu_bar.entryconfigure(Strings.ENABLED_NEW_FUNC, state="disabled")
        else:
            self.menu_bar.add_command(label=Strings.NOT_ENABLED_NEW_FUNC)
            self.menu_bar.entryconfigure(Strings.NOT_ENABLED_NEW_FUNC, command=self.logo_on_click)

    def refresh_main_frame(self):
        """加载或刷新主界面"""
        print(f"刷新...")
        # 菜单刷新
        self.current_full_version = subfunc_file.get_app_current_version()
        for widget in self.tab_frame.winfo_children():
            widget.destroy()

        # 主界面刷新
        print(f"加载主界面.........................................................")
        self.start_time = time.time()
        self.edit_menu.entryconfig("刷新", state="disabled")
        print(f"初始化，已用时：{time.time() - self.start_time:.4f}秒")

        # 使用ThreadManager异步获取账户列表
        print(f"获取登录状态.........................................................")
        try:
            # 线程启动获取登录情况和渲染列表
            def thread_func():
                success, result = func_account.get_account_list(
                    self.sw, self.sw_data_dir, self.multiple_status)
                self.root.after(0, self.create_account_list_ui, success, result)

            threading.Thread(target=thread_func).start()
        except Exception as e:
            logger.error(e)

    def create_account_list_ui(self, success, result):
        """渲染主界面账号列表"""
        if success is not True:
            error_label = ttk.Label(self.main_frame, text="无法获取账户列表，请检查路径设置", foreground="red")
            error_label.pack(pady=Constants.ERR_LBL_PAD_Y)
            self.settings_button = ttk.Button(self.main_frame, text="设置", style='Custom.TButton',
                                              command=partial(self.open_settings, self.sw))
            self.settings_button.pack()
            self.edit_menu.entryconfig("刷新", state="normal")
            return
        print(f"渲染账号列表.........................................................")

        login, logout, wechat_processes, mutex = result

        # 底部框架=手动登录
        bottom_frame = ttk.Frame(self.tab_frame, padding=Constants.BTN_FRAME_PAD)
        bottom_frame.pack(side=tk.BOTTOM)
        prefix = Strings.MUTEX_SIGN if mutex is True and self.sign_visibility else ""
        manual_login_text = f"{prefix}手动登录"
        manual_login_button = ttk.Button(bottom_frame, text=manual_login_text,
                                         command=self.manual_login_account, style='Custom.TButton')
        manual_login_button.pack(side=tk.LEFT)

        # 创建canvas和滚动条区域，注意要先pack滚动条区域，这样能保证滚动条区域优先级更高
        scrollbar_frame = tk.Frame(self.tab_frame)
        scrollbar_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas = tk.Canvas(self.tab_frame, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, side=tk.LEFT, expand=True)

        # 创建滚动条
        self.scrollbar = ttk.Scrollbar(scrollbar_frame, orient="vertical", command=self.canvas.yview)
        self.scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        # 创建一个Frame在Canvas中
        self.main_frame = ttk.Frame(self.canvas)
        # 将main_frame放置到Canvas的窗口中，并禁用Canvas的宽高跟随调整
        self.canvas_window = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        # 将滚动条连接到Canvas
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        # 配置Canvas的滚动区域
        self.canvas.bind('<Configure>', self.on_canvas_configure)

        # 创建账号列表界面
        if self.chosen_view == "classic":
            self.classic_ui = classic_row_ui.ClassicRowUI(
                self.root, self, self.main_frame, result, self.sw_data_dir, self.multiple_status, self.sw)
        elif self.chosen_view == "tree":
            self.tree_uis[self.sw] = treeview_row_ui.TreeviewRowUI(
                self.root, self, self.main_frame, result, self.sw_data_dir, self.multiple_status, self.sw)
        else:
            pass

        subfunc_file.update_refresh_time_statistic(
            self.chosen_view, str(len(login)), time.time() - self.start_time, self.sw)
        print(f"加载完成！用时：{time.time() - self.start_time:.4f}秒")

        # 恢复刷新可用性
        self.edit_menu.entryconfig("刷新", state="normal")

        # 加载完成后更新一下界面并且触发事件以此更新绑定
        self.canvas.update_idletasks()
        event = tk.Event()
        event.width = self.canvas.winfo_width()
        self.on_canvas_configure(event)

        # 获取已登录的窗口hwnd
        func_account.get_main_hwnd_of_accounts(login, self.sw)

        # 进行静默获取头像及配置
        func_account.silent_get_and_config(login, logout, self.sw_data_dir,
                                           self.refresh_main_frame, self.sw)

    def reset_and_refresh(self):
        """重新配置设置后调用"""
        self.check_and_init()
        self.refresh()

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
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            width = event.width
            self.canvas.itemconfig(tagOrId=self.canvas_window, width=width)
            if self.main_frame.winfo_height() > self.canvas.winfo_height():
                self.bind_mouse_wheel(self.canvas)
                self.scrollbar.pack(side=tk.LEFT, fill=tk.Y)
            else:
                self.unbind_mouse_wheel(self.canvas)
                self.scrollbar.pack_forget()
        except Exception as e:
            logger.error(e)

    def open_statistic(self):
        """打开统计窗口"""
        statistic_window = tk.Toplevel(self.root)
        statistic_ui.StatisticWindow(statistic_window, self.sw)

    def change_classic_view(self):
        self.root.unbind("<Configure>")
        func_setting.toggle_view("classic", self.refresh, self.sw)

    def change_tree_view(self):
        func_setting.toggle_view("tree", self.refresh, self.sw)

    def open_settings(self, tab):
        """打开设置窗口"""
        settings_window = tk.Toplevel(self.root)
        setting_ui.SettingWindow(settings_window, tab, self.multiple_status,
                                 self.reset_and_refresh)

    def toggle_patch_mode(self, mode):
        """切换是否全局多开或防撤回"""
        if mode == "multiple":
            mode_text = "全局多开"
        elif mode == "revoke":
            mode_text = "防撤回"
        else:
            return
        success, result = func_account.get_account_list(self.sw, self.sw_data_dir, self.multiple_status)
        if success is True:
            logged_in, _, _, _ = result
            if len(logged_in) > 0:
                answer = messagebox.askokcancel(
                    "警告",
                    "检测到正在使用微信。切换模式需要修改 WechatWin.dll 文件，请先手动退出所有微信后再进行，否则将会强制关闭微信进程。"
                )
                if not answer:
                    self.recognize_curr_tab_and_refresh()
                    return

        try:
            result = func_sw_dll.switch_dll(self.sw, mode, self.sw_dll_dir, self.sw_ver)  # 执行切换操作
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
            self.refresh()

    def open_rewards(self):
        """打开支持窗口"""
        rewards_window = tk.Toplevel(self.root)
        rewards_ui.RewardsWindow(self.root, self.root, rewards_window, Config.REWARDS_PNG_PATH)

    def open_update_log(self):
        """打开版本日志窗口"""
        success, result = func_update.split_vers_by_cur_from_local(self.current_full_version)
        if success is True:
            new_versions, old_versions = result
            update_log_window = tk.Toplevel(self.root)
            update_log_ui.UpdateLogWindow(self.root, self.root, update_log_window, old_versions)
        else:
            messagebox.showerror("错误", result)

    def open_about(self, need_to_update):
        """打开关于窗口"""
        about_wnd = tk.Toplevel(self.root)
        about_ui.AboutWindow(self.root, self.root, about_wnd, need_to_update)

    def logo_on_click(self):
        print("触发了点击")
        self.logo_click_count += 1
        if self.logo_click_count == 3:
            self.to_enable_new_func()
            self.logo_click_count = 0  # 重置计数器
        else:
            self.reset_timer = self.root.after(1000, lambda: setattr(self, 'logo_click_count', 0))  # 1秒后重置

    def to_enable_new_func(self):
        subfunc_file.set_enable_new_func_in_ini()
        messagebox.showinfo("发现彩蛋", "解锁新菜单，快去看看吧！")
        self.refresh()

    def manual_login_account(self):
        """按钮：手动登录"""
        print("手动登录")
        threading.Thread(
            target=func_login.manual_login,
            args=(
                self,
                self.sw,
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
