# main_ui.py
import json
import os
import random
import sys
import threading
from tkinter import ttk, messagebox

import keyboard
from PIL import ImageTk

from components import CustomNotebook
from components.widget_wrappers import StatusBarW, ProgressBarW
from functions import subfunc_file
from functions.acc_func import AccOperator
from functions.app_func import AppFunc, AppInfo, GlobalSettings
from functions.sw_func import SwInfoFunc, Sw
from public import Config, Strings
from public.enums import LocalCfg, SwStates, RemoteCfg
from public.global_members import GlobalMembers
from ui import login_ui, acc_manager_ui, sw_manager_ui
from ui.menu_ui import MenuUI
from ui.wnd_ui import WndCreator
from utils import hwnd_utils, image_utils
from utils.logger_utils import mylogger as logger, Logger, Printer
from utils.widget_utils import WidgetUtils


# ------------------------------------------------------------------
# 本程序文件层次:
# main_ui > 基本ui > 窗口ui
# > acc_func > sw_func > app_func
# > utils
# > component
# > public
# ------------------------------------------------------------------


class RootClass:
    """
    构建主窗口的类,属于全局的成员放在这里
    管理ui: 根界面root_ui,菜单menu_ui,账号管理acc_manager_ui,软件管理sw_manager_ui,账号登录页acc_tab_ui
    管理数据: 全局配置global_settings,软件配置sw_classes
    """

    def __init__(self, root, args=None):
        # 代理接管属性
        self._main_frame = None
        self._root = root
        self._root_frame = None
        self._menu_ui = None
        self._main_ui = None
        self._sw_manager_ui = None
        self._login_ui = None
        self._acc_manager_ui = None

        # 全局化
        GlobalMembers.root_class = self
        self.root_class = self
        # 程序参数
        self.debug = args.debug
        self.new = args.new

        self.hotkey_manager = None
        self.statusbar_ui = None
        # 加载标志
        self.first_created_acc_ui = None
        self.finish_started = None
        # 全局数据
        self.sw_classes: dict = {}
        self.remote_cfg_data = None
        self.global_settings_value = None
        self.global_settings_var = None
        self.app_info = AppInfo()

        # 创建基本的窗口元素: 状态栏, 进度条, 主框架
        self.root = root
        self.root.withdraw()  # 初始化时隐藏主窗口
        self.root_frame.pack(expand=True, fill='both')
        if self.statusbar_ui is None or not self.statusbar_ui.status_bar.winfo_exists():
            self.statusbar_ui = StatusBarW(self.root, self.root_frame, self.debug)
        if self.debug:
            self.statusbar_ui.status_bar.bind("<Button-1>", lambda event: WndCreator.open_debug_window())
        print(f"状态栏加载完成!")
        self.top_bar_frame = ttk.Frame(self.root_frame)
        self.top_bar_frame.config(height=10)
        self.top_bar_frame.pack_propagate(False)
        self.top_bar_frame.pack(side="bottom", fill="x")
        self.progress_bar = ProgressBarW(self.top_bar_frame)
        self.main_frame.pack(expand=True, fill='both')

        hwnd_utils.set_size_and_bring_tk_wnd_to_(self.root, *Config.ROOT_WND_SIZE)
        self.root.deiconify()

        # 设置主窗口
        title = os.path.basename(sys.argv[0])
        print(f"获取窗口名为: {title}")
        try:
            remote_title, = subfunc_file.get_remote_cfg(RemoteCfg.GLOBAL, app_name=None)
            title = remote_title or title
            self._safe_set_icon()
        except Exception as e:
            Logger().error(e)
        finally:
            print(f"设置窗口名为: {title}")
            self.root.title(title)
            self.after_refresh_when_start()

        # -初始化构建窗口内容...
        self.initialize_in_root()
        # self.root.after(200, self.initialize_in_root)
        # -初次使用
        if self.new is True:
            self.root.after(3000, WndCreator.open_update_log)
            self.root.after(3000, lambda: AppFunc.mov_backup(new=self.new))

    def _safe_set_icon(self):
        """
        安全设置窗口图标
        """
        try:
            # 1. 外部图标
            self.root.iconbitmap(Config.PROJ_ICO_PATH)
            return
        except Exception as e:
            Logger().error(e)
        try:
            # 2. exe 内置图标
            exe_path = sys.executable
            icon_image = image_utils.extract_icon_image(exe_path)
            tk_icon = ImageTk.PhotoImage(icon_image)
            self.root.iconphoto(True, tk_icon)
            self.root._tk_icon_ref = tk_icon  # 防止被垃圾回收
            return
        except Exception as e:
            Logger().error(e)

    @property
    def root_frame(self):
        """代理：始终返回一个存活的 Frame"""
        if not (self._root_frame and self._root_frame.winfo_exists()):
            self._root_frame = ttk.Frame(self._root)
        return self._root_frame

    @root_frame.setter
    def root_frame(self, _):
        """禁止外部重设"""
        raise AttributeError("root_frame 是只读属性，不允许重新赋值")

    @property
    def main_frame(self):
        """代理：始终返回一个存活的 Frame"""
        if not (self._main_frame and self._main_frame.winfo_exists()):
            self._main_frame = ttk.Frame(self.root_frame)
        return self._main_frame

    @main_frame.setter
    def main_frame(self, _):
        """禁止外部重设"""
        raise AttributeError("main_frame 是只读属性，不允许重新赋值")

    @property
    def main_ui(self):
        if not isinstance(self._main_ui, MainUI):
            self._main_ui = MainUI(self.root, self.main_frame)
        return self._main_ui

    @main_ui.setter
    def main_ui(self, value):
        self._main_ui = value

    @property
    def menu_ui(self):
        if not isinstance(self._menu_ui, MenuUI):
            self._menu_ui = MenuUI()
        return self._menu_ui

    @menu_ui.setter
    def menu_ui(self, value):
        self._menu_ui = value

    @property
    def acc_manager_ui(self):
        if self._acc_manager_ui is None:
            self._acc_manager_ui = acc_manager_ui.AccManagerUI(self.root, self.main_ui.acc_mng_frame)
        return self._acc_manager_ui

    @acc_manager_ui.setter
    def acc_manager_ui(self, value):
        self._acc_manager_ui = value

    @property
    def sw_manager_ui(self):
        if self._sw_manager_ui is None:
            self._sw_manager_ui = sw_manager_ui.SwManagerUI(self.root, self.main_ui.sw_mng_frame)
        return self._sw_manager_ui

    @sw_manager_ui.setter
    def sw_manager_ui(self, value):
        self._sw_manager_ui = value

    @property
    def login_ui(self):
        if self._login_ui is None:
            self._login_ui = login_ui.LoginUI()
        return self._login_ui

    @login_ui.setter
    def login_ui(self, value):
        self._login_ui = value

    @staticmethod
    def _ensure_file_resources_exists():
        # 检查项目根目录中是否有 user_files 这个文件夹，没有则创建
        if not os.path.exists(Config.PROJ_USER_PATH):  # 如果路径不存在
            os.makedirs(Config.PROJ_USER_PATH)  # 创建 user_files 文件夹
            print(f"已创建文件夹: {Config.PROJ_USER_PATH}")

    @staticmethod
    def _set_tk_style():
        # 统一管理style
        style = ttk.Style()
        style.configure('Custom.TButton', padding=Config.TK_BTN_PAD,
                        width=Config.TK_BTN_WIDTH, relief="sunken", borderwidth=3)
        style.configure("Treeview")
        style.configure('FirstTitle.TLabel', font=("", Config.FIRST_TITLE_FONTSIZE, "bold"))
        style.configure('Link.TLabel', font=("", Config.LINK_FONTSIZE), foreground="grey")
        style.configure('SecondTitle.TLabel', font=("", Config.SECOND_TITLE_FONTSIZE))
        style.configure("RedWarning.TLabel", foreground="red", font=("", Config.LITTLE_FONTSIZE))
        style.configure("LittleText.TLabel", font=("", Config.LITTLE_FONTSIZE))
        style.configure("LittleGreyText.TLabel", font=("", Config.LITTLE_FONTSIZE), foreground="grey")
        style.configure("RowTreeview", background="#FFFFFF", foreground="black",
                        rowheight=Config.TREE_ROW_HEIGHT, selectmode="extended")
        style.layout("RowTreeview", style.layout("Treeview"))  # 继承默认布局
        style.configure("SidebarTreeview", background="#FFFFFF", foreground="black",
                        rowheight=Config.TREE_ROW_HEIGHT, selectmode="extended",
                        borderwidth=0, highlightthickness=0)
        style.layout("SidebarTreeview", style.layout("Treeview"))  # 继承默认布局
        style.configure("Mutex.TLabel", foreground="red")

    def with_progress_factory(self):
        """将self传入, 返回一个装饰器, 这个装饰器将对装饰的函数过程收尾添加进度条的展示和结束."""

        def decorator(func):
            def wrapper(*args, **kwargs):
                self.root.after(0, self.progress_bar.loading)
                try:
                    return func(*args, **kwargs)
                finally:
                    self.root.after(0, self.progress_bar.finished)

            return wrapper

        return decorator

    def initialize_in_root(self):
        """初始化加载"""

        def _thread():
            self._ensure_file_resources_exists()
            AppFunc.apply_proxy_setting()
            self.remote_cfg_data = subfunc_file.read_remote_cfg_in_rules()
            if self.remote_cfg_data is None:
                messagebox.showerror("错误", "未找到配置文件，将退出程序，请检查网络设置，稍后重试")
                self.root.destroy()
                return
            self._set_tk_style()

            self.global_settings_value = GlobalSettings()
            self.global_settings_var = GlobalSettings()
            self.hotkey_manager = HotkeyManager()

            self.root.after(0, self.main_ui.initialize_in_root_main_ui)

        _thread()
        # threading.Thread(target=_thread).start()

    def reinit_root_ui(self):
        """重新加载主窗口UI"""

        def _thread():
            AppFunc.apply_proxy_setting()
            self.remote_cfg_data = subfunc_file.read_remote_cfg_in_rules()
            if self.remote_cfg_data is None:
                messagebox.showerror("错误", "未找到配置文件，将退出程序，请检查网络设置，稍后重试")
                self.root.destroy()
                return
            self._set_tk_style()

            # 重置变量
            self.main_ui = None
            self.menu_ui = None
            self.login_ui = None
            self.acc_manager_ui = None
            self.sw_manager_ui = None
            self.global_settings_value = GlobalSettings()
            self.global_settings_var = GlobalSettings()
            self.hotkey_manager = HotkeyManager()

            self.root.after(0, hwnd_utils.set_size_and_bring_tk_wnd_to_, self.root, *Config.ROOT_WND_SIZE)
            self.root.after(0, self.main_ui.initialize_in_root_main_ui)

        _thread()
        # threading.Thread(target=_thread).start()

    def after_refresh_when_start(self):
        """首次启动后，无论是否成功创建账号列表，都执行"""
        if self.finish_started is True:
            return
        # 需要进行的操作
        pass
        self.finish_started = True


