# main_ui.py
import os
import queue
import sys
import threading
import time
import tkinter as tk
from functools import partial
from tkinter import messagebox
from tkinter import ttk

from typing import Dict, Union

from functions import func_setting, func_login, func_file, func_account, subfunc_file, func_update, func_config
from resources import Strings, Config, Constants
from ui import setting_ui, debug_ui, update_log_ui, classic_row_ui, treeview_row_ui, loading_ui, detail_ui, menu_ui
from utils import hwnd_utils, debug_utils
from utils.logger_utils import mylogger as logger


# def read_yaml(file_path):
#     """读取YML文件并解析"""
#     with open(file_path, 'r', encoding='utf-8') as file:
#         return yaml.safe_load(file)
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
        self.root_menu = None
        
        self.states: Dict[str, Union[str, None]] = {
            "multiple": None,
            "revoke": None,
        }        
        self.sw_info: Dict[str, Union[str, None]] = {
            "data_dir": None,
            "inst_path": None,
            "ver": None,
            "dll_dir": None,
            "login_size": None,
            "view": None,
        }
        self.tree_uis = {
            "WeChat": None,
            "Weixin": None,
        }
        self.classic_uis = {
            "WeChat": None,
            "Weixin": None,
        }
        self.settings_values: Dict[str, Union[str, None, bool]] = {
            "sign_vis": None,
            "hide_wnd": None,
            "new_func": None,
            "scale": None,
            "rest_mode": None,
        }
        self.settings_variables: Dict[str, Union[tk.BooleanVar, tk.StringVar, None]] = {
            "sign_vis": None,
            "hide_wnd": None,
            "new_func": None,
            "scale": None,
            "rest_mode": None,
        }
        self.app_info: Dict[str, Union[str, bool, None]] = {
            "curr_full_ver": None,
            "need_update": False,
        }
        
        self.sw = subfunc_file.fetch_global_setting_or_set_default("tab")
        self.app_info["curr_full_ver"] = subfunc_file.get_app_current_version()

        self.root = root
        self.loading_window = tk.Toplevel(self.root)
        self.loading_class = loading_ui.LoadingWindow(self.loading_window)
        self.root.withdraw()  # 初始化时隐藏主窗口
        # 启动自检
        print("稍后自检...")
        self.root.after(2000, self.load_on_startup)

        self.error_frame = None
        self.scrollbar = None
        self.canvas_window = None
        self.canvas = None
        self.tab_control = None
        self.tab_dict = None
        self.tab_frame = None
        self.chosen_view = None
        self.debug = args.debug
        self.new = args.new
        self.settings_button = None
        self.start_time = None
        self.status_bar = None
        self.statusbar_output_var = None
        self.main_frame = None

        # 版本更新，统计表结构更新，需升级
        subfunc_file.merge_refresh_nodes()
        subfunc_file.move_data_to_wechat()
        subfunc_file.swap_cnt_and_mode_levels_in_auto()
        subfunc_file.downgrade_item_lvl_under_manual()

        # style管理
        style = ttk.Style()
        style.configure('Custom.TButton', padding=Constants.CUS_BTN_PAD,
                        width=Constants.CUS_BTN_WIDTH)  # 水平方向20像素，垂直方向10像素的内边距
        style.configure('Tool.TButton', width=2)  # 水平方向20像素，垂直方向10像素的内边距
        style.configure('FirstTitle.TLabel', font=("", Constants.FIRST_TITLE_FONTSIZE, "bold"))
        style.configure('Link.TLabel', font=("", Constants.LINK_FONTSIZE), foreground="grey")
        style.configure('SecondTitle.TLabel', font=("", Constants.SECOND_TITLE_FONTSIZE))
        style.configure("RedWarning.TLabel", foreground="red", font=("", Constants.LITTLE_FONTSIZE))
        style.configure("LittleText.TLabel", font=("", Constants.LITTLE_FONTSIZE))

        # 主窗口属性
        self.root.title("微信多开管理器")
        self.root.iconbitmap(Config.PROJ_ICO_PATH)
        self.window_width, self.window_height = Constants.PROJ_WND_SIZE

        # 创建状态栏
        self.create_status_bar()
        self.message_queue = queue.Queue()  # 创建消息队列
        sys.stdout = debug_utils.RedirectText(self.statusbar_output_var, self.message_queue, self.debug)  # 重定向 stdout
        self.update_status()  # 定期检查队列中的消息

        # 创建选项卡
        self.create_tab()

        # 初次使用
        if self.new is True:
            self.root.after(3000, self.open_update_log)
            self.root.after(3000, lambda: func_file.mov_backup(new=self.new))

    def create_status_bar(self):
        """创建状态栏"""
        print(f"加载状态栏...")
        self.statusbar_output_var = tk.StringVar()
        self.status_bar = tk.Label(self.root, textvariable=self.statusbar_output_var, bd=Constants.STATUS_BAR_BD,
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
                self.statusbar_output_var.set(message)
        except queue.Empty:
            pass
        except Exception as e:
            print(e)
            pass
        # 每 1 毫秒检查一次队列
        self.root.after(1, self.update_status)

    def create_tab(self):
        """创建选项卡"""
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
            config_data = subfunc_file.try_get_local_cfg()
            self.tab_dict = config_data["global"]["all_sw"]
        except Exception as e:
            logger.error(e)

        for item in self.tab_dict.keys():
            self.tab_dict[item]['frame'] = ttk.Frame(self.tab_control)
            self.tab_dict[item]['frame'].var = item
            self.tab_control.add(self.tab_dict[item]['frame'], text=self.tab_dict[item]['text'])
            print(self.tab_dict)
        self.tab_control.select(self.tab_dict[self.sw]['frame'])
        self.tab_control.pack(expand=True, fill='both')
        self.on_tab_change(_event=None)

    def load_on_startup(self):
        """启动时关闭等待窗口，并检查配置是否有错误"""

        # print(f"启动自检中...")
        def func_thread():
            # self.check_and_init()
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
        # print(f"初始化检查...")
        subfunc_file.try_get_local_cfg()

        # 检查项目根目录中是否有 user_files 这个文件夹，没有则创建
        if not os.path.exists(Config.PROJ_USER_PATH):  # 如果路径不存在
            os.makedirs(Config.PROJ_USER_PATH)  # 创建 user_files 文件夹
            print(f"已创建文件夹: {Config.PROJ_USER_PATH}")

        if os.path.exists(Config.REMOTE_SETTING_JSON_PATH):
            success, result = func_update.split_vers_by_cur_from_local(self.app_info["curr_full_ver"])
            if success is True:
                new_versions, old_versions = result
                if len(new_versions) != 0:
                    self.app_info["need_update"] = True

        self.chosen_view = subfunc_file.fetch_sw_setting_or_set_default(self.sw, "view")

        if self.sw_info["inst_path"] is None or self.sw_info["data_dir"] is None or self.sw_info["dll_dir"] is None:
            print("路径设置错误，请点击按钮修改")
            self.root.after(0, self.show_setting_error)
            return False
        else:
            screen_size = subfunc_file.fetch_global_setting_or_set_default('screen_size')
            if not screen_size or screen_size == "":
                # 获取屏幕和登录窗口尺寸
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                # 保存屏幕尺寸
                subfunc_file.save_global_setting('screen_size', f"{screen_width}*{screen_height}")
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
            subfunc_file.save_global_setting("tab", selected_tab)
            self.recognize_curr_tab_and_refresh()
            print(f"当前选项卡: {selected_tab}")

    def recognize_curr_tab_and_refresh(self):
        """确认选项卡并载入"""
        self.sw = subfunc_file.fetch_global_setting_or_set_default("tab")
        # print(f"切换前：{self.tab_frame}")
        # print(self.tab_dict)
        self.tab_frame = self.tab_dict[self.sw]['frame']
        # print(f"切换后：{self.tab_frame}")
        # 若标签页为空则创建
        if len(self.tab_frame.winfo_children()) == 0:
            threading.Thread(target=self.check_and_init).start()
        self.refresh()

    def refresh(self):
        """刷新菜单和界面"""
        print(f"刷新菜单与界面...")
        # 只读取ini中存储的配置
        self.sw_info["data_dir"] = func_setting.get_sw_data_dir(self.sw, False)
        self.sw_info["inst_path"], self.sw_info["ver"] = func_setting.get_sw_inst_path_and_ver(self.sw, False)
        self.sw_info["dll_dir"] = func_setting.get_sw_dll_dir(self.sw, False)

        def reload_func():
            self.root_menu = menu_ui.MenuUI(
                self.root, self, self.sw, self.app_info, self.sw_info,
                self.states, self.settings_values, self.settings_variables)
            self.root.after(0, self.root_menu.create_root_menu_bar)
            self.root.after(0, self.refresh_main_frame)

        try:
            # 线程启动获取登录情况和渲染列表
            threading.Thread(target=reload_func).start()
        except Exception as e:
            logger.error(e)

    def refresh_main_frame(self):
        """加载或刷新主界面"""
        print(f"刷新主界面...")
        # 菜单刷新
        for widget in self.tab_frame.winfo_children():
            widget.destroy()

        # 主界面刷新
        print(f"加载主界面.........................................................")
        self.start_time = time.time()
        self.root_menu.edit_menu.entryconfig("刷新", state="disabled")
        print(f"初始化，已用时：{time.time() - self.start_time:.4f}秒")

        # 使用ThreadManager异步获取账户列表
        print(f"获取登录状态.........................................................")
        try:
            # 线程启动获取登录情况和渲染列表
            def thread_func():
                success, result = func_account.get_sw_acc_list(
                    self.sw, self.sw_info["data_dir"], self.states["multiple"])
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
            self.root_menu.edit_menu.entryconfig("刷新", state="normal")
            return

        print(f"渲染账号列表.........................................................")

        acc_list_dict, _, mutex = result
        login = acc_list_dict["login"]
        logout = acc_list_dict["logout"]

        # 底部框架=手动登录
        bottom_frame = ttk.Frame(self.tab_frame, padding=Constants.BTN_FRAME_PAD)
        bottom_frame.pack(side=tk.BOTTOM)
        prefix = Strings.MUTEX_SIGN if mutex is True and self.settings_values["sign_vis"] else ""
        manual_login_text = f"{prefix}手动登录"
        manual_login_button = ttk.Button(bottom_frame, text=manual_login_text,
                                         command=self.to_manual_login, style='Custom.TButton')
        manual_login_button.pack(side=tk.LEFT)

        # 创建canvas和滚动条区域，注意要先pack滚动条区域，这样能保证滚动条区域优先级更高
        scrollbar_frame = tk.Frame(self.tab_frame)
        scrollbar_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas = tk.Canvas(self.tab_frame, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, side=tk.LEFT, expand=True)

        # 创建滚动条
        print("创建滚动条...")
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
            self.classic_uis[self.sw] = classic_row_ui.ClassicRowUI(
                self.root, self, self.main_frame, result, self.sw_info["data_dir"], self.sw)
        elif self.chosen_view == "tree":
            self.tree_uis[self.sw] = treeview_row_ui.TreeviewRowUI(
                self.root, self, self.main_frame, result, self.sw_info["data_dir"], self.sw)
        else:
            pass

        subfunc_file.update_statistic_data(
            self.sw, 'refresh', self.chosen_view, str(len(login)), time.time() - self.start_time)
        print(f"加载完成！用时：{time.time() - self.start_time:.4f}秒")

        # 恢复刷新可用性
        self.root_menu.edit_menu.entryconfig("刷新", state="normal")

        # 加载完成后更新一下界面并且触发事件以此更新绑定
        self.canvas.update_idletasks()
        event = tk.Event()
        event.width = self.canvas.winfo_width()
        self.on_canvas_configure(event)

        # 获取已登录的窗口hwnd
        func_account.get_main_hwnd_of_accounts(login, self.sw)

        # 进行静默获取头像及配置
        func_account.silent_get_and_config(login, logout, self.sw_info["data_dir"],
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

    def open_settings(self, tab):
        """打开设置窗口"""
        settings_window = tk.Toplevel(self.root)
        setting_ui.SettingWindow(settings_window, tab, self.states["multiple"],
                                 self.reset_and_refresh)

    def open_update_log(self):
        """打开版本日志窗口"""
        success, result = func_update.split_vers_by_cur_from_local(self.app_info["curr_full_ver"])
        if success is True:
            new_versions, old_versions = result
            update_log_window = tk.Toplevel(self.root)
            update_log_ui.UpdateLogWindow(self.root, self.root, update_log_window, old_versions)
        else:
            messagebox.showerror("错误", result)

    def open_debug_window(self):
        """打开调试窗口，显示所有输出日志"""
        debug_window = tk.Toplevel(self.root)
        debug_ui.DebugWindow(debug_window)

    def to_manual_login(self):
        """按钮：手动登录"""
        print("手动登录")
        threading.Thread(
            target=func_login.manual_login,
            args=(
                self,
                self.sw,
                self.states["multiple"],
                partial(hwnd_utils.bring_wnd_to_front, window_class=self, root=self.root)
            )
        ).start()

    def to_auto_login(self, accounts):
        """登录所选账号"""
        if self.root_menu.need_hide_wnd is True:
            self.root.iconify()  # 最小化主窗口
        try:
            threading.Thread(
                target=func_login.auto_login_accounts,
                args=(accounts, self.states["multiple"], self.refresh_main_frame, self.sw)
            ).start()
        except Exception as e:
            logger.error(e)

    def to_create_config(self, account):
        """按钮：创建或重新配置"""
        threading.Thread(target=func_config.test,
                         args=(self, account, self.states["multiple"], self.sw)).start()

    def open_acc_detail(self, account, event=None):
        """打开详情窗口"""
        if event is None:
            pass
        detail_window = tk.Toplevel(self.root)
        detail_ui.DetailWindow(self.root, self.root, detail_window, self.sw,
                               account, self.refresh_main_frame)
