import json
import os
import shutil
import sys
import threading
import time
from tkinter import messagebox
from typing import Union, Tuple

import psutil
import win32com
import winshell
from PIL import Image
from pystray import Menu
from win32com.client import Dispatch

from legacy_python.functions import subfunc_file
from legacy_python.public.config import Config
from legacy_python.public.enums import LocalCfg, RemoteCfg
from legacy_python.public.global_members import GlobalMembers
from legacy_python.utils import sys_utils, file_utils
from legacy_python.utils.logger_utils import mylogger as logger


class AppInfo:
    def __init__(self):
        self.name = os.path.basename(sys.argv[0])
        self.author = "吾峰起浪"
        self.curr_full_ver = subfunc_file.get_app_current_version()
        self.need_update = None
        self.hint = "狂按"


class GlobalSettings:
    def __init__(self):
        self.sign_vis = None
        self.scale = None
        self.login_size = None
        self.rest_mode = None
        self.hide_wnd = None
        self.kill_idle = None
        self.unlock_cfg = None
        self.all_set_has_mutex = None
        self.call_mode = None
        self.new_func = None
        self.auto_press = None
        self.disable_proxy = None
        self.use_txt_avt = None
        self.in_tray = False
        self.prefer_coexist = None


class AppFunc:
    @staticmethod
    def get_root_class() -> property:
        """获得软件根类"""
        return GlobalMembers.root_class

    @classmethod
    def get_root_wnd(cls):
        """获得软件主窗口"""
        return cls.get_root_class().root

    @classmethod
    def get_global_settings_value_obj(cls) -> GlobalSettings:
        """获取软件全局设置值"""
        return cls.get_root_class().global_settings_value

    @classmethod
    def get_global_settings_var_obj(cls) -> GlobalSettings:
        """获取软件全局设置变量"""
        return cls.get_root_class().global_settings_var

    @classmethod
    def get_global_setting_value_by_local_record(cls, key):
        """从本地记录获取软件全局设置值"""
        return subfunc_file.fetch_a_setting_or_set_default_or_none(LocalCfg.GLOBAL_SECTION, key)

    @classmethod
    def save_a_global_setting_and_callback(cls, key, value, callback=None):
        return subfunc_file.save_a_setting_and_callback(LocalCfg.GLOBAL_SECTION, key, value, callback)

    @staticmethod
    def migrate_old_user_files():
        current_pid = os.getpid()
        target_names = ["微信多开管理器.exe", "极峰多聊.exe"]

        # 1. 找出目标进程
        candidates = []
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                if proc.info['name'] in target_names and proc.info['pid'] != current_pid:
                    candidates.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        print(f"找到旧版进程: {candidates}")

        # 2. 判断情况
        if len(candidates) == 0:
            messagebox.showwarning("提示", "请打开旧版程序")
            return
        elif len(candidates) > 1:
            messagebox.showwarning("提示", "请只保留一个旧版程序进程")
            return

        proc = candidates[0]
        old_exe_path = proc.info['exe']
        old_dir = os.path.dirname(old_exe_path)

        print(f"旧版进程路径: {old_exe_path}")
        print(f"旧版进程目录: {old_dir}")

        # 3. 搜索 user_files 文件夹
        old_user_path = None
        for root, dirs, files in os.walk(old_dir):
            print(f"当前目录: {root}")
            print(f"子目录: {dirs}")
            print(f"文件: {files}")
            if "user_files" in dirs:
                old_user_path = os.path.join(root, "user_files")
                print(f"旧版 user_files 路径: {old_user_path}")
                break

        if not old_user_path or not os.path.isdir(old_user_path):
            messagebox.showerror("错误", "未找到旧版 user_files 文件夹")
            return

        if not messagebox.askokcancel("提示", "已识别到旧版程序, 是否导入(拷贝)旧版数据？\n本程序数据将会备份至桌面!"):
            return

        # 4. 备份新程序的用户文件夹
        if os.path.exists(Config.PROJ_USER_PATH):
            desktop = winshell.desktop()
            ts = time.strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(desktop, f"user_files_backup_{ts}")
            print(f"备份路径: {backup_path}")
            shutil.move(Config.PROJ_USER_PATH, backup_path)
            print(f"旧版数据已备份至: {backup_path}")

        # 5. 拷贝旧版数据
        shutil.copytree(old_user_path, Config.PROJ_USER_PATH)
        print(f"旧版数据已拷贝至: {Config.PROJ_USER_PATH}")

        # 6. 完成提示
        messagebox.showinfo("完成", "导入完成！")

        GlobalMembers.root_class.initialize_in_root()

    @staticmethod
    def create_tray(root):
        from pystray import Icon, MenuItem
        def on_restore(_icon, _item=None):
            root.after(0, lambda: root.deiconify())

        def on_exit(_icon, _item=None):
            _icon.visible = False
            _icon.stop()
            root.after(0, root.destroy)

        menu = Menu(
            MenuItem("显示窗口", on_restore),
            MenuItem("退出", on_exit)
        )

        icon_img = Image.open(Config.PROJ_ICO_PATH)
        tray_icon = Icon("JFMC", icon_img, title="极峰多聊", menu=menu)

        # 给托盘图标绑定鼠标点击恢复窗口
        def setup(icon):
            icon.visible = True
            icon._run_detached = True  # 防止点击后阻塞
            icon.icon = icon_img
            icon.menu = menu
            icon.title = "极峰多聊"
            icon.update_menu()
            # 点击事件：多数系统支持
            icon.on_click = lambda: on_restore(icon)

        def run_icon():
            tray_icon.run(setup)

        # 在后台线程中运行托盘图标
        threading.Thread(target=run_icon, daemon=True).start()

        return tray_icon

    @classmethod
    def apply_proxy_setting(cls):
        use_proxy = cls.get_global_setting_value_by_local_record(
            LocalCfg.USE_PROXY)
        print(use_proxy)
        if use_proxy is True:
            proxy_ip = cls.get_global_setting_value_by_local_record(LocalCfg.PROXY_IP)
            proxy_port = cls.get_global_setting_value_by_local_record(LocalCfg.PROXY_PORT)
            os.environ['http_proxy'] = f"{proxy_ip}:{proxy_port}"
            os.environ['https_proxy'] = f"{proxy_ip}:{proxy_port}"
            # 可选：清空 no_proxy
            os.environ['no_proxy'] = ''
            print("已启用代理！")
        else:
            os.environ['http_proxy'] = ''
            os.environ['https_proxy'] = ''
            os.environ['no_proxy'] = '*'
            print("已禁用代理！")

    @staticmethod
    def has_newer_version(curr_ver) -> bool:
        """
        检查是否有新版本
        :param curr_ver: 当前版本
        :return: Union[Tuple[成功, 是的], Tuple[失败, 错误信息]]
        """
        success, result = AppFunc.split_vers_by_cur_from_local(curr_ver)
        if success is True:
            new_versions, old_versions = result
            if new_versions:
                return True
        return False

    @staticmethod
    def split_vers_by_cur_from_local(current_ver) -> Union[Tuple[bool, Tuple[list, list]], Tuple[bool, str]]:
        """
        从本地获取所有版本号，然后根据当前版本号将其分为两部分：
        一部分是高于或等于当前版本号的，另一部分是低于当前版本号的。
        :param current_ver: 当前版本
        :return: Union[Tuple[成功, Tuple[新版列表, 旧表列表]], Tuple[失败, 错误信息]]
        """
        try:
            with open(Config.REMOTE_SETTING_JSON_PATH, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            if not config_data:
                print("没有数据")
                return False, "错误：没有数据"
            else:
                # 获取 update 节点的所有版本
                all_versions = list(config_data["global"]["update"].keys())
                # 对版本号进行排序
                sorted_versions = file_utils.get_sorted_full_versions(all_versions)
                if len(sorted_versions) == 0:
                    return False, "版本列表为空"
                # 遍历 sorted_versions，通过 file_utils.get_newest_full_version 比较
                for i, version in enumerate(sorted_versions):
                    if file_utils.get_newest_full_version([current_ver, version]) == current_ver:
                        # 如果找到第一个不高于 current_ver 的版本
                        lower_or_equal_versions = sorted_versions[i:]
                        higher_versions = sorted_versions[:i]
                        break
                else:
                    # 如果没有找到比 current_ver 小或等于的版本，所有都更高
                    higher_versions = sorted_versions
                    lower_or_equal_versions = []
                return True, (higher_versions, lower_or_equal_versions)

        except Exception as e:
            logger.error(e)
            return False, "错误：无法获取版本信息"

    @staticmethod
    def open_user_file():
        """打开用户文件夹"""
        if not os.path.exists(Config.PROJ_USER_PATH):
            os.makedirs(Config.PROJ_USER_PATH)
        os.startfile(Config.PROJ_USER_PATH)

    @staticmethod
    def clear_user_file(after):
        """清除用户文件夹"""
        confirm = messagebox.askokcancel(
            "确认清除",
            "该操作将会清空头像、昵称、配置的路径等数据，请确认是否需要清除？"
        )
        user_dir = Config.PROJ_USER_PATH
        items = [os.path.join(user_dir, item) for item in os.listdir(user_dir)]
        if confirm:
            try:
                file_utils.move_files_to_recycle_bin(items)
                messagebox.showinfo("清除完成", "用户目录已移入回收站。")
                after()
                return
            except Exception as e:
                logger.error(e)
                messagebox.showerror("错误", "清除失败，将打开用户目录。")
                AppFunc.open_user_file()
                after()
                return

    @staticmethod
    def open_program_file():
        if getattr(sys, 'frozen', False):  # 打包环境
            executable_path = sys.executable
            # 打开文件夹
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.CurrentDirectory = os.path.dirname(executable_path)
            shell.Run(f'explorer /select,"{os.path.basename(executable_path)}"')
        else:
            messagebox.showinfo("提醒", "请从打包环境中使用此功能")
            return

    @staticmethod
    def mov_backup(new=None):
        if getattr(sys, 'frozen', False):  # 打包环境
            executable_dir = os.path.dirname(sys.executable)
        else:
            messagebox.showinfo("提醒", "请从打包环境中使用此功能")
            return
        answer = None
        if new is None:
            answer = messagebox.askokcancel(
                "确认清除",
                "是否删除旧版备份？\n（可从回收站中恢复）"
            )
        elif new is True:
            answer = messagebox.askokcancel(
                "确认清除",
                "已更新最新版，是否删除旧版备份？\n（可从回收站中恢复）"
            )

        items_to_delete = []

        if answer:
            # 移动文件夹到回收站
            for item in os.listdir(executable_dir):
                item_path = os.path.join(executable_dir, item)
                if os.path.isdir(item_path) and item.startswith("[") and item.endswith("]"):
                    items_to_delete.append(item_path)
            try:
                file_utils.move_files_to_recycle_bin(items_to_delete)
            except Exception as e:
                logger.error(e)
                messagebox.showerror("错误", f"移动文件夹到回收站时发生错误：\n"
                                             f"{str(e)}\n将打开程序文件夹")
                AppFunc.open_program_file()
            messagebox.showinfo("成功", "已成功移动到回收站！")

    @staticmethod
    def clear_statistic_data(after):
        """清除统计数据"""
        confirm = messagebox.askokcancel(
            "确认清除",
            "该操作将会清空统计的数据，请确认是否需要清除？"
        )
        if confirm:
            file_path = Config.STATISTIC_JSON_PATH
            try:
                file_utils.move_files_to_recycle_bin([file_path])
                print(f"已删除: {file_path}")
            except Exception as e:
                print(f"无法删除 {file_path}: {e}")
                logger.error(e)
            after()
            print("成功清除统计数据！")

    @staticmethod
    def create_app_lnk():
        """创建程序快捷方式"""
        # 打包后的环境？
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
        else:
            exe_path = os.path.abspath(r'./dist/极峰多聊38/极峰多聊/极峰多聊.exe')

        notice = []
        exe_dir = os.path.dirname(exe_path)
        exe_name = os.path.basename(exe_path)
        shortcut_name = os.path.splitext(exe_name)[0]  # 去掉 .exe 后缀
        desktop = winshell.desktop()

        # 定义子方法用于创建快捷方式
        def create_shortcut(suffix, arguments=""):
            """创建快捷方式"""
            formated_suffix = f"_{suffix}" if suffix != "" else ""
            shortcut_path = os.path.join(desktop, f"{shortcut_name}{formated_suffix}.lnk")
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.TargetPath = exe_path
            shortcut.Arguments = arguments
            shortcut.WorkingDirectory = exe_dir
            shortcut.IconLocation = exe_path
            shortcut.save()
            notice.append(f"{suffix}快捷方式已创建： {shortcut_path}")

        # 创建常规版本快捷方式
        create_shortcut("")  # 常规版，无后缀

        # 创建调试版快捷方式
        create_shortcut("调试版", "--debug")  # 添加 --debug 参数

        # 创建假装首次使用版快捷方式
        create_shortcut("假装首次使用版", "--new")  # 添加 --new 参数

        # 打印所有创建成功信息
        messagebox.showinfo("成功", "\n".join(notice))

    @staticmethod
    def check_auto_start_or_toggle_to_(target_state=None):
        startup_folder = sys_utils.get_startup_folder()
        print(startup_folder)
        if getattr(sys, 'frozen', False):
            # 如果是打包后的可执行文件
            app_path = sys.executable
        else:
            # 如果是源代码运行
            app_path = None

        if app_path is None:
            auto_start, paths = False, None
            shortcut_path = None
        else:
            auto_start, paths = file_utils.check_shortcut_in_folder(startup_folder, app_path)
            shortcut_name = os.path.splitext(os.path.basename(app_path))[0]
            shortcut_path = os.path.join(startup_folder, f"{shortcut_name}.lnk")

        if target_state is None:
            return True, auto_start

        else:
            try:
                if target_state is True:
                    file_utils.create_shortcut_for_(app_path, shortcut_path)
                elif target_state is False:
                    file_utils.move_files_to_recycle_bin(paths)
                return True, None
            except Exception as e:
                logger.error(e)
                return False, str(e)

    @classmethod
    def reset(cls, after):
        """
        重置应用设置和删除部分用户文件
        :param after: 结束后执行的方法：初始化
        :return: 无
        """
        # 显示确认对话框
        confirm = messagebox.askokcancel(
            "确认重置",
            "该操作需要关闭所有微信进程，将清空除配置文件外的所有文件及设置，请确认是否需要重置？"
        )

        if not confirm:
            messagebox.showinfo("操作取消", "重置操作已取消。")
        else:
            items_to_del = []
            try:
                # 恢复每个平台的补丁dll
                all_sw, = subfunc_file.get_remote_cfg(RemoteCfg.GLOBAL, **{RemoteCfg.SP_SW: []})
                # print(all_sw)
                for sw in all_sw:
                    sw_obj = cls.get_root_class().sw_classes[sw]
                    del_path = sw_obj.del_config_and_reset()
                    if del_path is not None:
                        items_to_del.append(del_path)
                    # dll_dir_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.DLL_DIR)
                    # if dll_dir_path is None:
                    #     continue
                    # patch_dll, = subfunc_file.get_remote_cfg(
                    #     sw, patch_dll=None)
                    # if patch_dll is None:
                    #     continue
                    # dll_path = os.path.join(dll_dir_path, patch_dll)
                    # bak_path = os.path.join(dll_dir_path, f"{patch_dll}.bak")
                    # del_path = os.path.join(dll_dir_path, f"{patch_dll}.del")
                    # try:
                    #     # 检查 .bak 文件是否存在
                    #     if os.path.exists(bak_path):
                    #         # 如果 ?.dll 存在，准备删除它
                    #         if os.path.exists(dll_path):
                    #             os.rename(dll_path, del_path)
                    #             items_to_del.append(del_path)
                    #             print(f"加入待删列表：{del_path}")
                    #         # 将 ?.dll.bak 文件重命名为 ?.dll
                    #         os.rename(bak_path, dll_path)
                    #         print(f"已恢复: {dll_path} from {bak_path}")
                    # except Exception as e:
                    #     logger.error(e)

                # 删除用户文件
                user_dir = Config.PROJ_USER_PATH
                items = [os.path.join(user_dir, item) for item in os.listdir(user_dir)]
                items_to_del.extend(items)

                try:
                    file_utils.move_files_to_recycle_bin(items_to_del)
                except Exception as e:
                    logger.error(e)

                messagebox.showinfo("重置完成", "目录已成功重置。")
                after()
            except Exception as e:
                logger.error(e)
                messagebox.showinfo("拒绝访问", "请确保微信已全部退出。")
