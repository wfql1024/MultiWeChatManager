import os
import threading
import time
import tkinter as tk
import webbrowser
from functools import partial
from pathlib import Path
from tkinter import messagebox, simpledialog

from legacy_python.functions import subfunc_file
from legacy_python.functions.app_func import AppFunc
from legacy_python.functions.main_func import MultiSwFunc
from legacy_python.functions.sw_func import SwInfoFunc, SwOperator
from legacy_python.public import Strings, Config
from legacy_python.public.enums import LocalCfg, MultirunMode, RemoteCfg, CallMode
from legacy_python.public.global_members import GlobalMembers
from legacy_python.ui.wnd_ui import WndCreator
from legacy_python.utils import widget_utils
from legacy_python.utils import sys_utils
from legacy_python.utils.logger_utils import mylogger as logger
from legacy_python.utils.logger_utils import myprinter as printer
from legacy_python.utils.sys_utils import Tk2Sys


# TODO: 用户可以自定义多开的全流程: 剩余: 指定点击按钮文字
# TODO: 主题色选择

class MenuUI:
    def __init__(self):
        """获取必要的设置项信息"""
        self.coexist_menu = None
        self._to_tray_label = None
        self.used_tray = None
        self.sidebar_menu_label = None
        print("构建菜单ui...")
        self.sw_class = None
        self.sw = None
        self.acc_tab_ui = None
        self.is_login_menu = None
        self.menu_updater = None
        self.multirun_menu_index = None
        self.anti_revoke_menu_index = None
        self.menu_queue = None
        self.start_time = None
        self.coexist_channel_menus_dict = {}
        self.multirun_channel_menus_dict = {}
        self.anti_revoke_channel_menus_dict = {}
        self.coexist_channel_radio_list = []
        self.multirun_channel_vars_dict = {}
        self.anti_revoke_channel_vars_dict = {}
        self.multirun_menu = None
        self.anti_revoke_menu = None
        self.freely_multirun_var = None
        self.sidebar_ui = None
        self.sidebar_wnd = None
        self.call_mode_menu = None
        self.auto_start_menu = None
        self.path_error = None
        self.multiple_err = None
        self.help_menu = None
        self.rest_mode_menu = None
        self.settings_menu = None
        self.wnd_scale_menu = None
        self.view_options_menu = None
        self.view_menu = None
        self.edit_menu = None
        self.statistic_menu = None
        self.program_file_menu = None
        self.config_file_menu = None
        self.user_file_menu = None
        self.file_menu = None
        self.menu_bar = None

        self.root_class = GlobalMembers.root_class
        self.root = self.root_class.root
        self.global_settings_value = self.root_class.global_settings_value
        self.global_settings_var = self.root_class.global_settings_var
        self.app_info = self.root_class.app_info
        self.sw_classes = self.root_class.sw_classes

    def create_root_menu_bar(self):
        """创建菜单栏"""
        # ————————————————————————————设置菜单————————————————————————————
        self.settings_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label="设置", menu=self.settings_menu)
        self._create_setting_menu()
        print(f"设置菜单用时：{time.time() - self.start_time:.4f}秒")



    def _create_setting_menu(self):
        ...

        if self.is_login_menu:
            # -应用设置
            self.settings_menu.add_separator()  # ————————————————分割线————————————————
            self.settings_menu.add_command(label="平台设置", command=partial(WndCreator.open_sw_settings, self.sw))
            self.coexist_menu = tk.Menu(self.settings_menu, tearoff=False)
            self.settings_menu.add_cascade(label="共存", menu=self.coexist_menu)
            self.anti_revoke_menu = tk.Menu(self.settings_menu, tearoff=False)
            self.settings_menu.add_cascade(label="防撤回", menu=self.anti_revoke_menu)
            self.multirun_menu = tk.Menu(self.settings_menu, tearoff=False)
            self.settings_menu.add_cascade(label="全局多开", menu=self.multirun_menu)
            self.settings_menu.add_separator()  # ————————————————分割线————————————————

            # 开启更新多开,防撤回等子菜单的更新线程
            self.update_settings_menu_thread()



    def _calc_multirun_mode_and_save(self, mode):
        """计算多开模式并保存"""
        subfunc_file.save_a_setting_and_callback(
            self.sw, LocalCfg.REST_MULTIRUN_MODE, mode, self.create_root_menu_bar)
        self.sw_class.multirun_mode = MultirunMode.FREELY_MULTIRUN if self.sw_class.can_freely_multirun is True else mode


    def _toggle_patch_mode(self, mode, channel):
        """切换是否全局多开或防撤回"""
        try:
            success, msg = SwOperator.switch_dll(self.sw, mode, channel)  # 执行切换操作
            if success:
                try:
                    channel_des, = subfunc_file.get_remote_cfg(
                        self.sw, mode, RemoteCfg.CHANNELS, **{channel: None})
                    channel_authors = channel_des["author"]
                    channel_label = channel_des["label"]
                except KeyError:
                    channel_authors = []
                    channel_label = ""
                if len(channel_authors) > 0:
                    author_text = ", ".join(channel_authors)
                    msg = f"{msg}\n鸣谢:{channel_label}方案特征码来自{author_text}"
                messagebox.showinfo("提示", f"{msg}")
            else:
                messagebox.showerror("错误", f"{msg}")
        except Exception as e:
            messagebox.showerror("错误", f"操作失败: {str(e)}")
            logger.error(f"发生错误: {str(e)}")
        finally:
            self.root_class.login_ui.refresh()



    def _introduce_channel(self, mode, channels_res_dict):
        text = ""
        for channel in channels_res_dict:
            channel_des, = subfunc_file.get_remote_cfg(
                self.sw, mode, RemoteCfg.CHANNELS, **{channel: None})
            try:
                channel_label = channel_des["label"]
                channel_introduce = channel_des["introduce"]
                channel_author = channel_des["author"]
            except KeyError:
                channel_label = channel
                channel_introduce = "暂无介绍"
                channel_author = "未知"
            text = f"[{channel_label}]\n{channel_introduce}\n作者：{channel_author}\n"
        messagebox.showinfo("简介", text)

    """更新多开,共存,防撤回子菜单的线程"""

    def _update_coexist_menu(self, mode_channels_res_dict, msg):
        # Printer().debug(mode_channels_res_dict)
        # 以有无适配为准; 若没有适配,检查是否是原生支持多开
        if mode_channels_res_dict is None:
            # 没有适配, 检查是否是原生支持多开
            native_coexist, = subfunc_file.get_remote_cfg(
                self.sw, RemoteCfg.COEXIST, **{RemoteCfg.NATIVE.value: None})
            if native_coexist is True:
                self.coexist_menu.add_command(label="无需共存", state="disabled")
            else:
                self.settings_menu.entryconfig("共存", label="！共存", foreground="red")
                self.coexist_menu.add_command(label=f"[点击复制]{msg}", foreground="red",
                                              command=lambda i=msg: Tk2Sys.copy_to_clipboard(self.root, i))
        else:
            self.coexist_menu.add_command(label="请选择一个开启:", state="disabled")
            self.coexist_channel_var = tk.StringVar()
            for channel, channel_res_dict in mode_channels_res_dict.items():
                try:
                    channel_des, = subfunc_file.get_remote_cfg(
                        self.sw, RemoteCfg.COEXIST.value, RemoteCfg.CHANNELS, **{channel: None})
                    channel_label = channel_des["label"]
                except KeyError:
                    channel_label = channel
                coexist_status = channel_res_dict["status"]
                channel_msg = channel_res_dict["msg"]
                if coexist_status is not True:
                    menu = self.coexist_channel_menus_dict[channel] = tk.Menu(
                        self.coexist_menu, tearoff=False)
                    self.coexist_menu.add_cascade(label=channel_label, menu=menu)
                    menu.add_command(label=f"[点击复制]{channel_msg}", foreground="red",
                                     command=lambda i=channel_msg: Tk2Sys.copy_to_clipboard(self.root, i))
                else:
                    self.coexist_menu.add_radiobutton(
                        label=channel_label,
                        value=channel,
                        variable=self.coexist_channel_var,
                        command=partial(
                            subfunc_file.save_a_setting_and_callback,
                            self.sw, LocalCfg.COEXIST_MODE.value, channel, self.create_root_menu_bar),
                    )
                    self.coexist_channel_radio_list.append(channel)
            current_coexist_mode = subfunc_file.fetch_sw_setting_or_set_default_or_none(
                self.sw, LocalCfg.COEXIST_MODE.value)
            # 如果这个模式在单选值列表中,则选择这个值,否则选择第一个值
            if current_coexist_mode in self.coexist_channel_radio_list:
                # Printer().debug("该模式在单选列表中...")
                self.coexist_channel_var.set(current_coexist_mode)
            else:
                if len(self.coexist_channel_radio_list) > 0:
                    # Printer().debug("该模式不在单选列表中...")
                    self.coexist_channel_var.set(self.coexist_channel_radio_list[0])

            # 频道简介菜单
            self.coexist_menu.add_separator()  # ————————————————分割线————————————————
            self.coexist_menu.add_command(
                label="怎么选?", command=partial(
                    self._introduce_channel, RemoteCfg.COEXIST.value, mode_channels_res_dict))
        self.coexist_menu.add_separator()  # ————————————————分割线————————————————
        self.coexist_menu.add_command(
            label="清除缓存",
            command=partial(self._clear_cache, RemoteCfg.COEXIST.value))
        printer.print_last()

    def _update_anti_revoke_menu(self, mode_channels_res_dict, msg):
        # 原来的防撤回菜单创建代码
        # Printer().debug(mode_channels_res_dict)
        if mode_channels_res_dict is None:
            self.settings_menu.entryconfig("防撤回", label="！防撤回", foreground="red")
            self.anti_revoke_menu.add_command(label=f"[点击复制]{msg}", foreground="red",
                                              command=lambda i=msg: Tk2Sys.copy_to_clipboard(self.root, i))
        else:
            self.anti_revoke_menu.add_command(label="请选择一个开启:", state="disabled")
            for channel, channel_res_dict in mode_channels_res_dict.items():
                try:
                    channel_des, = subfunc_file.get_remote_cfg(
                        self.sw, RemoteCfg.REVOKE.value, RemoteCfg.CHANNELS, **{channel: None})
                    channel_label = channel_des["label"]
                except KeyError:
                    channel_label = channel
                anti_revoke_status = channel_res_dict["status"]
                channel_msg = channel_res_dict["msg"]
                if anti_revoke_status is None:
                    menu = self.anti_revoke_channel_menus_dict[channel] = tk.Menu(
                        self.anti_revoke_menu, tearoff=False)
                    self.anti_revoke_menu.add_cascade(label=channel_label, menu=menu)
                    menu.add_command(label=f"[点击复制]{channel_msg}", foreground="red",
                                     command=lambda i=channel_msg: Tk2Sys.copy_to_clipboard(self.root, i))
                else:
                    self.anti_revoke_channel_vars_dict[channel] = tk.BooleanVar(value=anti_revoke_status)
                    self.anti_revoke_menu.add_checkbutton(
                        label=channel_label, variable=self.anti_revoke_channel_vars_dict[channel],
                        command=partial(self._toggle_patch_mode, mode=RemoteCfg.REVOKE, channel=channel))
            self.anti_revoke_menu.add_separator()  # ————————————————分割线————————————————
            # 频道简介菜单
            self.anti_revoke_menu.add_command(
                label="怎么选?",
                command=partial(self._introduce_channel, RemoteCfg.REVOKE.value, mode_channels_res_dict))
        self.anti_revoke_menu.add_separator()  # ————————————————分割线————————————————
        self.anti_revoke_menu.add_command(
            label="清除缓存",
            command=partial(self._clear_cache, RemoteCfg.REVOKE.value))
        printer.print_last()

    def _update_multirun_menu(self, mode_channels_res_dict, msg):
        self.sw_class.can_freely_multirun = None
        # 以有无适配为准; 若没有适配,检查是否是原生支持多开
        if mode_channels_res_dict is None:
            # 没有适配, 检查是否是原生支持多开
            native_multirun, = subfunc_file.get_remote_cfg(
                self.sw, RemoteCfg.MULTI, **{RemoteCfg.NATIVE.value: None})
            if native_multirun is True:
                self.sw_class.can_freely_multirun = True
                self.multirun_menu.add_command(label="原生支持多开", state="disabled")
            else:
                self.settings_menu.entryconfig("全局多开", label="！全局多开", foreground="red")
                self.multirun_menu.add_command(label=f"[点击复制]{msg}", foreground="red",
                                               command=lambda i=msg: Tk2Sys.copy_to_clipboard(self.root, i))
        else:
            self.multirun_menu.add_command(label="请选择一个开启:", state="disabled")
            # 列出所有频道
            for channel, channel_res_dict in mode_channels_res_dict.items():
                try:
                    channel_des, = subfunc_file.get_remote_cfg(
                        self.sw, RemoteCfg.MULTI.value, RemoteCfg.CHANNELS, **{channel: None})
                    channel_label = channel_des["label"]
                except KeyError:
                    channel_label = channel
                freely_multirun_status = channel_res_dict["status"]
                channel_msg = channel_res_dict["msg"]
                if freely_multirun_status is None:
                    menu = self.multirun_channel_menus_dict[channel] = tk.Menu(
                        self.multirun_menu, tearoff=False)
                    self.multirun_menu.add_cascade(label=channel_label, menu=menu)
                    menu.add_command(label=f"[点击复制]{channel_msg}", foreground="red",
                                     command=lambda i=channel_msg: Tk2Sys.copy_to_clipboard(self.root, i))
                else:
                    # 只要有freely_multirun为True，就将其设为True
                    if freely_multirun_status is True:
                        self.sw_class.can_freely_multirun = True
                    self.multirun_channel_vars_dict[channel] = tk.BooleanVar(value=freely_multirun_status)
                    self.multirun_menu.add_checkbutton(
                        label=channel_label, variable=self.multirun_channel_vars_dict[channel],
                        command=partial(self._toggle_patch_mode, mode=RemoteCfg.MULTI, channel=channel))
            self.multirun_menu.add_separator()  # ————————————————分割线————————————————
            # 频道简介菜单
            self.multirun_menu.add_command(
                label="怎么选?",
                command=partial(self._introduce_channel, RemoteCfg.MULTI.value, mode_channels_res_dict))
        self.multirun_menu.add_separator()  # ————————————————分割线————————————————

        # >多开子程序选择
        # 得出使用的多开模式,若开了全局多开,则使用全局多开模式,否则使用其他模式
        if self.sw_class.can_freely_multirun:
            self.sw_class.multirun_mode = MultirunMode.FREELY_MULTIRUN
            self.multirun_menu.add_command(label="非全局多开使用", state="disabled")
        else:
            self.rest_mode_menu = tk.Menu(self.multirun_menu, tearoff=False)
            self.multirun_menu.add_cascade(label="非全局多开使用", menu=self.rest_mode_menu)
            rest_mode_value = self.global_settings_value.rest_mode = subfunc_file.fetch_sw_setting_or_set_default_or_none(
                self.sw, LocalCfg.REST_MULTIRUN_MODE)
            # print("当前项", rest_mode_value)
            self.sw_class.multirun_mode = rest_mode_value
            rest_mode_var = self.global_settings_var.rest_mode = tk.StringVar(value=rest_mode_value)  # 设置初始选中的子程序
            # 添加 Python 的单选按钮
            self.rest_mode_menu.add_radiobutton(
                label='内置',
                value='内置',
                variable=rest_mode_var,
                command=partial(self._calc_multirun_mode_and_save, MultirunMode.BUILTIN.value),
            )
            # 动态添加外部子程序
            external_res_path = Config.PROJ_EXTERNAL_RES_PATH
            exe_files = [str(p) for p in Path(external_res_path).rglob(f"{self.sw}Multiple_*.exe")]
            if len(exe_files) != 0:
                self.rest_mode_menu.add_separator()  # ————————————————分割线————————————————
                for exe_file in exe_files:
                    exe_name = os.path.basename(exe_file)
                    right_part = exe_name.split('_', 1)[1].rsplit('.exe', 1)[0]
                    self.rest_mode_menu.add_radiobutton(
                        label=right_part,
                        value=exe_name,
                        variable=rest_mode_var,
                        command=partial(self._calc_multirun_mode_and_save, exe_name),
                    )
        self.multirun_menu.add_separator()  # ————————————————分割线————————————————
        self.multirun_menu.add_command(
            label="清除缓存",
            command=partial(self._clear_cache, RemoteCfg.MULTI.value))
        printer.print_last()

    def update_settings_menu_thread(self):
        threading.Thread(target=self._identify_dll_and_update_menu).start()

    def _identify_dll_and_update_menu(self):
        """实现抽象方法（原_create_menus_thread逻辑）"""
        print("更新设置菜单...")
        try:
            # 共存部分
            res_dict, msg = SwInfoFunc.identify_dll(
                self.sw, RemoteCfg.COEXIST.value, True)
            self.root.after(0, self._update_coexist_menu, res_dict, msg)
            # 防撤回部分
            res_dict, msg = SwInfoFunc.identify_dll(
                self.sw, RemoteCfg.REVOKE.value)
            self.root.after(0, self._update_anti_revoke_menu, res_dict, msg)
            # 全局多开部分
            res_dict, msg = SwInfoFunc.identify_dll(
                self.sw, RemoteCfg.MULTI.value)
            self.root.after(0, self._update_multirun_menu, res_dict, msg)
        except Exception as e:
            print(e)
