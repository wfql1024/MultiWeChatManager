import tkinter as tk
from tkinter import messagebox, ttk
import ctypes
from ctypes import wintypes
import threading
import time

# 定义 Windows API 函数
user32 = ctypes.windll.user32

# 手动定义 WINDOWPLACEMENT 结构体
class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_uint),
        ("flags", ctypes.c_uint),
        ("showCmd", ctypes.c_uint),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
    ]

# 定义窗口状态常量
SW_MAXIMIZE = 3
SW_RESTORE = 9

import win32api
import win32con
import win32gui

from public_class.global_members import GlobalMembers


def create_button_in_wnd(hwnd, x, y, width, height, button_text="Click Me"):
    # 加载kernel32.dll，用于获取模块句柄
    kernel32 = ctypes.windll.kernel32

    # 定义按钮ID
    BUTTON_ID = 1001

    # 获取当前模块句柄
    h_instance = kernel32.GetModuleHandleW(None)

    # 创建一个按钮控件，放置在指定的窗口位置
    h_button = win32gui.CreateWindowEx(
        0,  # 无扩展样式
        "Button",  # 控件类型为按钮
        button_text,  # 按钮上的文字
        win32con.WS_VISIBLE | win32con.WS_CHILD | win32con.BS_DEFPUSHBUTTON,  # 控件样式：可见、子窗口、默认按钮样式
        x,  # X坐标
        y,  # Y坐标
        width,  # 宽度
        height,  # 高度
        hwnd,  # 父窗口句柄
        BUTTON_ID,  # 控件ID
        h_instance,  # 应用程序实例句柄
        None  # 无额外参数
    )

    # 检查按钮是否创建成功
    if not h_button:
        print("按钮创建失败")
    else:
        print("按钮创建成功")
        return h_button


def create_frame_wnd(title, width, height):
    """
    创建一个框架窗口
    """
    wc = win32gui.WNDCLASS()
    wc.lpfnWndProc = win32gui.DefWindowProc  # 默认窗口过程
    wc.lpszClassName = 'MyFrameWindow'
    wc.hInstance = win32api.GetModuleHandle(None)
    wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
    wc.hbrBackground = win32gui.GetStockObject(win32con.WHITE_BRUSH)

    class_atom = win32gui.RegisterClass(wc)

    hwnd = win32gui.CreateWindow(
        class_atom,  # 窗口类名
        title,  # 窗口标题
        win32con.WS_OVERLAPPEDWINDOW,  # 窗口样式
        100,  # X 坐标
        100,  # Y 坐标
        width,  # 窗口宽度
        height,  # 窗口高度
        0,  # 父窗口句柄
        0,  # 菜单句柄
        wc.hInstance,  # 实例句柄
        None  # 额外参数
    )

    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
    return hwnd


def create_left_panel(frame_hwnd, width):
    """
    创建左侧面板，宽度固定为 75
    """
    wc = win32gui.WNDCLASS()
    wc.lpfnWndProc = win32gui.DefWindowProc
    wc.lpszClassName = 'LeftPanel'
    wc.hInstance = win32api.GetModuleHandle(None)
    wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
    wc.hbrBackground = win32gui.GetStockObject(win32con.LTGRAY_BRUSH)

    class_atom = win32gui.RegisterClass(wc)

    panel_hwnd = win32gui.CreateWindow(
        class_atom,  # 窗口类名
        "",  # 窗口标题
        win32con.WS_CHILD | win32con.WS_VISIBLE,  # 窗口样式
        0,  # X 坐标（左侧靠齐）
        0,  # Y 坐标
        width,  # 面板宽度
        win32gui.GetClientRect(frame_hwnd)[3],  # 面板高度与父窗口一样
        frame_hwnd,  # 父窗口句柄
        0,  # 菜单句柄
        wc.hInstance,  # 实例句柄
        None  # 额外参数
    )

    win32gui.ShowWindow(panel_hwnd, win32con.SW_SHOW)
    return panel_hwnd


