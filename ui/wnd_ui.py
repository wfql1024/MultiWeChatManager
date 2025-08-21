import os
import re
import sys
import tempfile
import threading
import tkinter as tk
import uuid
import webbrowser
from abc import ABC
from datetime import datetime
from functools import partial
from tkinter import filedialog, scrolledtext, ttk, messagebox
from tkinter.font import Font
from typing import Dict, Union

import win32com
import win32com.client
import winshell
from PIL import Image, ImageTk

from functions import subfunc_file
from functions.acc_func import AccInfoFunc, AccOperator
from functions.app_func import AppFunc
from functions.sw_func import SwOperator, SwInfoFunc, SwInfoUtils
from functions.wnd_func import DetailWndFunc, UpdateLogWndFunc
from components.custom_widgets import CustomBtn, CustomCornerBtn
from public.enums import LocalCfg, RemoteCfg, SwStates
from public.global_members import GlobalMembers
from components.custom_widgets import DefaultEntry
from components.widget_wrappers import SubToolWndUI, HotkeyEntry4KeyboardW, ScrollableCanvasW
from public import Config, Strings
from utils import file_utils, sys_utils, widget_utils
from utils.encoding_utils import StringUtils
from utils.file_utils import JsonUtils
from utils.logger_utils import mylogger as logger, myprinter as printer, DebugUtils
from utils.sys_utils import Tk2Sys
from utils.widget_utils import UnlimitedClickHandler


class WndCreator:

    @staticmethod
    def open_feedback():
        feedback_wnd = tk.Toplevel(GlobalMembers.root_class.root)
        FeedBackWndUI(feedback_wnd, "反馈渠道")

    @staticmethod
    def open_sw_settings(sw):
        """打开设置窗口"""
        settings_window = tk.Toplevel(GlobalMembers.root_class.root)
        SettingWndUI(settings_window, sw, f"{sw}设置")

    @staticmethod
    def open_update_log():
        """打开版本日志窗口"""
        root_class = GlobalMembers.root_class
        success, result = AppFunc.split_vers_by_cur_from_local(root_class.app_info.curr_full_ver)
        if success is True:
            new_versions, old_versions = result
            update_log_window = tk.Toplevel(root_class.root)
            UpdateLogWndUI(update_log_window, "", old_versions)
        else:
            messagebox.showerror("错误", result)

    @staticmethod
    def open_debug_window():
        """打开调试窗口，显示所有输出日志"""
        debug_window = tk.Toplevel(GlobalMembers.root_class.root)
        DebugWndUI(debug_window, "调试窗口")

    @staticmethod
    def open_acc_detail(item, tab_class, widget_to_focus=None, event=None):
        """打开详情窗口"""
        if event is None:
            pass
        sw, acc = item.split("/")
        detail_window = tk.Toplevel(GlobalMembers.root_class.root)
        detail_ui = DetailUI(detail_window, f"属性 - {acc}", sw, acc, tab_class)
        detail_ui.set_focus_to_(widget_to_focus)

    @staticmethod
    def open_statistic(sw):
        """打开统计窗口"""
        statistic_window = tk.Toplevel(GlobalMembers.root_class.root)
        StatisticWndUI(statistic_window, f"{sw}统计数据", sw)

    @staticmethod
    def open_global_setting_wnd():
        """打开设置窗口"""
        global_setting_wnd = tk.Toplevel(GlobalMembers.root_class.root)
        GlobalSettingWndUI(global_setting_wnd, "全局设置")

    @staticmethod
    def open_rewards():
        """打开赞赏窗口"""
        rewards_window = tk.Toplevel(GlobalMembers.root_class.root)
        RewardsWndUI(rewards_window, "我来赏你！")

    @staticmethod
    def open_about(app_info):
        """打开关于窗口"""
        about_wnd = tk.Toplevel(GlobalMembers.root_class.root)
        AboutWndUI(about_wnd, "关于", app_info)


