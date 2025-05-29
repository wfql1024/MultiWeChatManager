# main_ui.py
import json
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import keyboard

from functions import subfunc_file
from functions.acc_func import AccOperator
from functions.app_func import AppFunc
from functions.sw_func import SwInfoFunc
from public_class import reusable_widgets
from public_class.custom_widget import CustomNotebook
from public_class.enums import LocalCfg, SwStates, RemoteCfg
from public_class.global_members import GlobalMembers
from resources import Config, Constants
from ui import login_ui, acc_manager_ui, sw_manager_ui
from ui.wnd_ui import LoadingWndUI, WndCreator
from utils import hwnd_utils
from utils.logger_utils import mylogger as logger
from utils.logger_utils import myprinter as printer


# ------------------------------------------------------------------
# 本程序文件层次:
# main_ui > 基本ui > 窗口ui > func > utils > public_class > resources
# ------------------------------------------------------------------

# TODO: 标签页布局优化


class RootWnd:
    def __init__(self, root):
        self.root = root
        self.root_class = GlobalMembers.root_class
        self.root_height = None
        self.root_width = None
        self.root_frame = None
        self.root.withdraw()  # 初始化时隐藏主窗口
        self.root_width, self.root_height = Constants.PROJ_WND_SIZE

    def set_wnd(self):
        # 设置主窗口
        try:
            title = self.root_class.remote_cfg_data["global"]["app_name"]
        except Exception as e:
            logger.error(e)
            title = os.path.basename(sys.argv[0])
        self.root.title(title)
        self.root.iconbitmap(Config.PROJ_ICO_PATH)
        self.root.after(0, hwnd_utils.set_size_and_bring_tk_wnd_to_, self.root, self.root_width, self.root_height)
        self.root.overrideredirect(False)