def create_right_panel(frame_hwnd, x, width, height):
    """
    创建右侧主窗口，位置从 x = 75 开始
    """
    wc = win32gui.WNDCLASS()
    wc.lpfnWndProc = win32gui.DefWindowProc
    wc.lpszClassName = 'RightPanel'
    wc.hInstance = win32api.GetModuleHandle(None)
    wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
    wc.hbrBackground = win32gui.GetStockObject(win32con.WHITE_BRUSH)

    class_atom = win32gui.RegisterClass(wc)

    right_panel_hwnd = win32gui.CreateWindow(
        class_atom,  # 窗口类名
        "",  # 窗口标题
        win32con.WS_CHILD | win32con.WS_VISIBLE,  # 窗口样式
        x,  # X 坐标（右侧靠齐）
        0,  # Y 坐标
        width,  # 右侧主窗口的宽度
        height,  # 右侧主窗口的高度
        frame_hwnd,  # 父窗口句柄
        0,  # 菜单句柄
        wc.hInstance,  # 实例句柄
        None  # 额外参数
    )

    win32gui.ShowWindow(right_panel_hwnd, win32con.SW_SHOW)
    return right_panel_hwnd




# 定义监听线程
def window_state_listener(hwnd_target, root):
    while True:
        # 获取目标窗口的状态
        placement = WINDOWPLACEMENT()
        placement.length = ctypes.sizeof(placement)
        user32.GetWindowPlacement(hwnd_target, ctypes.byref(placement))

        # 判断目标窗口的状态
        if placement.showCmd == SW_MAXIMIZE:
            # 目标窗口最大化，将我的窗口也最大化
            print("最大化")
            # root.state("zoomed")
        elif placement.showCmd == SW_RESTORE:
            # 目标窗口恢复常规大小，将我的窗口也恢复常规大小
            print("恢复")
            root.state("normal")
            root.geometry("1600x800")

        # 间隔 20ms
        time.sleep(0.02)


