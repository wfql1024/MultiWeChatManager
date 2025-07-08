import threading
import time
import tkinter as tk
from functools import partial
from tkinter import ttk, messagebox

import customtkinter as ctk

from functions import subfunc_file
from functions.acc_func import AccInfoFunc, AccOperator
from functions.main_func import MultiSwFunc
from functions.sw_func import SwOperator, SwInfoFunc
from public_class import reusable_widgets
from public_class.enums import OnlineStatus, LocalCfg
from public_class.global_members import GlobalMembers
from resources import Constants, Config
from ui import treeview_row_ui, classic_row_ui
from ui.wnd_ui import WndCreator
from utils.logger_utils import mylogger as logger, Printer
from utils.logger_utils import myprinter as printer


class LoginUI:
    """构建主窗口的类"""

    def __init__(self):
        print("构建登录管理ui...")
        self.quick_refresh_mode = None
        # IDE初始化
        self.path_error = None
        self.acc_list_dict = None
        self.sw_class = None
        self.settings_button = None
        self.error_frame = None
        self.main_frame = None
        self.scrollable_canvas = None
        self.start_time = None
        self.tab_frame = None
        self.sw = None
        self.get_data_thread = None

        self.root_class = GlobalMembers.root_class
        self.sw_classes = self.root_class.sw_classes
        self.root = self.root_class.root
        self.global_settings_value = self.root_class.global_settings_value
        self.hotkey_manager = self.root_class.hotkey_manager

    def init_login_ui(self):
        # 如果界面没有元素则自动刷新
        self.sw = subfunc_file.fetch_global_setting_or_set_default_or_none("login_tab")
        self.sw_class = self.sw_classes[self.sw]
        self.tab_frame = self.sw_class.frame
        if self.tab_frame is None or len(self.tab_frame.winfo_children()) == 0:
            self.refresh()
        else:
            self.refresh(True)

    def refresh(self, only_menu=False):
        """刷新菜单和界面"""
        print(f"登录页:刷新菜单与界面...")
        self.sw = subfunc_file.fetch_global_setting_or_set_default_or_none("login_tab")
        self.sw_class = self.sw_classes[self.sw]
        self.tab_frame = self.sw_class.frame

        # 刷新菜单
        config_data = subfunc_file.read_remote_cfg_in_rules()
        if config_data is None:
            messagebox.showerror("错误", "配置文件获取失败，将关闭软件，请检查网络后重启")
            self.root.destroy()

        # 路径检查
        self.sw_class.data_dir = SwInfoFunc.get_saved_path_of_(self.sw, LocalCfg.DATA_DIR)
        self.sw_class.inst_path = SwInfoFunc.get_saved_path_of_(self.sw, LocalCfg.INST_PATH)
        self.sw_class.dll_dir = SwInfoFunc.get_saved_path_of_(self.sw, LocalCfg.DLL_DIR)
        self.sw_class.ver = SwInfoFunc.calc_sw_ver(self.sw)

        try:
            self.root.after(0, self.root_class.menu_ui.create_root_menu_bar)
        except Exception as re:
            logger.error(re)
            messagebox.showerror("错误", "配置文件损坏，将关闭软件，请检查网络后重启")
            self.root.destroy()

        if only_menu is True:
            return
        # 刷新界面
        try:
            self.root.after(0, self.refresh_frame)
        except Exception as e:
            logger.error(e)
            self.root.after(3000, self.refresh_frame)

    def refresh_frame(self, sw=None):
        """加载或刷新主界面"""
        # 如果要刷新的页面不是当前选定选项卡，不用处理
        if sw is not None and sw != self.sw:
            return

        def _get_data_thread(callback):
            result = AccInfoFunc.get_sw_acc_list(self.root, self, self.sw)
            callback(result)

        self.start_time = time.time()
        print(f"计时开始：{time.time() - self.start_time:.4f}秒")
        _get_data_thread(self._update_result_from_result)

        # print(f"锁定刷新按钮...")
        # self.root_menu.edit_menu.entryconfig("刷新", state="disabled")
        print(f"获取登录状态...")
        self.root.after(0, self.create_main_ui)

    def _update_result_from_result(self, result):
        self.get_acc_list_answer = result

    def create_main_ui(self):
        """渲染主界面账号列表"""
        # 检测是否路径错误
        # if self.path_error is True:
        #     self.show_setting_error()
        success, result = self.get_acc_list_answer
        print(success, result)
        printer.print_vn(f"[{time.time() - self.start_time:.4f}s] 数据收集完成！")
        if success is not True:
            self.show_setting_error()
        else:
            self.create_account_list_ui()

        # print("创建完成，无论是错误界面还是正常界面，下面代码都要进行")

        # 恢复刷新可用性
        # self.root_menu.edit_menu.entryconfig("刷新", state="normal")

        # 加载完成后更新一下界面并且触发事件
        if self.scrollable_canvas is not None and self.scrollable_canvas.canvas.winfo_exists():
            self.scrollable_canvas.refresh_canvas()

    def create_account_list_ui(self):
        """账号列表获取成功，加载列表"""
        success, result = self.get_acc_list_answer

        def slowly_create():
            printer.vital("刷新")
            print(f"清除旧界面...")
            if self.tab_frame is not None and self.tab_frame.winfo_exists():
                print(self.tab_frame.winfo_children())
                for widget in self.tab_frame.winfo_children():
                    widget.destroy()

            ctk.set_appearance_mode("Light")
            # 底部框架=版本号+手动登录
            # bottom_frame = ctk.CTkFrame(self.tab_frame, corner_radius=0)  # padding 参数在 CTkFrame 里没有，可用 padx/pady
            # bottom_frame.pack(side=tk.BOTTOM, padx=5, pady=5)
            #
            # sw_ver = SwInfoFunc.calc_sw_ver(self.sw)
            # if sw_ver is not None:
            #     sw_ver_label = ctk.CTkLabel(bottom_frame, text=f"{sw_ver}", text_color="grey")
            #     sw_ver_label.pack(side=tk.BOTTOM, pady=2)
            bottom_frame = ttk.Frame(self.tab_frame, padding=Constants.BTN_FRAME_PAD)
            bottom_frame.pack(side=tk.BOTTOM)
            sw_ver = SwInfoFunc.calc_sw_ver(self.sw)
            if sw_ver is not None:
                sw_ver_label = ttk.Label(bottom_frame, text=f"{sw_ver}", foreground="grey")
                sw_ver_label.pack(side=tk.BOTTOM)
            # prefix = Strings.MUTEX_SIGN if has_mutex is True and self.global_settings_value.sign_vis else ""
            # manual_login_text = f"{prefix}手动登录"
            # manual_login_button = ttk.Button(bottom_frame, text=manual_login_text,
            #                                  command=self.to_manual_login, style='Custom.TButton')
            # manual_login_button.pack(side=tk.BOTTOM)

            self.is_original = False

            self.btn_switch = ttk.Button(bottom_frame, text="切换", command=self._switch_mode, width=40)
            self.btn_switch.pack(side="left", padx=5, pady=5)

            self.btn_login = ttk.Button(bottom_frame, text="共存登录", command=self.login_coexist, width=40)
            self.btn_login.pack(side="left", expand=True, fill="x", padx=5, pady=5)

            self.btn_extra = ttk.Button(bottom_frame, text="+", command=self.plus_action, width=40)
            self.btn_extra.pack(side="left", padx=5, pady=5)

            # 创建一个可以滚动的画布，并放置一个主框架在画布上
            self.scrollable_canvas = reusable_widgets.ScrollableCanvas(self.tab_frame)
            self.main_frame = self.scrollable_canvas.main_frame

        print(f"渲染账号列表...")
        acc_list_dict, has_mutex = result
        self.acc_list_dict = acc_list_dict
        logins = self.sw_class.login_accounts = acc_list_dict["login"]

        self.sw_class.view = subfunc_file.fetch_sw_setting_or_set_default_or_none(self.sw, "view")

        if self.sw_class.view == "classic":
            # 经典视图没有做快速刷新功能
            slowly_create()
            self.sw_class.classic_ui = classic_row_ui.ClassicLoginUI(result)

        elif self.sw_class.view == "tree":
            if self.quick_refresh_mode is True:
                try:
                    acc_list_dict, _ = result
                    tree_class = self.sw_class.tree_ui.tree_class
                    if all(tree_class[t].can_quick_refresh for t in tree_class):
                        # self.root.update_idletasks()
                        # time.sleep(5)
                        # 快速刷新
                        for t in tree_class:
                            tree_class[t].quick_refresh_items(acc_list_dict[t])
                except Exception as e:
                    logger.warning(e)
                    self.quick_refresh_mode = False
                    slowly_create()
                    self.sw_class.tree_ui = treeview_row_ui.TreeviewLoginUI(result)
            else:
                slowly_create()
                self.sw_class.tree_ui = treeview_row_ui.TreeviewLoginUI(result)
        else:
            pass

        subfunc_file.update_statistic_data(
            self.sw, 'refresh', self.sw_classes[self.sw].view, str(len(logins)), time.time() - self.start_time)
        last_msg = printer.print_vn(f"[{time.time() - self.start_time:.4f}s] 加载完成！")
        printer.last(last_msg)
        Printer().print_last()

        self.after_success_create_acc_ui_when_start()
        self.after_success_create_acc_ui()

    def login_coexist(self):
        print("共存登录")

    def login_original(self):
        print("原生登录")

    def plus_action(self):
        print("+")

    def lightning_action(self):
        print("⚡")

    def _switch_mode(self):
        self.is_original = not self.is_original
        if self.is_original:
            self.btn_login.configure(text="原生登录", command=self.login_original)
            self.btn_extra.configure(text="⚡", command=self.lightning_action)
        else:
            self.btn_login.configure(text="共存登录", command=self.login_coexist)
            self.btn_extra.configure(text="+", command=self.plus_action)

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
                                          command=partial(WndCreator.open_sw_settings, self.sw))
        self.settings_button.pack()

    """后处理"""

    def after_success_create_acc_ui_when_start(self):
        """首次启动后，成功创建账号列表才会执行"""
        if self.root_class.first_created_acc_ui is True:
            return

        # 需要进行的操作
        MultiSwFunc.thread_to_login_auto_start_accounts()

        self.root_class.first_created_acc_ui = True

    def after_success_create_acc_ui(self):
        """成功创建账号列表才会执行"""
        # 获取已登录的窗口hwnd
        logins = self.acc_list_dict[OnlineStatus.LOGIN]
        AccInfoFunc.get_main_hwnd_of_accounts(self.sw, logins)

        # 进行静默获取头像及配置
        def func():
            AccInfoFunc.silent_get_and_config(self.sw)

        threading.Thread(target=func).start()

        # 先停止旧的监听线程
        self.hotkey_manager.stop_hotkey_listener()
        # 更新快捷键
        self.hotkey_manager.load_hotkeys_from_json(Config.TAB_ACC_JSON_PATH)
        # 开启监听线程
        self.hotkey_manager.start_hotkey_listener()

        # 刷新设置菜单
        # self.root_menu.create_setting_menu()

    """功能区"""

    def to_manual_login(self):
        """按钮：手动登录"""
        print("手动登录")
        try:
            SwOperator.start_thread_to_manual_login(self.sw)
        except Exception as e:
            logger.error(e)

    def to_auto_login(self, items):
        """登录所选账号"""
        login_dict = LoginUI._items_to_dict(items)
        if self.global_settings_value.hide_wnd is True:
            self.root.iconify()  # 最小化主窗口
        try:
            AccOperator.start_auto_login_accounts_thread(login_dict)
        except Exception as e:
            logger.error(e)

    def to_create_config(self, items):
        """按钮：创建或重新配置"""
        accounts = [items.split("/")[1] for items in items]
        threading.Thread(target=AccOperator.open_sw_and_ask,
                         args=(self.sw, accounts[0], self.sw_classes[self.sw].multirun_mode)).start()

    @staticmethod
    def to_create_starter(items):
        sw_accounts_dict = LoginUI._items_to_dict(items)
        success, err = AccOperator.create_starter_lnk_for_accounts(sw_accounts_dict)
        if success is True:
            messagebox.showinfo("提示", "创建成功")
        else:
            err_str = "\n".join([f"{e}:{m}" for e, m in err.items()])
            messagebox.showwarning("警告", err_str)

    def to_quit_accounts(self, items):
        """退出所选账号"""
        accounts = [items.split("/")[1] for items in items]
        answer = AccOperator.quit_selected_accounts(self.sw, accounts)
        if answer is True:
            self.refresh_frame(self.sw)

    @staticmethod
    def _items_to_dict(items):
        login_dict = {}
        for item in items:
            sw, acc = item.split("/")
            if sw not in login_dict:
                login_dict[sw] = []
            login_dict[sw].append(acc)
        return login_dict
