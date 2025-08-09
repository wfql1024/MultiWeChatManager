import ctypes
import threading
import time
import tkinter as tk
from abc import ABC
from enum import Enum
from tkinter import ttk

import win32con
import win32gui
from PIL import Image, ImageTk

from functions import subfunc_file
from functions.acc_func import AccInfoFunc
from public_class.custom_widget import CustomCornerBtn
from public_class.enums import OnlineStatus
from public_class.global_members import GlobalMembers
from public_class.widget_frameworks import RadioTreeView
from resources import Constants
from ui.wnd_ui import WndCreator
from utils import hwnd_utils
from utils.hwnd_utils import TkWndUtils
from utils.logger_utils import mylogger as logger, Printer
from utils.widget_utils import TreeUtils


class WndProperties(str, Enum):
    """
    窗口状态枚举类
    """
    IS_HIDDEN = "hidden"
    IS_MAXIMIZED = "maximized"
    IS_MINIMIZED = "minimized"
    IS_FOREGROUND = "foreground"
    IS_DEF_MAXIMIZED = "def_maximized"
    RECT = "rect"


class SidebarUI:
    # TODO: 若无法找到窗口，联动详情窗口来获取窗口句柄
    # TODO: 列表选中状态应该是根据目前已经链接的窗口来确定
    # TODO: 增加最大化判断
    def __init__(self, wnd, title):
        self.thread_result = None
        self.find_acc_wnd_thread = None
        self.logout_class = None
        self.login_class = None
        self.last_linked_rect = None
        self.home_btn = None
        self.logout_frame = None
        self.login_frame = None
        self.wnd = wnd
        self.title = title

        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root

        self.bar_hwnd = None
        self.bar_frame = None
        self.nested_window_drag_thread = None
        self.restore_button = None
        self.pause_event = None
        self.listener_running = None
        self.root_hwnd = None
        self.linked_hwnd = None  # 存储目标窗口句柄
        self.bar_width = None
        # 拖拽相关变量
        self.offset_x = 0
        self.offset_y = 0

        self.initialize_members_in_init()

        # 设置窗口
        wnd.title(self.title)
        wnd.attributes('-toolwindow', True)

        self.set_wnd()
        self.load_content()

    def initialize_members_in_init(self):
        self.pause_event = threading.Event()
        self.root_hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        self.bar_width = Constants.SIDEBAR_WIDTH

    def set_wnd(self):
        self.wnd.overrideredirect(True)  # 去除窗口标题栏

    def load_content(self):
        # # 绑定鼠标事件实现拖拽功能
        # self.wnd.bind("<Button-1>", self.start_drag)
        # self.wnd.bind("<B1-Motion>", self.do_drag)
        # self.wnd.bind("<ButtonRelease-1>", self.stop_drag)

        # 左侧栏
        self.bar_frame = tk.Frame(self.wnd, width=self.bar_width)
        self.bar_frame.pack(side="left", fill="y")
        # self.bar_frame.pack_propagate(False)  # 禁止根据子控件调整大小
        self.bar_hwnd = ctypes.windll.user32.GetParent(self.bar_frame.winfo_id())

        # 置顶的控件
        self.login_frame = ttk.Frame(self.bar_frame)
        self.login_frame.pack(side=tk.TOP, fill=tk.X)

        # # 中间框架
        # self.middle_frame = ttk.Frame(self.bar_frame)
        # self.middle_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        #
        # self.tip_label = tk.Label(
        #     self.middle_frame,
        #     text=" ",
        #     fg="red",
        #     wraplength=self.bar_width - 20,  # 设置自动换行宽度，留出边距
        #     justify="left"
        # )
        # self.tip_label.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        # 置底控件
        self.home_btn = CustomCornerBtn(self.bar_frame, text="管理器")
        self.home_btn.set_bind_map(**{"1": self.switch_root_wnd}).apply_bind(self.root)
        self.home_btn.pack(side="bottom", fill="x")
        # self.logout_frame = ttk.Frame(self.bar_frame)
        # self.logout_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.login_class = SidebarTree(self, self.login_frame, OnlineStatus.LOGIN)
        # self.logout_class = SidebarTree(self, self.logout_frame, OnlineStatus.LOGOUT)

        # 首次显示时，设置 bar 窗口的位置和大小
        self.linked_hwnd = self.root_hwnd
        curr_linked_wnd_state = self.get_linked_wnd_state(self.linked_hwnd)
        self._update_sidebar(curr_linked_wnd_state)

        # 开启线程监听嵌套窗口的拖动行为
        self.listener_running = True
        self.nested_window_drag_thread = threading.Thread(target=self._monitor_linked_wnd_thread, daemon=True)
        self.nested_window_drag_thread.start()

    # @staticmethod
    # def ensure_taskbar_visibility():
    #     """
    #     确保窗口在任务栏中显示
    #     """
    #     hwnd = win32gui.GetForegroundWindow()  # 获取窗口句柄
    #     print("hwnd:", hwnd)
    #     win32gui.ShowWindow(hwnd, win32con.SW_HIDE)  # 隐藏窗口
    #     win32gui.SetWindowLong(
    #         hwnd,
    #         win32con.GWL_EXSTYLE,
    #         win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) | win32con.WS_EX_APPWINDOW
    #     )  # 设置扩展样式
    #     win32gui.ShowWindow(hwnd, win32con.SW_SHOW)  # 显示窗口

    @staticmethod
    def get_linked_wnd_state(hwnd):
        """
        获取窗口的状态
        """
        window_style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        linked_rect = win32gui.GetWindowRect(hwnd)
        # 将所有状态合并到一个字典中
        current_state = {
            "hwnd": hwnd,
            WndProperties.IS_MINIMIZED: bool(window_style & win32con.WS_MINIMIZE),
            WndProperties.IS_MAXIMIZED: bool(window_style & win32con.WS_MAXIMIZE),
            WndProperties.IS_FOREGROUND: win32gui.GetForegroundWindow() == hwnd,
            WndProperties.IS_HIDDEN: not bool(window_style & win32con.WS_VISIBLE),
            WndProperties.RECT: linked_rect
        }
        return current_state

    def _update_linked_wnd_from_states(self, old_state, new_state):
        """
        根据新旧状态对窗口进行操作
        """
        # 判断两个字典是否相等
        # print(old_state)
        # print(new_state)
        if old_state == new_state:
            # print("无需操作")
            return False

        is_minimized = new_state[WndProperties.IS_MINIMIZED]
        is_maximized = new_state[WndProperties.IS_MAXIMIZED]
        is_foreground = new_state[WndProperties.IS_FOREGROUND]
        linked_rect = new_state[WndProperties.RECT]

        return True

    def _update_sidebar(self, curr_linked_wnd_state):
        """
        设置 bar 窗口的位置和大小
        原则是：先确定钩子窗口是否还在，若不在则获取类似窗口，并给钩子
        若存在则根据钩子窗口的位置和大小设置 bar 窗口的位置和大小
        """
        is_minimized = curr_linked_wnd_state[WndProperties.IS_MINIMIZED]
        is_maximized = curr_linked_wnd_state[WndProperties.IS_MAXIMIZED]
        is_foreground = curr_linked_wnd_state[WndProperties.IS_FOREGROUND]
        linked_rect = curr_linked_wnd_state[WndProperties.RECT]

        # 如果主窗口不在前台且工具栏未获得焦点，则寻找在前台的窗口
        if not is_foreground and not self.wnd.focus_get():
            self.wnd.attributes("-topmost", False)
            self.find_foreground_wnd()
            return

        # 计算 bar 窗口的位置
        bar_rect = win32gui.GetClientRect(self.bar_hwnd)
        new_x = linked_rect[0] - bar_rect[2]  # 让 bar 窗口始终在主窗口左侧
        new_y = linked_rect[1]
        new_height = linked_rect[3] - linked_rect[1]
        # 置顶wnd后取消置顶
        self.wnd.attributes("-topmost", True)
        self.wnd.attributes("-topmost", False)
        # 同步 bar 窗口的位置
        self.wnd.geometry(f"{self.bar_width}x{new_height}+{new_x}+{new_y}")

    def _monitor_linked_wnd_thread(self):
        """
        监控嵌套窗口的拖动行为，并同步调整 bar 窗口的位置和层级。
        监听频率会随时间增加,状态变化时重置。
        """
        last_change_time = time.time()  # 记录上一次状态变化的时间
        base_interval = 0.05  # 基础监听间隔
        current_interval = base_interval  # 初始监听间隔

        last_linked_wnd_state = None  # 记录上一次的窗口状态
        is_def_max_wnd = False  # "最大化"状态

        while True:
            if self.listener_running:
                if self.linked_hwnd and win32gui.IsWindow(self.linked_hwnd):
                    # 获取目标窗口当前各种状态
                    curr_linked_wnd_state = self.get_linked_wnd_state(self.linked_hwnd)
                    Printer().debug(f"{self.linked_hwnd}当前状态: "
                                    f"最小化={curr_linked_wnd_state[WndProperties.IS_MINIMIZED]}, "
                                    f"最大化={curr_linked_wnd_state[WndProperties.IS_MAXIMIZED]}, "
                                    f"前台={curr_linked_wnd_state[WndProperties.IS_FOREGROUND]}, "
                                    f"隐藏={curr_linked_wnd_state[WndProperties.IS_MINIMIZED]},"
                                    f"位置={curr_linked_wnd_state[WndProperties.RECT]}，"
                                    f"“最大化”={is_def_max_wnd}，"
                                    f"记录的“非最大化”位置：{self.last_linked_rect}")  # 每次监听都打印状态

                    # 首次运行时初始化 last_linked_wnd_state
                    if last_linked_wnd_state is None:
                        last_linked_wnd_state = curr_linked_wnd_state

                    # # 更新“最大化”状态
                    # if is_maximized:
                    #     # 这里用户双击了窗口，需要切换窗口状态
                    #     print("触发取反")
                    #     is_def_max_wnd = not is_def_max_wnd
                    #     self.set_linked_wnd_maximized(is_def_max_wnd)
                    # else:
                    #     if curr_linked_wnd_state[4] != last_linked_wnd_state[4]:  # 如果窗口位置发生变化
                    #         is_def_max_wnd = False
                    #
                    # # 记录下最后“非最大化”的位置大小
                    # if is_def_max_wnd is False:
                    #     self.last_linked_rect = linked_rect
                    #
                    # # 检查状态是否发生变化
                    # if curr_linked_wnd_state != last_linked_wnd_state:
                    #     is_minimized = curr_linked_wnd_state[1]
                    #     is_maximized = curr_linked_wnd_state[2]
                    #     print(f"窗口状态变化 - 最小化: {is_minimized}, 最大化: {is_maximized}")
                    #     if not curr_linked_wnd_state[1]:
                    #         self.wnd.deiconify()  # 还原窗口

                    # # 更新“最大化”状态
                    # if is_maximized:
                    #     # 这里用户双击了窗口，需要切换窗口状态
                    #     self.set_linked_wnd_maximized(is_def_max_wnd)
                    #
                    # else:
                    #     if curr_linked_wnd_state[4] != last_linked_wnd_state[4]:  # 如果窗口位置发生变化
                    #         is_def_max_wnd = False

                    # # 对链接窗口进行操作后，更新下窗口状态
                    # curr_linked_wnd_state = self.get_linked_wnd_state(self.linked_hwnd)
                    # last_linked_wnd_state = curr_linked_wnd_state

                    # 状态有变，则操作链接窗口后，更新信息后更新工具栏
                    if self._update_linked_wnd_from_states(last_linked_wnd_state, curr_linked_wnd_state):
                        curr_linked_wnd_state = self.get_linked_wnd_state(self.linked_hwnd)
                        print(f"--{self.linked_hwnd}更新状态: "
                              f"最小化={curr_linked_wnd_state[WndProperties.IS_MINIMIZED]}, "
                              f"最大化={curr_linked_wnd_state[WndProperties.IS_MAXIMIZED]}, "
                              f"前台={curr_linked_wnd_state[WndProperties.IS_FOREGROUND]}, "
                              f"位置={curr_linked_wnd_state[WndProperties.RECT]}，"
                              f"“最大化”={is_def_max_wnd}，"
                              f"记录的“非最大化”位置：{self.last_linked_rect}")  # 每次监听都打印状态
                        self._update_sidebar(curr_linked_wnd_state)
                        last_change_time = time.time()  # 重置计时
                        current_interval = base_interval  # 重置监听间隔

                    last_linked_wnd_state = curr_linked_wnd_state
                else:
                    # 如果目标窗口不存在，寻找在前台的窗口
                    last_linked_wnd_state = None  # 重置状态
                    self.find_foreground_wnd()

            else:
                pass

            # 计算当前应该的监听间隔
            elapsed_time = time.time() - last_change_time
            if elapsed_time >= 0.5:  # 每0.5秒
                current_interval = min(current_interval * 2, 1.0)  # 翻倍但不超过1秒
                last_change_time = time.time()  # 重置计时

            time.sleep(current_interval)

    def turn_on_listener(self):
        """
        监听总闸，开启监听标识
        :return:
        """
        self.listener_running = True

    def turn_off_listener(self):
        """
        监听总闸，关闭监听标识
        :return:
        """
        self.listener_running = False

    def switch_acc_wnd(self, item_id):
        """
        切换到账号窗口
        :param item_id: 列表id，格式为：sw/acc
        :return:
        """
        print("切换到账号窗口...")
        # 暂停监听线程
        self.turn_off_listener()

        # 切换前后窗口的hwnd
        sw, acc = item_id.split("/")
        new_linked_hwnd, = subfunc_file.get_sw_acc_data(sw, acc, main_hwnd=None)
        old_linked_hwnd = self.linked_hwnd
        print("切换前后窗口的hwnd:", old_linked_hwnd, new_linked_hwnd)

        # 如果新窗口不存在
        if not new_linked_hwnd or not win32gui.IsWindow(new_linked_hwnd):
            # 开启查找窗口线程
            self.wait_for_acc_wnd(sw, acc)
            # self.find_acc_wnd_thread = threading.Thread(target=self.wait_for_acc_wnd, args=(sw, acc,))
            # self.find_acc_wnd_thread.start()
            # self.find_acc_wnd_thread.join()  # 等待线程结束
            new_linked_hwnd = self.thread_result

        # 获取不到的话，则不变换窗口
        if not new_linked_hwnd or not win32gui.IsWindow(new_linked_hwnd):
            new_linked_hwnd = old_linked_hwnd

        # 如果原窗口是其他账号的窗口
        if old_linked_hwnd and win32gui.IsWindow(old_linked_hwnd) and old_linked_hwnd != self.root_hwnd:
            print("账号切换到账号窗口...")
            # 获取窗口的位置和尺寸
            bar_rect = win32gui.GetWindowRect(self.bar_hwnd)
            old_linked_wnd_rect = win32gui.GetWindowRect(old_linked_hwnd)
            # 将主窗口调整到侧栏右侧，并设置相同高度
            hwnd_utils.restore_window(new_linked_hwnd)
            try:
                win32gui.SetWindowPos(
                    new_linked_hwnd,
                    win32con.HWND_TOP,
                    bar_rect[2],  # x坐标设为侧栏右边界
                    bar_rect[1],  # y坐标与侧栏对齐
                    old_linked_wnd_rect[2] - old_linked_wnd_rect[0],  # 保持原有宽度
                    old_linked_wnd_rect[3] - old_linked_wnd_rect[1],  # 高度与侧栏一致
                    win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW
                )
            except Exception as e:
                logger.warning(e)
        else:
            print("管理器切换到账号窗口...")
            hwnd_utils.restore_window(new_linked_hwnd)
            # 使用保存的原始位置和大小
            new_linked_wnd_rect = win32gui.GetWindowRect(new_linked_hwnd)
            try:
                win32gui.SetWindowPos(
                    new_linked_hwnd,
                    win32con.HWND_TOP,
                    new_linked_wnd_rect[0],
                    new_linked_wnd_rect[1],
                    new_linked_wnd_rect[2] - new_linked_wnd_rect[0],
                    new_linked_wnd_rect[3] - new_linked_wnd_rect[1],
                    win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW
                )
            except Exception as e:
                logger.warning(e)

        self.linked_hwnd = new_linked_hwnd
        state = self.get_linked_wnd_state(self.linked_hwnd)
        self._update_sidebar(state)

        # 恢复监听线程
        self.turn_on_listener()

    def switch_root_wnd(self):
        print("切换到管理器窗口...")
        # 暂停监听线程
        self.turn_off_listener()

        # 置顶管理器
        TkWndUtils.bring_wnd_to_front(self.root, self.root)
        self.linked_hwnd = self.root_hwnd
        self._update_sidebar(self.get_linked_wnd_state(self.linked_hwnd))

        # 恢复监听线程
        self.turn_on_listener()

    # def start_drag(self, event):
    #     """
    #     记录鼠标起始位置
    #     """
    #     print("记录鼠标起始位置")
    #     self.offset_x = event.x
    #     self.offset_y = event.y
    #     self.pause_event.clear()
    #
    # def do_drag(self, event):
    #     """
    #     根据鼠标移动调整窗口位置
    #     """
    #     print("根据鼠标移动调整窗口位置")
    #     x = self.wnd.winfo_x() + (event.x - self.offset_x)
    #     y = self.wnd.winfo_y() + (event.y - self.offset_y)
    #     self.wnd.geometry(f"+{x}+{y}")
    #
    #     if self.hwnd_linked and win32gui.IsWindow(self.hwnd_linked):
    #         # 获取程序窗口和右侧区域的大小
    #         root_rect = win32gui.GetWindowRect(self.root_hwnd)
    #         panel_rect = win32gui.GetClientRect(self.bar_hwnd)
    #         linked_rect = win32gui.GetWindowRect(self.hwnd_linked)
    #
    #         new_x = panel_rect[2] + root_rect[0]
    #         new_y = root_rect[1]
    #         new_height = root_rect[3] - root_rect[1]
    #
    #         # 调整嵌入窗口的位置和大小
    #         win32gui.SetWindowPos(
    #             self.hwnd_linked,
    #             None,
    #             new_x,
    #             new_y,
    #             linked_rect[2] - linked_rect[0],
    #             new_height,
    #             win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW
    #         )
    #         print(f"嵌入窗口：原宽度x{new_height}+{new_x}+{new_y}")
    #
    # def stop_drag(self, event):
    #     """
    #     停止拖动
    #     """
    #     time.sleep(0.8)
    #     self.pause_event.set()
    #     print("停止拖动")

    def set_linked_wnd_maximized(self, is_maximized_with_sidebar):
        if not self.linked_hwnd or not win32gui.IsWindow(self.linked_hwnd):
            return

        # 恢复到非最大化状态
        win32gui.ShowWindow(self.linked_hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(self.linked_hwnd)

        if is_maximized_with_sidebar:
            # 获取当前窗口位置和大小
            linked_rect = win32gui.GetWindowRect(self.linked_hwnd)
            new_x = linked_rect[0] + self.bar_width
            new_width = linked_rect[2] - linked_rect[0] - self.bar_width

            # 调整窗口位置和大小
            win32gui.SetWindowPos(
                self.linked_hwnd,
                None,
                new_x,
                linked_rect[1],
                new_width,
                linked_rect[3] - linked_rect[1],
                win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW
            )
        else:
            # 使用保存的原始位置和大小
            win32gui.SetWindowPos(
                self.linked_hwnd,
                None,
                self.last_linked_rect[0],
                self.last_linked_rect[1],
                self.last_linked_rect[2] - self.last_linked_rect[0],
                self.last_linked_rect[3] - self.last_linked_rect[1],
                win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW
            )

    def find_foreground_wnd(self):
        """
        寻找前台的特定窗口
        :return:
        """
        print("链接窗口不在前台，重新寻找前台窗口...")
        hwnd_list = []
        # 获取当前所有账号
        tree = self.login_class.tree
        items = tree.get_children()
        for item in items:
            # 获取每个账号的hwnd
            sw, acc = item.split("/")
            hwnd, = subfunc_file.get_sw_acc_data(sw, acc, main_hwnd=None)
            hwnd_list.append(hwnd)

        hwnd_list.append(self.root_hwnd)

        self.linked_hwnd = None
        # 寻找前台窗口
        for hwnd in hwnd_list:
            if hwnd and win32gui.IsWindow(hwnd) and win32gui.GetForegroundWindow() == hwnd:
                self.linked_hwnd = hwnd
                self._update_sidebar(self.get_linked_wnd_state(self.linked_hwnd))
                break

    def wait_for_acc_wnd(self, sw, acc):
        """
        等待账号窗口出现
        :param acc:
        :param sw: 软件名称
        :return: 窗口句柄或None(超时)
        """
        self.turn_off_listener()
        time.sleep(1)
        # 打开详情页
        WndCreator.open_acc_detail(f"{sw}/{acc}", self)

        # 重新获取hwnd
        hwnd, = subfunc_file.get_sw_acc_data(sw, acc, main_hwnd=None)
        self.thread_result = hwnd
        self.turn_on_listener()

        # start_time = time.time()
        #
        # def on_tip_click(e):
        #     nonlocal last_time
        #     last_time = 0
        #
        # # print(start_time)
        # self.root.after(0, lambda: self.tip_label.bind("<Button-1>", on_tip_click))
        #
        # while True:
        #     hwnd = win32gui.GetForegroundWindow()
        #     # print(hwnd)
        #     if hwnd and win32gui.IsWindow(hwnd) and AccInfoFunc.is_hwnd_a_main_wnd_of_acc_on_sw(hwnd, sw, acc):
        #         self.thread_result = hwnd
        #         return
        #
        #     # 计算剩余时间
        #     elapsed_time = time.time() - start_time
        #     last_time = int(timeout - elapsed_time)
        #
        #     if last_time <= 0:
        #         self.root.after(0, lambda: self.tip_label.config(text=" "))
        #         self.thread_result = None
        #         return
        #
        #     # 更新提示信息
        #     self.root.after(0, lambda: self.tip_label.config(
        #         text=f"（点击可取消）窗口丢失，请{last_time}秒内打开对应窗口..."))
        #     time.sleep(0.02)


class SidebarTree(RadioTreeView, ABC):
    def __init__(self, parent_class, parent_frame, tree_tag, title_text=None):
        super().__init__(parent_class, parent_frame, tree_tag, title_text)

    def initialize_members_in_init(self):
        self.columns = (" ",)
        self.data_src = subfunc_file.get_sw_acc_data()
        pass

    def set_table_style(self):
        super().set_table_style()

        tree = self.tree
        # 特定列的宽度和样式设置
        tree.column("#0", minwidth=Constants.TREE_ID_MIN_WIDTH,
                    width=Constants.TREE_ID_WIDTH, stretch=tk.NO)
        tree.column(" ", minwidth=Constants.TREE_DSP_MIN_WIDTH,
                    width=Constants.TREE_DSP_WIDTH, anchor='w')

    def display_table(self):
        tree = self.tree.nametowidget(self.tree)
        sw_acc_data = self.data_src
        table_tag = self.table_tag

        # 假设你已经有了一个用于存储 sw 节点的字典
        sw_nodes = {}

        for sw in sw_acc_data:
            sw_data = sw_acc_data[sw]
            for acc in sw_data.keys():
                if table_tag == OnlineStatus.LOGIN and sw_data[acc].get("pid", None) is None:
                    continue
                if table_tag == OnlineStatus.LOGOUT and sw_data[acc].get("pid", None) is not None:
                    continue

                # display_name = "  " + AccInfoFunc.get_acc_origin_display_name(sw, acc)
                # 获取头像图像
                linked_acc = AccInfoFunc.get_real_acc(sw, acc)
                img = AccInfoFunc.get_acc_avatar_from_files(sw, linked_acc)
                img = img.resize(Constants.AVT_SIZE, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.photo_images.append(photo)

                # # 插入二级
                # # 如果该 sw 节点还没有插入过，先插入它
                # if sw not in sw_nodes:
                #     # 插入 sw 节点，并保存节点的 ID
                #     sw_node_id = tree.insert("", "end", iid=sw, open=True)
                #     sw_nodes[sw] = sw_node_id
                # else:
                #     # 已经有这个 sw 节点，使用已存储的 ID
                #     sw_node_id = sw_nodes[sw]
                #
                # # 插入 account 数据，作为 sw 节点的子节点
                # tree.insert(sw_node_id, "end", iid=f"{sw}/{acc}", image=photo)

                # 一级插入
                tree.insert("", "end", iid=f"{sw}/{acc}", image=photo)

    def click_on_id_column(self, click_time, item_id):
        # self.click_on_leaf_item(click_time, item_id, None)
        print(item_id)
        if click_time == 1:
            self.parent_class.switch_acc_wnd(item_id)

    def adjust_treeview_height(self, event):
        if event:
            # print(event.y)
            pass

        tree = self.tree.nametowidget(self.tree)

        total_rows = 0
        for root_item in tree.get_children():
            total_rows += TreeUtils.count_visible_rows_recursive(tree, root_item)
        print(total_rows)
        if self.table_tag == OnlineStatus.LOGOUT:
            set_height = min(total_rows, 5)
        elif self.table_tag == OnlineStatus.LOGIN:
            set_height = min(total_rows, 10)
        else:
            set_height = total_rows
        print(set_height)
        tree.configure(height=set_height)

# if __name__ == "__main__":
#     SidebarWnd.wait_for_acc_wnd(SW.WEIXIN)