class RootClass:
    """
    构建主窗口的类,属于全局的成员放在这里
    管理ui: 根界面root_ui,菜单menu_ui,账号管理acc_manager_ui,软件管理sw_manager_ui,账号登录页acc_tab_ui
    管理数据: 全局配置global_settings,软件配置sw_classes
    """

    def __init__(self, args=None):
        # 未分类

        # 全局化
        GlobalMembers.root_class = self
        self.root_class = self
        # 程序参数
        self.debug = args.debug
        self.new = args.new
        # ui
        self.root_ui = None
        self.menu_ui = None
        self.login_ui = None
        self.acc_manager_ui = None
        self.sw_manager_ui = None
        self.hotkey_manager = None
        self.statusbar_ui = None
        # 加载标志
        self.first_created_acc_ui = None
        self.finish_started = None
        # 全局数据
        self.sw_classes: dict = {}
        self.remote_cfg_data = None
        self.global_settings_value = GlobalSettings()
        self.global_settings_var = GlobalSettings()
        self.app_info = AppInfo()

        # 进入程序的操作
        # -主窗口
        root = tk.Tk()
        self.root = root
        self.root_wnd = RootWnd(self.root)
        # -载入窗口
        self.loading_wnd = tk.Toplevel(self.root)
        self.loading_wnd_class = LoadingWndUI(self.loading_wnd, "加载中...")
        # try:
        # -初次使用
        if self.new is True:
            self.root.after(3000, WndCreator.open_update_log)
            self.root.after(3000, lambda: AppFunc.mov_backup(new=self.new))
        # -关闭加载窗口
        print("1.5秒后关闭加载窗口...")
        self.root.after(1500, self.wait_for_loading_close_and_bind)
        # -初始化构建...
        self.initialize_in_root()
        # except Exception as e:
        #     logger.error(e)
        self.root.mainloop()

    def initialize_in_root(self):
        """初始化加载"""
        # 检查项目根目录中是否有 user_files 这个文件夹，没有则创建
        if not os.path.exists(Config.PROJ_USER_PATH):  # 如果路径不存在
            os.makedirs(Config.PROJ_USER_PATH)  # 创建 user_files 文件夹
            print(f"已创建文件夹: {Config.PROJ_USER_PATH}")
        # # 版本更新，统计表结构更新，需升级
        # subfunc_file.merge_refresh_nodes()
        # subfunc_file.move_data_to_wechat()
        # subfunc_file.swap_cnt_and_mode_levels_in_auto()
        # subfunc_file.downgrade_item_lvl_under_manual()

        # 获取远程配置文件
        try:
            self.remote_cfg_data = subfunc_file.try_read_remote_cfg_locally()
        except Exception as e:
            logger.error(e)
            try:
                self.remote_cfg_data = subfunc_file.force_fetch_remote_encrypted_cfg()
            except Exception as e:
                logger.error(e)
        # 没有配置文件则退出程序
        if self.remote_cfg_data is None:
            messagebox.showerror("错误", "未找到配置文件，将退出程序，请检查网络设置，稍后重试")
            self.root.after(0, self.root.destroy)
            return

        # 统一管理style
        style = ttk.Style()
        style.configure('Custom.TButton', padding=Constants.CUS_BTN_PAD,
                        width=Constants.CUS_BTN_WIDTH, relief="flat", borderwidth=0)
        style.configure("Treeview")
        # style.configure('Tool.TButton', width=2)
        style.configure('FirstTitle.TLabel', font=("", Constants.FIRST_TITLE_FONTSIZE, "bold"))
        style.configure('Link.TLabel', font=("", Constants.LINK_FONTSIZE), foreground="grey")
        style.configure('SecondTitle.TLabel', font=("", Constants.SECOND_TITLE_FONTSIZE))
        style.configure("RedWarning.TLabel", foreground="red", font=("", Constants.LITTLE_FONTSIZE))
        style.configure("LittleText.TLabel", font=("", Constants.LITTLE_FONTSIZE))
        style.configure("RowTreeview", background="#FFFFFF", foreground="black",
                        rowheight=Constants.TREE_ROW_HEIGHT, selectmode="extended")
        style.layout("RowTreeview", style.layout("Treeview"))  # 继承默认布局
        style.configure("SidebarTreeview", background="#FFFFFF", foreground="black",
                        rowheight=Constants.TREE_ROW_HEIGHT, selectmode="extended",
                        borderwidth=0, highlightthickness=0)
        style.layout("SidebarTreeview", style.layout("Treeview"))  # 继承默认布局
        style.configure("Mutex.TLabel", foreground="red")

        # 代理
        AppFunc.apply_proxy_setting()
        # 创建状态栏
        if self.statusbar_ui is None or not self.statusbar_ui.status_bar.winfo_exists():
            self.statusbar_ui = reusable_widgets.StatusBarUI(self.root, self, self.debug)
            if self.debug:
                self.statusbar_ui.status_bar.bind("<Button-1>", lambda event: WndCreator.open_debug_window())

        # 重置变量
        self.hotkey_manager = None
        self.root_ui = None
        self.menu_ui = None
        self.login_ui = None
        self.acc_manager_ui = None
        self.sw_manager_ui = None
        self.global_settings_value = GlobalSettings()
        self.global_settings_var = GlobalSettings()
        # 快捷键管理
        self.hotkey_manager = HotkeyManager()
        self.init_root_ui()
        self.root_wnd.set_wnd()

    def init_root_ui(self):
        root_frame = self.root_wnd.root_frame
        if hasattr(self.root_wnd, 'root_frame') and root_frame is not None:
            if root_frame.winfo_exists():
                root_frame = root_frame.nametowidget(root_frame)
                for wdg in root_frame.winfo_children():
                    wdg.destroy()
                root_frame.destroy()
        root_frame = tk.Frame(self.root)
        root_frame.pack(expand=True, fill='both')
        self.root_ui = RootUI(self.root, root_frame)
        self.root_wnd.root_frame = root_frame
        self.root_ui.initialize_in_root_ui()

    def wait_for_loading_close_and_bind(self):
        """启动时关闭等待窗口，绑定事件"""

        def func_thread():
            # self.check_and_init()
            if hasattr(self, 'loading_wnd_class') and self.loading_wnd_class:
                # print("主程序关闭等待窗口")
                self.root.after(0, self.loading_wnd_class.auto_close)
                self.loading_wnd_class = None
            # 设置主窗口位置
            self.root.after(0, self.root.deiconify)

        try:
            # 线程启动获取登录情况和渲染列表
            threading.Thread(target=func_thread).start()
            self.after_refresh_when_start()
        except Exception as e:
            logger.error(e)

    def after_refresh_when_start(self):
        """首次启动后，无论是否成功创建账号列表，都执行"""
        if self.finish_started is True:
            return
        # 需要进行的操作
        pass
        self.finish_started = True


