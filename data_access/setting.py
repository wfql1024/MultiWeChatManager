import math
import os
import re
import sys
from enum import Enum
from typing import Union, Dict, Tuple, Any, Optional, Type

from public import Config, Strings
from public.enums import SwEnum, RootCfgKey
from utils import file_utils
from utils.file_utils import JsonUtils, DictUtils
from utils.logger_utils import Logger


class AbsSetting:
    """单例的抽象类, 子类也具有单例模式"""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, path=None):
        self._data = {}
        if path is not None:
            self._data_src = path

    def set_data_src(self, path):
        self._data_src = path

    def load(self) -> dict:
        """默认json格式, 可以重写"""
        self._data = JsonUtils.load_json(self._data_src)
        return self._data

    def _save(self):
        return self.save(self._data)

    def save(self, data):
        """默认json格式, 可以重写"""
        return JsonUtils.save_json(self._data_src, data)

    def clear_node(self, *addr) -> bool:
        """
        根据路径找到对应节点,将节点置为空字典或None
        :return: 是否成功
        """
        try:
            # print(f"置空{addr}处数据...")
            data = self.load()
            DictUtils.clear_nested_values(data, *addr)
            self._save()
            return True
        except Exception as e:
            Logger().error(e)
            return False

    def del_node(self, *addr) -> bool:
        """
        根据路径找到对应节点,将节点删除
        :return: 是否成功
        """
        try:
            # print(f"删除{addr}处数据...")
            data = self.load()
            DictUtils.del_nested_values(data, *addr)
            self._save()
            return True
        except Exception as e:
            Logger().error(e)
            return False

    def update_(self, *front_addr, **kwargs) -> bool:
        """更新账户信息到 JSON"""
        try:
            data = self.load()
            success = DictUtils.set_nested_values(data, None, *front_addr, **kwargs)
            self._save()
            return success
        except Exception as e:
            Logger().error(e)
            return False

    def get_(self, *front_addr, **kwargs) -> Union[Dict, Tuple[Any, ...]]:
        """
        根据用户输入的变量名，获取对应的账户信息
        :param front_addr: 前置地址，如：("wechat", "account1")
        :param kwargs: 需要获取的键地址及其默认值（如 note="", nickname=None）
        :return: 包含所请求数据的元组
        """
        data = self.load()
        return DictUtils.get_nested_values(data, None, *front_addr, **kwargs)

    @property
    def data(self):
        return self.load()


class RootSetting(AbsSetting):
    def __init__(self, path=None):
        super().__init__()
        if path is not None:
            self.set_data_src(path)
        else:
            self.set_data_src(self.ver_root_dir + "/" + Config.ROOT_CONFIG_PATH_SUFFIX)

    def get_current_ver_root_dir(self):
        """获取当前版本的根配置目录"""
        version = self.get_app_current_version()
        try:
            ver_root_dir = Config.ROOT_DATA_ADDR.replace("%VER%", version)
        except Exception as e:
            print(e)
            ver_root_dir = Config.ROOT_DATA_ADDR + f"/{version}"
        return ver_root_dir

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

    def fetch_user_dir_or_set_default(self):
        user_dir, = self.get_(**{RootCfgKey.USER_DIR: None})
        if user_dir is None:
            user_dir = self.ver_root_dir + "/" + Config.DEFAULT_USER_DIR_SUFFIX
            self.update_(**{RootCfgKey.USER_DIR: user_dir})
        return user_dir

    def fetch_remote_sw_url_or_set_default(self):
        remote_sw_url, = self.get_(**{RootCfgKey.REMOTE_SW: None})
        if remote_sw_url is None:
            remote_sw_url = Strings.REMOTE_SW_GITEE
            self.update_(**{RootCfgKey.REMOTE_SW: remote_sw_url})
        return remote_sw_url

    def fetch_remote_global_url_or_set_default(self):
        remote_global_url, = self.get_(**{RootCfgKey.REMOTE_GLOBAL: None})
        if remote_global_url is None:
            remote_global_url = Strings.REMOTE_GLOBAL_GITEE
            self.update_(**{RootCfgKey.REMOTE_GLOBAL: remote_global_url})
        return remote_global_url

    @property
    def ver_root_dir(self):
        return self.get_current_ver_root_dir()

    @property
    def user_dir(self):
        return self.fetch_user_dir_or_set_default()

    @property
    def remote_sw_url(self):
        return self.fetch_remote_sw_url_or_set_default()

    @property
    def remote_global_url(self):
        return self.fetch_remote_global_url_or_set_default()


class LocalSetting(AbsSetting):
    def __init__(self, path=None):
        super().__init__()
        if path is not None:
            self.set_data_src(path)
        else:
            setting_path = self.get_file_path_from_root_cfg()
            self.set_data_src(setting_path)

    @staticmethod
    def get_file_path_from_root_cfg():
        user_dir = RootSetting().user_dir
        setting_path = os.path.join(user_dir, Config.LOCAL_SETTING_PATH_SUFFIX).replace("\\", "/")
        return setting_path

    def save_and_check_changed(self, section, key, value):
        """
        保存设置并回调
        :param section: 配置文件中的section
        :param key: 配置文件中的key
        :param value: 配置文件中的value
        :return:
        """
        changed = False
        origin_value = self.get_(section, key)
        # 如果value是枚举类,则获取其值
        if isinstance(value, Enum):
            value = value.value
        self.update_(section, **{key: value})

        new_value = self.get_(section, key)
        if new_value != origin_value:
            changed = True
        return changed

    def fetch_or_set_default_or_none(self, section: str, setting_key: str, enum_cls: Optional[Type[Enum]] = None):
        """
        获取配置项，若没有则设置默认值，若没有默认值则返回None
        若传入枚举类，会严格验证值是否在枚举范围内，无效则使用枚举第一个值

        :param section: 配置文件中的section
        :param setting_key: 配置键名
        :param enum_cls: 可选枚举类（用于严格验证值）
        :return: 配置值（保证符合枚举约束）或None
        """
        # 原值
        value, = self.get_(section, **{setting_key: None})
        if value in (None, "", "None", "none", "null", "NULL"):
            try:
                # 默认值
                try:
                    sw_dict = Config.INI_DEFAULT_VALUE[section]
                except KeyError as ke:
                    print(ke)
                    sw_dict = Config.INI_DEFAULT_VALUE[SwEnum.DEFAULT]
                value = sw_dict[setting_key]
                pass
            except (KeyError, AttributeError) as e:
                print(e)
                # 空值
                value = None
        if isinstance(value, Enum):
            value = value.value
        # 若使用了枚举,检测值是否在枚举范围内，无效则使用枚举第一个值
        if enum_cls is not None:
            valid_values = {e.value for e in enum_cls}  # 保持原始大小写
            if value not in valid_values:
                value = next(iter(enum_cls)).value  # 使用第一个枚举值

        self.update_(section, **{setting_key: value})
        return value


