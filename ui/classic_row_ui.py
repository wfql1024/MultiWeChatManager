from PIL import ImageTk
from utils import string_utils, widget_utils
import subprocess
import sys
import time
import tkinter as tk
from functools import partial
from tkinter import ttk

import psutil

from functions import func_config, func_login, func_account, subfunc_file
from resources.config import Config
from ui import detail_ui
from utils import handle_utils, json_utils, process_utils


class AccountRow:
    """
    为每一个账号创建其行布局的类
    """

    def __init__(self, parent_frame, account, data_path, status, is_logged_in, callbacks,
                 update_top_checkbox_callback):
        self.data_path = data_path
        self.status = status
        self.start_time = time.time()
        self.tooltips = {}
        self.toggle_avatar_label = None
        self.size = None
        self.update_top_checkbox_callback = update_top_checkbox_callback
        self.is_logged_in = is_logged_in
        style = ttk.Style()
        style.configure('Custom.TButton', padding=(5, 5))  # 水平方向20像素，垂直方向10像素的内边距

        display_name = func_account.get_account_display_name(account)
        config_status = func_config.get_config_status_by_account(account, self.data_path)

        # 行框架=复选框+头像标签+账号标签+按钮区域+配置标签
        self.row_frame = ttk.Frame(parent_frame)
        self.row_frame.pack(fill=tk.X, pady=2)

        # 复选框
        self.checkbox_var = tk.BooleanVar(value=False)
        self.checkbox = tk.Checkbutton(self.row_frame, variable=self.checkbox_var)
        self.checkbox.pack(side=tk.LEFT)

        # 头像标签
        self.avatar_label = self.create_avatar_label(account)
        self.avatar_label.pack(side=tk.LEFT)
        self.avatar_label.bind("<Enter>", lambda event: event.widget.config(cursor="hand2"))
        self.avatar_label.bind("<Leave>", lambda event: event.widget.config(cursor=""))

        # 账号标签
        has_mutex, = subfunc_file.get_acc_details_from_acc_json(account, has_mutex=None)
        style = ttk.Style()
        style.configure("Mutex.TLabel", foreground="red")
        # 清理 display_name
        cleaned_display_name = string_utils.clean_display_name(display_name)
        try:
            if has_mutex:
                self.account_label = ttk.Label(self.row_frame, text=display_name, style="Mutex.TLabel")
            else:
                self.account_label = ttk.Label(self.row_frame, text=display_name)
            self.account_label.pack(side=tk.LEFT, fill=tk.X, padx=(0, 10))
        except Exception as e:
            print(e)
            if has_mutex:
                self.account_label = ttk.Label(self.row_frame, text=cleaned_display_name, style="Mutex.TLabel")
            else:
                self.account_label = ttk.Label(self.row_frame, text=cleaned_display_name)
            self.account_label.pack(side=tk.LEFT, fill=tk.X, padx=(0, 10))

        # 按钮区域=配置或登录按钮
        self.button_frame = ttk.Frame(self.row_frame)
        self.button_frame.pack(side=tk.RIGHT)

        # 配置标签
        self.config_status_label = ttk.Label(self.row_frame, text=config_status, anchor='e')
        self.config_status_label.pack(side=tk.RIGHT, padx=5, fill=tk.X, expand=True)

        if is_logged_in:
            # 配置按钮
            self.config_button_text = "重新配置" if config_status != "无配置" else "添加配置"
            self.config_button = ttk.Button(
                self.button_frame,
                text=self.config_button_text,
                style='Custom.TButton',
                width=8,
                command=lambda: callbacks['config'](account, self.status)
            )
            self.config_button.pack(side=tk.RIGHT, padx=0)
            self.row_frame.bind("<Button-1>", self.toggle_checkbox, add="+")
            for child in self.row_frame.winfo_children():
                child.bind("<Button-1>", self.toggle_checkbox, add="+")
        else:
            # 登录按钮
            self.login_button = ttk.Button(self.button_frame, text="自动登录", style='Custom.TButton', width=8,
                                           command=lambda: callbacks['login'](account))
            self.login_button.pack(side=tk.RIGHT, padx=0)

            if config_status == "无配置":
                # 无配置禁用按钮且置底
                widget_utils.disable_button_and_add_tip(self.tooltips, self.login_button, "请先手动登录后配置")
                self.checkbox.config(state='disabled')
                self.row_frame.pack(side=tk.BOTTOM)
            else:
                # 启用按钮且为行区域添加复选框绑定
                widget_utils.enable_button_and_unbind_tip(self.tooltips, self.login_button)
                self.row_frame.bind("<Button-1>", self.toggle_checkbox, add="+")
                for child in self.row_frame.winfo_children():
                    child.bind("<Button-1>", self.toggle_checkbox, add="+")

        # 头像绑定详情事件
        self.avatar_label.bind("<Button-1>", lambda event: callbacks['detail'](account))
        print(f"加载{account}界面用时{time.time() - self.start_time:.4f}秒")

    def toggle_checkbox(self, event):
        """
        切换复选框状态
        :param event: 点击复选框
        :return: 阻断继续切换
        """
        self.checkbox_var.set(not self.checkbox_var.get())
        self.update_top_checkbox_callback(self.is_logged_in)
        return "break"

    def set_checkbox(self, value):
        """设置当前复选框的状态"""
        self.checkbox_var.set(value)

    def is_checked(self):
        """
        获取复选框状态
        :return: 复选框状态 -> bool
        """
        return self.checkbox_var.get()

    def create_avatar_label(self, account):
        """
        创建头像标签
        :param account: 原始微信号
        :return: 头像标签 -> Label
        """
        try:
            img = func_account.get_acc_avatar_from_files(account)
            img = img.resize((44, 44))
            photo = ImageTk.PhotoImage(img)
            avatar_label = ttk.Label(self.row_frame, image=photo)
            avatar_label.image = photo  # 保持对图像的引用
        except Exception as e:
            print(f"Error creating avatar label: {e}")
            # 如果加载失败，使用一个空白标签
            avatar_label = ttk.Label(self.row_frame, width=10)
        return avatar_label


