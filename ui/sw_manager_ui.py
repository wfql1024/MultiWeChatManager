import os
import tkinter as tk
from abc import ABC
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from functions import subfunc_file
from functions.sw_func import SwInfoFunc
from public_class import reusable_widgets
from public_class.custom_classes import Condition
from public_class.enums import RemoteCfg, LocalCfg, SwStates
from public_class.global_members import GlobalMembers
from public_class.reusable_widgets import SubToolWndUI
from public_class.widget_frameworks import ActionableTreeView
from resources import Constants
from ui.wnd_ui import WndCreator
from utils.encoding_utils import StringUtils
from utils.logger_utils import mylogger as logger
from utils.logger_utils import myprinter as printer


class SwManagerWndUI(SubToolWndUI, ABC):
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
        self.sw_manager_ui.display_sw_mng_ui()


class SwManagerUI:
    """平台管理UI"""

    def __init__(self, wnd, frame):
        print("构建平台管理ui...")
        self.quick_refresh_mode = None
        self.main_frame = None
        self.scrollable_canvas = None
        self.sw_list = None
        self.tree_class = {}
        self.frame_dict = {}

        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root
        self.wnd = wnd
        self.tab_frame = frame
        # 按钮模板,使用请使用浅拷贝
        self.btn_dict = {
            "visible": {
                "text": "显示",
                "btn": None,
                "func": self._create_set_state_method(SwStates.VISIBLE),
                "enable_scopes": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要显示的平台": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                }
            },
            "hidden": {
                "text": "隐藏",
                "btn": None,
                "func": self._create_set_state_method(SwStates.HIDDEN),
                "enable_scopes": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要隐藏的平台": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)]),
                },
            },
            "disable": {
                "text": "禁用",
                "btn": None,
                "func": self._create_set_state_method(SwStates.DISABLED),
                "enable_scopes": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要禁用的平台": Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                },
            },
            "enable": {
                "text": "启用",
                "btn": None,
                "func": self._create_set_state_method(SwStates.VISIBLE),
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

    def init_sw_manager_ui(self):
        """初始化账号管理UI"""
        if self.tab_frame is None or len(self.tab_frame.winfo_children()) == 0:
            self.refresh()

    def display_sw_mng_ui(self):
        print("创建平台管理界面...")
        # 创建一个可以滚动的画布，并放置一个主框架在画布上
        self.scrollable_canvas = reusable_widgets.ScrollableCanvas(self.tab_frame)
        self.main_frame = self.scrollable_canvas.main_frame

        self.sw_list, = subfunc_file.get_remote_cfg(RemoteCfg.GLOBAL, **{RemoteCfg.SP_SW: []})
        # 添加占位控件
        self.frame_dict["enable"] = ttk.Frame(self.main_frame)
        self.frame_dict["enable"].pack(side=tk.TOP, fill=tk.X)
        self.frame_dict["disable"] = ttk.Frame(self.main_frame)
        self.frame_dict["disable"].pack(side=tk.TOP, fill=tk.X)

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
        config_data = subfunc_file.read_remote_cfg_in_rules()
        if config_data is None:
            messagebox.showerror("错误", "配置文件获取失败，将关闭软件，请检查网络后重启")
            self.root.destroy()
        try:
            self.root.after(0, self.root_class.menu_ui.create_root_menu_bar)
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

    def _create_set_state_method(self, state):
        def set_state(items):
            for sw in items:
                subfunc_file.update_settings(sw, **{LocalCfg.STATE: state})
            self.refresh_frame()

        return set_state

    @staticmethod
    def to_setting_(items):
        item = items[0]
        WndCreator.open_sw_settings(item)

    def refresh_frame(self, sw=None):
        print("进入平台管理刷新")
        if sw:
            pass
        def slowly_refresh():
            if isinstance(self.tab_frame, ttk.Frame) and self.tab_frame.winfo_exists():
                printer.vital("刷新页面")
                for widget in self.tab_frame.winfo_children():
                    widget.destroy()
            self.display_sw_mng_ui()

        if self.quick_refresh_mode is True:
            try:
                # 不要忘记更新数据
                self.sw_list, = subfunc_file.get_remote_cfg(RemoteCfg.GLOBAL, **{RemoteCfg.SP_SW: []})
                tree_class = self.tree_class
                if all(tree_class[t].can_quick_refresh for t in tree_class):
                    for t in tree_class:
                        tree_class[t].quick_refresh_items(self.sw_list)
            except Exception as e:
                logger.warning(e)
                self.quick_refresh_mode = False
                slowly_refresh()
        else:
            slowly_refresh()
        printer.print_vn("加载完成!")


class SwManagerTreeView(ActionableTreeView, ABC):
    def __init__(self, parent_class, table_tag, title_text, major_btn_dict, *rest_btn_dicts):
        """用于展示不同登录状态列表的表格"""
        self.data_src = None
        self.wnd = None
        self.photo_images = []
        self.can_quick_refresh = None
        super().__init__(parent_class, table_tag, title_text, major_btn_dict, *rest_btn_dicts)

    def initialize_members_in_init(self):
        self.wnd = self.parent_class.wnd
        # print(f"self.wnd={self.wnd}")
        self.data_src = self.parent_class.sw_list
        self.columns = (" ", "状态", "版本", "安装路径", "存储路径", "DLL路径")
        sort_str = subfunc_file.fetch_global_setting_or_set_default_or_none(f"{self.table_tag}_sort")
        if isinstance(sort_str, str):
            if len(sort_str.split(",")) == 2:
                self.sort["col"], self.sort["is_asc"] = sort_str.split(",")

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
            if table_tag == "enable" and (state != SwStates.VISIBLE and state != SwStates.HIDDEN):
                continue
            if table_tag == "disable" and state != SwStates.DISABLED:
                continue

            display_name = SwInfoFunc.get_sw_origin_display_name(sw)
            f_display_name = " " + display_name
            inst_path, data_dir, dll_dir = subfunc_file.get_settings(
                sw,
                inst_path=None,
                data_dir=None,
                dll_dir=None
            )
            dll_path = dll_dir
            try:
                patch_dll, = subfunc_file.get_remote_cfg(sw, patch_dll=None)
                dll_path = os.path.join(dll_dir, patch_dll)
            except Exception as e:
                logger.warning(e)
            version = SwInfoFunc.get_sw_ver(sw, dll_path)
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

            try:
                tree.insert("", "end", iid=f"{sw}", image=photo,
                            values=(f_display_name, state, version, inst_path, data_dir, dll_dir))
            except Exception as e:
                logger.warning(e)
                tree.insert("", "end", iid=f"{sw}", image=photo,
                            values=StringUtils.clean_texts(
                                f_display_name, state, version, inst_path, data_dir, dll_dir))

        self.can_quick_refresh = True
        self.parent_class.quick_refresh_mode = True

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
            WndCreator.open_sw_settings(item_id)

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
