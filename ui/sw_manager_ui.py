import tkinter as tk
from abc import ABC
from tkinter import messagebox

from PIL import Image, ImageTk

from functions import subfunc_file
from functions.sw_func import SwInfoFunc
from public_class import reusable_widgets
from public_class.custom_classes import Condition
from public_class.enums import RemoteCfg, LocalCfg, SwStates
from public_class.global_members import GlobalMembers
from public_class.reusable_widgets import SubToolWnd
from public_class.widget_frameworks import ActionableTreeView
from resources import Constants
from ui import menu_ui
from utils.logger_utils import mylogger as logger


class SwManagerWnd(SubToolWnd, ABC):
    """账号管理窗口"""

    def __init__(self, wnd, title):
        self.sw_manager_ui = None
        self.sw = None
        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.wnd_width, self.wnd_height = Constants.ACC_MNG_WND_SIZE
        self.sw_manager_ui = SwManagerUI(self.wnd, self.wnd)

    def load_ui(self):
        self.sw_manager_ui.refresh_frame()
        pass

    def update_content(self):
        self.sw_manager_ui.display_ui()


class SwManagerUI:
    """平台管理UI"""
    def __init__(self, wnd, frame):
        self.root_menu = None
        self.main_frame = None
        self.scrollable_canvas = None
        self.sw_list = None
        self.tree_class = {}

        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root
        self.wnd = wnd
        self.tab_frame = frame
        # 按钮模板,使用请使用浅拷贝
        self.btn_dict = {
            "visible": {
                "text": "显示",
                "btn": None,
                "func": self.to_visible_,
                "enable_scopes": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要显示的平台": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                }
            },
            "hidden": {
                "text": "隐藏",
                "btn": None,
                "func": self.to_hidden_,
                "enable_scopes": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要隐藏的平台": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)]),
                },
            },
            "disable": {
                "text": "禁用",
                "btn": None,
                "func": self.to_disable_,
                "enable_scopes": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要禁用的平台": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                },
            },
            "enable": {
                "text": "启用",
                "btn": None,
                "func": self.to_enable_,
                "enable_scopes": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要启用的平台": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                },
            },
            "setting": {
                "text": "设置",
                "btn": None,
                "func": self.to_setting_,
                "enable_scopes": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, 1)]),
                "tip_scopes_dict": {
                    "请选择一个要设置的平台": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)]),
                    "一个一个来啦~": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(2, None)])
                },
            }
        }

    def display_ui(self):
        # 创建一个可以滚动的画布，并放置一个主框架在画布上
        self.scrollable_canvas = reusable_widgets.ScrollableCanvas(self.tab_frame)
        self.main_frame = self.scrollable_canvas.main_frame

        self.sw_list, = subfunc_file.get_remote_cfg(RemoteCfg.GLOBAL, **{RemoteCfg.SP_SW: []})
        # 加载已启用列表
        self.tree_class["enable"] = SwManagerTreeView(
            self,
            "enable", "已启用：", None,
            self.btn_dict["disable"].copy(),
            self.btn_dict["hidden"].copy(),
            self.btn_dict["visible"].copy(),
            self.btn_dict["setting"].copy()
        )
        # 加载已禁用列表
        self.tree_class["disable"] = SwManagerTreeView(
            self, "disable", "已禁用：", None,
            self.btn_dict["enable"].copy(),
            self.btn_dict["setting"].copy()
        )

        print("列表都加载完，已经在这里了")

        # 加载完成后更新一下界面并且触发事件
        if self.scrollable_canvas is not None and self.scrollable_canvas.canvas.winfo_exists():
            self.scrollable_canvas.refresh_canvas()

    def refresh(self):
        """刷新菜单和界面"""
        print(f"刷新菜单与界面...")

        # 刷新菜单
        self.root_menu = menu_ui.MenuUI()
        config_data = subfunc_file.read_remote_cfg_in_rules()
        if config_data is None:
            messagebox.showerror("错误", "配置文件获取失败，将关闭软件，请检查网络后重启")
            self.root.destroy()
        try:
            self.root.after(0, self.root_menu.create_root_menu_bar)
        except Exception as re:
            logger.error(re)
            messagebox.showerror("错误", "配置文件损坏，将关闭软件，请检查网络后重启")
            self.root.destroy()

        # 刷新界面
        try:
            self.root.after(0, self.refresh_frame)
        except Exception as e:
            logger.error(e)
            self.root.after(3000, self.refresh_frame)


    def to_visible_(self, items):
        for sw in items:
            subfunc_file.update_settings(sw, **{LocalCfg.STATE: SwStates.VISIBLE})
        self.refresh_frame()
        pass

    def to_disable_(self, items):
        for sw in items:
            subfunc_file.update_settings(sw, **{LocalCfg.STATE: SwStates.DISABLED})
        self.refresh_frame()
        pass

    def to_hidden_(self, items):
        for sw in items:
            subfunc_file.update_settings(sw, **{LocalCfg.STATE: SwStates.HIDDEN})
        self.refresh_frame()
        pass

    def to_enable_(self, items):
        for sw in items:
            subfunc_file.update_settings(sw, **{LocalCfg.STATE: SwStates.VISIBLE})
        self.refresh_frame()
        pass

    def to_setting_(self, items):
        item = items[0]
        self.root_menu.open_sw_settings(item)
        pass

    def to_open_sw_detail(self, item):
        """打开详情窗口"""
        self.root_menu.open_sw_settings(item)

    def refresh_frame(self, sw=None):
        if sw:
            pass
        print("清理平台管理界面...")
        for widget in self.tab_frame.winfo_children():
            widget.destroy()
        self.display_ui()


