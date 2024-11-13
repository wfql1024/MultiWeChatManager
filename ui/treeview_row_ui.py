import threading

from PIL import ImageTk, Image
from utils import widget_utils, string_utils
import tkinter as tk
from functools import partial
from tkinter import ttk, messagebox

from functions import func_config, func_login, func_account, subfunc_file
from ui import detail_ui
from utils import handle_utils
from utils.logger_utils import mylogger as logger


def try_convert(value):
    try:
        return float(value)
    except ValueError:
        return value


class TreeviewRowUI:
    def __init__(self, main_window, m_master, m_main_frame, result, data_path, multiple_status):
        self.acc_index = None
        self.hovered_item = None
        self.single_click_id = None
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
        self.tooltips = {}
        self.master = m_master
        self.main_frame = m_main_frame
        self.sort_order = {"logged_in": True, "not_logged_in": True}  # 控制排序顺序
        logged_in_list, not_logged_in_list, wechat_processes = result
        # 调整行高
        style = ttk.Style()
        style.configure("RowTreeview", background="#FFFFFF", foreground="black", rowheight=50,
                        selectmode="none", borderwidth=20)
        style.layout("RowTreeview", style.layout("Treeview"))  # 继承默认布局

        if len(logged_in_list) != 0:
            # 已登录框架=已登录标题+已登录列表
            self.logged_in_frame = ttk.Frame(self.main_frame)
            self.logged_in_frame.pack(side=tk.TOP, fill=tk.X, pady=5, padx=(10, 0))

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
            # 配置
            self.config_btn = ttk.Button(self.logged_in_button_frame, text="❐配 置", width=8, style='Custom.TButton',
                                         command=partial(self.create_config, multiple_status=self.multiple_status)
                                         )
            self.config_btn.pack(side=tk.RIGHT, pady=0)
            widget_utils.disable_button_and_add_tip(
                self.tooltips, self.config_btn, "请选择一个账号进行配置，配置前有螺丝符号表示推荐配置的账号")

            self.logged_in_tree = self.create_table("logged_in")
            self.display_table(logged_in_list, "logged_in")
            self.update_top_title("logged_in")
            self.logged_in_tree.bind("<Leave>", partial(self.on_leave))
            self.logged_in_tree.bind("<Motion>", partial(self.on_mouse_motion))
            self.logged_in_tree.bind("<Button-1>", partial(self.on_single_click, is_logged_in="logged_in"))
            self.logged_in_tree.bind("<Double-1>", partial(self.double_selection, is_logged_in="logged_in"))
            self.logged_in_tree.bind("<Configure>", self.adjust_columns_on_maximize)

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
        self.not_logged_in_tree = self.create_table("not_logged_in")
        self.display_table(not_logged_in_list, "not_logged_in")
        self.update_top_title("not_logged_in")
        self.not_logged_in_tree.bind("<Leave>", partial(self.on_leave))
        self.not_logged_in_tree.bind("<Motion>", partial(self.on_mouse_motion))
        self.not_logged_in_tree.bind("<Button-1>", partial(self.on_single_click, is_logged_in="not_logged_in"))
        self.not_logged_in_tree.bind("<Double-1>", partial(self.double_selection, is_logged_in="not_logged_in"))
        self.not_logged_in_tree.bind("<Configure>", self.adjust_columns_on_maximize)

    def create_table(self, table_type):
        """定义表格，根据表格类型选择手动或自动登录表格"""
        columns = (" ", "配置", "pid", "原始微信号", "当前微信号", "昵称")
        self.acc_index = columns.index("原始微信号")
        tree = ttk.Treeview(self.main_frame, columns=columns, show='tree', height=1, style="RowTreeview")

        # 设置列标题和排序功能
        for col in columns:
            tree.heading(
                col, text=col,
                command=lambda c=col: self.sort_column(tree, c, table_type)
            )
            tree.column(col, anchor='center')  # 设置列宽

        # 特定列的宽度和样式设置
        tree.column("#0", minwidth=64, width=64, stretch=tk.NO)
        tree.column("pid", minwidth=80, width=80, anchor='e', stretch=tk.NO)
        tree.column("配置", minwidth=144, width=144, anchor='center', stretch=tk.NO)
        tree.column(" ", minwidth=140, width=10, anchor='w')
        tree.column("原始微信号", anchor='center')
        tree.column("当前微信号", anchor='center')

        tree.pack(fill=tk.X, expand=True, padx=(10, 0), pady=(0, 10))

        selected_bg = "#B2E0F7"
        hover_bg = "#E5F5FD"

        # 设置标签样式
        tree.tag_configure("disabled", background="#F5F7FA", foreground="grey")
        tree.tag_configure("selected", background=selected_bg, foreground="black")
        tree.tag_configure("hover", background=hover_bg, foreground="black")

        return tree

    def display_table(self, accounts, is_logged_in):
        if is_logged_in == "logged_in":
            tree = self.logged_in_tree
        elif is_logged_in == "not_logged_in":
            tree = self.not_logged_in_tree
        else:
            tree = ttk.Treeview(self.main_frame, show='tree', height=1, style="RowTreeview")
        for account in accounts:
            display_name = " " + func_account.get_acc_origin_display_name(account)
            config_status = func_config.get_config_status_by_account(account, self.data_path)
            avatar_url, alias, nickname, pid, has_mutex = subfunc_file.get_acc_details_from_acc_json(
                account,
                avatar_url=None,
                alias="请获取数据",
                nickname="请获取数据",
                pid=None,
                has_mutex=None
            )

            img = func_account.get_acc_avatar_from_files(account)
            img = img.resize((44, 44), Image.Resampling.NEAREST)
            photo = ImageTk.PhotoImage(img)

            self.photo_images.append(photo)

            pid = "⚔" + str(pid) + " " if has_mutex else "" + str(pid) + " "

            try:
                tree.insert("", "end", iid=account, image=photo,
                            values=(display_name, config_status, pid, account, alias, nickname))
            except Exception as ec:
                logger.warning(ec)
                cleaned_display_name = string_utils.clean_display_name(display_name)
                cleaned_nickname = string_utils.clean_display_name(nickname)
                tree.insert("", "end", iid=account, image=photo,
                            values=(cleaned_display_name, config_status,
                                    pid, account, alias, cleaned_nickname))

            if config_status == "无配置" and is_logged_in == "not_logged_in":
                widget_utils.add_a_tag_to_item(self.not_logged_in_tree, account, "disabled")

        tree.config(height=len(accounts))

    def adjust_columns_on_maximize(self, event=None):
        columns_to_hide = ["原始微信号", "当前微信号", "昵称"]
        tree = event.widget
        # print(event.widget)
        if self.master.state() != "zoomed":  # 非最大化时隐藏列和标题
            tree["show"] = "tree"  # 隐藏标题
            for col in columns_to_hide:
                tree.column(col, width=0, stretch=False)
        else:  # 最大化时显示列和标题
            width = int(self.master.winfo_screenwidth() / 5)
            tree["show"] = "tree headings"  # 显示标题
            for col in columns_to_hide:
                tree.column(col, width=width)  # 设置合适的宽度

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

    def update_selected_display(self, is_logged_in):
        # 获取选中行的“英语”列数据
        if is_logged_in == "logged_in":
            tree = self.logged_in_tree
            selected_items = self.selected_logged_in_items
            selected_accounts = [tree.item(item, "values")[self.acc_index] for item in selected_items]
            self.selected_logged_in_accounts = selected_accounts
            if len(selected_accounts) == 1:
                widget_utils.enable_button_and_unbind_tip(
                    self.tooltips, self.config_btn)
            else:
                widget_utils.disable_button_and_add_tip(
                    self.tooltips, self.config_btn, "请选择一个账号进行配置，配置前有螺丝符号表示推荐配置的账号")
        else:
            tree = self.not_logged_in_tree
            selected_items = self.selected_not_logged_in_items
            selected_accounts = [tree.item(item, "values")[self.acc_index] for item in selected_items]
            self.selected_not_logged_in_accounts = selected_accounts
        print(is_logged_in, selected_accounts)

    def toggle_top_checkbox(self, event, is_logged_in):
        """
        切换顶部复选框状态，更新子列表
        :param is_logged_in: 是否登录
        :param event: 点击复选框
        :return: 阻断继续切换
        """
        print(event.widget)
        print(self.logged_in_checkbox)
        if is_logged_in == "logged_in":
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
            widget_utils.enable_button_and_unbind_tip(self.tooltips, button)
            # 执行全选
            for item_id in tree.get_children():
                # print(tree.item(item_id, "tags"))
                if "disabled" not in tree.item(item_id, "tags"):  # 只选择允许选中的行
                    selected_items.append(item_id)
                    widget_utils.add_a_tag_to_item(tree, item_id, "selected")
        else:
            widget_utils.disable_button_and_add_tip(self.tooltips, button, tip)
            # 取消所有选择
            selected_items.clear()
            for item_id in tree.get_children():
                if "disabled" not in tree.item(item_id, "tags"):
                    widget_utils.remove_a_tag_of_item(tree, item_id, "selected")
        self.update_selected_display(is_logged_in)  # 更新显示
        return "break"

    def update_top_title(self, is_logged_in):
        """根据AccountRow实例的复选框状态更新顶行复选框状态"""
        # toggle方法
        toggle = partial(self.toggle_top_checkbox, is_logged_in=is_logged_in)

        # 判断是要更新哪一个顶行
        if is_logged_in == "logged_in":
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
            widget_utils.disable_button_and_add_tip(self.tooltips, button, tip)
        else:
            # 列表不为空则绑定和复用
            title.bind("<Button-1>", toggle, add="+")
            for child in title.winfo_children():
                child.bind("<Button-1>", toggle, add="+")
            checkbox.config(state="normal")

            # 从子列表的状态来更新顶部复选框
            if len(selected_rows) == len(all_rows):
                checkbox_var.set(1)
                widget_utils.enable_button_and_unbind_tip(self.tooltips, button)
            elif 0 < len(selected_rows) < len(all_rows):
                checkbox_var.set(-1)
                widget_utils.enable_button_and_unbind_tip(self.tooltips, button)
            else:
                checkbox_var.set(0)
                widget_utils.disable_button_and_add_tip(self.tooltips, button, tip)

    def on_leave(self, event):
        if self.hovered_item is not None:
            widget_utils.remove_a_tag_of_item(self.hovered_item[0], self.hovered_item[1], "hover")
            self.hovered_item = None

    def on_mouse_motion(self, event):
        tree = event.widget

        # 获取当前鼠标所在的行 ID
        item = tree.identify_row(event.y)

        # 检查是否是新的悬停行
        if self.hovered_item is not None:
            if self.hovered_item[0] != tree or self.hovered_item[1] != item:
                widget_utils.remove_a_tag_of_item(tree, self.hovered_item[1], "hover")
                widget_utils.add_a_tag_to_item(tree, item, "hover")
                # 更新当前悬停行
                self.hovered_item = (tree, item)
        else:
            widget_utils.add_a_tag_to_item(tree, item, "hover")
            # 更新当前悬停行
            self.hovered_item = (tree, item)

    def on_single_click(self, event, is_logged_in):
        """处理单击事件，并在检测到双击时取消"""
        # 取消之前的单击延时处理（如果有）
        if self.single_click_id:
            self.master.after_cancel(self.single_click_id)
        # 设置一个延时，若在此期间未检测到双击，则处理单击事件
        self.single_click_id = self.master.after(200, lambda: self.toggle_selection(event, is_logged_in))

    def toggle_selection(self, event, is_logged_in):
        print("进入了单击判定")
        if is_logged_in == "logged_in":
            tree = self.logged_in_tree
            selected_items = self.selected_logged_in_items
        elif is_logged_in == "not_logged_in":
            tree = self.not_logged_in_tree
            selected_items = self.selected_not_logged_in_items
        else:
            tree = None
            selected_items = []
        item_id = tree.identify_row(event.y)
        if len(item_id) == 0:
            return
        if tree.identify_column(event.x) == "#0":  # 检查是否点击了图片列
            # print("测试", len(tree.identify_row(event.y)))
            # 弹出提示窗口
            self.open_detail(tree.item(item_id, "values")[self.acc_index])
        else:
            if item_id and "disabled" not in tree.item(item_id, "tags"):  # 确保不可选的行不触发
                if item_id in selected_items:
                    selected_items.remove(item_id)
                    widget_utils.remove_a_tag_of_item(tree, item_id, "selected")
                else:
                    selected_items.append(item_id)
                    widget_utils.add_a_tag_to_item(tree, item_id, "selected")
                self.update_selected_display(is_logged_in)  # 实时更新选中行显示
                self.update_top_title(is_logged_in)

    def double_selection(self, event, is_logged_in):
        if self.single_click_id:
            self.master.after_cancel(self.single_click_id)
            self.single_click_id = None
        print("进入了双击判定")
        if is_logged_in == "logged_in":
            tree = self.logged_in_tree
            selected_items = self.selected_logged_in_items
            callback = self.quit_selected_accounts
        elif is_logged_in == "not_logged_in":
            tree = self.not_logged_in_tree
            selected_items = self.selected_not_logged_in_items
            callback = self.auto_login_selected_acc
        else:
            tree = event.widget
            selected_items = []
            callback = None
        item_id = tree.identify_row(event.y)
        if len(item_id) == 0:
            return
        if tree.identify_column(event.x) == "#0":  # 检查是否点击了图片列
            # print("测试", len(tree.identify_row(event.y)))
            # 弹出提示窗口
            self.open_detail(tree.item(item_id, "values")[self.acc_index])
        else:
            if item_id and "disabled" not in tree.item(item_id, "tags"):  # 确保不可选的行不触发
                selected_items.clear()
                for i in tree.get_children():
                    widget_utils.remove_a_tag_of_item(tree, i, "selected")
                selected_items.append(item_id)
                widget_utils.add_a_tag_to_item(tree, item_id, "selected")
                self.update_selected_display(is_logged_in)  # 实时更新选中行显示
                self.update_top_title(is_logged_in)
                callback()

    def open_detail(self, account):
        """打开详情窗口"""
        detail_window = tk.Toplevel(self.master)
        detail_ui.DetailWindow(detail_window, account, self.main_window.create_main_frame_and_menu)
        handle_utils.center_window(detail_window)

    def create_config(self, multiple_status):
        """按钮：创建或重新配置"""
        accounts = self.selected_logged_in_items
        self.main_window.thread_manager.create_config_thread(
            accounts[0],
            func_config.test,
            multiple_status,
            self.main_window.create_main_frame_and_menu
        )

    def quit_selected_accounts(self):
        """退出所选账号"""
        # messagebox.showinfo("待修复", "测试中发现重大bug，先不给点，略~")
        accounts = self.selected_logged_in_items
        accounts_to_quit = []
        for account in accounts:
            pid, = subfunc_file.get_acc_details_from_acc_json(account, pid=None)
            display_name = func_account.get_acc_origin_display_name(account)
            cleaned_display_name = string_utils.clean_display_name(display_name)
            accounts_to_quit.append(f"[{pid}: {cleaned_display_name}]")
        accounts_to_quit_str = "\n".join(accounts_to_quit)
        if messagebox.askokcancel("提示",
                                  f"确认退登：\n{accounts_to_quit_str}？"):
            try:
                quited_accounts = func_account.quit_accounts(accounts)
                quited_accounts_str = "\n".join(quited_accounts)
                messagebox.showinfo("提示", f"已退登：\n{quited_accounts_str}")
                self.main_window.create_main_frame_and_menu()
            except Exception as e:
                logger.error(e)

    def auto_login_selected_accounts(self):
        """登录所选账号"""
        accounts = self.selected_not_logged_in_items
        self.master.iconify()  # 最小化主窗口
        try:
            threading.Thread(
                target=func_login.auto_login_accounts,
                args=(accounts, self.multiple_status, self.main_window.create_main_frame_and_menu)
            ).start()
        except Exception as e:
            logger.error(e)

    def auto_login_selected_acc(self):
        """登录所选账号"""
        accounts = self.selected_not_logged_in_items
        try:
            threading.Thread(
                target=func_login.auto_login_accounts,
                args=(accounts, self.multiple_status, self.main_window.create_main_frame_and_menu)
            ).start()
        except Exception as e:
            logger.error(e)