class RemoteSw(AbsSetting):
    def __init__(self, path=None):
        super().__init__()
        if path is not None:
            self.set_data_src(path)
        else:
            setting_path = self.get_file_path_from_root_cfg()
            self.set_data_src(setting_path)

    @staticmethod
    def get_file_path_from_root_cfg():
        user_dir = RootSetting().user_dir
        setting_path = os.path.join(user_dir, Config.REMOTE_SW_PATH_SUFFIX).replace("\\", "/")
        return setting_path

    def _save(self):
        """本配置是只读文件, 不能修改"""
        raise NotImplementedError

    def save(self, data):
        """本配置是只读文件, 不能修改"""
        raise NotImplementedError


class RemoteGlobal(AbsSetting):
    def __init__(self, path=None):
        super().__init__()
        if path is not None:
            self.set_data_src(path)
        else:
            setting_path = self.get_file_path_from_root_cfg()
            self.set_data_src(setting_path)

    @staticmethod
    def get_file_path_from_root_cfg():
        user_dir = RootSetting().user_dir
        setting_path = os.path.join(user_dir, Config.REMOTE_GLOBAL_PATH_SUFFIX).replace("\\", "/")
        return setting_path

    def _save(self):
        """本配置是只读文件, 不能修改"""
        raise NotImplementedError

    def save(self, data):
        """本配置是只读文件, 不能修改"""
        raise NotImplementedError


class SwCache(AbsSetting):
    def __init__(self, path=None):
        super().__init__()
        if path is not None:
            self.set_data_src(path)
        else:
            setting_path = self.get_file_path_from_root_cfg()
            self.set_data_src(setting_path)

    @staticmethod
    def get_file_path_from_root_cfg():
        user_dir = RootSetting().user_dir
        setting_path = os.path.join(user_dir, Config.SW_CACHE_PATH_SUFFIX).replace("\\", "/")
        return setting_path


class SwAccData(AbsSetting):
    def __init__(self, path=None):
        super().__init__()
        if path is not None:
            self.set_data_src(path)
        else:
            setting_path = self.get_file_path_from_root_cfg()
            self.set_data_src(setting_path)

    @staticmethod
    def get_file_path_from_root_cfg():
        user_dir = RootSetting().user_dir
        setting_path = os.path.join(user_dir, Config.SW_ACC_PATH_SUFFIX).replace("\\", "/")
        return setting_path


class StatisticData(AbsSetting):
    def __init__(self, path=None):
        super().__init__()
        if path is not None:
            self.set_data_src(path)
        else:
            setting_path = self.get_file_path_from_root_cfg()
            self.set_data_src(setting_path)

    @staticmethod
    def get_file_path_from_root_cfg():
        user_dir = RootSetting().user_dir
        setting_path = os.path.join(user_dir, Config.STATISTIC_PATH_SUFFIX).replace("\\", "/")
        return setting_path

    def update_statistic_data(self, sw, mode, main_key, sub_key, time_spent):
        """更新时间统计"""
        print(sw, mode, main_key, sub_key, time_spent)
        if mode == "manual" and time_spent > 20:
            return
        if mode == "auto" and time_spent > 60:
            return
        if mode == 'refresh' and time_spent > 2:
            return

        data = self.get_()
        if sw not in data:
            Logger().info(f"sw不存在：{sw}")
            data[sw] = {}
        tab_info = data.get(sw, {})
        if mode not in tab_info:
            Logger().info(f"mode不存在：{mode}")
            tab_info[mode] = {}
        if main_key not in tab_info[mode]:
            Logger().info(f"main_key不存在：{main_key}")
            tab_info[mode][main_key] = {}
        if sub_key not in tab_info[mode][main_key]:
            Logger().info(f"sub_key不存在：{sub_key}")
            tab_info[mode][main_key][sub_key] = f"{math.inf},0,0,0"  # 初始化为“最短时间, (次数, 平均用时), 最长时间”

        # 获取当前最小、最大值，次数，平均用时
        current_min, count, avg_time, current_max = map(
            lambda x: float(x) if x != "null" else 0, tab_info[mode][main_key][sub_key].split(","))

        # 更新最小和最大值
        new_min = min(current_min or math.inf, time_spent)
        new_max = max(current_max or 0, time_spent)

        # 更新次数和平均用时
        new_count = count + 1
        new_avg_time = (avg_time * count + time_spent) / new_count

        tab_info[mode][main_key][sub_key] = f"{new_min:.4f},{new_count},{new_avg_time:.4f},{new_max:.4f}"
        self.save(data)
