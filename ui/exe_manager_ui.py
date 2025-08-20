import tkinter as tk
from tkinter import ttk, messagebox

from PIL import ImageTk, Image

from functions import subfunc_file
from functions.acc_func import AccInfoFunc
from functions.sw_func import SwInfoFunc, SwOperator
from public_class import reusable_widgets
from public_class.custom_classes import Condition
from public_class.custom_widget import CustomCornerBtn, CustomBtn
from public_class.enums import CfgStatus, AccKeys, RemoteCfg
from public_class.global_members import GlobalMembers
from public_class.reusable_widgets import SubToolWndUI
from public_class.widget_frameworks import ClassicATT, CkbRow
from resources import Constants
from utils import widget_utils
from utils.encoding_utils import StringUtils
from utils.logger_utils import Logger, Printer


class ExeManagerWndCreator:
    @staticmethod
    def open_exe_manager_wnd():
        exe_manager_wnd = tk.Toplevel(GlobalMembers.root_class.root)
        ExeManagerWndUI(exe_manager_wnd, "共存管理")


class ExeManagerWndUI(SubToolWndUI):
    def __init__(self, wnd, title):
        self.exe_manager_ui = None
        self.sw = None
        super().__init__(wnd, title)

    def initialize_members_in_init(self):
        self.wnd_width, self.wnd_height = Constants.ABOUT_WND_SIZE

    def load_ui(self):
        self.exe_manager_ui = ExeManagerUI(self.wnd, self.wnd_frame)
        self.exe_manager_ui.display_ui()
        pass

    def update_content(self):
        ...


class ExeManagerUI:
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
            "del_exe_btn": {
                "text": "×",
                "btn": None,
                "func": self.to_del_coexist_exe_of_accounts,
                "enable_scopes":
                    Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要删除的共存, 删除后将会出现在历史记录中":
                        Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                },
                "negative": True,
                "square": True
            },
            "del_history_btn": {
                "text": "×",
                "btn": None,
                "func": self.to_del_coexist_accounts_history,
                "enable_scopes":
                    Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要删除的历史记录":
                        Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                },
                "negative": True,
                "square": True
            },
            "rebuild_exe_btn": {
                "text": "重建",
                "btn": None,
                "func": self.to_rebuild_coexist_exe_for_accounts,
                "enable_scopes":
                    Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要重建的共存":
                        Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                },
                "negative": False
            }
        }

    def display_ui(self):
        # 创建一个可以滚动的画布，并放置一个主框架在画布上
        self.scrollable_canvas = reusable_widgets.ScrollableCanvas(self.ui_frame)
        self.main_frame = self.scrollable_canvas.main_frame

        # 添加占位控件
        self.table_frames[CfgStatus.USING] = ttk.Frame(self.main_frame)
        self.table_frames[CfgStatus.USING].pack(side="top", fill="x")
        self.table_frames[CfgStatus.HISTORY] = ttk.Frame(self.main_frame)
        self.table_frames[CfgStatus.HISTORY].pack(side="top", fill="x")

        # 加载登录列表
        self.classic_table_class[CfgStatus.USING] = ExeManagerCATT(
            self, self.table_frames[CfgStatus.USING], CfgStatus.USING.value,
            "当前使用：", self.btn_dict["del_exe_btn"].copy(),
            self.btn_dict["rebuild_exe_btn"].copy())
        self.classic_table_class[CfgStatus.HISTORY] = ExeManagerCATT(
            self, self.table_frames[CfgStatus.HISTORY], CfgStatus.HISTORY.value,
            "历史记录：", self.btn_dict["del_history_btn"].copy(),
            self.btn_dict["rebuild_exe_btn"].copy())

    def refresh_frame(self, sw=None):
        print("进入账号管理刷新")
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

    def to_del_coexist_accounts_history(self, items: list):
        """删除选中的账号的记录"""
        accounts = [item.split("/")[1] for item in items]
        Printer().debug(f"删除选中的账号的配置：{accounts}")
        for acc in accounts:
            subfunc_file.clear_some_acc_data(self.sw, acc)
        self.refresh_frame()

    def to_del_coexist_exe_of_accounts(self, items: list):
        """删除选中的共存程序"""
        accounts = [item.split("/")[1] for item in items]
        success, msg_dict = SwOperator.del_coexist_exe(self.sw, accounts)
        if success:
            messagebox.showinfo("成功", "删除成功!")
        else:
            msg_str = "\n".join(f"{acc}: {msg_dict[acc]}" for acc in msg_dict)
            messagebox.showerror("失败", f"失败账号及原因:\n{msg_str}")
        self.refresh_frame()

    def to_rebuild_coexist_exe_for_accounts(self, items: list):
        accounts = [item.split("/")[1] for item in items]
        ...
        self.refresh_frame()



