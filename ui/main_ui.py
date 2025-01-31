# main_ui.py
import os
import sys
import threading
import time
import tkinter as tk
from functools import partial
from tkinter import ttk

from functions import func_login, func_file, func_account, subfunc_file, func_config, func_setting
from public_class import reusable_widget
from resources import Strings, Config, Constants
from ui import debug_ui, classic_row_ui, treeview_row_ui, loading_ui, detail_ui, menu_ui
from utils import hwnd_utils
from utils.logger_utils import mylogger as logger


class MainWindow:
    """构建主窗口的类"""

    def __init__(self, root, args=None):
        # IDE初始化
        self.sw_classes = None
        self._initialized = None
        self.statusbar_class = None
        self.sw = None
        self.start_time = None
        self.root_menu = None
        self.cfg_data = None
        self.settings_button = None
        self.error_frame = None
        self.sw_notebook = None
        self.tab_frame = None
        self.main_frame = None
        self.scrollable_canvas = None
        self.finish_started = None

        self.sw_classes = {

        }

        self.root = root
        self.debug = args.debug
        self.new = args.new

        # 统一管理style
        style = ttk.Style()
        style.configure('Custom.TButton', padding=Constants.CUS_BTN_PAD,
                        width=Constants.CUS_BTN_WIDTH)
        style.configure('Tool.TButton', width=2)
        style.configure('FirstTitle.TLabel', font=("", Constants.FIRST_TITLE_FONTSIZE, "bold"))
        style.configure('Link.TLabel', font=("", Constants.LINK_FONTSIZE), foreground="grey")
        style.configure('SecondTitle.TLabel', font=("", Constants.SECOND_TITLE_FONTSIZE))
        style.configure("RedWarning.TLabel", foreground="red", font=("", Constants.LITTLE_FONTSIZE))
        style.configure("LittleText.TLabel", font=("", Constants.LITTLE_FONTSIZE))
        style.configure("RowTreeview", background="#FFFFFF", foreground="black",
                        rowheight=Constants.TREE_ROW_HEIGHT, selectmode="extended")
        style.layout("RowTreeview", style.layout("Treeview"))  # 继承默认布局

        self.window_width, self.window_height = Constants.PROJ_WND_SIZE
        self.root.withdraw()  # 初始化时隐藏主窗口

        # 渲染加载窗口
        self.loading_wnd = tk.Toplevel(self.root)
        self.loading_wnd_class = loading_ui.LoadingWindow(self.loading_wnd)

        # 创建状态栏
        self.statusbar_class = reusable_widget.StatusBar(self.root, self, self.debug)

        try:
            # 初次使用
            if self.new is True:
                self.root.after(3000, menu_ui.MenuUI.open_update_log)
                self.root.after(3000, lambda: func_file.mov_backup(new=self.new))
            # 关闭加载窗口
            print("2秒后关闭加载窗口...")
            self.root.after(2000, self.wait_for_loading_close_and_bind)
            # 其余部分
            self.initialize_in_init()
        except Exception as e:
            logger.error(e)

    """主流程"""

    def initialize_in_init(self):
        """初始化加载"""
        # 检查项目根目录中是否有 user_files 这个文件夹，没有则创建
        if not os.path.exists(Config.PROJ_USER_PATH):  # 如果路径不存在
            os.makedirs(Config.PROJ_USER_PATH)  # 创建 user_files 文件夹
            print(f"已创建文件夹: {Config.PROJ_USER_PATH}")

        # 版本更新，统计表结构更新，需升级
        subfunc_file.merge_refresh_nodes()
        subfunc_file.move_data_to_wechat()
        subfunc_file.swap_cnt_and_mode_levels_in_auto()
        subfunc_file.downgrade_item_lvl_under_manual()

        # 获取基本属性，加载标签页
        self.sw = subfunc_file.fetch_global_setting_or_set_default("tab")
        self.cfg_data = subfunc_file.try_get_local_cfg()
        try:
            self.init_notebook()
        except Exception as e:
            logger.error(e)
            self.cfg_data = subfunc_file.force_fetch_remote_encrypted_cfg()
            self.init_notebook()

        # 设置主窗口
        try:
            title = self.cfg_data["global"]["app_name"]
        except Exception as e:
            logger.error(e)
            title = os.path.basename(sys.argv[0])
        self.root.title(title)
        self.root.iconbitmap(Config.PROJ_ICO_PATH)

    def init_notebook(self):
        """集中写界面初始化方法"""
        if hasattr(self, 'sw_notebook') and self.sw_notebook is not None:
            for wdg in self.sw_notebook.winfo_children():
                wdg.destroy()
            self.sw_notebook.destroy()
        self.create_tab()

    def create_tab(self):
        """创建选项卡"""
        print("创建选项卡...")
        self.sw_notebook = ttk.Notebook(self.root)
        self.sw_notebook.pack(expand=True, fill='both')
        tab_dict = self.cfg_data["global"]["all_sw"]
        print(tab_dict)
        for sw in tab_dict.keys():
            self.sw_classes[sw] = SoftwareInfo(sw)
            print(f"创建{sw}的信息体...")
            self.sw_classes[sw].data_dir = func_setting.get_sw_data_dir(sw)
            self.sw_classes[sw].inst_path, self.sw_classes[sw].ver = func_setting.get_sw_inst_path_and_ver(sw)
            self.sw_classes[sw].dll_dir = func_setting.get_sw_dll_dir(sw)
            self.sw_classes[sw].frame = ttk.Frame(self.sw_notebook)
            # print(self.sw_classes[sw].frame)
            self.sw_classes[sw].frame.var = sw
            self.sw_classes[sw].text = tab_dict[sw]['text']
            self.sw_classes[sw].name = tab_dict[sw]['name']
            self.sw_notebook.add(self.sw_classes[sw].frame, text=self.sw_classes[sw].text)
        # 选择一个选项卡并触发事件
        self.sw_notebook.select(self.sw_classes[self.sw].frame)
        # self.sw_notebook.bind('<<NotebookTabChanged>>', self.on_tab_change)
        self.on_tab_change(_event=None)

    def on_tab_change(self, _event):
        """处理选项卡变化事件，排除特殊选项卡"""
        print("切换选项卡响应中...")
        self.sw_notebook.unbind('<<NotebookTabChanged>>')  # 暂时取消绑定
        if not hasattr(self, '_initialized'):
            self._initialized = True
            return  # 忽略初始化触发
        if self.sw_notebook.select() == "!disabled":
            return
        selected_frame = self.sw_notebook.nametowidget(self.sw_notebook.select())  # 获取当前选中的Frame
        selected_sw = getattr(selected_frame, 'var', None)  # 获取与当前选项卡相关的变量
        if selected_sw:
            subfunc_file.save_global_setting("tab", selected_sw)
            msg_str = f"当前选项卡: {selected_sw}"
            self.refresh(message=msg_str)
            print(msg_str)

    def refresh(self, message=None):
        """刷新菜单和界面"""
        print(f"刷新菜单与界面...")
        self.sw = subfunc_file.fetch_global_setting_or_set_default("tab")

        self.tab_frame = self.sw_classes[self.sw].frame

        # 刷新菜单
        self.root_menu = menu_ui.MenuUI(self.root, self)
        try:
            self.root.after(0, self.root_menu.create_root_menu_bar)
        except Exception as re:
            logger.error(re)
            subfunc_file.force_fetch_remote_encrypted_cfg()
            self.root.after(0, self.root_menu.create_root_menu_bar)

        # 刷新界面
        def reload_func():
            try:
                self.root.after(0, self.refresh_sw_main_frame, self.sw, message)
            except Exception as e_reload:
                logger.error(e_reload)
                self.root.after(5000, self.refresh_sw_main_frame, self.sw, message)

        try:
            # 线程启动获取登录情况和渲染列表
            threading.Thread(target=reload_func).start()
        except Exception as e:
            logger.error(e)

    def refresh_sw_main_frame(self, sw, message=None):
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
                self.root.after(0, self.create_main_ui, message)

            threading.Thread(target=thread_func).start()
        except Exception as e:
            logger.error(e)

    def create_main_ui(self, message=None):
        """渲染主界面账号列表"""
        # 检测是否路径错误
        if self.root_menu.path_error is True:
            self.show_setting_error()

        else:
            success, result = func_account.get_sw_acc_list(self.root, self, self.sw)
            if success is not True:
                self.show_setting_error()
            else:
                self.create_account_list_ui(result, message)

        # print("创建完成，无论是错误界面还是正常界面，下面代码都要进行")

        # 恢复刷新可用性
        self.root_menu.edit_menu.entryconfig("刷新", state="normal")

        # 加载完成后更新一下界面并且触发事件
        if self.scrollable_canvas is not None and self.scrollable_canvas.canvas.winfo_exists():
            self.scrollable_canvas.refresh_canvas()

        self.after_refresh_when_start()

        # 重新绑定标签切换事件
        self.sw_notebook.bind('<<NotebookTabChanged>>', self.on_tab_change)

    def create_account_list_ui(self, result, message=None):
        print(f"渲染账号列表.........................................................")

        acc_list_dict, _, mutex = result
        login = acc_list_dict["login"]
        logout = acc_list_dict["logout"]

        self.sw_classes[self.sw].login_accounts = login
        self.sw_classes[self.sw].logout_accounts = logout

        # 底部框架=手动登录
        bottom_frame = ttk.Frame(self.tab_frame, padding=Constants.BTN_FRAME_PAD)
        bottom_frame.pack(side=tk.BOTTOM)
        prefix = Strings.MUTEX_SIGN if mutex is True and self.root_menu.settings_values["sign_vis"] else ""
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
            self.sw_classes[self.sw].classic_ui = classic_row_ui.ClassicRowUI(
                self.root, self, self.main_frame, result, self.sw_classes[self.sw].data_dir, self.sw)
        elif self.sw_classes[self.sw].view == "tree":
            self.sw_classes[self.sw].tree_ui = treeview_row_ui.TreeviewRowUI(
                self, result)
        else:
            pass
        subfunc_file.update_statistic_data(
            self.sw, 'refresh', self.sw_classes[self.sw].view, str(len(login)), time.time() - self.start_time)
        msg_str = f"{message} | " if message else ""
        print(f"{msg_str}加载完成！用时：{time.time() - self.start_time:.4f}秒")

        # 获取已登录的窗口hwnd
        func_account.get_main_hwnd_of_accounts(login, self.sw)

        # 进行静默获取头像及配置
        func_account.silent_get_and_config(self.root, self, self.sw, login, logout)

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

    def after_refresh_when_start(self):
        """首次启动后，无论是否成功创建账号列表，都执行"""
        if self.finish_started is True:
            return

        # 需要进行的操作
        pass

        self.finish_started = True

    def after_success_create_acc_ui_when_start(self):
        """首次启动后，成功创建账号列表才会执行"""
        if self.finish_started is True:
            return

        # 需要进行的操作
        self.to_login_auto_start_accounts()

        self.finish_started = True

    def wait_for_loading_close_and_bind(self):
        """启动时关闭等待窗口，绑定事件"""

        def func_thread():
            # self.check_and_init()
            if hasattr(self, 'loading_wnd_class') and self.loading_wnd_class:
                # print("主程序关闭等待窗口")
                self.root.after(0, self.loading_wnd_class.auto_close)
                self.loading_wnd_class = None
            # 设置主窗口位置
            self.root.after(0, hwnd_utils.bring_tk_wnd_to_center, self.root, self.window_width, self.window_height)
            self.root.deiconify()
            # self.sw_notebook.bind('<<NotebookTabChanged>>', self.on_tab_change)

        try:
            # 线程启动获取登录情况和渲染列表
            threading.Thread(target=func_thread).start()
        except Exception as e:
            logger.error(e)

    """功能区"""

    def open_debug_window(self):
        """打开调试窗口，显示所有输出日志"""
        debug_window = tk.Toplevel(self.root)
        debug_ui.DebugWindow(debug_window)

    def to_manual_login(self):
        """按钮：手动登录"""
        print("手动登录")
        threading.Thread(
            target=func_login.manual_login,
            args=(self.root, self, self.sw)
        ).start()

    def to_auto_login(self, items):
        """登录所选账号"""
        login_dict = {}
        for item in items:
            sw, acc = item.split("/")
            if sw not in login_dict:
                login_dict[sw] = []
            login_dict[sw].append(acc)

        if self.root_menu.settings_values["hide_wnd"] is True:
            self.root.iconify()  # 最小化主窗口

        try:
            t = threading.Thread(
                target=func_login.auto_login_accounts,
                args=(self, login_dict)
            )
            t.start()
        except Exception as e:
            logger.error(e)

    def to_create_config(self, items):
        """按钮：创建或重新配置"""
        accounts = [items.split("/")[1] for items in items]
        threading.Thread(target=func_config.test,
                         args=(self, self.sw, accounts[0], self.sw_classes[self.sw].multiple_state)).start()

    def to_quit_accounts(self, items):
        """退出所选账号"""
        accounts = [items.split("/")[1] for items in items]
        answer = func_account.quit_selected_accounts(self.sw, accounts)
        if answer is True:
            self.refresh_sw_main_frame(self.sw)

    def to_login_auto_start_accounts(self):
        """启动程序后自动登录"""
        thread = threading.Thread(target=func_login.login_auto_start_accounts,
                                  args=(self.root, self))
        thread.start()

    def open_acc_detail(self, item, event=None):
        """打开详情窗口"""
        if event is None:
            pass
        sw, acc = item.split("/")
        detail_window = tk.Toplevel(self.root)
        detail_ui.DetailWindow(self.root, self.root, detail_window, sw,
                               acc, self.refresh_sw_main_frame)


class SoftwareInfo:
    def __init__(self, sw):
        self.sw = sw
        self.name = None
        self.frame = None
        self.view = None
        self.multiple_state = None
        self.revoke = None
        self.classic_ui = None
        self.tree_ui = None
        self.inst_path = None
        self.data_dir = None
        self.dll_dir = None
        self.ver = None
        self.data_dir = None
        self.inst_path = None
        self.ver = None
        self.dll_dir = None
        self.login_accounts = None
        self.logout_accounts = None
