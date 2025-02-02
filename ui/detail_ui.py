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
from public_class import reusable_widget
from resources import Constants
from resources.config import Config
from resources.strings import Strings
from utils import string_utils, widget_utils, hwnd_utils
from utils.logger_utils import mylogger as logger


class DetailWindow:
    def __init__(self, root, parent, root_class, wnd, sw,
                 account):
        self.root = root
        self.parent = parent
        self.root_class = root_class
        self.wnd = wnd
        self.sw = sw
        self.wnd.withdraw()
        self.account = account
        self.tooltips = {}  # 初始化 tooltip 属性
        self.last_valid_hotkey = ""  # 记录上一个有效的快捷键
        self.current_keys = set()  # 当前按下的键

        # 禁用窗口大小调整
        self.wnd.resizable(False, False)

        wnd.title(f"属性 - {self.account}")

        wnd.attributes('-toolwindow', True)

        frame = ttk.Frame(wnd, padding=Constants.FRM_PAD)
        frame.pack(**Constants.FRM_PACK)

        # 头像
        self.top_frame = ttk.Frame(frame, padding=Constants.T_FRM_PAD)
        self.top_frame.pack(**Constants.T_FRM_PACK)
        self.avatar_frame = ttk.Frame(self.top_frame, padding=Constants.L_FRM_PAD)
        self.avatar_frame.pack(**Constants.L_FRM_PACK)
        self.avatar_label = ttk.Label(self.avatar_frame)
        self.avatar_label.pack(**Constants.T_WGT_PACK)
        self.avatar_status_label = ttk.Label(self.avatar_frame, text="")
        self.avatar_status_label.pack(**Constants.B_WGT_PACK)

        # PID
        self.pid_label = ttk.Label(self.top_frame)
        self.pid_label.pack(anchor="w", **Constants.T_WGT_PACK)

        # 原始微信号
        self.origin_id_lbl = ttk.Label(frame, text=f"原id: {self.account}")
        self.origin_id_lbl.pack(anchor="w", **Constants.T_WGT_PACK)

        # 当前微信号
        self.cur_id_lbl = ttk.Label(frame)
        self.cur_id_lbl.pack(anchor="w", **Constants.T_WGT_PACK)

        # 昵称
        self.nickname_lbl = ttk.Label(frame)
        self.nickname_lbl.pack(anchor="w", **Constants.T_WGT_PACK)

        # 备注
        note, = subfunc_file.get_sw_acc_details_from_json(self.sw, self.account, note=None)
        self.note_var = tk.StringVar(value="") if note is None else tk.StringVar(value=note)
        self.note_frame = ttk.Frame(frame)
        self.note_frame.pack(anchor="w", **Constants.T_WGT_PACK)
        note_label = ttk.Label(self.note_frame, text="备注：")
        note_label.pack(side=tk.LEFT, anchor="w")
        self.note_entry = ttk.Entry(self.note_frame, textvariable=self.note_var, width=30)
        self.note_entry.pack(side=tk.LEFT)

        # 热键
        hotkey, = subfunc_file.get_sw_acc_details_from_json(self.sw, self.account, hotkey=None)
        self.hotkey_frame = ttk.Frame(frame)
        self.hotkey_frame.pack(anchor="w", **Constants.T_WGT_PACK)
        hotkey_label = ttk.Label(self.hotkey_frame, text="热键：")
        hotkey_label.pack(side=tk.LEFT, anchor="w")
        self.hotkey_entry_class = reusable_widget.HotkeyEntry4Keyboard(hotkey, self.hotkey_frame)

        # 隐藏账号
        self.hidden_frame = ttk.Frame(frame)
        self.hidden, = subfunc_file.get_sw_acc_details_from_json(sw, account, hidden=False)
        self.hidden_var = tk.BooleanVar(value=self.hidden)
        self.hidden_checkbox = tk.Checkbutton(self.hidden_frame, text="未登录时隐藏", variable=self.hidden_var)
        self.hidden_checkbox.pack(side=tk.LEFT)

        # 账号自启动
        self.auto_start_frame = ttk.Frame(frame)
        self.auto_start, = subfunc_file.get_sw_acc_details_from_json(sw, account, auto_start=False)
        self.auto_start_var = tk.BooleanVar(value=self.auto_start)
        self.auto_start_checkbox = tk.Checkbutton(
            self.auto_start_frame, text="进入软件时自启动", variable=self.auto_start_var)
        self.auto_start_checkbox.pack(side=tk.LEFT)

        # 按钮区域
        button_frame = ttk.Frame(frame, padding=Constants.B_FRM_PAD)
        ttk.Frame(button_frame).pack(side=tk.LEFT, expand=True)  # 占位
        ttk.Frame(button_frame).pack(side=tk.RIGHT, expand=True)  # 占位
        self.fetch_button = ttk.Button(button_frame, text="获取", command=self.fetch_data)
        self.fetch_button.pack(**Constants.L_WGT_PACK)
        save_button = ttk.Button(button_frame, text="保存", command=self.save_acc_settings)
        save_button.pack(**Constants.R_WGT_PACK)

        # 底部区域按从下至上的顺序pack
        button_frame.pack(**Constants.B_FRM_PACK)
        self.auto_start_frame.pack(anchor="w", **Constants.B_WGT_PACK)
        self.hidden_frame.pack(anchor="w", **Constants.B_WGT_PACK)

        ttk.Frame(frame).pack(fill=tk.BOTH, expand=True)  # 占位

        print(f"加载控件完成")

        self.load_data_label()

        wnd_width, wnd_height = Constants.DETAIL_WND_SIZE
        hwnd_utils.bring_tk_wnd_to_center(self.wnd, wnd_width, wnd_height)
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
        avatar_url, alias, nickname, pid = subfunc_file.get_sw_acc_details_from_json(
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
            logger.error(e)
            self.nickname_lbl.config(text=f"昵称: {string_utils.clean_texts(nickname)}")
        self.pid_label.config(text=f"PID: {pid}")
        if not pid:
            widget_utils.disable_button_and_add_tip(self.tooltips, self.fetch_button, "请登录后获取")
            self.pid_label.config(text=f"PID: 未登录")
            subfunc_file.update_sw_acc_details_to_json(self.sw, self.account, has_mutex=True)
        else:
            has_mutex, main_hwnd = subfunc_file.get_sw_acc_details_from_json(
                self.sw, self.account, has_mutex=True, main_hwnd=None)
            if has_mutex:
                self.pid_label.config(text=f"PID: {pid}(有互斥体)\nHWND: {main_hwnd}")
            else:
                self.pid_label.config(text=f"PID: {pid}(无互斥体)\nHWND: {main_hwnd}")
            widget_utils.enable_button_and_unbind_tip(self.tooltips, self.fetch_button)
        print(f"载入数据完成")

    def load_avatar(self, avatar_path, avatar_url):
        try:
            img = Image.open(avatar_path)
            img = img.resize(Constants.AVT_SIZE, Image.Resampling.LANCZOS)
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
        pid, = subfunc_file.get_sw_acc_details_from_json(self.sw, self.account, pid=None)
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

    def save_acc_settings(self):
        """
        保存账号设置
        :return:
        """
        new_note = self.note_var.get().strip()
        if new_note == "":
            subfunc_file.update_sw_acc_details_to_json(self.sw, self.account, note=None)
        else:
            subfunc_file.update_sw_acc_details_to_json(self.sw, self.account, note=new_note)
        hidden = self.hidden_var.get()
        subfunc_file.update_sw_acc_details_to_json(self.sw, self.account, hidden=hidden)
        auto_start = self.auto_start_var.get()
        subfunc_file.update_sw_acc_details_to_json(self.sw, self.account, auto_start=auto_start)
        hotkey = self.hotkey_entry_class.hotkey_var.get().strip()
        subfunc_file.update_sw_acc_details_to_json(self.sw, self.account, hotkey=hotkey)
        self.root_class.refresh_sw_main_frame(self.sw, message="账号设置成功")
        self.wnd.destroy()

    def set_focus_to_(self, widget_tag):
        if widget_tag == "note":
            self.note_entry.focus_set()
        elif widget_tag == "hotkey":
            self.hotkey_entry_class.hotkey_entry.focus_set()
