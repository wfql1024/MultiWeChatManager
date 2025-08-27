import threading
import tkinter as tk
from functools import partial
from tkinter import ttk, messagebox

from PIL import ImageTk, Image

from components.composited_controls import ClassicAHT, CkbRow
from components.custom_widgets import CustomCornerBtn, CustomBtn
from components.widget_wrappers import SubToolWndUI, ScrollableCanvasW, TopProgressBar
from functions import subfunc_file
from functions.acc_func import AccInfoFunc
from functions.sw_func import SwInfoFunc, SwOperator
from public import Config
from public.custom_classes import Condition, FlowControlError
from public.enums import CfgStatus, AccKeys, RemoteCfg, LocalCfg
from public.global_members import GlobalMembers
from utils import widget_utils
from utils.encoding_utils import StringUtils
from utils.logger_utils import Logger, Printer

# TODO: 优化界面刷新, 不要啥都全页面刷新

def with_progress_factory(self):
    """将self传入, 返回一个装饰器, 这个装饰器将对装饰的函数过程收尾添加进度条的展示和结束."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            self.root.after(0, self.progress_bar.loading)
            try:
                return func(*args, **kwargs)
            finally:
                self.root.after(0, self.progress_bar.finished)
        return wrapper
    return decorator

def with_progress(func):
    def wrapper(self, *args, **kwargs):   # 注意这里把 self 作为参数
        self.root.after(0, self.progress_bar.loading)
        try:
            return func(self, *args, **kwargs)
        finally:
            self.root.after(0, self.progress_bar.finished)
    return wrapper


customized_btn_pad = int(Config.CUS_BTN_PAD_X * 0.4)
customized_btn_ipad = int(Config.CUS_BTN_PAD_Y * 2.0)


def _create_btn_in_(frame_of_btn, text):
    """方法提取: 创建个普通按钮"""
    btn = CustomCornerBtn(frame_of_btn, text=text, i_padx=customized_btn_ipad * 2.5, i_pady=customized_btn_ipad)
    return btn


def _create_square_btn_in(frame_of_btn, text):
    """方法提取: 创建个方形按钮"""
    btn = CustomCornerBtn(frame_of_btn, text=text, i_pady=customized_btn_ipad)
    return btn


def _pack_btn_right(btn):
    """方法提取: 将按钮布局到右边"""
    btn.pack(side="right", padx=customized_btn_pad, pady=customized_btn_pad)


def _set_negative_style(btn):
    """方法提取: 将按钮设置为消极效果(红色)"""
    btn.set_major_colors("#FF0000")


def _create_and_pack_vertical_line_btn_in_(frame_of_btn):
    """方法提取: 创建一个竖线表示分割线"""
    btn = CustomCornerBtn(frame_of_btn, width=5, text="")
    btn.set_state(CustomBtn.State.DISABLED)
    _pack_btn_right(btn)


def _thread_to_load_patching_button(
        instance, sw, mode, frame, tooltips,
        switch_and_fresh_func, coexist_channel=None, ordinal=None):
    """提取的公共方法, 用以批量创建补丁按钮"""
    def _thread():
        res, msg = SwInfoFunc.identify_dll(sw, mode, False, coexist_channel, ordinal)
        instance.root.after(0, _update_ui, res, msg)

    def _update_ui(res, msg):
        if not isinstance(res, dict):
            mode_text, = subfunc_file.get_remote_cfg(sw, mode, label="")
            no_patch_btn = _create_btn_in_(frame, mode_text)
            _pack_btn_right(no_patch_btn)
            no_patch_btn.set_state(CustomBtn.State.DISABLED)
            widget_utils.set_widget_tip_when_(tooltips, no_patch_btn, {msg: True})
        else:
            for patch_channel, patch_channel_res_dict in res.items():
                channel_des, = subfunc_file.get_remote_cfg(
                    sw, mode, RemoteCfg.CHANNELS, **{patch_channel: None})
                try:
                    channel_label = channel_des["label"]
                except KeyError:
                    channel_label = patch_channel
                try:
                    channel_tip = channel_des[RemoteCfg.INTRO] + f"  作者: {channel_des[RemoteCfg.AUTHOR]}"
                except KeyError:
                    channel_tip = "该方案尚无简介.  作者: 未知"
                patch_status = patch_channel_res_dict["status"]
                channel_msg = patch_channel_res_dict["msg"]
                patch_btn = _create_btn_in_(frame, f"{channel_label}")
                (patch_btn.set_bind_map(
                    **{"1": partial(switch_and_fresh_func, mode, patch_channel, coexist_channel, ordinal)})
                 .apply_bind(GlobalMembers.root_class.root))
                _pack_btn_right(patch_btn)
                if patch_status is True:
                    patch_btn.set_state(CustomBtn.State.SELECTED)
                if patch_status is None:
                    patch_btn.set_state(CustomBtn.State.DISABLED)
                    widget_utils.set_widget_tip_when_(tooltips, patch_btn, {channel_msg: True})
                else:
                    widget_utils.set_widget_tip_when_(tooltips, patch_btn, {channel_tip: True})

    threading.Thread(target=_thread).start()


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
        self.wnd_width, self.wnd_height = Config.EXE_MNG_WND_SIZE

    def load_ui(self):
        self.exe_manager_ui = ExeManagerUI(self.wnd, self.wnd_frame)
        self.exe_manager_ui.load_ui()
        pass

    def update_content(self):
        ...


class ExeManagerUI:
    def __init__(self, wnd, frame):
        self.patching_frame = {}
        self.content_frame = None
        self.top_bar_frame = None
        self.progress_bar = None
        self.main_header_frame = None
        self.create_coexist_btn = None
        self.coexist_channel_btn_dict = None
        self.tooltips = {}
        self.coexist_selector_frame = None
        self.cs_occupy_frame = None
        self._coexist_selector_visibility = False
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
                "func": self.thread_to_del_coexist_exe_of_accounts,
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
                "func": self.thread_to_del_coexist_accounts_history,
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
                "func": self.thread_to_rebuild_coexist_exes,
                "enable_scopes":
                    Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(1, None)]),
                "tip_scopes_dict": {
                    "请选择要重建的共存":
                        Condition(None, Condition.ConditionType.OR_INT_SCOPE, [(0, 0)])
                },
                "negative": False
            }
        }


    def load_ui(self):
        self._create_general_framework()
        self.create_em_ui()

    def update_ui(self):
        self.refresh_em_ui()

    def _create_general_framework(self):
        """搭建总体框架"""
        self.top_bar_frame = ttk.Frame(self.ui_frame)
        self.top_bar_frame.config(height=10)
        self.top_bar_frame.pack_propagate(False)
        self.top_bar_frame.pack(side="top", fill="x")
        self.progress_bar = TopProgressBar(self.top_bar_frame)

        bottom_frame = ttk.Frame(self.ui_frame)
        bottom_frame.pack(**Config.B_FRM_PACK)
        refresh_btn = CustomCornerBtn(bottom_frame, "刷新")
        refresh_btn.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        bottom_frame.grid_columnconfigure(0, weight=1)
        refresh_btn.set_bind_map(**{"1": self.refresh_em_ui}).apply_bind(self.root)

        self.content_frame = ttk.Frame(self.ui_frame)
        self.content_frame.pack(fill="both", expand=True)
        # 创建一个可以滚动的画布，并放置一个主框架在画布上
        self.scrollable_canvas = ScrollableCanvasW(self.content_frame)
        self.main_frame = self.scrollable_canvas.main_frame

    def create_em_ui(self):
        """创建主要内容"""
        # 第一行放主程序, 右边是防撤回区域, 新建共存按钮, 共存方案展开按钮
        main_header_frame = ttk.Frame(self.main_frame)
        main_header_frame.pack(side="top", fill="x")
        self.main_header_frame = main_header_frame
        self._refresh_header_frame()
        # - 共存选择器
        self.cs_occupy_frame = ttk.Frame(self.main_frame)
        self.cs_occupy_frame.pack(side="top", fill="x")
        self.coexist_selector_frame = ttk.Frame(self.cs_occupy_frame)  # 默认不pack
        self.thread_to_refresh_coexist_selector_frame()
        # 添加占位控件
        self.table_frames[CfgStatus.USING] = ttk.Frame(self.main_frame)
        self.table_frames[CfgStatus.USING].pack(side="top", fill="x")
        self.table_frames[CfgStatus.HISTORY] = ttk.Frame(self.main_frame)
        self.table_frames[CfgStatus.HISTORY].pack(side="top", fill="x")
        # 加载当前使用和历史记录
        self.classic_table_class[CfgStatus.USING] = ExeManagerCAHT(
            self, self.table_frames[CfgStatus.USING], CfgStatus.USING.value,
            "当前使用：", None,
            self.btn_dict["del_exe_btn"].copy(),
            self.btn_dict["rebuild_exe_btn"].copy())
        self.classic_table_class[CfgStatus.HISTORY] = ExeManagerCAHT(
            self, self.table_frames[CfgStatus.HISTORY], CfgStatus.HISTORY.value,
            "历史记录：", None,
            self.btn_dict["del_history_btn"].copy(),
            self.btn_dict["rebuild_exe_btn"].copy())

    def refresh_em_ui(self):
        def slowly_refresh():
            if isinstance(self.main_frame, (ttk.Frame, tk.Frame)) and self.main_frame.winfo_exists():
                Printer().vital("刷新页面")
                for widget in self.main_frame.winfo_children():
                    widget.destroy()
            self.coexist_channel_btn_dict.clear()
            self.create_em_ui()
        slowly_refresh()
        Printer().print_vn("加载完成!")

    def _refresh_header_frame(self):
        """刷新头部主程序区域"""
        main_header_frame = self.main_header_frame
        # 清空头部界面
        for widget in main_header_frame.winfo_children():
            widget.destroy()
        # - 主程序标签
        main_exe_label = ttk.Label(main_header_frame, text="主程序:", style='FirstTitle.TLabel')
        main_exe_label.pack(side="left", fill="x", anchor="w",
                            padx=Config.LOG_IO_FRM_PAD_X, pady=Config.LOG_IO_LBL_PAD_Y)
        # - 选择按钮
        show_coexist_channel_btn = _create_square_btn_in(main_header_frame, "···")
        (show_coexist_channel_btn.set_bind_map(
            **{"1": self._toggle_coexist_selector_visibility})
         .apply_bind(self.root))
        _pack_btn_right(show_coexist_channel_btn)
        # - 新建按钮
        self.create_coexist_btn = _create_btn_in_(main_header_frame, "新建")
        (self.create_coexist_btn.set_bind_map(
            **{"1": self._thread_to_create_coexist_exe})
         .apply_bind(self.root))
        _pack_btn_right(self.create_coexist_btn)
        # - 防撤回区域及按钮
        anti_revoke_frame = ttk.Frame(main_header_frame)
        anti_revoke_frame.pack(side="right")
        self.patching_frame[RemoteCfg.REVOKE.value] = anti_revoke_frame
        self._reload_patching_buttons(RemoteCfg.REVOKE.value)
        # - 多开区域及按钮
        multi_frame = ttk.Frame(main_header_frame)
        multi_frame.pack(side="right")
        self.patching_frame[RemoteCfg.MULTI.value] = multi_frame
        self._reload_patching_buttons(RemoteCfg.MULTI.value)

    def _reload_patching_buttons(self, mode):
        """重新加载补丁区按钮"""
        frame = self.patching_frame[mode]
        for btn in self.patching_frame[mode].winfo_children():
            btn.destroy()
        _create_and_pack_vertical_line_btn_in_(frame)  # 分割线
        _thread_to_load_patching_button(
            self, self.sw, mode, frame, self.tooltips,
            self._thread_to_switch_main_dll_and_refresh)

    def _refresh_coexist_selector_frame(self):
        """刷新共存方案切换器内容"""
        # 获取当前的选择并决定新建按钮是否可用
        now_coexist_channel, channels_res_dict, msg = SwInfoFunc.identity_and_get_available_coexist_mode(self.sw)
        if len(channels_res_dict) == 0 or now_coexist_channel is None:
            self.create_coexist_btn.set_state(CustomBtn.State.DISABLED)
        try:
            # 设置缓存按钮中的已选择按钮, 其余设为正常
            if len(channels_res_dict) != len(self.coexist_channel_btn_dict):
                raise FlowControlError
            self.coexist_channel_btn_dict[now_coexist_channel].set_state(CustomBtn.State.SELECTED)
            for channel in channels_res_dict:
                if channel != now_coexist_channel:
                    self.coexist_channel_btn_dict[channel].set_state(CustomBtn.State.NORMAL)
        except (KeyError, TypeError, FlowControlError):
            print("共存选择列表改变, 重建页面...")
            # 清空界面
            for widget in self.coexist_selector_frame.winfo_children():
                widget.destroy()
            self.coexist_channel_btn_dict = {}
            for coexist_channel, coexist_channel_dict in channels_res_dict.items():
                cc_label, = subfunc_file.get_remote_cfg(
                    self.sw, RemoteCfg.COEXIST, RemoteCfg.CHANNELS, coexist_channel, label=None)

                coexist_channel_btn = _create_btn_in_(self.coexist_selector_frame, f"{cc_label}")
                self.coexist_channel_btn_dict[coexist_channel] = coexist_channel_btn
                (coexist_channel_btn.set_bind_map(
                    **{"1": partial(
                        subfunc_file.save_a_setting_and_callback, self.sw,
                        LocalCfg.COEXIST_MODE.value, coexist_channel, self.thread_to_refresh_coexist_selector_frame)})
                 .apply_bind(self.root))
                _pack_btn_right(coexist_channel_btn)
                coexist_status = coexist_channel_dict["status"]
                if coexist_status is not True:
                    coexist_channel_btn.set_state(CustomBtn.State.DISABLED)
            self.coexist_channel_btn_dict[now_coexist_channel].set_state(CustomBtn.State.SELECTED)
        finally:
            self.progress_bar.finished()

    def _toggle_coexist_selector_visibility(self):
        """[...]按钮功能: 切换共存方案选择器的显示状态"""
        visible = self._coexist_selector_visibility = not self._coexist_selector_visibility
        if visible is False:
            self.coexist_selector_frame.pack_forget()
            self.cs_occupy_frame.config(height=1)
        else:
            self.cs_occupy_frame.pack_propagate(True)  # 自动调整自身大小
            self.coexist_selector_frame.pack(side="top", fill="x")

    def thread_to_refresh_coexist_selector_frame(self):
        """[(共存方案)]按钮功能: 刷新共存方案切换器内容"""
        @with_progress_factory(self)
        def _thread():
            self._refresh_coexist_selector_frame()
        threading.Thread(target=_thread).start()

    def _thread_to_create_coexist_exe(self):
        """[新建]按钮功能: 新建共存程序"""
        @with_progress_factory(self)
        def _thread():
            new_exe, _ = SwOperator.create_coexist_exe_core(self.sw)
            self.root.after(0, self.classic_table_class[CfgStatus.USING].update_coexist_rows, [new_exe])
            self.root.after(0, self.classic_table_class[CfgStatus.HISTORY].del_coexist_rows, [new_exe])
        threading.Thread(target=_thread).start()

    def _thread_to_switch_main_dll_and_refresh(self, mode, channel, coexist_channel=None, ordinal=None):
        """[(补丁方案)]按钮功能: 切换选中的补丁方案的状态"""
        @with_progress_factory(self)
        def _thread():
            SwOperator.switch_dll(self.sw, mode, channel, coexist_channel, ordinal)
            self.root.after(0, self._reload_patching_buttons, mode)
        threading.Thread(target=_thread).start()

    def thread_to_del_coexist_exe_of_accounts(self, items: list):
        """[×]按钮功能: 删除选中的共存程序"""
        @with_progress_factory(self)
        def _thread():
            accounts = [item.split("/")[1] for item in items]
            deleted_accs, failed_msg_dict = SwOperator.del_coexist_exe(self.sw, accounts)
            if len(failed_msg_dict) > 0:
                msg_str = "\n".join(f"{acc}: {failed_msg_dict[acc]}" for acc in failed_msg_dict)
                self.root.after(0, messagebox.showerror, "失败", f"失败账号及原因:\n{msg_str}")
            self.root.after(0, self.classic_table_class[CfgStatus.USING.value].del_coexist_rows, deleted_accs)
            self.root.after(0, self.classic_table_class[CfgStatus.HISTORY.value].update_coexist_rows, deleted_accs)
        threading.Thread(target=_thread).start()

    def thread_to_rebuild_coexist_exes(self, items: list):
        """[重建]按钮功能: 重建选中的共存程序"""
        @with_progress_factory(self)
        def _thread():
            accounts = [item.split("/")[1] for item in items]
            exes = SwOperator.rebuild_coexist_exes(self.sw, accounts)
            # 刷新使用中的共存程序列表
            self.root.after(
                0, self.classic_table_class[CfgStatus.USING.value].update_coexist_rows, exes)
            self.root.after(0, self.classic_table_class[CfgStatus.HISTORY.value].del_coexist_rows, exes)
        threading.Thread(target=_thread).start()

    def thread_to_del_coexist_accounts_history(self, items: list):
        """[×]按钮功能: 删除选中的账号的记录"""
        @with_progress_factory(self)
        def _thread():
            accounts = [item.split("/")[1] for item in items]
            del_accs = []
            sw_acc_dict = subfunc_file.get_sw_acc_data(self.sw)
            for acc in accounts:
                if isinstance(sw_acc_dict, dict):
                    del sw_acc_dict[acc]
                    del_accs.append(acc)
            subfunc_file.update_sw_acc_data(**{self.sw: sw_acc_dict})
            self.root.after(0, self.classic_table_class[CfgStatus.HISTORY.value].del_coexist_rows, del_accs)
        threading.Thread(target=_thread).start()


class ExeManagerCAHT(ClassicAHT):
    def __init__(self, parent_class, parent_frame, table_tag, title_text, major_btn_dict, *rest_btn_dicts):
        """用于展示不同登录状态列表的表格"""
        self.sw = None
        self.exe_manager_ui = None
        super().__init__(parent_class, parent_frame, table_tag, title_text, major_btn_dict, *rest_btn_dicts)

    def initialize_members_in_init(self):
        self.sw = self.parent_class.sw
        self.exe_manager_ui = self.parent_class
        pass

    def load_form(self):
        self._create_coexist_exe_rows()

    def update_form(self):
        for widget in self.form_frame.winfo_children():
            widget.destroy()
        print(f"刷新表单: {self.table_tag}")
        self._create_coexist_exe_rows()

    def _create_coexist_exe_rows(self):
        self.rows.clear()
        existed_coexist_accs = SwInfoFunc.get_sw_all_accounts_existed(self.sw, only="coexist")
        if self.table_tag == CfgStatus.USING.value:
            # "当前使用"的数据来源: 获取所有的原生账号
            existed_coexist_accs.sort()
            all_items = existed_coexist_accs
        elif self.table_tag == CfgStatus.HISTORY.value:
            # "历史记录"的数据来源: 记录中的所有共存账号 - 当前使用的账号
            all_coexist_accs = [
                acc for acc in subfunc_file.get_sw_acc_data(self.sw)
                if AccInfoFunc.is_acc_coexist(self.sw, acc)
            ]
            history_accs = list(set(all_coexist_accs) - set(existed_coexist_accs))
            history_accs.sort()
            all_items = history_accs
        else:
            all_items = []

        for row_id in all_items:
            row = ExeManagerCkRow(self, self.form_frame, row_id, self.table_tag)
            self.rows[row_id] = row
        self.null_data = True if len(self.rows) == 0 else False

    def update_coexist_rows(self, row_ids):
        for row_id in row_ids:
            if row_id not in self.rows:
                row = ExeManagerCkRow(self, self.form_frame, row_id, self.table_tag)
                self.rows[row_id] = row
            else:
                # 单行的刷新
                self.rows[row_id].update_row()
        self._adjust()

    def del_coexist_rows(self, row_ids):
        for row_id in row_ids:
            if row_id in self.rows:
                self.rows[row_id].row_frame.destroy()
                del self.rows[row_id]
        self._adjust()

    def reformat_selected_items(self):
        """
        将选中的iid进行格式处理
        """
        self.selected_items = [f"{self.sw}/{item}" for item in self.selected_items_original]
        print(self.selected_items)


class ExeManagerCkRow(CkbRow):
    def __init__(self, parent_class, parent_frame, item, table_tag):
        self.progress_bar = None
        self.patching_frame = {}
        self.btn_frame = None
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

    def load_row_content(self):
        self._create_coexist_row()

    def update_row_content(self):
        for widget in self.row_frame.winfo_children():
            widget.destroy()
        self._create_coexist_row()

    def adjust_row(self):
        self._adjust_coexist_row()

    def _create_coexist_row(self):
        account = self.item

        # 账号详情
        details = AccInfoFunc.get_acc_details(self.sw, account)
        iid = details[AccKeys.IID]
        img = details[AccKeys.AVATAR]
        display_name = details[AccKeys.DISPLAY]
        config_status = details[AccKeys.CONFIG_STATUS]
        coexist_channel, ordinal = subfunc_file.get_sw_acc_data(
            self.sw, account, channel=None, **{AccKeys.ORDINAL: None})

        # 对详情中的数据进行处理
        if config_status == CfgStatus.NO_CFG:
            self.disabled = True
        img = img.resize(Config.AVT_SIZE, Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        self.photo_images.append(photo)
        try:
            channel_label, = subfunc_file.get_remote_cfg(
                self.sw, RemoteCfg.COEXIST, RemoteCfg.CHANNELS, coexist_channel, label=None)
            channel_checked = channel_label is not None
            channel_label = channel_label if channel_checked else "??"
        except (KeyError, TypeError):
            channel_label = "??"
            channel_checked = False
        sequence_checked = isinstance(ordinal, str) and len(ordinal) == 1
        sequence_label = ordinal if sequence_checked else "?"
        index_label = f"{channel_label}[{sequence_label}]"
        has_precise_coexist_index = channel_checked and sequence_checked

        # 行框架=复选框+头像标签+账号标签+按钮区域+配置标签
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

        # 按钮区域
        btn_frame = ttk.Frame(self.row_frame)
        self.btn_frame = btn_frame
        btn_frame.pack(side="right")
        # - 删除按钮
        del_coexist_btn = _create_square_btn_in(btn_frame, "×")
        if self.table_tag == CfgStatus.USING:
            (del_coexist_btn.set_bind_map(
                **{"1": lambda: self.exe_manager_ui.thread_to_del_coexist_exe_of_accounts([iid])})
             .apply_bind(self.root))
        else:
            (del_coexist_btn.set_bind_map(
                **{"1": lambda: self.exe_manager_ui.thread_to_del_coexist_accounts_history([iid])})
             .apply_bind(self.root))
        _pack_btn_right(del_coexist_btn)
        _set_negative_style(del_coexist_btn)
        # - 重建按钮
        rebuild_coexist_btn = _create_btn_in_(btn_frame, "重建")
        (rebuild_coexist_btn.set_bind_map(
            **{"1": lambda: self.exe_manager_ui.thread_to_rebuild_coexist_exes([iid])})
         .apply_bind(self.root))
        _pack_btn_right(rebuild_coexist_btn)
        # - 防撤回按钮
        if self.table_tag == CfgStatus.USING:
            anti_revoke_frame = ttk.Frame(btn_frame)
            anti_revoke_frame.pack(side="right")
            self.patching_frame[RemoteCfg.REVOKE.value] = anti_revoke_frame
            # - 防撤回的按钮
            self._reload_patching_buttons(RemoteCfg.REVOKE.value, coexist_channel, ordinal)

        # 账号区域分两行, 上行是程序名称, 下行是账号名称
        self.item_frame = ttk.Frame(self.row_frame)
        self.item_frame.pack(side="left", fill="x")
        # 账号标签
        self.item_label = ttk.Label(self.item_frame, text=config_status)
        self.item_label.pack(fill="x", padx=Config.CLZ_ROW_LBL_PAD_X)
        exe_remark_text = f"{index_label}"
        if display_name != config_status:
            exe_remark_text += f"  {display_name}"
        # 程序链接了账号
        try:
            exe_remark_label = ttk.Label(
                self.item_frame, text=exe_remark_text, style="LittleGreyText.TLabel")
        except Exception as e:
            Logger().warning(e)
            exe_remark_label = ttk.Label(
                self.item_frame, text=StringUtils.clean_texts(exe_remark_text), style="LittleGreyText.TLabel")
        exe_remark_label.pack(side="bottom", fill="x", padx=Config.CLZ_ROW_LBL_PAD_X)
        # 设置控件状态
        CustomBtn.enable_custom_widget_when_(rebuild_coexist_btn, has_precise_coexist_index)
        # 设置提示
        widget_utils.set_widget_tip_when_(
            self.tooltips, rebuild_coexist_btn,
            {"未知共存索引": not has_precise_coexist_index}
        )

    def _reload_patching_buttons(self, mode, coexist_channel, ordinal):
        """重新加载补丁区按钮"""
        frame = self.patching_frame[mode]
        for btn in self.patching_frame[mode].winfo_children():
            btn.destroy()
        _create_and_pack_vertical_line_btn_in_(frame)  # 分割线
        if not isinstance(coexist_channel, str) or not isinstance(ordinal, str):
            no_anti_revoke_btn = _create_btn_in_(frame, "防撤")
            _pack_btn_right(no_anti_revoke_btn)
            no_anti_revoke_btn.set_state(CustomBtn.State.DISABLED)
            widget_utils.set_widget_tip_when_(self.tooltips, no_anti_revoke_btn, {"未知共存索引": True})
        else:
            _thread_to_load_patching_button(
                self, self.sw, RemoteCfg.REVOKE.value, frame, self.tooltips,
                self.thread_to_switch_coexist_dll_and_refresh, coexist_channel, ordinal)

    def thread_to_switch_coexist_dll_and_refresh(self, mode, channel, coexist_channel, ordinal):
        """[(补丁方案)]按钮功能: 切换选中的补丁方案的状态"""
        self.progress_bar = self.exe_manager_ui.progress_bar
        @with_progress_factory(self)
        def _thread():
            SwOperator.switch_dll(self.sw, mode, channel, coexist_channel, ordinal)
            self.root.after(0, self._reload_patching_buttons, mode, coexist_channel, ordinal)
        threading.Thread(target=_thread).start()

    def _adjust_coexist_row(self):
        # 绑定事件到控件范围内所有位置
        widget_utils.exclusively_bind_event_to_frame_when_(
            [self.btn_frame], self.row_frame, "<Button-1>", self.toggle_checkbox,
            Condition(self.disabled, Condition.ConditionType.NOT_EQUAL, True)
        )