class RootUI:
    def __init__(self, wnd, frame):
        print("构建根UI...")
        self.sw_classes = {}
        self.root_nb_cls = None
        self.manage_nb_cls = None
        self.login_frm_pool = None
        self.login_nb_cls = None
        self.sw = None
        self.acc_mng_frame = None
        self.sw_mng_frame = None
        self.main_frame = None
        self.scrollable_canvas = None

        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root
        self.wnd = wnd
        self.root_frame = frame

        self.load_ui()

    def load_ui(self):
        """
        每一级标签有三重包裹,分别为:所在的框架xxx_frame,标签栏xxx_nb,框架池区域xxx_frame_pool
        因此,子级标签应该先在父级的框架池之下创建好其所属的框架xxx_frame,以此类推
        """

        # 主页面="管理"+"登录"
        self.root_nb_cls = root_nb_cls = CustomNotebook(self.root, self.root_frame)
        root_nb_cls.set_major_color(selected_bg='#00FF00')
        root_nb_frm_pool = root_nb_cls.frames_pool
        login_nb_frame = ttk.Frame(root_nb_frm_pool)
        manager_nb_frame = ttk.Frame(root_nb_frm_pool)
        root_nb_cls.add("manage", "管理", manager_nb_frame)
        root_nb_cls.add("login", "登录", login_nb_frame)

        # "登录"=∑各平台
        self.login_nb_cls = login_nb_cls = CustomNotebook(self.root, login_nb_frame)
        login_frm_pool = login_nb_cls.frames_pool

        # "管理"="平台"+"账号"
        self.manage_nb_cls = manage_nb_cls = CustomNotebook(self.root, manager_nb_frame)
        manage_frm_pool = manage_nb_cls.frames_pool
        sw_mng_frame = ttk.Frame(manage_frm_pool)
        acc_mng_frame = ttk.Frame(manage_frm_pool)
        manage_nb_cls.add("acc", "账号", acc_mng_frame)
        manage_nb_cls.add("sw", "平台", sw_mng_frame)

        self.login_frm_pool = login_frm_pool
        self.sw_mng_frame = sw_mng_frame
        self.acc_mng_frame = acc_mng_frame

        # 各级的细节加载
        self._load_root_nb_frame()
        # 启动线程完成sw的路径获取
        threading.Thread(target=self._get_path_thread).start()
        self._load_all_sw_frame()
        self._load_manage_frame()

    def _load_root_nb_frame(self):
        self.root_nb_cls.select_callback = self._on_tab_in_root_selected

    def _load_all_sw_frame(self):
        sp_sw, = subfunc_file.get_remote_cfg(RemoteCfg.GLOBAL, **{RemoteCfg.SP_SW: []})
        if not isinstance(sp_sw, list):
            return
        if len(sp_sw) == 0:
            sp_sw = ["WeChat"]
        for sw in sp_sw:
            # 使用枚举类型保证其位于正确的状态
            state = subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, LocalCfg.STATE, SwStates)
            if not state == SwStates.VISIBLE and not state == SwStates.HIDDEN:
                continue
            try:
                sw_cls = self.sw_classes[sw]
                if not isinstance(sw_cls, SoftwareInfo):
                    sw_cls = SoftwareInfo(sw)
            except Exception as e:
                logger.warning(e)
                sw_cls = SoftwareInfo(sw)
                self.sw_classes[sw] = sw_cls
            print(f"更新{sw}的信息体...")
            if state == SwStates.VISIBLE:
                sw_cls.frame = ttk.Frame(self.login_frm_pool)
                # print(sw_cls.frame)
                label, = subfunc_file.get_remote_cfg(sw, label="未知")
                sw_cls.label = label
                self.login_nb_cls.add(sw, sw_cls.label, sw_cls.frame)
            self.root_class.sw_classes[sw] = sw_cls
            self.sw_classes[sw] = sw_cls

        self.login_nb_cls.select_callback = self._on_tab_in_login_selected

    def _get_path_thread(self):
        sp_sw, = subfunc_file.get_remote_cfg(RemoteCfg.GLOBAL, **{RemoteCfg.SP_SW: []})
        if not isinstance(sp_sw, list):
            return
        for sw in sp_sw:
            # 使用枚举类型保证其位于正确的状态
            state = subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, LocalCfg.STATE, SwStates)
            if not state == SwStates.VISIBLE and not state == SwStates.HIDDEN:
                continue
            print(f"创建{sw}的信息体...")
            sw_cls = SoftwareInfo(sw)
            sw_cls.data_dir = SwInfoFunc.get_sw_data_dir(sw)
            sw_cls.inst_path = SwInfoFunc.get_sw_install_path(sw)
            sw_cls.ver = SwInfoFunc.get_sw_ver(sw, sw_cls.data_dir)
            sw_cls.dll_dir = SwInfoFunc.get_sw_dll_dir(sw)
        # print("载入完成,所有信息体:", [sw.__dict__ for sw in self.sw_classes.values()])
        printer.print_last()

    def _load_manage_frame(self):
        self.manage_nb_cls.select_callback = self._on_tab_in_manage_selected

    def initialize_in_root_ui(self):
        root_tab = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.ROOT_TAB)
        self.root_nb_cls.select(root_tab)

    def _on_tab_in_root_selected(self):
        """根标签切换时,将自动选择下一级的标签"""
        root_tab = self.root_nb_cls.curr_tab_id
        subfunc_file.save_a_global_setting_and_callback(LocalCfg.ROOT_TAB, root_tab)
        if root_tab == "manage":
            manage_tab = self.manage_nb_cls.curr_tab_id
            if not manage_tab:
                manage_tab = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.MNG_TAB)
            try:
                self.manage_nb_cls.select(manage_tab)
            except Exception as e:
                logger.warning(e)
                self.manage_nb_cls.select(next(iter(self.manage_nb_cls.tabs.keys())))
        elif root_tab == "login":
            login_tab = self.login_nb_cls.curr_tab_id
            if not login_tab:
                login_tab = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.LOGIN_TAB)
            try:
                self.login_nb_cls.select(login_tab)
            except Exception as e:
                logger.warning(e)
                self.login_nb_cls.select(next(iter(self.login_nb_cls.tabs)))

    def _on_tab_in_login_selected(self):
        self.sw = self.login_nb_cls.curr_tab_id
        print(f"当前是{self.sw}的标签页")
        self.root_class.sw = self.sw
        subfunc_file.save_a_global_setting_and_callback(LocalCfg.LOGIN_TAB, self.sw)
        if self.root_class.login_ui is None:
            self.root_class.login_ui = login_ui.LoginUI()
        self.root_class.login_ui.refresh()

    def _on_tab_in_manage_selected(self):
        self.manage_tab = self.manage_nb_cls.curr_tab_id
        subfunc_file.save_a_global_setting_and_callback(LocalCfg.MNG_TAB, self.manage_tab)
        if self.manage_tab == "acc":
            if self.root_class.acc_manager_ui is None:
                self.root_class.acc_manager_ui = acc_manager_ui.AccManagerUI(self.root, self.acc_mng_frame)
            print("刷新账号管理界面和菜单...")
            self.root_class.acc_manager_ui.refresh()
        elif self.manage_tab == "sw":
            if self.root_class.sw_manager_ui is None:
                self.root_class.sw_manager_ui = sw_manager_ui.SwManagerUI(self.root, self.sw_mng_frame)
            print("刷新软件管理界面和菜单...")
            self.root_class.sw_manager_ui.refresh()


class SoftwareInfo:
    def __init__(self, sw):
        self.sw = sw
        self.name = None
        self.frame = None
        self.view = None
        self.freely_multirun = None
        self.multirun_mode = None
        self.anti_revoke = None
        self.classic_ui = None
        self.tree_ui = None
        self.inst_path = None
        self.data_dir = None
        self.dll_dir = None
        self.ver = None
        self.login_accounts = None
        self.logout_accounts = None


class AppInfo:
    def __init__(self):
        self.name = os.path.basename(sys.argv[0])
        self.author = "吾峰起浪"
        self.curr_full_ver = subfunc_file.get_app_current_version()
        self.need_update = None
        self.hint = "狂按"


class GlobalSettings:
    def __init__(self):
        self.sign_vis = None
        self.scale = None
        self.login_size = None
        self.rest_mode = None
        self.hide_wnd = None
        self.call_mode = None
        self.new_func = None
        self.auto_press = None
        self.disable_proxy = None


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
            logger.info("监听快捷键中...")
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
