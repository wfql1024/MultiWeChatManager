import tkinter as tk

from tkinter import ttk


class LoadingWindow:
    def __init__(self, master):
        self.master = master
        self.window = tk.Toplevel(master)
        self.window.withdraw()  # 初始时隐藏窗口
        self.window.title("加载中")

        window_width = 300
        window_height = 100

        # 计算窗口位置
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.window.resizable(False, False)

        self.label = ttk.Label(self.window, text="正在载入，请稍等……")
        self.label.pack(pady=20)

        self.progress = ttk.Progressbar(self.window, mode="indeterminate", length=200)
        self.progress.pack(pady=10)

        self.window.deiconify()  # 显示窗口
        self.progress.start(10)

    def destroy(self):
        if self.window.winfo_exists():
            self.progress.stop()
            self.window.destroy()