class DetailUI(SubToolWndUI, ABC):
    def __init__(self, wnd, title, sw, account, tab_class):
        self.disable_avatar_var = None
        self.mutex_label = None
        self.hwnd_label = None
        self.login_status_frame = None
        self.hotkey_entry = None
        self.hotkey_var = None
        self.nickname_var = None
        self.cur_id_var = None
        self.origin_id_var = None
        self.pid = None
        self.fetch_button = None
        self.auto_start_var = None
        self.hidden_var = None
        self.note_entry = None
        self.note_var = None
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

    def load_ui(self):
        sw = self.sw
        account = self.account

        frame = ttk.Frame(self.wnd_frame, padding=Config.FRM_PAD)
        frame.pack(**Config.FRM_PACK)

        # 使用网格布局
        basic_info_grid = ttk.Frame(frame)
        basic_info_grid.pack()

        # 头像
        avatar_frame = ttk.Frame(basic_info_grid)
        avatar_frame.grid(row=0, column=0, **Config.W_GRID_PACK)
        avatar_label = ttk.Label(avatar_frame)
        avatar_label.pack(**Config.T_WGT_PACK)
        avatar_operate_frame = ttk.Frame(avatar_frame)
        avatar_operate_frame.pack(**Config.B_WGT_PACK)
        # 左右的占位符
        ttk.Frame(avatar_operate_frame).pack(side="left", expand=True, fill="both")
        ttk.Frame(avatar_operate_frame).pack(side="right", expand=True, fill="both")
        # avatar_status_label = ttk.Label(avatar_frame, text="")
        # avatar_status_label.pack(**Constants.B_WGT_PACK)

        # 登录状态=pid+hwnd
        customized_btn_pad = int(Config.CUS_BTN_PAD_X * 0.4)
        customized_btn_ipad = int(Config.CUS_BTN_PAD_Y * 0.8)

        def _create_btn_in_(frame_of_btn, text):
            btn = CustomCornerBtn(frame_of_btn, text=text, i_padx=customized_btn_ipad * 2.5, i_pady=customized_btn_ipad)
            return btn

        def _create_square_btn_in(frame_of_btn, text):
            btn = CustomCornerBtn(frame_of_btn, text=text, i_pady=customized_btn_ipad)
            return btn

        def _pack_btn(btn):
            btn.pack(side="left", padx=customized_btn_pad, pady=customized_btn_pad)

        def _set_negative_style(btn):
            btn.set_major_colors("#FF0000")

        change_avatar_btn = _create_btn_in_(avatar_operate_frame, "修改")
        change_avatar_btn.pack(side="left", padx=customized_btn_pad, pady=customized_btn_pad)
        (change_avatar_btn.set_bind_map(
            **{"1": lambda: self.do_and_update_ui(partial(AccInfoFunc.manual_choose_avatar_for_acc, sw, account))})
         .apply_bind(self.root))
        delete_avatar_btn = _create_square_btn_in(avatar_operate_frame, "×")
        delete_avatar_btn.pack(side="left", padx=customized_btn_pad, pady=customized_btn_pad)
        (delete_avatar_btn.set_bind_map(
            **{"1": lambda: self.do_and_update_ui(partial(AccInfoFunc.delete_avatar_for_acc, sw, account))})
         .apply_bind(self.root))

        login_status_frame = ttk.Frame(basic_info_grid)
        login_status_frame.grid(row=0, column=1, **Config.W_GRID_PACK)
        # pid
        pid_frame = ttk.Frame(login_status_frame)
        pid_frame.pack(side="top", anchor="w")
        pid_label = ttk.Label(pid_frame)
        pid_label.pack(side="left")
        kill_pid_btn = _create_square_btn_in(pid_frame, "×")
        (kill_pid_btn
         .set_bind_map(
            **{"1": lambda: self.do_and_update_ui(partial(AccOperator.quit_selected_accounts, sw, [account]))})
         .apply_bind(self.root))
        _pack_btn(kill_pid_btn)
        re_login_btn = _create_btn_in_(pid_frame, "重登")
        re_login_btn.set_bind_map(
            **{"1": partial(AccOperator.start_auto_login_accounts_thread, {sw: [account]})}).apply_bind(self.root)
        re_login_btn.set_bind_map(
            **{"1": self.wnd.destroy}).apply_bind(self.root)
        _pack_btn(re_login_btn)
        # mutex
        mutex_frame = ttk.Frame(login_status_frame)
        mutex_frame.pack(side="top", anchor="w")
        mutex_label = ttk.Label(mutex_frame)
        mutex_label.pack(side="left")
        kill_mutex_btn = _create_square_btn_in(mutex_frame, "×")
        (kill_mutex_btn.set_bind_map(
            **{"1": lambda: self.do_and_update_ui(partial(AccOperator.kill_mutex_of_pid, sw, account))})
         .apply_bind(self.root))
        _pack_btn(kill_mutex_btn)
        # hwnd
        hwnd_frame = ttk.Frame(login_status_frame)
        hwnd_frame.pack(side="top", anchor="w")
        hwnd_label = ttk.Label(hwnd_frame)
        hwnd_label.pack(side="left")
        unlink_hwnd_btn = _create_square_btn_in(hwnd_frame, "×")
        (unlink_hwnd_btn.set_bind_map(
            **{"1": lambda: self.do_and_update_ui(partial(AccInfoFunc.unlink_hwnd_of_account, sw, account))})
         .apply_bind(self.root))
        _pack_btn(unlink_hwnd_btn)
        relink_hwnd_btn = _create_btn_in_(hwnd_frame, "获取")
        (relink_hwnd_btn.set_bind_map(
            **{"1": lambda: self.do_and_update_ui(partial(AccInfoFunc.relink_hwnd_of_account, sw, account))})
         .apply_bind(self.root))
        _pack_btn(relink_hwnd_btn)
        manual_link_hwnd_btn = _create_btn_in_(hwnd_frame, "手绑")
        (manual_link_hwnd_btn.set_bind_map(
            **{"1": lambda: self.do_and_update_ui(partial(AccInfoFunc.manual_link_hwnd_of_account, sw, account))})
         .apply_bind(self.root))
        _pack_btn(manual_link_hwnd_btn)
        hidden_hwnd_btn = _create_btn_in_(hwnd_frame, "隐藏")
        _pack_btn(hidden_hwnd_btn)
        hidden_hwnd_btn.set_state(CustomBtn.State.DISABLED)
        # 将隐藏按钮设为负样式
        for negative_btn in [delete_avatar_btn, kill_pid_btn, kill_mutex_btn, unlink_hwnd_btn]:
            _set_negative_style(negative_btn)

        # 原始微信号
        _, _, origin_id_var = DetailUI._create_label_entry_grid(
            basic_info_grid, "账号标识", f"{account}", readonly=True)
        # 当前微信号
        _, _, cur_id_var = DetailUI._create_label_entry_grid(
            basic_info_grid, "平台账号", "", readonly=True)
        # 昵称
        _, _, nickname_var = DetailUI._create_label_entry_grid(
            basic_info_grid, "昵称", "", readonly=True)
        # 备注
        note, = subfunc_file.get_sw_acc_data(sw, account, note=None)
        _, note_entry, note_var = DetailUI._create_label_entry_grid(
            basic_info_grid, "备注", "" if note is None else note)
        # 热键
        hotkey, = subfunc_file.get_sw_acc_data(sw, account, hotkey=None)
        _, hotkey_entry, hotkey_var = DetailUI._create_label_entry_grid(
            basic_info_grid, "热键", "" if hotkey is None else hotkey)
        HotkeyEntry4KeyboardW(hotkey_entry, hotkey_var)
        # 复选框区域
        current_row = max([widget.grid_info().get('row', -1) for widget in basic_info_grid.grid_slaves()],
                          default=-1) + 1
        ckb_frm = ttk.Frame(basic_info_grid)
        ckb_frm.grid(row=current_row, column=0, columnspan=2, **Config.W_GRID_PACK)
        # -隐藏账号
        hidden, = subfunc_file.get_sw_acc_data(sw, account, hidden=False)
        hidden_var = tk.BooleanVar(value=hidden)
        hidden_checkbox = tk.Checkbutton(ckb_frm, text="未登录时隐藏", variable=hidden_var)
        hidden_checkbox.pack(side="left")
        # -账号自启动
        auto_start, = subfunc_file.get_sw_acc_data(sw, account, auto_start=False)
        auto_start_var = tk.BooleanVar(value=auto_start)
        auto_start_checkbox = tk.Checkbutton(
            ckb_frm, text="进入软件时自启动", variable=auto_start_var)
        auto_start_checkbox.pack(side="left")
        # -头像禁用
        disable_avatar, = subfunc_file.get_sw_acc_data(sw, account, disable_avatar=False)
        disable_avatar_var = tk.BooleanVar(value=disable_avatar)
        disable_avatar_checkbox = tk.Checkbutton(
            ckb_frm, text="禁用头像", variable=disable_avatar_var)
        disable_avatar_checkbox.pack(side="left")
        # 按钮区域
        button_frame = ttk.Frame(frame, padding=Config.B_FRM_PAD)
        save_button = ttk.Button(button_frame, text="保存", command=self._save_acc_settings)
        save_button.pack(**Config.R_WGT_PACK)
        self.fetch_button = ttk.Button(button_frame, text="获取", command=self._fetch_newest_data)
        self.fetch_button.pack(**Config.R_WGT_PACK)

        # 底部区域按从下至上的顺序pack
        button_frame.pack(**Config.B_FRM_PACK)

        ttk.Frame(frame).pack(fill="both", expand=True)  # 占位

        print(f"加载控件完成")

        self.avatar_label = avatar_label
        self.pid_label = pid_label
        self.mutex_label = mutex_label
        self.hwnd_label = hwnd_label
        self.origin_id_var = origin_id_var
        self.cur_id_var = cur_id_var
        self.nickname_var = nickname_var
        self.note_entry = note_entry
        self.note_var = note_var
        self.hotkey_entry = hotkey_entry
        self.hotkey_var = hotkey_var
        self.hidden_var = hidden_var
        self.disable_avatar_var = disable_avatar_var
        self.auto_start_var = auto_start_var

    def update_content(self):
        # 更新数据
        self._update_data_to_ui()
        widget_utils.enable_widget_when_(self.fetch_button, self.pid is not None)
        widget_utils.set_widget_tip_when_(self.tooltips, self.fetch_button,
                                          {"请登录后获取": self.pid is None})

    def set_wnd(self):
        # 禁用窗口大小调整
        self.wnd.resizable(False, False)

    def _update_data_to_ui(self):
        # 将实例变量存储为局部变量
        sw = self.sw
        account = self.account

        printer.vital(f"加载账号详情...")

        # 获取信息
        printer.print_vn(f"加载对应头像...")
        # 获取其余信息
        has_mutex, main_hwnd = subfunc_file.get_sw_acc_data(
            sw, account, has_mutex=True, main_hwnd=None)
        avatar_url, alias, nickname, pid = subfunc_file.get_sw_acc_data(
            sw, account, avatar_url=None, alias="请获取数据", nickname="请获取数据", pid=None)
        _, img = AccInfoFunc.get_acc_avatar_from_files(sw, account)
        self._update_avatar_and_bind(img, avatar_url)
        # 刷新其他信息
        pid_str = f"{pid}" if pid is not None else "未登录"
        self.pid_label.config(text=f"进程: {pid_str}")
        self.mutex_label.config(text=f"互斥体: {has_mutex}")
        self.hwnd_label.config(text=f"窗口: {main_hwnd}")
        self.origin_id_var.set(account)
        self.cur_id_var.set(alias)
        try:
            self.nickname_var.set(nickname)
        except Exception as e:
            logger.warning(e)
            self.nickname_var.set(StringUtils.clean_texts(nickname))
        if not pid:
            subfunc_file.update_sw_acc_data(sw, account, has_mutex=True)
        printer.print_vn(f"载入数据完成")

        # 将局部变量赋值回实例变量
        self.pid = pid
        self.main_hwnd = main_hwnd
        self.avatar_url = avatar_url

    @staticmethod
    def _create_label_entry_grid(grid_frame, label_text, var_value, readonly=False):
        """内部使用的批量方法：创建一个标签和一个输入框，并返回标签和输入框的变量"""
        # 获取当前frame中已布局的组件数量，作为新组件的行号
        current_row = max([widget.grid_info().get('row', -1) for widget in grid_frame.grid_slaves()],
                          default=-1) + 1

        label = ttk.Label(grid_frame, text=label_text)
        label.grid(row=current_row, column=0, **Config.W_GRID_PACK)

        var = tk.StringVar(value=var_value)
        entry = ttk.Entry(grid_frame, width=30, textvariable=var, state="readonly" if readonly else "normal")
        entry.grid(row=current_row, column=1, **Config.W_GRID_PACK)

        return label, entry, var

    def _update_avatar_and_bind(self, img, avatar_url):
        try:
            new_size = tuple(int(dim * 2) for dim in Config.AVT_SIZE)
            img = img.resize(new_size, Image.Resampling.LANCZOS)  # type: ignore
            photo = ImageTk.PhotoImage(img)
            self.avatar_label.config(image=photo)
            self.avatar_label.image = photo
            self.avatar_label.bind("<Leave>", lambda event: self.avatar_label.config(cursor=""))
            if avatar_url:
                self.avatar_label.bind("<Enter>", lambda event: self.avatar_label.config(cursor="hand2"))
                self.avatar_label.bind("<Button-1>", lambda event: webbrowser.open(avatar_url))
            else:
                self.avatar_label.bind("<Enter>", lambda event: self.avatar_label.config(cursor=""))
                self.avatar_label.unbind("<Button-1>")
        except Exception as e:
            print(f"Error loading avatar: {e}")
            self.avatar_label.config(text="无头像")

    def do_and_update_ui(self, method):
        method()
        self.update_content()

    def _fetch_newest_data(self):
        self.fetching = True
        widget_utils.enable_widget_when_(self.fetch_button, False)
        widget_utils.set_widget_tip_when_(self.tooltips, self.fetch_button, {"获取中...": True})
        DetailWndFunc.thread_to_fetch_acc_detail_by_pid(self.sw, self.pid, self.account, self.update_content)

    def _save_acc_settings(self):
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
        auto_start = self.auto_start_var.get()
        hotkey = self.hotkey_var.get().strip()
        disable_avatar = self.disable_avatar_var.get()
        subfunc_file.update_sw_acc_data(
            self.sw, self.account, hidden=hidden, auto_start=auto_start, hotkey=hotkey, disable_avatar=disable_avatar)
        printer.vital("账号设置成功")
        self.wnd.destroy()
        self.tab_class.refresh_frame(self.sw)

    # def _set_avatar_disabled(self, disabled):
    #     if disabled is True:
    #         AccInfoFunc.disable_avatar_for_acc(self.sw, self.account)
    #     elif disabled is False and self.avatar_url == Strings.NO_NEED_AVT_URL:
    #         subfunc_file.update_sw_acc_data(self.sw, self.account, avatar_url=None)

    def set_focus_to_(self, widget_tag):
        if widget_tag == "note":
            self.note_entry.focus_set()
        elif widget_tag == "hotkey":
            self.hotkey_entry.focus_set()


