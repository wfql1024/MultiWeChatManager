import os
import re
import tkinter as tk
import webbrowser
from functools import partial
from pathlib import Path
from tkinter import messagebox

from functions import func_file, subfunc_file, func_setting, func_sw_dll, func_update
from public_class.global_members import GlobalMembers
from resources import Strings, Config
from ui import about_ui, rewards_ui, sidebar_ui, statistic_ui, setting_ui, update_log_ui, acc_manager_ui
from utils import widget_utils
from utils.logger_utils import mylogger as logger
from utils.logger_utils import myprinter as printer


class MenuUI:
    def __init__(self):
        """获取必要的设置项信息"""
        self.call_mode_menu = None
        self.auto_start_menu = None
        self.path_error = None
        self.multiple_err = None
        self.revoke_err = None
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
        self.cfg_data = self.root_class.cfg_data

        self.acc_tab_ui = self.root_class.acc_tab_ui
        self.sw = self.acc_tab_ui.sw
        self.sw_class = self.sw_classes[self.sw]

    def create_root_menu_bar(self):
        """创建菜单栏"""
        if self.root_class.finish_started is True:
            # 路径检查
            self.sw_class.data_dir = func_setting.get_sw_data_dir(self.sw)
            self.sw_class.inst_path, self.sw_class.ver = func_setting.get_sw_inst_path_and_ver(self.sw)
            self.sw_class.dll_dir = func_setting.get_sw_dll_dir(self.sw)

        # 传递错误信息给主窗口
        if self.sw_class.inst_path is None or self.sw_class.data_dir is None or self.sw_class.dll_dir is None:
            print("路径设置错误...")
            self.path_error = True

        print("创建菜单栏...")
        if hasattr(self, 'menu_bar'):
            # 清空现有菜单栏
            setattr(self, 'menu_bar', None)
        else:
            self.menu_bar = tk.Menu(self.root)
            self.root.config(menu=self.menu_bar)

        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)

        # ————————————————————————————文件菜单————————————————————————————
        self.file_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label="文件", menu=self.file_menu)
        # >用户文件
        self.user_file_menu = tk.Menu(self.file_menu, tearoff=False)
        self.file_menu.add_cascade(label="用户文件", menu=self.user_file_menu)
        self.user_file_menu.add_command(label="打开", command=func_file.open_user_file)
        self.user_file_menu.add_command(label="清除", command=partial(
            func_file.clear_user_file, self.root_class.initialize_in_init))
        # >配置文件
        self.config_file_menu = tk.Menu(self.file_menu, tearoff=False)
        if not self.sw_class.data_dir:
            self.file_menu.add_command(label="配置文件  未获取")
            self.file_menu.entryconfig(f"配置文件  未获取", state="disable")
        else:
            self.file_menu.add_cascade(label="配置文件", menu=self.config_file_menu)
            self.config_file_menu.add_command(label="打开",
                                              command=partial(func_file.open_config_file, self.sw))
            self.config_file_menu.add_command(label="清除",
                                              command=partial(func_file.clear_config_file, self.sw,
                                                              self.root_class.acc_tab_ui.refresh))
        # >程序目录
        self.program_file_menu = tk.Menu(self.file_menu, tearoff=False)
        self.file_menu.add_cascade(label="程序目录", menu=self.program_file_menu)
        self.program_file_menu.add_command(label="打开", command=func_file.open_program_file)
        self.program_file_menu.add_command(label="删除旧版备份",
                                           command=partial(func_file.mov_backup))

        # >统计数据
        self.statistic_menu = tk.Menu(self.file_menu, tearoff=False)
        self.file_menu.add_cascade(label="统计", menu=self.statistic_menu)
        self.statistic_menu.add_command(label="查看", command=self.open_statistic)
        self.statistic_menu.add_command(label="清除",
                                        command=partial(func_file.clear_statistic_data,
                                                        self.create_root_menu_bar))
        # -打开主dll所在文件夹
        self.file_menu.add_command(label="查看DLL目录", command=partial(func_file.open_dll_dir, self.sw))
        if self.sw_class.data_dir is None:
            self.file_menu.entryconfig(f"查看DLL目录", state="disable")

        # -创建软件快捷方式
        self.file_menu.add_command(label="创建程序快捷方式", command=func_file.create_app_lnk)

        # -创建快捷启动
        quick_start_sp, = subfunc_file.get_details_from_remote_setting_json(self.sw, support_quick_start=None)
        # print(f"支持快捷启动：{quick_start_sp}")
        self.file_menu.add_command(label="创建快捷启动",
                                   command=partial(func_file.create_multiple_lnk,
                                                   self.sw, self.sw_class.multiple_state, self.create_root_menu_bar),
                                   state="normal" if quick_start_sp is True else "disabled")

        # ————————————————————————————编辑菜单————————————————————————————
        self.edit_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label="编辑", menu=self.edit_menu)
        # -刷新
        self.edit_menu.add_command(label="刷新", command=self.to_refresh)

        # ————————————————————————————视图菜单————————————————————————————
        # 视图单选
        view_value = self.global_settings_value.view = subfunc_file.fetch_sw_setting_or_set_default(
            self.sw, "view")
        view_var = self.global_settings_var.view = tk.StringVar(value=view_value)
        self.view_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label="视图", menu=self.view_menu)

        self.view_menu.add_radiobutton(label="经典", variable=view_var, value="classic",
                                       command=self.change_classic_view)
        self.view_menu.add_radiobutton(label="列表", variable=view_var, value="tree",
                                       command=self.change_tree_view)
        self.view_menu.add_radiobutton(label="侧栏", variable=view_var, value="sidebar",
                                       command=self.change_sidebar_view)

        # 视图选项
        sign_vis_value = self.global_settings_value.sign_vis = \
            True if subfunc_file.fetch_global_setting_or_set_default("sign_visible") == "True" else False
        sign_vis_var = self.global_settings_var.sign_vis = tk.BooleanVar(value=sign_vis_value)
        self.view_options_menu = tk.Menu(self.view_menu, tearoff=False)
        self.view_menu.add_cascade(label=f"视图选项", menu=self.view_options_menu)
        self.view_options_menu.add_checkbutton(
            label="显示状态标志", variable=sign_vis_var,
            command=partial(subfunc_file.save_global_setting,
                            "sign_visible", not self.global_settings_value.sign_vis, self.root_class.acc_tab_ui.refresh)
        )
        # 特有菜单
        if view_value == "classic":
            # 添加经典视图的菜单项
            pass
        elif view_value == "tree":
            # 添加列表视图的菜单项
            pass

        # 缩放
        self.view_menu.add_separator()  # ————————————————分割线————————————————
        scale_value = self.global_settings_value.scale = subfunc_file.fetch_global_setting_or_set_default("scale")
        scale_var = self.global_settings_var.scale = tk.StringVar(value=scale_value)
        self.wnd_scale_menu = tk.Menu(self.view_menu, tearoff=False)
        self.view_menu.add_cascade(label=f"窗口缩放", menu=self.wnd_scale_menu)
        self.wnd_scale_menu.add_radiobutton(label="跟随系统", variable=scale_var, value="auto",
                                            command=partial(func_setting.set_wnd_scale,
                                                            self.create_root_menu_bar, "auto"))
        options = ["100", "125", "150", "175", "200"]
        for option in options:
            self.wnd_scale_menu.add_radiobutton(label=f"{option}%", variable=scale_var, value=option,
                                                command=partial(func_setting.set_wnd_scale,
                                                                self.create_root_menu_bar, option))
        if scale_value != "auto" and scale_value not in options:
            self.wnd_scale_menu.add_radiobutton(label=f"自定义:{scale_value}%",
                                                variable=scale_var, value=scale_value,
                                                command=partial(func_setting.set_wnd_scale,
                                                                self.create_root_menu_bar))
        else:
            self.wnd_scale_menu.add_radiobutton(label=f"自定义",
                                                variable=scale_var, value="0",
                                                command=partial(func_setting.set_wnd_scale,
                                                                self.create_root_menu_bar))

        # ————————————————————————————设置菜单————————————————————————————
        self.settings_menu = tk.Menu(self.menu_bar, tearoff=False)
        # -应用设置
        login_size = subfunc_file.fetch_sw_setting_or_set_default(self.sw, "login_size")
        # print(f"登录窗口大小：{login_size}")
        warning_sign = Strings.WARNING_SIGN
        if not login_size or not re.match(r"^\d+\*\d+$", login_size):
            self.menu_bar.add_cascade(label=f"{warning_sign}设置", menu=self.settings_menu)
            self.settings_menu.add_command(label=f"{warning_sign}应用设置", foreground='red',
                                           command=partial(self.open_settings, self.sw))
        else:
            self.menu_bar.add_cascade(label="设置", menu=self.settings_menu)
            self.settings_menu.add_command(label="应用设置",
                                           command=partial(self.open_settings, self.sw))
        self.settings_menu.add_separator()  # ————————————————分割线————————————————

        self.settings_menu.add_command(label=f"账号管理", command=self.open_acc_setting)
        self.settings_menu.add_separator()  # ————————————————分割线————————————————

        # 防撤回和全局多开需要依赖存储路径，因此判断若无路径直接跳过菜单创建
        if self.sw_class.data_dir is not None:
            # -防撤回
            self.sw_class.revoke_state, _, _ = func_sw_dll.check_dll(
                self.sw, "revoke", self.sw_class.dll_dir)
            revoke_state = self.sw_class.revoke_state
            if revoke_state == "不可用":
                self.settings_menu.add_command(label=f"防撤回      {revoke_state}", state="disabled")
            elif revoke_state.startswith("错误"):
                self.revoke_err = tk.Menu(self.settings_menu, tearoff=False)
                self.settings_menu.add_cascade(label="防撤回      错误!", menu=self.revoke_err, foreground="red")
                self.revoke_err.add_command(label=f"[点击复制]{revoke_state}", foreground="red",
                                            command=lambda: self.root.clipboard_append(revoke_state))
            else:
                self.settings_menu.add_command(label=f"防撤回      {revoke_state}",
                                               command=partial(self.toggle_patch_mode, mode="revoke"))
            self.settings_menu.add_separator()  # ————————————————分割线————————————————
            # -全局多开
            self.sw_class.multiple_state, _, _ = func_sw_dll.check_dll(
                self.sw, "multiple", self.sw_class.dll_dir)
            multiple_state = self.sw_class.multiple_state
            if multiple_state == "不可用":
                self.settings_menu.add_command(label=f"全局多开  {multiple_state}", state="disabled")
            elif multiple_state.startswith("错误"):
                self.multiple_err = tk.Menu(self.settings_menu, tearoff=False)
                self.settings_menu.add_cascade(label="全局多开  错误!", menu=self.multiple_err, foreground="red")
                self.multiple_err.add_command(label=f"[点击复制]{multiple_state}", foreground="red",
                                              command=lambda: self.root.clipboard_append(multiple_state))
            else:
                self.settings_menu.add_command(label=f"全局多开  {multiple_state}",
                                               command=partial(self.toggle_patch_mode, mode="multiple"))
        else:
            self.sw_class.multiple_state = multiple_state = "不可用"
            self.sw_class.revoke_state = "不可用"

        # >多开子程序选择
        # 检查状态
        if multiple_state == "已开启":
            self.settings_menu.add_command(label="其余模式", state="disabled")
        else:
            self.rest_mode_menu = tk.Menu(self.settings_menu, tearoff=False)
            self.settings_menu.add_cascade(label="其余模式", menu=self.rest_mode_menu)
            rest_mode_value = self.global_settings_value.rest_mode = subfunc_file.fetch_sw_setting_or_set_default(
                self.sw, "rest_mode")
            rest_mode_var = self.global_settings_var.rest_mode = tk.StringVar(value=rest_mode_value)  # 设置初始选中的子程序
            python_sp, python_s_sp, handle_sp = subfunc_file.get_details_from_remote_setting_json(
                self.sw, support_python_mode=None, support_python_s_mode=None, support_handle_mode=None)
            # 添加 Python 的单选按钮
            self.rest_mode_menu.add_radiobutton(
                label='python',
                value='python',
                variable=rest_mode_var,
                command=partial(subfunc_file.save_sw_setting,
                                self.sw, "rest_mode", "python", self.create_root_menu_bar),
                state='disabled' if not python_sp else 'normal'
            )
            # 添加 强力Python 的单选按钮
            self.rest_mode_menu.add_radiobutton(
                label='python[S]',
                value='python[S]',
                variable=rest_mode_var,
                command=partial(subfunc_file.save_sw_setting,
                                self.sw, "rest_mode", "python[S]", self.create_root_menu_bar),
                state='disabled' if not python_s_sp else 'normal'
            )
            self.rest_mode_menu.add_separator()  # ————————————————分割线————————————————
            # 添加 Handle 的单选按钮
            self.rest_mode_menu.add_radiobutton(
                label='handle',
                value='handle',
                variable=rest_mode_var,
                command=partial(subfunc_file.save_sw_setting,
                                self.sw, "rest_mode", "handle", self.create_root_menu_bar),
                state='disabled' if not handle_sp else 'normal'
            )
            # 动态添加外部子程序
            external_res_path = Config.PROJ_EXTERNAL_RES_PATH
            exe_files = [str(p) for p in Path(external_res_path).rglob(f"{self.sw}Multiple_*.exe")]
            # exe_files = glob.glob(os.path.join(external_res_path, f"{self.sw}Multiple_*.exe"))
            if len(exe_files) != 0:
                self.rest_mode_menu.add_separator()  # ————————————————分割线————————————————
                for exe_file in exe_files:
                    exe_name = os.path.basename(exe_file)
                    right_part = exe_name.split('_', 1)[1].rsplit('.exe', 1)[0]
                    self.rest_mode_menu.add_radiobutton(
                        label=right_part,
                        value=exe_name,
                        variable=rest_mode_var,
                        command=partial(subfunc_file.save_sw_setting,
                                        self.sw, "rest_mode", exe_name, self.create_root_menu_bar),
                    )

        hide_wnd_value = self.global_settings_value.hide_wnd = \
            True if subfunc_file.fetch_global_setting_or_set_default("hide_wnd") == "True" else False
        hide_wnd_var = self.global_settings_var.hide_wnd = tk.BooleanVar(value=hide_wnd_value)
        self.settings_menu.add_checkbutton(
            label="自动登录前隐藏主窗口", variable=hide_wnd_var,
            command=partial(subfunc_file.save_global_setting,
                            "hide_wnd", not hide_wnd_value, self.create_root_menu_bar))

        # >调用模式
        self.call_mode_menu = tk.Menu(self.settings_menu, tearoff=False)
        self.settings_menu.add_cascade(label="调用模式", menu=self.call_mode_menu)
        call_mode_value = self.global_settings_value.call_mode = subfunc_file.fetch_global_setting_or_set_default(
            "call_mode")
        call_mode_var = self.global_settings_var.call_mode = tk.StringVar(value=call_mode_value)  # 设置初始选中的子程序

        python_sp, python_s_sp, handle_sp = subfunc_file.get_details_from_remote_setting_json(
            self.sw, support_python_mode=None, support_python_s_mode=None, support_handle_mode=None)
        # 添加 HANDLE 的单选按钮
        self.call_mode_menu.add_radiobutton(
            label='HANDLE',
            value='HANDLE',
            variable=call_mode_var,
            command=partial(subfunc_file.save_global_setting,
                            "call_mode", "HANDLE", self.create_root_menu_bar),
            state='disabled' if not python_sp else 'normal'
        )
        # 添加 DEFAULT 的单选按钮
        self.call_mode_menu.add_radiobutton(
            label='DEFAULT',
            value='DEFAULT',
            variable=call_mode_var,
            command=partial(subfunc_file.save_global_setting,
                            "call_mode", "DEFAULT", self.create_root_menu_bar),
            state='disabled' if not python_s_sp else 'normal'
        )
        # 添加 LOGON 的单选按钮
        self.call_mode_menu.add_radiobutton(
            label='LOGON',
            value='LOGON',
            variable=call_mode_var,
            command=partial(subfunc_file.save_global_setting,
                            "call_mode", "handle", self.create_root_menu_bar),
            state='disabled' if not handle_sp else 'normal'
        )

        auto_press_value = self.global_settings_value.auto_press = \
            True if subfunc_file.fetch_global_setting_or_set_default("auto_press") == "True" else False
        auto_press_var = self.global_settings_var.auto_press = tk.BooleanVar(value=auto_press_value)
        self.settings_menu.add_checkbutton(
            label="自动点击登录按钮", variable=auto_press_var,
            command=partial(subfunc_file.save_global_setting,
                            "auto_press", not auto_press_value, self.create_root_menu_bar))

        self.settings_menu.add_separator()  # ————————————————分割线————————————————
        _, self.global_settings_value.auto_start = subfunc_file.check_auto_start_or_toggle_to_()
        auto_start_value = self.global_settings_value.auto_start
        auto_start_var = self.global_settings_var.auto_start = tk.BooleanVar(value=auto_start_value)
        self.auto_start_menu = tk.Menu(self.settings_menu, tearoff=False)
        self.settings_menu.add_cascade(label="自启动", menu=self.auto_start_menu)
        self.auto_start_menu.add_checkbutton(
            label="开机自启动", variable=auto_start_var,
            command=partial(self.toggle_auto_start,
                            not self.global_settings_value.auto_start))
        self.auto_start_menu.add_command(
            label="测试登录自启动账号", command=partial(self.root_class.to_login_auto_start_accounts))

        self.settings_menu.add_separator()  # ————————————————分割线————————————————
        self.settings_menu.add_command(
            label="重置", command=partial(func_file.reset, self.root_class.initialize_in_init))

        # ————————————————————————————帮助菜单————————————————————————————
        # 检查版本表是否当天已更新
        subfunc_file.try_get_local_cfg()
        surprise_sign = Strings.SURPRISE_SIGN
        self.app_info.need_update = func_update.has_newer_version(self.app_info.curr_full_ver)
        prefix = surprise_sign if self.app_info.need_update is True else ""
        self.help_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label=f"{prefix}帮助", menu=self.help_menu)
        self.help_menu.add_command(label="我来赏你！", command=self.open_rewards)
        self.help_menu.add_command(label="视频教程",
                                   command=lambda: webbrowser.open_new(Strings.VIDEO_TUTORIAL_LINK))
        self.help_menu.add_command(label="更新日志", command=self.open_update_log)
        self.help_menu.add_command(label=f"{prefix}关于",
                                   command=partial(self.open_about, self.app_info))

        # ————————————————————————————作者标签————————————————————————————
        new_func_value = self.global_settings_value.new_func = \
            True if subfunc_file.fetch_global_setting_or_set_default("enable_new_func") == "True" else False
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
                lambda *args, **kwargs: None,  # 第一次点击，不执行任何操作
                lambda *args, **kwargs: None,  # 第二次点击，不执行任何操作
                partial(self.to_enable_new_func)  # 第三次点击，执行 to_enable_new_func
            )
            self.menu_bar.entryconfigure(author_str_with_hint, command=handler.on_click)

    def open_statistic(self):
        """打开统计窗口"""
        statistic_window = tk.Toplevel(self.root)
        statistic_ui.StatisticWindow(statistic_window, self.sw, self.global_settings_value.view)

    def to_refresh(self):
        printer.vital("手动刷新")
        self.root_class.acc_tab_ui.refresh()

    def change_classic_view(self):
        self.root.unbind("<Configure>")
        subfunc_file.save_sw_setting(self.sw, "view", "classic", self.root_class.acc_tab_ui.refresh)

    def change_tree_view(self):
        subfunc_file.save_sw_setting(self.sw, "view", "tree", self.root_class.acc_tab_ui.refresh)

    def change_sidebar_view(self):
        # 清除窗口中的所有控件
        for widget in self.root.winfo_children():
            widget.destroy()
        sidebar_ui.SidebarUI()

    def open_acc_setting(self):
        acc_manager_window = tk.Toplevel(self.root)
        acc_manager_ui.AccManagerWindow(self, acc_manager_window)

    def open_settings(self, sw):
        """打开设置窗口"""
        settings_window = tk.Toplevel(self.root)
        setting_ui.SettingWindow(settings_window, sw, self.sw_class.multiple_state,
                                 self.root_class.acc_tab_ui.refresh)

    def toggle_patch_mode(self, mode):
        """切换是否全局多开或防撤回"""
        try:
            func_sw_dll.switch_dll(self.sw, mode, self.sw_class.dll_dir)  # 执行切换操作
        except Exception as e:
            messagebox.showerror("错误", f"操作失败: {str(e)}")
            logger.error(f"发生错误: {str(e)}")
        finally:
            self.root_class.acc_tab_ui.refresh()

    def toggle_auto_start(self, value):
        """切换是否开机自启动"""
        success, res = subfunc_file.check_auto_start_or_toggle_to_(value)
        self.create_root_menu_bar()
        if success is not True:
            messagebox.showerror("错误", res)
            print("操作失败！")
        else:
            print(f"已添加自启动！" if value is True else f"已关闭自启动！")

    def open_rewards(self):
        """打开赞赏窗口"""
        rewards_window = tk.Toplevel(self.root)
        rewards_ui.RewardsWindow(self.root, self.root, rewards_window, Config.REWARDS_PNG_PATH)

    def open_update_log(self):
        """打开版本日志窗口"""
        success, result = func_update.split_vers_by_cur_from_local(self.app_info.curr_full_ver)
        if success is True:
            new_versions, old_versions = result
            update_log_window = tk.Toplevel(self.root)
            update_log_ui.UpdateLogWindow(self.root, self.root, update_log_window, old_versions)
        else:
            messagebox.showerror("错误", result)

    def open_about(self, app_info):
        """打开关于窗口"""
        about_wnd = tk.Toplevel(self.root)
        about_ui.AboutWindow(self.root, self.root, about_wnd, app_info)

    def to_enable_new_func(self, event=None):
        if event is None:
            pass
        subfunc_file.save_global_setting('enable_new_func', True)
        messagebox.showinfo("发现彩蛋", "解锁新功能，快去找找吧！")
        self.create_root_menu_bar()
