# detail_ui.py
import base64
import os
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

import psutil
from PIL import Image, ImageTk

from functions import func_setting, func_detail
from resources.config import Config
from resources.strings import Strings
from utils import json_utils
from utils.window_utils import Tooltip


class DetailWindow:
    def __init__(self, master, account, account_manager, update_callback):
        self.account_data = None
        self.master = master
        self.account = account
        self.account_manager = account_manager
        self.update_callback = update_callback
        self.tooltip = None  # 初始化 tooltip 属性

        master.title(f"属性 - {account}")

        window_width = 275
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
        self.avatar_frame = ttk.Frame(frame)
        self.avatar_frame.pack(side=tk.TOP, pady=(5, 10), fill=tk.X)
        self.avatar_label = ttk.Label(self.avatar_frame)
        self.avatar_label.pack(side=tk.LEFT)
        self.avatar_status_label = ttk.Label(self.avatar_frame, text="")
        self.avatar_status_label.pack(side=tk.LEFT, padx=(10, 0))

        # PID
        self.pid_label = ttk.Label(frame, text="PID: ")
        self.pid_label.pack(side=tk.TOP, pady=(5, 10), anchor="w")

        # 原始微信号
        self.original_account_label = ttk.Label(frame, text=f"原始微信号: {account}")
        self.original_account_label.pack(side=tk.TOP, pady=(5, 10), anchor="w")

        # 当前微信号
        self.current_account_label = ttk.Label(frame, text="当前微信号: ")
        self.current_account_label.pack(side=tk.TOP, pady=(5, 10), anchor="w")

        # 昵称
        self.nickname_label = ttk.Label(frame, text="昵称: ")
        self.nickname_label.pack(side=tk.TOP, pady=(5, 10), anchor="w")

        # 备注
        self.note_frame = ttk.Frame(frame)
        self.note_frame.pack(side=tk.TOP, pady=(5, 10), fill=tk.X, expand=True)

        note_label = ttk.Label(self.note_frame, text="备注：")
        note_label.pack(side=tk.LEFT, anchor="w")

        self.note_var = tk.StringVar(value=self.account_manager.get_account_note(account))
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

        print("加载控件完成")

        self.load_data_label()

    def load_data_label(self):
        self.account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
        print("尝试获取...")
        data_path = func_setting.get_wechat_data_path()

        # 构建头像文件路径
        avatar_path = os.path.join(Config.PROJ_USER_PATH, f"{self.account}", f"{self.account}.jpg")
        print("加载对应头像...")

        # 加载头像
        if os.path.exists(avatar_path):
            print("对应头像存在...")
            avatar_url = self.account_data.get(self.account, {}).get("avatar_url", None)
            self.load_avatar(avatar_path, avatar_url)
        else:
            # 如果没有，检查default.jpg
            print("没有对应头像，加载默认头像...")
            default_path = os.path.join(Config.PROJ_USER_PATH, f"default.jpg")
            base64_string = Strings.DEFAULT_AVATAR_BASE64
            image_data = base64.b64decode(base64_string)
            with open(default_path, "wb") as f:
                f.write(image_data)
            print(f"默认头像已保存到 {default_path}")
            avatar_url = self.account_data.get(self.account, {}).get("avatar_url", None)
            self.load_avatar(default_path, avatar_url)


        # 更新其他标签
        pid = self.account_data.get(self.account, {}).get("pid", None)
        self.pid_label.config(text=f"PID: {pid}")
        if not pid:
            self.disable_fetch_button()
        else:
            self.enable_fetch_button()
        self.current_account_label.config(
            text=f"当前微信号: {self.account_data.get(self.account, {}).get("alias", "请获取数据")}")
        self.nickname_label.config(
            text=f"昵称: {self.account_data.get(self.account, {}).get("nickname", "请获取数据")}")

        json_utils.save_json_data(Config.ACC_DATA_JSON_PATH, self.account_data)
        print("载入数据完成")

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
            img = img.resize((44, 44), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.avatar_label.config(image=photo)
            self.avatar_label.image = photo

            if avatar_url:
                self.avatar_label.bind("<Enter>", lambda event: self.avatar_label.config(cursor="hand2"))
                self.avatar_label.bind("<Leave>", lambda event: self.avatar_label.config(cursor=""))
                self.avatar_label.bind("<Button-1>", lambda event: webbrowser.open(avatar_url))
                self.avatar_status_label.config(text="")
            else:
                self.avatar_label.bind("<Enter>", lambda event: self.avatar_label.config(cursor=""))
                self.avatar_label.bind("<Leave>", lambda event: self.avatar_label.config(cursor=""))
                self.avatar_label.unbind("<Button-1>")
                self.avatar_status_label.config(text="头像未更新")
        except Exception as e:
            print(f"Error loading avatar: {e}")
            self.avatar_label.config(text="无头像")

    def fetch_data(self):
        self.account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)

        pid = self.account_data.get(self.account, {}).get("pid", "")
        if not pid:
            self.disable_fetch_button()
            messagebox.showinfo("提示", "未检测到该账号登录")
            return

        try:
            psutil.Process(pid)
        except psutil.NoSuchProcess:
            print(f"No process found with PID: {pid}")
            json_utils.save_json_data(Config.ACC_DATA_JSON_PATH, self.account_data)
            self.disable_fetch_button()
            messagebox.showinfo("提示", "未检测到该账号登录")
            return

        json_utils.save_json_data(Config.ACC_DATA_JSON_PATH, self.account_data)

        func_detail.fetch_account_detail(pid, self.account, self.disable_fetch_button, self.enable_fetch_button)
        # 刷新显示
        self.load_data_label()

    def save_note(self):
        new_note = self.note_var.get().strip()
        self.account_manager.update_note(self.account, new_note)
        self.update_callback()
        self.master.destroy()
