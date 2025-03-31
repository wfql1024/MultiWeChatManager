import base64, os, re, sys, tempfile, threading, uuid, webbrowser
import psutil, win32com, winshell
import win32com.client
import tkinter as tk
from abc import ABC
from datetime import datetime
from functools import partial
from tkinter import filedialog, scrolledtext, ttk, messagebox
from tkinter.font import Font
from typing import Dict, Union
from PIL import Image, ImageTk

from functions import func_detail, subfunc_file, func_setting, func_sw_dll, subfunc_sw, func_update
from public_class import reusable_widgets
from public_class.enums import Keywords
from public_class.reusable_widgets import SubToolWnd
from resources import Constants, Config, Strings
from utils import file_utils, sys_utils, widget_utils, sw_utils
from utils.encoding_utils import StringUtils
from utils.file_utils import JsonUtils
from utils.logger_utils import mylogger as logger, myprinter as printer, DebugUtils


class DetailWnd(SubToolWnd, ABC):
    def __init__(self, wnd, title, sw, account, tab_class):
        self.pid = None
        self.fetch_button = None
        self.auto_start_var = None
        self.hidden_var = None
        self.hotkey_entry_class = None
        self.note_entry = None
        self.note_var = None
        self.nickname_lbl = None
        self.cur_id_lbl = None
        self.pid_label = None
        self.avatar_status_label = None
        self.avatar_label = None
        self.current_keys = None
        self.last_valid_hotkey = None
        self.tooltips = None

        self.sw = sw
        self.account = account
        self.tab_class = tab_class

        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.tooltips = {}  # 初始化 tooltip 属性
        self.last_valid_hotkey = ""  # 记录上一个有效的快捷键
        self.current_keys = set()  # 当前按下的键
        self.wnd_width, self.wnd_height = Constants.DETAIL_WND_SIZE

    def load_content(self):
        wnd = self.wnd
        sw = self.sw
        account = self.account

        frame = ttk.Frame(wnd, padding=Constants.FRM_PAD)
        frame.pack(**Constants.FRM_PACK)

        # 头像
        top_frame = ttk.Frame(frame, padding=Constants.T_FRM_PAD)
        top_frame.pack(**Constants.T_FRM_PACK)
        avatar_frame = ttk.Frame(top_frame, padding=Constants.L_FRM_PAD)
        avatar_frame.pack(**Constants.L_FRM_PACK)
        self.avatar_label = ttk.Label(avatar_frame)
        self.avatar_label.pack(**Constants.T_WGT_PACK)
        self.avatar_status_label = ttk.Label(avatar_frame, text="")
        self.avatar_status_label.pack(**Constants.B_WGT_PACK)

        # PID
        self.pid_label = ttk.Label(top_frame)
        self.pid_label.pack(anchor="w", **Constants.T_WGT_PACK)

        # 原始微信号
        origin_id_lbl = ttk.Label(frame, text=f"原id: {self.account}")
        origin_id_lbl.pack(anchor="w", **Constants.T_WGT_PACK)

        # 当前微信号
        self.cur_id_lbl = ttk.Label(frame)
        self.cur_id_lbl.pack(anchor="w", **Constants.T_WGT_PACK)

        # 昵称
        self.nickname_lbl = ttk.Label(frame)
        self.nickname_lbl.pack(anchor="w", **Constants.T_WGT_PACK)

        # 备注
        note, = subfunc_file.get_sw_acc_data(self.sw, self.account, note=None)
        self.note_var = tk.StringVar(value="") if note is None else tk.StringVar(value=note)
        note_frame = ttk.Frame(frame)
        note_frame.pack(anchor="w", **Constants.T_WGT_PACK)
        note_label = ttk.Label(note_frame, text="备注：")
        note_label.pack(side=tk.LEFT, anchor="w")
        self.note_entry = ttk.Entry(note_frame, textvariable=self.note_var, width=30)
        self.note_entry.pack(side=tk.LEFT)

        # 热键
        hotkey, = subfunc_file.get_sw_acc_data(self.sw, self.account, hotkey=None)
        hotkey_frame = ttk.Frame(frame)
        hotkey_frame.pack(anchor="w", **Constants.T_WGT_PACK)
        hotkey_label = ttk.Label(hotkey_frame, text="热键：")
        hotkey_label.pack(side=tk.LEFT, anchor="w")
        self.hotkey_entry_class = reusable_widgets.HotkeyEntry4Keyboard(hotkey, hotkey_frame)

        # 隐藏账号
        hidden_frame = ttk.Frame(frame)
        hidden, = subfunc_file.get_sw_acc_data(sw, account, hidden=False)
        self.hidden_var = tk.BooleanVar(value=hidden)
        hidden_checkbox = tk.Checkbutton(hidden_frame, text="未登录时隐藏", variable=self.hidden_var)
        hidden_checkbox.pack(side=tk.LEFT)

        # 账号自启动
        auto_start_frame = ttk.Frame(frame)
        auto_start, = subfunc_file.get_sw_acc_data(sw, account, auto_start=False)
        self.auto_start_var = tk.BooleanVar(value=auto_start)
        auto_start_checkbox = tk.Checkbutton(
            auto_start_frame, text="进入软件时自启动", variable=self.auto_start_var)
        auto_start_checkbox.pack(side=tk.LEFT)

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
        auto_start_frame.pack(anchor="w", **Constants.B_WGT_PACK)
        hidden_frame.pack(anchor="w", **Constants.B_WGT_PACK)

        ttk.Frame(frame).pack(fill=tk.BOTH, expand=True)  # 占位

        print(f"加载控件完成")

        self.load_data()

    def set_wnd(self):
        # 禁用窗口大小调整
        self.wnd.resizable(False, False)

    def load_data(self):
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
        avatar_url, alias, nickname, pid = subfunc_file.get_sw_acc_data(
            self.sw,
            self.account,
            avatar_url=None,
            alias="请获取数据",
            nickname="请获取数据",
            pid=None
        )
        self.pid = pid
        self.load_avatar(avatar_path, avatar_url)
        self.cur_id_lbl.config(text=f"现id: {alias}")
        try:
            self.nickname_lbl.config(text=f"昵称: {nickname}")
        except Exception as e:
            logger.warning(e)
            self.nickname_lbl.config(text=f"昵称: {StringUtils.clean_texts(nickname)}")
        self.pid_label.config(text=f"PID: {pid}")
        if not pid:
            widget_utils.enable_widget_when_(self.fetch_button, False)
            widget_utils.set_widget_tip_when_(self.tooltips, self.fetch_button, {"请登录后获取": True})
            self.pid_label.config(text=f"PID: 未登录")
            subfunc_file.update_sw_acc_data(self.sw, self.account, has_mutex=True)
        else:
            has_mutex, main_hwnd = subfunc_file.get_sw_acc_data(
                self.sw, self.account, has_mutex=True, main_hwnd=None)
            if has_mutex:
                self.pid_label.config(text=f"PID: {pid}(有互斥体)\nHWND: {main_hwnd}")
            else:
                self.pid_label.config(text=f"PID: {pid}(无互斥体)\nHWND: {main_hwnd}")
            widget_utils.enable_widget_when_(self.fetch_button, True)
            widget_utils.set_widget_tip_when_(self.tooltips, self.fetch_button, {"请登录后获取": False})
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
        pid = self.pid
        try:
            psutil.Process(pid)
        except psutil.NoSuchProcess:
            # 用户在此过程偷偷把账号退了...
            logger.warning(f"该进程已不存在: {pid}")
            widget_utils.enable_widget_when_(self.fetch_button, False)
            widget_utils.set_widget_tip_when_(self.tooltips, self.fetch_button, {"请登录后获取": True})
            messagebox.showinfo("提示", "未检测到该账号登录")
            return

        # 线程启动获取详情
        threading.Thread(target=func_detail.fetch_acc_detail_by_pid,
                         args=(self.sw, pid, self.account, self.after_fetch)).start()
        widget_utils.enable_widget_when_(self.fetch_button, False)
        widget_utils.set_widget_tip_when_(self.tooltips, self.fetch_button, {"获取中...": True})

    def after_fetch(self):
        widget_utils.enable_widget_when_(self.fetch_button, True)
        widget_utils.set_widget_tip_when_(self.tooltips, self.fetch_button, {"获取中...": False})
        self.load_data()

    def save_acc_settings(self):
        """
        保存账号设置
        :return:
        """
        new_note = self.note_var.get().strip()
        if new_note == "":
            subfunc_file.update_sw_acc_data(self.sw, self.account, note=None)
        else:
            subfunc_file.update_sw_acc_data(self.sw, self.account, note=new_note)
        hidden = self.hidden_var.get()
        subfunc_file.update_sw_acc_data(self.sw, self.account, hidden=hidden)
        auto_start = self.auto_start_var.get()
        subfunc_file.update_sw_acc_data(self.sw, self.account, auto_start=auto_start)
        hotkey = self.hotkey_entry_class.hotkey_var.get().strip()
        subfunc_file.update_sw_acc_data(self.sw, self.account, hotkey=hotkey)
        printer.vital("账号设置成功")
        self.tab_class.refresh_frame(self.sw)
        self.wnd.destroy()

    def set_focus_to_(self, widget_tag):
        if widget_tag == "note":
            self.note_entry.focus_set()
        elif widget_tag == "hotkey":
            self.hotkey_entry_class.hotkey_entry.focus_set()


