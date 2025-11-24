import os
import sys

from func_core.app_func_core import AppFuncCore
from functions import subfunc_file
from public.global_members import GlobalMembers

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
        self._curr_full_ver = subfunc_file.get_app_current_version()
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
            curr_full_ver = subfunc_file.get_app_current_version()
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