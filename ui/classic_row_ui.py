import time
import tkinter as tk
from functools import partial
from tkinter import ttk

from PIL import ImageTk, Image

from components.composited_controls import ClassicAHT, CkbRow
from components.custom_widgets import CustomCornerBtn, CustomBtn
from functions import subfunc_file
from functions.acc_func import AccInfoFunc, AccOperator
from public import Config, Strings
from public.custom_classes import Condition
from public.enums import OnlineStatus, LocalCfg, CfgStatus, AccKeys
from public.global_members import GlobalMembers
from ui.wnd_ui import WndCreator
from utils import widget_utils
from utils.encoding_utils import StringUtils
from utils.logger_utils import Logger

# 登录/配置按钮
customized_btn_pad = Config.CUS_BTN_PAD
customized_btn_ipad_y = Config.CUS_BTN_IPAD_Y
customized_btn_ipad_x = Config.CUS_BTN_IPAD_X


def _create_btn_in_(frame_of_btn, text):
    btn = CustomCornerBtn(frame_of_btn, text=text, i_padx=customized_btn_ipad_x, i_pady=customized_btn_ipad_y)
    return btn


def _pack_btn(btn):
    btn.pack(side="right", padx=customized_btn_pad, pady=customized_btn_pad)


def _set_negative_style(btn):
    btn.set_major_colors("#FF0000")


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
                "text": "退 出",
                "btn": None,
                "func": self.login_ui.to_quit_accounts,
                "enable_scopes":
                    Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要退出的账号":
                        Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                },
                "negative": True
            },
            "auto_login_btn": {
                "text": "登 录",
                "btn": None,
                "tip": "请选择要登录的账号",
                "func": self.login_ui.to_auto_login,
                "enable_scopes":
                    Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要登录的账号":
                        Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                }
            },
            "create_starter": {
                "text": "快 捷",
                "btn": None,
                "func": self.login_ui.to_create_starter,
                "enable_scopes":
                    Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要创建的账号, 创建桌面快捷方式, 可以脱离本软件直接登录对应账号":
                        Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                }
            }
        }

        # 加载登录列表
        self.classic_table_class["login"] = AccLoginCAHT(
            self, self.table_frames[OnlineStatus.LOGIN], "login",
            "已登录：", self.btn_dict["auto_quit_btn"].copy(),
            self.btn_dict["create_starter"].copy()
        )

        self.classic_table_class["logout"] = AccLoginCAHT(
            self, self.table_frames[OnlineStatus.LOGOUT], "logout",
            "未登录：", self.btn_dict["auto_login_btn"].copy(),
            self.btn_dict["create_starter"].copy()
        )


class AccLoginCAHT(ClassicAHT):
    def __init__(self, parent_class, parent_frame, table_tag, title_text, major_btn_dict, *rest_btn_dicts):
        """用于展示不同登录状态列表的表格"""
        self.sw = None
        self.data_src = None
        super().__init__(parent_class, parent_frame, table_tag, title_text, major_btn_dict, *rest_btn_dicts)

    def initialize_members_in_init(self):
        self.data_src = self.parent_class.acc_list_dict[self.table_tag]
        self.sw = self.parent_class.sw
        # self.main_frame = ttk.Frame(self.parent_frame)
        # self.main_frame.pack(fill="both", expand=True)
        pass

    def load_form(self):
        self._create_acc_rows()

    def update_form(self):
        for widget in self.form_frame.winfo_children():
            widget.destroy()
        self._create_acc_rows()

    def _create_acc_rows(self):
        priority = {}
        row_ids = self.data_src
        for row_id in row_ids:
            priority[row_id] = 1 if AccInfoFunc.is_acc_coexist(self.sw, row_id) else 0
        # 补充代码，通过priority对row_ids进行排序
        sorted_row_ids = sorted(row_ids, key=lambda x: (priority[x], x), reverse=True)
        for row_id in sorted_row_ids:
            table_tag = self.table_tag
            # 创建列表实例
            # Printer().debug(self.rows_frame)
            row = AccLoginCR(self, self.form_frame, row_id, table_tag)
            if row.hidden is not True:
                self.rows[row_id] = row
        if len(self.rows) == 0:
            self.null_data = True

    def reformat_selected_items(self):
        """
        将选中的iid进行格式处理
        """
        self.selected_items = [f"{self.sw}/{item}" for item in self.selected_items_original]
        print(self.selected_items)