class ExeManagerCATT(ClassicATT):
    def __init__(self, parent_class, parent_frame, table_tag, title_text, major_btn_dict, *rest_btn_dicts):
        """用于展示不同登录状态列表的表格"""
        self.sw = None
        self.exe_manager_ui = None
        super().__init__(parent_class, parent_frame, table_tag, title_text, major_btn_dict, *rest_btn_dicts)

    def initialize_members_in_init(self):
        self.sw = self.parent_class.sw
        self.exe_manager_ui = self.parent_class
        pass

    def create_rows(self):
        self.rows_frame = ttk.Frame(self.main_frame)
        self.rows_frame.pack(side="top", fill="x")
        if self.table_tag == CfgStatus.USING.value:
            # "当前使用"的数据来源: 获取所有的原生账号
            existed_coexist_accs = SwInfoFunc.get_sw_all_accounts_existed(self.sw, only="coexist")
            existed_coexist_accs.sort()
            for row_id in existed_coexist_accs:
                table_tag = self.table_tag
                # 创建列表实例
                # Printer().debug(self.rows_frame)
                row = ExeManagerCkRow(self, self.rows_frame, row_id, table_tag)
                self.rows[row_id] = row
        elif self.table_tag == CfgStatus.HISTORY.value:
            # "历史记录"的数据来源: 记录中的所有共存账号 - 当前使用的账号
            existed_coexist_accs = SwInfoFunc.get_sw_all_accounts_existed(self.sw, only="coexist")
            all_coexist_accs = [
                acc for acc in subfunc_file.get_sw_acc_data(self.sw)
                if AccInfoFunc.is_acc_coexist(self.sw, acc)
            ]
            history_accs = list(set(all_coexist_accs) - set(existed_coexist_accs))
            history_accs.sort()
            for row_id in history_accs:
                table_tag = self.table_tag
                # 创建列表实例
                # Printer().debug(self.rows_frame)
                row = ExeManagerCkRow(self, self.rows_frame, row_id, table_tag)
                self.rows[row_id] = row

    def transfer_selected_iid_to_list(self):
        """
        将选中的iid进行格式处理
        """
        self.selected_items = [f"{self.sw}/{item}" for item in self.selected_iid_list]
        print(self.selected_items)


