import tkinter as tk
from abc import ABC, abstractmethod
from functools import partial
from tkinter import ttk
from typing import Dict, Optional

from functions import subfunc_file
from public_class.custom_classes import Condition
from public_class.global_members import GlobalMembers
from resources import Constants
from utils import widget_utils
from utils.encoding_utils import StringUtils, ColorUtils
from utils.logger_utils import mylogger as logger
from utils.logger_utils import myprinter as printer
from utils.widget_utils import TreeUtils


class ActionableClassicTable(ABC):
    def __init__(self, parent_class, parent_frame, table_tag, title_text, major_btn_dict, *rest_btn_dicts):
        """
        创建一个普通控件组成的面板，可全选、多选，可以批量添加能对选中的条目进行操作的按钮，可以对单个条目的id列添加功能交互
        :param parent_class: 实例该列表的类
        :param table_tag: 表标识
        :param title_text: 列表标题
        :param major_btn_dict: 主按钮信息
        :param rest_btn_dicts: 其他按钮信息
        """
        self.rows_frame = None
        self.selected_iid_list = None
        self.usable_rows_dict = None
        self.tooltips = {}
        self.selected_items = []
        self.rows = {}
        self.data_src: dict = {}

        self.table_frame = None
        self.title_frame = None
        self.title = None
        self.checkbox = None
        self.checkbox_var = None
        self.label = None
        self.button_frame = None

        # 将传入的参数赋值给成员变量
        self.parent_class = parent_class
        self.parent_frame = parent_frame
        self.main_frame = parent_frame  # 默认直接使用提供的父框架
        self.table_tag = table_tag
        self.title_text = title_text
        self.major_btn_dict = major_btn_dict
        self.rest_btn_dicts = rest_btn_dicts

        # 其他的成员变量
        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root

        self.initialize_members_in_init()
        self.create_title()
        self.rows_frame = ttk.Frame(self.main_frame)
        self.rows_frame.pack(side="top", fill="x")
        self.create_rows()
        self.get_usable_rows()
        self.update_top_title()

    @abstractmethod
    def initialize_members_in_init(self):
        """子类中重写方法若需要设置或新增成员变量，重写这个方法并在其中定义和赋值成员"""
        pass

    def create_title(self):
        self.title_frame = ttk.Frame(self.main_frame)
        self.title_frame.pack(side="top", fill="x",
                              padx=Constants.LOG_IO_FRM_PAD_X, pady=Constants.LOG_IO_FRM_PAD_Y)
        # 标题=复选框+标签+按钮区域
        self.title = ttk.Frame(self.title_frame)
        self.title.pack(side="top", fill="x")

        # 复选框
        self.checkbox_var = tk.IntVar(value=0)
        self.checkbox = tk.Checkbutton(
            self.title,
            variable=self.checkbox_var,
            tristatevalue=-1
        )
        self.checkbox.pack(side="left")

        # 标签
        self.label = ttk.Label(self.title, text=self.title_text,
                               style='FirstTitle.TLabel')
        self.label.pack(side="left", fill="x", anchor="w", pady=Constants.LOG_IO_LBL_PAD_Y)

        # 按钮区域
        self.button_frame = ttk.Frame(self.title)
        self.button_frame.pack(side="right")

        # 主按钮
        if self.major_btn_dict is not None:
            major_btn = ttk.Button(
                self.button_frame, text=self.major_btn_dict["text"], style='Custom.TButton',
                command=lambda: self.major_btn_dict["func"](self.selected_items))
            self.major_btn_dict["btn"] = major_btn
            major_btn.pack(side="right")

        # 加载其他按钮
        if self.rest_btn_dicts is not None and len(self.rest_btn_dicts) != 0:
            for btn_dict in self.rest_btn_dicts:
                btn = ttk.Button(
                    self.button_frame, text=btn_dict["text"], style='Custom.TButton',
                    command=lambda b=btn_dict: b["func"](self.selected_items))
                btn_dict["btn"] = btn
                btn.pack(side="right")

    @abstractmethod
    def create_rows(self):
        """渲染账号所在行，请重写"""
        for item in self.data_src[self.table_tag]:
            table_tag = self.table_tag
            # 创建列表实例
            row = CkBoxRow(self, item, self.rows_frame, table_tag)
            self.rows[item] = row

    def toggle_top_checkbox(self, _event):
        """
        切换顶部复选框状态，更新子列表
        :param _event: 点击复选框
        :return: 阻断继续切换
        """
        checkbox_var = self.checkbox_var
        usable_rows_dict = self.usable_rows_dict

        for row in usable_rows_dict.values():
            row.checkbox_var.set(not checkbox_var.get())
        self.update_top_title()

        return "break"

    def update_top_title(self):
        """根据AccountRow实例的复选框状态更新顶行复选框状态"""
        self._get_selected_idd_list()

        # toggle方法
        toggle = partial(self.toggle_top_checkbox)
        usable_rows_dict = self.usable_rows_dict
        checkbox = self.checkbox
        title = self.title
        checkbox_var = self.checkbox_var
        button = self.major_btn_dict["btn"]
        tip_scopes_dict = self.major_btn_dict["tip_scopes_dict"]
        checkbox_var.set(0)

        # 调整复选框和frame的可用性
        checkbox.config(state="normal") if len(usable_rows_dict.keys()) != 0 else checkbox.config(state="disabled")
        widget_utils.bind_event_to_frame_when_(
            title, "<Button-1>", toggle,
            Condition(len(usable_rows_dict.keys()), Condition.ConditionType.NOT_EQUAL, 0)
        )
        # 更新复选框的值
        states = [row.checkbox_var.get() for row in usable_rows_dict.values() if len(usable_rows_dict.keys()) != 0]
        checkbox_var.set(1) if all(states) else checkbox_var.set(-1) if any(states) else checkbox_var.set(0)
        # 补充条件
        for condition in tip_scopes_dict.values():
            condition.value = checkbox_var.get()
        # 调整按钮的可用性和提示信息
        widget_utils.enable_widget_when_(
            button, Condition(checkbox_var.get(), Condition.ConditionType.NOT_EQUAL, 0))
        widget_utils.set_widget_tip_when_(
            self.tooltips, button, tip_scopes_dict)

    def _get_selected_idd_list(self):
        """获取已选的iid"""
        self.selected_iid_list = [account for account, row in self.rows.items() if row.checkbox_var.get()]
        # print(self.selected_iid_list)
        self.transfer_selected_iid_to_list()

    def transfer_selected_iid_to_list(self):
        """
        将选中的iid进行格式处理，默认直接输出iid列表，可以重写修改
        """
        self.selected_items = self.selected_iid_list
        # print(self.selected_items)

    def get_usable_rows(self):
        """获取可用的行"""
        self.usable_rows_dict = {
            item: row for item, row in self.rows.items()
            if row.disabled is not True
        }