class AccLoginCR(CkbRow):
    def __init__(self, parent_class, parent_frame, item, table_tag):
        self.photo_images = []
        self.tooltips = None
        self.data_dir = None
        self.sw_class = None
        self.sw = None
        self.login_ui = None
        self.hidden = None
        super().__init__(parent_class, parent_frame, item, table_tag)

    def initialize_members_in_init(self):
        self.tooltips = {}
        self.login_ui = self.root_class.login_ui
        self.sw = self.login_ui.sw
        self.sw_class = self.root_class.sw_classes[self.sw]
        self.data_dir = self.sw_class.data_dir

    def load_row_content(self):
        self._create_acc_row()

    def update_row_content(self):
        for widget in self.row_frame.winfo_children():
            widget.destroy()
        self._create_acc_row()

    def _create_acc_row(self):
        account = self.item
        login_status = self.table_tag
        sign_visible: bool = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.SIGN_VISIBLE)
        start_time = time.time()

        curr_config_acc = AccInfoFunc.get_curr_wx_id_from_config_file(self.sw)

        # 未登录账号中，隐藏的账号不显示
        hidden, = subfunc_file.get_sw_acc_data(self.sw, account, hidden=None)
        if hidden is True and login_status == "logout":
            self.hidden = True
            return
        # 账号详情
        details = AccInfoFunc.get_acc_details(self.sw, account)
        iid = details[AccKeys.IID]
        img = details[AccKeys.AVATAR]
        wrapped_display_name = details[AccKeys.WRAP_DISPLAY]
        config_status = details[AccKeys.CONFIG_STATUS]
        has_mutex = details[AccKeys.HAS_MUTEX]
        # 对详情中的数据进行处理
        img = img.resize(Config.AVT_SIZE, Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        self.photo_images.append(photo)
        cs_suffix = Strings.CFG_SIGN if account == curr_config_acc and sign_visible else ""
        config_status = "" + str(config_status) + cs_suffix

        # 行框架=复选框+头像标签+账号标签+按钮区域+配置标签
        if config_status == CfgStatus.NO_CFG and login_status == "logout":
            self.disabled = True
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
        avatar_label.bind("<Enter>", lambda event: event.widget.config(cursor="hand2"))
        avatar_label.bind("<Leave>", lambda event: event.widget.config(cursor=""))
        # 按钮区域=配置或登录按钮
        btn_frame = ttk.Frame(self.row_frame)
        btn_frame.pack(side="right")
        # 配置标签
        cfg_info_label = ttk.Label(self.row_frame, text=config_status, anchor='e')
        cfg_info_label.pack(side="right", padx=Config.CLZ_CFG_LBL_PAD_X,
                            fill="x", expand=True)

        btn_text = "登 录" if login_status != "login" else "配 置"
        btn_cmd = self.login_ui.to_auto_login if login_status != "login" else self.login_ui.to_create_config
        acc_btn = _create_btn_in_(btn_frame, btn_text)
        (acc_btn.set_bind_map(
            **{"1": partial(btn_cmd, [iid])})
         .apply_bind(self.root))
        _pack_btn(acc_btn)
        # 账号标签: 账号含有互斥体, 则使用红色字体
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
        self.item_label.pack(side="left", fill="x", padx=Config.CLZ_ROW_LBL_PAD_X)

        # 绑定事件到控件范围内所有位置
        widget_utils.exclusively_bind_event_to_frame_when_(
            [avatar_label, btn_frame], self.row_frame, "<Button-1>", self.toggle_checkbox,
            Condition(self.disabled, Condition.ConditionType.NOT_EQUAL, True)
        )
        # 设置控件状态
        CustomBtn.enable_custom_widget_when_(
            acc_btn, Condition(self.disabled, Condition.ConditionType.NOT_EQUAL, True)
        )
        # 设置提示
        widget_utils.set_widget_tip_when_(
            self.tooltips,
            acc_btn,
            {"请先手动登录后配置": Condition(
                self.disabled, Condition.ConditionType.EQUAL, True)}
        )
        # 头像绑定详情事件
        widget_utils.UnlimitedClickHandler(
            self.root,
            avatar_label,
            **{"1": partial(WndCreator.open_acc_detail, iid, self.login_ui),
               "2": partial(AccOperator.switch_to_sw_account_wnd, iid)}
        )
        print(f"加载 {account} 行用时{time.time() - start_time:.4f}秒")