class DebugWnd(SubToolWnd, ABC):
    def __init__(self, wnd, title):
        self.text_area = None
        self.simplify_checkbox = None
        self.simplify_var = None
        self.callstack_var = None
        self.max_indent_scale = None
        self.min_indent_scale = None
        self.indent_var = None
        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.wnd_width, self.wnd_height = Constants.DEBUG_WND_SIZE

    def load_content(self):
        wnd = self.wnd

        # 创建工具栏
        toolbar = tk.Frame(wnd)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        # 刷新按钮
        refresh_button = tk.Button(toolbar, text="刷新", command=self.refresh_text)
        refresh_button.pack(side=tk.LEFT)

        # 打印日志按钮
        print_log_button = tk.Button(toolbar, text="生成日志文件", command=self.write_log_to_txt)
        print_log_button.pack(side=tk.LEFT)

        # 缩进复选框
        self.indent_var = tk.BooleanVar(value=True)
        indent_checkbox = tk.Checkbutton(toolbar, text="缩进", variable=self.indent_var,
                                         command=self.refresh_text)
        indent_checkbox.pack(side=tk.LEFT)

        # 创建Frame用于包含两个滑块
        indent_frame = tk.Frame(toolbar)
        indent_frame.pack(side=tk.LEFT)

        # 最小缩进尺
        min_indent_label = tk.Label(indent_frame, text="最小缩进:")
        min_indent_label.pack(side=tk.LEFT)
        self.min_indent_scale = tk.Scale(indent_frame, from_=0, to=20, orient=tk.HORIZONTAL,
                                         command=lambda x: self.update_indent_scales())
        self.min_indent_scale.set(0)  # 设置默认最小缩进
        self.min_indent_scale.pack(side=tk.LEFT)

        # 最大缩进尺
        max_indent_label = tk.Label(indent_frame, text="最大缩进:")
        max_indent_label.pack(side=tk.LEFT)
        self.max_indent_scale = tk.Scale(indent_frame, from_=0, to=20, orient=tk.HORIZONTAL,
                                         command=lambda x: self.update_indent_scales())
        self.max_indent_scale.set(20)  # 设置默认最大缩进
        self.max_indent_scale.pack(side=tk.LEFT)

        # 调用复选框
        self.callstack_var = tk.BooleanVar(value=True)
        callstack_checkbox = tk.Checkbutton(toolbar, text="调用栈", variable=self.callstack_var,
                                            command=self.update_simplify_checkbox)
        callstack_checkbox.pack(side=tk.LEFT)

        # 简化复选框
        self.simplify_var = tk.BooleanVar(value=True)
        self.simplify_checkbox = tk.Checkbutton(toolbar, text="简化调用栈",
                                                variable=self.simplify_var, command=self.refresh_text)
        self.simplify_checkbox.pack(side=tk.LEFT)

        # 创建带滚动条的文本框
        self.text_area = scrolledtext.ScrolledText(wnd, wrap=tk.NONE)
        self.text_area.pack(fill=tk.BOTH, expand=True)
        self.text_area.tag_configure("unimportant", foreground="grey")

        # 设置字体
        font = Font(family="JetBrains Mono", size=10)
        self.text_area.config(font=font)

        # 初始化显示日志
        self.refresh_text()

    # 更新缩进滑块逻辑
    def update_indent_scales(self):
        """缩进滑块的更新"""
        min_indent = self.min_indent_scale.get()
        max_indent = self.max_indent_scale.get()

        # 确保最小缩进小于最大缩进
        if min_indent > max_indent:
            self.min_indent_scale.set(max_indent)
            self.max_indent_scale.set(min_indent)

        # 调用refresh_text更新显示
        self.refresh_text()

    def update_simplify_checkbox(self):
        """刷新简化复选框"""
        if self.callstack_var.get():
            self.simplify_checkbox.config(state=tk.NORMAL)  # 启用
        else:
            self.simplify_checkbox.config(state=tk.DISABLED)  # 禁用
        self.refresh_text()

    def refresh_text(self):
        """刷新文本区域，根据复选框的状态更新内容显示"""
        self.text_area.config(state=tk.NORMAL)
        current_scroll_position = self.text_area.yview()  # 保存当前滚动位置
        self.text_area.delete(1.0, tk.END)

        logs = sys.stdout.get_logs()
        for log in logs:
            if len(log['output_prefix']) < self.min_indent_scale.get() or len(
                    log['output_prefix']) > self.max_indent_scale.get():
                continue
            # 调用栈前缀
            if self.indent_var.get() and self.callstack_var.get():
                stack_prefix = log['stack_prefix']
            else:
                stack_prefix = ""
            # 调用栈
            if self.callstack_var.get():
                if self.simplify_var.get() is False:
                    call_stack = log['call_stack'] + "\n"
                else:
                    origin_call_stack = log['call_stack']
                    call_stack = DebugUtils.simplify_call_stack(origin_call_stack) + "\n"
            else:
                call_stack = ""
            # 输出前缀
            if self.indent_var.get():
                output_prefix = log['output_prefix']
            else:
                output_prefix = ""
            # 输出
            if self.callstack_var.get():
                output_content = log['output_content'] + "\n"
            else:
                output_content = log['output_content'] + "\n"

            self.text_area.insert(tk.END, stack_prefix, "unimportant")
            self.text_area.insert(tk.END, call_stack, "unimportant")
            self.text_area.insert(tk.END, output_prefix, "unimportant")
            self.text_area.insert(tk.END, output_content)

        self.text_area.update_idletasks()  # 确保插入文本后所有更新完成
        self.text_area.yview_moveto(current_scroll_position[0])  # 恢复滚动条位置

        self.text_area.config(state=tk.DISABLED)

    def write_log_to_txt(self):
        # 获取桌面路径
        desktop = winshell.desktop()

        # 根据当前日期时间生成文件名
        current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"mwm_log_{current_time}.txt"
        file_path = os.path.join(desktop, file_name)

        try:
            # 获取文本框内容
            content = self.text_area.get("1.0", "end").strip()  # 获取从第一行到末尾的内容，并移除多余空白

            # 写入文件
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            print(f"日志已成功保存到：{file_path}")
        except Exception as e:
            print(f"保存日志时发生错误：{e}")


