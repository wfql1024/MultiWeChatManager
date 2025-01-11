import tkinter as tk
from functools import partial
from tkinter import ttk

from PIL import ImageTk, Image

from functions import func_config, func_account, subfunc_file, subfunc_sw
from resources import Constants, Strings
from utils import widget_utils, string_utils
from utils.logger_utils import mylogger as logger
from utils.widget_utils import UnlimitedClickHandler


class TreeviewRowUI:
    def __init__(self, root_class, result):
        self.tree_class = {
            "login": None,
            "logout": None
        }

        self.root_class = root_class
        self.root = self.root_class.root
        self.acc_list_dict, _, _ = result

        self.main_frame = self.root_class.main_frame
        self.btn_dict = {
            "auto_quit_btn": {
                "text": "一键退出",
                "btn": None,
                "tip": "请选择要退出的账号",
                "func": self.root_class.to_quit_accounts,
                "enable_scope": (1, None),
                "tip_scope": (0, 0)
            },
            "auto_login_btn": {
                "text": "一键登录",
                "btn": None,
                "tip": "请选择要登录的账号",
                "func": self.root_class.to_auto_login,
                "enable_scope": (1, None),
                "tip_scope": (0, 0)
            },
            "config_btn": {
                "text": "❐配 置",
                "btn": None,
                "tip": "请选择一个账号进行配置，伴有符号为推荐配置账号",
                "func": self.root_class.to_create_config,
                "enable_scope": (1, 1),
                "tip_scope": (0, 0)
            }
        }

        # 加载登录列表
        if len(self.acc_list_dict["login"]) != 0:
            self.tree_class["login"] = TreeViewTable(
                self,
                "login", "已登录：", self.btn_dict["auto_quit_btn"],
                self.btn_dict["config_btn"],)

        # 加载未登录列表
        if len(self.acc_list_dict["logout"]) != 0:
            self.tree_class["login"] = TreeViewTable(
                self, "logout", "未登录：", self.btn_dict["auto_login_btn"])


