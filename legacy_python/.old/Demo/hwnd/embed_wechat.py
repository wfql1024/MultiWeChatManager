import tkinter as tk
from tkinter import messagebox, ttk
import win32gui
import win32con
import ctypes
import threading
import time


class App:
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
    app = App(root)
    root.mainloop()
