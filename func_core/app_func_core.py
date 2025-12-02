import datetime as dt
import json
import os
import re
import shutil
import sys
import threading
import time
from tkinter import messagebox
from typing import Union, Tuple

import psutil
import requests
import win32com
import winshell
from PIL import Image
from pystray import Menu
from win32com.client import Dispatch

from data_access import SwAccData
from data_access.setting import LocalSetting, RootSetting, RemoteSw, StatisticData, RemoteGlobal
from public import Strings
from public.config import Config
from public.enums import LocalCfgKey, RemoteGlobalKey, SwStates, RemoteSwKey, RootCfgKey
from public.global_members import GlobalMembers
from utils import file_utils, sys_utils
from utils.encoding_utils import CryptoUtils
from utils.logger_utils import mylogger as logger, Logger


class AppFuncCore:
    @staticmethod
    def get_user_dir():
        return RootSetting().user_dir

    @staticmethod
    def get_sw_acc_data(*addr, **kwargs):
        return SwAccData().get_(*addr, **kwargs)

    @staticmethod
    def get_remote_sw(*addr, **kwargs):
        return RemoteSw().get_(*addr, **kwargs)

    @staticmethod
    def get_remote_global(*addr, **kwargs):
        return RemoteGlobal().get_(*addr, **kwargs)

    @staticmethod
    def get_root_settings(*addr, **kwargs):
        return RootSetting().get_(*addr, **kwargs)

    @staticmethod
    def update_root_settings(*front_addr, **kwargs):
        return RootSetting().update_(*front_addr, **kwargs)

    @staticmethod
    def get_global_settings(*addr, **kwargs):
        return LocalSetting().get_(LocalCfgKey.GLOBAL_SECTION, *addr, **kwargs)

    @staticmethod
    def update_global_settings(*front_addr, **kwargs):
        return LocalSetting().update_(LocalCfgKey.GLOBAL_SECTION, *front_addr, **kwargs)

    @staticmethod
    def fetch_global_setting_or_set_default(key, enum_cls=None):
        """从本地记录获取软件全局设置值"""
        return LocalSetting().fetch_or_set_default_or_none(LocalCfgKey.GLOBAL_SECTION, key, enum_cls)

    @staticmethod
    def save_global_setting_and_check_changed(key, value):
        try:
            return LocalSetting().save_and_check_changed(LocalCfgKey.GLOBAL_SECTION, key, value)
        except Exception as e:
            Logger().error(e)
            return e

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
        user_dir = RootSetting().user_dir
        if os.path.exists(user_dir):
            desktop = winshell.desktop()
            ts = time.strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(desktop, f"user_files_backup_{ts}")
            print(f"备份路径: {backup_path}")
            shutil.move(user_dir, backup_path)
            print(f"旧版数据已备份至: {backup_path}")

        # 5. 拷贝旧版数据
        shutil.copytree(old_user_path, user_dir)
        print(f"旧版数据已拷贝至: {user_dir}")

        # 6. 完成提示
        messagebox.showinfo("完成", "导入完成！")

        GlobalMembers().get_root_class().initialize_in_root()

    @staticmethod
    def create_tray(root):
        from pystray import Icon, MenuItem
        def on_restore(_icon, _item=None):
            root.after(0, lambda: root.deiconify())

        def on_exit(_icon, _item=None):
            _icon.visible = False
            _icon.stop()
            root.after(0, root.destroy)
        # 给托盘图标绑定鼠标点击恢复窗口
        def setup(icon):
            icon.visible = True
            icon._run_detached = True  # 防止点击后阻塞
            icon.icon = icon_img
            icon.menu = menu
            icon.title = "极峰多聊"
            icon.update_menu()

        def run_icon():
            try:
                print("隐藏主界面")
                root.after(0, root.withdraw)
                GlobalMembers().get_root_class().app.global_settings_value.in_tray = True
                print("安装图标")
                tray_icon.run(setup)
            except Exception as e:
                tray_icon.stop()
                root.after(0, root.deiconify)
                GlobalMembers().get_root_class().app.global_settings_value.in_tray = False
                Logger().error(e)
                messagebox.showerror("错误", f"创建托盘图标失败: {e}")

        menu = Menu(
            MenuItem("打开主界面", on_restore, default=True),
            MenuItem("退出", on_exit)
        )
        icon_img = Image.open(Config.PROJ_ICO_PATH)
        tray_icon = None
        tray_icon = Icon("JFMC", icon_img, title="极峰多聊", menu=menu)
        # 在后台线程中运行托盘图标
        threading.Thread(target=run_icon, daemon=True).start()

        return tray_icon

    @classmethod
    def apply_proxy_setting(cls):
        use_proxy = cls.fetch_global_setting_or_set_default(
            LocalCfgKey.USE_PROXY)
        print(use_proxy)
        if use_proxy is True:
            proxy_ip = cls.fetch_global_setting_or_set_default(LocalCfgKey.PROXY_IP)
            proxy_port = cls.fetch_global_setting_or_set_default(LocalCfgKey.PROXY_PORT)
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
        success, result = AppFuncCore.split_vers_by_cur_from_local(curr_ver)
        if success is True:
            new_versions, old_versions = result
            if new_versions:
                return True
        return False

    @staticmethod
    def get_app_current_version():
        # 获取版本号
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
            version_number = file_utils.get_file_version(exe_path)  # 获取当前执行文件的版本信息
        else:
            with open(Config.VERSION_FILE, 'r', encoding='utf-8') as version_file:
                version_info = version_file.read()
                # 使用正则表达式提取文件版本
                match = re.search(r'filevers=\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', version_info)
                if match:
                    version_number = '.'.join([match.group(1), match.group(2), match.group(3), match.group(4)])
                else:
                    version_number = "未知版本"

        return f"v{version_number}-{Config.VER_STATUS}"

    @classmethod
    def split_vers_by_cur_from_local(cls, current_ver) -> Union[Tuple[bool, Tuple[list, list]], Tuple[bool, str]]:
        """
        从本地获取所有版本号，然后根据当前版本号将其分为两部分：
        一部分是高于或等于当前版本号的，另一部分是低于当前版本号的。
        :param current_ver: 当前版本
        :return: Union[Tuple[成功, Tuple[新版列表, 旧表列表]], Tuple[失败, 错误信息]]
        """
        try:
            # 获取 update 节点的所有版本
            all_versions_dict = cls.get_remote_global(RemoteGlobalKey.UPDATE)
            if not isinstance(all_versions_dict, dict):
                return False, "错误：数据格式错误"
            all_versions = list(all_versions_dict.keys())
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
        user_dir = RootSetting().user_dir
        try:
            if not os.path.exists(user_dir):
                os.makedirs(user_dir)
            os.startfile(user_dir)
        except Exception as e:
            Logger().error(e)
            return False, e

    @staticmethod
    def clear_user_file(after):
        """清除用户文件夹"""
        confirm = messagebox.askokcancel(
            "确认清除",
            "该操作将会清空头像、昵称、配置的路径等数据，请确认是否需要清除？"
        )
        user_dir = RootSetting().user_dir
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
                AppFuncCore.open_user_file()
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
                AppFuncCore.open_program_file()
            messagebox.showinfo("成功", "已成功移动到回收站！")

    @staticmethod
    def force_fetch_remote_encrypted_cfg(ns=RootCfgKey.REMOTE_SW_NS.value, url=None):
        """强制从网络中获取最新的配置文件"""
        print(f"正从远程源下载...")
        if ns == RootCfgKey.REMOTE_SW_NS:
            seen = set()
            urls_raw = []
            user_url = RootSetting().remote_sw_url
            builtin_url = [Strings.REMOTE_SW_GITEE, Strings.REMOTE_SW_GITHUB]
            remote_cfg_path = RemoteSw().get_file_path_from_root_cfg()
        elif ns == RootCfgKey.REMOTE_GLOBAL_NS:
            seen = set()
            urls_raw = []
            user_url = RootSetting().remote_global_url
            builtin_url = [Strings.REMOTE_GLOBAL_GITEE, Strings.REMOTE_GLOBAL_GITHUB]
            remote_cfg_path = RemoteGlobal().get_file_path_from_root_cfg()
        else:
            return None
        # 拼接
        if user_url is not None and user_url != "":
            urls_raw.append(user_url)
        urls_raw.extend(builtin_url)
        # 去重
        urls = [u for u in urls_raw if not (u in seen or seen.add(u))]
        # 方法指定的, 放在首位
        if url is not None:
            urls = [url].extend(urls)

        for url in urls:
            print(f"正在尝试从此处下载: {url}...")
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    with open(remote_cfg_path, 'w', encoding='utf-8') as remote_cfg:
                        decrypted_data = CryptoUtils.decrypt_response(response.text)
                        remote_cfg.write(decrypted_data)  # 将下载的 JSON 保存到文件
                    print(f"成功从 {url} 获取并保存 JSON 文件")
                    return json.loads(decrypted_data)  # 返回加载的 JSON 数据
                else:
                    print(f"获取失败: {response.status_code}，尝试下一个源...")

            except requests.exceptions.Timeout:
                Logger().warning(f"请求 {url} 超时，尝试下一个源...")
            except Exception as e:
                Logger().error(f"从 {url} 获取时发生错误: {e}，尝试下一个源...")

        return None

    @classmethod
    def _try_read_remote_cfg_locally(cls, ns=RootCfgKey.REMOTE_SW_NS):
        """
        尝试从本地读取配置数据，优先从本地获取，成功后停止；失败会从网络下载远程配置
        :return: 是否成功；数据
        """
        remote_cfg = None
        if ns == "RemoteSw":
            remote_cfg_path = RemoteSw().get_file_path_from_root_cfg()
        elif ns == "RemoteGlobal":
            remote_cfg_path = RemoteGlobal().get_file_path_from_root_cfg()
        else:
            return None
        try:
            with open(remote_cfg_path, 'r', encoding='utf-8') as f:
                remote_cfg = json.load(f)
            # remote_cfg = RemoteSetting().get_()
        except Exception as e:
            Logger().error(f"错误：读取本地 JSON 文件失败: {e}，尝试从云端下载")
            try:
                remote_cfg = cls.force_fetch_remote_encrypted_cfg(ns)
                Logger().info(f"成功从云端下载了配置文件!")
            except Exception as e:
                Logger().error(f"错误：从云端下载 JSON 文件失败: {e}")
        return remote_cfg

    @classmethod
    def read_remote_cfg_in_rules(cls, ns=RootCfgKey.REMOTE_SW_NS):
        """
        有策略地获取远程配置：
            检查是否到了需要强制更新的日期，
            如果是，则强制从网络获取，失败则使用本地，成功则将日期往后推；
            如果不是，则从本地获取。
        :return:
        """
        # 获取存储的日期
        next_check_time_str = LocalSetting().fetch_or_set_default_or_none(
            LocalCfgKey.GLOBAL_SECTION, LocalCfgKey.NEXT_CHECK_TIME)
        if not isinstance(next_check_time_str, str):
            next_check_time = dt.datetime.today().date()
        else:
            # 将字符串日期解析为日期对象
            next_check_time = dt.datetime.strptime(next_check_time_str, "%Y-%m-%d").date()
        today = dt.datetime.today().date()
        # 如果今天的日期大于等于 next_check_time 或者不存在远程配置文件，执行代码并更新 next_check_time
        if today >= next_check_time:
            # 强制获取远程配置
            config_data = cls.force_fetch_remote_encrypted_cfg(ns)
            if config_data is not None:
                # 更新 next_check_time 为明天
                next_check_time = today + dt.timedelta(days=1)
                next_check_time_str = next_check_time.strftime("%Y-%m-%d")
                LocalSetting().save_and_check_changed(
                    LocalCfgKey.GLOBAL_SECTION, LocalCfgKey.NEXT_CHECK_TIME, next_check_time_str)
                return config_data
            else:
                # 失败加载本地
                return cls._try_read_remote_cfg_locally(ns)
        else:
            # 不到时间直接加载本地
            return cls._try_read_remote_cfg_locally(ns)

    @classmethod
    def clear_statistic_data(cls, after):
        """清除统计数据"""
        confirm = messagebox.askokcancel(
            "确认清除",
            "该操作将会清空统计的数据，请确认是否需要清除？"
        )
        if confirm:
            file_path = StatisticData().get_file_path_from_root_cfg()
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

    """结构调整相关"""

    @staticmethod
    def merge_refresh_nodes():
        """统计数据结构改变后，将所有的节点分流到classic和tree中"""
        data = StatisticData().get_()
        # 确保 refresh 节点存在
        if "refresh" not in data or not isinstance(data["refresh"], dict):
            return data

        print("数据结构调整：需要进行刷新节点分流...")
        refresh_data = data["refresh"]

        # 初始化 classic 和 tree，如果不存在则创建
        refresh_data.setdefault("classic", {})
        refresh_data.setdefault("tree", {})

        # 遍历 refresh 中的所有节点
        for key, value in list(refresh_data.items()):
            # 跳过 classic 和 tree 节点
            if key in ("classic", "tree"):
                continue

            # 将当前节点合并到 classic
            if isinstance(value, str):  # 如果是字符串
                refresh_data["classic"][key] = value
            elif isinstance(value, dict):  # 如果是字典
                refresh_data["classic"].update(value)

            # 将当前节点合并到 tree
            if isinstance(value, str):  # 如果是字符串
                refresh_data["tree"][key] = value
            elif isinstance(value, dict):  # 如果是字典
                refresh_data["tree"].update(value)

            # 删除原始节点
            del refresh_data[key]
        StatisticData().save(data)
        return data

    @staticmethod
    def move_data_to_wechat():
        """统计数据结构改变后，将原本所有的数据移动到WeChat节点下"""
        data = StatisticData().get_()

        # 检查是否已有 "WeChat" 节点
        if "WeChat" not in data:
            print("数据结构调整：将数据置于到微信节点下...")
            wechat_data = {
                "WeChat": data
            }
            StatisticData().save(wechat_data)

    @staticmethod
    def swap_cnt_and_mode_levels_in_auto():
        """将auto表中的次数节点和模式节点交换层级"""
        data = StatisticData().get_()
        for sw in data.keys():
            auto_info = data.get(sw, {}).get("auto", {})
            # print(auto_info)

            # 已经升级结构的标志
            if 'avg' in auto_info.keys():
                continue

            print(f"数据结构调整：对调{sw}节点下的二三级层级...")
            tmp = {}
            # 交换层级
            for second_level_key, third_level_dict in auto_info.items():
                print(auto_info[second_level_key].keys())
                for third_level_key, value in third_level_dict.items():
                    # 如果第三级键还未在结果字典中初始化，则创建一个新的字典
                    if third_level_key not in tmp:
                        tmp[third_level_key] = {}
                    # 将二级键作为新的第三级键
                    tmp[third_level_key][second_level_key] = value
            # print(tmp)

            # 执行完更新后就添加avg节点
            if 'avg' not in tmp.keys():
                tmp['avg'] = {}

            # 转换好的结果重新赋给json文件中
            data[sw]['auto'] = tmp
        StatisticData().save(data)

    @staticmethod
    def downgrade_item_lvl_under_manual():
        """将manual表中的节点降级"""
        data = StatisticData().get_()
        for sw in data.keys():
            manual_info = data.get(sw, {}).get("manual", {})
            # print(manual_info)

            # 已经升级结构的标志
            if '_' in manual_info.keys():
                continue

            print("数据结构调整：将手动节点内容降低一个层级...")
            tmp = manual_info
            manual_info = {
                "_": tmp
            }

            # 转换好的结果重新赋给json文件中
            data[sw]['manual'] = manual_info
        StatisticData().save(data)

    @staticmethod
    def get_all_enable_sw() -> list:
        """获取所有启用的平台"""
        all_sw_list, = RemoteGlobal().get_(**{RemoteSwKey.SP_SW: []})
        all_enable_sw = []
        for sw in all_sw_list:
            state = LocalSetting().get_(sw, LocalCfgKey.STATE)
            if state == SwStates.HIDDEN or state == SwStates.VISIBLE:
                all_enable_sw.append(sw)
        return all_enable_sw

    @staticmethod
    def get_all_visible_sw() -> list:
        """获取所有可见的平台"""
        all_sw_list, = RemoteGlobal().get_(**{RemoteSwKey.SP_SW: []})
        all_visible_sw = []
        for sw in all_sw_list:
            state = LocalSetting().get_(sw, LocalCfgKey.STATE)
            if state == SwStates.VISIBLE:
                all_visible_sw.append(sw)
        return all_visible_sw
