import os
import sys
import threading
import time
from tkinter import messagebox
from typing import Callable, Dict

from func_core.acc_func_core import AccOperatorCore, AccInfoFuncCore
from func_core.app_func_core import AppFuncCore
from func_core.sw_func_core import SwOperatorCore, SwInfoFuncCore
from public.enums import RootCfgKey, RemoteGlobalKey
from public.global_members import GlobalMembers
from utils import file_utils
from utils.logger_utils import Logger


class App:
    _instance = None
    _root_class_initialized = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 防止重复初始化
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        # ------- 初始化成员 -------
        self._name = os.path.basename(sys.argv[0])
        self._author = "吾峰起浪"
        self._curr_full_ver = AppFuncCore.get_app_current_version()
        self._need_update = None
        self._hint = "狂按"
        self._global_settings_value = GlobalSettings()
        self._global_settings_var = GlobalSettings()
        self._root_class = AppFunc.get_root_class()

    @classmethod
    def reinit(cls):
        """强制重新构造实例，相同 id 会替换之前的实例。"""
        instance = super(App, cls).__new__(cls)  # 直接创建新实例
        cls._instance = instance  # 覆盖旧实例
        instance.__init__()  # 重新初始化
        return instance

    """根配置"""

    @staticmethod
    def get_root_settings(*addr, **kwargs):
        return AppFuncCore.get_root_settings(*addr, **kwargs)

    @staticmethod
    def update_root_settings(*addr, **kwargs):
        """更新软件设置"""
        return AppFuncCore.update_root_settings(*addr, **kwargs)

    @staticmethod
    def get_user_dir():
        return AppFuncCore.get_user_dir()

    """本地配置"""

    @staticmethod
    def get_settings(*addr, **kwargs):
        return AppFuncCore.get_global_settings(*addr, **kwargs)

    @staticmethod
    def fetch_setting_or_set_default(key, enum_cls=None):
        return AppFuncCore.fetch_global_setting_or_set_default(key, enum_cls)

    @staticmethod
    def update_settings(*addr, **kwargs):
        """更新软件设置"""
        return AppFuncCore.update_global_settings(*addr, **kwargs)

    @staticmethod
    def save_setting_and_do(key, value, callback=None):
        changed = AppFuncCore.save_global_setting_and_check_changed(key, value)
        if changed is True:
            print(f"成功修改{key}为{value}！")
        elif changed is False:
            print(f"一致的值：{key}为{value}！")
        if changed is not None:
            if isinstance(callback, Callable):
                callback()
        else:
            print("修改错误！")

    """账号信息"""

    @staticmethod
    def get_sw_acc_data(*addr, **kwargs):
        return AppFuncCore.get_sw_acc_data(*addr, **kwargs)

    """远程配置"""

    @staticmethod
    def get_remote_sw(*addr, **kwargs):
        return AppFuncCore.get_remote_sw(*addr, **kwargs)

    @staticmethod
    def get_remote_global(*addr, **kwargs):
        return AppFuncCore.get_remote_global(*addr, **kwargs)

    @staticmethod
    def force_get_remote_cfg(ns=RootCfgKey.REMOTE_SW_NS):
        return AppFuncCore.force_fetch_remote_encrypted_cfg(ns)

    @staticmethod
    def regularly_get_remote_cfg(ns=RootCfgKey.REMOTE_SW_NS):
        return AppFuncCore.read_remote_cfg_in_rules(ns)

    @staticmethod
    def reset(after):
        AppFunc.reset(after)

    @property
    def name(self):
        name = self._name
        if name is None:
            name = os.path.basename(sys.argv[0])
            self._name = name
        return self._name

    @property
    def author(self):
        author = self._author
        if author is None:
            author = "吾峰起浪"
            self._author = author
        return self._author

    @property
    def curr_full_ver(self):
        curr_full_ver = self._curr_full_ver
        if curr_full_ver is None:
            curr_full_ver = AppFuncCore.get_app_current_version()
            self._curr_full_ver = curr_full_ver
        return self._curr_full_ver

    @property
    def need_update(self):
        need_update = self._need_update
        if need_update is None:
            need_update = AppFuncCore.has_newer_version(self.curr_full_ver)
            self._need_update = need_update
        return self._need_update

    @property
    def hint(self):
        hint = self._hint
        if hint is None:
            hint = "狂按"
            self._hint = hint
        return self._hint

    @property
    def global_settings_value(self):
        if not isinstance(self._global_settings_value, GlobalSettings):
            self._global_settings_value = GlobalSettings()
        return self._global_settings_value

    @global_settings_value.setter
    def global_settings_value(self, value):
        if not isinstance(value, GlobalSettings):
            raise TypeError("value must be GlobalSettings")
        self._global_settings_value = value

    @property
    def global_settings_var(self):
        if not isinstance(self._global_settings_var, GlobalSettings):
            self._global_settings_var = GlobalSettings()
        return self._global_settings_var

    @global_settings_var.setter
    def global_settings_var(self, value):
        if not isinstance(value, GlobalSettings):
            raise TypeError("value must be GlobalSettings")
        self._global_settings_var = value

    @property
    def root_class(self):
        if self._root_class is None:
            self._root_class = AppFunc.get_root_class()
        return AppFunc.get_root_class()

    @root_class.setter
    def root_class(self, value):
        if self._root_class_initialized is not True:
            self._root_class = value
            self._root_class_initialized = True
        else:
            pass

    @property
    def user_dir(self):
        return self.get_user_dir()


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
        return GlobalMembers().get_root_class()

    @staticmethod
    def reset(after):
        """
        重置应用设置和删除部分用户文件
        :param after: 结束后执行的方法：初始化
        :return: 无
        """
        # 显示确认对话框
        confirm = messagebox.askokcancel(
            "确认重置",
            "该操作需要关闭所有平台进程，将清空除配置文件外的所有文件及设置，请确认是否需要重置？"
        )

        if not confirm:
            messagebox.showinfo("操作取消", "重置操作已取消。")
        else:
            items_to_del = []
            try:
                # 恢复每个平台的补丁dll
                all_sw, = AppFuncCore.get_remote_global(**{RemoteGlobalKey.SP_SW: []})
                # print(all_sw)
                for sw in all_sw:
                    # sw_obj = cls.get_root_class().get_sw_obj(sw)
                    # del_path = sw_obj.del_config_and_reset()
                    del_paths = SwOperatorCore.restore_dll_and_get_del_paths(sw)
                    if isinstance(del_paths, list):
                        items_to_del.extend(del_paths)

                # 删除用户文件
                user_dir = AppFuncCore.get_user_dir()
                items = [os.path.join(user_dir, item) for item in os.listdir(user_dir)]
                items_to_del.extend(items)

                try:
                    file_utils.move_files_to_recycle_bin(items_to_del)
                except Exception as e:
                    Logger().error(e)

                messagebox.showinfo("重置完成", "目录已成功重置。")
                after()
            except Exception as e:
                Logger().error(e)
                messagebox.showinfo("拒绝访问", "请确保微信已全部退出。")

    @classmethod
    def _login_auto_start_accounts(cls):
        all_sw = AppFuncCore.get_all_enable_sw()
        print("所有平台：", all_sw)
        # 获取需要自启动的账号
        accounts_to_auto_start: Dict[str, set] = {}
        for sw in all_sw:
            if sw not in accounts_to_auto_start:
                accounts_to_auto_start[sw] = set()
            sw_data = SwInfoFuncCore.get_sw_acc_data(sw)
            if sw_data is None:
                continue
            for acc in sw_data:
                auto_start, = SwInfoFuncCore.get_sw_acc_data(sw, acc, auto_start=None)
                if auto_start is True:
                    accounts_to_auto_start[sw].add(acc)
        print(f"设置了自启动：{accounts_to_auto_start}")
        # 获取已经登录的账号
        for sw in accounts_to_auto_start:
            success, result = AccInfoFuncCore.get_sw_accounts_login_status(sw)
            if success is not True:
                continue
            acc_list_dict, _ = result
            logins = acc_list_dict["login"]
            if isinstance(logins, list):
                for acc in logins:
                    accounts_to_auto_start[sw].discard(acc)
        # 登录需要自启但未登录的账号
        if not any(len(sw_set) != 0 for sw, sw_set in accounts_to_auto_start.items()):
            print("自启动账号都已登录完毕！")
            return
        print(f"排除已登录之后需要登录：{accounts_to_auto_start}")
        # 打印即将自动登录的提示
        for i in range(0, 3):
            print(f"即将自动登录：{3 - i}秒")
            time.sleep(1)
        login_dict = {}
        for sw, acc_set in sorted(accounts_to_auto_start.items(), reverse=True):
            if not isinstance(acc_set, set) or len(acc_set) == 0:
                continue
            login_dict[sw] = list(acc_set)
        print(login_dict)
        # 遍历登录需要自启但未登录的账号
        try:
            AccOperatorCore.start_login_accounts_thread(login_dict)
        except Exception as e:
            Logger().error(e)
            return

    @classmethod
    def thread_to_login_auto_start_accounts(cls):
        try:
            threading.Thread(target=cls._login_auto_start_accounts).start()
        except Exception as e:
            Logger().error(e)
