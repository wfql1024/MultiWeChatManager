import threading
import time
import tkinter as tk
from functools import partial
from tkinter import ttk

from PIL import ImageTk, Image

from functions import func_config, func_login, func_account, subfunc_file, subfunc_sw, func_setting
from resources import Constants
from ui import detail_ui
from utils import string_utils, widget_utils
from utils.logger_utils import mylogger as logger


class AccountRow:
    """
    为每一个账号创建其行布局的类
    """

    def __init__(self, root, m_class, parent_frame, account, data_path, config_status,
                 multiple_status, login_status, update_top_checkbox_callback, sw="WeChat"):
        self.chosen_tab = sw
        self.root = root
        self.m_class = m_class
        self.single_click_id = None
        self.data_path = data_path
        self.config_status = config_status
        self.multiple_status = multiple_status
        self.start_time = time.time()
        self.tooltips = {}
        self.toggle_avatar_label = None
        self.size = None
        self.update_top_checkbox_callback = update_top_checkbox_callback
        self.login_status = login_status
        # print(f"初始化用时{time.time() - self.start_time:.4f}秒")

        # 行框架=复选框+头像标签+账号标签+按钮区域+配置标签
        self.row_frame = ttk.Frame(parent_frame)
        self.row_frame.pack(fill=tk.X, pady=Constants.CLZ_ROW_FRM_PAD_Y)

        # 复选框
        self.checkbox_var = tk.BooleanVar(value=False)
        self.checkbox = tk.Checkbutton(self.row_frame, variable=self.checkbox_var)
        self.checkbox.pack(side=tk.LEFT)

        # 头像标签
        self.avatar_label = self.create_avatar_label(account)
        self.avatar_label.pack(side=tk.LEFT)
        self.avatar_label.bind("<Enter>", lambda event: event.widget.config(cursor="hand2"))
        self.avatar_label.bind("<Leave>", lambda event: event.widget.config(cursor=""))
        # print(f"加载头像区域用时{time.time() - self.start_time:.4f}秒")

        # 账号标签
        self.sign_visible: bool = func_setting.fetch_global_setting_or_set_default("sign_visible") == "True"
        wrapped_display_name = func_account.get_acc_wrapped_display_name(self.chosen_tab, account)
        has_mutex, = subfunc_file.get_acc_details_from_json_by_tab("WeChat", account, has_mutex=None)
        style = ttk.Style()
        style.configure("Mutex.TLabel", foreground="red")
        try:
            if has_mutex and self.sign_visible:
                self.account_label = ttk.Label(self.row_frame, text=wrapped_display_name, style="Mutex.TLabel")
            else:
                self.account_label = ttk.Label(self.row_frame, text=wrapped_display_name)
            self.account_label.pack(side=tk.LEFT, fill=tk.X, padx=Constants.CLZ_ROW_LBL_PAD_X)
        except Exception as e:
            logger.warning(e)
            # 清理 display_name
            cleaned_display_name = string_utils.clean_display_name(wrapped_display_name)
            if has_mutex and self.sign_visible:
                self.account_label = ttk.Label(self.row_frame, text=cleaned_display_name, style="Mutex.TLabel")
            else:
                self.account_label = ttk.Label(self.row_frame, text=cleaned_display_name)
            self.account_label.pack(side=tk.LEFT, fill=tk.X, padx=Constants.CLZ_ROW_LBL_PAD_X)

        # print(f"加载账号显示区域用时{time.time() - self.start_time:.4f}秒")

        # 按钮区域=配置或登录按钮
        self.button_frame = ttk.Frame(self.row_frame)
        self.button_frame.pack(side=tk.RIGHT)

        # 配置标签
        self.config_status_label = ttk.Label(self.row_frame, text=self.config_status, anchor='e')
        self.config_status_label.pack(side=tk.RIGHT, padx=Constants.CLZ_CFG_LBL_PAD_X,
                                      fill=tk.X, expand=True)

        # 登录/配置按钮
        if login_status == "login":
            # 配置按钮
            self.config_button_text = "重新配置" if self.config_status != "无配置" else "添加配置"
            self.config_button = ttk.Button(
                self.button_frame, text=self.config_button_text, style='Custom.TButton',
                command=partial(self.create_config, account, self.multiple_status)
            )
            self.config_button.pack(side=tk.RIGHT)
            self.row_frame.bind("<Button-1>", self.toggle_checkbox, add="+")
            for child in self.row_frame.winfo_children():
                child.bind("<Button-1>", self.toggle_checkbox, add="+")
        else:
            # 登录按钮
            self.login_button = ttk.Button(self.button_frame, text="自动登录", style='Custom.TButton',
                                           command=partial(self.auto_login_account, account))
            self.login_button.pack(side=tk.RIGHT)

            if self.config_status == "无配置":
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
        # print(f"加载配置/登录区域用时{time.time() - self.start_time:.4f}秒")

        # 头像绑定详情事件
        self.avatar_label.bind("<Button-1>", lambda event: self.on_single_click(account))
        self.avatar_label.bind("<Double-1>", lambda event: self.double_selection(account))

        print(f"加载{account}界面用时{time.time() - self.start_time:.4f}秒")

    def toggle_checkbox(self, _event):
        """
        切换复选框状态
        :param _event: 点击复选框
        :return: 阻断继续切换
        """
        self.checkbox_var.set(not self.checkbox_var.get())
        self.update_top_checkbox_callback(self.login_status)
        return "break"

    def create_avatar_label(self, account):
        """
        创建头像标签
        :param account: 原始微信号
        :return: 头像标签 -> Label
        """
        try:
            img = func_account.get_acc_avatar_from_files(account, self.chosen_tab)
            img = img.resize(Constants.AVT_SIZE)
            photo = ImageTk.PhotoImage(img)
            avatar_label = ttk.Label(self.row_frame, image=photo)

        except Exception as e:
            print(f"Error creating avatar label: {e}")
            # 如果加载失败，使用一个空白标签
            photo = ImageTk.PhotoImage(image=Image.new('RGB', Constants.BLANK_AVT_SIZE, color='white'))
            avatar_label = ttk.Label(self.row_frame, image=photo)
        avatar_label.image = photo  # 保持对图像的引用
        return avatar_label

    def on_single_click(self, account):
        """处理单击事件，并在检测到双击时取消"""
        # 取消之前的单击延时处理（如果有）
        if self.single_click_id:
            self.root.after_cancel(self.single_click_id)
        # 设置一个延时，若在此期间未检测到双击，则处理单击事件
        self.single_click_id = self.root.after(200, lambda: self.open_detail(account))

    def double_selection(self, account):
        if self.single_click_id:
            self.root.after_cancel(self.single_click_id)
            self.single_click_id = None
        subfunc_sw.switch_to_sw_account_wnd(self.chosen_tab, account, self.root)

    def open_detail(self, account):
        """打开详情窗口"""
        detail_window = tk.Toplevel(self.root)
        detail_ui.DetailWindow(self.root, self.root, detail_window, self.chosen_tab,
                               account, self.m_class.refresh_main_frame)

    def create_config(self, account, multiple_status):
        """按钮：创建或重新配置"""
        threading.Thread(target=func_config.test,
                         args=(self.m_class, account, multiple_status, self.chosen_tab)).start()

    def auto_login_account(self, account):
        """按钮：自动登录某个账号"""
        self.root.iconify()  # 最小化主窗口
        try:
            threading.Thread(
                target=func_login.auto_login_accounts,
                args=([account], self.multiple_status, self.m_class.refresh_main_frame, self.chosen_tab)
            ).start()
        except Exception as e:
            logger.error(e)