class SwManagerTreeView(ActionableTreeView, ABC):
    def __init__(self, parent_class, table_tag, title_text, major_btn_dict, *rest_btn_dicts):
        """用于展示不同登录状态列表的表格"""
        self.data_src = None
        self.wnd = None
        self.photo_images = []
        super().__init__(parent_class, table_tag, title_text, major_btn_dict, *rest_btn_dicts)

    def initialize_members_in_init(self):
        self.wnd = self.parent_class.wnd
        # print(f"self.wnd={self.wnd}")
        self.data_src = self.parent_class.sw_list
        self.columns = (" ", "状态", "版本", "安装路径", "存储路径", "DLL路径")
        sort_str = subfunc_file.fetch_global_setting_or_set_default_or_none(f"{self.table_tag}_sort")
        if isinstance(sort_str, str):
            if len(sort_str.split(",")) == 2:
                self.default_sort["col"], self.default_sort["is_asc"] = sort_str.split(",")

    def set_table_style(self):
        super().set_table_style()

        tree = self.tree
        # 特定列的宽度和样式设置
        tree.column("#0", minwidth=Constants.COLUMN_MIN_WIDTH["SEC_ID"],
                    width=Constants.COLUMN_WIDTH["SEC_ID"], stretch=tk.NO)
        tree.column(" ", minwidth=Constants.COLUMN_MIN_WIDTH["展示"],
                    width=Constants.COLUMN_WIDTH["展示"], anchor='w')
        tree.column("状态", minwidth=Constants.COLUMN_MIN_WIDTH["状态"],
                    width=Constants.COLUMN_WIDTH["状态"], anchor='center', stretch=tk.NO)
        tree.column("版本", minwidth=Constants.COLUMN_MIN_WIDTH["版本"],
                    width=Constants.COLUMN_WIDTH["版本"], anchor='center', stretch=tk.NO)
        tree.column("安装路径", minwidth=Constants.COLUMN_MIN_WIDTH["安装路径"],
                    width=Constants.COLUMN_WIDTH["安装路径"], anchor='w', stretch=tk.NO)
        tree.column("存储路径", minwidth=Constants.COLUMN_MIN_WIDTH["存储路径"],
                    width=Constants.COLUMN_WIDTH["存储路径"], anchor='w', stretch=tk.NO)
        tree.column("DLL路径", minwidth=Constants.COLUMN_MIN_WIDTH["DLL路径"],
                    width=Constants.COLUMN_WIDTH["DLL路径"], anchor='w', stretch=tk.NO)

    def display_table(self):
        tree = self.tree.nametowidget(self.tree)
        sw_list = self.data_src
        table_tag = self.table_tag

        for sw in sw_list:
            if sw == "global":
                continue
            state = subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, LocalCfg.STATE, SwStates)
            if table_tag == "enable" and (state != SwStates.VISIBLE and state!= SwStates.HIDDEN):
                continue
            if table_tag == "disable" and state!= SwStates.DISABLED:
                continue

            display_name = " " + sw
            inst_path, data_dir, dll_dir = subfunc_file.get_settings(
                sw,
                inst_path=None,
                data_dir=None,
                dll_dir=None
            )
            version = SwInfoFunc.get_sw_ver(sw, dll_dir)
            # 获取平台图像
            img = SwInfoFunc.get_sw_logo(sw)
            img = img.resize(Constants.AVT_SIZE, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.photo_images.append(photo)

            # 转成显示的字符
            state = "显示" if state == SwStates.VISIBLE else "隐藏" if state == SwStates.HIDDEN else "禁用"
            inst_path = inst_path if inst_path else "请设置路径"
            data_dir = data_dir if data_dir else "请设置路径"
            dll_dir = dll_dir if dll_dir else "请设置路径"

            tree.insert("", "end", iid=f"{sw}", image=photo,
                        values=(display_name, state, version, inst_path, data_dir, dll_dir))

    def adjust_columns(self, event, wnd, col_width_to_show, columns_to_hide=None):
        # print("触发列宽调整")
        tree = self.tree.nametowidget(event.widget)

        if wnd.state() != "zoomed":
            # 非最大化时隐藏列和标题
            tree["show"] = "tree headings"  # 隐藏标题
            for col in columns_to_hide:
                if col in tree["columns"]:
                    tree.column(col, width=0, stretch=False)
        else:
            # 最大化时显示列和标题
            width = col_width_to_show
            tree["show"] = "tree headings"  # 显示标题
            for col in columns_to_hide:
                if col in tree["columns"]:
                    tree.column(col, width=width)  # 设置合适的宽度

    def click_on_id_column(self, click_time, item_id):
        """
        单击id列时，执行的操作
        :param click_time: 点击次数
        :param item_id: 所在行id
        :return:
        """
        if click_time == 1:
            self.parent_class.to_open_sw_detail(item_id)

    def on_tree_configure(self, event):
        """
        表格配置时，执行的操作
        :param event:
        :return:
        """
        # 在非全屏时，隐藏特定列
        columns_to_hide = ["安装路径", "存储路径", "DLL路径"]
        col_width_to_show = int(self.root.winfo_screenwidth() / 5)
        self.tree.bind("<Configure>", lambda e: self.adjust_columns(
            e, self.wnd, col_width_to_show, columns_to_hide), add='+')