class LoadingWnd(SubToolWnd, ABC):
    def __init__(self, wnd, title):
        self.progress = None
        self.label = None

        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.wnd_width, self.wnd_height = Constants.LOADING_WND_SIZE

    def set_wnd(self):
        self.wnd.resizable(False, False)
        self.wnd.overrideredirect(True)  # 去除窗口标题栏

    def load_content(self):
        self.label = ttk.Label(self.wnd, text="正在载入，请稍等……")
        self.label.pack(pady=Constants.T_PAD_Y)
        self.progress = ttk.Progressbar(self.wnd, mode="determinate", length=Constants.LOADING_PRG_LEN)
        self.progress.pack(pady=Constants.T_PAD_Y)

        self.progress.start(15)

    def auto_close(self):
        if self.wnd.winfo_exists():
            self.progress.stop()
            self.progress['value'] = self.progress['maximum']
            self.wnd.update_idletasks()
            self.wnd.destroy()


class Direction:
    def __init__(self, initial=1):
        self.value = initial


class AboutWnd(SubToolWnd, ABC):
    def __init__(self, wnd, title, app_info):
        self.logo_img = None
        self.scroll_text_str = None
        self.scroll_direction = None
        self.scroll_tasks = None
        self.remote_cfg_data = None
        self.about_info = None
        self.app_name = None
        self.content_frame = None
        self.main_frame = None

        self.app_info = app_info

        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.wnd_width, self.wnd_height = Constants.ABOUT_WND_SIZE
        self.scroll_tasks: Dict[str, Union[list, None]] = {
            "reference": None,
            "sponsor": None,
        }
        self.scroll_direction: Dict[str, Union[Direction, None]] = {
            "reference": None,
            "sponsor": None,
        }
        self.scroll_text_str: Dict[str, Union[str, None]] = {
            "reference": None,
            "sponsor": None,
        }
        self.logo_img = []

    def set_wnd(self):
        self.wnd.resizable(False, False)

    def load_content(self):
        self.remote_cfg_data = subfunc_file.read_remote_cfg_in_rules()
        if self.remote_cfg_data is None:
            messagebox.showinfo("提示", "无法获取配置文件，请检查网络连接后重试")
            # 关闭wnd窗口
            self.wnd.destroy()
        else:
            self.display_main_content()

    def display_main_content(self):
        self.app_name = self.remote_cfg_data[Keywords.GLOBAL_SECTION]["app_name"]
        self.about_info = self.remote_cfg_data[Keywords.GLOBAL_SECTION]["about"]

        self.main_frame = ttk.Frame(self.wnd, padding=Constants.FRM_PAD)
        self.main_frame.pack(**Constants.FRM_PACK)

        # 图标框架（左框架）
        logo_frame = ttk.Frame(self.main_frame, padding=Constants.L_FRM_PAD)
        logo_frame.pack(**Constants.L_FRM_PACK)

        # 内容框架（右框架）
        self.content_frame = ttk.Frame(self.main_frame, padding=Constants.R_FRM_PAD)
        self.content_frame.pack(**Constants.R_FRM_PACK)

        # 加载并调整图标
        try:
            icon_image = Image.open(Config.PROJ_ICO_PATH)
            icon_image = icon_image.resize(Constants.LOGO_SIZE, Image.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(icon_image)
        except Exception as e:
            logger.error(f"无法加载图标图片: {e}")
            # 如果图标加载失败，仍然继续布局
            self.logo_img = ImageTk.PhotoImage(Image.new('RGB', Constants.LOGO_SIZE, color='white'))
        icon_label = ttk.Label(logo_frame, image=self.logo_img)
        icon_label.image = self.logo_img
        icon_label.pack(**Constants.T_WGT_PACK)

        # 顶部：标题和版本号框架
        title_version_frame = ttk.Frame(self.content_frame)
        title_version_frame.pack(**Constants.T_FRM_PACK)

        # 标题和版本号标签
        current_full_version = subfunc_file.get_app_current_version()
        title_version_str = f"{self.app_name} {current_full_version}"
        title_version_label = ttk.Label(
            title_version_frame,
            text=title_version_str,
            style='FirstTitle.TLabel',
        )
        title_version_label.pack(anchor='sw', **Constants.T_WGT_PACK, ipady=Constants.IPAD_Y)

        # 开发者主页
        author_label = ttk.Label(self.content_frame, text="by 吾峰起浪", style='SecondTitle.TLabel')
        author_label.pack(anchor='sw', **Constants.T_WGT_PACK)
        self.pack_grids(self.content_frame, self.about_info["author"])

        # 项目信息
        proj_label = ttk.Label(self.content_frame, text="项目信息", style='SecondTitle.TLabel')
        proj_label.pack(anchor='sw', **Constants.T_WGT_PACK)
        self.pack_grids(self.content_frame, self.about_info["project"])

        # 鸣谢
        thanks_label = ttk.Label(self.content_frame, text="鸣谢", style='SecondTitle.TLabel')
        thanks_label.pack(anchor='sw', **Constants.T_WGT_PACK)
        self.pack_grids(self.content_frame, self.about_info["thanks"])

        # 技术参考
        reference_label = ttk.Label(self.content_frame, text="技术参考", style='SecondTitle.TLabel')
        reference_label.pack(anchor='w', **Constants.T_WGT_PACK)
        reference_frame = ttk.Frame(self.content_frame)
        reference_frame.pack(**Constants.T_FRM_PACK)

        reference_list = self.about_info.get('reference', [])
        lines = []
        for item in reference_list:
            lines.append(item["title"])
            lines.append(item["link"])
            lines.append("")  # 空行
        self.scroll_text_str["reference"] = "\n".join(lines).strip()

        self.pack_scrollable_text(reference_frame, "reference", 12)

        # 赞助
        sponsor_label = ttk.Label(self.content_frame, text="赞助", style='SecondTitle.TLabel')
        sponsor_frame = ttk.Frame(self.content_frame)
        sponsor_label.pack(anchor='w', **Constants.T_WGT_PACK)
        sponsor_frame.pack(**Constants.T_FRM_PACK)

        sponsor_list = self.about_info.get('sponsor', [])
        sponsor_list_lines = []
        for idx, item in enumerate(sponsor_list):
            date = sponsor_list[idx].get('date', None)
            currency = sponsor_list[idx].get('currency', None)
            amount = sponsor_list[idx].get('amount', None)
            user = sponsor_list[idx].get('user', None)
            sponsor_list_lines.append(f"• {date}  {currency}{amount}  {user}")
        self.scroll_text_str["sponsor"] = "\n".join(sponsor_list_lines)

        self.pack_scrollable_text(sponsor_frame, "sponsor", 5)

        # 底部区域=声明+检查更新按钮
        bottom_frame = ttk.Frame(self.content_frame)
        bottom_frame.pack(**Constants.B_FRM_PACK)

        surprise_sign = Strings.SURPRISE_SIGN
        prefix = surprise_sign if self.app_info.need_update is True else ""

        # 左边：声明框架
        disclaimer_frame = ttk.Frame(bottom_frame, padding=Constants.L_FRM_PAD)
        disclaimer_frame.pack(**Constants.L_FRM_PACK)
        # 右边：更新按钮
        update_button = ttk.Button(bottom_frame, text=f"{prefix}检查更新", style='Custom.TButton',
                                   command=partial(self.check_for_updates,
                                                   current_full_version=current_full_version))
        update_button.pack(side=tk.RIGHT)

        # 免责声明
        disclaimer_label = ttk.Label(disclaimer_frame, style="RedWarning.TLabel",
                                     text="仅供学习交流，严禁用于商业用途，请于24小时内删除")
        disclaimer_label.pack(**Constants.B_WGT_PACK)

        # 版权信息标签
        copyright_label = ttk.Label(
            disclaimer_frame,
            text="Copyright © 2024 吾峰起浪. All rights reserved.",
            style="LittleText.TLabel",
        )
        copyright_label.pack(**Constants.T_WGT_PACK)

    def pack_scrollable_text(self, frame, part, height):
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text = tk.Text(frame, wrap=tk.WORD, font=("", Constants.LITTLE_FONTSIZE),
                       height=height, bg=self.wnd.cget("bg"),
                       yscrollcommand=scrollbar.set, bd=0, highlightthickness=0)

        text.insert(tk.END, '\n')
        text.insert(tk.END, self.scroll_text_str[part])
        text.insert(tk.END, '\n')

        widget_utils.add_hyperlink_events(text, self.scroll_text_str[part])
        text.config(state=tk.DISABLED)
        text.pack(side=tk.LEFT, fill=tk.X, expand=False, padx=Constants.GRID_PAD)
        scrollbar.config(command=text.yview)
        # 创建方向对象
        self.scroll_direction[part] = Direction(1)  # 初始方向为向下
        self.scroll_tasks[part] = []
        # 启动滚动任务
        widget_utils.auto_scroll_text(
            self.scroll_tasks[part], self.scroll_direction[part], text, self.root
        )
        # 鼠标进入控件时取消所有任务
        text.bind(
            "<Enter>",
            lambda event: [
                self.root.after_cancel(task) for task in self.scroll_tasks[part]
            ]
        )
        # 鼠标离开控件时继续滚动，保留当前方向
        text.bind(
            "<Leave>",
            lambda event: widget_utils.auto_scroll_text(
                self.scroll_tasks[part], self.scroll_direction[part], text, self.root
            )
        )

    def check_for_updates(self, current_full_version):
        config_data = subfunc_file.force_fetch_remote_encrypted_cfg()
        if config_data is None:
            messagebox.showinfo("提示", "无法获取配置文件，请检查网络连接后重试")
            return False
        success, result = func_update.split_vers_by_cur_from_local(current_full_version)
        if success is True:
            new_versions, old_versions = result
            if len(new_versions) != 0:
                update_log_window = tk.Toplevel(self.wnd)
                UpdateLogWnd(update_log_window, "", old_versions, new_versions)
            else:
                messagebox.showinfo("提醒", f"当前版本{current_full_version}已是最新版本。")
                return True
        else:
            messagebox.showinfo("错误", result)
            return False

    @staticmethod
    def pack_grids(frame, part_dict, max_columns=6):
        grids = ttk.Frame(frame)
        grids.pack(**Constants.T_FRM_PACK)
        for idx, info in enumerate(part_dict.values()):
            item = ttk.Label(grids, text=info.get('text', None),
                             style="Link.TLabel", cursor="hand2")
            row = idx // max_columns
            column = idx % max_columns
            item.grid(row=row, column=column, **Constants.W_GRID_PACK)

            # 获取所有链接
            urls = []
            for link in info["links"].values():
                urls.append(link)

            # 绑定点击事件
            item.bind("<Button-1>", partial(lambda event, urls2open: AboutWnd.open_urls(urls2open), urls2open=urls))

    @staticmethod
    def open_urls(urls):
        if urls is None:
            return
        url_list = list(urls)
        if len(url_list) == 0:
            return
        for url in url_list:
            webbrowser.open_new(url)

    def finally_do(self):
        for info in self.scroll_tasks.values():
            for task in info:
                try:
                    self.root.after_cancel(task)  # 取消滚动任务
                except Exception as e:
                    logger.error(f"Error cancelling task: {e}")


class RewardsWnd(SubToolWnd, ABC):
    def __init__(self, wnd, title, image_path):
        self.img = None
        self.image_path = image_path

        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        # 加载图片
        self.img = Image.open(self.image_path)
        # 设置窗口大小为图片的大小
        self.wnd_width, self.wnd_height = self.img.size

    def load_content(self):
        # 创建Frame并填充
        frame = ttk.Frame(self.wnd)
        frame.pack(fill=tk.BOTH, expand=True)
        # 调用方法在frame中显示图片
        self.show_image_in_frame(frame, self.img)

    @staticmethod
    def show_image_in_frame(frame, img):
        # 将图片转换为Tkinter格式
        tk_img = ImageTk.PhotoImage(img)

        # 在frame中创建Label用于显示图片
        label = ttk.Label(frame, image=tk_img)
        label.image = tk_img  # 防止图片被垃圾回收
        label.pack()


class UpdateLogWnd(SubToolWnd, ABC):
    def __init__(self, wnd, title, old_versions, new_versions=None):
        self.log_text = None
        self.old_versions = old_versions
        self.new_versions = new_versions

        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.wnd_width, self.wnd_height = Constants.UPDATE_LOG_WND_SIZE

    def set_wnd(self):
        self.wnd.resizable(False, False)
        self.wnd.title("版本日志" if not self.new_versions else "发现新版本")

    def load_content(self):
        new_versions = self.new_versions
        old_versions = self.old_versions

        main_frame = ttk.Frame(self.wnd, padding="5")
        main_frame.pack(fill="both", expand=True)

        # 更新日志(标题)
        log_label = ttk.Label(main_frame, text="更新日志", font=("", 11))
        log_label.pack(anchor='w', pady=(10, 0))

        print("显示更新日志")

        config_data = subfunc_file.read_remote_cfg_in_rules()
        if config_data is None:
            messagebox.showerror("错误", "无法获取远程配置文件")
            self.wnd.destroy()
            return

        global_info = config_data["global"]
        # 创建一个用于放置滚动文本框的框架
        log_frame = ttk.Frame(main_frame)
        log_frame.pack(pady=(5, 0), fill=tk.BOTH, expand=True)

        # 创建滚动条
        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 创建不可编辑且可滚动的文本框
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, font=("", 10), height=6, bg=self.wnd.cget("bg"),
                                yscrollcommand=scrollbar.set, bd=0, highlightthickness=0)

        # 需要显示新版本
        if new_versions:
            try:
                newest_version = file_utils.get_newest_full_version(new_versions)
                print(newest_version)
                curr_sys_ver_name = sys_utils.get_sys_major_version_name()
                curr_sys_newest_ver_dicts = global_info["update"][newest_version]["pkgs"][curr_sys_ver_name]
                bottom_frame = ttk.Frame(main_frame)
                bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=20)
                cancel_button = ttk.Button(bottom_frame, text="以后再说",
                                           command=lambda: self.root.destroy())
                cancel_button.pack(side=tk.RIGHT)
                download_button = ttk.Button(bottom_frame, text="下载新版",
                                             command=partial(self.show_download_window,
                                                             ver_dicts=curr_sys_newest_ver_dicts))
                download_button.pack(side=tk.RIGHT)
                # 说明
                information_label = ttk.Label(
                    bottom_frame,
                    text="发现新版本，是否下载？"
                )
                information_label.pack(side=tk.RIGHT, pady=(5, 0))

                self.log_text.insert(tk.END, "新版本：\n")
                for v in new_versions:
                    self.log_text.insert(tk.END, v + "：\n")

                    # 遍历每个分类（如"新增"、"修复"、"优化"等）
                    for category, logs in global_info["update"][v]["logs"].items():
                        self.log_text.insert(tk.END, f"#{category}：\n")
                        for log in logs:
                            self.log_text.insert(tk.END, f"-{log}\n")  # 在日志前添加适当的缩进
                        self.log_text.insert(tk.END, "\n")

                self.log_text.insert(tk.END, "\n\n旧版本：\n")
            except Exception as e:
                print(e)
                messagebox.showerror("错误", f"发生错误：{e}")

        try:
            for v in old_versions:
                self.log_text.insert(tk.END, v + "：\n")

                # 遍历每个分类（如"新增"、"修复"、"优化"等）
                for category, logs in global_info["update"][v]["logs"].items():
                    self.log_text.insert(tk.END, f"#{category}：\n")
                    for log in logs:
                        self.log_text.insert(tk.END, f"-{log}\n")  # 在日志前添加适当的缩进
                    self.log_text.insert(tk.END, "\n")

        except Exception as e:
            print(e)
            messagebox.showerror("错误", f"发生错误：{e}")

        # 设置文本框为不可编辑
        self.log_text.config(state=tk.DISABLED)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 配置滚动条
        scrollbar.config(command=self.log_text.yview)

    def show_download_window(self, ver_dicts, download_dir=None):
        def update_progress(idx, total_files, downloaded, total_length):
            try:
                percentage = (downloaded / total_length) * 100 if total_length else 0
                progress_var.set(f"下载文件 {idx + 1}/{total_files}: {percentage:.2f}% 完成")
                progress_bar['value'] = percentage
                self.root.update_idletasks()
            except Exception as e:
                print(e)

        def on_window_close():
            status["stop"] = True  # 更新状态为停止下载
            download_window.destroy()

        # 下载文件夹及下载路径的生成
        if download_dir is None:
            download_dir = tempfile.gettempdir()
        # 在路径中创建一个临时文件夹和临时文件路径
        download_path = os.path.join(tempfile.mkdtemp(dir=download_dir), f"{uuid.uuid4().hex}.zip")

        # 在下载文件夹中查找近期的文件夹
        recent_folders = file_utils.get_recent_folders_from_dir(download_dir)
        md5_list = [d.get("md5") for d in ver_dicts if "md5" in d]
        matched_file = subfunc_file.get_file_with_correct_md5(recent_folders, md5_list)

        if matched_file:
            download_path = matched_file

        status = {"stop": False}  # 定义状态字典

        # 创建窗口、设置进度条等 UI 元素
        download_window = tk.Toplevel(self.root)
        download_window.title("下载更新")
        window_width = 300
        window_height = 135
        # 计算窗口位置
        screen_width = download_window.winfo_screenwidth()
        screen_height = download_window.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        download_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        download_window.resizable(False, False)
        download_window.grab_set()

        progress_var = tk.StringVar(value="开始下载...")
        tk.Label(download_window, textvariable=progress_var).pack(pady=10)
        progress_bar = ttk.Progressbar(download_window, orient="horizontal", length=250, mode="determinate")

        # 关闭并更新按钮
        close_and_update_btn = ttk.Button(download_window, text="关闭并更新", style='Custom.TButton',
                                          command=partial(func_update.close_and_update, tmp_path=download_path))
        progress_bar.pack(pady=5)
        close_and_update_btn.pack(pady=5)
        close_and_update_btn.config(state="disabled")

        # 当用户关闭窗口时，设置`status["stop"]`为True
        download_window.protocol("WM_DELETE_WINDOW", on_window_close)  # 绑定窗口关闭事件

        if matched_file:
            print(f"找到匹配的文件: {matched_file}")
            progress_var.set(f"您近期已经完成下载！")
            progress_bar['value'] = 100
            close_and_update_btn.config(state="normal")
            self.root.update_idletasks()
        else:
            print("没有找到匹配的文件")
            # 开始下载文件（多线程）
            t = threading.Thread(target=func_update.download_files,
                                 args=(ver_dicts, download_path, update_progress,
                                       lambda: close_and_update_btn.config(state="normal"), status))
            t.start()