class MainUI:
    """主界面包装类"""

    def __init__(self, wnd, frame):
        self.top_bar_frame = None
        self._root_nb_cls = None
        self._sw_mng_frame = None
        self._acc_mng_frame = None
        self._login_nb_frame = None
        self._manage_nb_frame = None
        self._login_nb_cls = None
        self._manage_nb_cls = None
        print("构建根UI...")
        self.login_nb_frame = None
        self.manage_nb_frame = None
        self.sw_classes = {}
        self.root_nb_cls = None
        self.manage_nb_cls = None
        self.login_nb_cls = None
        self.login_frm_pool = None
        self.sw = None
        self.acc_mng_frame = None
        self.sw_mng_frame = None
        self.scrollable_canvas = None

        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root
        self.wnd = wnd
        self.main_frame = frame

    def initialize_in_root_main_ui(self):
        # self.top_bar_frame = ttk.Frame(self.main_frame)
        # self.top_bar_frame.config(height=10)
        # self.top_bar_frame.pack_propagate(False)
        # self.top_bar_frame.pack(side="top", fill="x")
        # self.progress_bar = TopProgressBar(self.top_bar_frame)
        self._load_root_nb_frame()
        threading.Thread(target=self._get_path_thread).start()
        root_tab = AppFunc.get_global_setting_value_by_local_record(LocalCfg.ROOT_TAB)
        self.root_nb_cls.select(root_tab)

    def _load_root_nb_frame(self):
        # 清理界面
        WidgetUtils.clear_all_children_of_frame(self.main_frame)
        # 主页面="管理"+"登录"
        root_nb_cls = self.root_nb_cls = CustomNotebook(self.root, self.main_frame)
        self.root_nb_cls.select_callback = self._on_tab_in_root_selected
        root_nb_cls.set_major_color(selected_bg='#00FF00')
        root_nb_frm_pool = root_nb_cls.frames_pool
        self.login_nb_frame = ttk.Frame(root_nb_frm_pool)
        self.manage_nb_frame = ttk.Frame(root_nb_frm_pool)

        self.used_refresh = AppFunc.get_global_setting_value_by_local_record(LocalCfg.USED_REFRESH)
        suffix = "" if self.used_refresh is True else Strings.REFRESH_HINT
        root_nb_cls.add("manage", f"管理{suffix}", self.manage_nb_frame)
        root_nb_cls.add("login", "登录", self.login_nb_frame)
        pass

    def _load_manage_frame(self):
        # 清理界面
        WidgetUtils.clear_all_children_of_frame(self.manage_nb_frame)
        # "管理"="平台"+"账号"
        manage_nb_cls = self.manage_nb_cls = CustomNotebook(self.root, self.manage_nb_frame)
        self.manage_nb_cls.select_callback = self._on_tab_in_manage_selected
        self.manage_frm_pool = manage_frm_pool = manage_nb_cls.frames_pool
        self.sw_mng_frame = ttk.Frame(manage_frm_pool)
        self.acc_mng_frame = ttk.Frame(manage_frm_pool)
        manage_nb_cls.add("acc", "账号", self.acc_mng_frame)
        manage_nb_cls.add("sw", "平台", self.sw_mng_frame)
        pass

    def _load_login_frame(self):
        # 清理界面
        WidgetUtils.clear_all_children_of_frame(self.login_nb_frame)
        # "登录"=∑各平台
        login_nb_cls = self.login_nb_cls = CustomNotebook(self.root, self.login_nb_frame)
        self.login_nb_cls.select_callback = self._on_tab_in_login_selected
        self.login_frm_pool = login_nb_cls.frames_pool
        # 加载各平台
        sp_sw, = subfunc_file.get_remote_cfg(RemoteCfg.GLOBAL, **{RemoteCfg.SP_SW: []})
        if not isinstance(sp_sw, list):
            return
        for sw in sp_sw:
            # 使用枚举类型保证其位于正确的状态
            state = SwInfoFunc.get_sw_setting_by_local_record(sw, LocalCfg.STATE, SwStates)
            if not state == SwStates.VISIBLE and not state == SwStates.HIDDEN:
                continue
            try:
                if sw in self.sw_classes:
                    sw_cls = self.sw_classes[sw]
                    if not isinstance(sw_cls, Sw):
                        sw_cls = Sw(sw)
                else:
                    sw_cls = Sw(sw)
            except Exception as e:
                logger.warning(e)
                sw_cls = Sw(sw)
                self.sw_classes[sw] = sw_cls
            print(f"更新{sw}的信息体...")
            if state == SwStates.VISIBLE:
                sw_cls.frame = ttk.Frame(self.login_frm_pool)
                sw_cls.label = SwInfoFunc.get_sw_origin_display_name(sw)
                self.login_nb_cls.add(sw, sw_cls.label, sw_cls.frame)
            self.root_class.sw_classes[sw] = sw_cls
            self.sw_classes[sw] = sw_cls
        if len(self.login_nb_cls.tabs) == 0:
            hint = self._get_random_hint()
            tmp_label = ttk.Label(self.login_frm_pool, text=hint, style="FirstTitle.TLabel")
            tmp_label.pack(pady=200, fill="y", expand=True)

    @staticmethod
    def _get_path_thread():
        sp_sw, = subfunc_file.get_remote_cfg(RemoteCfg.GLOBAL, **{RemoteCfg.SP_SW: []})
        if not isinstance(sp_sw, list):
            return
        for sw in sp_sw:
            # 使用枚举类型保证其位于正确的状态
            state = SwInfoFunc.get_sw_setting_by_local_record(sw, LocalCfg.STATE, SwStates)
            if not state == SwStates.VISIBLE and not state == SwStates.HIDDEN:
                continue
            print(f"创建{sw}的信息体...")
            sw_cls = Sw(sw)
            sw_cls.data_dir = SwInfoFunc.try_get_path_of_(sw, LocalCfg.DATA_DIR)
            sw_cls.inst_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.INST_PATH)
            sw_cls.dll_dir = SwInfoFunc.try_get_path_of_(sw, LocalCfg.DLL_DIR)
            sw_cls.ver = SwInfoFunc.calc_sw_ver(sw)
        Printer().print_last()

    def _on_tab_in_root_selected(self, click_time):
        """根标签切换时,将自动选择下一级的标签"""
        root_tab = self.root_nb_cls.curr_tab_id
        subfunc_file.update_settings(LocalCfg.GLOBAL_SECTION, **{LocalCfg.ROOT_TAB: root_tab})
        tab_dict = self.root_nb_cls.tabs[root_tab]
        tab_text = tab_dict["text"]
        if root_tab == "manage":
            if click_time <= 1:
                # 检测,没有则加载管理标签下的页面
                manage_nb_cls = self.manage_nb_cls
                if not isinstance(manage_nb_cls, CustomNotebook):
                    self._load_manage_frame()
                pass
            elif click_time >= 2:
                # 首次使用,消除提示
                if self.used_refresh is not True:
                    tab_text = tab_text.replace(Strings.REFRESH_HINT, "")
                    subfunc_file.update_settings(LocalCfg.GLOBAL_SECTION, **{LocalCfg.USED_REFRESH: True})
                    self.used_refresh = True
                tab_dict["tab_widget"].set_text(f"⟳{tab_text}").redraw()
                self.root.update_idletasks()
                self.root_class.acc_manager_ui = None
                self.root_class.sw_manager_ui = None
                self._load_manage_frame()
                tab_dict["tab_widget"].set_text(tab_text).redraw()
            # 自动选择下一级标签
            manage_tab = self.manage_nb_cls.curr_tab_id
            if not manage_tab:
                manage_tab = AppFunc.get_global_setting_value_by_local_record(LocalCfg.MNG_TAB)
            try:
                self.manage_nb_cls.select(manage_tab)
            except Exception as e:
                logger.warning(e)
                self.manage_nb_cls.select(next(iter(self.manage_nb_cls.tabs.keys())))

        elif root_tab == "login":
            if click_time <= 1:
                # 检测,没有则加载登录标签下的页面
                login_nb_cls = self.login_nb_cls
                if not isinstance(login_nb_cls, CustomNotebook):
                    self._load_login_frame()
            elif click_time >= 2:
                tab_dict["tab_widget"].set_text(f"⟳{tab_text}").redraw()
                self.root.update_idletasks()
                self.root_class.login_ui = None
                self._load_login_frame()
                tab_dict["tab_widget"].set_text(tab_text).redraw()
            # 自动选择下一级标签
            login_tab = self.login_nb_cls.curr_tab_id
            if not login_tab:
                login_tab = AppFunc.get_global_setting_value_by_local_record(LocalCfg.LOGIN_TAB)
            try:
                self.login_nb_cls.select(login_tab)
            except Exception as e:
                logger.warning(e)
                if len(self.login_nb_cls.tabs) > 0:
                    self.login_nb_cls.select(next(iter(self.login_nb_cls.tabs.keys())))

    def _on_tab_in_login_selected(self, click_time):
        self.root_class.login_ui.sw = self.login_nb_cls.curr_tab_id
        tab_dict = self.login_nb_cls.tabs[self.root_class.login_ui.sw]
        tab_text = tab_dict["text"]
        print(f"当前是{self.root_class.login_ui.sw}的标签页")
        subfunc_file.update_settings(
            LocalCfg.GLOBAL_SECTION, **{LocalCfg.LOGIN_TAB: self.root_class.login_ui.sw})
        if click_time <= 1:
            self.root_class.login_ui.init_login_ui()
        elif click_time >= 2:
            tab_dict["tab_widget"].set_text(f"⟳{tab_text}").redraw()
            self.root.update_idletasks()
            self.root_class.login_ui.refresh()
            tab_dict["tab_widget"].set_text(tab_text).redraw()

    def _on_tab_in_manage_selected(self, click_time):
        self.manage_tab = self.manage_nb_cls.curr_tab_id
        subfunc_file.update_settings(
            LocalCfg.GLOBAL_SECTION, **{LocalCfg.MNG_TAB: self.manage_tab})
        tab_dict = self.manage_nb_cls.tabs[self.manage_tab]
        tab_text = tab_dict["text"]
        if self.manage_tab == "acc":
            if click_time <= 1:
                self.root_class.acc_manager_ui.init_acc_manager_ui()
            elif click_time >= 2:
                tab_dict["tab_widget"].set_text(f"⟳{tab_text}").redraw()
                self.root.update_idletasks()
                self.root_class.acc_manager_ui.refresh()
                tab_dict["tab_widget"].set_text(tab_text).redraw()

        elif self.manage_tab == "sw":
            if click_time <= 1:
                self.root_class.sw_manager_ui.init_sw_manager_ui()
            elif click_time >= 2:
                tab_dict["tab_widget"].set_text(f"⟳{tab_text}").redraw()
                self.root.update_idletasks()
                self.root_class.sw_manager_ui.refresh()
                tab_dict["tab_widget"].set_text(tab_text).redraw()

    @staticmethod
    def _get_random_hint():
        # 从所有文案中打乱后随机选一个
        all_messages = sum(Strings.PLATFORM_DISABLED_HINTS.values(), [])
        return random.choice(all_messages)

    def refresh_current_tab(self, quick=True):
        """刷新当前标签页"""
        root_tab = self.root_nb_cls.curr_tab_id
        if root_tab == "manage":
            manage_tab = self.manage_nb_cls.curr_tab_id
            if manage_tab == "acc":
                self.root_class.acc_manager_ui.quick_refresh_mode = quick
                self.root_class.acc_manager_ui.refresh()
            elif manage_tab == "sw":
                self.root_class.sw_manager_ui.quick_refresh_mode = quick
                self.root_class.sw_manager_ui.refresh()
        elif root_tab == "login":
            self.root_class.login_ui.quick_refresh_mode = quick
            self.root_class.login_ui.refresh()