class ClassicRowUI:
    def __init__(self, root, m_class, m_main_frame, result, data_path, multiple_status, sw="WeChat"):
        self.chosen_tab = sw
        self.m_class = m_class
        self.data_path = data_path
        self.multiple_status = multiple_status
        self.logout_rows = {}
        self.login_rows = {}
        self.tooltips = {}
        self.root = root
        self.main_frame = m_main_frame
        self.login_rows.clear()
        self.logout_rows.clear()
        login, logout, wechat_processes, mutex = result

        if len(login) != 0:
            # 已登录框架=已登录标题+已登录列表
            self.login_frame = ttk.Frame(self.main_frame)
            self.login_frame.pack(side=tk.TOP, fill=tk.X,
                                  padx=Constants.LOG_IO_FRM_PAD_X, pady=Constants.LOG_IO_FRM_PAD_Y)

            # 已登录标题=已登录复选框+已登录标签+已登录按钮区域
            self.login_title = ttk.Frame(self.login_frame)
            self.login_title.pack(side=tk.TOP, fill=tk.X)

            # 已登录复选框
            self.login_checkbox_var = tk.IntVar(value=0)
            self.login_checkbox = tk.Checkbutton(
                self.login_title,
                variable=self.login_checkbox_var,
                tristatevalue=-1
            )
            self.login_checkbox.pack(side=tk.LEFT)

            # 已登录标签
            self.login_label = ttk.Label(self.login_title, text="已登录账号：",
                                         style='FirstTitle.TLabel')
            self.login_label.pack(side=tk.LEFT, fill=tk.X, anchor="w", pady=Constants.LOG_IO_LBL_PAD_Y)

            # 已登录按钮区域=一键退出
            self.login_btn_frame = ttk.Frame(self.login_title)
            self.login_btn_frame.pack(side=tk.RIGHT)

            # 一键退出
            self.one_key_quit = ttk.Button(self.login_btn_frame, text="一键退出",
                                           command=self.one_click_to_quit, style='Custom.TButton')
            self.one_key_quit.pack(side=tk.RIGHT)

            # 加载已登录列表
            for account in login:
                self.add_account_row(self.login_frame, account, "login")

            self.update_top_title("login")

        if len(logout) != 0:
            # 未登录框架=未登录标题+未登录列表
            self.logout_frame = ttk.Frame(self.main_frame)
            self.logout_frame.pack(side=tk.TOP, fill=tk.X, pady=Constants.LOG_IO_FRM_PAD_Y,
                                   padx=Constants.LOG_IO_FRM_PAD_X)

            # 未登录标题=未登录复选框+未登录标签+未登录按钮区域
            self.logout_title = ttk.Frame(self.logout_frame)
            self.logout_title.pack(side=tk.TOP, fill=tk.X)

            # 未登录复选框
            self.logout_checkbox_var = tk.IntVar(value=0)
            self.logout_checkbox = tk.Checkbutton(
                self.logout_title,
                variable=self.logout_checkbox_var,
                tristatevalue=-1
            )
            self.logout_checkbox.pack(side=tk.LEFT)

            # 未登录标签
            self.logout_label = ttk.Label(self.logout_title, text="未登录账号：",
                                          style='FirstTitle.TLabel')
            self.logout_label.pack(side=tk.LEFT, fill=tk.X, anchor="w", pady=Constants.LOG_IO_LBL_PAD_Y)

            # 未登录按钮区域=一键登录
            self.logout_bottom_frame = ttk.Frame(self.logout_title)
            self.logout_bottom_frame.pack(side=tk.RIGHT)

            # 一键登录
            self.one_key_auto_login = ttk.Button(self.logout_bottom_frame, text="一键登录",
                                                 command=self.auto_login_selected_accounts, style='Custom.TButton')
            self.one_key_auto_login.pack(side=tk.RIGHT)

            # 加载未登录列表
            for account in logout:
                self.add_account_row(self.logout_frame, account, "logout")

            # 更新顶部复选框状态
            self.update_top_title("logout")

    def add_account_row(self, parent_frame, account, login_status):
        """渲染账号所在行"""
        print(f"渲染{account}.........................................................")
        config_status = func_config.get_config_status_by_account(account, self.data_path, self.chosen_tab)

        # 创建列表实例
        row = AccountRow(self.root, self.m_class, parent_frame, account, self.data_path, config_status,
                         self.multiple_status, login_status, self.update_top_title, self.chosen_tab)

        # 将已登录、未登录但已配置实例存入字典
        if login_status == "login":
            self.login_rows[account] = row
        elif login_status == "logout":
            if config_status == "无配置":
                pass
            else:
                self.logout_rows[account] = row

    def toggle_top_checkbox(self, _event, login_status):
        """
        切换顶部复选框状态，更新子列表
        :param login_status: 是否登录
        :param _event: 点击复选框
        :return: 阻断继续切换
        """
        if login_status == "login":
            checkbox_var = self.login_checkbox_var
            rows = self.login_rows
            button = self.one_key_quit
            tip = "请选择要退出的账号"
        else:
            checkbox_var = self.logout_checkbox_var
            rows = self.logout_rows
            button = self.one_key_auto_login
            tip = "请选择要登录的账号"
        checkbox_var.set(not checkbox_var.get())
        value = checkbox_var.get()
        if value:
            widget_utils.enable_button_and_unbind_tip(self.tooltips, button)
        else:
            widget_utils.disable_button_and_add_tip(self.tooltips, button, tip)
        for row in rows.values():
            row.checkbox_var.set(value)
        return "break"

    def update_top_title(self, login_status):
        """根据AccountRow实例的复选框状态更新顶行复选框状态"""
        # toggle方法
        toggle = partial(self.toggle_top_checkbox, login_status=login_status)

        # 判断是要更新哪一个顶行
        if login_status == "login":
            all_rows = list(self.login_rows.values())
            checkbox = self.login_checkbox
            title = self.login_title
            checkbox_var = self.login_checkbox_var
            button = self.one_key_quit
            tip = "请选择要退出的账号"
        else:
            all_rows = list(self.logout_rows.values())
            checkbox = self.logout_checkbox
            title = self.logout_title
            checkbox_var = self.logout_checkbox_var
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

    def one_click_to_quit(self):
        """退出所选账号"""
        accounts = [
            account
            for account, row in self.login_rows.items() if row.checkbox_var.get()
        ]
        try:
            func_account.to_quit_selected_accounts(self.chosen_tab, accounts, self.m_class.refresh_main_frame)
        except Exception as e:
            logger.error(e)

    def auto_login_selected_accounts(self):
        """登录所选账号"""
        accounts = [account for account, row in self.logout_rows.items() if row.checkbox_var.get()]
        self.root.iconify()  # 最小化主窗口
        try:
            threading.Thread(
                target=func_login.auto_login_accounts,
                args=(accounts, self.multiple_status, self.m_class.refresh_main_frame, self.chosen_tab)
            ).start()
        except Exception as e:
            logger.error(e)