class DebugWndUI(SubToolWndUI, ABC):
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
        self.wnd_width, self.wnd_height = Config.DEBUG_WND_SIZE

    def load_ui(self):
        # 创建工具栏
        toolbar = tk.Frame(self.wnd_frame)
        toolbar.pack(side="top", fill="x")

        # 刷新按钮
        refresh_button = tk.Button(toolbar, text="刷新", command=self.refresh_text)
        refresh_button.pack(side="left")
        # 打印日志按钮
        print_log_button = tk.Button(toolbar, text="生成日志文件", command=self.save_log_to_desktop)
        print_log_button.pack(side="left")
        # 缩进复选框
        self.indent_var = tk.BooleanVar(value=True)
        indent_checkbox = tk.Checkbutton(toolbar, text="缩进", variable=self.indent_var, command=self.refresh_text)
        indent_checkbox.pack(side="left")
        # 创建Frame用于包含两个滑块
        indent_frame = tk.Frame(toolbar)
        indent_frame.pack(side="left")
        # 最小缩进尺
        min_indent_label = tk.Label(indent_frame, text="最小缩进:")
        min_indent_label.pack(side="left")
        self.min_indent_scale = tk.Scale(indent_frame, from_=0, to=20, orient="horizontal",
                                         command=lambda x: self._update_indent_scales())
        self.min_indent_scale.set(0)  # 设置默认最小缩进
        self.min_indent_scale.pack(side="left")
        # 最大缩进尺
        max_indent_label = tk.Label(indent_frame, text="最大缩进:")
        max_indent_label.pack(side="left")
        self.max_indent_scale = tk.Scale(indent_frame, from_=0, to=20, orient="horizontal",
                                         command=lambda x: self._update_indent_scales())
        self.max_indent_scale.set(20)  # 设置默认最大缩进
        self.max_indent_scale.pack(side="left")
        # 调用复选框
        self.callstack_var = tk.BooleanVar(value=True)
        callstack_checkbox = tk.Checkbutton(toolbar, text="调用栈", variable=self.callstack_var,
                                            command=self._update_simplify_checkbox)
        callstack_checkbox.pack(side="left")
        # 简化复选框
        self.simplify_var = tk.BooleanVar(value=True)
        self.simplify_checkbox = tk.Checkbutton(toolbar, text="简化调用栈",
                                                variable=self.simplify_var, command=self.refresh_text)
        self.simplify_checkbox.pack(side="left")
        # 创建带滚动条的文本框
        self.text_area = scrolledtext.ScrolledText(self.wnd_frame, wrap=tk.NONE)
        self.text_area.pack(fill="both", expand=True)
        self.text_area.tag_configure("unimportant", foreground="grey")
        # 设置字体
        font = Font(family="JetBrains Mono", size=10)
        self.text_area.config(font=font)

    def update_content(self):
        # 初始化显示日志
        self.refresh_text()

    def _update_indent_scales(self):
        """缩进滑块的更新"""
        min_indent = self.min_indent_scale.get()
        max_indent = self.max_indent_scale.get()
        # 确保最小缩进小于最大缩进
        if min_indent > max_indent:
            self.min_indent_scale.set(max_indent)
            self.max_indent_scale.set(min_indent)
        # 调用refresh_text更新显示
        self.refresh_text()

    def _update_simplify_checkbox(self):
        """刷新简化复选框"""
        if self.callstack_var.get():
            self.simplify_checkbox.config(state=tk.NORMAL)  # 启用
        else:
            self.simplify_checkbox.config(state="disabled")  # 禁用
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
        self.text_area.config(state="disabled")

    def save_log_to_desktop(self):
        desktop = winshell.desktop()
        current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"mwm_log_{current_time}.txt"
        file_path = os.path.join(desktop, file_name)
        try:
            content = self.text_area.get("1.0", "end").strip()  # 获取从第一行到末尾的内容，并移除多余空白
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"日志已成功保存到：{file_path}")
        except Exception as e:
            print(f"保存日志时发生错误：{e}")


class LoadingWndUI(SubToolWndUI):
    def __init__(self, wnd, title):
        self.progress = None
        self.label = None
        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        # self.wnd_width, self.wnd_height = Constants.LOADING_WND_SIZE
        pass

    def set_wnd(self):
        self.wnd.resizable(False, False)
        self.wnd.overrideredirect(True)  # 去除窗口标题栏

    def load_ui(self):
        frame = ttk.Frame(self.wnd_frame, padding=Config.FRM_PAD)
        frame.pack(**Config.FRM_PACK)
        self.label = ttk.Label(frame, text="正在载入，请稍等……")
        self.label.pack(pady=Config.T_PAD_Y)
        self.progress = ttk.Progressbar(frame, mode="determinate", length=Config.LOADING_PRG_LEN)
        self.progress.pack(pady=Config.T_PAD_Y)

    def update_content(self):
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


