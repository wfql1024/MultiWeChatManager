import time
import tkinter as tk
from abc import ABC
from functools import partial
from tkinter import ttk

from PIL import ImageTk, Image

from functions import subfunc_file
from functions.acc_func import AccInfoFunc, AccOperator
from functions.sw_func import SwInfoFunc
from public_class.custom_classes import Condition
from public_class.enums import OnlineStatus, LocalCfg, CfgStatus
from public_class.global_members import GlobalMembers
from public_class.widget_frameworks import ActionableClassicTable, CkBoxRow
from resources import Constants, Strings
from ui.wnd_ui import WndCreator
from utils import widget_utils
from utils.encoding_utils import StringUtils
from utils.logger_utils import Logger


class ClassicLoginUI:
    def __init__(self, result):
        self.classic_table_class = {}

        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root
        self.login_ui = self.root_class.login_ui
        self.sw = self.login_ui.sw

        self.acc_list_dict, _ = result
        self.table_frames = dict()
        self.main_frame = self.login_ui.main_frame  # 获取主框架:登录界面的带有滚动条的框架
        # 添加占位控件
        self.table_frames[OnlineStatus.LOGIN] = ttk.Frame(self.main_frame)
        self.table_frames[OnlineStatus.LOGIN].pack(side="top", fill="x")
        self.table_frames[OnlineStatus.LOGOUT] = ttk.Frame(self.main_frame)
        self.table_frames[OnlineStatus.LOGOUT].pack(side="top", fill="x")

        self.btn_dict = {
            "auto_quit_btn": {
                "text": "一键退出",
                "btn": None,
                "func": self.login_ui.to_quit_accounts,
                "enable_scopes":
                    Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要退出的账号":
                        Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                }
            },
            "auto_login_btn": {
                "text": "一键登录",
                "btn": None,
                "tip": "请选择要登录的账号",
                "func": self.login_ui.to_auto_login,
                "enable_scopes":
                    Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要登录的账号":
                        Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                }
            }
        }

        # 加载登录列表
        self.classic_table_class["login"] = ClassicLoginTable(
            self, self.table_frames[OnlineStatus.LOGIN], "login",
            "已登录：", self.btn_dict["auto_quit_btn"])

        self.classic_table_class["logout"] = ClassicLoginTable(
            self, self.table_frames[OnlineStatus.LOGOUT], "logout",
            "未登录：", self.btn_dict["auto_login_btn"])


class ClassicLoginTable(ActionableClassicTable, ABC):
    def __init__(self, parent_class, parent_frame, table_tag, title_text, major_btn_dict, *rest_btn_dicts):
        """用于展示不同登录状态列表的表格"""
        self.sw = None
        self.data_src = None
        super().__init__(parent_class, parent_frame, table_tag, title_text, major_btn_dict, *rest_btn_dicts)

    def initialize_members_in_init(self):
        self.data_src = self.parent_class.acc_list_dict
        self.sw = self.parent_class.sw
        self.main_frame = ttk.Frame(self.parent_frame)
        self.main_frame.pack(fill="both", expand=True)
        pass

    def create_rows(self):
        priority = {}
        row_ids = self.data_src[self.table_tag]
        for row_id in row_ids:
            acc_dict: dict = subfunc_file.get_sw_acc_data(self.sw, row_id)
            if "linked_acc" in acc_dict:
                priority[row_id] = 1
            else:
                priority[row_id] = 0
        # 补充代码，通过priority对row_ids进行排序
        sorted_row_ids = sorted(row_ids, key=lambda x: (priority[x], x), reverse=True)
        for row_id in sorted_row_ids:
            table_tag = self.table_tag
            # 创建列表实例
            # Printer().debug(self.rows_frame)
            row = LoginCkRow(self, self.rows_frame, row_id, table_tag)
            if row.hidden is not True:
                self.rows[row_id] = row

    def transfer_selected_iid_to_list(self):
        """
        将选中的iid进行格式处理
        """
        self.selected_items = [f"{self.sw}/{item}" for item in self.selected_iid_list]
        print(self.selected_items)