class HotkeyManager:
    def __init__(self):
        self.listener_thread = None
        self.stop_event = None

        self.hotkey_map = {
        }
        self.root_class = GlobalMembers.root_class

        self.listener_thread = None  # 监听线程
        self.stop_event = threading.Event()  # 用于控制线程退出

        # 在子线程中运行监听
        listener_thread = threading.Thread(target=self.start_hotkey_listener, daemon=True)
        listener_thread.start()

    def load_hotkeys_from_json(self, json_path):
        """ 从 JSON 文件加载快捷键映射 """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        hotkey_map = {}
        for sw, accounts in data.items():
            for acc, details in accounts.items():
                if isinstance(details, dict) and "hotkey" in details:
                    hotkey = details["hotkey"]
                    if hotkey is not None and hotkey != "":  # 确保 hotkey 不是 None 或 空字符串
                        hotkey_map[hotkey] = \
                            lambda software=sw, account=acc: AccOperator.switch_to_sw_account_wnd(
                                f"{software}/{account}")

        # 更新映射
        self.hotkey_map = hotkey_map
        # print(self.hotkey_map)

    def start_hotkey_listener(self):
        """ 启动全局快捷键监听 """
        if self.listener_thread and self.listener_thread.is_alive():
            return  # 避免重复启动

        # 先清除之前的快捷键绑定
        keyboard.unhook_all()

        # 注册新的快捷键
        for hk in self.hotkey_map:
            keyboard.add_hotkey(hk, lambda hotkey=hk: self.execute_task(hotkey))

        # 启动监听线程
        self.stop_event.clear()
        self.listener_thread = threading.Thread(target=self._hotkey_listener, daemon=True)
        self.listener_thread.start()

    def _hotkey_listener(self):
        """ 热键监听线程，等待退出信号 """
        while not self.stop_event.is_set():
            Logger().info("监听快捷键中...")
            keyboard.wait()  # 等待快捷键事件，直到 stop_event 触发

    def stop_hotkey_listener(self):
        """ 停止全局快捷键监听 """
        if self.listener_thread and self.listener_thread.is_alive():
            self.stop_event.set()  # 设置退出信号
            keyboard.unhook_all()  # 取消所有快捷键监听
            self.listener_thread = None  # 清除线程引用

    def execute_task(self, hotkey):
        if hotkey in self.hotkey_map:
            self.hotkey_map[hotkey]()  # 执行绑定的任务
