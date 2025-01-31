import tkinter as tk
from abc import ABC

from PIL import ImageTk, Image

from functions import func_config, func_account, subfunc_file
from public_class import reusable_widget
from resources import Constants, Strings
from utils import widget_utils, string_utils
from utils.logger_utils import mylogger as logger


class TreeviewRowUI:
    def __init__(self, root_class, result):
        self.tree_class = {

        }

        self.root_class = root_class
        self.root = self.root_class.root
        self.acc_list_dict, _, _ = result

        self.main_frame = self.root_class.main_frame
        self.btn_dict = {
            "auto_quit_btn": {
                "text": "一键退出",
                "btn": None,
                "func": self.root_class.to_quit_accounts,
                "enable_scopes": [(1, None)],
                "tip_scopes_dict": {
                    "请选择要退出的账号": [(0, 0)],
                }
            },
            "auto_login_btn": {
                "text": "一键登录",
                "btn": None,
                "tip": "请选择要登录的账号",
                "func": self.root_class.to_auto_login,
                "enable_scopes": [(1, None)],
                "tip_scopes_dict": {
                    "请选择要登录的账号": [(0, 0)],
                }
            },
            "config_btn": {
                "text": "❐配 置",
                "btn": None,
                "func": self.root_class.to_create_config,
                "enable_scopes": [(1, 1)],
                "tip_scopes_dict": {
                    "请选择一个账号进行配置，伴有符号为推荐配置账号": [(0, 0)],
                    "只能配置一个账号哦~": [(2, None)],
                }
            }
        }

        # 加载登录列表
        if len(self.acc_list_dict["login"]) != 0:
            self.tree_class["login"] = AccLoginTreeView(
                self,
                "login", "已登录：", self.btn_dict["auto_quit_btn"],
                self.btn_dict["config_btn"], )

        # 加载未登录列表
        if len(self.acc_list_dict["logout"]) != 0:
            self.tree_class["logout"] = AccLoginTreeView(
                self, "logout", "未登录：", self.btn_dict["auto_login_btn"])


class AccLoginTreeView(reusable_widget.ActionableTreeView, ABC):
    def __init__(self, parent_class, table_tag, title_text, major_btn_dict, *rest_btn_dicts):
        """用于展示不同登录状态列表的表格"""
        self.root = None
        self.photo_images = []
        self.sign_visible = None
        self.data_dir = None
        self.item_list = None
        super().__init__(parent_class, table_tag, title_text, major_btn_dict, *rest_btn_dicts)

    def initialize_members_in_init(self):
        self.root = self.parent_class.root
        self.item_list = self.parent_class.acc_list_dict[self.table_tag]
        self.sw = self.root_class.sw
        self.data_dir = self.root_class.sw_classes[self.sw].data_dir
        self.sign_visible: bool = subfunc_file.fetch_global_setting_or_set_default("sign_visible") == "True"
        self.columns = (" ", "配置", "pid", "原始id", "当前id", "昵称")
        sort_str = subfunc_file.fetch_sw_setting_or_set_default(self.sw, f"{self.table_tag}_sort")
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
        tree.column("原始id", anchor='center')
        tree.column("当前id", anchor='center')
        tree.column("昵称", anchor='center')

        # 在非全屏时，隐藏特定列
        columns_to_hide = ["原始id", "当前id", "昵称"]
        col_width_to_show = int(self.root.winfo_screenwidth() / 5)
        self.tree.bind("<Configure>", lambda e: self.adjust_columns_on_maximize_(
            e, self.root, col_width_to_show, columns_to_hide), add='+')

    def display_table(self):
        tree = self.tree.nametowidget(self.tree)
        accounts = self.item_list
        login_status = self.table_tag

        curr_config_acc = subfunc_file.get_curr_wx_id_from_config_file(self.sw, self.data_dir)

        for account in accounts:
            # 未登录账号中，隐藏的账号不显示
            hidden, = subfunc_file.get_sw_acc_details_from_json(self.sw, account, hidden=None)
            if hidden is True and login_status == "logout":
                continue

            display_name = "  " + func_account.get_acc_origin_display_name(self.sw, account)
            config_status = func_config.get_sw_acc_login_cfg(self.sw, account, self.data_dir)
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
            pid = " " + str(pid) + suffix
            suffix = Strings.CFG_SIGN if account == curr_config_acc and self.sign_visible else ""
            config_status = "" + str(config_status) + suffix

            iid = f"{self.sw}/{account}"

            try:
                tree.insert("", "end", iid=iid, image=photo,
                            values=(display_name, config_status, pid, account, alias, nickname))
            except Exception as ec:
                logger.warning(ec)
                tree.insert("", "end", iid=iid, image=photo,
                            values=string_utils.clean_texts(
                                display_name, config_status, pid, account, alias, nickname))

            if config_status == "无配置" and login_status == "logout":
                widget_utils.add_a_tag_to_item(tree, iid, "disabled")

        self.adjust_treeview_height(None)