class CkBoxRow(ABC):
    """
    为每一个账号创建其行布局的类
    """

    def __init__(self, parent_class, parent_frame, item, table_tag):
        self.disabled = None
        self.item_label = None
        self.checkbox = None
        self.checkbox_var = None
        self.row_frame = None

        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root

        # 变量
        self.parent_class = parent_class
        self.table_tag = table_tag
        self.item = item
        self.parent_frame = parent_frame
        self.main_frame = self.parent_frame
        self.update_top_title = self.parent_class.update_top_title
        self.iid = self.item
        self.initialize_members_in_init()
        self.create_row()

    @abstractmethod
    def initialize_members_in_init(self):
        pass

    def create_row(self):
        main_frame = self.main_frame

        # 行框架
        self.row_frame = ttk.Frame(main_frame)
        self.row_frame.pack(fill="x", padx=Constants.LOG_IO_FRM_PAD_X, pady=Constants.CLZ_ROW_FRM_PAD_Y) if \
            self.disabled is not True else \
            self.row_frame.pack(side="bottom", fill="x", padx=Constants.LOG_IO_FRM_PAD_X,
                                pady=Constants.CLZ_ROW_FRM_PAD_Y)
        # 复选框
        self.checkbox_var = tk.BooleanVar(value=False)
        self.checkbox = tk.Checkbutton(self.row_frame, variable=self.checkbox_var)
        self.checkbox.pack(side="left")
        # 行内容
        self.item_label = ttk.Label(self.row_frame, style="Mutex.TLabel", text="请设计行元素")
        self.item_label.pack(side="left", fill="x", padx=Constants.CLZ_ROW_LBL_PAD_X)
        widget_utils.bind_event_to_frame_when_(
            self.row_frame, "<Button-1>", self.toggle_checkbox,
            Condition(self.disabled, Condition.ConditionType.NOT_EQUAL, True)
        )
        self.checkbox.config(state='disabled') if self.disabled else self.checkbox.config(
            state='normal')

    def toggle_checkbox(self, _event):
        """
        切换复选框状态
        :param _event: 点击复选框
        :return: 阻断继续切换
        """
        self.checkbox_var.set(not self.checkbox_var.get())
        self.update_top_title()
        return "break"


