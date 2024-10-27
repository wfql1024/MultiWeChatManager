from PIL import ImageTk, Image
from utils import string_utils
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


def try_convert(value):
    try:
        return float(value)
    except ValueError:
        return value


class TreeviewRowUI:
    def __init__(self, main_window, m_master, m_main_frame, result, data_path, multiple_status):
        self.photo_images = []
        self.selected_not_logged_in_accounts = None
        self.selected_logged_in_accounts = None
        self.not_logged_in_tree = None
        self.logged_in_tree = None
        self.selected_not_logged_in_items = []
        self.selected_logged_in_items = []
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
        self.sort_order = {"logged_in": True, "not_logged_in": True}  # 控制排序顺序
        logged_in, not_logged_in, wechat_processes = result
        # 调整行高
        style = ttk.Style()
        style.configure("RowTreeview", background="#FFFFFF", foreground="black", rowheight=50,
                        selectmode="none", borderwidth=20)
        style.layout("RowTreeview", style.layout("Treeview"))  # 继承默认布局

        if len(logged_in) != 0:
            # 已登录框架=已登录标题+已登录列表
            self.logged_in_frame = ttk.Frame(self.main_frame)
            self.logged_in_frame.pack(side=tk.TOP, fill=tk.X, pady=5, padx=10)

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

            self.create_logged_in_table()
            self.display_logged_in_table(logged_in)

        # 未登录框架=未登录标题+未登录列表
        self.not_logged_in_frame = ttk.Frame(self.main_frame)
        self.not_logged_in_frame.pack(side=tk.TOP, fill=tk.X, pady=5, padx=10)

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

        # 更新顶部复选框状态
        self.create_not_logged_in_table()
        self.display_not_logged_in_table(not_logged_in)

    def disable_button_and_add_tip(self, button, text):
        """
        禁用按钮，启用提示
        :return: None
        """
        button.state(['disabled'])
        if button not in self.tooltips:
            self.tooltips[button] = handle_utils.Tooltip(button, text)

    def enable_button_and_unbind_tip(self, button):
        """
        启用按钮，去除提示
        :return: None
        """
        button.state(['!disabled'])
        if button in self.tooltips:
            self.tooltips[button].widget.unbind("<Enter>")
            self.tooltips[button].widget.unbind("<Leave>")
            del self.tooltips[button]

    def toggle_top_checkbox(self, event, is_logged_in):
        """
        切换顶部复选框状态，更新子列表
        :param is_logged_in: 是否登录
        :param event: 点击复选框
        :return: 阻断继续切换
        """
        if is_logged_in:
            checkbox_var = self.logged_in_checkbox_var
            tree = self.logged_in_tree
            selected_items = self.selected_logged_in_items
            button = self.one_key_quit
            tip = "请选择要退出的账号"
        else:
            checkbox_var = self.not_logged_in_checkbox_var
            tree = self.not_logged_in_tree
            selected_items = self.selected_not_logged_in_items
            button = self.one_key_auto_login
            tip = "请选择要登录的账号"
        checkbox_var.set(not checkbox_var.get())
        value = checkbox_var.get()
        if value:
            self.enable_button_and_unbind_tip(button)
            # 执行全选
            for item_id in tree.get_children():
                print(tree.item(item_id, "tags"))
                if "disabled" not in tree.item(item_id, "tags"):  # 只选择允许选中的行
                    selected_items.append(item_id)
                    # 添加“selected”标签
                    current_tags = tree.item(item_id, "tags")
                    if isinstance(current_tags, str) and current_tags == "":
                        current_tags = ()  # 将空字符串转换为元组
                    new_tags = current_tags + ("selected",)  # 添加“selected”
                    tree.item(item_id, tags=new_tags)
        else:
            self.disable_button_and_add_tip(button, tip)
            # 取消所有选择
            selected_items.clear()
            for item_id in tree.get_children():
                if "disabled" not in tree.item(item_id, "tags"):
                    # 移除“selected”标签
                    current_tags = tree.item(item_id, "tags")
                    if isinstance(current_tags, str) and current_tags == "":
                        current_tags = ()  # 将空字符串转换为元组
                    current_tags = tuple(tag for tag in current_tags if tag != "selected")  # 移除“selected”
                    tree.item(item_id, tags=current_tags)
        self.update_selected_display(is_logged_in)  # 更新显示
        return "break"

    def update_top_title(self, is_logged_in):
        """根据AccountRow实例的复选框状态更新顶行复选框状态"""
        # toggle方法
        toggle = partial(self.toggle_top_checkbox, is_logged_in=is_logged_in)

        # 判断是要更新哪一个顶行
        if is_logged_in:
            all_rows = [item for item in self.logged_in_tree.get_children()
                        if "disabled" not in self.logged_in_tree.item(item, "tags")]
            selected_rows = self.selected_logged_in_items
            checkbox = self.logged_in_checkbox
            title = self.logged_in_title
            checkbox_var = self.logged_in_checkbox_var
            button = self.one_key_quit
            tip = "请选择要退出的账号"
        else:
            all_rows = [item for item in self.not_logged_in_tree.get_children()
                        if "disabled" not in self.not_logged_in_tree.item(item, "tags")]
            # print("测试：", all_rows)
            selected_rows = self.selected_not_logged_in_items
            checkbox = self.not_logged_in_checkbox
            title = self.not_logged_in_title
            checkbox_var = self.not_logged_in_checkbox_var
            button = self.one_key_auto_login
            tip = "请选择要登录的账号"

        if len(all_rows) == 0 or all_rows is None:
            # 列表为空时解绑复选框相关事件，禁用复选框和按钮
            title.unbind("<Button-1>")
            for child in title.winfo_children():
                child.unbind("<Button-1>")
            checkbox.config(state="disabled")
            self.disable_button_and_add_tip(button, tip)
        else:
            # 列表不为空则绑定和复用
            title.bind("<Button-1>", toggle, add="+")
            for child in title.winfo_children():
                child.bind("<Button-1>", toggle, add="+")
            checkbox.config(state="normal")

            # 从子列表的状态来更新顶部复选框
            if len(selected_rows) == len(all_rows):
                checkbox_var.set(1)
                self.enable_button_and_unbind_tip(button)
            elif 0 < len(selected_rows) < len(all_rows):
                checkbox_var.set(-1)
                self.enable_button_and_unbind_tip(button)
            else:
                checkbox_var.set(0)
                self.disable_button_and_add_tip(button, tip)

    def open_detail(self, account):
        """打开详情窗口"""
        detail_window = tk.Toplevel(self.master)
        detail_ui.DetailWindow(detail_window, account, self.main_window.create_main_frame_and_menu)
        handle_utils.center_window(detail_window)

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
        accounts = self.selected_logged_in_accounts
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
        accounts = self.selected_not_logged_in_accounts
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

    def create_logged_in_table(self):
        """定义手动登录表格"""
        columns = (" ", "原始微信号", "当前微信号", "昵称", "配置", "pid")
        self.logged_in_tree = ttk.Treeview(self.main_frame,
                                           columns=columns,
                                           show='tree', height=1, style="RowTreeview")
        for col in columns:
            self.logged_in_tree.heading(
                col, text=col,
                command=lambda c=col: self.sort_column(self.logged_in_tree, c, "logged_in")
            )
            self.logged_in_tree.column(col, anchor='center')  # 设置列宽

        self.logged_in_tree.column("#0", minwidth=70, width=70, anchor='w', stretch=tk.NO)
        self.logged_in_tree.column("pid", minwidth=80, width=80, anchor='center', stretch=tk.NO)
        self.logged_in_tree.column("配置", minwidth=140, width=140, anchor='center', stretch=tk.NO)
        self.logged_in_tree.column(" ", minwidth=140, anchor='w')
        self.logged_in_tree.column("原始微信号", anchor='center')
        self.logged_in_tree.column("当前微信号", anchor='center')

        self.logged_in_tree.pack(fill=tk.X, expand=True, padx=(10, 0), pady=(0, 10))

        # 设置不可选行的灰色背景
        self.logged_in_tree.tag_configure("disabled", background="#F5F7FA", foreground="grey")
        # 设置选中行的蓝色背景
        self.logged_in_tree.tag_configure("selected", background="lightblue", foreground="black")

    def create_not_logged_in_table(self):
        """定义自动登录表格"""
        columns = (" ", "原始微信号", "当前微信号", "昵称", "配置", "pid")
        self.not_logged_in_tree = ttk.Treeview(self.main_frame,
                                               columns=columns,
                                               show='tree headings', height=1, style="RowTreeview")
        for col in columns:
            self.not_logged_in_tree.heading(
                col, text=col,
                command=lambda c=col: self.sort_column(self.not_logged_in_tree, c, "not_logged_in")
            )
            self.not_logged_in_tree.column(col, anchor='center' if col == "模式" else 'w', width=100)  # 设置列宽

        self.not_logged_in_tree.pack(fill=tk.X, expand=True, padx=(10, 0), pady=(0, 10))

        # 设置不可选行的灰色背景
        self.not_logged_in_tree.tag_configure("disabled", background="#F5F7FA", foreground="grey")
        # 设置选中行的蓝色背景
        self.not_logged_in_tree.tag_configure("selected", background="lightblue", foreground="black")

    def display_logged_in_table(self, accounts):
        for account in accounts:
            display_name = func_account.get_account_display_name(account)
            config_status = func_config.get_config_status_by_account(account, self.data_path)
            avatar_url, alias, nickname, pid = subfunc_file.get_acc_details_from_acc_json(
                account,
                avatar_url=None,
                alias="请获取数据",
                nickname="请获取数据",
                pid=None
            )

            img = func_account.get_acc_avatar_from_files(account)
            img = img.resize((44, 44), Image.Resampling.NEAREST)
            photo = ImageTk.PhotoImage(img)

            self.photo_images.append(photo)

            self.logged_in_tree.insert("", "end", iid=account, image=photo,
                                       values=(display_name, account, alias, nickname, config_status, pid))

        self.logged_in_tree.config(height=len(accounts))
        self.update_top_title(True)
        self.logged_in_tree.bind("<Button-1>", partial(self.toggle_selection, is_logged_in=True))

    def display_not_logged_in_table(self, accounts):
        for account in accounts:
            display_name = func_account.get_account_display_name(account)
            config_status = func_config.get_config_status_by_account(account, self.data_path)
            alias, nickname, pid = subfunc_file.get_acc_details_from_acc_json(
                account,
                alias="请获取数据",
                nickname="请获取数据",
                pid=None
            )

            img = func_account.get_acc_avatar_from_files(account)
            img = img.resize((44, 44), Image.Resampling.NEAREST)
            photo = ImageTk.PhotoImage(img)

            self.photo_images.append(photo)
            
            self.not_logged_in_tree.insert("", "end", iid=account, image=photo,
                                           values=(display_name, account, alias, nickname, config_status, pid))

            if config_status == "无配置":
                current_tags = self.not_logged_in_tree.item(account, "tags")
                if isinstance(current_tags, str) and current_tags == "":
                    current_tags = ()  # 将空字符串转换为元组
                new_tags = current_tags + ("disabled",)  # 添加“disabled”
                self.not_logged_in_tree.item(account, tags=new_tags)

        self.not_logged_in_tree.config(height=len(accounts))
        self.update_top_title(False)
        self.not_logged_in_tree.bind("<Button-1>", partial(self.toggle_selection, is_logged_in=False))

    def sort_column(self, tree, col, table_type):
        # 获取当前表格数据的 values、text、image 和 tags
        items = [
            (tree.item(i)["values"], tree.item(i)["text"], tree.item(i)["image"], tree.item(i)["tags"])
            for i in tree.get_children()
        ]

        # 获取排序顺序
        is_ascending = self.sort_order[table_type]

        # 按列排序
        items.sort(
            key=lambda x: (try_convert(x[0][list(tree["columns"]).index(col)]) if col not in ["模式"] else x[0][
                list(tree["columns"]).index(col)]),
            reverse=not is_ascending
        )

        # 清空表格并重新插入排序后的数据，保留 values、text、image 和 tags 信息
        for i in tree.get_children():
            tree.delete(i)
        for item in items:
            tree.insert("", "end", text=item[1], image=item[2], values=item[0],
                        tags=item[3])  # 保留 #0 列的 text、image 和 tags 信息

        # 根据排序后的行数调整 Treeview 的高度
        tree.configure(height=len(items))

        # 切换排序顺序
        self.sort_order[table_type] = not is_ascending

    def toggle_selection(self, event, is_logged_in):
        if is_logged_in is True:
            tree = self.logged_in_tree
            selected_items = self.selected_logged_in_items
        else:
            tree = self.not_logged_in_tree
            selected_items = self.selected_not_logged_in_items
        item_id = tree.identify_row(event.y)
        if len(item_id) == 0:
            return
        if tree.identify_column(event.x) == "#0":  # 检查是否点击了图片列
            print("测试", len(tree.identify_row(event.y)))
            # 弹出提示窗口
            self.open_detail(item_id)
        else:
            if item_id and "disabled" not in tree.item(item_id, "tags"):  # 确保不可选的行不触发
                if item_id in selected_items:
                    selected_items.remove(item_id)
                    # 移除“selected”标签
                    current_tags = tree.item(item_id, "tags")
                    if isinstance(current_tags, str) and current_tags == "":
                        current_tags = ()  # 将空字符串转换为元组
                    new_tags = tuple(tag for tag in current_tags if tag != "selected")  # 移除“selected”
                    tree.item(item_id, tags=list(new_tags))
                    print(current_tags, new_tags, tree.item(item_id, "tags"))
                else:
                    selected_items.append(item_id)
                    # 添加“selected”标签
                    current_tags = tree.item(item_id, "tags")
                    if isinstance(current_tags, str) and current_tags == "":
                        current_tags = ()  # 将空字符串转换为元组
                    new_tags = current_tags + ("selected",)  # 添加“selected”
                    tree.item(item_id, tags=list(new_tags))
                    print(current_tags, new_tags, tree.item(item_id, "tags"))
                self.update_selected_display(is_logged_in)  # 实时更新选中行显示
                self.update_top_title(is_logged_in)

    def update_selected_display(self, is_logged_in):
        # 获取选中行的“英语”列数据
        if is_logged_in is True:
            tree = self.logged_in_tree
            selected_items = self.selected_logged_in_items
            selected_accounts = [tree.item(item, "values")[1] for item in selected_items]
            self.selected_logged_in_accounts = selected_accounts
        else:
            tree = self.not_logged_in_tree
            selected_items = self.selected_not_logged_in_items
            selected_accounts = [tree.item(item, "values")[1] for item in selected_items]
            self.selected_not_logged_in_accounts = selected_accounts
        print(selected_accounts)
