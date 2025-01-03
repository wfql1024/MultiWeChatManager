import glob
import os
import re
import tkinter as tk
import webbrowser
from functools import partial
from tkinter import messagebox

import psutil

from functions import func_file, subfunc_file, func_setting, func_sw_dll, func_account
from resources import Strings, Config
from ui import about_ui, rewards_ui, sidebar_ui, statistic_ui
from utils import widget_utils


class MenuUI:
    def __init__(self, root, r_class, sw, app_info, sw_info,
                 states, settings_values, settings_variables):
        self.multiple_err = None
        self.revoke_err = None
        self.login_menu = None
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
        
        self.root = root
        self.r_class = r_class
        self.sw = sw
        self.app_info = app_info
        self.sw_info = sw_info
        self.states = states
        self.settings_values = settings_values
        self.settings_var = settings_variables
        
        self.scale = self.settings_values['scale']
        self.multiple_state = self.states['multiple']
        self.revoke_state = self.states['revoke']

    def create_root_menu_bar(self):
        """创建菜单栏"""
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
        self.user_file_menu.add_command(label="清除",
                                        command=partial(func_file.clear_user_file, self.r_class.refresh))
        # >配置文件
        self.config_file_menu = tk.Menu(self.file_menu, tearoff=False)
        if not self.sw_info["data_dir"]:
            self.file_menu.add_command(label="配置文件  未获取")
            self.file_menu.entryconfig(f"配置文件  未获取", state="disable")
        else:
            self.file_menu.add_cascade(label="配置文件", menu=self.config_file_menu)
            self.config_file_menu.add_command(label="打开",
                                              command=partial(func_file.open_config_file, self.sw))
            self.config_file_menu.add_command(label="清除",
                                              command=partial(func_file.clear_config_file, self.sw,
                                                              self.r_class.refresh))
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
        self.file_menu.add_command(label="查看DLL", command=partial(func_file.open_dll_dir, self.sw))
        # -创建软件快捷方式
        self.file_menu.add_command(label="创建程序快捷方式", command=func_file.create_app_lnk)
        # -创建快捷启动
        quick_start_sp, = subfunc_file.get_details_from_remote_setting_json(self.sw, support_quick_start=None)
        # print(f"支持快捷启动：{quick_start_sp}")
        self.file_menu.add_command(label="创建快捷启动",
                                   command=partial(func_file.create_multiple_lnk,
                                                   self.sw, self.multiple_state, self.create_root_menu_bar),
                                   state="normal" if quick_start_sp is True else "disabled")

        # ————————————————————————————编辑菜单————————————————————————————
        self.edit_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label="编辑", menu=self.edit_menu)
        # -刷新
        self.edit_menu.add_command(label="刷新", command=self.r_class.refresh)

        # ————————————————————————————视图菜单————————————————————————————
        # 添加单选框选项
        self.settings_values["view"] = subfunc_file.fetch_sw_setting_or_set_default(self.sw, "view")
        self.settings_var["view"] = tk.StringVar(value=self.settings_values["view"])
        self.view_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label="视图", menu=self.view_menu)

        self.view_menu.add_radiobutton(label="经典", variable=self.settings_var["view"], value="classic",
                                       command=self.change_classic_view)
        self.view_menu.add_radiobutton(label="列表", variable=self.settings_var["view"], value="tree",
                                       command=self.change_tree_view)

        # 显示当前选择的视图
        self.settings_values["sign_vis"] = \
            True if subfunc_file.fetch_global_setting_or_set_default("sign_visible") == "True" else False
        self.settings_var["sign_vis"] = tk.BooleanVar(value=self.settings_values["sign_vis"])
        self.view_options_menu = tk.Menu(self.view_menu, tearoff=False)
        self.view_menu.add_cascade(label=f"视图选项", menu=self.view_options_menu)
        self.view_options_menu.add_checkbutton(
            label="显示状态标志", variable=self.settings_var["sign_vis"],
            command=partial(subfunc_file.save_global_setting,
                            "sign_visible", not self.settings_values["sign_vis"], self.r_class.refresh)
        )
        if self.settings_values["view"] == "classic":
            # 添加经典视图的菜单项
            pass
        elif self.settings_values["view"] == "tree":
            # 添加列表视图的菜单项
            pass

        self.view_menu.add_separator()  # ————————————————分割线————————————————

        self.settings_values["scale"] = subfunc_file.fetch_global_setting_or_set_default("scale")
        self.settings_var["scale"] = tk.StringVar(value=self.settings_values["scale"])
        self.wnd_scale_menu = tk.Menu(self.view_menu, tearoff=False)
        self.view_menu.add_cascade(label=f"窗口缩放", menu=self.wnd_scale_menu)
        self.wnd_scale_menu.add_radiobutton(label="跟随系统", variable=self.settings_var["scale"], value="auto",
                                            command=partial(func_setting.set_wnd_scale,
                                                            self.create_root_menu_bar, "auto"))
        options = ["100", "125", "150", "175", "200"]
        for option in options:
            self.wnd_scale_menu.add_radiobutton(label=f"{option}%", variable=self.settings_var["scale"], value=option,
                                                command=partial(func_setting.set_wnd_scale,
                                                                self.create_root_menu_bar, option))
        if self.settings_values["scale"] != "auto" and self.settings_values["scale"] not in options:
            self.wnd_scale_menu.add_radiobutton(label=f"自定义:{self.scale}%",
                                                variable=self.settings_var["scale"], value=self.settings_values["scale"],
                                                command=partial(func_setting.set_wnd_scale,
                                                                self.create_root_menu_bar))
        else:
            self.wnd_scale_menu.add_radiobutton(label=f"自定义",
                                                variable=self.settings_var["scale"], value="0",
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
                                           command=partial(self.r_class.open_settings, self.sw))
        else:
            self.menu_bar.add_cascade(label="设置", menu=self.settings_menu)
            self.settings_menu.add_command(label="应用设置",
                                           command=partial(self.r_class.open_settings, self.sw))
        self.settings_menu.add_separator()  # ————————————————分割线————————————————
        # -防撤回
        self.revoke_state, _, _ = func_sw_dll.check_dll(
            self.sw, "revoke", self.sw_info["dll_dir"], self.sw_info["ver"])
        if self.revoke_state == "不可用":
            self.settings_menu.add_command(label=f"防撤回      {self.revoke_state}", state="disabled")
        elif self.revoke_state.startswith("错误"):
            self.revoke_err = tk.Menu(self.settings_menu, tearoff=False)
            self.settings_menu.add_cascade(label="防撤回      错误!", menu=self.revoke_err, foreground="red")
            self.revoke_err.add_command(label=f"[点击复制]{self.revoke_state}", foreground="red",
                                        command=lambda: self.root.clipboard_append(self.revoke_state))
        else:
            self.settings_menu.add_command(label=f"防撤回      {self.revoke_state}",
                                           command=partial(self.toggle_patch_mode, mode="revoke"))
        self.settings_menu.add_separator()  # ————————————————分割线————————————————
        # -全局多开
        self.multiple_state, _, _ = func_sw_dll.check_dll(
            self.sw, "multiple", self.sw_info["dll_dir"], self.sw_info["ver"])
        if self.multiple_state == "不可用":
            self.settings_menu.add_command(label=f"全局多开  {self.multiple_state}", state="disabled")
        elif self.multiple_state.startswith("错误"):
            self.multiple_err = tk.Menu(self.settings_menu, tearoff=False)
            self.settings_menu.add_cascade(label="全局多开  错误!", menu=self.multiple_err, foreground="red")
            self.multiple_err.add_command(label=f"[点击复制]{self.multiple_state}", foreground="red",
                                          command=lambda: self.root.clipboard_append(self.multiple_state))
        else:
            self.settings_menu.add_command(label=f"全局多开  {self.multiple_state}",
                                           command=partial(self.toggle_patch_mode, mode="multiple"))
        # >多开子程序选择
        self.settings_var["rest_mode"] = tk.StringVar()  # 用于跟踪当前选中的子程序
        # 检查状态
        if self.multiple_state == "已开启":
            self.settings_menu.add_command(label="其余模式", state="disabled")
        else:
            self.rest_mode_menu = tk.Menu(self.settings_menu, tearoff=False)
            self.settings_menu.add_cascade(label="其余模式", menu=self.rest_mode_menu)
            self.settings_values["rest_mode"] = subfunc_file.fetch_sw_setting_or_set_default(
                self.sw, "rest_mode")
            self.settings_var["rest_mode"].set(self.settings_values["rest_mode"])  # 设置初始选中的子程序
            python_sp, python_s_sp, handle_sp = subfunc_file.get_details_from_remote_setting_json(
                self.sw, support_python_mode=None, support_python_s_mode=None, support_handle_mode=None)
            # 添加 Python 的单选按钮
            self.rest_mode_menu.add_radiobutton(
                label='python',
                value='python',
                variable=self.settings_var["rest_mode"],
                command=partial(subfunc_file.save_sw_setting,
                                self.sw, "rest_mode", "python", self.create_root_menu_bar),
                state='disabled' if not python_sp else 'normal'
            )
            # 添加 强力Python 的单选按钮
            self.rest_mode_menu.add_radiobutton(
                label='python[S]',
                value='python[S]',
                variable=self.settings_var["rest_mode"],
                command=partial(subfunc_file.save_sw_setting,
                                self.sw, "rest_mode", "python[S]", self.create_root_menu_bar),
                state='disabled' if not python_s_sp else 'normal'
            )
            self.rest_mode_menu.add_separator()  # ————————————————分割线————————————————
            # 添加 Handle 的单选按钮
            self.rest_mode_menu.add_radiobutton(
                label='handle',
                value='handle',
                variable=self.settings_var["rest_mode"],
                command=partial(subfunc_file.save_sw_setting,
                                self.sw, "rest_mode", "handle", self.create_root_menu_bar),
                state='disabled' if not handle_sp else 'normal'
            )
            # 动态添加外部子程序
            external_res_path = Config.PROJ_EXTERNAL_RES_PATH
            exe_files = glob.glob(os.path.join(external_res_path, f"{self.sw}Multiple_*.exe"))
            if len(exe_files) != 0:
                self.rest_mode_menu.add_separator()  # ————————————————分割线————————————————
                for exe_file in exe_files:
                    exe_name = os.path.basename(exe_file)
                    right_part = exe_name.split('_', 1)[1].rsplit('.exe', 1)[0]
                    self.rest_mode_menu.add_radiobutton(
                        label=right_part,
                        value=exe_name,
                        variable=self.settings_var["rest_mode"],
                        command=partial(subfunc_file.save_sw_setting,
                                        self.sw, "rest_mode", exe_name, self.create_root_menu_bar),
                    )

        # >登录选项
        self.settings_values["hide_wnd"] = \
            True if subfunc_file.fetch_global_setting_or_set_default("hide_wnd") == "True" else False
        self.settings_var["hide_wnd"] = tk.BooleanVar(value=self.settings_values["hide_wnd"])
        self.login_menu = tk.Menu(self.settings_menu, tearoff=False)
        self.settings_menu.add_cascade(label="登录选项", menu=self.login_menu)
        self.login_menu.add_checkbutton(
            label="一键登录时隐藏窗口", variable=self.settings_var["hide_wnd"],
            command=partial(subfunc_file.save_global_setting,
                            "hide_wnd", not self.settings_values["hide_wnd"], self.create_root_menu_bar))

        self.settings_menu.add_separator()  # ————————————————分割线————————————————
        self.settings_menu.add_command(label="重置", command=partial(func_file.reset, self.r_class.load_on_startup))

        # ————————————————————————————帮助菜单————————————————————————————
        # 检查版本表是否当天已更新
        subfunc_file.try_get_local_cfg()
        surprise_sign = Strings.SURPRISE_SIGN
        prefix = surprise_sign if self.app_info["need_update"] is True else ""
        self.help_menu = tk.Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label=f"{prefix}帮助", menu=self.help_menu)
        self.help_menu.add_command(label="我来赏你！", command=self.open_rewards)
        self.help_menu.add_command(label="视频教程",
                                   command=lambda: webbrowser.open_new(Strings.VIDEO_TUTORIAL_LINK))
        self.help_menu.add_command(label="更新日志", command=self.r_class.open_update_log)
        self.help_menu.add_command(label=f"{prefix}关于",
                                   command=partial(self.open_about, self.app_info["need_update"]))

        # ————————————————————————————作者标签————————————————————————————
        self.settings_var["new_func"] = \
            True if subfunc_file.fetch_global_setting_or_set_default("enable_new_func") == "True" else False
        if self.settings_var["new_func"] is True:
            self.menu_bar.add_command(label=Strings.ENABLED_NEW_FUNC)
            self.menu_bar.entryconfigure(Strings.ENABLED_NEW_FUNC, state="disabled")
        else:
            self.menu_bar.add_command(label=Strings.NOT_ENABLED_NEW_FUNC)
            handler = widget_utils.UnlimitedClickHandler(
                self.root,
                self.menu_bar,
                lambda *args, **kwargs: None,  # 第一次点击，不执行任何操作
                lambda *args, **kwargs: None,  # 第二次点击，不执行任何操作
                partial(self.to_enable_new_func)  # 第三次点击，执行 to_enable_new_func
            )
            self.menu_bar.entryconfigure(Strings.NOT_ENABLED_NEW_FUNC, command=handler.on_click)

    def open_statistic(self):
        """打开统计窗口"""
        statistic_window = tk.Toplevel(self.root)
        statistic_ui.StatisticWindow(statistic_window, self.sw, self.settings_values["view"])

    def change_classic_view(self):
        self.root.unbind("<Configure>")
        subfunc_file.save_sw_setting(self.sw, "view", "classic", self.r_class.refresh)

    def change_tree_view(self):
        subfunc_file.save_sw_setting(self.sw, "view", "tree", self.r_class.refresh)

    def change_sidebar_view(self):
        # 清除窗口中的所有控件
        for widget in self.root.winfo_children():
            widget.destroy()
        sidebar_ui.SidebarUI(self.root)

    def toggle_patch_mode(self, mode):
        """切换是否全局多开或防撤回"""
        if mode == "multiple":
            mode_text = "全局多开"
        elif mode == "revoke":
            mode_text = "防撤回"
        else:
            return
        success, result = func_account.get_sw_acc_list(self.sw, self.sw_info["data_dir"], self.multiple_state)
        if success is True:
            acc_list_dict, _, _ = result
            login = acc_list_dict["login"]
            if len(login) > 0:
                answer = messagebox.askokcancel(
                    "警告",
                    "检测到正在使用微信。切换模式需要修改 WechatWin.dll 文件，请先手动退出所有微信后再进行，否则将会强制关闭微信进程。"
                )
                if not answer:
                    self.r_class.refresh()
                    return

        try:
            result = func_sw_dll.switch_dll(self.sw, mode, self.sw_info["dll_dir"], self.sw_info["ver"])  # 执行切换操作
            if result is True:
                messagebox.showinfo("提示", f"成功开启:{mode_text}")
            elif result is False:
                messagebox.showinfo("提示", f"成功关闭:{mode_text}")
            else:
                messagebox.showinfo("提示", "请重试！")
        except psutil.AccessDenied:
            messagebox.showerror("权限不足", "无法终止微信进程，请以管理员身份运行程序。")
        except Exception as e:
            messagebox.showerror("错误", f"操作失败: {str(e)}")
        finally:
            self.r_class.refresh()

    def open_rewards(self):
        """打开赞赏窗口"""
        rewards_window = tk.Toplevel(self.root)
        rewards_ui.RewardsWindow(self.root, self.root, rewards_window, Config.REWARDS_PNG_PATH)

    def open_about(self, need_to_update):
        """打开关于窗口"""
        about_wnd = tk.Toplevel(self.root)
        about_ui.AboutWindow(self.root, self.root, about_wnd, need_to_update)

    def to_enable_new_func(self, event=None):
        if event is None:
            pass
        subfunc_file.save_global_setting('enable_new_func', True)
        messagebox.showinfo("发现彩蛋", "解锁新菜单，快去看看吧！")
        self.r_class.refresh()