class ActionableTreeView(ABC):
    def __init__(self, parent_class, table_tag, title_text, major_btn_dict, *rest_btn_dicts):
        """
        创建一个TreeView列表，可全选、多选，可以批量添加能对选中的条目进行操作的按钮，可以对单个条目的id列添加功能交互
        按钮信息格式为：
        "visible(id)": {
                "text": "显示",  # 按钮文本
                "btn": None,  # 按钮实例,在按钮生成后再设置
                "func": self.to_visible_,  # 按钮的功能,注意参数只能是一个列表,作用是对Tree中的选中的项目进行操作
                "enable_scopes": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),  # 启用条件
                "tip_scopes_dict": {
                    "请选择要显示的平台": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])  # 提示条件
                }
                # 条件范围请查看Condition类的说明
            },
        :param parent_class: 实例该列表的类
        :param table_tag: 表标识
        :param title_text: 列表标题
        :param major_btn_dict: 主按钮信息
        :param rest_btn_dicts: 其他按钮信息
        """
        self.tree_has_bind = False
        self.last_single_item = None
        self.data_src = None
        self.hovered_item = None
        self.tooltips = {}
        self.btn_dict = {}
        self.selected_items = []
        self.sw = None

        self.treeview_frame = None
        self.title_frame = None
        self.title = None
        self.checkbox = None
        self.checkbox_var = None
        self.label = None
        self.button_frame = None

        self.sort: Dict[str, bool] = {}
        self.default_sort = {
            "col": "#0",
            "is_asc": "True"
        }
        self.columns: tuple = ("子类请传入列的元组self.columns", "该列全屏不隐藏", "set_table_style中调列宽")
        self.selected_values: Dict[str, Dict] = {
            "column": {},
            "relate_chain": {}
        }

        # 将传入的参数赋值给成员变量
        self.parent_class = parent_class
        self.table_tag = table_tag
        self.title_text = title_text
        self.major_btn_dict = major_btn_dict
        self.rest_btn_dicts = rest_btn_dicts

        # 其他的成员变量
        self.root_class = self.parent_class.root_class
        self.root = self.root_class.root
        self.main_frame = self.parent_class.main_frame  # 默认使用父类的main_frame

        self.initialize_members_in_init()

        self.create_title()
        self.tree = self.create_table(self.columns)
        self.display_table()
        self.set_table_style()
        self._adjust_table()
        self._update_top_title()

    @abstractmethod
    def initialize_members_in_init(self):
        """子类中重写方法若需要设置或新增成员变量，重写这个方法并在其中定义和赋值成员"""
        pass

    def create_title(self):
        # 框架=标题+列表
        self.treeview_frame = ttk.Frame(self.main_frame)
        self.treeview_frame.pack(side="top", fill="x")
        self.title_frame = ttk.Frame(self.treeview_frame)
        self.title_frame.pack(side="top", fill="x",
                              padx=Constants.LOG_IO_FRM_PAD_X, pady=Constants.LOG_IO_FRM_PAD_Y)

        # 标题=复选框+标签+按钮区域
        self.title = ttk.Frame(self.title_frame)
        self.title.pack(side="top", fill="x")

        # 复选框
        self.checkbox_var = tk.IntVar(value=0)
        self.checkbox = tk.Checkbutton(
            self.title,
            variable=self.checkbox_var,
            tristatevalue=-1
        )
        self.checkbox.pack(side="left")

        # 标签
        self.label = ttk.Label(self.title, text=self.title_text,
                               style='FirstTitle.TLabel')
        self.label.pack(side="left", fill="x", anchor="w", pady=Constants.LOG_IO_LBL_PAD_Y)

        # 按钮区域
        self.button_frame = ttk.Frame(self.title)
        self.button_frame.pack(side="right")

        # 主按钮
        if self.major_btn_dict is not None:
            major_btn = ttk.Button(
                self.button_frame, text=self.major_btn_dict["text"], style='Custom.TButton',
                command=lambda: self.major_btn_dict["func"](self.selected_items))
            self.major_btn_dict["btn"] = major_btn
            major_btn.pack(side="right")

        # 加载其他按钮
        if self.rest_btn_dicts is not None and len(self.rest_btn_dicts) != 0:
            for btn_dict in self.rest_btn_dicts:
                btn = ttk.Button(
                    self.button_frame, text=btn_dict["text"], style='Custom.TButton',
                    command=lambda b=btn_dict: b["func"](self.selected_items))
                btn_dict["btn"] = btn
                btn.pack(side="right")

    def create_table(self, columns: tuple = ()):
        """定义表格，根据表格类型选择手动或自动登录表格"""
        tree = ttk.Treeview(self.treeview_frame, columns=columns, show='tree', height=1, style="RowTreeview")

        # 设置列标题和排序功能
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, anchor='center')  # 设置列宽
            self.sort[col] = True
        tree.pack(fill="x", expand=True, padx=(10, 0))
        return tree

    def display_table(self):
        """请重写此方法，以下为示例"""
        tree = self.tree.nametowidget(self.tree)
        values = tuple("请重写展示数据方法" for _ in tree["columns"])
        tree.insert("", "end", iid="item1", text="示例项", values=values)
        pass

    def set_table_style(self):
        """请重写此方法，以下为示例"""
        tree = self.tree.nametowidget(self.tree)

        # 默认情况下
        selected_bg = "#B2E0F7"
        hover_bg = ColorUtils.fade_color(selected_bg, 0.8)
        tree.tag_configure("disabled", background="#F5F7FA", foreground="grey")
        tree.tag_configure("selected", background=selected_bg, foreground="black")
        tree.tag_configure("hover", background=hover_bg, foreground="black")
        self.tree.bind("<Configure>", lambda e: self.on_tree_configure(e), add='+')

        # 以下为自定义样式示例
        # # 特定列的宽度和样式设置
        # tree.column("#0", minwidth=100, width=100, stretch=tk.YES)
        #
        # # 在非全屏时，隐藏特定列
        # columns_to_hide = ["该列全屏不隐藏"]
        # col_width_to_show = int(self.root.winfo_screenwidth() / 5)
        # tree.bind("<Configure>", lambda e: self.adjust_columns_on_maximize_(
        #     e, self.root, col_width_to_show, columns_to_hide), add='+')
        pass

    def _adjust_table(self):
        """
        绑定事件以实现自适应调整表格
        :return: 结束
        """
        tree = self.tree.nametowidget(self.tree)

        if len(tree.get_children()) == 0:
            # 如果条目数量为 0，隐藏控件
            print(f"应该隐藏{self.table_tag}列表")
            self.treeview_frame.pack_forget()
            self.main_frame.config(height=1)
            # self.main_frame.pack_propagate(False)  # 不自动调整自身大小
        else:
            # 如果条目数量不为 0则显示控件
            print(f"应该显示{self.table_tag}列表")
            self.main_frame.pack_propagate(True)  # 自动调整自身大小
            self.treeview_frame.pack(side="top", fill="x")
            self._adjust_treeview_height(None)
            # 排序+调整列宽
            self._apply_or_switch_col_order()
            self.on_tree_configure(None)
            if self.tree_has_bind is not True:
                # 绑定事件
                widget_utils.UnlimitedClickHandler(
                    self.root,
                    tree,
                    self._on_click_in_tree
                )
                tree.bind("<Leave>", partial(self._on_leave_tree))
                tree.bind("<Motion>", partial(self._moving_on_tree))
                self.tree_has_bind = True

    def _get_selected_values(self):
        # 获取选中行的“账号”列数据
        tree = self.tree.nametowidget(self.tree)
        selected_items = self.selected_items
        # print(selected_items)
        # print([tree.item(i) for i in selected_items])

        # 开辟一个新的字典，存储每一列的选中行的值
        for index, column in enumerate(tree["columns"]):
            selected_values_of_column = []
            for i in selected_items:
                try:
                    value = tree.item(i, "values")[index]
                    selected_values_of_column.append(value)
                except IndexError:
                    # 超出范围，跳过当前项
                    continue
            self.selected_values["column"][column] = selected_values_of_column

        # 添加 relate_chain 逻辑
        self.selected_values["relate_chain"] = {}
        for item_id in selected_items:
            relate_chain = []
            current_id = item_id
            while current_id:  # 一直向上查找父节点，直到根节点
                relate_chain.append(current_id)
                current_id = tree.parent(current_id)  # 获取父节点的 ID
            self.selected_values["relate_chain"][item_id] = relate_chain

        print(self.selected_values)
        print(tree.selection())

    def _toggle_top_checkbox(self, _event):
        """
        切换顶部复选框状态，更新子列表
        :param _event: 触发事件的控件
        :return: 阻断继续切换
        """
        # print(event.widget)
        # print(self.login_checkbox)
        checkbox_var = self.checkbox_var
        tree = self.tree.nametowidget(self.tree)
        selected_items = self.selected_items

        checkbox_var.set(not checkbox_var.get())
        value = checkbox_var.get()
        all_leaf_rows = TreeUtils.get_all_leaf_items_recursive(tree)
        for item_id in all_leaf_rows:
            if "disabled" not in tree.item(item_id, "tags"):  # 只选择允许选中的行
                if value:
                    # 执行全选
                    # print(tree.item(item_id, "tags"))
                    selected_items.append(item_id)
                    TreeUtils.add_a_tag_to_item(tree, item_id, "selected")
                else:
                    # 取消所有选择
                    selected_items.clear()
                    TreeUtils.remove_a_tag_of_item(tree, item_id, "selected")

        # 获取选中行的数据包以及根据选中情况更新顶部状态
        self._get_selected_values()
        self._update_top_title()
        return "break"

    def _update_top_title(self):
        """
        根据tree的状态更新顶行复选框状态
        :return:
        """
        # toggle方法
        toggle = partial(self._toggle_top_checkbox)
        tree = self.tree.nametowidget(self.tree)

        all_leaf_rows = TreeUtils.get_all_leaf_items_recursive(tree)
        all_usable_rows = [i for i in all_leaf_rows if "disabled" not in tree.item(i, "tags")]
        selected_rows = self.selected_items
        title = self.title
        checkbox_var = self.checkbox_var
        checkbox = self.checkbox
        tooltips = self.tooltips
        major_btn_dict = self.major_btn_dict
        rest_btn_dicts = self.rest_btn_dicts
        all_buttons = (major_btn_dict, *rest_btn_dicts)

        # 根据列表是否有可选设置复选框相关事件的绑定
        if len(all_usable_rows) == 0:
            title.unbind("<Button-1>")
            for child in title.winfo_children():
                child.unbind("<Button-1>")
        else:
            title.bind("<Button-1>", toggle, add="+")
            for child in title.winfo_children():
                child.bind("<Button-1>", toggle, add="+")

            # 根据子列表的状态来更新顶部复选框
            if len(selected_rows) == len(all_usable_rows):
                checkbox_var.set(1)
            elif 0 < len(selected_rows) < len(all_usable_rows):
                checkbox_var.set(-1)
            else:
                checkbox_var.set(0)

        # 完善按钮的状态设置和提示设置
        for btn_dict in all_buttons:
            if btn_dict is None:
                continue
            btn_dict["enable_scopes"].value = len(selected_rows)
            for tip, condition in btn_dict["tip_scopes_dict"].items():
                condition.value = len(selected_rows)
        # 控件的状态设置和提示设置
        widget_utils.enable_widget_when_(
            checkbox,
            Condition(len(all_usable_rows), Condition.ConditionType.OR_INT_SCOPE, [(1, None)])
        )
        for btn_dict in all_buttons:
            if btn_dict is None:  # 确保 btn_dict 不是 None
                continue
            widget_utils.enable_widget_when_(btn_dict["btn"], btn_dict["enable_scopes"])
            widget_utils.set_widget_tip_when_(tooltips, btn_dict["btn"], btn_dict["tip_scopes_dict"])

    def click_on_id_column(self, click_time, item_id):
        """
        单击id列时，执行的操作
        :param click_time: 点击次数
        :param item_id: 所在行id
        :return:
        """
        pass

    def click_on_col_headings(self, click_time, col_id):
        """
        单击列标题时，执行的操作
        :param click_time: 点击次数
        :param col_id: 所在列id
        :return: 阻断继续切换
        """
        if click_time:
            pass
        tree = self.tree.nametowidget(self.tree)
        col_name = tree.heading(col_id)["text"]  # 获取列标题
        self._apply_or_switch_col_order(col_name)

    def click_on_leaf_item(self, click_time, item_id, col_id):
        """
        单击叶子节点时，执行的操作
        :param click_time: 点击次数
        :param item_id: 所在行id
        :param col_id: 所在列id
        :return:
        """
        if col_id:
            pass
        tree = self.tree
        selected_items = self.selected_items

        # 不可选的行不触发
        if "disabled" in tree.item(item_id, "tags"):
            return

        if click_time == 1:

            # 获取当前选中的所有项
            current_selection = tree.selection()

            if len(current_selection) == 1:
                # 单选情况
                self.last_single_item = item_id
                if item_id in selected_items:
                    selected_items.remove(item_id)
                    TreeUtils.remove_a_tag_of_item(tree, item_id, "selected")
                else:
                    selected_items.append(item_id)
                    TreeUtils.add_a_tag_to_item(tree, item_id, "selected")
            else:
                # 多选情况，以last_single_item的状态为准
                all_need_to_be_selected = self.last_single_item in selected_items
                for sel_id in current_selection:
                    if all_need_to_be_selected:
                        if sel_id not in selected_items:
                            selected_items.append(sel_id)
                            TreeUtils.add_a_tag_to_item(tree, sel_id, "selected")
                    else:
                        if sel_id in selected_items:
                            selected_items.remove(sel_id)
                            TreeUtils.remove_a_tag_of_item(tree, sel_id, "selected")

        elif click_time == 2:
            # 取消所有选择
            selected_items.clear()

            # 移除所有项目的selected标签
            print(f"所有条目：{TreeUtils.get_all_items(tree)}")
            for i in TreeUtils.get_all_items(tree):
                TreeUtils.remove_a_tag_of_item(tree, i, "selected")

            # 只选择当前行
            selected_items.append(item_id)
            TreeUtils.add_a_tag_to_item(tree, item_id, "selected")
            self.major_btn_dict["func"](selected_items)

    def click_on_parent_item(self, click_time, item_id, col_id):
        """
        单击父节点时，执行的操作
        :param click_time: 点击次数
        :param item_id: 所在行id
        :param col_id: 所在列id
        :return:
        """
        pass

    def _on_click_in_tree(self, click_time, event):
        """
        单击树时，执行的操作
        :param click_time: 点击次数
        :param event: 事件
        :return
        """
        tree = event.widget
        item_id = tree.identify_row(event.y)
        column_id = tree.identify_column(event.x)
        print(f"{click_time}击({item_id}, {column_id})")

        # 列标题
        if len(item_id) == 0:
            self.click_on_col_headings(click_time, column_id)
        else:
            # id列
            if column_id == "#0":  # 检查是否点击了图片列
                self.click_on_id_column(click_time, item_id)
            else:
                # 父节点
                if tree.get_children(item_id):
                    self.click_on_parent_item(click_time, item_id, column_id)
                else:
                    # 叶子节点
                    self.click_on_leaf_item(click_time, item_id, column_id)

        self._adjust_treeview_height(None)
        self._update_top_title()
        self._get_selected_values()  # 实时更新选中行显示

        return "break"

    def _on_leave_tree(self, _event):
        """
        鼠标离开树时，执行的操作
        :param _event:
        :return:
        """
        if self.hovered_item is not None:
            TreeUtils.remove_a_tag_of_item(self.hovered_item[0], self.hovered_item[1], "hover")
            self.hovered_item = None

    def _moving_on_tree(self, event):
        """
        鼠标移动时，执行的操作
        :param event:
        :return:
        """
        tree = event.widget

        # 获取当前鼠标所在的行 ID
        item = tree.identify_row(event.y)

        # 检查是否是新的悬停行
        if self.hovered_item is not None:
            if self.hovered_item[0] != tree or self.hovered_item[1] != item:
                TreeUtils.remove_a_tag_of_item(tree, self.hovered_item[1], "hover")
                TreeUtils.add_a_tag_to_item(tree, item, "hover")
                # 更新当前悬停行
                self.hovered_item = (tree, item)
        else:
            TreeUtils.add_a_tag_to_item(tree, item, "hover")
            # 更新当前悬停行
            self.hovered_item = (tree, item)

    def on_tree_configure(self, event):
        """
        表格配置时，执行的操作
        :param event:
        :return:
        """

    def adjust_columns(self, event, wnd, col_width_to_show, columns_to_hide=None):
        """
        自适应调整列宽的方法
        :param event:
        :param wnd:
        :param col_width_to_show:
        :param columns_to_hide:
        :return:
        """
        pass
        # # print("触发列宽调整")
        # tree = self.tree.nametowidget(event.widget)
        #
        # if wnd.state() != "zoomed":
        #     # 非最大化时隐藏列和标题
        #     tree["show"] = "tree"  # 隐藏标题
        #     for col in columns_to_hide:
        #         if col in tree["columns"]:
        #             tree.column(col, width=0, stretch=False)
        # else:
        #     # 最大化时显示列和标题
        #     width = col_width_to_show
        #     tree["show"] = "tree headings"  # 显示标题
        #     for col in columns_to_hide:
        #         if col in tree["columns"]:
        #             tree.column(col, width=width)  # 设置合适的宽度

    def _adjust_treeview_height(self, event):
        # print("触发表高调整")
        # print(event)
        if event:
            # print(event.y)
            pass

        tree = self.tree.nametowidget(self.tree)

        total_rows = 0
        for root_item in tree.get_children():
            total_rows += TreeUtils.count_visible_rows_recursive(tree, root_item)
        # print(total_rows)
        tree.configure(height=total_rows)

        # return "break"

    def _apply_or_switch_col_order(self, col=None):
        """
        切换列排序或应用列排序，支持多级 TreeView，若不传入 col，则应用列排序
        :param col: 列
        :return: 无
        """
        print(f"当前排序:{self.default_sort}")
        table_tag = self.table_tag
        tree = self.tree.nametowidget(self.tree)

        # 调用递归函数获取所有数据
        copied_data = TreeUtils.CopiedTreeData(tree)
        copied_items = copied_data.items

        # 确定排序的列和顺序
        if col is not None:
            # 切换col的排序，同时把其他列的排序设置为降序，这样下次点击其他列默认升序
            is_asc = self.sort[col] is True
            for c in tree["columns"]:
                if c != col:
                    self.sort[c] = False
            is_asc_after = not is_asc
            print(f"切换列排序：{col},{is_asc_after}")
        else:
            # 获取要应用的列和顺序，若没有则默认用id列排正序
            col = self.default_sort["col"] if self.default_sort["col"] in tree["columns"] else "#0"
            is_asc = (self.default_sort["is_asc"] == "True") if self.default_sort["is_asc"] is not None else True
            is_asc_after = is_asc
            print(f"应用列排序：{col},{is_asc_after}")

        # 排序函数
        if col == "#0":
            # 直接对iid排序
            sort_key_by_float = lambda x: StringUtils.try_convert_to_float(x["iid"])
            sort_key_by_str = lambda x: str(x["iid"])
        else:
            # 按列排序
            sort_key_by_float = lambda x: StringUtils.try_convert_to_float(
                x["values"][list(tree["columns"]).index(col)])
            sort_key_by_str = lambda x: str(x["values"][list(tree["columns"]).index(col)])

        # 排序
        try:
            copied_items.sort(key=sort_key_by_float, reverse=not is_asc_after)
        except Exception as e:
            logger.warning(e)
            copied_items.sort(key=sort_key_by_str, reverse=not is_asc_after)

        # 清空表格并重新插入排序后的数据，保留父子层级
        for i in tree.get_children():
            tree.delete(i)
        copied_data.insert_items(tree)

        # 根据排序后的行数调整 Treeview 的高度
        tree.configure(height=len(copied_data.items))

        # 保存排序状态
        col: str = str(col)
        self.sort[col] = is_asc_after
        self.default_sort["col"] = col
        self.default_sort["is_asc"] = str(is_asc_after)
        print(f"保存时排序:{self.default_sort}")
        if self.sw is not None:
            subfunc_file.save_a_setting_and_callback(self.sw, f'{table_tag}_sort', f"{col},{is_asc_after}")
        else:
            subfunc_file.save_a_global_setting_and_callback(f'{table_tag}_sort', f"{col},{is_asc_after}")

    # @PerformanceDebugger.measure_method("测试快速刷新", auto_break=True)
    def quick_refresh_items(self, data_src):
        """
        快速刷新，需要传入display方法所需要的数据列表
        :param data_src: 数据列表
        :return:
        """
        printer.vital(f"快速刷新")
        # print("快速刷新:", data_src)
        self.data_src = data_src

        self.tree.configure(displaycolumns=())  # 临时隐藏列

        self.tree.delete(*self.tree.get_children())
        self.display_table()

        self.tree.configure(displaycolumns=self.columns)

        self._adjust_table()

        self.selected_items.clear()
        self._update_top_title()