class ExeManagerCkRow(CkbRow):
    def __init__(self, parent_class, parent_frame, item, table_tag):
        # self.bottom_frame = None
        # self.major_frame = None
        self.item_frame = None
        self.photo_images = []
        self.tooltips = None
        self.sw = None
        self.login_ui = None
        self.exe_manager_ui = None
        super().__init__(parent_class, parent_frame, item, table_tag)

    def initialize_members_in_init(self):
        self.tooltips = {}
        self.login_ui = self.root_class.login_ui
        self.sw = self.login_ui.sw
        self.exe_manager_ui = self.parent_class.exe_manager_ui

    def create_row(self):

        customized_btn_pad = int(Constants.CUS_BTN_PAD_X * 0.4)
        customized_btn_ipad = int(Constants.CUS_BTN_PAD_Y * 2.0)

        def _create_btn_in_(frame_of_btn, text):
            btn = CustomCornerBtn(frame_of_btn, text=text, i_padx=customized_btn_ipad * 2.5, i_pady=customized_btn_ipad)
            return btn

        def _create_square_btn_in(frame_of_btn, text):
            btn = CustomCornerBtn(frame_of_btn, text=text, i_pady=customized_btn_ipad)
            return btn

        def _pack_btn(btn):
            btn.pack(side="right", padx=customized_btn_pad, pady=customized_btn_pad)

        def _set_negative_style(btn):
            btn.set_major_colors("#FF0000")

        rows_frame = self.main_frame
        account = self.item

        # 账号详情
        details = AccInfoFunc.get_acc_details(self.sw, account)
        iid = details[AccKeys.IID]
        img = details[AccKeys.AVATAR]
        display_name = details[AccKeys.DISPLAY]
        config_status = details[AccKeys.CONFIG_STATUS]
        coexist_channel, sequence = subfunc_file.get_sw_acc_data(self.sw, account, channel=None, sequence=None)

        # 对详情中的数据进行处理
        if config_status == CfgStatus.NO_CFG:
            self.disabled = True
        img = img.resize(Constants.AVT_SIZE, Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        self.photo_images.append(photo)
        if coexist_channel is not None:
            channel_label, = subfunc_file.get_remote_cfg(
                self.sw, RemoteCfg.COEXIST, "channel", coexist_channel, label=None)
            if channel_label is None:
                channel_label = "??"
        else:
            channel_label = "??"

        # 行框架=复选框+头像标签+账号标签+按钮区域+配置标签
        self.row_frame = ttk.Frame(rows_frame)
        # 复选框
        self.checkbox_var = tk.BooleanVar(value=False)
        self.checkbox = tk.Checkbutton(self.row_frame, variable=self.checkbox_var)
        self.checkbox.pack(side="left")
        # 头像标签
        img = img.resize(Constants.AVT_SIZE)
        photo = ImageTk.PhotoImage(img)
        avatar_label = ttk.Label(self.row_frame, image=photo)
        avatar_label.image = photo
        avatar_label.pack(side="left")

        # 按钮区域
        btn_frame = ttk.Frame(self.row_frame)
        btn_frame.pack(side="right")
        # - 删除按钮
        del_coexist_btn = _create_square_btn_in(btn_frame, "×")
        if self.table_tag == CfgStatus.USING:
            (del_coexist_btn.set_bind_map(
                **{"1": lambda: self.exe_manager_ui.to_del_coexist_exe_of_accounts([iid])})
             .apply_bind(self.root))
        else:
            (del_coexist_btn.set_bind_map(
                **{"1": lambda: self.exe_manager_ui.to_del_coexist_accounts_history([iid])})
             .apply_bind(self.root))
        _pack_btn(del_coexist_btn)
        _set_negative_style(del_coexist_btn)
        # - 重建按钮
        rebuild_coexist_btn = _create_btn_in_(btn_frame, "重建")
        (rebuild_coexist_btn.set_bind_map(
            **{"1": lambda: ...})
         .apply_bind(self.root))
        _pack_btn(rebuild_coexist_btn)
        # - 防撤回的按钮
        if not isinstance(coexist_channel, str) or not isinstance(sequence, str):
            no_anti_revoke_btn = _create_btn_in_(btn_frame, "防撤")
            _pack_btn(no_anti_revoke_btn)
            no_anti_revoke_btn.set_state(CustomBtn.State.DISABLED)
            widget_utils.set_widget_tip_when_(self.tooltips, no_anti_revoke_btn, {"未知共存方案": True})
        else:
            res, msg = SwInfoFunc.identify_dll(self.sw, RemoteCfg.REVOKE.value, False, coexist_channel, sequence)
            if not isinstance(res, dict):
                no_anti_revoke_btn = _create_btn_in_(btn_frame, "防撤")
                _pack_btn(no_anti_revoke_btn)
                no_anti_revoke_btn.set_state(CustomBtn.State.DISABLED)
                widget_utils.set_widget_tip_when_(self.tooltips, no_anti_revoke_btn, {msg: True})
            else:
                for c, channel_res_tuple in res.items():
                    if not isinstance(channel_res_tuple, tuple) or len(channel_res_tuple) != 3:
                        continue
                    channel_des, = subfunc_file.get_remote_cfg(
                        self.sw, RemoteCfg.REVOKE.value, "channel", **{c: None})
                    # print(channel_des)
                    c_label = c
                    if isinstance(channel_des, dict):
                        if "label" in channel_des:
                            c_label = channel_des["label"]
                    anti_revoke_status, channel_msg, _ = channel_res_tuple
                    anti_revoke_btn = _create_btn_in_(btn_frame, f"{c_label}防撤")
                    (anti_revoke_btn.set_bind_map(
                        **{"1": lambda: SwOperator.switch_dll(self.sw, RemoteCfg.REVOKE.value, c, coexist_channel, sequence)})
                     .apply_bind(self.root))
                    _pack_btn(anti_revoke_btn)
                    if anti_revoke_status is True:
                        anti_revoke_btn.set_state(CustomBtn.State.SELECTED)
                    if anti_revoke_status is None:
                        anti_revoke_btn.set_state(CustomBtn.State.DISABLED)



        # 账号区域分两行, 上行是程序名称, 下行是账号名称
        self.item_frame = ttk.Frame(self.row_frame)
        self.item_frame.pack(side="left", fill="x")
        # 账号标签
        self.item_label = ttk.Label(self.item_frame, text=config_status)
        self.item_label.pack(fill="x", padx=Constants.CLZ_ROW_LBL_PAD_X)
        exe_remark_text = f"{channel_label}"
        if display_name != config_status:
            exe_remark_text += f"/{display_name}"
        # 程序链接了账号
        try:
            exe_remark_label = ttk.Label(
                self.item_frame, text=exe_remark_text, style="LittleGreyText.TLabel")
        except Exception as e:
            Logger().warning(e)
            exe_remark_label = ttk.Label(
                self.item_frame, text=StringUtils.clean_texts(exe_remark_text), style="LittleGreyText.TLabel")
        exe_remark_label.pack(side="bottom", fill="x", padx=Constants.CLZ_ROW_LBL_PAD_X)

        # 绑定事件到控件范围内所有位置
        widget_utils.exclusively_bind_event_to_frame_when_(
            [btn_frame], self.row_frame, "<Button-1>", self.toggle_checkbox,
            Condition(self.disabled, Condition.ConditionType.NOT_EQUAL, True)
        )
        # 设置控件状态
        CustomBtn.enable_custom_widget_when_(
            rebuild_coexist_btn, Condition(coexist_channel, Condition.ConditionType.NOT_EQUAL, None))
        # 设置提示
        widget_utils.set_widget_tip_when_(
            self.tooltips, rebuild_coexist_btn,
            {"方案未知": Condition(coexist_channel, Condition.ConditionType.EQUAL, None)}
        )
        # 复选框的状态
        self.checkbox.config(state='disabled') if self.disabled is True else self.checkbox.config(
            state='normal')

        # 将行布局到界面上
        if self.disabled is True:
            self.row_frame.pack(side="bottom", fill="x", padx=Constants.LOG_IO_FRM_PAD_X,
                                pady=Constants.CLZ_ROW_FRM_PAD_Y)
        else:
            self.row_frame.pack(fill="x", padx=Constants.LOG_IO_FRM_PAD_X, pady=Constants.CLZ_ROW_FRM_PAD_Y)
