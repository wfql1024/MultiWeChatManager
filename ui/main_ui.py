# main_ui.py
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from functions import func_file, subfunc_file, func_setting, subfunc_sw, func_login, func_hotkey
from public_class import reusable_widget
from public_class.global_members import GlobalMembers
from resources import Config, Constants
from ui import loading_ui, menu_ui, acc_tab_ui, debug_ui, detail_ui, acc_manager_ui
from utils import hwnd_utils
from utils.logger_utils import mylogger as logger
from utils.logger_utils import myprinter as printer


class MainWindow:
    """构建主窗口的类"""

    def __init__(self, root, args=None):
        # IDE初始化
        self.quick_refresh = None
        self.acc_manager_ui = None
        self.all_acc_frame = None
        self.hotkey_manager = None
        self.acc_tab_ui = None
        self.window_height = None
        self.window_width = None
        self.detail_ui_class = None
        self._initialized = None
        self.statusbar_class = None
        self.cfg_data = None
        self.sw_notebook = None
        self.first_created_acc_ui = None
        self.finish_started = None

        self.sw_classes: dict = {}
        self.global_settings_value = GlobalSettings()
        self.global_settings_var = GlobalSettings()
        self.app_info = AppInfo()
        GlobalMembers.root_class = self
        self.root_class = self

        # 构造方法的参数加载
        self.root = root
        self.debug = args.debug
        self.new = args.new

        self.root.withdraw()  # 初始化时隐藏主窗口
        # 渲染加载窗口
        self.loading_wnd = tk.Toplevel(self.root)
        self.loading_wnd_class = loading_ui.LoadingWindow(self.loading_wnd)

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

        # 获取远程配置文件
        try:
            self.cfg_data = subfunc_file.try_read_remote_cfg_locally()
        except Exception as e:
            logger.error(e)
            try:
                self.cfg_data = subfunc_file.force_fetch_remote_encrypted_cfg()
            except Exception as e:
                logger.error(e)

        # 没有配置文件则退出程序
        if self.cfg_data is None:
            messagebox.showerror("错误", "未找到配置文件，将退出程序，请检查网络设置，稍后重试")
            self.root.after(0, self.root.destroy)
            return

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

        # 创建状态栏
        if self.statusbar_class is None or not self.statusbar_class.status_bar.winfo_exists():
            self.statusbar_class = reusable_widget.StatusBar(self.root, self, self.debug)
        self.hotkey_manager = func_hotkey.HotkeyManager()

        self.window_width, self.window_height = Constants.PROJ_WND_SIZE

        # 加载标签页
        self.init_notebook()

        # 设置主窗口
        try:
            title = self.cfg_data["global"]["app_name"]
        except Exception as e:
            logger.error(e)
            title = os.path.basename(sys.argv[0])
        self.root.title(title)
        self.root.iconbitmap(Config.PROJ_ICO_PATH)

        self.root.after(0, hwnd_utils.bring_tk_wnd_to_center, self.root, self.window_width, self.window_height)
        self.root.overrideredirect(False)

    def init_notebook(self):
        """集中写界面初始化方法"""
        if hasattr(self, 'sw_notebook') and self.sw_notebook is not None:
            if self.sw_notebook.winfo_exists():
                sw_notebook = self.sw_notebook.nametowidget(self.sw_notebook)
                for wdg in sw_notebook.winfo_children():
                    wdg.destroy()
                sw_notebook.destroy()
        self.create_tab()

    def create_tab(self):
        """创建选项卡"""
        print("创建选项卡...")
        self.sw_notebook = ttk.Notebook(self.root)
        self.sw_notebook.pack(expand=True, fill='both')
        self.all_acc_frame = ttk.Frame(self.sw_notebook)
        self.sw_notebook.add(self.all_acc_frame, text="全部")

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
        current_sw = subfunc_file.fetch_global_setting_or_set_default("tab")
        self.sw_notebook.select(self.sw_classes[current_sw].frame)
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
            # 是平台选项卡
            subfunc_file.save_global_setting("tab", selected_sw)
            printer.vital(f"当前选项卡: {selected_sw}")
            self.acc_tab_ui = acc_tab_ui.AccTabUI()
            self.acc_tab_ui.refresh()
        else:
            # 不是平台选项卡
            self.acc_manager_ui = acc_manager_ui.AccManagerUI(self, self.root, selected_frame)
            self.acc_manager_ui.refresh_frame()

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

    def open_debug_window(self):
        """打开调试窗口，显示所有输出日志"""
        debug_window = tk.Toplevel(self.root)
        debug_ui.DebugWindow(debug_window)

    @staticmethod
    def to_login_auto_start_accounts():
        """启动程序后自动登录"""
        thread = threading.Thread(target=func_login.login_auto_start_accounts)
        thread.start()

    def open_acc_detail(self, item, parent_frame, widget_tag=None, event=None):
        """打开详情窗口"""
        if event is None:
            pass
        sw, acc = item.split("/")
        detail_window = tk.Toplevel(self.root)
        self.detail_ui_class = detail_ui.DetailWindow(self.root, self.root, parent_frame, detail_window, sw,
                                                      acc)
        self.detail_ui_class.set_focus_to_(widget_tag)

    def to_switch_to_sw_account_wnd(self, item, event=None):
        if event:
            pass
        subfunc_sw.switch_to_sw_account_wnd(item, self.root)


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
