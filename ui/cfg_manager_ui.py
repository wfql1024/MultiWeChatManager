import tkinter as tk
from functools import partial
from tkinter import ttk

from PIL import ImageTk, Image

from functions.acc_func import AccInfoFunc, AccOperator
from functions.sw_func import SwInfoFunc
from public.custom_classes import Condition
from public.enums import CfgStatus, AccKeys
from public.global_members import GlobalMembers
from components.widget_wrappers import SubToolWndUI, ScrollableCanvasW
from components.composited_controls import ClassicAHT, CkbRow
from public import Config
from utils import widget_utils
from utils.encoding_utils import StringUtils
from utils.logger_utils import Logger, Printer


class CfgManagerWndCreator:
    @staticmethod
    def open_cfg_manager_wnd():
        cfg_manager_wnd = tk.Toplevel(GlobalMembers.root_class.root)
        CfgManagerWndUI(cfg_manager_wnd, "配置管理")


class CfgManagerWndUI(SubToolWndUI):
    def __init__(self, wnd, title):
        self.cfg_manager_ui = None
        self.sw = None
        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.wnd_width, self.wnd_height = Config.ABOUT_WND_SIZE

    def load_ui(self):
        self.cfg_manager_ui = CfgManagerUI(self.wnd, self.wnd_frame)
        self.cfg_manager_ui.display_ui()
        pass

    def update_content(self):
        ...


class CfgManagerUI:
    def __init__(self, wnd, frame):
        self.main_frame = None
        self.scrollable_canvas = None
        self.classic_table_class = {}

        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root
        self.login_ui = self.root_class.login_ui
        self.sw = self.login_ui.sw

        self.wnd = wnd
        self.ui_frame = frame

        self.table_frames = dict()

        self.btn_dict = {
            "del_cfg_btn": {
                "text": "一键删除",
                "btn": None,
                "func": self.to_del_cfg_of_accounts,
                "enable_scopes":
                    Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要删除的配置":
                        Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                }
            },
        }

    def display_ui(self):
        # 创建一个可以滚动的画布，并放置一个主框架在画布上
        self.scrollable_canvas = ScrollableCanvasW(self.ui_frame)
        self.main_frame = self.scrollable_canvas.main_frame

        # 添加占位控件
        self.table_frames[CfgStatus.USING] = ttk.Frame(self.main_frame)
        self.table_frames[CfgStatus.USING].pack(side="top", fill="x")
        self.table_frames[CfgStatus.HISTORY] = ttk.Frame(self.main_frame)
        self.table_frames[CfgStatus.HISTORY].pack(side="top", fill="x")

        # 加载登录列表
        self.classic_table_class[CfgStatus.USING] = CfgManagerCAHT(
            self, self.table_frames[CfgStatus.USING], CfgStatus.USING.value,
            "当前使用：", self.btn_dict["del_cfg_btn"].copy())

    def refresh_frame(self, sw=None):
        print("进入配置管理刷新")
        if sw:
            pass

        def slowly_refresh():
            if isinstance(self.ui_frame, (ttk.Frame, tk.Frame)) and self.ui_frame.winfo_exists():
                Printer().vital("刷新页面")
                for widget in self.ui_frame.winfo_children():
                    widget.destroy()
            self.display_ui()

        slowly_refresh()
        Printer().print_vn("加载完成!")

    def to_del_cfg_of_accounts(self, items: list):
        """删除选中的账号的配置"""
        accounts = [item.split("/")[1] for item in items]
        Printer().debug(f"删除选中的账号的配置：{accounts}")
        AccOperator.del_config_of_accounts(self.sw, accounts)
        self.refresh_frame()


class CfgManagerCAHT(ClassicAHT):
    def __init__(self, parent_class, parent_frame, table_tag, title_text, major_btn_dict, *rest_btn_dicts):
        """用于展示不同登录状态列表的表格"""
        self.sw = None
        self.cfg_manager_ui = None
        super().__init__(parent_class, parent_frame, table_tag, title_text, major_btn_dict, *rest_btn_dicts)

    def initialize_members_in_init(self):
        self.sw = self.parent_class.sw
        self.cfg_manager_ui = self.parent_class
        pass

    def create_rows(self):
        self.rows_frame = ttk.Frame(self.main_frame)
        self.rows_frame.pack(side="top", fill="x")
        # "当前使用"的数据来源: 获取所有的原生账号
        origin_accs = SwInfoFunc.get_sw_all_accounts_existed(self.sw, only="origin")

        for row_id in origin_accs:
            table_tag = self.table_tag
            # 创建列表实例
            # Printer().debug(self.rows_frame)
            row = CfgManagerCR(self, self.rows_frame, row_id, table_tag)
            self.rows[row_id] = row

        if len(self.rows) == 0:
            self.null_data = True

    def transfer_selected_iid_to_list(self):
        """
        将选中的iid进行格式处理
        """
        self.selected_items = [f"{self.sw}/{item}" for item in self.selected_iid_list]
        print(self.selected_items)