class RadioTreeView(ABC):
    def __init__(self, parent_class, parent_frame, table_tag, title_text=None):
        """
        创建一个只能单选的TreeView列表，可以对单个条目的id列添加功能交互
        :param parent_class: 实例该列表的类
        :param table_tag: 表标识
        :param title_text: 列表标题
        """
        self.tree_has_bind = None
        self.data_src = None
        self.hovered_item = None
        self.photo_images = []
        self.tooltips = {}
        self.selected_item = []
        self.sw = None

        self.tree_frame = None
        self.title_frame = None
        self.title = None
        self.checkbox = None
        self.checkbox_var = None
        self.label = None
        self.button_frame = None

        self.sort: Dict[str, bool] = {

        }
        self.default_sort = {
            "col": "#0",
            "is_asc": True
        }
        self.columns: tuple = ("子类请传入列的元组self.columns", "该列全屏不隐藏", "set_table_style中调列宽")
        self.selected_values: Dict[str, Dict] = {
            "column": {},
            "relate_chain": {}
        }

        # 将传入的参数赋值给成员变量
        self.parent_class = parent_class
        self.table_tag = table_tag
        self.title_text = title_text

        # 其他的成员变量
        self.root_class = self.parent_class.root_class
        self.root = self.root_class.root
        self.main_frame = parent_frame

        self.initialize_members_in_init()

        self.create_frame()
        self.create_title() if self.title_text is not None else None
        self.tree = self.create_table(self.columns)
        self.display_table()
        self.set_table_style()
        self._adjust_table()

    @abstractmethod
    def initialize_members_in_init(self):
        """子类中重写方法若需要设置或新增成员变量，重写这个方法并在其中定义和赋值成员"""
        pass

    def create_frame(self):
        # 框架=标题+列表
        self.tree_frame = ttk.Frame(self.main_frame)
        self.tree_frame.pack(side="top", fill="x")

    def create_title(self):
        self.title_frame = ttk.Frame(self.tree_frame)
        self.title_frame.pack(side="top", fill="x",
                              padx=Constants.LOG_IO_FRM_PAD_X, pady=Constants.LOG_IO_FRM_PAD_Y)

        # 标题=标签
        self.title = ttk.Frame(self.title_frame)
        self.title.pack(side="top", fill="x")

        # 标签
        self.label = ttk.Label(self.title, text=self.title_text,
                               style='FirstTitle.TLabel')
        self.label.pack(side="left", fill="x", anchor="w", pady=Constants.LOG_IO_LBL_PAD_Y)

    def create_table(self, columns: tuple = ()):
        """定义表格，根据表格类型选择手动或自动登录表格"""
        tree = ttk.Treeview(self.tree_frame, columns=columns,
                            show='tree', height=1, style="SidebarTreeview", selectmode="browse")
        # 设置列标题和排序功能
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, anchor='center')  # 设置列宽
            self.sort[col] = True

        tree.pack(fill="x", expand=True, padx=(0, 0))
        return tree

    def display_table(self):
        """请重写此方法，以下为示例"""
        tree = self.tree.nametowidget(self.tree)
        values = tuple("请重写展示数据方法" for _ in tree["columns"])
        tree.insert("", "end", iid="item1", text="示例项", values=values)
        pass

    def set_table_style(self):
        """请重写此方法，以下为示例"""
        tree = self.tree.nametowidget(self.tree)

        # 默认情况下
        selected_bg = "#B2E0F7"
        hover_bg = "#E5F5FD"
        tree.tag_configure("disabled", background="#F5F7FA", foreground="grey")
        tree.tag_configure("selected", background=selected_bg, foreground="black")
        tree.tag_configure("hover", background=hover_bg, foreground="black")
        self.tree.bind("<Configure>", lambda e: self.on_tree_configure(e), add='+')

        # 以下为自定义样式示例
        # # 特定列的宽度和样式设置
        # tree.column("#0", minwidth=100, width=100, stretch=tk.YES)
        #
        # # 在非全屏时，隐藏特定列
        # columns_to_hide = ["该列全屏不隐藏"]
        # col_width_to_show = int(self.root.winfo_screenwidth() / 5)
        # tree.bind("<Configure>", lambda e: self.adjust_columns_on_maximize_(
        #     e, self.root, col_width_to_show, columns_to_hide), add='+')
        pass

    def _adjust_table(self):
        """
        绑定事件以实现自适应调整表格
        :return: 结束
        """
        tree = self.tree.nametowidget(self.tree)

        if len(tree.get_children()) == 0:
            # 如果条目数量为 0，隐藏控件
            print(f"应该隐藏{self.table_tag}列表")
            self.tree_frame.pack_forget()
        else:
            # 如果条目数量不为 0则显示控件
            print(f"应该显示{self.table_tag}列表")
            self.tree_frame.pack(side="top", fill="x")
            if self.tree_has_bind is not True:
                widget_utils.UnlimitedClickHandler(
                    self.root,
                    tree,
                    self._on_click_in_tree
                )
                tree.bind("<Leave>", partial(self._on_leave_tree))
                tree.bind("<Motion>", partial(self._moving_on_tree))
                self.tree_has_bind = True
            self.adjust_treeview_height(None)
            self._apply_or_switch_col_order()
            self.on_tree_configure(None)

    def _get_selected_values(self):
        # 获取选中行的“账号”列数据
        tree = self.tree.nametowidget(self.tree)
        selected_items = self.selected_item
        # print(selected_items)
        # print([tree.item(i) for i in selected_items])

        # 开辟一个新的字典，存储每一列的选中行的值
        for index, column in enumerate(tree["columns"]):
            selected_values_of_column = []
            for i in selected_items:
                try:
                    value = tree.item(i, "values")[index]
                    selected_values_of_column.append(value)
                except IndexError:
                    # 超出范围，跳过当前项
                    continue
            self.selected_values["column"][column] = selected_values_of_column

        # 添加 relate_chain 逻辑
        self.selected_values["relate_chain"] = {}
        for item_id in selected_items:
            relate_chain = []
            current_id = item_id
            while current_id:  # 一直向上查找父节点，直到根节点
                relate_chain.append(current_id)
                current_id = tree.parent(current_id)  # 获取父节点的 ID
            self.selected_values["relate_chain"][item_id] = relate_chain

        print(self.selected_values)
        print(tree.selection())

    def click_on_id_column(self, click_time, item_id):
        """
        单击id列时，执行的操作
        :param click_time: 点击次数
        :param item_id: 所在行id
        :return:
        """
        pass

    def click_on_col_headings(self, click_time, col_id):
        """
        单击列标题时，执行的操作
        :param click_time: 点击次数
        :param col_id: 所在列id
        :return: 阻断继续切换
        """
        if click_time:
            pass
        tree = self.tree.nametowidget(self.tree)
        col_name = tree.heading(col_id)["text"]  # 获取列标题
        self._apply_or_switch_col_order(col_name)

    def click_on_leaf_item(self, click_time, item_id, col_id):
        """
        单击叶子节点时，执行的操作
        :param click_time: 点击次数
        :param item_id: 所在行id
        :param col_id: 所在列id
        :return:
        """
        if col_id:
            pass
        if click_time:
            pass
        tree = self.tree
        selected_items = self.selected_item

        # 不可选的行不触发
        if "disabled" in tree.item(item_id, "tags"):
            return

        # 取消所有选择
        selected_items.clear()

        # 移除所有项目的selected标签
        print(f"所有条目：{TreeUtils.get_all_items(tree)}")
        for i in TreeUtils.get_all_items(tree):
            TreeUtils.remove_a_tag_of_item(tree, i, "selected")
        # 只选择当前行
        selected_items.append(item_id)
        TreeUtils.add_a_tag_to_item(tree, item_id, "selected")

    def click_on_parent_item(self, click_time, item_id, col_id):
        """
        单击父节点时，执行的操作
        :param click_time: 点击次数
        :param item_id: 所在行id
        :param col_id: 所在列id
        :return:
        """
        pass

    def _on_click_in_tree(self, click_time, event):
        """
        单击树时，执行的操作
        :param click_time: 点击次数
        :param event: 事件
        :return
        """
        tree = event.widget
        item_id = tree.identify_row(event.y)
        column_id = tree.identify_column(event.x)
        print(f"{click_time}击({item_id}, {column_id})")

        # 列标题
        if len(item_id) == 0:
            self.click_on_col_headings(click_time, column_id)
        else:
            # id列
            if column_id == "#0":  # 检查是否点击了图片列
                self.click_on_id_column(click_time, item_id)
            else:
                # 父节点
                if tree.get_children(item_id):
                    self.click_on_parent_item(click_time, item_id, column_id)
                else:
                    # 叶子节点
                    self.click_on_leaf_item(click_time, item_id, column_id)

        self.adjust_treeview_height(None)
        self._get_selected_values()  # 实时更新选中行显示

        return "break"

    def _on_leave_tree(self, _event):
        """
        鼠标离开树时，执行的操作
        :param _event:
        :return:
        """
        if self.hovered_item is not None:
            TreeUtils.remove_a_tag_of_item(self.hovered_item[0], self.hovered_item[1], "hover")
            self.hovered_item = None

    def _moving_on_tree(self, event):
        """
        鼠标移动时，执行的操作
        :param event:
        :return:
        """
        tree = event.widget

        # 获取当前鼠标所在的行 ID
        item = tree.identify_row(event.y)

        # 检查是否是新的悬停行
        if self.hovered_item is not None:
            if self.hovered_item[0] != tree or self.hovered_item[1] != item:
                TreeUtils.remove_a_tag_of_item(tree, self.hovered_item[1], "hover")
                TreeUtils.add_a_tag_to_item(tree, item, "hover")
                # 更新当前悬停行
                self.hovered_item = (tree, item)
        else:
            TreeUtils.add_a_tag_to_item(tree, item, "hover")
            # 更新当前悬停行
            self.hovered_item = (tree, item)

    def on_tree_configure(self, event):
        """
        表格配置时，执行的操作
        :param event:
        :return:
        """

    def adjust_columns(self, event, wnd, col_width_to_show, columns_to_hide=None):
        """
        自适应调整列宽的方法
        :param event:
        :param wnd:
        :param col_width_to_show:
        :param columns_to_hide:
        :return:
        """
        pass
        # # print("触发列宽调整")
        # tree = self.tree.nametowidget(event.widget)
        #
        # if wnd.state() != "zoomed":
        #     # 非最大化时隐藏列和标题
        #     tree["show"] = "tree"  # 隐藏标题
        #     for col in columns_to_hide:
        #         if col in tree["columns"]:
        #             tree.column(col, width=0, stretch=False)
        # else:
        #     # 最大化时显示列和标题
        #     width = col_width_to_show
        #     tree["show"] = "tree headings"  # 显示标题
        #     for col in columns_to_hide:
        #         if col in tree["columns"]:
        #             tree.column(col, width=width)  # 设置合适的宽度

    def adjust_treeview_height(self, event):
        # print("触发表高调整")
        # print(event)
        if event:
            # print(event.y)
            pass

        tree = self.tree.nametowidget(self.tree)

        total_rows = 0
        for root_item in tree.get_children():
            total_rows += TreeUtils.count_visible_rows_recursive(tree, root_item)
        # print(total_rows)
        tree.configure(height=total_rows)

        # return "break"

    def _apply_or_switch_col_order(self, col: Optional[str] = None):
        """
        切换列排序或应用列排序，支持多级 TreeView，若不传入 col，则应用列排序
        :param col: 列
        :return: 无
        """
        table_tag = self.table_tag
        tree = self.tree.nametowidget(self.tree)

        # 调用递归函数获取所有数据
        copied_data = TreeUtils.CopiedTreeData(tree)
        copied_items = copied_data.items

        # 确定排序的列和顺序
        if col is not None:
            # 切换col的排序，同时把其他列的排序设置为降序，这样下次点击其他列默认升序
            is_asc = self.sort[col] is True
            for c in tree["columns"]:
                if c != col:
                    self.sort[c] = False
            is_asc_after = not is_asc
            print(f"切换列排序：{col},{is_asc_after}")
        else:
            # 获取要应用的列和顺序，若没有则默认用id列排正序
            col = self.default_sort["col"] if self.default_sort["col"] in tree["columns"] else "#0"
            is_asc = (self.default_sort["is_asc"] == "True") if self.default_sort["is_asc"] is not None else True
            is_asc_after = is_asc
            print(f"应用列排序：{col},{is_asc_after}")

        # 排序函数
        if col == "#0":
            # 直接对iid排序
            sort_key_by_float = lambda x: StringUtils.try_convert_to_float(x["iid"])
            sort_key_by_str = lambda x: str(x["iid"])
        else:
            # 按列排序
            sort_key_by_float = lambda x: StringUtils.try_convert_to_float(
                x["values"][list(tree["columns"]).index(col)])
            sort_key_by_str = lambda x: str(x["values"][list(tree["columns"]).index(col)])

        # 排序
        try:
            copied_items.sort(key=sort_key_by_float, reverse=not is_asc_after)
        except Exception as e:
            logger.warning(e)
            copied_items.sort(key=sort_key_by_str, reverse=not is_asc_after)

        # 清空表格并重新插入排序后的数据，保留父子层级
        for i in tree.get_children():
            tree.delete(i)
        copied_data.insert_items(tree)

        self.adjust_treeview_height(None)

        # 保存排序状态
        self.sort[col] = is_asc_after
        if self.sw is not None:
            subfunc_file.save_a_setting_and_callback(self.sw, f'{table_tag}_sort', f"{col},{is_asc_after}")
        else:
            subfunc_file.save_a_global_setting_and_callback(f'{table_tag}_sort', f"{col},{is_asc_after}")

    def quick_refresh_items(self, data_src):
        """
        快速刷新，需要传入display方法所需要的数据列表
        :param data_src: 数据列表
        :return:
        """
        self.root.update_idletasks()
        printer.vital("快速刷新")
        tree = self.tree.nametowidget(self.tree)
        self.data_src = data_src

        for i in tree.get_children():
            tree.delete(i)

        self.display_table()
        self._adjust_table()
        self.selected_item.clear()