class AboutWndUI(SubToolWndUI, ABC):
    # TODO: 提取滚动文本的公共方法
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
        self.wnd_width, self.wnd_height = Config.ABOUT_WND_SIZE
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

    def load_ui(self):
        self.remote_cfg_data = subfunc_file.read_remote_cfg_in_rules()
        if self.remote_cfg_data is None:
            messagebox.showinfo("提示", "无法获取配置文件，请检查网络连接后重试")
            # 关闭wnd窗口
            self.wnd.destroy()
        else:
            self._display_main_content()

    def _display_main_content(self):
        self.app_name = self.remote_cfg_data[LocalCfg.GLOBAL_SECTION]["app_name"]
        self.about_info = self.remote_cfg_data[LocalCfg.GLOBAL_SECTION]["about"]

        self.main_frame = ttk.Frame(self.wnd_frame, padding=Config.FRM_PAD)
        self.main_frame.pack(**Config.FRM_PACK)

        # 图标框架（左框架）
        logo_frame = ttk.Frame(self.main_frame, padding=Config.L_FRM_PAD)
        logo_frame.pack(**Config.L_FRM_PACK)

        # 内容框架（右框架）
        self.content_frame = ttk.Frame(self.main_frame, padding=Config.R_FRM_PAD)
        self.content_frame.pack(**Config.R_FRM_PACK)

        # 加载并调整图标
        try:
            icon_image = Image.open(Config.PROJ_ICO_PATH)
            icon_image = icon_image.resize(Config.LOGO_SIZE, Image.Resampling.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(icon_image)
        except Exception as e:
            logger.error(f"无法加载图标图片: {e}")
            # 如果图标加载失败，仍然继续布局
            self.logo_img = ImageTk.PhotoImage(Image.new('RGB', Config.LOGO_SIZE, color='white'))
        icon_label = ttk.Label(logo_frame, image=self.logo_img)
        icon_label.image = self.logo_img
        icon_label.pack(**Config.T_WGT_PACK)

        # 顶部：标题和版本号框架
        title_version_frame = ttk.Frame(self.content_frame)
        title_version_frame.pack(**Config.T_FRM_PACK)

        # 标题和版本号标签
        current_full_version = subfunc_file.get_app_current_version()
        title_version_str = f"{self.app_name} {current_full_version}"
        title_version_label = ttk.Label(
            title_version_frame,
            text=title_version_str,
            style='FirstTitle.TLabel',
        )
        title_version_label.pack(anchor='sw', **Config.T_WGT_PACK, ipady=Config.IPAD_Y)

        # 开发者主页
        author_label = ttk.Label(self.content_frame, text="by 吾峰起浪", style='SecondTitle.TLabel')
        author_label.pack(anchor='sw', **Config.T_WGT_PACK)
        self.pack_grids(self.content_frame, self.about_info["author"])

        # 项目信息
        proj_label = ttk.Label(self.content_frame, text="项目信息", style='SecondTitle.TLabel')
        proj_label.pack(anchor='sw', **Config.T_WGT_PACK)
        self.pack_grids(self.content_frame, self.about_info["project"])

        # 鸣谢
        thanks_label = ttk.Label(self.content_frame, text="鸣谢", style='SecondTitle.TLabel')
        thanks_label.pack(anchor='sw', **Config.T_WGT_PACK)
        self.pack_grids(self.content_frame, self.about_info["thanks"])

        # 技术参考
        reference_label = ttk.Label(self.content_frame, text="技术参考", style='SecondTitle.TLabel')
        reference_label.pack(anchor='w', **Config.T_WGT_PACK)
        reference_frame = ttk.Frame(self.content_frame)
        reference_frame.pack(**Config.T_FRM_PACK)

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
        sponsor_label.pack(anchor='w', **Config.T_WGT_PACK)
        sponsor_frame.pack(**Config.T_FRM_PACK)

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
        bottom_frame.pack(**Config.B_FRM_PACK)

        surprise_sign = Strings.SURPRISE_SIGN
        prefix = surprise_sign if self.app_info.need_update is True else ""

        # 左边：声明框架
        disclaimer_frame = ttk.Frame(bottom_frame, padding=Config.L_FRM_PAD)
        disclaimer_frame.pack(**Config.L_FRM_PACK)
        # 右边：更新按钮
        update_button = ttk.Button(bottom_frame, text=f"{prefix}检查更新", style='Custom.TButton',
                                   command=partial(self.check_for_updates,
                                                   current_full_version=current_full_version))
        update_button.pack(side="right")

        # 免责声明
        disclaimer_label = ttk.Label(disclaimer_frame, style="RedWarning.TLabel",
                                     text="仅供学习交流，严禁用于商业用途，请于24小时内删除")
        disclaimer_label.pack(**Config.B_WGT_PACK)

        # 版权信息标签
        copyright_label = ttk.Label(
            disclaimer_frame,
            text="Copyright © 2025 吾峰起浪. All rights reserved.",
            style="LittleText.TLabel",
        )
        copyright_label.pack(**Config.T_WGT_PACK)

    def pack_scrollable_text(self, frame, part, height):
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
        text = tk.Text(frame, wrap="word", font=("", Config.LITTLE_FONTSIZE),
                       height=height, bg=self.wnd.cget("bg"),
                       yscrollcommand=scrollbar.set, bd=0, highlightthickness=0)

        text.insert(tk.END, '\n')
        text.insert(tk.END, self.scroll_text_str[part])
        text.insert(tk.END, '\n')

        widget_utils.add_hyperlink_events(text, self.scroll_text_str[part])
        text.config(state="disabled")
        text.pack(side="left", fill="x", expand=False, padx=Config.GRID_PAD)
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
        success, result = AppFunc.split_vers_by_cur_from_local(current_full_version)
        if success is True:
            new_versions, old_versions = result
            if len(new_versions) != 0:
                update_log_window = tk.Toplevel(self.wnd)
                UpdateLogWndUI(update_log_window, "", old_versions, new_versions)
                return True
            else:
                messagebox.showinfo("提醒", f"当前版本{current_full_version}已是最新版本。")
                return True
        else:
            messagebox.showinfo("错误", result)
            return False

    @staticmethod
    def pack_grids(frame, part_dict, max_columns=6):
        grids = ttk.Frame(frame)
        grids.pack(**Config.T_FRM_PACK)
        for idx, info in enumerate(part_dict.values()):
            item = ttk.Label(grids, text=info.get('text', None),
                             style="Link.TLabel", cursor="hand2")
            row = idx // max_columns
            column = idx % max_columns
            item.grid(row=row, column=column, **Config.W_GRID_PACK)

            # 获取所有链接
            urls = []
            for link in info["links"].values():
                urls.append(link)

            # 绑定点击事件
            item.bind("<Button-1>", partial(lambda event, urls2open: AboutWndUI.open_urls(urls2open), urls2open=urls))

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


class RewardsWndUI(SubToolWndUI, ABC):
    def __init__(self, wnd, title):
        self.img = None
        self.image_path = Config.REWARDS_PNG_PATH
        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        # 加载图片
        self.img = Image.open(self.image_path)

    def load_ui(self):
        # 创建Frame并填充
        frame = ttk.Frame(self.wnd_frame)
        frame.pack(fill="both", expand=True)
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


class FeedBackWndUI(SubToolWndUI, ABC):
    def __init__(self, wnd, title):
        self.img = None
        self.image_path = Config.FEEDBACK_PNG_PATH
        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        # 加载图片
        self.img = Image.open(self.image_path)
        w, h = self.img.size
        self.img = self.img.resize((w // 2, h // 2), Image.Resampling.LANCZOS)

    def load_ui(self):
        # 创建Frame并填充
        img_frame = ttk.Frame(self.wnd_frame)
        img_frame.pack(fill="both", expand=True)
        # 调用方法在frame中显示图片
        self.show_image_in_frame(img_frame, self.img)
        btn_grid_frm = ttk.Frame(self.wnd_frame)
        btn_grid_frm.pack(**Config.B_FRM_PACK)
        copy_qq_channel_num_btn = CustomCornerBtn(btn_grid_frm, "复制频道号")
        copy_qq_channel_num_btn.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        btn_grid_frm.grid_columnconfigure(0, weight=1)
        UnlimitedClickHandler(
            self.root, copy_qq_channel_num_btn, **{"1": lambda: Tk2Sys.copy_to_clipboard(self.root, "pd94878499")})
        copy_qq_group_num_btn = CustomCornerBtn(btn_grid_frm, "复制群号")
        copy_qq_group_num_btn.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        btn_grid_frm.grid_columnconfigure(1, weight=1)
        UnlimitedClickHandler(
            self.root, copy_qq_group_num_btn, **{"1": lambda: Tk2Sys.copy_to_clipboard(self.root, "1040033347")}
        )

    @staticmethod
    def show_image_in_frame(frame, img):
        # 将图片转换为Tkinter格式
        tk_img = ImageTk.PhotoImage(img)

        # 在frame中创建Label用于显示图片
        label = ttk.Label(frame, image=tk_img)
        label.image = tk_img  # 防止图片被垃圾回收
        label.pack()


class UpdateLogWndUI(SubToolWndUI, ABC):
    def __init__(self, wnd, title, old_versions, new_versions=None):
        self.log_text = None
        self.old_versions = old_versions
        self.new_versions = new_versions

        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.wnd_width, self.wnd_height = Config.UPDATE_LOG_WND_SIZE

    def set_wnd(self):
        self.wnd.resizable(False, False)
        self.wnd.title("版本日志" if not self.new_versions else "发现新版本")

    def load_ui(self):
        new_versions = self.new_versions
        old_versions = self.old_versions

        main_frame = self.wnd_frame

        # 更新日志(标题)
        log_label = ttk.Label(main_frame, text="版本日志", font=("", 11))
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
        log_frame.pack(pady=(5, 0), fill="both", expand=True)

        # 创建滚动条
        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side="right", fill="y")

        # 创建不可编辑且可滚动的文本框
        self.log_text = tk.Text(log_frame, wrap="word", font=("", 10), height=6, bg=self.wnd.cget("bg"),
                                yscrollcommand=scrollbar.set, bd=0, highlightthickness=0)

        # 需要显示新版本
        if new_versions:
            try:
                newest_version = file_utils.get_newest_full_version(new_versions)
                print(newest_version)
                curr_sys_ver_name = sys_utils.get_sys_major_version_name()
                curr_sys_newest_ver_dicts = global_info["update"][newest_version]["pkgs"][curr_sys_ver_name]
                bottom_frame = ttk.Frame(main_frame)
                bottom_frame.pack(side="bottom", fill="x", padx=20, pady=20)
                cancel_button = ttk.Button(bottom_frame, text="以后再说",
                                           command=lambda: self.root.destroy())
                cancel_button.pack(side="right")
                download_button = ttk.Button(bottom_frame, text="下载新版",
                                             command=partial(self.show_download_window,
                                                             ver_dicts=curr_sys_newest_ver_dicts))
                download_button.pack(side="right")
                # 说明
                information_label = ttk.Label(
                    bottom_frame,
                    text="发现新版本，是否下载？"
                )
                information_label.pack(side="right", pady=(5, 0))

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
        self.log_text.config(state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)

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
                                          command=partial(UpdateLogWndFunc.close_and_update, tmp_path=download_path))
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
            t = threading.Thread(target=UpdateLogWndFunc.download_files,
                                 args=(ver_dicts, download_path, update_progress,
                                       lambda: close_and_update_btn.config(state="normal"), status))
            t.start()


class StatisticWndUI(SubToolWndUI, ABC):
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
        self.wnd_width, self.wnd_height = Config.STATISTIC_WND_SIZE
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

    def load_ui(self):
        # 创建一个可以滚动的画布，并放置一个主框架在画布上
        self.scrollable_canvas = ScrollableCanvasW(self.wnd_frame)
        self.main_frame = self.scrollable_canvas.main_frame

        self.create_manual_table()
        self.create_auto_table()
        self.create_refresh_table()

    def update_content(self):
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

        self.manual_tree.pack(fill="x", expand=True, padx=(20, 5), pady=(0, 10))
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

        self.auto_tree.pack(fill="x", expand=True, padx=(20, 5), pady=(0, 10))
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

        self.refresh_tree.pack(fill="x", expand=True, padx=(20, 5), pady=(0, 10))
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


class SettingWndUI(SubToolWndUI, ABC):
    def __init__(self, wnd, sw, title):
        self.path_var_dict = {}
        self.clear_acc_var = None
        self.title_entry = None
        self.need_to_reinit = None
        self.visible_ckb = None
        self.visible_var = None
        self.enable_cb = None
        self.enable_var = None
        self.error_msg = {}
        self.main_frame = None
        self.multirun_mode = None
        self.origin_values = None
        self.changed = None
        self.login_size_entry = None
        self.login_size_var = None
        self.screen_size_entry = None
        self.screen_size_var = None
        self.version_entry = None
        self.version_var = None
        self.dll_path_entry = None
        self.data_path_entry = None
        self.install_path_entry = None

        self.sw = sw
        self.need_to_clear_acc = False

        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.wnd_width, self.wnd_height = Config.SETTING_WND_SIZE
        self.wnd_height = None
        self.changed: Dict[str, bool] = {
            "inst_path": False,
            "data_dir": False,
            "dll_dir": False,
            "login_size": False,
            "state": False,
        }
        sw = self.sw
        self.origin_values = {
            "inst_path": subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, LocalCfg.INST_PATH),
            "data_dir": subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, LocalCfg.DATA_DIR),
            "dll_dir": subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, LocalCfg.DLL_DIR),
            "login_size": subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, LocalCfg.LOGIN_SIZE),
            "state": subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, LocalCfg.STATE),
        }
        self.error_msg = {
            "inst_path": "请选择可执行文件!",
            "data_dir": "请选择正常的存储文件夹!",
            "dll_dir": "请选择包含dll文件的版本号最新的文件夹!",
            "login_size": '不符合"数字*数字"的格式'
        }

    def load_ui(self):
        def _get_new_row_in_grid(grid_frm):
            return max([widget.grid_info().get('row', -1) for widget in grid_frm.grid_slaves()], default=-1) + 1

        main_frame = ttk.Frame(self.wnd_frame, padding=Config.FRM_PAD)
        main_frame.pack(**Config.FRM_PACK)
        settings_grid_frm = ttk.Frame(main_frame, padding=Config.FRM_PAD)
        settings_grid_frm.pack(**Config.T_FRM_PACK)
        # 标题
        current_row = _get_new_row_in_grid(settings_grid_frm)
        default_value, = subfunc_file.get_settings(self.sw, label="")
        note_label = tk.Label(settings_grid_frm, text="平台备注：")
        note_label.grid(row=current_row, column=0, **Config.W_GRID_PACK)
        self.title_entry = DefaultEntry(settings_grid_frm, default_label=default_value)
        self.title_entry.grid(row=current_row, column=1, columnspan=3, **Config.WE_GRID_PACK)
        now_value, = subfunc_file.get_settings(self.sw, note="")
        self.title_entry.set_value(now_value)
        # 第一行 - 安装路径
        current_row = _get_new_row_in_grid(settings_grid_frm)
        install_label = tk.Label(settings_grid_frm, text="程序路径：")
        install_label.grid(row=current_row, column=0, **Config.W_GRID_PACK)
        self.path_var_dict[LocalCfg.INST_PATH] = tk.StringVar()
        install_path_entry = tk.Entry(settings_grid_frm, textvariable=self.path_var_dict[LocalCfg.INST_PATH], width=70)
        install_path_entry.grid(row=current_row, column=1, **Config.WE_GRID_PACK)
        install_get_button = ttk.Button(
            settings_grid_frm, text="获取", command=partial(self.load_or_detect_path_of, LocalCfg.INST_PATH, True))
        install_get_button.grid(row=current_row, column=2, **Config.WE_GRID_PACK)
        install_choose_button = ttk.Button(settings_grid_frm, text="选择路径",
                                           command=partial(self.choose_sw_inst_path, self.sw))
        install_choose_button.grid(row=current_row, column=3, **Config.WE_GRID_PACK)
        # 第二行 - 数据存储路径
        current_row = _get_new_row_in_grid(settings_grid_frm)
        data_label = tk.Label(settings_grid_frm, text="存储路径：")
        data_label.grid(row=current_row, column=0, **Config.W_GRID_PACK)
        self.path_var_dict[LocalCfg.DATA_DIR] = tk.StringVar()
        data_path_entry = tk.Entry(settings_grid_frm, textvariable=self.path_var_dict[LocalCfg.DATA_DIR], width=70)
        data_path_entry.grid(row=current_row, column=1, **Config.WE_GRID_PACK)
        data_get_button = ttk.Button(settings_grid_frm, text="获取",
                                     command=partial(self.load_or_detect_path_of, LocalCfg.DATA_DIR, True))
        data_get_button.grid(row=current_row, column=2, **Config.WE_GRID_PACK)
        data_choose_button = ttk.Button(settings_grid_frm, text="选择路径",
                                        command=partial(self.choose_sw_data_dir, self.sw))
        data_choose_button.grid(row=current_row, column=3, **Config.WE_GRID_PACK)
        # 新增第三行 - dll路径
        current_row = _get_new_row_in_grid(settings_grid_frm)
        dll_label = tk.Label(settings_grid_frm, text="DLL所在路径：")
        dll_label.grid(row=current_row, column=0, **Config.W_GRID_PACK)
        self.path_var_dict[LocalCfg.DLL_DIR] = tk.StringVar()
        dll_path_entry = tk.Entry(settings_grid_frm, textvariable=self.path_var_dict[LocalCfg.DLL_DIR], width=70)
        dll_path_entry.grid(row=current_row, column=1, **Config.WE_GRID_PACK)
        dll_get_button = ttk.Button(settings_grid_frm, text="获取",
                                    command=partial(self.load_or_detect_path_of, LocalCfg.DLL_DIR, True))
        dll_get_button.grid(row=current_row, column=2, **Config.WE_GRID_PACK)
        dll_choose_button = ttk.Button(settings_grid_frm, text="选择路径",
                                       command=partial(self.choose_sw_dll_dir, self.sw))
        dll_choose_button.grid(row=current_row, column=3, **Config.WE_GRID_PACK)
        # 新增第四行 - 登录窗口大小
        current_row = _get_new_row_in_grid(settings_grid_frm)
        login_size_label = tk.Label(settings_grid_frm, text="登录尺寸：")
        login_size_label.grid(row=current_row, column=0, **Config.W_GRID_PACK)
        self.login_size_var = tk.StringVar()
        login_size_entry = tk.Entry(settings_grid_frm, textvariable=self.login_size_var, width=70)
        login_size_entry.grid(row=current_row, column=1, **Config.WE_GRID_PACK)
        login_size_get_button = ttk.Button(settings_grid_frm, text="获取", command=self.thread_to_get_login_size)
        login_size_get_button.grid(row=current_row, column=2, columnspan=2, **Config.WE_GRID_PACK)
        # 新增第五行 - 平台禁用与显示
        current_row = _get_new_row_in_grid(settings_grid_frm)
        stata_frame = ttk.Frame(settings_grid_frm, padding=Config.FRM_PAD)
        stata_frame.grid(row=current_row, column=0, columnspan=3, **Config.WE_GRID_PACK)
        # 启用复选框
        self.enable_var = tk.BooleanVar()
        enable_ckb = ttk.Checkbutton(stata_frame, text="启用(所有功能,包括自启动账号功能)",
                                     variable=self.enable_var,
                                     command=self._update_visible_state)
        enable_ckb.pack(**Config.R_WGT_PACK)
        # 显示复选框
        self.visible_var = tk.BooleanVar()
        self.visible_ckb = ttk.Checkbutton(stata_frame, text="在主界面显示", variable=self.visible_var)
        self.visible_ckb.pack(**Config.R_WGT_PACK)
        # 清除账号数据复选框
        self.clear_acc_var = tk.BooleanVar()
        clear_acc_ckb = ttk.Checkbutton(stata_frame, text="清除账号数据(本次)", variable=self.clear_acc_var)
        clear_acc_ckb.pack(**Config.R_WGT_PACK)

        # 修改确定按钮，从第4行到第5行
        current_row = _get_new_row_in_grid(settings_grid_frm)
        ok_button = ttk.Button(settings_grid_frm, text="保存", command=self.on_ok)
        ok_button.grid(row=current_row - 1, column=3, **Config.NEWS_GRID_PACK)

        # 配置列的权重，使得中间的 Entry 可以自动扩展
        settings_grid_frm.grid_columnconfigure(1, weight=1)
        self.main_frame = settings_grid_frm

    def update_content(self):
        # 初始加载已经配置的，或是没有配置的话自动获取
        self.path_var_dict[LocalCfg.INST_PATH].set(self.origin_values[LocalCfg.INST_PATH])
        self.path_var_dict[LocalCfg.DATA_DIR].set(self.origin_values[LocalCfg.DATA_DIR])
        self.path_var_dict[LocalCfg.DLL_DIR].set(self.origin_values[LocalCfg.DLL_DIR])
        self.login_size_var.set(self.origin_values[LocalCfg.LOGIN_SIZE])
        self.set_sw_state_cb_from_(self.origin_values[LocalCfg.STATE])

    def _update_visible_state(self):
        """内部使用的联动逻辑"""
        if self.enable_var.get():
            self.visible_ckb.config(state="normal")  # 启用显示复选框
        else:
            self.visible_ckb.config(state="disabled")  # 禁用显示复选框
            self.visible_var.set(False)  # 强制取消勾选

    def set_sw_state_cb_from_(self, state_code):
        """根据状态码设置复选框值和状态"""
        enable_var = self.enable_var
        visible_var = self.visible_var
        visible_cb = self.visible_ckb

        if state_code == SwStates.DISABLED:
            enable_var.set(False)
            visible_var.set(False)
            visible_cb.config(state="disabled")
        elif state_code == SwStates.HIDDEN:
            enable_var.set(True)
            visible_var.set(False)
            visible_cb.config(state="normal")
        elif state_code == SwStates.VISIBLE:
            enable_var.set(True)
            visible_var.set(True)
            visible_cb.config(state="normal")

    def get_sw_state_from_ckb(self):
        """根据复选框值返回当前状态码"""
        if not self.enable_var.get():
            return SwStates.DISABLED
        return SwStates.VISIBLE if self.visible_var.get() else SwStates.HIDDEN

    def check_bools(self):
        # 需要检验是否更改的属性
        for path_type in [LocalCfg.INST_PATH, LocalCfg.DATA_DIR, LocalCfg.DLL_DIR]:
            self.changed[path_type] = self.path_var_dict[path_type].get() != self.origin_values[path_type]
        # self.changed[LocalCfg.INST_PATH] = self.path_var_dict[LocalCfg.INST_PATH].get() != self.origin_values[LocalCfg.INST_PATH]
        # self.changed[LocalCfg.DATA_DIR] = self.data_dir_var.get() != self.origin_values[LocalCfg.DATA_DIR]
        # self.changed[LocalCfg.DLL_DIR] = self.dll_dir_var.get() != self.origin_values[LocalCfg.DLL_DIR]
        self.changed[LocalCfg.LOGIN_SIZE] = self.login_size_var.get() != self.origin_values[LocalCfg.LOGIN_SIZE]
        self.changed[LocalCfg.STATE] = self.get_sw_state_from_ckb() != self.origin_values[LocalCfg.STATE]

        # # 需要清除平台账号数据的情况
        # keys_to_check = ["data_dir"]
        # self.need_to_clear_acc = any(self.changed[key] for key in keys_to_check)
        # 需要重新初始化的情况
        if self.changed[LocalCfg.STATE]:
            self.need_to_reinit = True

    def on_ok(self):
        if not self.validate_paths_and_ask():
            return
        inst_path = self.path_var_dict[LocalCfg.INST_PATH].get()
        data_dir = self.path_var_dict[LocalCfg.DATA_DIR].get()
        dll_dir = self.path_var_dict[LocalCfg.DLL_DIR].get()
        login_size = self.login_size_var.get()
        inst_path = None if inst_path.startswith("获取失败") else inst_path
        data_dir = None if data_dir.startswith("获取失败") else data_dir
        dll_dir = None if dll_dir.startswith("获取失败") else dll_dir
        state = self.get_sw_state_from_ckb()
        note = self.title_entry.get_value()
        # print(f"结束时候状态:{state}")
        subfunc_file.save_a_setting_and_callback(self.sw, LocalCfg.INST_PATH, inst_path)
        subfunc_file.save_a_setting_and_callback(self.sw, LocalCfg.DATA_DIR, data_dir)
        subfunc_file.save_a_setting_and_callback(self.sw, LocalCfg.DLL_DIR, dll_dir)
        subfunc_file.save_a_setting_and_callback(self.sw, LocalCfg.LOGIN_SIZE, login_size)
        subfunc_file.save_a_setting_and_callback(self.sw, LocalCfg.STATE, state)
        subfunc_file.save_a_setting_and_callback(self.sw, LocalCfg.NOTE, note)
        self.wnd.destroy()

        self.check_bools()

        def _do():
            # 检查是否需要清空账号信息
            if self.clear_acc_var.get() is True:
                print("清除平台账号数据")
                subfunc_file.clear_some_acc_data(self.sw)
            if self.need_to_reinit:
                self.root_class.initialize_in_root()
                return
            if self.root_class.root_ui:
                self.root_class.root_ui.refresh_current_tab()

        _do()

    def finally_do(self):
        # 关闭窗口的话,不保存
        subfunc_file.save_a_setting_and_callback(self.sw, LocalCfg.INST_PATH, self.origin_values[LocalCfg.INST_PATH])
        subfunc_file.save_a_setting_and_callback(self.sw, LocalCfg.DATA_DIR, self.origin_values[LocalCfg.DATA_DIR])
        subfunc_file.save_a_setting_and_callback(self.sw, LocalCfg.DLL_DIR, self.origin_values[LocalCfg.DLL_DIR])
        subfunc_file.save_a_setting_and_callback(self.sw, LocalCfg.LOGIN_SIZE, self.origin_values[LocalCfg.LOGIN_SIZE])

    def validate_paths_and_ask(self):
        invalid_vars = []
        inst_path = self.path_var_dict[LocalCfg.INST_PATH].get()
        data_dir = self.path_var_dict[LocalCfg.DATA_DIR].get()
        dll_dir = self.path_var_dict[LocalCfg.DLL_DIR].get()
        login_size = self.login_size_var.get()

        if not SwInfoUtils.is_valid_sw_path(LocalCfg.INST_PATH, self.sw, inst_path):
            invalid_vars.append(LocalCfg.INST_PATH.value)
        if not SwInfoUtils.is_valid_sw_path(LocalCfg.DATA_DIR, self.sw, data_dir):
            invalid_vars.append(LocalCfg.DATA_DIR.value)
        if not SwInfoUtils.is_valid_sw_path(LocalCfg.DLL_DIR, self.sw, dll_dir):
            invalid_vars.append(LocalCfg.DLL_DIR.value)
        if not bool(re.match(r'^\d+\*\d+$', login_size)):
            invalid_vars.append(LocalCfg.LOGIN_SIZE.value)

        if not invalid_vars:
            return True
        # 存在无效项时询问用户
        error_msg = "以下设置项存在问题：\n\n" + "\n".join(f"• {item}:{self.error_msg[item]}" for item in invalid_vars)
        error_msg += "\n\n是否坚持使用当前设置？"

        return messagebox.askyesno(
            "设置验证",
            error_msg,
            icon="warning"
        )

    def load_or_detect_path_of(self, path_type, detect=False):
        """获取路径, 若成功会进行保存, detect为是否忽略本地记录重新探索"""
        if detect is False:
            path = SwInfoFunc.try_get_path_of_(self.sw, path_type)
        else:
            path = SwInfoFunc.detect_path_of_(self.sw, path_type)
        if path:
            self.path_var_dict[path_type].set(path.replace('\\', '/'))

    # def load_or_get_sw_inst_path(self, sw, detect=False):
    #     """获取路径, 若成功会进行保存, detect为是否忽略本地记录重新探索"""
    #     if detect is False:
    #         path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.INST_PATH)
    #     else:
    #         path = SwInfoFunc.detect_path_of_(sw, LocalCfg.INST_PATH)
    #     if path:
    #         self.inst_path_var.set(path.replace('\\', '/'))

    def choose_sw_inst_path(self, sw):
        """选择路径，若检验成功会进行保存"""
        selected_path = None  # 用于保存最终选择的路径
        while True:
            path = filedialog.askopenfilename(filetypes=[("Executable files", "*.exe"), ("All files", "*.*")])
            if not path:  # 用户取消选择
                return
            if SwInfoUtils.is_valid_sw_path(LocalCfg.INST_PATH, sw, path):
                selected_path = path
                break
            else:
                if not messagebox.askyesno(
                        "提醒",
                        f"该路径可能不是有效的程序路径，{self.error_msg[LocalCfg.INST_PATH]}\n是否坚持选择该路径？",
                        icon="warning"):
                    continue  # 用户选择"否"，继续循环
                selected_path = path
                break

        if selected_path:
            self.path_var_dict[LocalCfg.INST_PATH].set(selected_path)

    # def load_or_get_sw_data_dir(self, sw, ignore_local_rec=False):
    #     """获取路径，若成功会进行保存"""
    #     path = SwInfoFunc.detect_path_of_(sw, LocalCfg.DATA_DIR, ignore_local_rec)
    #     if path:
    #         self.data_dir_var.set(path.replace('\\', '/'))

    @staticmethod
    def _ask_for_directory():
        try:
            # 尝试使用 `filedialog.askdirectory` 方法
            path = filedialog.askdirectory()
            if not path:  # 用户取消选择
                return None
            return path
        except Exception as e:
            logger.error(f"filedialog.askdirectory 失败，尝试使用 win32com.client: {e}")
            try:
                # 异常处理部分，使用 `win32com.client`
                shell = win32com.client.Dispatch("Shell.Application")
                folder = shell.BrowseForFolder(0, "Select Folder", 0, 0)
                if not folder:  # 用户取消选择
                    return None
                return folder.Self.Path.replace('\\', '/')
            except Exception as e:
                logger.error(f"win32com.client 也失败了: {e}")
                return None

    def choose_sw_data_dir(self, sw):
        """选择路径，若检验成功会进行保存"""
        selected_path = None  # 用于保存最终选择的路径
        while True:
            path = SettingWndUI._ask_for_directory()
            if not path:  # 用户取消选择
                return
            if SwInfoUtils.is_valid_sw_path(LocalCfg.DATA_DIR, sw, path):
                selected_path = path
                break
            else:
                if not messagebox.askyesno(
                        "提醒",
                        f"该路径可能不是有效的存储路径，{self.error_msg[LocalCfg.DATA_DIR]}\n是否坚持选择该路径？",
                        icon="warning"):
                    continue  # 用户选择"否"，继续循环
                selected_path = path
                break

        if selected_path:
            self.path_var_dict[LocalCfg.DATA_DIR].set(selected_path)

    # def load_or_get_sw_dll_dir(self, sw, ignore_local_rec=False):
    #     """获取路径，若成功会进行保存"""
    #     path = SwInfoFunc.detect_path_of_(sw, LocalCfg.DLL_DIR, ignore_local_rec)
    #     if path:
    #         self.dll_dir_var.set(path.replace('\\', '/'))

    def choose_sw_dll_dir(self, sw):
        """选择路径，若检验成功会进行保存"""
        selected_path = None  # 用于保存最终选择的路径
        while True:
            path = SettingWndUI._ask_for_directory()
            if not path:  # 用户取消选择
                return
            if SwInfoUtils.is_valid_sw_path(LocalCfg.DLL_DIR, sw, path):
                selected_path = path
                break
            else:
                if not messagebox.askyesno(
                        "提醒",
                        f"该路径可能不是有效的存储路径，{self.error_msg[LocalCfg.DLL_DIR]}\n是否坚持选择该路径？",
                        icon="warning"):
                    continue  # 用户选择"否"，继续循环
                selected_path = path
                break

        if selected_path:
            self.path_var_dict[LocalCfg.DLL_DIR].set(selected_path)

    def thread_to_get_login_size(self):
        def thread():
            sw = self.sw
            self.multirun_mode = self.root_class.sw_classes[sw].multirun_mode
            result = SwOperator.get_login_size(sw)
            if isinstance(result, tuple):
                login_width, login_height = result
                self.root.after(0, self.login_size_var.set, f"{login_width}*{login_height}")

        threading.Thread(target=thread).start()