class TreeViewTable:
    def __init__(self, parent_class, login_status, title_text, major_btn_dict, *btn_dicts):
        """

        :param parent_class:
        :param login_status:
        :param title_text:
        :param major_btn_dict:
        :param btn_dicts:
        """
        self.acc_list_dict = None
        self.photo_images = []
        self.hovered_item = None
        self.checkbox_var = None
        self.title = None
        self.checkbox = None
        self.tooltips = {}
        self.selected_accounts = []
        self.selected_items = []
        self.acc_index = None
        self.index_col_func = None

        self.parent_class = parent_class
        self.login_status = login_status
        self.title_text = title_text
        self.major_btn_dict = major_btn_dict
        self.btn_dicts = btn_dicts

        self.acc_list = self.parent_class.acc_list_dict[login_status]
        self.root = self.parent_class.root
        self.root_class = self.parent_class.root_class
        self.main_frame = self.root_class.main_frame
        self.data_dir = self.root_class.sw_info["data_dir"]
        self.sw = self.root_class.sw

        self.sign_visible: bool = subfunc_file.fetch_global_setting_or_set_default("sign_visible") == "True"

        # 框架=标题+列表
        self.tree_frame = ttk.Frame(self.main_frame)
        self.tree_frame.pack(side=tk.TOP, fill=tk.X,
                             padx=Constants.LOG_IO_FRM_PAD_X, pady=Constants.LOG_IO_FRM_PAD_Y)

        # 标题=复选框+标签+按钮区域
        self.title = ttk.Frame(self.tree_frame)
        self.title.pack(side=tk.TOP, fill=tk.X)

        # 复选框
        self.checkbox_var = tk.IntVar(value=0)
        self.checkbox = tk.Checkbutton(
            self.title,
            variable=self.checkbox_var,
            tristatevalue=-1
        )
        self.checkbox.pack(side=tk.LEFT)

        # 标签
        self.label = ttk.Label(self.title, text=title_text,
                               style='FirstTitle.TLabel')
        self.label.pack(side=tk.LEFT, fill=tk.X, anchor="w", pady=Constants.LOG_IO_LBL_PAD_Y)

        # 按钮区域=一键退出
        self.button_frame = ttk.Frame(self.title)
        self.button_frame.pack(side=tk.RIGHT)

        # 主按钮
        major_btn = ttk.Button(
            self.button_frame, text=self.major_btn_dict["text"], style='Custom.TButton',
            command=lambda: self.major_btn_dict["func"](self.selected_accounts))
        self.major_btn_dict["btn"] = major_btn
        major_btn.pack(side=tk.RIGHT)

        # 加载其他按钮
        if self.btn_dicts is not None and len(self.btn_dicts) != 0:
            for btn_dict in self.btn_dicts:
                btn = ttk.Button(
                    self.button_frame, text=btn_dict["text"], style='Custom.TButton',
                    command=lambda: btn_dict["func"](self.selected_accounts))
                btn_dict["btn"] = btn
                btn.pack(side=tk.RIGHT)

        self.tree = self.create_table()
        self.display_table()
        self.update_top_title()
        self.tree.bind("<Leave>", partial(self.on_leave))
        self.tree.bind("<Motion>", partial(self.on_mouse_motion))

        UnlimitedClickHandler(
            self.root,
            self.tree,
            partial(self.on_selection_in_tree),
            partial(self.on_double_selection_in_tree)
        )

        self.apply_or_switch_col_order()

    def create_table(self):
        """定义表格，根据表格类型选择手动或自动登录表格"""
        columns = (" ", "配置", "pid", "原始id", "当前id", "昵称")
        self.acc_index = columns.index("原始id")
        tree = ttk.Treeview(self.main_frame, columns=columns, show='tree', height=1, style="RowTreeview")

        # 设置列标题和排序功能
        for col in columns:
            tree.heading(
                col, text=col,
                command=lambda c=col: self.apply_or_switch_col_order(c)
            )
            tree.column(col, anchor='center')  # 设置列宽

        # 特定列的宽度和样式设置
        tree.column("#0", minwidth=Constants.TREE_ID_MIN_WIDTH,
                    width=Constants.TREE_ID_WIDTH, stretch=tk.NO)
        tree.column("pid", minwidth=Constants.TREE_PID_MIN_WIDTH,
                    width=Constants.TREE_PID_WIDTH, anchor='center', stretch=tk.NO)
        tree.column("配置", minwidth=Constants.TREE_CFG_MIN_WIDTH,
                    width=Constants.TREE_CFG_WIDTH, anchor='w', stretch=tk.NO)
        tree.column(" ", minwidth=Constants.TREE_DSP_MIN_WIDTH,
                    width=Constants.TREE_DSP_WIDTH, anchor='w')
        tree.column("原始id", anchor='center')
        tree.column("当前id", anchor='center')

        tree.pack(fill=tk.X, expand=True, padx=(10, 0))

        selected_bg = "#B2E0F7"
        hover_bg = "#E5F5FD"

        # 设置标签样式
        tree.tag_configure("disabled", background="#F5F7FA", foreground="grey")
        tree.tag_configure("selected", background=selected_bg, foreground="black")
        tree.tag_configure("hover", background=hover_bg, foreground="black")

        tree.bind("<Configure>", lambda e:self.adjust_columns_on_maximize(e), add='+')

        return tree

    def display_table(self):
        tree = self.tree
        accounts = self.acc_list
        login_status = self.login_status

        curr_config_acc = subfunc_file.get_curr_wx_id_from_config_file(self.data_dir, self.sw)
        for account in accounts:
            # 未登录账号中，隐藏的账号不显示
            hidden, = subfunc_file.get_sw_acc_details_from_json(self.sw, account, hidden=None)
            if hidden and login_status == "logout":
                continue

            display_name = "  " + func_account.get_acc_origin_display_name(self.sw, account)
            config_status = func_config.get_config_status_by_account(account, self.data_dir, self.sw)
            avatar_url, alias, nickname, pid, has_mutex = subfunc_file.get_sw_acc_details_from_json(
                self.sw,
                account,
                avatar_url=None,
                alias="请获取数据",
                nickname="请获取数据",
                pid=None,
                has_mutex=None
            )

            img = func_account.get_acc_avatar_from_files(account, self.sw)
            img = img.resize(Constants.AVT_SIZE, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            self.photo_images.append(photo)

            suffix = Strings.MUTEX_SIGN if has_mutex and self.sign_visible else ""
            pid =  " " +  str(pid) + suffix
            suffix = Strings.CFG_SIGN if account == curr_config_acc and self.sign_visible else ""
            config_status = "" + str(config_status) + suffix

            try:
                tree.insert("", "end", iid=account, image=photo,
                            values=(display_name, config_status, pid, account, alias, nickname))
            except Exception as ec:
                logger.warning(ec)
                tree.insert("", "end", iid=account, image=photo,
                            values=string_utils.clean_texts(
                                display_name, config_status, pid, account, alias, nickname))

            if config_status == "无配置" and login_status == "logout":
                widget_utils.add_a_tag_to_item(self.tree, account, "disabled")

        tree.config(height=len(accounts))

    def apply_or_switch_col_order(self, col=None):
        login_status = self.login_status

        # 加载列表排序设置
        tree = self.root.nametowidget(self.tree)
        sort_str = subfunc_file.fetch_sw_setting_or_set_default(self.sw, f"{login_status}_sort")
        tmp_col, sort = sort_str.split(",")
        is_asc: bool = sort == "True"

        if col is not None:
            print("切换列排序...")
            need_switch = True
        else:
            print("应用列排序...")
            need_switch = False
            col = tmp_col

        # 获取当前表格数据的 values、text、image 和 tags
        # print(tree)
        # print(tree.winfo_parent())

        origin_items = self.tree.get_children()

        copied_items = [
            {
                "values": tree.item(i)["values"],
                "text": tree.item(i)["text"],
                "image": tree.item(i)["image"],
                "tags": tree.item(i)["tags"],
                "iid": i  # 包括 iid
            }
            for i in origin_items
        ]

        # 当前是否要调成倒序，其和当前顺序的真值是一样的
        need_to_desc: bool = is_asc if need_switch else not is_asc

        # print(f"当前的顺序是：{is_asc}, 是否调整为倒序：{need_to_desc}")
        # print(list(tree["columns"]).index(col))

        # 按列排序
        copied_items.sort(
            key=lambda x: string_utils.try_convert_to_float(x["values"][list(self.tree["columns"]).index(col)]),
            reverse=need_to_desc  # 是否逆序
        )

        # 清空表格并重新插入排序后的数据，保留 values、text、image 和 tags 信息
        for i in self.tree.get_children():
            self.tree.delete(i)
        for item in copied_items:
            self.tree.insert(
                "",  # 父节点为空，表示插入到根节点
                "end",  # 插入位置
                iid=item["iid"],  # 使用字典中的 iid
                text=item["text"],  # #0 列的文本
                image=item["image"],  # 图像对象
                values=item["values"],  # 列数据
                tags=item["tags"]  # 标签
            )

        # 根据排序后的行数调整 Treeview 的高度
        self.tree.configure(height=len(copied_items))

        # 判断是否切换排序顺序，并保存
        now_asc = not is_asc if need_switch else is_asc
        subfunc_file.save_sw_setting(self.sw, f'{login_status}_sort', f"{col},{now_asc}")


    def get_selected_accounts(self):
        # 获取选中行的“账号”列数据
        tree = self.tree
        selected_items = self.selected_items
        selected_accounts = [tree.item(i, "values")[self.acc_index] for i in selected_items]
        self.selected_accounts = selected_accounts

    def update_top_title(self):
        """根据AccountRow实例的复选框状态更新顶行复选框状态"""
        # toggle方法
        toggle = partial(self.toggle_top_checkbox)

        all_rows = [item for item in self.tree.get_children()
                    if "disabled" not in self.tree.item(item, "tags")]
        selected_rows = self.selected_items
        title = self.title
        checkbox_var = self.checkbox_var
        checkbox = self.checkbox
        tooltips = self.tooltips
        major_btn_dict = self.major_btn_dict
        btn_dicts = self.btn_dicts

        # 根据列表是否有可选设置复选框相关事件的绑定
        if len(all_rows) == 0:
            title.unbind("<Button-1>")
            for child in title.winfo_children():
                child.unbind("<Button-1>")
        else:
            title.bind("<Button-1>", toggle, add="+")
            for child in title.winfo_children():
                child.bind("<Button-1>", toggle, add="+")

            # 根据子列表的状态来更新顶部复选框
            if len(selected_rows) == len(all_rows):
                checkbox_var.set(1)
            elif 0 < len(selected_rows) < len(all_rows):
                checkbox_var.set(-1)
            else:
                checkbox_var.set(0)

        # 控件的状态设置和提示设置
        widget_utils.enable_widget_with_condition(checkbox, (len(all_rows), (1, None)))

        widget_utils.enable_widget_with_condition(
            major_btn_dict["btn"], (len(selected_rows), major_btn_dict["enable_scope"]))
        widget_utils.set_widget_tip_with_condition(
            tooltips, major_btn_dict["btn"], major_btn_dict["tip"],
            (len(selected_rows), major_btn_dict["tip_scope"]))

        if btn_dicts is not None and len(btn_dicts) > 0:
            for btn_dict in btn_dicts:
                widget_utils.enable_widget_with_condition(
                    btn_dict["btn"], (len(selected_rows), btn_dict["enable_scope"]))
                widget_utils.set_widget_tip_with_condition(
                    tooltips, btn_dict["btn"], btn_dict["tip"],
                    (len(selected_rows), btn_dict["tip_scope"]))


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

    def toggle_top_checkbox(self, _event):
        """
        切换顶部复选框状态，更新子列表
        :param _event: 触发事件的控件
        :return: 阻断继续切换
        """
        # print(event.widget)
        # print(self.login_checkbox)
        checkbox_var = self.checkbox_var
        tree = self.tree
        selected_items = self.selected_items

        checkbox_var.set(not checkbox_var.get())
        value = checkbox_var.get()
        for item_id in tree.get_children():
            if "disabled" not in tree.item(item_id, "tags"):  # 只选择允许选中的行
                if value:
                    # 执行全选
                    # print(tree.item(item_id, "tags"))
                    selected_items.append(item_id)
                    widget_utils.add_a_tag_to_item(tree, item_id, "selected")
                else:
                    # 取消所有选择
                    selected_items.clear()
                    widget_utils.remove_a_tag_of_item(tree, item_id, "selected")

        self.get_selected_accounts()
        self.update_top_title()  # 更新显示
        return "break"

    def on_selection_in_tree(self, event=None):
        # print("进入了单击判定")
        tree = event.widget
        selected_items = self.selected_items
        item_id = tree.identify_row(event.y)
        self.index_col_func = lambda: self.root_class.open_acc_detail(tree.item(item_id, "values")[self.acc_index])

        # 列标题不响应
        if len(item_id) == 0:
            return
        # 列表未加载，跳过
        if selected_items is None:
            return
        # 不可选的行不触发
        if "disabled" in tree.item(item_id, "tags"):
            return

        if tree.identify_column(event.x) == "#0":  # 检查是否点击了图片列
            self.index_col_func()
        else:
            if item_id:
                if item_id in selected_items:
                    selected_items.remove(item_id)
                    widget_utils.remove_a_tag_of_item(tree, item_id, "selected")
                else:
                    selected_items.append(item_id)
                    widget_utils.add_a_tag_to_item(tree, item_id, "selected")
                self.get_selected_accounts()  # 实时更新选中行显示
                self.update_top_title()

    def on_double_selection_in_tree(self, event=None):
        double_click_func = lambda: self.major_btn_dict["func"](self.selected_accounts)

        tree = self.tree
        selected_items = self.selected_items
        item_id = tree.identify_row(event.y)
        # print(f"item_id: {item_id}")

        # 对列标题不触发
        if len(item_id) == 0:
            return
        # 不可选的不触发
        if "disabled" in tree.item(item_id, "tags"):
            return
        # 图片列双击切换窗口
        if tree.identify_column(event.x) == "#0":  # 检查是否点击了图片列
            subfunc_sw.switch_to_sw_account_wnd(
                self.sw, tree.item(item_id, "values")[self.acc_index], self.root)
        else:
            if item_id:
                # 取消所有选择
                selected_items.clear()
                for i in tree.get_children():
                    widget_utils.remove_a_tag_of_item(tree, i, "selected")
                # 只选择当前行
                selected_items.append(item_id)
                widget_utils.add_a_tag_to_item(tree, item_id, "selected")

                self.get_selected_accounts()  # 实时更新选中行显示
                self.update_top_title()
                double_click_func()

    def adjust_columns_on_maximize(self, event):
        # print("触发列宽调整")
        columns_to_hide = ["原始id", "当前id", "昵称"]

        tree = self.root.nametowidget(event.widget)
        # print(tree)

        if self.root.state() != "zoomed":
            # 非最大化时隐藏列和标题
            tree["show"] = "tree"  # 隐藏标题
            for col in columns_to_hide:
                tree.column(col, width=0, stretch=False)
        else:
            # 最大化时显示列和标题
            width = int(self.root.winfo_screenwidth() / 5)
            tree["show"] = "tree headings"  # 显示标题
            for col in columns_to_hide:
                tree.column(col, width=width)  # 设置合适的宽度




