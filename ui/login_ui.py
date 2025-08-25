import threading
import time
from functools import partial
from tkinter import ttk, messagebox

from components.custom_widgets import CustomCornerBtn
from components.widget_wrappers import ScrollableCanvasW
from functions import subfunc_file
from functions.acc_func import AccInfoFunc, AccOperator
from functions.main_func import MultiSwFunc
from functions.sw_func import SwOperator, SwInfoFunc
from public import Config, Strings
from public.enums import OnlineStatus, LocalCfg
from public.global_members import GlobalMembers
from ui.cfg_manager_ui import CfgManagerWndCreator
from ui.classic_row_ui import ClassicLoginUI
from ui.exe_manager_ui import ExeManagerWndCreator
from ui.treeview_row_ui import TreeviewLoginUI
from ui.wnd_ui import WndCreator
from utils.logger_utils import mylogger as logger, Printer
from utils.logger_utils import myprinter as printer


# TODO: 登录页面底部按钮状态要同步更改

class LoginUI:
    """构建主窗口的类"""

    def __init__(self):
        self.btn_extra = None
        self.btn_login = None
        self.is_original = None
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
        self.sw_class.data_dir = SwInfoFunc.try_get_path_of_(self.sw, LocalCfg.DATA_DIR)
        self.sw_class.inst_path = SwInfoFunc.try_get_path_of_(self.sw, LocalCfg.INST_PATH)
        self.sw_class.dll_dir = SwInfoFunc.try_get_path_of_(self.sw, LocalCfg.DLL_DIR)
        self.sw_class.ver = SwInfoFunc.calc_sw_ver(self.sw)

        # 创建菜单
        try:
            self.root.after(0, self.root_class.menu_ui.create_root_menu_bar)
        except Exception as re:
            logger.error(re)
            messagebox.showerror("错误", "配置文件损坏，将关闭软件，请检查网络后重启")
            self.root.destroy()

        if not (only_menu is True):
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
        printer.print_vn(f"[{time.time() - self.start_time:.4f}s] 进程检测完成！")
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

    def _ui_pre_load(self):
        printer.vital("刷新")
        print(f"清除旧界面...")
        if self.tab_frame is not None and self.tab_frame.winfo_exists():
            print(self.tab_frame.winfo_children())
            for widget in self.tab_frame.winfo_children():
                widget.destroy()

        bottom_frame = ttk.Frame(self.tab_frame, padding=Config.BTN_FRAME_PAD)
        bottom_frame.pack(side='bottom')
        sw_ver = SwInfoFunc.calc_sw_ver(self.sw)
        if sw_ver is not None:
            sw_ver_label = ttk.Label(bottom_frame, text=f"{sw_ver}", foreground="grey")
            sw_ver_label.pack(side='bottom')

        self.is_original = False
        btn_height = 35
        self.btn_switch = CustomCornerBtn(
            bottom_frame, text="⇄", width=btn_height, height=btn_height, corner_radius=12)
        self.btn_switch.pack(side="left", padx=5, pady=5)
        self.btn_switch.set_bind_map(**{"1": self._switch_mode}).apply_bind(self.root)

        self.btn_login = CustomCornerBtn(
            bottom_frame, text="共存登录", width=80, height=btn_height, corner_radius=4)
        self.btn_login.pack(side="left", expand=True, fill="x", padx=0, pady=5)
        self.btn_login.set_bind_map(**{"1": self._to_manual_login}).apply_bind(self.root)

        # self.btn_extra = CustomCornerBtn(
        #     bottom_frame, text="+", width=btn_height, height=btn_height, corner_radius=4)
        # self.btn_extra.pack(side="left", expand=True, fill="x", padx=0, pady=5)
        # self.btn_extra.set_bind_map(**{"1": self._to_extra_func}).apply_bind(self.root)

        self.btn_mng = CustomCornerBtn(
            bottom_frame, text=Strings.MNG_SIGN, width=btn_height, height=btn_height, corner_radius=4)
        self.btn_mng.pack(side="left", expand=True, fill="x", padx=0, pady=5)
        self.btn_mng.set_bind_map(**{"1": self._to_mng_func}).apply_bind(self.root)

        # 创建一个可以滚动的画布，并放置一个主框架在画布上
        self.scrollable_canvas = ScrollableCanvasW(self.tab_frame)
        self.main_frame = self.scrollable_canvas.main_frame

    def create_account_list_ui(self):
        """账号列表获取成功，加载列表"""
        success, result = self.get_acc_list_answer
        print(f"渲染账号列表...")
        acc_list_dict, has_mutex = result
        self.acc_list_dict = acc_list_dict
        logins = self.sw_class.login_accounts = acc_list_dict["login"]

        self.sw_class.view = subfunc_file.fetch_sw_setting_or_set_default_or_none(self.sw, "view")

        if self.sw_class.view == "classic":
            # 经典视图没有做快速刷新功能
            self._ui_pre_load()
            self.sw_class.classic_ui = ClassicLoginUI(result)

        elif self.sw_class.view == "tree":
            if self.quick_refresh_mode is True:
                try:
                    acc_list_dict, _ = result
                    table = self.sw_class.treeview_ui.table_classes
                    self.sw_class.treeview_ui.acc_list_dict = acc_list_dict
                    if all(table[t].can_quick_refresh for t in table):
                        # 快速刷新
                        for t in table:
                            # tree_class[t].quick_refresh_items(acc_list_dict[t])
                            table[t].quick_refresh_items()
                except Exception as e:
                    logger.warning(e)
                    self.quick_refresh_mode = False
                    self._ui_pre_load()
                    self.sw_class.treeview_ui = TreeviewLoginUI(result)
            else:
                self._ui_pre_load()
                self.sw_class.treeview_ui = TreeviewLoginUI(result)
        else:
            pass

        subfunc_file.update_statistic_data(
            self.sw, 'refresh', self.sw_classes[self.sw].view, str(len(logins)), time.time() - self.start_time)
        last_msg = printer.print_vn(f"[{time.time() - self.start_time:.4f}s] 加载完成！")
        printer.last(last_msg)
        Printer().print_last()

        self.after_success_create_acc_ui_when_start()
        self.after_success_create_acc_ui()

    def _to_manual_login(self):
        if self.is_original is not True:
            print("共存登录")
            SwOperator.start_thread_to_manual_login_coexist(self.sw)

        else:
            print("原生登录")
            SwOperator.start_thread_to_manual_login_origin(self.sw)

    def _to_mng_func(self):
        if self.is_original is not True:
            print("共存程序管理")
            ExeManagerWndCreator.open_exe_manager_wnd()
        else:
            print("原生配置管理")
            CfgManagerWndCreator.open_cfg_manager_wnd()

    def _switch_mode(self):
        self.is_original = not self.is_original
        if self.is_original:
            self.btn_login.set_text("原生登录").redraw()
            self.btn_mng.set_text(Strings.MNG_SIGN).redraw()
        else:
            self.btn_login.set_text("共存登录").redraw()
            self.btn_mng.set_text(Strings.MNG_SIGN).redraw()

    def show_setting_error(self):
        """出错的话，选择已经有的界面中创建错误信息显示"""
        if self.tab_frame is not None:
            for widget in self.tab_frame.winfo_children():
                widget.destroy()
            self.error_frame = ttk.Frame(self.tab_frame, padding=Config.T_FRM_PAD)

        self.error_frame.pack(**Config.T_FRM_PACK)
        error_label = ttk.Label(self.error_frame, text="路径设置错误，请点击按钮修改", foreground="red",
                                anchor="center")
        error_label.pack(**Config.T_WGT_PACK)
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

        # 进行静默获取头像及配置, 获取已登录的窗口hwnd
        def func():
            AccOperator.silent_get_and_config(self.sw)
            logins = self.acc_list_dict[OnlineStatus.LOGIN]
            AccInfoFunc.bind_main_wnd_to_accounts_in_sw(self.sw, logins)

        threading.Thread(target=func).start()

        # 先停止旧的监听线程
        self.hotkey_manager.stop_hotkey_listener()
        # 更新快捷键
        self.hotkey_manager.load_hotkeys_from_json(Config.TAB_ACC_JSON_PATH)
        # 开启监听线程
        self.hotkey_manager.start_hotkey_listener()

    """功能区"""

    def to_manual_login(self):
        """按钮：手动登录"""
        print("手动登录")
        try:
            SwOperator.start_thread_to_manual_login_origin(self.sw)
        except Exception as e:
            logger.error(e)

    def to_auto_login(self, items):
        """登录所选账号"""
        login_dict = LoginUI._items_to_dict(items)
        Printer().vital("自动登录")
        hide_wnd = self.global_settings_value.hide_wnd
        Printer().print_vn(f"[INFO]登录前隐藏主窗口: {hide_wnd}")
        if hide_wnd is True:
            self.root.iconify()  # 最小化主窗口
        try:
            AccOperator.start_auto_login_accounts_thread(login_dict)
        except Exception as e:
            logger.error(e)

    def to_create_config(self, items):
        """按钮：创建或重新配置"""
        accounts = [items.split("/")[1] for items in items]
        threading.Thread(target=AccOperator.open_sw_and_ask,
                         args=(self.sw, accounts[0])).start()

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
        accounts = [item.split("/")[1] for item in items]
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
