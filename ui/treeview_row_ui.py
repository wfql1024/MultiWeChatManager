import tkinter as tk
from abc import ABC
from collections.abc import Sized
from tkinter import ttk

from PIL import ImageTk, Image

from functions import subfunc_file
from functions.acc_func import AccInfoFunc, AccOperator
from functions.sw_func import SwInfoFunc
from public_class.custom_classes import Condition
from public_class.enums import OnlineStatus, LocalCfg, CfgStatus, AccKeys
from public_class.global_members import GlobalMembers
from public_class.widget_frameworks import ActionableTreeView
from resources import Constants, Strings
from ui.wnd_ui import WndCreator
from utils.encoding_utils import StringUtils
from utils.logger_utils import mylogger as logger
from utils.widget_utils import TreeUtils


class TreeviewLoginUI:
    def __init__(self, result):
        self.tree_class = {}
        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root
        self.login_ui = self.root_class.login_ui

        self.acc_list_dict, _ = result

        logins = self.acc_list_dict["login"]
        logouts = self.acc_list_dict["logout"]

        self.main_frame = self.login_ui.main_frame
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
                "func": self.login_ui.to_auto_login,
                "enable_scopes":
                    Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要登录的账号":
                        Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                }
            },
            "config_btn": {
                "text": "❐配 置",
                "btn": None,
                "func": self.login_ui.to_create_config,
                "enable_scopes":
                    Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, 1)]),
                "tip_scopes_dict": {
                    "请选择一个账号进行配置，伴有符号为推荐配置账号":
                        Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)]),
                    "只能配置一个账号哦~":
                        Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(2, None)])
                }
            },
            "create_starter": {
                "text": "创建启动器",
                "btn": None,
                "func": self.login_ui.to_create_starter,
                "enable_scopes":
                    Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要创建的账号":
                        Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                }
            }
        }
        self.ui_frame = dict()
        # 添加占位控件
        self.ui_frame[OnlineStatus.LOGIN] = ttk.Frame(self.main_frame)
        self.ui_frame[OnlineStatus.LOGIN].pack(side=tk.TOP, fill=tk.X)
        self.ui_frame[OnlineStatus.LOGOUT] = ttk.Frame(self.main_frame)
        self.ui_frame[OnlineStatus.LOGOUT].pack(side=tk.TOP, fill=tk.X)

        # 加载登录列表
        if isinstance(logins, Sized):
            self.tree_class["login"] = AccLoginTreeView(
                self,
                "login", "已登录：", self.btn_dict["auto_quit_btn"].copy(),
                self.btn_dict["config_btn"].copy(),
                self.btn_dict["create_starter"].copy(),
            )

        # 加载未登录列表
        if isinstance(logouts, Sized):
            self.tree_class["logout"] = AccLoginTreeView(
                self, "logout", "未登录：", self.btn_dict["auto_login_btn"].copy(),
                self.btn_dict["create_starter"].copy(),
            )