class StatisticWnd(SubToolWnd, ABC):
    def __init__(self, wnd, title, sw):
        self.refresh_mode_combobox = None
        self.refresh_tree = None
        self.manual_tree = None
        self.auto_tree = None
        self.auto_count_combobox = None
        self.tree_dict = None
        self.main_frame = None
        self.scrollable_canvas = None
        self.view = None

        self.sw = sw
        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.view = self.root_class.global_settings_value.view
        self.wnd_width, self.wnd_height = Constants.STATISTIC_WND_SIZE
        self.tree_dict = {
            "manual": {
                "sort": False
            },
            "auto": {
                "sort": False
            },
            "refresh": {
                "sort": False
            }
        }

    def load_content(self):
        # 创建一个可以滚动的画布，并放置一个主框架在画布上
        self.scrollable_canvas = reusable_widgets.ScrollableCanvas(self.wnd)
        self.main_frame = self.scrollable_canvas.main_frame

        self.create_manual_table()
        self.create_auto_table()
        self.create_refresh_table()

        self.display_table()

    def create_manual_table(self):
        """定义手动登录表格"""
        label = tk.Label(self.main_frame, text="手动登录", font=("Microsoft YaHei", 14, "bold"))
        label.pack(padx=(20, 5))

        columns = ("模式", "最短时间", "使用次数", "平均时间", "最长时间")
        self.manual_tree = ttk.Treeview(self.main_frame,
                                        columns=columns,
                                        show='headings', height=1)
        for col in columns:
            self.manual_tree.heading(col, text=col,
                                     command=lambda c=col: self.sort_column("manual", c))
            self.manual_tree.column(col, anchor='center' if col == "模式" else 'e', width=100)  # 设置列宽

        self.manual_tree.pack(fill=tk.X, expand=True, padx=(20, 5), pady=(0, 10))
        self.tree_dict["manual"]["tree"] = self.manual_tree

    def create_auto_table(self):
        """定义自动登录表格"""
        label = tk.Label(self.main_frame, text="自动登录", font=("Microsoft YaHei", 14, "bold"))
        label.pack(padx=(20, 5))

        description = tk.Label(self.main_frame, text="查看登录第i个账号的数据：")
        description.pack()

        self.auto_count_combobox = ttk.Combobox(self.main_frame, values=[], state="readonly")
        self.auto_count_combobox.pack()
        self.auto_count_combobox.bind("<<ComboboxSelected>>", self.on_selected_auto)

        columns = ("模式", "最短时间", "使用次数", "平均时间", "最长时间")

        self.auto_tree = ttk.Treeview(self.main_frame, columns=columns,
                                      show='headings', height=1)
        for col in columns:
            self.auto_tree.heading(col, text=col,
                                   command=lambda c=col: self.sort_column("auto", c))
            self.auto_tree.column(col, anchor='center' if col == "模式" else 'e', width=100)  # 设置列宽

        self.auto_tree.pack(fill=tk.X, expand=True, padx=(20, 5), pady=(0, 10))
        self.tree_dict["auto"]["tree"] = self.auto_tree

    def create_refresh_table(self):
        """定义刷新表格"""
        label = tk.Label(self.main_frame, text="刷新", font=("Microsoft YaHei", 14, "bold"))
        label.pack(padx=(20, 5))

        description = tk.Label(self.main_frame, text="选择视图查看：")
        description.pack()

        self.refresh_mode_combobox = ttk.Combobox(self.main_frame, values=[], state="readonly")
        self.refresh_mode_combobox.pack()
        self.refresh_mode_combobox.bind("<<ComboboxSelected>>", self.on_selected_refresh)

        columns = ("账号数", "最短时间", "使用次数", "平均时间", "最长时间")
        self.refresh_tree = ttk.Treeview(self.main_frame,
                                         columns=columns,
                                         show='headings', height=1)
        for col in columns:
            self.refresh_tree.heading(col, text=col,
                                      command=lambda c=col: self.sort_column("refresh", c))
            self.refresh_tree.column(col, anchor='center' if col == "账号数" else 'e', width=100)  # 设置列宽

        self.refresh_tree.pack(fill=tk.X, expand=True, padx=(20, 5), pady=(0, 10))
        self.refresh_tree.var = "refresh"
        self.tree_dict["refresh"]["tree"] = self.refresh_tree

    def display_table(self):
        data = JsonUtils.load_json(Config.STATISTIC_JSON_PATH)
        if self.sw not in data:
            data[self.sw] = {}
        tab_info = data.get(self.sw, {})

        # 添加手动统计数据
        manual_data = tab_info.get("manual", {}).get("_", {})
        for mode, stats in manual_data.items():
            min_time, count, avg_time, max_time = stats.split(",")
            self.manual_tree.insert("", "end",
                                    values=(mode, min_time.replace("inf", "null"),
                                            int(float(count)), avg_time, max_time))
        self.manual_tree.config(height=len(manual_data.items()) + 1)

        # 更新下拉框选项
        auto_data = tab_info.get("auto", {})
        index_values = set()  # 使用集合去重
        for mode, _ in auto_data.items():
            if mode == 'avg':
                continue
            index_values.add(mode)  # 添加索引值
        sorted_index_values = sorted(map(int, index_values))  # 将字符串转为整数后排序
        self.auto_count_combobox['values'] = ['avg'] + sorted_index_values  # 设置为排序后的列表
        # 添加自动统计数据
        if self.auto_count_combobox['values']:  # 确保下拉框有值
            self.auto_count_combobox.current(0)  # 默认选择第一个
            # self.update_auto_table_from_selection(self.auto_count_combobox.get())
            self.update_table_from_selection('auto', self.auto_count_combobox.get())

        # 更新下拉框选项
        refresh_data = tab_info.get("refresh", {})
        view_values = set()  # 使用集合去重
        for mode, _ in refresh_data.items():
            # print(f"mode={mode}")
            view_values.add(mode)  # 添加索引值
        # print(view_values)
        sorted_view_values = sorted(map(str, view_values))  # 字符串排序
        self.refresh_mode_combobox['values'] = sorted_view_values  # 设置为排序后的列表
        # 添加刷新统计数据
        if self.refresh_mode_combobox['values']:  # 确保下拉框有值
            if self.view in self.refresh_mode_combobox['values']:
                self.refresh_mode_combobox.current(sorted_view_values.index(self.view))  # 选择当前的视图
            else:
                self.refresh_mode_combobox.current(0)  # 默认选择第一个
            # self.update_refresh_table_from_selection(self.refresh_mode_combobox.get())
            self.update_table_from_selection('refresh', self.refresh_mode_combobox.get())

        for t in self.tree_dict.keys():
            self.sort_column(t, "平均时间")

    def update_table_from_selection(self, mode, selected):
        """根据下拉框的选择，更新对应的表数据"""
        data = JsonUtils.load_json(Config.STATISTIC_JSON_PATH)
        tree = self.tree_dict[mode]['tree']
        # 清空之前的数据
        for item in tree.get_children():
            tree.delete(item)
        refresh_data = data.get(self.sw, {}).get(mode, {}).get(selected, {}).items()
        try:
            for acc_count, stats in refresh_data:
                min_time, count, avg_time, max_time = stats.split(",")
                tree.insert("", "end",
                            values=(acc_count, min_time.replace("inf", "null"),
                                    int(float(count)), avg_time, max_time))
            tree.config(height=len(refresh_data) + 1)
        except Exception as e:
            logger.error(e)

    def on_selected_auto(self, event):
        """选中下拉框中的数值时"""
        selected_index = event.widget.get()  # 获取选中的index
        self.update_table_from_selection('auto', selected_index)

    def on_selected_refresh(self, event):
        """选中下拉框中的数值时"""
        selected_view = event.widget.get()  # 获取选中的index
        self.update_table_from_selection("refresh", selected_view)

    def sort_column(self, tree_type, col):
        tree = self.tree_dict[tree_type]['tree']
        items = [(tree.item(i)["values"], i) for i in tree.get_children()]
        is_ascending = self.tree_dict[tree_type]['sort']
        need_to_reverse = is_ascending
        items.sort(key=lambda x: (StringUtils.try_convert_to_float(x[0][list(tree["columns"]).index(col)])),
                   reverse=need_to_reverse)
        # 清空表格并重新插入排序后的数据
        for i in tree.get_children():
            tree.delete(i)
        for item in items:
            tree.insert("", "end", values=item[0])
        tree.configure(height=len(items) + 1)
        self.tree_dict[tree_type]['sort'] = not is_ascending  # 切换排序顺序


