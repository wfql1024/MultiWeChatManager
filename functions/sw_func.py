from typing import Tuple, Optional

from func_core.sw_func_core import SwInfoFuncCore, SwOperatorCore
from functions import subfunc_file
from utils.logger_utils import Logger
import weakref


# class SwSettings:
#     def __init__(self):
#         self.view = None
#         self.inst_path = None
#         self.data_dir = None
#         self.dll_dir = None
#         self.ver = None

class Sw:
    _instances = weakref.WeakValueDictionary()

    def __new__(cls, sw_id):
        # 如果实例已存在，优先返回旧实例
        if sw_id in cls._instances:
            return cls._instances[sw_id]
        # 否则创建新实例
        instance = super().__new__(cls)
        cls._instances[sw_id] = instance
        return instance

    def __init__(self, sw_id):
        # 防止重复初始化
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.id = sw_id
        # ------- 初始化成员 -------
        self.frame = None
        self.available_revoke_channels = []
        self.load_main_patching_finished = False
        self._multirun_mode = None
        self._path = {}
        self._logo = None
        self._label = None
        self._ver = None
        self.classic_ui = None
        self.treeview_ui = None
        self.login_accounts = None
        self.logout_accounts = None
        self.widget_dict = {}
        self.is_original = None
        self.force_rescan = None
        # self.settings = SwSettings()
        self.view = None
        self.inst_path = None
        self.data_dir = None
        self.dll_dir = None

    @classmethod
    def reinit(cls, sw_id):
        """强制重新构造实例，相同 id 会替换之前的实例。"""
        instance = super(Sw, cls).__new__(cls)  # 直接创建新实例
        cls._instances[sw_id] = instance  # 覆盖旧实例
        instance.__init__(sw_id)  # 重新初始化
        return instance

    """属性"""

    @property
    def logo(self):
        logo = self._logo
        if logo is None:
            logo = SwInfoFuncCore.get_sw_logo(self.id)
        self._logo = logo
        return self._logo

    @property
    def label(self):
        label = self._label
        if label is None:
            label = SwInfoFuncCore.get_sw_origin_display_name(self.id)
        self._label = label
        return self._label

    @property
    def ver(self):
        ver = self._ver
        if ver is None:
            ver = SwInfoFuncCore.calc_sw_ver(self.id)
        self._ver = ver
        return self._ver

    """配置"""

    def del_config_and_reset(self):
        """删除配置并重置"""
        return SwOperatorCore.del_config_and_reset(self.id)

    def get_saved_setting(self, key, enum_cls=None):
        return SwInfoFuncCore.get_sw_setting_by_local_record(self.id, key, enum_cls)

    def save_setting_and_do(self, key, value, callback=None):
        return SwInfoFuncCore.save_sw_setting_to_local_record_and_call_back(self.id, key, value, callback)

    """互斥体"""

    def kill_all_mutexes_now(self):
        """立即查杀所有互斥体"""
        return SwOperatorCore.kill_all_mutexes_now(self.id)

    def can_freely_multirun(self):
        return SwInfoFuncCore.check_if_sw_can_freely_multirun(self.id)

    @property
    def multirun_mode(self):
        return SwInfoFuncCore.get_sw_multirun_mode(self.id)

    @multirun_mode.setter
    def multirun_mode(self, value):
        self._multirun_mode = value

    """路径"""

    def get_path_from_cache(self, path_type):
        path = None
        try:
            path = self._path[path_type]
        except Exception as e:
            Logger().warning(e)
        return path

    def try_get_path(self, path_type):
        """优先获取缓存, 再者已保存的路径, 若没有则通过方法自动搜寻"""
        # 从缓存拿
        path = self.get_path_from_cache(path_type)
        if path is not None:
            return path
        # 从文件拿
        path = SwInfoFuncCore.get_saved_path_of_(self.id, path_type)
        # Printer().debug(f"从本地记录获取{sw}的{path_type}路径: {path}")
        if path is None:
            # 重新探测
            path = SwInfoFuncCore.detect_path_of_(self.id, path_type)
        # 数据有效, 缓存起来
        if path is not None and path != "":
            if not isinstance(self._path, dict):
                self._path = {}
            self._path[path_type] = path
        return path

    def detect_path(self, path_type):
        path = SwInfoFuncCore.detect_path_of_(self.id, path_type)
        if not isinstance(self._path, dict):
            self._path = {}
        self._path[path_type] = path
        return path

    def backup_sw_all_patching_files(self):
        return SwOperatorCore.backup_sw_all_patching_files(self.id)

    def get_setting_by_local_record(self, key, enum_cls=None):
        return subfunc_file.fetch_a_setting_or_set_default_or_none(self.id, key, enum_cls)

    """登录"""
    def kill_sw_multiple_processes(self):
        return SwOperatorCore.kill_sw_multiple_processes(self.id)

    def open_sw_and_return_hwnd(self, exe=None) -> Tuple[Optional[int], str]:
        return SwOperatorCore.open_sw_and_return_hwnd(self.id, exe=exe)

    """账号"""

    def get_existed_accounts(self, only=None):
        return SwInfoFuncCore.get_sw_all_accounts_existed(self.id, only)

    def get_last_login_acc(self):
        return SwInfoFuncCore.get_curr_wx_id_from_cfg_file(self.id)

    """补丁"""

    def choose_channel_in_conflicts_and_switch_dll_to_(
            self, mode, channel, conflicts: list, coexist_channel=None, ordinal=None, target=None):
        """
        处理互斥方案打补丁
        :param mode: 模式
        :param channel: 当前操作方案
        :param conflicts: 冲突方案列表
        :param coexist_channel: 可选共存方案
        :param ordinal: 可选序号
        :param target: True=打补丁, False=撤销补丁, None=自动判断
        :return: True/False, 提示信息
        """
        return SwOperatorCore.choose_channel_in_conflicts_and_switch_dll_to_(
            self.id, mode, channel, conflicts, coexist_channel=coexist_channel, ordinal=ordinal, target=target)

    def identify_patch(
            self, mode, channels=None, coexist_channel=None, ordinal=None) -> Tuple[Optional[dict], str]:
        """
        检查当前补丁状态，返回结果字典(若没有适配则返回None)和消息
        结果字典格式: {channel1: {status:bool, msg:str}, channel2: {...}, ...}
        """
        return SwInfoFuncCore.identify_dll_core(self.id, mode, channels, coexist_channel, ordinal, self.force_rescan)

# class SwInfoFunc:
#     @staticmethod
#     def get_curr_wx_id_from_cfg_file(sw):
#         # Printer().debug(FuncTool.get_sw_acc_func_impl(AccInfoFuncImpl, sw))
#         return FuncTool.get_sw_acc_func_impl(SwInfoFuncImpl, sw).get_curr_wx_id_from_config_file(sw)