class CfgManagerCR(CkbRow):
    def __init__(self, parent_class, parent_frame, item, table_tag):
        self.photo_images = []
        self.tooltips = None
        self.sw = None
        self.login_ui = None
        self.cfg_manager_ui = None
        super().__init__(parent_class, parent_frame, item, table_tag)

    def initialize_members_in_init(self):
        self.tooltips = {}
        self.login_ui = self.root_class.login_ui
        self.sw = self.login_ui.sw
        self.cfg_manager_ui = self.parent_class.cfg_manager_ui

    def create_row(self):
        rows_frame = self.main_frame
        account = self.item

        # 账号详情
        details = AccInfoFunc.get_acc_details(self.sw, account)
        iid = details[AccKeys.IID]
        img = details[AccKeys.AVATAR]
        wrapped_display_name = details[AccKeys.WRAP_DISPLAY]
        config_status = details[AccKeys.CONFIG_STATUS]
        # 对详情中的数据进行处理
        if config_status == CfgStatus.NO_CFG:
            self.disabled = True
        img = img.resize(Config.AVT_SIZE, Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        self.photo_images.append(photo)

        # 行框架=复选框+头像标签+账号标签+按钮区域+配置标签
        self.row_frame = ttk.Frame(rows_frame)
        # 复选框
        self.checkbox_var = tk.BooleanVar(value=False)
        self.checkbox = tk.Checkbutton(self.row_frame, variable=self.checkbox_var)
        self.checkbox.pack(side="left")
        # 头像标签
        img = img.resize(Config.AVT_SIZE)
        photo = ImageTk.PhotoImage(img)
        avatar_label = ttk.Label(self.row_frame, image=photo)
        avatar_label.image = photo
        avatar_label.pack(side="left")
        # 按钮区域=配置按钮
        btn_frame = ttk.Frame(self.row_frame)
        btn_frame.pack(side="right")
        # 配置标签
        cfg_info_label = ttk.Label(self.row_frame, text=config_status, anchor='e')
        cfg_info_label.pack(side="right", padx=Config.CLZ_CFG_LBL_PAD_X, fill="x", expand=True)
        # 配置按钮
        btn_text = "删 除"
        btn_cmd = self.cfg_manager_ui.to_del_cfg_of_accounts
        btn = ttk.Button(
            btn_frame, text=btn_text, style='Custom.TButton',
            command=partial(btn_cmd, [iid])
        )
        btn.pack(side="right")
        # 账号标签
        try:
            self.item_label = ttk.Label(
                self.row_frame, text=wrapped_display_name)
        except Exception as e:
            Logger().warning(e)
            self.item_label = ttk.Label(
                self.row_frame, text=StringUtils.clean_texts(wrapped_display_name))
        self.item_label.pack(side="left", fill="x", padx=Config.CLZ_ROW_LBL_PAD_X)

        # 绑定事件到控件范围内所有位置
        widget_utils.exclusively_bind_event_to_frame_when_(
            [btn_frame], self.row_frame, "<Button-1>", self.toggle_checkbox,
            Condition(self.disabled, Condition.ConditionType.NOT_EQUAL, True)
        )
        # 设置控件状态
        widget_utils.enable_widget_when_(btn, Condition(self.disabled, Condition.ConditionType.NOT_EQUAL, True))
        # 设置提示
        widget_utils.set_widget_tip_when_(
            self.tooltips, btn,
            {"配置不存在": Condition(self.disabled, Condition.ConditionType.EQUAL, True)}
        )
        # 复选框的状态
        self.checkbox.config(state='disabled') if self.disabled is True else self.checkbox.config(
            state='normal')

        # 将行布局到界面上
        if self.disabled is True:
            self.row_frame.pack(side="bottom", fill="x", padx=Config.LOG_IO_FRM_PAD_X,
                                pady=Config.CLZ_ROW_FRM_PAD_Y)
        else:
            self.row_frame.pack(fill="x", padx=Config.LOG_IO_FRM_PAD_X, pady=Config.CLZ_ROW_FRM_PAD_Y)
