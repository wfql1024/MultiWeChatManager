import ctypes
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import win32api
import win32con
import win32gui


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


def embed_wnd_into_right_panel(right_panel_hwnd, target_hwnd):
    """
    将微信窗口嵌入到右侧主窗口中，并最大化
    """
    # 设置微信窗口的父窗口为右侧主窗口
    ctypes.windll.user32.SetParent(target_hwnd, right_panel_hwnd)

    # 获取右侧主窗口的大小
    right_rect = win32gui.GetClientRect(right_panel_hwnd)

    # 设置微信窗口的位置和大小
    win32gui.SetWindowPos(
        target_hwnd,  # 目标窗口句柄
        None,  # 不改变 Z 顺序
        0,  # X 坐标
        0,  # Y 坐标
        right_rect[2],  # 宽度为右侧主窗口的宽度
        right_rect[3],  # 高度为右侧主窗口的高度
        win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW  # 显示窗口
    )


class SidebarUI:
    def __init__(self, root):
        self.root = root
        self.root.title("窗口嵌入示例")
        self.root.geometry("1600x800")  # 窗口大小
        self.target_handle = None  # 存储目标窗口句柄
        self.left_frame_width = 96
        self.root.overrideredirect(True)  # 去除窗口标题栏

        # 拖拽相关变量
        self.offset_x = 0
        self.offset_y = 0

        # 绑定鼠标事件实现拖拽功能
        self.root.bind("<Button-1>", self.start_drag)
        self.root.bind("<B1-Motion>", self.do_drag)

        # 左侧栏
        self.left_frame = tk.Frame(root, bg="gray", width=self.left_frame_width)
        self.left_frame.pack(side="left", fill="y")
        self.left_frame.pack_propagate(False)  # 禁止根据子控件调整大小

        # 输入框
        self.handle_entry = ttk.Entry(self.left_frame, width=5)
        self.handle_entry.pack(pady=20)

        # 按钮：绑定
        self.bind_button = tk.Button(self.left_frame, text="绑定窗口", command=self.bind_window)
        self.bind_button.pack(pady=10)

        # 按钮：解绑
        self.unbind_button = tk.Button(self.left_frame, text="解绑窗口", command=self.unbind_window)
        self.unbind_button.pack(pady=10)

        # 剩余右侧区域（用于嵌入窗口的地方）
        self.right_frame_hwnd = self.create_right_frame()
        self.monitor_thread = threading.Thread(target=self.monitor_window_position, daemon=True)
        self.monitor_thread.start()

        self.ensure_taskbar_visibility()
        # self.nested_window_drag_thread = threading.Thread(target=self.monitor_nested_window_drag, daemon=True)
        # self.nested_window_drag_thread.start()

    def ensure_taskbar_visibility(self):
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
        right_frame.pack(side="right", fill="both", expand=True)

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

        self.target_handle = int(handle)
        if not win32gui.IsWindow(self.target_handle):
            messagebox.showerror("错误", "输入的句柄不是有效窗口！")
            return

        # 设置为右侧区域的子窗口
        win32gui.SetParent(self.target_handle, self.right_frame_hwnd)
        win32gui.ShowWindow(self.target_handle, win32con.SW_MAXIMIZE)
        messagebox.showinfo("成功", f"窗口 {self.target_handle} 已嵌入！")

    def unbind_window(self):
        """
        将目标窗口从右侧区域中解绑
        """
        if self.target_handle and win32gui.IsWindow(self.target_handle):
            win32gui.SetParent(self.target_handle, None)
            messagebox.showinfo("成功", f"窗口 {self.target_handle} 已解绑！")
            self.target_handle = None
        else:
            messagebox.showerror("错误", "当前没有已绑定的窗口！")

    def monitor_window_position(self):
        """
        实时调整目标窗口的位置，确保不会覆盖左侧栏
        """
        while True:
            if self.target_handle and win32gui.IsWindow(self.target_handle):
                # 获取程序窗口和右侧区域的大小
                root_rect = win32gui.GetWindowRect(ctypes.windll.user32.GetParent(self.root.winfo_id()))
                right_rect = win32gui.GetClientRect(self.right_frame_hwnd)

                new_x = self.left_frame_width
                new_y = 0
                new_width = right_rect[2] - self.left_frame_width
                new_height = right_rect[3]

                # 调整嵌入窗口的位置和大小
                win32gui.SetWindowPos(
                    self.target_handle,
                    None,
                    new_x,
                    new_y,
                    new_width,
                    new_height,
                    win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW
                )
            time.sleep(0.05)

    def monitor_nested_window_drag(self):
        """
        监控嵌套窗口的拖动行为，并同步调整主程序窗口的位置。
        """
        last_position = None
        while True:
            if self.target_handle and win32gui.IsWindow(self.target_handle):
                # 获取嵌套窗口的位置
                nested_rect = win32gui.GetWindowRect(self.target_handle)
                if last_position is None:
                    last_position = nested_rect

                # 判断窗口是否移动
                if nested_rect != last_position:
                    # 计算嵌套窗口的移动量
                    dx = nested_rect[0] - last_position[0]
                    dy = nested_rect[1] - last_position[1]

                    # 调整主窗口的位置
                    main_x = self.root.winfo_x() + dx
                    main_y = self.root.winfo_y() + dy
                    self.root.geometry(f"+{main_x}+{main_y}")

                    # 更新上次的位置记录
                    last_position = nested_rect
            time.sleep(0.05)

    def start_drag(self, event):
        """
        记录鼠标起始位置
        """
        self.offset_x = event.x
        self.offset_y = event.y

    def do_drag(self, event):
        """
        根据鼠标移动调整窗口位置
        """
        x = self.root.winfo_x() + (event.x - self.offset_x)
        y = self.root.winfo_y() + (event.y - self.offset_y)
        self.root.geometry(f"+{x}+{y}")

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


if __name__ == "__main__":
    root = tk.Tk()
    app = SidebarUI(root)
    root.mainloop()