class SidebarUI:
    def __init__(self):
        self.listener_running = None
        self.root_hwnd = None
        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root
        self.root.title("窗口嵌入示例")
        # self.root.geometry("1600x800")  # 窗口大小
        self.hwnd_embed = None  # 存储目标窗口句柄
        self.left_frame_width = 96
        self.pause_event = threading.Event()
        self.root.overrideredirect(True)  # 去除窗口标题栏

        self.root_hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())

        # 拖拽相关变量
        self.offset_x = 0
        self.offset_y = 0

        # 绑定鼠标事件实现拖拽功能
        self.root.bind("<Button-1>", self.start_drag)
        self.root.bind("<B1-Motion>", self.do_drag)
        self.root.bind("<ButtonRelease-1>", self.stop_drag)

        # 左侧栏
        self.left_frame = tk.Frame(self.root, bg="gray", width=self.left_frame_width)
        self.left_frame.pack(side="left", fill="y")
        self.left_frame.pack_propagate(False)  # 禁止根据子控件调整大小
        self.left_frame_hwnd = ctypes.windll.user32.GetParent(self.left_frame.winfo_id())

        # 输入框
        self.handle_entry = ttk.Entry(self.left_frame, width=5)
        self.handle_entry.pack(pady=20)

        # 按钮：绑定
        self.bind_button = tk.Button(self.left_frame, text="绑定窗口", command=self.bind_window)
        self.bind_button.pack(pady=10)

        # # 按钮：解绑
        # self.unbind_button = tk.Button(self.left_frame, text="解绑窗口", command=self.unbind_window)
        # self.unbind_button.pack(pady=10)

        # 恢复窗口
        self.restore_button = tk.Button(self.left_frame, text="恢复窗口", command=self.restore_to_main_ui)
        self.restore_button.pack(pady=10)

        self.ensure_taskbar_visibility()

        self.nested_window_drag_thread = threading.Thread(target=self.monitor_nested_window_drag, daemon=True)
        self.listener_running = True
        self.nested_window_drag_thread.start()

    def restore_to_main_ui(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        try:
            self.listener_running = False  # 停止线程
            self.nested_window_drag_thread.join()  # 等待线程结束
        except KeyboardInterrupt:
            self.listener_running = False
            self.nested_window_drag_thread.join()
        self.root_class.initialize_in_init()
        self.root.unbind("<Button-1>")
        self.root.unbind("<B1-Motion>")
        self.root.unbind("<ButtonRelease-1>")

    @staticmethod
    def ensure_taskbar_visibility():
        """
        确保窗口在任务栏中显示
        """
        hwnd = win32gui.GetForegroundWindow()  # 获取窗口句柄
        print("hwnd:", hwnd)
        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)  # 隐藏窗口
        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) | win32con.WS_EX_APPWINDOW
        )  # 设置扩展样式
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)  # 显示窗口

    def create_right_frame(self):
        """
        创建右侧嵌入区域的 Frame
        """
        right_frame = tk.Frame(self.root, bg="white")
        right_frame.pack(side="right")

        # 获取 Tkinter 窗口句柄
        hwnd = ctypes.windll.user32.GetParent(right_frame.winfo_id())
        return hwnd

    def bind_window(self):
        """
        将目标窗口设置为右侧区域的子窗口
        """
        handle = self.handle_entry.get()
        if not handle.isdigit():
            messagebox.showerror("错误", "请输入有效的窗口句柄 (数字)！")
            return

        self.hwnd_embed = int(handle)
        if not win32gui.IsWindow(self.hwnd_embed):
            messagebox.showerror("错误", "输入的句柄不是有效窗口！")
            return

        # 设置为右侧区域的子窗口
        # win32gui.SetParent(self.hwnd_embed, None)
        # win32gui.ShowWindow(self.hwnd_embed, win32con.SW_RESTORE)
        messagebox.showinfo("成功", f"窗口 {self.hwnd_embed} 已嵌入！")

        # listener_thread = threading.Thread(
        #     target=window_state_listener,
        #     args=(self.hwnd_embed, self.root),
        #     daemon=True
        # )
        # listener_thread.start()

    # def unbind_window(self):
    #     """
    #     将目标窗口从右侧区域中解绑
    #     """
    #     if self.hwnd_embed and win32gui.IsWindow(self.hwnd_embed):
    #         win32gui.SetParent(self.hwnd_embed, None)
    #         messagebox.showinfo("成功", f"窗口 {self.hwnd_embed} 已解绑！")
    #         self.hwnd_embed = None
    #     else:
    #         messagebox.showerror("错误", "当前没有已绑定的窗口！")

    def monitor_nested_window_drag(self):
        """
        监控嵌套窗口的拖动行为，并同步调整主程序窗口的位置。
        """
        while (self.listener_running):
            if self.hwnd_embed and win32gui.IsWindow(self.hwnd_embed):
                # 获取程序窗口和右侧区域的大小
                embed_rect = win32gui.GetWindowRect(self.hwnd_embed)
                panel_rect = win32gui.GetClientRect(self.left_frame_hwnd)

                new_x = - panel_rect[2] + embed_rect[0]
                new_y = embed_rect[1]
                new_height = embed_rect[3] - embed_rect[1]

                self.root.geometry(f"{self.left_frame_width}x{new_height}+{new_x}+{new_y}")
                print(embed_rect)
                print(f"主窗口：{self.left_frame_width}x{new_height}+{new_x}+{new_y}")

            self.pause_event.wait()
            time.sleep(0.02)

    def start_drag(self, event):
        """
        记录鼠标起始位置
        """
        print("记录鼠标起始位置")
        self.offset_x = event.x
        self.offset_y = event.y
        self.pause_event.clear()

    def do_drag(self, event):
        """
        根据鼠标移动调整窗口位置
        """
        print("根据鼠标移动调整窗口位置")
        x = self.root.winfo_x() + (event.x - self.offset_x)
        y = self.root.winfo_y() + (event.y - self.offset_y)
        self.root.geometry(f"+{x}+{y}")

        if self.hwnd_embed and win32gui.IsWindow(self.hwnd_embed):
            # 获取程序窗口和右侧区域的大小
            root_rect = win32gui.GetWindowRect(self.root_hwnd)
            panel_rect = win32gui.GetClientRect(self.left_frame_hwnd)
            embed_rect = win32gui.GetWindowRect(self.hwnd_embed)

            new_x = panel_rect[2] + root_rect[0]
            new_y = root_rect[1]
            new_height = root_rect[3] - root_rect[1]

            # 调整嵌入窗口的位置和大小
            win32gui.SetWindowPos(
                self.hwnd_embed,
                None,
                new_x,
                new_y,
                embed_rect[2] - embed_rect[0],
                new_height,
                win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW
            )
            print(f"嵌入窗口：原宽度x{new_height}+{new_x}+{new_y}")

    def stop_drag(self, event):
        """
        停止拖动
        """
        time.sleep(0.8)
        self.pause_event.set()
        print("停止拖动")

    @staticmethod
    def find_all_windows_by_class_and_title(class_name, window_title=None):
        def enum_windows_callback(hwnd, results):
            # 获取窗口的类名和标题
            if win32gui.IsWindowVisible(hwnd):
                curr_class_name = win32gui.GetClassName(hwnd)
                curr_window_title = win32gui.GetWindowText(hwnd)
                # 仅匹配类名，若window_title不为空则继续匹配标题
                if curr_class_name == class_name and (window_title is None or curr_window_title == window_title):
                    results.append(hwnd)

        results = []
        win32gui.EnumWindows(enum_windows_callback, results)
        return results
