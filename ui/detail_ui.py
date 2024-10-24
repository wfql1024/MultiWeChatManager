# detail_ui.py
import base64
import ctypes
import os
import time
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

import psutil
import win32api
import win32con
import win32gui
from PIL import Image, ImageTk

from functions import func_detail, subfunc_file
from resources.config import Config
from resources.strings import Strings
from utils import string_utils, handle_utils, process_utils
from utils.handle_utils import Tooltip
from utils.process_utils import user32


class DetailWindow:
    def __init__(self, master, account, update_callback):
        self.master = master
        self.account = account
        self.update_callback = update_callback
        self.tooltip = None  # 初始化 tooltip 属性

        master.title(f"属性 - {self.account}")

        window_width = 265
        window_height = 345
        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        master.geometry(f"{window_width}x{window_height}+{x}+{y}")

        master.overrideredirect(True)
        master.overrideredirect(False)
        master.attributes('-toolwindow', True)

        master.grab_set()

        frame = ttk.Frame(master, padding="12")
        frame.pack(fill=tk.BOTH, expand=True)

        # 头像
        self.top_frame = ttk.Frame(frame)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)
        self.avatar_frame = ttk.Frame(self.top_frame)
        self.avatar_frame.pack(side=tk.LEFT, padx=5, pady=10, fill=tk.X)
        self.avatar_label = ttk.Label(self.avatar_frame)
        self.avatar_label.pack(side=tk.TOP)
        self.avatar_status_label = ttk.Label(self.avatar_frame, text="")
        self.avatar_status_label.pack(side=tk.BOTTOM)

        # PID
        self.pid_label = ttk.Label(self.top_frame, text="PID: ")
        self.pid_label.pack(side=tk.LEFT, padx=5, pady=10, anchor="w")

        # 原始微信号
        self.original_account_label = ttk.Label(frame, text=f"原wxid: {self.account}")
        self.original_account_label.pack(side=tk.TOP, pady=(5, 10), anchor="w")

        # 当前微信号
        self.current_account_label = ttk.Label(frame, text="现wxid: ")
        self.current_account_label.pack(side=tk.TOP, pady=(5, 10), anchor="w")

        # 昵称
        self.nickname_label = ttk.Label(frame, text="昵    称: ")
        self.nickname_label.pack(side=tk.TOP, pady=(5, 10), anchor="w")

        # 备注
        self.note_frame = ttk.Frame(frame)
        self.note_frame.pack(side=tk.TOP, pady=(5, 10), fill=tk.X, expand=True)

        note_label = ttk.Label(self.note_frame, text="备    注：")
        note_label.pack(side=tk.LEFT, anchor="w")

        note, = subfunc_file.get_acc_details_from_acc_json(self.account, note=None)
        if not note:
            self.note_var = tk.StringVar(value="")
        else:
            self.note_var = tk.StringVar(value=note)
        self.note_entry = ttk.Entry(self.note_frame, textvariable=self.note_var, width=25)
        self.note_entry.pack(side=tk.LEFT, pady=(5, 10), fill=tk.X)

        # 按钮区域
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM, expand=True)

        self.fetch_button = ttk.Button(button_frame, text="获取", command=self.fetch_data)
        self.fetch_button.pack(side=tk.LEFT, padx=(0, 5))

        save_button = ttk.Button(button_frame, text="保存", command=self.save_note)
        save_button.pack(side=tk.RIGHT, padx=(0, 5))

        ttk.Frame(frame).pack(fill=tk.BOTH, expand=True)

        print(f"加载控件完成")

        self.load_data_label()

    def load_data_label(self):
        print(f"尝试获取...")

        # 构建头像文件路径
        avatar_path = os.path.join(Config.PROJ_USER_PATH, f"{self.account}", f"{self.account}.jpg")
        print(f"加载对应头像...")

        # 加载头像
        if os.path.exists(avatar_path):
            print(f"对应头像存在...")
        else:
            # 如果没有，检查default.jpg
            print(f"没有对应头像，加载默认头像...")
            default_path = os.path.join(Config.PROJ_USER_PATH, f"default.jpg")
            base64_string = Strings.DEFAULT_AVATAR_BASE64
            image_data = base64.b64decode(base64_string)
            with open(default_path, "wb") as f:
                f.write(image_data)
            print(f"默认头像已保存到 {default_path}")
            avatar_path = default_path
        avatar_url, alias, nickname, pid = subfunc_file.get_acc_details_from_acc_json(
            self.account,
            avatar_url=None,
            alias="请获取数据",
            nickname="请获取数据",
            pid=None
        )
        self.load_avatar(avatar_path, avatar_url)
        self.current_account_label.config(text=f"现wxid: {alias}")
        try:
            self.nickname_label.config(text=f"昵    称: {nickname}")
        except Exception as e:
            print(e)
            self.nickname_label.config(text=f"昵    称: {string_utils.clean_display_name(nickname)}")
        self.pid_label.config(text=f"PID: {pid}")
        if not pid:
            self.disable_fetch_button()
            self.pid_label.config(text=f"PID: 未登录")
            subfunc_file.update_acc_details_to_acc_json(self.account, has_mutex=True)
        else:
            has_mutex, = subfunc_file.get_acc_details_from_acc_json(self.account, has_mutex=True)
            if has_mutex:
                self.pid_label.config(text=f"PID: {pid}\n(有互斥体)")
            else:
                self.pid_label.config(text=f"PID: {pid}\n(无互斥体)")
            self.enable_fetch_button()
        print(f"载入数据完成")

    def disable_fetch_button(self):
        self.fetch_button.state(['disabled'])
        if not self.tooltip:
            self.tooltip = Tooltip(self.fetch_button, "请登录后获取")

    def enable_fetch_button(self):
        self.fetch_button.state(['!disabled'])
        if self.tooltip:
            self.tooltip.widget.unbind("<Enter>")
            self.tooltip.widget.unbind("<Leave>")
            self.tooltip = None

    def load_avatar(self, avatar_path, avatar_url):
        try:
            img = Image.open(avatar_path)
            img = img.resize((44, 44), Image.LANCZOS)  # type: ignore
            photo = ImageTk.PhotoImage(img)
            self.avatar_label.config(image=photo)
            self.avatar_label.image = photo

            if avatar_url:
                self.avatar_label.bind("<Enter>", lambda event: self.avatar_label.config(cursor="hand2"))
                self.avatar_label.bind("<Leave>", lambda event: self.avatar_label.config(cursor=""))
                self.avatar_label.bind("<Button-1>", lambda event: webbrowser.open(avatar_url))
                self.avatar_status_label.forget()
            else:
                self.avatar_label.bind("<Enter>", lambda event: self.avatar_label.config(cursor=""))
                self.avatar_label.bind("<Leave>", lambda event: self.avatar_label.config(cursor=""))
                self.avatar_label.unbind("<Button-1>")
                self.avatar_status_label.config(text="未更新")
        except Exception as e:
            print(f"Error loading avatar: {e}")
            self.avatar_label.config(text="无头像")

    def fetch_data(self):

        pid, = subfunc_file.get_acc_details_from_acc_json(self.account, pid=None)
        if not pid:
            self.disable_fetch_button()
            messagebox.showinfo("提示", "未检测到该账号登录")
            return

        try:
            psutil.Process(pid)
        except psutil.NoSuchProcess:
            print(f"No process found with PID: {pid}")
            self.disable_fetch_button()
            messagebox.showinfo("提示", "未检测到该账号登录")
            return

        success = func_detail.fetch_acc_detail_by_pid(pid, self.account, self.disable_fetch_button,
                                                      self.enable_fetch_button)
        if success is False:
            messagebox.showerror(f"错误", "失败：超时")
        # 刷新显示
        self.load_data_label()

    def save_note(self):
        new_note = self.note_var.get().strip()
        if new_note == "":
            subfunc_file.update_acc_details_to_acc_json(self.account, note=None)
        else:
            subfunc_file.update_acc_details_to_acc_json(self.account, note=new_note)
        self.update_callback()
        self.master.destroy()