class LoginCkRow(CkBoxRow, ABC):
    def __init__(self, parent_class, parent_frame, item, table_tag):
        self.tooltips = None
        self.data_dir = None
        self.sw_class = None
        self.sw = None
        self.login_ui = None
        self.coexist_flag = False
        self.hidden = None
        super().__init__(parent_class, parent_frame, item, table_tag)

    def initialize_members_in_init(self):
        self.tooltips = {}
        self.login_ui = self.root_class.login_ui
        self.sw = self.login_ui.sw
        self.sw_class = self.root_class.sw_classes[self.sw]
        self.data_dir = self.sw_class.data_dir
        self.iid = f"{self.sw}/{self.item}"

    def create_row(self):
        rows_frame = self.main_frame
        iid = self.iid
        account = self.item
        login_status = self.table_tag
        sign_visible: bool = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.SIGN_VISIBLE)
        start_time = time.time()

        curr_config_acc = AccInfoFunc.get_curr_wx_id_from_config_file(self.sw, self.data_dir)

        # 未登录账号中，隐藏的账号不显示
        hidden, = subfunc_file.get_sw_acc_data(self.sw, account, hidden=None)
        if hidden is True and login_status == "logout":
            self.hidden = True
            return
        # 根据原始id得到真实id(共存程序会用linked_acc指向)
        acc_dict: dict = subfunc_file.get_sw_acc_data(self.sw, account)
        if "linked_acc" in acc_dict:
            config_status = account
            self.coexist_flag = True
            if acc_dict["linked_acc"] is not None:
                # 共存程序并且曾经登录过--------------------------------------------------------------------------
                linked_acc = acc_dict["linked_acc"]
            else:
                # 共存程序但不没有登录过--------------------------------------------------------------------------
                linked_acc = account
        else:
            # 主程序
            linked_acc = account
            config_status = AccInfoFunc.get_sw_acc_login_cfg(self.sw, linked_acc, self.data_dir)
            suffix = Strings.CFG_SIGN if linked_acc == curr_config_acc and sign_visible else ""
            config_status = "" + str(config_status) + suffix

        # 行框架=复选框+头像标签+账号标签+按钮区域+配置标签
        self.row_frame = ttk.Frame(rows_frame)
        if config_status == CfgStatus.NO_CFG:
            self.disabled = True
        # Printer().debug(self.item, config_status, self.coexist_flag, self.disabled)

        # 复选框
        self.checkbox_var = tk.BooleanVar(value=False)
        self.checkbox = tk.Checkbutton(self.row_frame, variable=self.checkbox_var)
        self.checkbox.pack(side="left")

        # 头像标签
        avatar_label = self.create_avatar_label(account)
        avatar_label.pack(side="left")
        avatar_label.bind("<Enter>", lambda event: event.widget.config(cursor="hand2"))
        avatar_label.bind("<Leave>", lambda event: event.widget.config(cursor=""))
        # print(f"加载头像区域用时{time.time() - start_time:.4f}秒")

        # 账号标签
        wrapped_display_name = AccInfoFunc.get_acc_wrapped_display_name(self.sw, linked_acc)
        has_mutex, = subfunc_file.get_sw_acc_data(self.sw, account, has_mutex=None)
        sign_visible: bool = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.SIGN_VISIBLE)
        if has_mutex and sign_visible:
            try:
                self.item_label = ttk.Label(
                    self.row_frame, style="Mutex.TLabel", text=wrapped_display_name)
            except Exception as e:
                Logger().warning(e)
                self.item_label = ttk.Label(
                    self.row_frame, style="Mutex.TLabel", text=StringUtils.clean_texts(wrapped_display_name))
        else:
            try:
                self.item_label = ttk.Label(
                    self.row_frame, text=wrapped_display_name)
            except Exception as e:
                Logger().warning(e)
                self.item_label = ttk.Label(
                    self.row_frame, text=StringUtils.clean_texts(wrapped_display_name))

        self.item_label.pack(side="left", fill="x", padx=Constants.CLZ_ROW_LBL_PAD_X)

        # print(f"加载账号显示区域用时{time.time() - start_time:.4f}秒")

        # 按钮区域=配置或登录按钮
        btn_frame = ttk.Frame(self.row_frame)
        btn_frame.pack(side="right")

        # 配置标签
        cfg_info_label = ttk.Label(self.row_frame, text=config_status, anchor='e')
        cfg_info_label.pack(side="right", padx=Constants.CLZ_CFG_LBL_PAD_X,
                            fill="x", expand=True)

        # 登录/配置按钮
        btn_text = "自动登录" if login_status != "login" else "配 置"
        btn_cmd = self.login_ui.to_auto_login if login_status != "login" else self.login_ui.to_create_config
        btn = ttk.Button(
            btn_frame, text=btn_text, style='Custom.TButton',
            command=partial(btn_cmd, [iid])
        )
        btn.pack(side="right")

        if login_status == "login":
            # 绑定事件到控件范围内所有位置
            widget_utils.exclusively_bind_event_to_frame_when_(
                [avatar_label], self.row_frame, "<Button-1>", self.toggle_checkbox, True)
        else:
            # 设置控件状态
            widget_utils.enable_widget_when_(
                btn, Condition(self.disabled, Condition.ConditionType.NOT_EQUAL, True)
            )
            # 设置提示
            widget_utils.set_widget_tip_when_(
                self.tooltips,
                btn,
                {"请先手动登录后配置": Condition(
                    self.disabled, Condition.ConditionType.EQUAL, True)}
            )
            # 绑定事件到控件范围内所有位置
            widget_utils.exclusively_bind_event_to_frame_when_(
                [avatar_label], self.row_frame, "<Button-1>", self.toggle_checkbox,
                Condition(self.disabled, Condition.ConditionType.NOT_EQUAL, True)
            )
            # 复选框的状态
            self.checkbox.config(state='disabled') if self.disabled is True else self.checkbox.config(
                state='normal')

        # 头像绑定详情事件
        widget_utils.UnlimitedClickHandler(
            self.root,
            avatar_label,
            **{"1": partial(WndCreator.open_acc_detail, iid, self.login_ui),
               "2": partial(AccOperator.switch_to_sw_account_wnd, iid)}
        )

        if self.coexist_flag is True:
            # Printer().debug(self.item, "应该置顶")
            self.row_frame.pack(side="top", fill="x", padx=Constants.LOG_IO_FRM_PAD_X,
                                pady=Constants.CLZ_ROW_FRM_PAD_Y)
        elif self.disabled is True:
            self.row_frame.pack(side="bottom", fill="x", padx=Constants.LOG_IO_FRM_PAD_X,
                                pady=Constants.CLZ_ROW_FRM_PAD_Y)
        else:
            self.row_frame.pack(fill="x", padx=Constants.LOG_IO_FRM_PAD_X, pady=Constants.CLZ_ROW_FRM_PAD_Y)

        print(f"加载 {account} 行用时{time.time() - start_time:.4f}秒")

    def create_avatar_label(self, account):
        """
        创建头像标签
        :param account: 原始微信号
        :return: 头像标签 -> Label
        """
        try:
            acc_dict: dict = subfunc_file.get_sw_acc_data(self.sw, account)
            if "linked_acc" in acc_dict:
                if acc_dict["linked_acc"] is not None:
                    # 共存程序曾经登录过--------------------------------------------------------------------------
                    linked_acc = acc_dict["linked_acc"]
                    img = AccInfoFunc.get_acc_avatar_from_files(self.sw, linked_acc)
                else:
                    # 共存程序但没登录过--------------------------------------------------------------------------
                    img = SwInfoFunc.get_sw_logo(self.sw)
            else:
                # 主程序
                linked_acc = account
                img = AccInfoFunc.get_acc_avatar_from_files(self.sw, linked_acc)
            img = img.resize(Constants.AVT_SIZE)
            photo = ImageTk.PhotoImage(img)
            avatar_label = ttk.Label(self.row_frame, image=photo)

        except Exception as e:
            print(f"Error creating avatar label: {e}")
            # 如果加载失败，使用一个空白标签
            photo = ImageTk.PhotoImage(image=Image.new('RGB', Constants.AVT_SIZE, color='white'))
            avatar_label = ttk.Label(self.row_frame, image=photo)
        avatar_label.image = photo  # 保持对图像的引用
        return avatar_label
