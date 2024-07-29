# func_about.py
import tkinter as tk
from tkinter import ttk


class AboutWindow:
    def __init__(self, master):
        self.master = master
        master.title("关于微信多开管理器")

        window_width = 600
        window_height = 250
        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        master.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # 移除窗口装饰并设置为工具窗口
        master.overrideredirect(True)
        master.overrideredirect(False)
        master.attributes('-toolwindow', True)

        frame = ttk.Frame(master, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(frame, text="微信多开管理器", font=("", 16, "bold"))
        title_label.pack(pady=(0, 10))

        version_label = ttk.Label(frame, text="版本号：1.0.79 Beta", font=("", 10))
        version_label.pack()

        author_label = ttk.Label(frame, text="原创作者：吾峰起浪（吾爱破解网 wfql1024）", font=("", 10))
        author_label.pack(pady=(10, 0))

        thanks_label = ttk.Label(frame, text="鸣谢子工具\"PC微信多开器\"提供者：吾爱破解网 lyie15", font=("", 10))
        thanks_label.pack(pady=(5, 0))

        copyright_label = ttk.Label(frame, text="Copyright © 2024 吾峰起浪. All rights reserved.", font=("", 8))
        copyright_label.pack(side=tk.BOTTOM, pady=(20, 0))

        ok_button = ttk.Button(frame, text="确定", command=master.destroy)
        ok_button.pack(side=tk.BOTTOM, pady=(20, 0))