class GlobalSettingWndUI(SubToolWndUI, ABC):
    def __init__(self, wnd, title):
        self.proxy_port = None
        self.proxy_ip = None
        self.proxy_detail_occ = None
        self.proxy_detail_frame = None
        self.port_var = None
        self.addr_var = None
        self.use_proxy_var = None
        self.main_frame = wnd
        self.remote_config_var = None
        self.screen_size_var = None
        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.remote_config_var = tk.StringVar()
        self.screen_size_var = tk.StringVar()
        self.use_proxy_var = tk.BooleanVar()
        self.addr_var = tk.StringVar()
        self.port_var = tk.StringVar()

    def load_ui(self):
        """加载主要控件"""
        # 总框架
        main_frame = ttk.Frame(self.wnd_frame, padding=Config.FRM_PAD)
        main_frame.pack(**Config.FRM_PACK)

        # 代理框架=使用代理复选框+代理设置框架
        proxy_frame = ttk.Frame(main_frame)
        proxy_frame.pack(side="top", fill="x")
        # 使用代理复选框
        proxy_checkbox = ttk.Checkbutton(
            proxy_frame, text="使用代理", variable=self.use_proxy_var,
            command=lambda: self.do_and_update(
                partial(subfunc_file.save_a_global_setting_and_callback, LocalCfg.USE_PROXY, self.use_proxy_var.get())))
        proxy_checkbox.pack(side="top", fill="x")
        # 代理设置框架，将会根据是否使用代理而显示或隐藏
        proxy_detail_frame = ttk.Frame(proxy_frame)
        proxy_detail_frame.pack(side="top", fill="x")
        # 使用方法创建地址和端口的grid
        _, ip_btn_frame, _, ip_var = self._create_label_btn_entry_grid(proxy_detail_frame, "地址:", "")
        _, port_btn_frame, _, port_var = self._create_label_btn_entry_grid(proxy_detail_frame, "端口:", "")
        # 添加预设按钮
        ip_presets, port_presets = subfunc_file.get_remote_cfg(RemoteCfg.GLOBAL, "proxy",
                                                               ip_presets=None, port_presets=None)
        customized_btn_pad = int(Config.CUS_BTN_PAD_X * 0.4)

        def _create_btn_in_(frame_of_btn, text):
            btn = CustomCornerBtn(frame_of_btn, text=text, i_padx=8, i_pady=2)
            return btn

        def _pack_btn(btn):
            btn.pack(side="left", padx=customized_btn_pad * 2, pady=customized_btn_pad)

        for ip in ip_presets:
            b = _create_btn_in_(ip_btn_frame, ip["name"])
            b.set_bind_map(
                **{"1": partial(ip_var.set, ip["value"])}).apply_bind(self.root)
            _pack_btn(b)
        for port in port_presets:
            b = _create_btn_in_(port_btn_frame, port["name"])
            b.set_bind_map(
                **{"1": partial(port_var.set, port["value"])}).apply_bind(self.root)
            _pack_btn(b)

        # 底部放三个按钮：确定，取消，应用
        bottom_btn_frame = ttk.Frame(main_frame)
        bottom_btn_frame.pack(side="bottom", fill="x")

        # 确定按钮
        ok_btn = _create_btn_in_(bottom_btn_frame, "确定")
        ok_btn.set_bind_map(
            **{"1": self.save_settings}).apply_bind(self.root)
        ok_btn.pack(side="right", padx=customized_btn_pad * 2, pady=customized_btn_pad)

        self.proxy_detail_frame = proxy_detail_frame
        self.proxy_ip = ip_var
        self.proxy_port = port_var

    def update_content(self):
        use_proxy = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.USE_PROXY)
        self.use_proxy_var.set(use_proxy)
        ip = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.PROXY_IP)
        port = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.PROXY_PORT)
        self.proxy_ip.set(ip)
        self.proxy_port.set(port)

        # 若为True，则显示代理设置框架
        if self.use_proxy_var.get():
            # 将内部的控件设为可用
            CustomBtn.set_all_custom_widgets_to_(self.proxy_detail_frame, CustomBtn.State.NORMAL)
            widget_utils.set_all_children_in_frame_to_state(self.proxy_detail_frame, CustomBtn.State.NORMAL)
        else:
            CustomBtn.set_all_custom_widgets_to_(self.proxy_detail_frame, CustomBtn.State.DISABLED)
            widget_utils.set_all_children_in_frame_to_state(self.proxy_detail_frame, CustomBtn.State.DISABLED)

    def get_screen_size(self):
        screen_width = self.wnd.winfo_screenwidth()
        screen_height = self.wnd.winfo_screenheight()
        self.screen_size_var.set(f"{screen_width}*{screen_height}")
        subfunc_file.save_a_global_setting_and_callback('screen_size', f"{screen_width}*{screen_height}")

    def save_settings(self):
        use_proxy = self.use_proxy_var.get()
        ip = self.proxy_ip.get()
        port = self.proxy_port.get()
        subfunc_file.save_a_global_setting_and_callback(LocalCfg.USE_PROXY, use_proxy)
        subfunc_file.save_a_global_setting_and_callback(LocalCfg.PROXY_IP, ip)
        subfunc_file.save_a_global_setting_and_callback(LocalCfg.PROXY_PORT, port)
        printer.vital("设置成功")
        self.wnd.destroy()
        AppFunc.apply_proxy_setting()

    def do_and_update(self, func):
        func()
        self.update_content()

    @staticmethod
    def _create_label_btn_entry_grid(grid_frame, label_text, var_value, readonly=False):
        """内部使用的批量方法：创建一个标签和一个输入框，并返回标签和输入框的变量"""
        # 获取当前frame中已布局的组件数量，作为新组件的行号
        current_row = max([widget.grid_info().get('row', -1) for widget in grid_frame.grid_slaves()],
                          default=-1) + 1
        w_grid_pack = Config.W_GRID_PACK
        # (0,0)标签
        label = ttk.Label(grid_frame, text=label_text)
        label.grid(row=current_row, column=0, **w_grid_pack)
        # (0,1)按钮区域
        btn_frame = ttk.Frame(grid_frame)
        btn_frame.grid(row=current_row, column=1, **w_grid_pack)
        # (1,0)为空，(1,1)输入框
        var = tk.StringVar(value=var_value)
        entry = ttk.Entry(grid_frame, width=30, textvariable=var, state="readonly" if readonly else "normal")
        entry.grid(row=current_row + 1, column=1, **w_grid_pack)

        return label, btn_frame, entry, var