# TODO:修改下获取程序路径，程序版本以及程序版本文件夹的逻辑


class SettingWnd(SubToolWnd, ABC):
    def __init__(self, wnd, sw, status, after, title):
        self.origin_values = None
        self.changed = None
        self.login_size_entry = None
        self.login_size_var = None
        self.screen_size_entry = None
        self.screen_size_var = None
        self.version_entry = None
        self.version_var = None
        self.dll_path_entry = None
        self.dll_dir_var = None
        self.data_path_entry = None
        self.data_dir_var = None
        self.install_path_entry = None
        self.inst_path_var = None
        self.ver = None
        self.inst_path = None
        self.data_dir = None
        self.dll_dir = None

        self.sw = sw
        self.status = status
        self.after = after
        self.need_to_clear_acc = False

        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.wnd_width, self.wnd_height = Constants.SETTING_WND_SIZE
        self.wnd_height = None
        self.changed: Dict[str, bool] = {
            "inst_path": False,
            "data_dir": False,
            "dll_dir": False,
            "login_size": False
        }
        sw = self.sw
        self.origin_values = {
            "inst_path": subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, "inst_path"),
            "data_dir": subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, "data_dir"),
            "dll_dir": subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, "dll_dir"),
            "login_size": subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, "login_size")
        }

    def load_content(self):
        wnd = self.wnd

        # 第一行 - 安装路径
        install_label = tk.Label(wnd, text="程序路径：")
        install_label.grid(row=0, column=0, **Constants.W_GRID_PACK)

        self.inst_path_var = tk.StringVar()
        self.install_path_entry = tk.Entry(wnd, textvariable=self.inst_path_var, state='readonly', width=70)
        self.install_path_entry.grid(row=0, column=1, **Constants.WE_GRID_PACK)

        install_get_button = ttk.Button(wnd, text="获取",
                                        command=partial(self.load_or_get_sw_inst_path, self.sw, True))
        install_get_button.grid(row=0, column=2, **Constants.WE_GRID_PACK)

        install_choose_button = ttk.Button(wnd, text="选择路径",
                                           command=partial(self.choose_sw_inst_path, self.sw))
        install_choose_button.grid(row=0, column=3, **Constants.WE_GRID_PACK)

        # 第二行 - 数据存储路径
        data_label = tk.Label(wnd, text="存储路径：")
        data_label.grid(row=1, column=0, **Constants.W_GRID_PACK)

        self.data_dir_var = tk.StringVar()
        self.data_path_entry = tk.Entry(wnd, textvariable=self.data_dir_var, state='readonly', width=70)
        self.data_path_entry.grid(row=1, column=1, **Constants.WE_GRID_PACK)

        data_get_button = ttk.Button(wnd, text="获取",
                                     command=partial(self.load_or_get_sw_data_dir, self.sw, True))
        data_get_button.grid(row=1, column=2, **Constants.WE_GRID_PACK)

        data_choose_button = ttk.Button(wnd, text="选择路径",
                                        command=partial(self.choose_sw_data_dir, self.sw))
        data_choose_button.grid(row=1, column=3, **Constants.WE_GRID_PACK)

        # 新增第三行 - dll路径
        dll_label = tk.Label(wnd, text="DLL所在路径：")
        dll_label.grid(row=2, column=0, **Constants.W_GRID_PACK)

        self.dll_dir_var = tk.StringVar()
        self.dll_path_entry = tk.Entry(wnd, textvariable=self.dll_dir_var, state='readonly', width=70)
        self.dll_path_entry.grid(row=2, column=1, **Constants.WE_GRID_PACK)

        dll_get_button = ttk.Button(wnd, text="获取",
                                    command=partial(self.load_or_get_sw_dll_dir, self.sw, True))
        dll_get_button.grid(row=2, column=2, **Constants.WE_GRID_PACK)

        dll_choose_button = ttk.Button(wnd, text="选择路径",
                                       command=partial(self.choose_sw_dll_dir, self.sw))
        dll_choose_button.grid(row=2, column=3, **Constants.WE_GRID_PACK)

        # 新增第四行 - 当前版本
        version_label = tk.Label(wnd, text="应用版本：")
        version_label.grid(row=3, column=0, **Constants.W_GRID_PACK)

        self.version_var = tk.StringVar()
        self.version_entry = tk.Entry(wnd, textvariable=self.version_var, state='readonly', width=70)
        self.version_entry.grid(row=3, column=1, **Constants.WE_GRID_PACK)

        ver_get_button = ttk.Button(wnd, text="获取",
                                    command=partial(self.get_cur_sw_ver, self.sw))
        ver_get_button.grid(row=3, column=2, **Constants.WE_GRID_PACK)

        # 新增第五行 - 屏幕大小
        screen_size_label = tk.Label(wnd, text="屏幕大小：")
        screen_size_label.grid(row=4, column=0, **Constants.W_GRID_PACK)

        self.screen_size_var = tk.StringVar()
        self.screen_size_entry = tk.Entry(wnd, textvariable=self.screen_size_var, state='readonly', width=70)
        self.screen_size_entry.grid(row=4, column=1, **Constants.WE_GRID_PACK)

        screen_size_get_button = ttk.Button(wnd, text="获取", command=self.get_screen_size)
        screen_size_get_button.grid(row=4, column=2, **Constants.WE_GRID_PACK)

        # 新增第六行 - 登录窗口大小
        login_size_label = tk.Label(wnd, text="登录尺寸：")
        login_size_label.grid(row=5, column=0, **Constants.W_GRID_PACK)

        self.login_size_var = tk.StringVar()
        self.login_size_entry = tk.Entry(wnd, textvariable=self.login_size_var, state='readonly', width=70)
        self.login_size_entry.grid(row=5, column=1, **Constants.WE_GRID_PACK)

        login_size_get_button = ttk.Button(wnd, text="获取",
                                           command=partial(self.to_get_login_size, self.status))
        login_size_get_button.grid(row=5, column=2, **Constants.WE_GRID_PACK)

        # 修改确定按钮，从第4行到第6行
        ok_button = ttk.Button(wnd, text="确定", command=self.on_ok)
        ok_button.grid(row=3, column=3, rowspan=3, **Constants.NEWS_GRID_PACK)

        # 配置列的权重，使得中间的 Entry 可以自动扩展
        wnd.grid_columnconfigure(1, weight=1)

        # 初始加载已经配置的，或是没有配置的话自动获取
        self.load_or_get_sw_inst_path(self.sw, False)
        self.load_or_get_sw_data_dir(self.sw, False)
        self.load_or_get_sw_dll_dir(self.sw, False)
        self.get_cur_sw_ver(self.sw, False)
        self.get_screen_size()
        login_size = subfunc_file.fetch_sw_setting_or_set_default_or_none(self.sw, 'login_size')
        self.login_size_var.set(login_size)

    def check_bools(self):
        # 需要检验是否更改的属性
        keys_to_check = ["data_dir"]
        self.need_to_clear_acc = any(self.changed[key] for key in keys_to_check)

    def on_ok(self):
        self.check_bools()
        if self.validate_paths():
            # 检查是否需要清空账号信息
            if self.need_to_clear_acc:
                subfunc_file.clear_some_acc_data(self.sw)
            self.after()
            self.wnd.destroy()

    def finally_do(self):
        self.check_bools()
        if self.need_to_clear_acc:
            subfunc_file.clear_some_acc_data(self.sw)
        self.after()

    def validate_paths(self):
        self.inst_path = self.inst_path_var.get()
        self.data_dir = self.data_dir_var.get()
        self.dll_dir = self.dll_dir_var.get()

        if "获取失败" in self.inst_path or "获取失败" in self.data_dir or "获取失败" in self.dll_dir:
            messagebox.showerror("错误", "请确保所有路径都已正确设置")
            return False
        elif not bool(re.match(r'^\d+\*\d+$', self.login_size_var.get())):
            messagebox.showerror("错误", f"请确保填入的尺寸符合\"整数*整数\"的形式")
            return False
        return True

    def load_or_get_sw_inst_path(self, sw, click=False):
        """获取路径，若成功会进行保存"""
        path = func_setting.get_sw_install_path(sw, click)  # 此函数会保存路径
        if path:
            self.inst_path_var.set(path.replace('\\', '/'))
            self.inst_path = path
            if self.inst_path != self.origin_values["inst_path"]:
                self.changed["inst_path"] = True
        else:
            self.inst_path_var.set("获取失败，请登录后获取或手动选择路径")

    def choose_sw_inst_path(self, sw):
        """选择路径，若检验成功会进行保存"""
        while True:
            path = filedialog.askopenfilename(filetypes=[("Executable files", "*.exe"), ("All files", "*.*")])
            if not path:  # 用户取消选择
                return
            path = path.replace('\\', '/')
            if sw_utils.is_valid_sw_install_path(sw, path):
                self.inst_path_var.set(path)
                self.inst_path = path
                subfunc_file.save_sw_setting(self.sw, 'inst_path', self.inst_path)
                if self.inst_path != self.origin_values["inst_path"]:
                    self.changed["inst_path"] = True
                break
            else:
                messagebox.showerror("错误", "请选择可执行文件！")

    def load_or_get_sw_data_dir(self, sw, click=False):
        """获取路径，若成功会进行保存"""
        path = func_setting.get_sw_data_dir(sw, click)  # 此函数会保存路径
        if path:
            self.data_dir_var.set(path.replace('\\', '/'))
            self.data_dir = path
            if self.data_dir != self.origin_values["data_dir"]:
                self.changed["data_dir"] = True
        else:
            self.data_dir_var.set("获取失败，请手动选择存储文件夹（可在平台设置中查看）")

    def choose_sw_data_dir(self, sw):
        """选择路径，若检验成功会进行保存"""
        while True:
            try:
                # 尝试使用 `filedialog.askdirectory` 方法
                path = filedialog.askdirectory()
                if not path:  # 用户取消选择
                    return
            except Exception as e:
                logger.error(f"filedialog.askdirectory 失败，尝试使用 win32com.client: {e}")
                try:
                    # 异常处理部分，使用 `win32com.client`
                    shell = win32com.client.Dispatch("Shell.Application")
                    folder = shell.BrowseForFolder(0, "Select Folder", 0, 0)
                    if not folder:  # 用户取消选择
                        return
                    path = folder.Self.Path.replace('\\', '/')
                except Exception as e:
                    logger.error(f"win32com.client 也失败了: {e}")
                    return
            if sw_utils.is_valid_sw_data_dir(sw, path):
                self.data_dir_var.set(path)
                self.data_dir = path
                subfunc_file.save_sw_setting(self.sw, 'data_dir', self.data_dir)
                if self.data_dir != self.origin_values["data_dir"]:
                    self.changed["data_dir"] = True
                break
            else:
                messagebox.showerror("错误", "该路径不是有效的存储路径，可以在平台设置中查看存储路径")

    def load_or_get_sw_dll_dir(self, sw, click=False):
        """获取路径，若成功会进行保存"""
        path = func_setting.get_sw_dll_dir(sw, click)  # 此函数会保存路径
        if path:
            self.dll_dir_var.set(path.replace('\\', '/'))
            self.dll_dir = path
            if self.dll_dir != self.origin_values["dll_dir"]:
                self.changed["dll_dir"] = True
        else:
            self.dll_dir_var.set("获取失败，请手动选择安装目录下最新版本号文件夹")

    def choose_sw_dll_dir(self, sw):
        """选择路径，若检验成功会进行保存"""
        while True:
            try:
                # 尝试使用 `filedialog.askdirectory` 方法
                path = filedialog.askdirectory()
                if not path:  # 用户取消选择
                    return
            except Exception as e:
                print(f"filedialog.askdirectory 失败，尝试使用 win32com.client: {e}")
                try:
                    # 异常处理部分，使用 `win32com.client`
                    shell = win32com.client.Dispatch("Shell.Application")
                    folder = shell.BrowseForFolder(0, "Select Folder", 0, 0)
                    if not folder:  # 用户取消选择
                        return
                    path = folder.Self.Path.replace('\\', '/')
                except Exception as e:
                    print(f"win32com.client 也失败了: {e}")
                    return
            if sw_utils.is_valid_sw_dll_dir(sw, path):
                self.dll_dir_var.set(path)
                self.dll_dir = path
                subfunc_file.save_sw_setting(self.sw, 'dll_dir', self.dll_dir)
                if self.dll_dir != self.origin_values["dll_dir"]:
                    self.changed["dll_dir"] = True
                break
            else:
                messagebox.showerror("错误", "请选择包含dll文件的版本号最新的文件夹")

    def get_cur_sw_ver(self, sw, click):
        print("获取版本号")
        _, version = func_setting.get_sw_inst_path_and_ver(sw, click)
        if version is not None:
            self.version_var.set(version)
            self.ver = version

    def get_screen_size(self):
        # 获取屏幕和登录窗口尺寸
        screen_width = self.wnd.winfo_screenwidth()
        screen_height = self.wnd.winfo_screenheight()
        self.screen_size_var.set(f"{screen_width}*{screen_height}")
        subfunc_file.save_global_setting('screen_size', f"{screen_width}*{screen_height}")

    def to_get_login_size(self, status):
        if status is None:
            status, _, _ = func_sw_dll.check_dll(self.sw, "multiple", self.dll_dir)
        result = subfunc_sw.get_login_size(self.sw, status)
        if result:
            login_width, login_height = result
            if 0.734 < login_width / login_height < 0.740:
                subfunc_file.save_sw_setting(self.sw, 'login_size', f"{login_width}*{login_height}")
                self.login_size_var.set(f"{login_width}*{login_height}")
            else:
                self.login_size_var.set(f"350*475")
