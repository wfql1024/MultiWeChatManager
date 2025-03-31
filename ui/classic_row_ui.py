from abc import ABC
from tkinter import ttk

from PIL import ImageTk, Image

from functions import func_account
from public_class.custom_classes import Condition
from public_class.global_members import GlobalMembers
from public_class.widget_frameworks import ActionableClassicTable, CheckboxItemRow
from resources import Constants


class ClassicRowUI:
    def __init__(self, result):
        self.classic_table_class = {}

        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root
        self.acc_tab_ui = self.root_class.acc_tab_ui
        self.sw = self.acc_tab_ui.sw

        self.acc_list_dict, _, _ = result
        self.frames = {}

        self.main_frame = self.acc_tab_ui.main_frame
        self.btn_dict = {
            "auto_quit_btn": {
                "text": "一键退出",
                "btn": None,
                "func": self.acc_tab_ui.to_quit_accounts,
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
                "func": self.acc_tab_ui.to_auto_login,
                "enable_scopes":
                    Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要登录的账号":
                        Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                }
            }
        }

        # 加载登录列表
        self.classic_table_class["login"] = AccLoginClassicTable(
                self, self.main_frame, "login", "已登录：", self.btn_dict["auto_quit_btn"])

        self.classic_table_class["logout"] = AccLoginClassicTable(
                self, self.main_frame, "logout", "未登录：", self.btn_dict["auto_login_btn"])

class AccLoginRowCheckbox(CheckboxItemRow, ABC):
    def __init__(self, parent_class, item, table_tag):
        super().__init__(parent_class, item, table_tag)

    def create_avatar_label(self, account):
        """
        创建头像标签
        :param account: 原始微信号
        :return: 头像标签 -> Label
        """
        try:
            img = func_account.get_acc_avatar_from_files(account, self.sw)
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

class AccLoginClassicTable(ActionableClassicTable, ABC):
    def __init__(self, parent_class, parent_frame, table_tag, title_text, major_btn_dict, *rest_btn_dicts):
        """用于展示不同登录状态列表的表格"""
        self.sw = None
        self.data_src = None
        super().__init__(parent_class, parent_frame, table_tag, title_text, major_btn_dict, *rest_btn_dicts)

    def initialize_members_in_init(self):
        self.data_src = self.parent_class.acc_list_dict
        self.sw = self.parent_class.sw
        pass

    def create_rows(self, item):
        table_tag = self.table_tag
        print(f"渲染{item}...")
        # 创建列表实例
        row = AccLoginRowCheckbox(self, item, table_tag)
        self.rows[item] = row

    def transfer_selected_iid_to_list(self):
        """
        将选中的iid进行格式处理
        """
        self.selected_items = [f"{self.sw}/{item}" for item in self.selected_iid_list]
        print(self.selected_items)
