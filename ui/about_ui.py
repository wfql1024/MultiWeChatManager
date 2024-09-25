# about_ui.py
import re
import tkinter as tk
import webbrowser
from tkinter import ttk

from resources import Config, Strings


class AboutWindow:
    def __init__(self, master):
        self.master = master
        master.title("关于微信多开管理器")

        window_width = 640
        window_height = 500
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

        with open(Config.VERSION_FILE, 'r', encoding='utf-8') as version_file:
            version_info = version_file.read()
            # 使用正则表达式提取文件版本
            match = re.search(r'(\d+,\s*\d+,\s*\d+,\s*\d+)', version_info)
            version_number = match.group(0) if match else "未知版本"

        version_label = ttk.Label(frame, text=f"版本号：{version_number}", font=("", 10))

        version_label.pack()

        # 原创作者标签
        author_label = ttk.Label(frame, text="开发者：吾峰起浪", font=("", 10))
        author_label.pack(pady=(10, 0))

        # 创建 GitHub 链接标签
        github_link = tk.Label(frame, text=f"GitHub开源：{Strings.GITHUB_REPO}", font=("", 10), fg="blue",
                               cursor="hand2")
        github_link.pack(pady=(5, 0))

        # 哔哩哔哩主页链接标签
        bilibili_link = tk.Label(frame, text=f"哔哩哔哩主页：{Strings.BILIBILI_SPACE}", font=("", 10), fg="blue",
                                 cursor="hand2")
        bilibili_link.pack(pady=(5, 0))

        # 绑定点击事件到标签
        github_link.bind("<Button-1>", lambda e: webbrowser.open_new(Strings.GITHUB_REPO))
        bilibili_link.bind("<Button-1>", lambda e: webbrowser.open_new(Strings.BILIBILI_SPACE))

        # 创建一个用于放置滚动文本框的框架
        thanks_frame = ttk.Frame(frame)
        thanks_frame.pack(pady=(5, 0), fill=tk.BOTH, expand=True)

        # 创建滚动条
        scrollbar = tk.Scrollbar(thanks_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 创建不可编辑且可滚动的文本框
        thanks_text = tk.Text(thanks_frame, wrap=tk.WORD, font=("", 10), height=4, yscrollcommand=scrollbar.set)
        thanks_text.insert(tk.END, "鸣谢\n", "title")
        # 配置标签样式
        thanks_text.tag_configure("title", font=("", 12), justify="center")  # 调整字号并居中
        thanks_text.insert(tk.END, Strings.THANKS_TEXT)
        thanks_text.config(state=tk.DISABLED)  # 设置文本框为不可编辑
        thanks_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 配置滚动条
        scrollbar.config(command=thanks_text.yview)

        # 创建一个自定义的样式
        style = ttk.Style()
        style.configure("Red.TLabel", foreground="red", font=("", 8))

        ok_button = ttk.Button(frame, text="确定", command=master.destroy)
        ok_button.pack(side=tk.BOTTOM, pady=(20, 0))

        # 使用自定义的样式创建标签
        disclaimer_label = ttk.Label(frame, text="仅供学习交流，严禁用于商业用途，请于24小时内删除", style="Red.TLabel")
        disclaimer_label.pack(side=tk.BOTTOM, pady=(20, 0))

        # 版权信息标签
        copyright_label = ttk.Label(frame, text="Copyright © 2024 吾峰起浪. All rights reserved.", font=("", 8))
        copyright_label.pack(side=tk.BOTTOM, pady=(20, 0))
