import os
import time
import tkinter as tk
import webbrowser
from functools import partial
from pathlib import Path
from tkinter import messagebox, simpledialog

from legacy_python.functions import subfunc_file
from legacy_python.functions.app_func import AppFunc, GlobalSettings
from legacy_python.functions.main_func import MultiSwFunc
from legacy_python.functions.sw_func import SwOperator, SwInfoFunc
from legacy_python.public import Strings, Config
from legacy_python.public.enums import LocalCfg, MultirunMode, CallMode
from legacy_python.public.global_members import GlobalMembers
from legacy_python.ui.exe_manager_ui import ExeManagerWndCreator
from legacy_python.ui.wnd_ui import WndCreator
from legacy_python.utils import widget_utils
from legacy_python.utils import sys_utils
from legacy_python.utils.logger_utils import myprinter as printer


# TODO: 用户可以自定义多开的全流程: 剩余: 登录结束后的流程
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
        self.global_settings_value: GlobalSettings = AppFunc.get_global_settings_value_obj()
        self.global_settings_var: GlobalSettings = AppFunc.get_global_settings_var_obj()
        self.app_info = self.root_class.app_info
        self.sw_classes = self.root_class.sw_classes

    def create_root_menu_bar(self):
        """创建菜单栏"""
        root_tab = AppFunc.get_global_setting_value_by_local_record(LocalCfg.ROOT_TAB)
        self.is_login_menu = root_tab == "login"
        if self.is_login_menu:
            self.acc_tab_ui = self.root_class.login_ui
            self.sw = self.acc_tab_ui.sw
            self.sw_class = self.sw_classes[self.sw]

            # 传递错误信息给主窗口
            if self.sw_class.inst_path is None or self.sw_class.data_dir is None or self.sw_class.dll_dir is None:
                print("路径设置错误...")
                self.acc_tab_ui.path_error = True

        print("创建菜单栏...")
        self.start_time = time.time()

        if not isinstance(self.menu_bar, tk.Menu):
            self.menu_bar = tk.Menu(self.root)
            self.root.config(menu=self.menu_bar)

        self.menu_bar.delete(0, tk.END)

        # ————————————————————————————侧栏菜单————————————————————————————
        used_sidebar = AppFunc.get_global_setting_value_by_local_record(LocalCfg.USED_SIDEBAR)
        suffix = "" if used_sidebar is True else Strings.SIDEBAR_HINT
        label = "❯" if self.sidebar_wnd is not None and self.sidebar_wnd.winfo_exists() else "❮"
        self.sidebar_menu_label = f"{label}{suffix}"
        self.menu_bar.add_command(label=self.sidebar_menu_label, command=partial(self._open_sidebar))
        # ————————————————————————————文件菜单————————————————————————————
        self.file_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label="文件", menu=self.file_menu)
        # >用户文件
        self.user_file_menu = tk.Menu(self.file_menu, tearoff=False)
        self.file_menu.add_cascade(label="用户文件", menu=self.user_file_menu)
        self.user_file_menu.add_command(label="打开", command=AppFunc.open_user_file)
        self.user_file_menu.add_command(label="清除", command=partial(
            AppFunc.clear_user_file, self.root_class.reinit_root_ui))
        # >程序目录
        self.program_file_menu = tk.Menu(self.file_menu, tearoff=False)
        self.file_menu.add_cascade(label="程序目录", menu=self.program_file_menu)
        self.program_file_menu.add_command(label="打开", command=AppFunc.open_program_file)
        self.program_file_menu.add_command(label="删除旧版备份",
                                           command=partial(AppFunc.mov_backup))
        # -创建软件快捷方式
        self.file_menu.add_command(label="创建程序快捷方式", command=AppFunc.create_app_lnk)

        # -导入旧版数据
        self.file_menu.add_command(label="导入旧版数据", command=AppFunc.migrate_old_user_files)

        if self.is_login_menu:
            self.file_menu.add_separator()  # ————————————————分割线————————————————
            # >统计数据
            self.statistic_menu = tk.Menu(self.file_menu, tearoff=False)
            self.file_menu.add_cascade(label="统计", menu=self.statistic_menu)
            self.statistic_menu.add_command(label="查看", command=partial(WndCreator.open_statistic, self.sw))
            self.statistic_menu.add_command(label="清除",
                                            command=partial(AppFunc.clear_statistic_data,
                                                            self.create_root_menu_bar))
            # >配置文件
            self.config_file_menu = tk.Menu(self.file_menu, tearoff=False)
            if not self.sw_class.data_dir:
                self.file_menu.add_command(label="配置文件  未获取")
                self.file_menu.entryconfig(f"配置文件  未获取", state="disable")
            else:
                self.file_menu.add_cascade(label="配置文件", menu=self.config_file_menu)
                self.config_file_menu.add_command(label="打开",
                                                  command=partial(SwOperator.open_config_file, self.sw))
                self.config_file_menu.add_command(label="清除",
                                                  command=partial(SwOperator.clear_config_file, self.sw,
                                                                  self.root_class.login_ui.refresh))
            # -打开主dll所在文件夹
            self.file_menu.add_command(label="查看DLL目录", command=partial(SwOperator.open_dll_dir, self.sw))
            if self.sw_class.dll_dir is None:
                self.file_menu.entryconfig(f"查看DLL目录", state="disable")
            print(f"文件菜单用时：{time.time() - self.start_time:.4f}秒")

        # ————————————————————————————编辑菜单————————————————————————————
        self.edit_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label="编辑", menu=self.edit_menu)
        # -刷新
        self.edit_menu.add_command(label="快速刷新", command=self.root_class.main_ui.refresh_current_tab)
        self.edit_menu.add_command(
            label="刷新", command=partial(self.root_class.main_ui.refresh_current_tab, False))
        self.edit_menu.add_separator()  # ————————————————分割线————————————————
        self.edit_menu.add_command(label="热更新", command=self._to_update_remote_cfg)
        self.edit_menu.add_separator()  # ————————————————分割线————————————————
        self.edit_menu.add_command(label="初始化", command=self._to_initialize)
        print(f"编辑菜单用时：{time.time() - self.start_time:.4f}秒")

        # ————————————————————————————视图菜单————————————————————————————
        self.view_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label="视图", menu=self.view_menu)
        if self.is_login_menu:
            # 视图单选
            view_value = self.global_settings_value.view = SwInfoFunc.get_sw_setting_by_local_record(
                self.sw, "view")
            view_var = self.global_settings_var.view = tk.StringVar(value=view_value)

            self.view_menu.add_radiobutton(label="经典", variable=view_var, value="classic",
                                           command=self._switch_to_classic_view)
            self.view_menu.add_radiobutton(label="列表", variable=view_var, value="tree",
                                           command=self._switch_to_tree_view)
            self.view_menu.add_separator()  # ————————————————分割线————————————————
        # 全局菜单:缩放+选项
        # 视图选项
        self.view_options_menu = tk.Menu(self.view_menu, tearoff=False)
        self.view_menu.add_cascade(label=f"视图选项", menu=self.view_options_menu)
        sign_vis_value = self.global_settings_value.sign_vis = \
            AppFunc.get_global_setting_value_by_local_record(LocalCfg.SIGN_VISIBLE)
        sign_vis_var = self.global_settings_var.sign_vis = tk.BooleanVar(value=sign_vis_value)
        self.view_options_menu.add_checkbutton(
            label="显示状态标志", variable=sign_vis_var,
            command=partial(AppFunc.save_a_global_setting_and_callback,
                            LocalCfg.SIGN_VISIBLE, not self.global_settings_value.sign_vis,
                            self.root_class.login_ui.refresh)
        )
        use_txt_avt = self.global_settings_value.use_txt_avt = \
            AppFunc.get_global_setting_value_by_local_record(LocalCfg.USE_TXT_AVT)
        use_txt_avt_var = self.global_settings_var.use_txt_avt = tk.BooleanVar(value=use_txt_avt)
        self.view_options_menu.add_checkbutton(
            label="使用文字头像", variable=use_txt_avt_var,
            command=partial(AppFunc.save_a_global_setting_and_callback,
                            LocalCfg.USE_TXT_AVT, not use_txt_avt,
                            self.root_class.login_ui.refresh)
        )
        scale_value = self.global_settings_value.scale = AppFunc.get_global_setting_value_by_local_record(
            "scale")
        scale_var = self.global_settings_var.scale = tk.StringVar(value=scale_value)
        self.wnd_scale_menu = tk.Menu(self.view_menu, tearoff=False)
        self.view_menu.add_cascade(label=f"窗口缩放", menu=self.wnd_scale_menu)
        self.wnd_scale_menu.add_radiobutton(label="跟随系统", variable=scale_var, value="auto",
                                            command=partial(self._set_wnd_scale, "auto"))
        options = ["100", "125", "150", "175", "200"]
        for option in options:
            self.wnd_scale_menu.add_radiobutton(label=f"{option}%", variable=scale_var, value=option,
                                                command=partial(self._set_wnd_scale, option))
        if scale_value != "auto" and scale_value not in options:
            self.wnd_scale_menu.add_radiobutton(label=f"自定义:{scale_value}%",
                                                variable=scale_var, value=scale_value,
                                                command=partial(self._set_wnd_scale))
        else:
            self.wnd_scale_menu.add_radiobutton(label=f"自定义",
                                                variable=scale_var, value="0",
                                                command=partial(self._set_wnd_scale))
        print(f"视图菜单用时：{time.time() - self.start_time:.4f}秒")

        # ————————————————————————————设置菜单————————————————————————————
        self.settings_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label="设置", menu=self.settings_menu)
        self._create_setting_menu()
        print(f"设置菜单用时：{time.time() - self.start_time:.4f}秒")

        # ————————————————————————————帮助菜单————————————————————————————
        # 检查版本表是否当天已更新
        subfunc_file.read_remote_cfg_in_rules()
        surprise_sign = Strings.SURPRISE_SIGN
        self.app_info.need_update = AppFunc.has_newer_version(self.app_info.curr_full_ver)
        prefix = surprise_sign if self.app_info.need_update is True else ""
        self.help_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label=f"{prefix}帮助", menu=self.help_menu)
        self.help_menu.add_command(label="我来赏你！", command=WndCreator.open_rewards)
        self.help_menu.add_command(label="视频教程",
                                   command=lambda: webbrowser.open_new(Strings.VIDEO_TUTORIAL_LINK))
        self.help_menu.add_command(label="更新日志", command=WndCreator.open_update_log)
        self.help_menu.add_command(label="反馈渠道", command=WndCreator.open_feedback)
        self.help_menu.add_command(label=f"{prefix}关于",
                                   command=partial(WndCreator.open_about, self.app_info))
        print(f"帮助菜单用时：{time.time() - self.start_time:.4f}秒")

        # ————————————————————————————作者标签————————————————————————————
        new_func_value = self.global_settings_value.new_func = \
            AppFunc.get_global_setting_value_by_local_record(
                LocalCfg.ENABLE_NEW_FUNC)
        author_str = self.app_info.author
        hint_str = self.app_info.hint
        author_str_without_hint = f"by {author_str}"
        author_str_with_hint = f"by {author_str}（{hint_str}）"

        if new_func_value is True:
            self.menu_bar.add_command(label=author_str_without_hint)
            self.menu_bar.entryconfigure(author_str_without_hint, state="disabled")
        else:
            self.menu_bar.add_command(label=author_str_with_hint)
            handler = widget_utils.UnlimitedClickHandler(
                self.root,
                self.menu_bar,
                **{"3": partial(self._to_enable_new_func)}
            )
            self.menu_bar.entryconfigure(author_str_with_hint, command=handler.on_click_down)

        self.used_tray = AppFunc.get_global_setting_value_by_local_record(LocalCfg.USED_TRAY)
        suffix = "" if self.used_tray is True else Strings.TRAY_HINT
        self._to_tray_label = f"⌟{suffix}"
        self.menu_bar.add_command(label=self._to_tray_label, command=self._to_bring_tk_to_tray)

    def _create_setting_menu(self):
        # -全局设置
        self.settings_menu.add_command(label=f"全局设置", command=WndCreator.open_global_setting_wnd)
        _, self.global_settings_value.auto_start = AppFunc.check_auto_start_or_toggle_to_()
        auto_start_value = self.global_settings_value.auto_start
        auto_start_var = self.global_settings_var.auto_start = tk.BooleanVar(value=auto_start_value)
        self.auto_start_menu = tk.Menu(self.settings_menu, tearoff=False)
        self.settings_menu.add_cascade(label="自启动", menu=self.auto_start_menu)
        self.auto_start_menu.add_checkbutton(
            label="开机自启动", variable=auto_start_var,
            command=partial(self._toggle_auto_start,
                            not self.global_settings_value.auto_start))
        self.auto_start_menu.add_command(
            label="测试登录自启动账号", command=MultiSwFunc.thread_to_login_auto_start_accounts)

        if self.is_login_menu:
            # -应用设置
            self.settings_menu.add_separator()  # ————————————————分割线————————————————
            self.settings_menu.add_command(label="平台设置", command=partial(WndCreator.open_sw_settings, self.sw))
            self.coexist_menu = tk.Menu(self.settings_menu, tearoff=False)
            self.settings_menu.add_command(label="共存与补丁",
                                           command=partial(ExeManagerWndCreator.open_exe_manager_wnd))

            self.rest_mode_menu = tk.Menu(self.settings_menu, tearoff=False)
            self.settings_menu.add_cascade(label="无补丁多开", menu=self.rest_mode_menu)
            rest_mode_value = self.global_settings_value.rest_mode = SwInfoFunc.get_sw_setting_by_local_record(
                self.sw, LocalCfg.REST_MULTIRUN_MODE)
            # print("当前项", rest_mode_value)
            self.sw_class.multirun_mode = rest_mode_value
            rest_mode_var = self.global_settings_var.rest_mode = tk.StringVar(value=rest_mode_value)  # 设置初始选中的子程序
            # 添加 内置 的单选按钮
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
            self.settings_menu.add_separator()  # ————————————————分割线————————————————

            # >登录设置
            self.login_settings_menu = tk.Menu(self.settings_menu, tearoff=False)
            self.settings_menu.add_cascade(label="登录设置", menu=self.login_settings_menu)

            self.login_settings_menu.add_command(label="登录说明", command=self._open_login_settings_instructions)
            self.login_settings_menu.add_separator()  # ————————————————分割线————————————————
            prefer_coexist_value = self.global_settings_value.prefer_coexist = \
                AppFunc.get_global_setting_value_by_local_record(LocalCfg.PREFER_COEXIST)
            prefer_coexist_var = self.global_settings_var.prefer_coexist = tk.BooleanVar(value=prefer_coexist_value)
            self.login_settings_menu.add_checkbutton(
                label="手动登录优选共存", variable=prefer_coexist_var,
                command=partial(AppFunc.save_a_global_setting_and_callback,
                                LocalCfg.PREFER_COEXIST, not prefer_coexist_value, self.create_root_menu_bar))

            hide_wnd_value = self.global_settings_value.hide_wnd = \
                AppFunc.get_global_setting_value_by_local_record(LocalCfg.HIDE_WND)
            hide_wnd_var = self.global_settings_var.hide_wnd = tk.BooleanVar(value=hide_wnd_value)
            self.login_settings_menu.add_checkbutton(
                label="一键登录前隐藏软件主窗口", variable=hide_wnd_var,
                command=partial(AppFunc.save_a_global_setting_and_callback,
                                LocalCfg.HIDE_WND, not hide_wnd_value, self.create_root_menu_bar))

            kill_idle_value = self.global_settings_value.kill_idle = \
                AppFunc.get_global_setting_value_by_local_record(LocalCfg.KILL_IDLE_LOGIN_WND)
            kill_idle_var = self.global_settings_var.kill_idle = tk.BooleanVar(value=kill_idle_value)
            self.login_settings_menu.add_checkbutton(
                label="一键登录前关闭多余登录窗口", variable=kill_idle_var,
                command=partial(AppFunc.save_a_global_setting_and_callback,
                                LocalCfg.KILL_IDLE_LOGIN_WND, not kill_idle_value, self.create_root_menu_bar))

            # >>互斥体
            self.mutant_menu = tk.Menu(self.login_settings_menu, tearoff=False)
            self.login_settings_menu.add_cascade(label="互斥体", menu=self.mutant_menu)
            unlock_cfg_value = self.global_settings_value.unlock_cfg = AppFunc.get_global_setting_value_by_local_record(
                LocalCfg.UNLOCK_CFG)
            unlock_cfg_var = self.global_settings_var.unlock_cfg = tk.BooleanVar(value=unlock_cfg_value)
            self.mutant_menu.add_checkbutton(
                label="登录时解锁配置文件", variable=unlock_cfg_var,
                command=partial(AppFunc.save_a_global_setting_and_callback,
                                LocalCfg.UNLOCK_CFG, not unlock_cfg_value, self.create_root_menu_bar))
            all_set_has_mutex_value = self.global_settings_value.all_set_has_mutex = AppFunc.get_global_setting_value_by_local_record(
                LocalCfg.ALL_HAS_MUTEX)
            all_set_has_mutex_var = self.global_settings_var.all_set_has_mutex = tk.BooleanVar(
                value=all_set_has_mutex_value)
            self.mutant_menu.add_checkbutton(
                label="默认含有互斥体", variable=all_set_has_mutex_var,
                command=partial(AppFunc.save_a_global_setting_and_callback,
                                LocalCfg.ALL_HAS_MUTEX, not all_set_has_mutex_value, self.create_root_menu_bar))
            self.mutant_menu.add_command(label="立即查杀所有互斥体", command=self._to_kill_mutexes)

            # >>调用模式
            self.call_mode_menu = tk.Menu(self.login_settings_menu, tearoff=False)
            self.login_settings_menu.add_cascade(label="调用模式", menu=self.call_mode_menu)
            call_mode_value = self.global_settings_value.call_mode = AppFunc.get_global_setting_value_by_local_record(
                "call_mode")
            call_mode_var = self.global_settings_var.call_mode = tk.StringVar(value=call_mode_value)
            for call_mode in CallMode:
                # >>-添加 {call_mode.value} 的单选按钮
                self.call_mode_menu.add_radiobutton(
                    label=call_mode.value,
                    value=call_mode.value,
                    variable=call_mode_var,
                    command=partial(AppFunc.save_a_global_setting_and_callback,
                                    LocalCfg.CALL_MODE, call_mode.value, self.create_root_menu_bar),
                )

            # >>登录按钮
            self.click_btn_menu = tk.Menu(self.login_settings_menu, tearoff=False)
            self.login_settings_menu.add_cascade(label="登录按钮", menu=self.click_btn_menu)
            auto_press_value = self.global_settings_value.auto_press = \
                AppFunc.get_global_setting_value_by_local_record(LocalCfg.AUTO_PRESS)
            auto_press_var = self.global_settings_var.auto_press = tk.BooleanVar(value=auto_press_value)
            self.click_btn_menu.add_checkbutton(
                label="自动点击", variable=auto_press_var,
                command=partial(AppFunc.save_a_global_setting_and_callback,
                                "auto_press", not auto_press_value, self.create_root_menu_bar))
            self.click_btn_menu.add_command(label="按钮识别列表", command=self._manager_sw_btn_list)

        self.settings_menu.add_separator()  # ————————————————分割线————————————————
        self.settings_menu.add_command(
            label="重置", command=partial(AppFunc.reset, self.root_class.reinit_root_ui))

    def _to_update_remote_cfg(self):
        printer.vital("更新远程配置")
        config_data = subfunc_file.force_fetch_remote_encrypted_cfg()
        if config_data is None:
            messagebox.showinfo("提示", "无法获取配置文件，请检查网络连接后重试")
            return False
        messagebox.showinfo("提示", "更新成功")
        self.root_class.main_ui.refresh_current_tab()
        return True

    def _to_initialize(self):
        printer.vital("初始化")
        self.root_class.reinit_root_ui()

    def _switch_to_classic_view(self):
        self.root.unbind("<Configure>")
        SwInfoFunc.save_sw_setting_to_local_record_and_call_back(self.sw, "view", "classic",
                                                                 self.root_class.login_ui.refresh)

    def _switch_to_tree_view(self):
        SwInfoFunc.save_sw_setting_to_local_record_and_call_back(self.sw, "view", "tree",
                                                                 self.root_class.login_ui.refresh)

    def _open_sidebar(self):
        if self.sidebar_wnd is not None and self.sidebar_wnd.winfo_exists():
            print("销毁", self.sidebar_wnd)
            new_label = "❮"
            self.menu_bar.entryconfigure(self.sidebar_menu_label, label=new_label)
            self.sidebar_menu_label = new_label
            if self.sidebar_ui is not None:
                self.sidebar_ui.listener_running = False
                self.sidebar_ui = None
            # self.sidebar_wnd.destroy()
        else:
            print("创建", self.sidebar_wnd)
            new_label = "❯"
            self.menu_bar.entryconfigure(self.sidebar_menu_label, label=new_label)
            if len(self.sidebar_menu_label) > 1:
                subfunc_file.update_settings(LocalCfg.GLOBAL_SECTION, **{LocalCfg.USED_SIDEBAR: True})
            self.sidebar_menu_label = new_label
            # self.sidebar_wnd = tk.Toplevel(self.root)
            # self.sidebar_ui = sidebar_ui.SidebarUI(self.sidebar_wnd, "导航条")

    def _set_wnd_scale(self, scale=None):
        if scale is None:
            # 创建输入框
            try:
                user_input = simpledialog.askstring(
                    title="输入 Scale",
                    prompt="请输入一个 75-500 之间的数字（含边界）：",
                    parent=self.root
                )
                if user_input is None:  # 用户取消或关闭输入框
                    return
                # 尝试将输入转换为整数并验证范围
                scale = int(user_input)
                if not (75 <= scale <= 500):
                    raise ValueError("输入值不在 75-500 范围内")
            except (ValueError, TypeError):
                messagebox.showerror("错误", "无效输入，操作已取消")
                return
        AppFunc.save_a_global_setting_and_callback(
            LocalCfg.SCALE,
            str(scale)
        )
        messagebox.showinfo("提示", "修改成功，将在重新启动程序后生效！")
        self.create_root_menu_bar()
        print(f"成功设置窗口缩放比例为 {scale}！")
        return

    def _toggle_auto_start(self, value):
        """切换是否开机自启动"""
        success, res = AppFunc.check_auto_start_or_toggle_to_(value)
        self.create_root_menu_bar()
        if success is not True:
            messagebox.showerror("错误", f"{res}\n将弹出自启动文件夹!")
            startup_folder = sys_utils.get_startup_folder()
            os.startfile(startup_folder)
            print("操作失败！")
        else:
            print(f"已添加自启动！" if value is True else f"已关闭自启动！")

    def _calc_multirun_mode_and_save(self, mode):
        """计算多开模式并保存"""
        SwInfoFunc.save_sw_setting_to_local_record_and_call_back(
            self.sw, LocalCfg.REST_MULTIRUN_MODE, mode, self.create_root_menu_bar)
        SwInfoFunc.get_sw_multirun_mode(self.sw)

    @staticmethod
    def _open_login_settings_instructions():
        """打开登录选项说明"""
        messagebox.showinfo("登录选项说明", Strings.LOGIN_SETTINGS_INSTRUCTIONS)

    def _to_kill_mutexes(self):
        """查杀所有互斥体"""
        success, msg = SwOperator.kill_all_mutexes_now(self.sw)
        if success is True:
            messagebox.showinfo("成功", msg)
        else:
            messagebox.showerror("错误", msg)
        self.root_class.login_ui.refresh()

    def _manager_sw_btn_list(self):
        # 弹出输入框
        sw_login_btn_list = SwInfoFunc.get_sw_setting_by_local_record(self.sw, LocalCfg.CLICK_BTNS)
        initial_value = sw_login_btn_list if isinstance(sw_login_btn_list, str) else ""
        btn_list = simpledialog.askstring(
            f"{self.sw}按钮识别列表", "当通过位置点击按钮失败, 会尝试根据文字依次查找按钮. "
                                      "输入示例: 进入微信/Enter WeChat\n"
                                      "添加按钮识别会轻微影响效率, 若能正常点击可以不用添加. 请输入:",
            initialvalue=initial_value, parent=self.root)
        if btn_list is None:
            return
        SwInfoFunc.save_sw_setting_to_local_record_and_call_back(self.sw, LocalCfg.CLICK_BTNS, btn_list)

    def _to_enable_new_func(self):
        AppFunc.save_a_global_setting_and_callback('enable_new_func', True)
        messagebox.showinfo("发现彩蛋", "解锁新功能，快去找找吧！")
        self.create_root_menu_bar()

    def _to_bring_tk_to_tray(self):
        """将tk窗口最小化到托盘"""
        self.root.withdraw()
        if self.used_tray is not True:
            self.used_tray = False
            subfunc_file.update_settings(LocalCfg.GLOBAL_SECTION, **{LocalCfg.USED_TRAY: True})
            new_label = self._to_tray_label.replace(Strings.TRAY_HINT, "")
            self.menu_bar.entryconfigure(self._to_tray_label, label=new_label)
            self._to_tray_label = new_label
        if not (self.root_class.global_settings_value.in_tray is True):
            AppFunc.create_tray(self.root)
            self.root_class.global_settings_value.in_tray = True