class ClassicRowUI:
    def __init__(self, main_window, m_master, m_main_frame, result, data_path, multiple_status):
        self.main_window = main_window
        self.data_path = data_path
        self.multiple_status = multiple_status
        self.not_logged_in_rows = {}
        self.logged_in_rows = {}
        self.tooltips = {}
        self.master = m_master
        self.main_frame = m_main_frame
        self.logged_in_rows.clear()
        self.not_logged_in_rows.clear()
        logged_in, not_logged_in, wechat_processes = result

        # TODO: 精简一下
        if len(logged_in) != 0:
            # 已登录框架=已登录标题+已登录列表
            self.logged_in_frame = ttk.Frame(self.main_frame)
            self.logged_in_frame.pack(side=tk.TOP, fill=tk.X, pady=15, padx=10)

            # 已登录标题=已登录复选框+已登录标签+已登录按钮区域
            self.logged_in_title = ttk.Frame(self.logged_in_frame)
            self.logged_in_title.pack(side=tk.TOP, fill=tk.X)

            # 已登录复选框
            self.logged_in_checkbox_var = tk.IntVar(value=0)
            self.logged_in_checkbox = tk.Checkbutton(
                self.logged_in_title,
                variable=self.logged_in_checkbox_var,
                tristatevalue=-1
            )
            self.logged_in_checkbox.pack(side=tk.LEFT)

            # 已登录标签
            self.logged_in_label = ttk.Label(self.logged_in_title, text="已登录账号：", font=("", 10, "bold"))
            self.logged_in_label.pack(side=tk.LEFT, fill=tk.X, anchor="w", pady=10)

            # 已登录按钮区域=一键退出
            self.logged_in_button_frame = ttk.Frame(self.logged_in_title)
            self.logged_in_button_frame.pack(side=tk.RIGHT)

            # 一键退出
            self.one_key_quit = ttk.Button(self.logged_in_button_frame, text="一键退出", width=8,
                                           command=self.quit_selected_accounts, style='Custom.TButton')
            self.one_key_quit.pack(side=tk.RIGHT, pady=0)

            # 加载已登录列表
            for account in logged_in:
                self.add_account_row(self.logged_in_frame, account, True)

            self.update_top_title(True)

        # 未登录框架=未登录标题+未登录列表
        self.not_logged_in_frame = ttk.Frame(self.main_frame)
        self.not_logged_in_frame.pack(side=tk.TOP, fill=tk.X, pady=15, padx=10)

        # 未登录标题=未登录复选框+未登录标签+未登录按钮区域
        self.not_logged_in_title = ttk.Frame(self.not_logged_in_frame)
        self.not_logged_in_title.pack(side=tk.TOP, fill=tk.X)

        # 未登录复选框
        self.not_logged_in_checkbox_var = tk.IntVar(value=0)
        self.not_logged_in_checkbox = tk.Checkbutton(
            self.not_logged_in_title,
            variable=self.not_logged_in_checkbox_var,
            tristatevalue=-1
        )
        self.not_logged_in_checkbox.pack(side=tk.LEFT)

        # 未登录标签
        self.not_logged_in_label = ttk.Label(self.not_logged_in_title, text="未登录账号：", font=("", 10, "bold"))
        self.not_logged_in_label.pack(side=tk.LEFT, fill=tk.X, anchor="w", pady=10)

        # 未登录按钮区域=一键登录
        self.not_logged_in_bottom_frame = ttk.Frame(self.not_logged_in_title)
        self.not_logged_in_bottom_frame.pack(side=tk.RIGHT)

        # 一键登录
        self.one_key_auto_login = ttk.Button(self.not_logged_in_bottom_frame, text="一键登录", width=8,
                                             command=self.auto_login_selected_accounts, style='Custom.TButton')
        self.one_key_auto_login.pack(side=tk.RIGHT, pady=0)

        # 加载未登录列表
        for account in not_logged_in:
            self.add_account_row(self.not_logged_in_frame, account, False)

        # 更新顶部复选框状态
        self.update_top_title(False)

    def add_account_row(self, parent_frame, account, is_logged_in):
        """渲染账号所在行"""
        print(f"渲染{account}.........................................................")
        config_status = func_config.get_config_status_by_account(account, self.data_path)

        callbacks = {
            'detail': self.open_detail,
            'config': self.create_config,
            'login': self.auto_login_account
        }

        # 创建列表实例
        row = AccountRow(parent_frame, account, self.data_path, self.multiple_status, is_logged_in,
                         callbacks,
                         self.update_top_title)

        # 将已登录、未登录但已配置实例存入字典
        if is_logged_in:
            self.logged_in_rows[account] = row
        else:
            if config_status == "无配置":
                pass
            else:
                self.not_logged_in_rows[account] = row

    def toggle_top_checkbox(self, event, is_logged_in):
        """
        切换顶部复选框状态，更新子列表
        :param is_logged_in: 是否登录
        :param event: 点击复选框
        :return: 阻断继续切换
        """
        if is_logged_in:
            checkbox_var = self.logged_in_checkbox_var
            rows = self.logged_in_rows
            button = self.one_key_quit
            tip = "请选择要退出的账号"
        else:
            checkbox_var = self.not_logged_in_checkbox_var
            rows = self.not_logged_in_rows
            button = self.one_key_auto_login
            tip = "请选择要登录的账号"
        checkbox_var.set(not checkbox_var.get())
        value = checkbox_var.get()
        if value:
            widget_utils.enable_button_and_unbind_tip(self.tooltips, button)
        else:
            widget_utils.disable_button_and_add_tip(self.tooltips, button, tip)
        for row in rows.values():
            row.set_checkbox(value)
        return "break"

    def update_top_title(self, is_logged_in):
        """根据AccountRow实例的复选框状态更新顶行复选框状态"""
        # toggle方法
        toggle = partial(self.toggle_top_checkbox, is_logged_in=is_logged_in)

        # 判断是要更新哪一个顶行
        if is_logged_in:
            all_rows = list(self.logged_in_rows.values())
            checkbox = self.logged_in_checkbox
            title = self.logged_in_title
            checkbox_var = self.logged_in_checkbox_var
            button = self.one_key_quit
            tip = "请选择要退出的账号"
        else:
            all_rows = list(self.not_logged_in_rows.values())
            checkbox = self.not_logged_in_checkbox
            title = self.not_logged_in_title
            checkbox_var = self.not_logged_in_checkbox_var
            button = self.one_key_auto_login
            tip = "请选择要登录的账号"

        if len(all_rows) == 0:
            # 列表为空时解绑复选框相关事件，禁用复选框和按钮
            title.unbind("<Button-1>")
            for child in title.winfo_children():
                child.unbind("<Button-1>")
            checkbox.config(state="disabled")
            widget_utils.disable_button_and_add_tip(self.tooltips, button, tip)
        else:
            # 列表不为空则绑定和复用
            title.bind("<Button-1>", toggle, add="+")
            for child in title.winfo_children():
                child.bind("<Button-1>", toggle, add="+")
            checkbox.config(state="normal")

            # 从子列表的状态来更新顶部复选框
            states = [row.checkbox_var.get() for row in all_rows]
            if all(states):
                checkbox_var.set(1)
                widget_utils.enable_button_and_unbind_tip(self.tooltips, button)
            elif any(states):
                checkbox_var.set(-1)
                widget_utils.enable_button_and_unbind_tip(self.tooltips, button)
            else:
                checkbox_var.set(0)
                widget_utils.disable_button_and_add_tip(self.tooltips, button, tip)

    def open_detail(self, account):
        """打开详情窗口"""
        detail_window = tk.Toplevel(self.master)
        detail_ui.DetailWindow(detail_window, account, self.main_window.create_main_frame_and_menu)
        handle_utils.center_window(detail_window)
        detail_window.focus_set()

    def create_config(self, account, status):
        """按钮：创建或重新配置"""
        self.main_window.thread_manager.create_config_thread(
            account,
            func_config.test,
            status,
            self.main_window.create_main_frame_and_menu
        )

    def auto_login_account(self, account):
        """按钮：自动登录某个账号"""
        try:
            self.main_window.thread_manager.login_accounts_thread(
                func_login.auto_login_accounts,
                [account],
                self.multiple_status,
                self.main_window.create_main_frame_and_menu
            )

        finally:
            # 恢复刷新可用性
            self.main_window.edit_menu.entryconfig("刷新", state="normal")

    def quit_selected_accounts(self):
        """退出所选账号"""
        # messagebox.showinfo("待修复", "测试中发现重大bug，先不给点，略~")
        account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
        accounts = [
            account
            for account, row in self.logged_in_rows.items()
            if row.is_checked()
        ]
        quited_accounts = []
        for account in accounts:
            try:
                pid = account_data.get(account, {}).get("pid", None)
                nickname = account_data.get(account, {}).get("nickname", None)
                process = psutil.Process(pid)
                if process_utils.process_exists(pid) and process.name() == "WeChat.exe":
                    startupinfo = None
                    if sys.platform == 'win32':
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    result = subprocess.run(
                        ['taskkill', '/T', '/F', '/PID', f'{pid}'],
                        startupinfo=startupinfo,
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        print(f"结束了 {pid} 的进程树")
                        quited_accounts.append((nickname, pid))
                    else:
                        print(f"无法结束 PID {pid} 的进程树，错误：{result.stderr.strip()}")
                else:
                    print(f"进程 {pid} 已经不存在。")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        json_utils.save_json_data(Config.ACC_DATA_JSON_PATH, account_data)
        self.main_window.create_main_frame_and_menu()

    def auto_login_selected_accounts(self):
        """登录所选账号"""
        accounts = [
            account
            for account, row in self.not_logged_in_rows.items()
            if row.is_checked()
        ]
        self.master.iconify()  # 最小化主窗口
        try:
            self.main_window.thread_manager.login_accounts_thread(
                func_login.auto_login_accounts,
                accounts,
                self.multiple_status,
                self.main_window.create_main_frame_and_menu
            )

        finally:
            # 恢复刷新可用性
            self.main_window.edit_menu.entryconfig("刷新", state="normal")
