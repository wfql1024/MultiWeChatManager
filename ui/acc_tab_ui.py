import threading
import time
import tkinter as tk
from functools import partial
from tkinter import ttk

from functions import subfunc_file, func_account, func_config, func_login
from public_class import reusable_widget
from public_class.global_members import GlobalMembers
from resources import Constants, Config, Strings
from ui import treeview_row_ui, classic_row_ui, menu_ui
from utils.logger_utils import mylogger as logger
from utils.logger_utils import myprinter as printer


class AccTabUI:
    """构建主窗口的类"""

    def __init__(self):
        # IDE初始化
        self.detail_ui_class = None
        self.settings_button = None
        self.error_frame = None
        self.main_frame = None
        self.scrollable_canvas = None
        self.start_time = None
        self.root_menu = None
        self.tab_frame = None
        self.sw = None

        self.root_class = GlobalMembers.root_class
        self.sw_classes = self.root_class.sw_classes
        self.root = self.root_class.root
        self.sw_notebook = self.root_class.sw_notebook
        self.global_settings_value = self.root_class.global_settings_value
        self.hotkey_manager = self.root_class.hotkey_manager

    def refresh(self):
        """刷新菜单和界面"""
        print(f"刷新菜单与界面...")
        self.sw = subfunc_file.fetch_global_setting_or_set_default("tab")

        self.tab_frame = self.sw_classes[self.sw].frame

        # 刷新菜单
        self.root_menu = menu_ui.MenuUI()
        try:
            self.root.after(0, self.root_menu.create_root_menu_bar)
        except Exception as re:
            logger.error(re)
            subfunc_file.force_fetch_remote_encrypted_cfg()
            self.root.after(0, self.root_menu.create_root_menu_bar)

        # 刷新界面
        def reload_func():
            try:
                self.root.after(0, self.refresh_frame, self.sw)
            except Exception as e_reload:
                logger.error(e_reload)
                self.root.after(5000, self.refresh_frame, self.sw)

        try:
            # 线程启动获取登录情况和渲染列表
            threading.Thread(target=reload_func).start()
        except Exception as e:
            logger.error(e)

    def refresh_frame(self, sw=None):
        """加载或刷新主界面"""
        # 如果要刷新的页面不是当前选定选项卡，不用处理
        if sw != self.sw:
            return

        print(f"清除旧界面...")
        for widget in self.tab_frame.winfo_children():
            widget.destroy()
        print(f"加载主界面，锁定刷新按钮...")
        self.root_menu.edit_menu.entryconfig("刷新", state="disabled")
        self.start_time = time.time()
        print(f"初始化，已用时：{time.time() - self.start_time:.4f}秒")
        # 使用ThreadManager异步获取账户列表
        print(f"获取登录状态...")
        try:
            # 线程启动获取登录情况和渲染列表
            def thread_func():
                self.root.after(0, self.create_main_ui)

            threading.Thread(target=thread_func).start()
        except Exception as e:
            logger.error(e)

    def create_main_ui(self):
        """渲染主界面账号列表"""
        # 检测是否路径错误
        if self.root_menu.path_error is True:
            self.show_setting_error()

        else:
            success, result = func_account.get_sw_acc_list(self.root, self, self.sw)
            if success is not True:
                self.show_setting_error()
            else:
                self.create_account_list_ui(result)

        # print("创建完成，无论是错误界面还是正常界面，下面代码都要进行")

        # 恢复刷新可用性
        self.root_menu.edit_menu.entryconfig("刷新", state="normal")

        # 加载完成后更新一下界面并且触发事件
        if self.scrollable_canvas is not None and self.scrollable_canvas.canvas.winfo_exists():
            self.scrollable_canvas.refresh_canvas()

        # 重新绑定标签切换事件
        self.sw_notebook.bind('<<NotebookTabChanged>>', self.root_class.on_tab_change)

    def create_account_list_ui(self, result):
        print(f"渲染账号列表.........................................................")

        acc_list_dict, _, mutex = result
        logins: list = acc_list_dict["login"]
        logouts: list = acc_list_dict["logout"]

        self.sw_classes[self.sw].login_accounts = logins
        self.sw_classes[self.sw].logout_accounts = logouts

        # 底部框架=手动登录
        bottom_frame = ttk.Frame(self.tab_frame, padding=Constants.BTN_FRAME_PAD)
        bottom_frame.pack(side=tk.BOTTOM)
        prefix = Strings.MUTEX_SIGN if mutex is True and self.global_settings_value.sign_vis else ""
        manual_login_text = f"{prefix}手动登录"
        manual_login_button = ttk.Button(bottom_frame, text=manual_login_text,
                                         command=self.to_manual_login, style='Custom.TButton')
        manual_login_button.pack(side=tk.LEFT)

        # 创建一个可以滚动的画布，并放置一个主框架在画布上
        self.scrollable_canvas = reusable_widget.ScrollableCanvas(self.tab_frame)
        self.main_frame = self.scrollable_canvas.main_frame

        # 创建账号列表界面并统计
        self.sw_classes[self.sw].view = subfunc_file.fetch_sw_setting_or_set_default(self.sw, "view")
        if self.sw_classes[self.sw].view == "classic":
            self.sw_classes[self.sw].classic_ui = classic_row_ui.ClassicRowUI(result)
        elif self.sw_classes[self.sw].view == "tree":
            self.sw_classes[self.sw].tree_ui = treeview_row_ui.TreeviewRowUI(result)
        else:
            pass
        subfunc_file.update_statistic_data(
            self.sw, 'refresh', self.sw_classes[self.sw].view, str(len(logins)), time.time() - self.start_time)
        printer.normal(f"加载完成！用时：{time.time() - self.start_time:.4f}秒")

        # 获取已登录的窗口hwnd
        func_account.get_main_hwnd_of_accounts(logins, self.sw)

        # 进行静默获取头像及配置
        func_account.silent_get_and_config(self.sw, logins, logouts)

        # 先停止旧的监听线程
        self.hotkey_manager.stop_hotkey_listener()
        # 更新快捷键
        self.hotkey_manager.load_hotkeys_from_json(Config.TAB_ACC_JSON_PATH)
        # 开启监听线程
        self.hotkey_manager.start_hotkey_listener()

        self.after_success_create_acc_ui_when_start()

    def show_setting_error(self):
        """出错的话，选择已经有的界面中创建错误信息显示"""
        if self.tab_frame is not None:
            for widget in self.tab_frame.winfo_children():
                widget.destroy()
            self.error_frame = ttk.Frame(self.tab_frame, padding=Constants.T_FRM_PAD)

        self.error_frame.pack(**Constants.T_FRM_PACK)
        error_label = ttk.Label(self.error_frame, text="路径设置错误，请点击按钮修改", foreground="red",
                                anchor=tk.CENTER)
        error_label.pack(**Constants.T_WGT_PACK)
        self.settings_button = ttk.Button(self.error_frame, text="设置", style='Custom.TButton',
                                          command=partial(self.root_menu.open_settings, self.sw))
        self.settings_button.pack()

    """后处理"""

    def after_success_create_acc_ui_when_start(self):
        """首次启动后，成功创建账号列表才会执行"""
        if self.root_class.first_created_acc_ui is True:
            return

        # 需要进行的操作
        self.root_class.to_login_auto_start_accounts()

        self.root_class.first_created_acc_ui = True

    """功能区"""

    def to_manual_login(self):
        """按钮：手动登录"""
        print("手动登录")
        threading.Thread(
            target=func_login.manual_login,
            args=(self.sw,)
        ).start()

    def to_auto_login(self, items):
        """登录所选账号"""
        login_dict = {}
        for item in items:
            sw, acc = item.split("/")
            if sw not in login_dict:
                login_dict[sw] = []
            login_dict[sw].append(acc)

        if self.global_settings_value.hide_wnd is True:
            self.root.iconify()  # 最小化主窗口

        try:
            t = threading.Thread(
                target=func_login.auto_login_accounts,
                args=(login_dict,)
            )
            t.start()
        except Exception as e:
            logger.error(e)

    def to_create_config(self, items):
        """按钮：创建或重新配置"""
        accounts = [items.split("/")[1] for items in items]
        threading.Thread(target=func_config.test,
                         args=(self.sw, accounts[0], self.sw_classes[self.sw].multiple_state)).start()

    def to_quit_accounts(self, items):
        """退出所选账号"""
        accounts = [items.split("/")[1] for items in items]
        answer = func_account.quit_selected_accounts(self.sw, accounts)
        if answer is True:
            self.refresh_frame(self.sw)

    def to_open_acc_detail(self, item, widget_tag=None, event=None):
        """打开详情窗口"""
        self.root_class.open_acc_detail(item, self, widget_tag, event)