class AccLoginTreeView(ActionableTreeView, ABC):
    def __init__(self, parent_class, table_tag, title_text, major_btn_dict, *rest_btn_dicts):
        """用于展示不同登录状态列表的表格"""
        self.global_settings_value = None
        self.can_quick_refresh = None
        self.login_ui = None
        self.root = None
        self.photo_images = []
        self.sign_visible = None
        self.data_dir = None
        self.data_src = None
        super().__init__(parent_class, table_tag, title_text, major_btn_dict, *rest_btn_dicts)

    def initialize_members_in_init(self):
        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root
        self.login_ui = self.root_class.login_ui
        self.sw = self.login_ui.sw
        self.main_frame = self.parent_class.ui_frame[self.table_tag]
        self.global_settings_value = self.root_class.global_settings_value

        self.data_src = self.parent_class.acc_list_dict[self.table_tag]
        self.data_dir = self.root_class.sw_classes[self.sw].data_dir
        self.sign_visible: bool = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.SIGN_VISIBLE)
        self.columns = (" ", "配置", "pid", "账号标识", "平台id", "昵称")
        sort_str = subfunc_file.fetch_sw_setting_or_set_default_or_none(self.sw, f"{self.table_tag}_sort")
        if isinstance(sort_str, str):
            if len(sort_str.split(",")) == 2:
                self.default_sort["col"], self.default_sort["is_asc"] = sort_str.split(",")

    def set_table_style(self):
        super().set_table_style()

        tree = self.tree
        # 特定列的宽度和样式设置
        tree.column("#0", minwidth=Constants.TREE_ID_MIN_WIDTH,
                    width=Constants.TREE_ID_WIDTH, stretch=tk.NO)
        tree.column("pid", minwidth=Constants.TREE_PID_MIN_WIDTH,
                    width=Constants.TREE_PID_WIDTH, anchor='center', stretch=tk.NO)
        tree.column("配置", minwidth=Constants.TREE_CFG_MIN_WIDTH,
                    width=Constants.TREE_CFG_WIDTH, anchor='w', stretch=tk.NO)
        tree.column(" ", minwidth=Constants.TREE_DSP_MIN_WIDTH,
                    width=Constants.TREE_DSP_WIDTH, anchor='w')
        tree.column("账号标识", anchor='center')
        tree.column("平台id", anchor='center')
        tree.column("昵称", anchor='center')

    def display_table(self):
        self.sign_visible: bool = self.root_class.global_settings_value.sign_vis
        tree = self.tree.nametowidget(self.tree)
        accounts = self.data_src
        login_status = self.table_tag

        curr_config_acc = AccInfoFunc.get_curr_wx_id_from_config_file(self.sw, self.data_dir)

        for account in accounts:
            # 未登录账号中，隐藏的账号不显示
            hidden, = subfunc_file.get_sw_acc_data(self.sw, account, hidden=None)
            if hidden is True and login_status == "logout":
                continue
            # 账号详情
            details = AccInfoFunc.get_acc_details(self.sw, account)
            iid = details[AccKeys.IID]
            img = details[AccKeys.AVATAR]
            display_name = details[AccKeys.DISPLAY]
            config_status = details[AccKeys.CONFIG_STATUS]
            pid = details[AccKeys.PID]
            has_mutex = details[AccKeys.HAS_MUTEX]
            alias = details[AccKeys.ALIAS]
            nickname = details[AccKeys.NICKNAME]
            # 对详情中的数据进行处理
            display_name = "  " + display_name
            img = img.resize(Constants.AVT_SIZE, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.photo_images.append(photo)
            cs_suffix = Strings.CFG_SIGN if account == curr_config_acc and self.sign_visible else ""
            config_status = "" + str(config_status) + cs_suffix
            pid_suffix = Strings.MUTEX_SIGN if has_mutex and self.sign_visible else ""
            pid_str = " " + str(pid) + pid_suffix
            try:
                tree.insert("", "end", iid=iid, image=photo,
                            values=(display_name, config_status, pid_str, account, alias, nickname))
            except Exception as ec:
                logger.warning(ec)
                tree.insert("", "end", iid=iid, image=photo,
                            values=StringUtils.clean_texts(
                                display_name, config_status, pid_str, account, alias, nickname))
            if config_status == CfgStatus.NO_CFG and login_status == "logout":
                TreeUtils.add_a_tag_to_item(tree, iid, "disabled")

        self.can_quick_refresh = True
        self.login_ui.quick_refresh_mode = True

    def click_on_id_column(self, click_time, item_id):
        """
        单击id列时，执行的操作
        :param click_time: 点击次数
        :param item_id: 所在行id
        :return:
        """
        if click_time == 1:
            WndCreator.open_acc_detail(item_id, self.login_ui)
        elif click_time == 2:
            AccOperator.switch_to_sw_account_wnd(item_id)

    def adjust_columns(self, event, wnd, col_width_to_show, columns_to_hide=None):
        # print("触发列宽调整")
        tree = self.tree.nametowidget(event.widget)

        if wnd.state() != "zoomed":
            # 非最大化时隐藏列和标题
            tree["show"] = "tree"  # 隐藏标题
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

    def on_tree_configure(self, event):
        # 在非全屏时，隐藏特定列
        columns_to_hide = ["账号标识", "平台id", "昵称"]
        col_width_to_show = int(self.root.winfo_screenwidth() / 5)
        self.tree.bind("<Configure>", lambda e: self.adjust_columns(
            e, self.root, col_width_to_show, columns_to_hide), add='+')
