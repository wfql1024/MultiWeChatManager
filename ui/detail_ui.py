# detail_ui.py
import base64
import os
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

import psutil
from PIL import Image, ImageTk

from functions import func_detail, subfunc_file
from resources import Constants
from resources.config import Config
from resources.strings import Strings
from utils import string_utils, widget_utils, hwnd_utils


class DetailWindow:
    def __init__(self, root, parent, wnd, sw,
                 account, update_callback):
        self.root = root
        self.parent = parent
        self.wnd = wnd
        self.sw = sw
        self.wnd.withdraw()
        self.account = account
        self.update_callback = update_callback
        self.tooltips = {}  # 初始化 tooltip 属性

        wnd.title(f"属性 - {self.account}")

        wnd.attributes('-toolwindow', True)

        frame = ttk.Frame(wnd, padding=Constants.NOR_FRM_PAD)
        frame.pack(fill=tk.BOTH, expand=True)

        # 头像
        self.top_frame = ttk.Frame(frame)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)
        self.avatar_frame = ttk.Frame(self.top_frame)
        self.avatar_frame.pack(side=tk.LEFT, pady=10, fill=tk.X)
        self.avatar_label = ttk.Label(self.avatar_frame)
        self.avatar_label.pack(side=tk.TOP)
        self.avatar_status_label = ttk.Label(self.avatar_frame, text="")
        self.avatar_status_label.pack(side=tk.BOTTOM)

        # PID
        self.pid_label = ttk.Label(self.top_frame, text="PID: ")
        self.pid_label.pack(side=tk.LEFT, padx=5, pady=10, anchor="w")

        # 原始微信号
        self.origin_id_lbl = ttk.Label(frame, text=f"原id: {self.account}")
        self.origin_id_lbl.pack(side=tk.TOP, pady=8, anchor="w")

        # 当前微信号
        self.cur_id_lbl = ttk.Label(frame, text="现id: ")
        self.cur_id_lbl.pack(side=tk.TOP, pady=8, anchor="w")

        # 昵称
        self.nickname_lbl = ttk.Label(frame, text="昵称: ")
        self.nickname_lbl.pack(side=tk.TOP, pady=8, anchor="w")

        # 备注
        self.note_frame = ttk.Frame(frame)
        self.note_frame.pack(side=tk.TOP, pady=8, fill=tk.X)

        note_label = ttk.Label(self.note_frame, text="备注：")
        note_label.pack(side=tk.LEFT, anchor="w")

        note, = subfunc_file.get_acc_details_from_json_by_tab(self.sw, self.account, note=None)
        self.note_var = tk.StringVar(value="") if note is None else tk.StringVar(value=note)
        self.note_entry = ttk.Entry(self.note_frame, textvariable=self.note_var, width=25)
        self.note_entry.pack(side=tk.LEFT, pady=8, fill=tk.X)

        # 按钮区域
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Frame(button_frame).pack(side=tk.LEFT, expand=True)
        ttk.Frame(button_frame).pack(side=tk.RIGHT, expand=True)

        self.fetch_button = ttk.Button(button_frame, text="获取", command=self.fetch_data)
        self.fetch_button.pack(side=tk.LEFT, padx=8)
        save_button = ttk.Button(button_frame, text="保存", command=self.save_note)
        save_button.pack(side=tk.LEFT, padx=8)


        ttk.Frame(frame).pack(fill=tk.BOTH, expand=True)

        print(f"加载控件完成")

        self.load_data_label()

        wnd_width, wnd_height = Constants.DETAIL_WND_SIZE
        hwnd_utils.bring_wnd_to_center(self.wnd, wnd_width, wnd_height)
        self.wnd.deiconify()
        wnd.grab_set()

    def load_data_label(self):
        print(f"加载数据...")

        # 构建头像文件路径
        avatar_path = os.path.join(Config.PROJ_USER_PATH, self.sw, f"{self.account}", f"{self.account}.jpg")
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
        avatar_url, alias, nickname, pid = subfunc_file.get_acc_details_from_json_by_tab(
            self.sw,
            self.account,
            avatar_url=None,
            alias="请获取数据",
            nickname="请获取数据",
            pid=None
        )
        self.load_avatar(avatar_path, avatar_url)
        self.cur_id_lbl.config(text=f"现id: {alias}")
        try:
            self.nickname_lbl.config(text=f"昵称: {nickname}")
        except Exception as e:
            print(e)
            self.nickname_lbl.config(text=f"昵称: {string_utils.clean_display_name(nickname)}")
        self.pid_label.config(text=f"PID: {pid}")
        if not pid:
            widget_utils.disable_button_and_add_tip(self.tooltips, self.fetch_button, "请登录后获取")
            self.pid_label.config(text=f"PID: 未登录")
            subfunc_file.update_acc_details_to_json_by_tab(self.sw, self.account, has_mutex=True)
        else:
            has_mutex, = subfunc_file.get_acc_details_from_json_by_tab(self.sw, self.account, has_mutex=True)
            if has_mutex:
                self.pid_label.config(text=f"PID: {pid}\n(有互斥体)")
            else:
                self.pid_label.config(text=f"PID: {pid}\n(无互斥体)")
            widget_utils.enable_button_and_unbind_tip(self.tooltips, self.fetch_button)
        print(f"载入数据完成")

    def load_avatar(self, avatar_path, avatar_url):
        try:
            img = Image.open(avatar_path)
            img = img.resize(Constants.DETAIL_AVT_LBL_SIZE, Image.Resampling.LANCZOS)
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
        pid, = subfunc_file.get_acc_details_from_json_by_tab(self.sw, self.account, pid=None)
        if not pid:
            widget_utils.disable_button_and_add_tip(self.tooltips, self.fetch_button, "请登录后获取")
            messagebox.showinfo("提示", "未检测到该账号登录")
            return
        try:
            psutil.Process(pid)
        except psutil.NoSuchProcess:
            print(f"No process found with PID: {pid}")
            widget_utils.disable_button_and_add_tip(self.tooltips, self.fetch_button, "请登录后获取")
            messagebox.showinfo("提示", "未检测到该账号登录")
            return

        # 线程启动获取详情
        threading.Thread(target=func_detail.fetch_acc_detail_by_pid,
                         args=(self.sw, pid, self.account, self.after_fetch)).start()
        widget_utils.disable_button_and_add_tip(self.tooltips, self.fetch_button, text="获取中...")

    def after_fetch(self):
        widget_utils.enable_button_and_unbind_tip(self.tooltips, self.fetch_button)
        self.load_data_label()

    def save_note(self):
        new_note = self.note_var.get().strip()
        if new_note == "":
            subfunc_file.update_acc_details_to_json_by_tab(self.sw, self.account, note=None)
        else:
            subfunc_file.update_acc_details_to_json_by_tab(self.sw, self.account, note=new_note)
        self.update_callback()
        self.wnd.destroy()
