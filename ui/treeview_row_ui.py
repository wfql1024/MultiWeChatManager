import threading
import tkinter as tk
from functools import partial
from tkinter import ttk, messagebox

from PIL import ImageTk, Image

from functions import func_config, func_login, func_account, subfunc_file, func_setting, subfunc_wechat
from resources import Constants
from ui import detail_ui
from utils import widget_utils, string_utils
from utils.logger_utils import mylogger as logger


def try_convert(value):
    try:
        return float(value)
    except ValueError:
        return value


class TreeviewRowUI:
    def __init__(self, root, m_class, m_main_frame, result, data_path, multiple_status, sw="WeChat"):
        self.chosen_tab = sw
        self.acc_index = None
        self.hovered_item = None
        self.single_click_id = None
        self.photo_images = []
        self.selected_logout_accounts = None
        self.selected_login_accounts = None
        self.logout_tree = None
        self.login_tree = None
        self.selected_logout_items = []
        self.selected_login_items = []
        self.m_class = m_class
        self.data_path = data_path
        self.multiple_status = multiple_status
        self.tooltips = {}
        self.root = root
        self.main_frame = m_main_frame

        print(self.chosen_tab)
        # 加载列表排序设置
        login_col_to_sort = func_setting.fetch_sw_setting_or_set_default("login_col_to_sort", self.chosen_tab)
        logout_col_to_sort = func_setting.fetch_sw_setting_or_set_default("logout_col_to_sort", self.chosen_tab)
        login_sort_asc = "false" \
            if func_setting.fetch_sw_setting_or_set_default("login_sort_asc", self.chosen_tab) == "true" \
            else "true"
        logout_sort_asc = "false" \
            if func_setting.fetch_sw_setting_or_set_default("logout_sort_asc", self.chosen_tab) == "true" \
            else "true"
        self.sort_order = {
            "login": (login_col_to_sort, login_sort_asc),
            "logout": (logout_col_to_sort, logout_sort_asc)
        }  # 控制排序顺序

        # 构建列表
        logins, logouts, wechat_processes = result
        # 调整行高
        style = ttk.Style()
        style.configure("RowTreeview", background="#FFFFFF", foreground="black",
                        rowheight=Constants.TREE_ROW_HEIGHT, selectmode="none")
        style.layout("RowTreeview", style.layout("Treeview"))  # 继承默认布局

        if len(logins) != 0:
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
            self.login_button_frame = ttk.Frame(self.login_title)
            self.login_button_frame.pack(side=tk.RIGHT)

            # 一键退出
            self.one_key_quit = ttk.Button(self.login_button_frame, text="一键退出",
                                           command=self.quit_selected_accounts, style='Custom.TButton')
            self.one_key_quit.pack(side=tk.RIGHT)
            # 配置
            self.config_btn = ttk.Button(self.login_button_frame, text="❐配 置", style='Custom.TButton',
                                         command=partial(self.create_config, multiple_status=self.multiple_status)
                                         )
            self.config_btn.pack(side=tk.RIGHT)
            widget_utils.disable_button_and_add_tip(
                self.tooltips, self.config_btn, "请选择一个账号进行配置，配置前有符号表示推荐配置的账号")

            self.login_tree = self.create_table("login")
            self.display_table(logins, "login")
            self.update_top_title("login")
            self.login_tree.bind("<Leave>", partial(self.on_leave))
            self.login_tree.bind("<Motion>", partial(self.on_mouse_motion))
            self.login_tree.bind("<Button-1>", partial(self.on_single_click, login_status="login"))
            self.login_tree.bind("<Double-1>", partial(self.double_selection, login_status="login"))
            self.login_tree.bind("<Configure>", self.adjust_columns_on_maximize)
            self.sort_column(self.login_tree, login_col_to_sort, "login")

        if len(logouts) != 0:
            # 未登录框架=未登录标题+未登录列表
            self.logout_frame = ttk.Frame(self.main_frame)
            self.logout_frame.pack(side=tk.TOP, fill=tk.X,
                                  padx=Constants.LOG_IO_FRM_PAD_X, pady=Constants.LOG_IO_FRM_PAD_Y)

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
            self.logout_button_frame = ttk.Frame(self.logout_title)
            self.logout_button_frame.pack(side=tk.RIGHT)

            # 一键登录
            self.one_key_auto_login = ttk.Button(self.logout_button_frame, text="一键登录",
                                                 command=self.auto_login_selected_accounts, style='Custom.TButton')
            self.one_key_auto_login.pack(side=tk.RIGHT)

            # 更新顶部复选框状态
            self.logout_tree = self.create_table("logout")
            self.display_table(logouts, "logout")
            self.update_top_title("logout")
            self.logout_tree.bind("<Leave>", partial(self.on_leave))
            self.logout_tree.bind("<Motion>", partial(self.on_mouse_motion))
            self.logout_tree.bind("<Button-1>", partial(self.on_single_click, login_status="logout"))
            self.logout_tree.bind("<Double-1>", partial(self.double_selection, login_status="logout"))
            self.logout_tree.bind("<Configure>", self.adjust_columns_on_maximize)
            self.sort_column(self.logout_tree, logout_col_to_sort, "logout")

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
        tree.column("#0", minwidth=Constants.TREE_ID_MIN_WIDTH,
                    width=Constants.TREE_ID_WIDTH, stretch=tk.NO)
        tree.column("pid", minwidth=Constants.TREE_PID_MIN_WIDTH,
                    width=Constants.TREE_PID_WIDTH, anchor='e', stretch=tk.NO)
        tree.column("配置", minwidth=Constants.TREE_CFG_MIN_WIDTH,
                    width=Constants.TREE_CFG_WIDTH, anchor='center', stretch=tk.NO)
        tree.column(" ", minwidth=Constants.TREE_DSP_MIN_WIDTH,
                    width=Constants.TREE_DSP_WIDTH, anchor='w')
        tree.column("原始微信号", anchor='center')
        tree.column("当前微信号", anchor='center')

        tree.pack(fill=tk.X, expand=True, padx=(10, 0))

        selected_bg = "#B2E0F7"
        hover_bg = "#E5F5FD"

        # 设置标签样式
        tree.tag_configure("disabled", background="#F5F7FA", foreground="grey")
        tree.tag_configure("selected", background=selected_bg, foreground="black")
        tree.tag_configure("hover", background=hover_bg, foreground="black")

        return tree

    def display_table(self, accounts, login_status):
        if login_status == "login":
            tree = self.login_tree
        elif login_status == "logout":
            tree = self.logout_tree
        else:
            tree = ttk.Treeview(self.main_frame, show='tree', height=1, style="RowTreeview")
        curr_config_acc = subfunc_file.get_curr_wx_id_from_config_file(self.data_path, self.chosen_tab)
        for account in accounts:
            display_name = " " + func_account.get_acc_origin_display_name(account)
            config_status = func_config.get_config_status_by_account(account, self.data_path, self.chosen_tab)
            avatar_url, alias, nickname, pid, has_mutex = subfunc_file.get_acc_details_from_json_by_tab(
                self.chosen_tab,
                account,
                avatar_url=None,
                alias="请获取数据",
                nickname="请获取数据",
                pid=None,
                has_mutex=None
            )

            img = func_account.get_acc_avatar_from_files(account)
            img = img.resize(Constants.TREE_AVT_LBL_SIZE, Image.Resampling.NEAREST)
            photo = ImageTk.PhotoImage(img)

            self.photo_images.append(photo)

            pid = "⚔" + str(pid) + " " if has_mutex else "" + str(pid) + " "
            config_status = "❐" + str(config_status) + "" if account == curr_config_acc else "" + str(
                config_status) + ""

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

            if config_status == "无配置" and login_status == "logout":
                widget_utils.add_a_tag_to_item(self.logout_tree, account, "disabled")

        tree.config(height=len(accounts))

    def adjust_columns_on_maximize(self, event=None):
        columns_to_hide = ["原始微信号", "当前微信号", "昵称"]
        tree = event.widget
        # print(event.widget)
        if self.root.state() != "zoomed":  # 非最大化时隐藏列和标题
            tree["show"] = "tree"  # 隐藏标题
            for col in columns_to_hide:
                tree.column(col, width=0, stretch=False)
        else:  # 最大化时显示列和标题
            width = int(self.root.winfo_screenwidth() / 5)
            tree["show"] = "tree headings"  # 显示标题
            for col in columns_to_hide:
                tree.column(col, width=width)  # 设置合适的宽度

    def sort_column(self, tree, col, table_type):
        # print("排序...")
        # 获取当前表格数据的 values、text、image 和 tags
        items = [
            {
                "values": tree.item(i)["values"],
                "text": tree.item(i)["text"],
                "image": tree.item(i)["image"],
                "tags": tree.item(i)["tags"],
                "iid": i  # 包括 iid
            }
            for i in tree.get_children()
        ]

        # 获取排序顺序
        _, asc_str = self.sort_order[table_type]
        is_ascending = True if asc_str == "true" else False

        # 按列排序
        items.sort(
            key=lambda x: (try_convert(x["values"][list(tree["columns"]).index(col)])),
            reverse=is_ascending
        )

        # 清空表格并重新插入排序后的数据，保留 values、text、image 和 tags 信息
        for i in tree.get_children():
            tree.delete(i)
        for item in items:
            tree.insert(
                "",  # 父节点为空，表示插入到根节点
                "end",  # 插入位置
                iid=item["iid"],  # 使用字典中的 iid
                text=item["text"],  # #0 列的文本
                image=item["image"],  # 图像对象
                values=item["values"],  # 列数据
                tags=item["tags"]  # 标签
            )

        # 根据排序后的行数调整 Treeview 的高度
        tree.configure(height=len(items))

        # 切换排序顺序
        self.sort_order[table_type] = col, "false" if asc_str == "true" else "true"
        subfunc_file.save_sw_sort_order_to_setting_ini(self.sort_order)

    def update_selected_display(self, login_status):
        # 获取选中行的“英语”列数据
        if login_status == "login":
            tree = self.login_tree
            selected_items = self.selected_login_items
            selected_accounts = [tree.item(item, "values")[self.acc_index] for item in selected_items]
            self.selected_login_accounts = selected_accounts
            # 配置只能是某1个账号
            if len(selected_accounts) == 1:
                widget_utils.enable_button_and_unbind_tip(
                    self.tooltips, self.config_btn)
            else:
                widget_utils.disable_button_and_add_tip(
                    self.tooltips, self.config_btn, "请选择一个账号进行配置，配置前有符号表示推荐配置的账号")
        else:
            tree = self.logout_tree
            selected_items = self.selected_logout_items
            selected_accounts = [tree.item(i, "values")[self.acc_index] for i in selected_items]
            self.selected_logout_accounts = selected_accounts

    def toggle_top_checkbox(self, _event, login_status):
        """
        切换顶部复选框状态，更新子列表
        :param _event: 触发事件的控件
        :param login_status: 是否登录
        :return: 阻断继续切换
        """
        # print(event.widget)
        # print(self.login_checkbox)
        if login_status == "login":
            checkbox_var = self.login_checkbox_var
            tree = self.login_tree
            selected_items = self.selected_login_items
            button = self.one_key_quit
            tip = "请选择要退出的账号"
        else:
            checkbox_var = self.logout_checkbox_var
            tree = self.logout_tree
            selected_items = self.selected_logout_items
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
        self.update_selected_display(login_status)  # 更新显示
        return "break"

    def update_top_title(self, login_status):
        """根据AccountRow实例的复选框状态更新顶行复选框状态"""
        # toggle方法
        toggle = partial(self.toggle_top_checkbox, login_status=login_status)

        # 判断是要更新哪一个顶行
        if login_status == "login":
            all_rows = [item for item in self.login_tree.get_children()
                        if "disabled" not in self.login_tree.item(item, "tags")]
            selected_rows = self.selected_login_items
            checkbox = self.login_checkbox
            title = self.login_title
            checkbox_var = self.login_checkbox_var
            button = self.one_key_quit
            tip = "请选择要退出的账号"
        else:
            all_rows = [item for item in self.logout_tree.get_children()
                        if "disabled" not in self.logout_tree.item(item, "tags")]
            selected_rows = self.selected_logout_items
            checkbox = self.logout_checkbox
            title = self.logout_title
            checkbox_var = self.logout_checkbox_var
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

    def on_leave(self, _event):
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

    def on_single_click(self, event, login_status):
        """处理单击事件，并在检测到双击时取消"""
        # 取消之前的单击延时处理（如果有）
        if self.single_click_id:
            self.root.after_cancel(self.single_click_id)
        # 设置一个延时，若在此期间未检测到双击，则处理单击事件
        self.single_click_id = self.root.after(200, lambda: self.toggle_selection(event, login_status))

    def toggle_selection(self, event, login_status):
        # print("进入了单击判定")
        if login_status == "login":
            tree = self.login_tree
            selected_items = self.selected_login_items
        elif login_status == "logout":
            tree = self.logout_tree
            selected_items = self.selected_logout_items
        else:
            tree = None
            selected_items = []
        item_id = tree.identify_row(event.y)
        if len(item_id) == 0:
            return
        if tree.identify_column(event.x) == "#0":  # 检查是否点击了图片列
            self.open_detail(tree.item(item_id, "values")[self.acc_index])
        else:
            if item_id and "disabled" not in tree.item(item_id, "tags"):  # 确保不可选的行不触发
                if item_id in selected_items:
                    selected_items.remove(item_id)
                    widget_utils.remove_a_tag_of_item(tree, item_id, "selected")
                else:
                    selected_items.append(item_id)
                    widget_utils.add_a_tag_to_item(tree, item_id, "selected")
                self.update_selected_display(login_status)  # 实时更新选中行显示
                self.update_top_title(login_status)

    def double_selection(self, event, login_status):
        if self.single_click_id:
            self.root.after_cancel(self.single_click_id)
            self.single_click_id = None
        # print("进入了双击判定")
        if login_status == "login":
            tree = self.login_tree
            selected_items = self.selected_login_items
            callback = self.quit_selected_accounts
        elif login_status == "logout":
            tree = self.logout_tree
            selected_items = self.selected_logout_items
            callback = self.auto_login_selected_acc
        else:
            tree = event.widget
            selected_items = []
            callback = None
        item_id = tree.identify_row(event.y)
        if len(item_id) == 0:
            return
        if tree.identify_column(event.x) == "#0":  # 检查是否点击了图片列
            subfunc_wechat.switch_to_wechat_account(self.root, tree.item(item_id, "values")[self.acc_index])
        else:
            if item_id and "disabled" not in tree.item(item_id, "tags"):  # 确保不可选的行不触发
                selected_items.clear()
                for i in tree.get_children():
                    widget_utils.remove_a_tag_of_item(tree, i, "selected")
                selected_items.append(item_id)
                widget_utils.add_a_tag_to_item(tree, item_id, "selected")
                self.update_selected_display(login_status)  # 实时更新选中行显示
                self.update_top_title(login_status)
                callback()

    def open_detail(self, account):
        """打开详情窗口"""
        detail_window = tk.Toplevel(self.root)
        detail_ui.DetailWindow(detail_window, account, self.m_class.create_main_frame_and_menu)

    def create_config(self, multiple_status):
        """按钮：创建或重新配置"""
        accounts = self.selected_login_items
        threading.Thread(target=func_config.test,
                         args=(self.m_class, accounts[0], multiple_status, self.chosen_tab)).start()

    def quit_selected_accounts(self):
        """退出所选账号"""
        accounts = self.selected_login_items
        accounts_to_quit = []
        for account in accounts:
            pid, = subfunc_file.get_acc_details_from_json_by_tab("WeChat", account, pid=None)
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
                self.m_class.create_main_frame_and_menu()
            except Exception as e:
                logger.error(e)

    def auto_login_selected_accounts(self):
        """登录所选账号"""
        accounts = self.selected_logout_items
        self.root.iconify()  # 最小化主窗口
        try:
            threading.Thread(
                target=func_login.auto_login_accounts,
                args=(accounts, self.multiple_status, self.m_class.create_main_frame_and_menu, self.chosen_tab)
            ).start()
        except Exception as e:
            logger.error(e)

    def auto_login_selected_acc(self):
        """登录所选账号"""
        accounts = self.selected_logout_items
        try:
            threading.Thread(
                target=func_login.auto_login_accounts,
                args=(accounts, self.multiple_status, self.m_class.create_main_frame_and_menu, self.chosen_tab)
            ).start()
        except Exception as e:
            logger.error(e)
