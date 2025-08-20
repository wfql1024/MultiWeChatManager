import configparser
import ctypes
import datetime as dt
import glob
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Optional, Union, Tuple, Dict, List

import win32api
import win32com.client
import winshell
import yaml
from readerwriterlock import rwlock

from utils.logger_utils import mylogger as logger

rw_lock = rwlock.RWLockFairD()


class DictUtils:
    """
    ⚠️ 注意:
    - kwargs 的 key 必须是合法的 Python 标识符 (字母/数字/下划线组成, 且不能以数字开头)。
    - 如果配置项 key 含有特殊字符(如 %, -, / 等)，请不要使用 kwargs。
      解决方法：只传 pre_nodes 获取中间 dict，再手动 dict.get(key, default)。
    """
    SEPARATOR = '/'

    @staticmethod
    def _get_nested_value(data: Any, key_path: Optional[str],
                          default_value: Any = None) -> Any:
        """
        按照地址格式获取字典中的子字典或值（若获取不到则使用默认值），该方法不会破坏原字典结构
        :param data: 嵌套字典
        :param key_path: 多级键路径，例如 "a/b/c"
        :param default_value: 如果路径不存在，返回的默认值
        :return: 对应的子字典或值，如果路径不存在则返回默认值
        """
        # print("获取数据……………………………………………………")
        # print(data, key_path, default_value, separator)
        try:
            # 不传入data，直接返回默认值
            if data is None:
                return default_value

            # 地址为空直接返回本值
            if key_path is None:
                return data

            # 地址无法解析，返回默认值
            if not isinstance(key_path, str):
                return default_value

            # 根据地址，查找对应的子字典或值，路径不存在则返回默认值
            keys = key_path.split(DictUtils.SEPARATOR)
            sub_data = data
            for key in keys:
                if isinstance(sub_data, dict) and key in sub_data:
                    sub_data = sub_data[key]
                else:
                    return default_value
            return sub_data
        except Exception as e:
            logger.error(e)
            return default_value

    @staticmethod
    def _set_nested_value(data: dict, key_path: str, value: Any) -> bool:
        """
        按照地址格式更新字典中的子字典或值（可以设置默认值），该方法会对不存在的键路径进行创建
        :param data: 嵌套字典
        :param key_path: 多级键路径，例如 "a/b/c"
        :param value: 要设置的值
        :return: 是否成功
        """
        # print("设置数据……………………………………………………")
        # print(data, key_path, value, separator)
        try:
            # 非字典，无法操作
            if not isinstance(data, dict):
                return False
            # 地址为空、地址不可解析，无法对自身操作
            if key_path is None or not isinstance(key_path, str):
                return False

            # 根据地址，查找对应的子字典或值，路径不存在则创建
            keys = key_path.split(DictUtils.SEPARATOR)
            current = data
            for key in keys[:-1]:  # 遍历除最后一个键外的所有键
                if key not in current or not isinstance(current[key], dict):
                    current[key] = {}  # 如果键不存在或不是字典，创建一个空字典
                current = current[key]
            current[keys[-1]] = value  # 设置最后一个键的值
            return True
        except Exception as e:
            logger.error(e)
            return False

    @staticmethod
    def _clear_nested_value(data: dict, key_path=Optional[str]) -> bool:
        """
        按照地址格式清空字典中的子字典或值（可以设置默认值），该方法不会对不存在的键路径进行创建
        :param data: 嵌套字典
        :param key_path: 多级键路径，例如 "a/b/c"
        :return: 是否成功
        """
        # print("清除节点……………………………………………………")
        # print(data, key_path, separator)
        try:
            # 非字典，不作任何操作
            if not isinstance(data, dict):
                return False

            # 获取值
            value = DictUtils._get_nested_value(data, key_path, None)
            print(value)

            # 如果值为空，说明路径错误或者值本身就是None，不作任何操作
            if value is None:
                return True
            # 如果值是字典，则清空字典
            if isinstance(value, dict):
                value.clear()
                return True
            # 如果值是列表，则清空列表
            if isinstance(value, list):
                value.clear()
                return True
            # 否则，设置为空
            DictUtils._set_nested_value(data, key_path, None)
            return True

        except Exception as e:
            logger.error(e)
            return False

    @staticmethod
    def get_nested_values(data: Any, default_value: Any, *front_addr, **kwargs) -> Union[Any, Tuple[Any, ...]]:
        """
        按照地址格式获取 任意数据 中的 一个或多个 子字典或值（可以设置默认值）
        注意: 如未传入kwargs,返回的是一个值,无需解包; 如传入了kwargs,返回的是一个元组,需要解包
        :param default_value: 若不是批量获取，则返回这个默认值
        :param data: 嵌套字典
        :param front_addr: 前置地址，如：("wechat", "account1")，可以不传入
        :param kwargs: 需要批量获取的键地址及其默认值（如 note="", nickname=None），可以不传入
        :return: 包含所请求数据的元组
        """
        # print("批量获取数据....................................")
        # print(data, default_value, separator, front_addr, kwargs)
        try:
            # 1. 先处理前置地址，获取中间根节点
            # 不传入前置地址，跳过获取中间根节点，进入后续操作
            if len(front_addr) == 0:
                sub_data = data
            else:
                if not all(key is None or isinstance(key, str) for key in front_addr):
                    # 存在非法拼接：若前置地址中并不都是空或者字符串，则拼接失败，直接返回默认值
                    return tuple(value for value in kwargs.values()) if len(kwargs) > 0 else default_value
                else:
                    # 拼接前置地址，获取中间根节点
                    sub_data = DictUtils._get_nested_value(data, DictUtils.SEPARATOR.join(front_addr), default_value)
            # 2. 已经获得中间根节点
            # 若后续地址为空，则直接返回中间根节点
            if len(kwargs) == 0:
                return sub_data
            result = tuple(
                DictUtils._get_nested_value(sub_data, key, default) for key, default in kwargs.items()
            )
            return result
        except Exception as e:
            logger.error(e)
            return tuple(None for _ in kwargs.keys())

    @staticmethod
    def set_nested_values(data: dict, value: Any, *front_addr: Optional[str], **kwargs) -> bool:
        """
        按照地址格式更新字典中的多个子字典或值（可以设置默认值）
        :param value: 要设置的值
        :param data: 嵌套字典
        :param front_addr: 前置地址，如：("wechat", "account1")
        :param kwargs: 需要更新的键地址及其值（如 note="", nickname=None）
        :return: 是否成功
        """
        # print("批量设置数据....................................")
        # print(data, value, separator, front_addr, kwargs)
        try:
            # 非字典，无法操作
            if not isinstance(data, dict):
                return False

            # 1. 尝试拼接前置地址，得到中间根节点
            # 没有传入前置地址，或者传入的都是None，则中间根节点为data本身
            if len(front_addr) == 0 or all(key is None for key in front_addr):
                if len(kwargs) == 0:
                    # 无法对自身操作
                    return False
                else:
                    # 中间根节点是data本身，进入后续处理
                    sub_data = data
            else:
                # 存在非法拼接：若前置地址中只能传入空或者字符串，若有其他类型则拼接失败，无法操作
                if not all(key is None or isinstance(key, str) for key in front_addr):
                    return False
                else:
                    # 合法拼接
                    if len(kwargs) == 0:
                        # 拼接前置地址，设置中间根节点的值
                        return DictUtils._set_nested_value(data, DictUtils.SEPARATOR.join(front_addr), value)
                    else:
                        # 拼接前置地址，得到中间根节点进行后续处理
                        sub_data = DictUtils._get_nested_value(data, DictUtils.SEPARATOR.join(front_addr), value)

            # 2. 中间根节点已经获取，处理一些特殊情况，其余可以交给set_nested_value方法批量处理
            # print(f"中间根节点：{sub_data}")
            # 中间根节点不是字典，则转成空字典
            if not isinstance(sub_data, dict):
                DictUtils._set_nested_value(data, DictUtils.SEPARATOR.join(front_addr), {})
                sub_data = DictUtils._get_nested_value(data, DictUtils.SEPARATOR.join(front_addr), value)
            # 中间根节点是字典，交给set_nested_value方法批量处理
            return all(DictUtils._set_nested_value(sub_data, key_path, value)
                       for key_path, value in kwargs.items())

        except Exception as e:
            logger.error(e)
            return False

    @staticmethod
    def clear_nested_values(data: dict, *front_addr, **kwargs) -> bool:
        """
        按照地址格式清空字典中的子字典,子列表或值，该方法不会对不存在的键路径进行创建
        建议不传入kwargs,单次使用只清理一个位置;批量清理可能并不能达到你想要的效果
        :param data: 嵌套字典
        :param front_addr: 前置地址，如：("wechat", "account1")
        :param kwargs: 需要更新的键地址及其值（如 note="", nickname=None）
        :return: 是否成功
        """
        # print("批量清除节点....................................")
        # print(data, front_addr, kwargs)
        try:
            # 非字典，无法操作
            if not isinstance(data, dict):
                return False

            sub_data = None
            # 1. 尝试拼接前置地址，得到中间根节点
            # 没有传入前置地址，或者传入的都是None，则中间根节点为data本身
            if len(front_addr) == 0 or all(key is None for key in front_addr):
                if len(kwargs) == 0:
                    # 对自身操作,清空字典
                    data.clear()
                else:
                    # 中间根节点是data本身，进入后续处理
                    sub_data = data
            else:
                # 存在非法拼接：若前置地址中只能传入空或者字符串，若有其他类型则拼接失败，无法操作
                if not all(key is None or isinstance(key, str) for key in front_addr):
                    return False
                else:
                    # 合法拼接
                    if len(kwargs) == 0:
                        # 拼接前置地址，清除该节点
                        return DictUtils._clear_nested_value(data, DictUtils.SEPARATOR.join(front_addr))
                    else:
                        # 拼接前置地址，得到中间根节点进行后续处理
                        sub_data = DictUtils._get_nested_value(data, DictUtils.SEPARATOR.join(front_addr))

            # 2. 中间根节点已经获取，处理一些特殊情况，其余可以交给set_nested_value方法批量处理
            # print(f"中间根节点：{sub_data}")
            # 中间根节点不是字典，则转成空字典
            if not isinstance(sub_data, dict):
                return False
            # 中间根节点是字典，交给set_nested_value方法批量处理
            return all(DictUtils._clear_nested_value(sub_data, key_path)
                       for key_path, value in kwargs.items())

        except Exception as e:
            logger.error(e)
            return False


class YamlUtils:
    @staticmethod
    def load_yaml(file_path: str) -> Optional[dict]:
        """加载 YAML 文件"""
        try:
            with rw_lock.gen_rlock():
                with open(file_path, 'r', encoding='utf-8') as file:
                    return yaml.safe_load(file)
        except Exception as e:
            logger.e(f"加载 YAML 文件失败: {e}")
            return None


class JsonUtils:
    @staticmethod
    def load_json(json_file):
        try:
            if os.path.exists(json_file):
                with rw_lock.gen_rlock():
                    with open(json_file, 'r', encoding='utf-8', errors="ignore") as f:
                        return json.load(f)
            return {}
        except Exception as e:
            logger.error(e)
            return {}

    @staticmethod
    def save_json(json_file, data):
        try:
            with rw_lock.gen_wlock():
                with open(json_file, 'w', encoding='utf-8', errors="ignore") as f:
                    json_string = json.dumps(data, ensure_ascii=False, indent=4)
                    f.write(json_string)
            return True
        except Exception as e:
            logger.error(e)
            return False


class IniUtils:
    @staticmethod
    def load_ini_as_dict(ini_path):
        try:
            # 检查文件是否存在
            if not os.path.exists(ini_path):
                logger.warning(f"文件不存在: {ini_path}，创建空文件")
                with rw_lock.gen_rlock():
                    open(ini_path, 'w', encoding='utf-8').close()  # 创建空文件
                    return {}
            # 读取配置文件
            config = configparser.ConfigParser()
            with rw_lock.gen_rlock():
                config.read(ini_path, encoding='utf-8')
                # 将ConfigParser对象转换为字典
                result_dict = {}
                for section in config.sections():
                    result_dict[section] = {}
                    for key, value in config[section].items():
                        result_dict[section][key] = value
                return result_dict
        except Exception as e:
            logger.error(f"读取配置文件失败: {ini_path}, 错误: {e}")
            return {}

    @staticmethod
    def save_ini_from_dict(ini_path, data_dict):
        """
        将字典数据强制以UTF-8编码保存到ini文件
        :param ini_path: ini文件路径
        :param data_dict: 要保存的完整字典数据
        :return: bool 是否保存成功
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(ini_path):
                logger.warning(f"文件不存在: {ini_path}，创建空文件")
                with rw_lock.gen_wlock():
                    open(ini_path, 'w').close()  # 创建空文件
            config = configparser.ConfigParser()
            config.read(ini_path)
            for section, items in data_dict.items():
                if not config.has_section(section):
                    config.add_section(section)
                for key, value in items.items():
                    config[section][key] = str(value)
            with rw_lock.gen_wlock():
                with open(ini_path, 'w', encoding='utf-8', errors="ignore") as f:
                    # f: IO[str] = f
                    config.write(f)  # type: ignore
            return True
        except Exception as e:
            logger.error(f"保存配置文件失败: {ini_path}, 错误: {e}")
            try:
                # 终极抢救：删除文件后重建
                os.remove(ini_path)
                config = configparser.ConfigParser()
                # 遍历字典并更新配置
                for section, items in data_dict.items():
                    if not config.has_section(section):
                        config.add_section(section)
                    for key, value in items.items():
                        config[section][key] = str(value)
                with rw_lock.gen_wlock():
                    with open(ini_path, 'w', encoding='utf-8') as f:
                        config.write(f)  # type:ignore
                return True
            except Exception as final_e:
                logger.critical(f"最终保存尝试失败: {final_e}")
                return False


class DllUtils:
    @staticmethod
    def find_hex_patterns_from_file(file_path, *hex_patterns):
        """
        在文件中查找指定的十六进制模式，并返回一个布尔列表。
        :param file_path: 文件的路径
        :param hex_patterns: 一个或多个十六进制模式，每个模式为一个字符串
        :return: 一个布尔列表，每个元素对应一个模式，True 表示找到，False 表示未找到
        """
        with rw_lock.gen_rlock():
            with open(file_path, 'rb') as f:
                dll_content = f.read()
        # 将所有传入的 hex_patterns 转换为字节模式
        patterns = [bytes.fromhex(pattern) for pattern in hex_patterns]
        # 返回布尔列表
        return [pattern in dll_content for pattern in patterns]

    @staticmethod
    def batch_atomic_replace_multi_files(file_patterns_map: Dict[str, List[Tuple[List[str], List[str]]]]) -> bool:
        """
        对多个文件执行原子替换操作，若任一文件替换失败，则回滚所有已处理文件的改动。
        :param file_patterns_map: {dll_path: [hex_patterns_tuples]}
        :return: transaction_success: 所有文件都成功则为 True，否则为 False（已回滚）
        """
        mmap_map = {}  # {dll_path: mmap_file}
        backup_map = {}  # {dll_path: 原始字节数据}
        transaction_success = True

        try:
            with rw_lock.gen_wlock():
                for dll_path, hex_patterns_tuples in file_patterns_map.items():
                    with open(dll_path, 'r+b') as f:
                        mmap_file = mmap.mmap(f.fileno(), 0)
                        mmap_map[dll_path] = mmap_file
                        backup_map[dll_path] = mmap_file[:]

                        for hex_patterns_tuple in hex_patterns_tuples:
                            success, _ = DllUtils._atomic_replace_hex_patterns(mmap_file, hex_patterns_tuple)
                            if not success:
                                print(f"替换失败: {dll_path}的{hex_patterns_tuple}")
                                transaction_success = False
                                break

                    if not transaction_success:
                        break  # 提前跳出，避免处理后续文件

            if not transaction_success:
                # 回滚所有已处理文件
                for dll_path, mmap_file in mmap_map.items():
                    mmap_file[:] = backup_map[dll_path]
                    mmap_file.flush()

        except Exception as e:
            print(f"发生异常: {str(e)}")
            transaction_success = False

        finally:
            for mmap_file in mmap_map.values():
                mmap_file.close()

        return transaction_success

    @staticmethod
    def _atomic_replace_hex_patterns(mmap_file, hex_patterns_tuple: tuple):
        """
        单次处理dll的多处替换（高效版本，使用已打开的mmap文件）
        :param mmap_file: 已打开的mmap文件对象
        :param hex_patterns_tuple: 元组列表：每个元组包含旧模式列表和新模式列表
        :return: (success, message) 元组
        """
        backup_data = None
        success = True
        old_patterns, new_patterns = hex_patterns_tuple

        # 确保两个列表长度相同
        if len(old_patterns) != len(new_patterns):
            return False, "错误：旧模式和新模式的数量不匹配。"

        # 备份当前位置
        original_pos = mmap_file.tell()

        try:
            # 先备份原始数据（只备份当前原子操作相关的部分）
            backup_data = bytearray()
            for old_pattern in old_patterns:
                old = bytes.fromhex(old_pattern)
                pos = mmap_file.find(old)
                if pos != -1:
                    backup_data.extend(mmap_file[pos:pos + len(old)])
                else:
                    return False, f"错误：未找到模式 {old_pattern}"

            # 重置位置准备写入
            mmap_file.seek(original_pos)

            # 遍历所有模式对
            for old_pattern, new_pattern in zip(old_patterns, new_patterns):
                old, new = bytes.fromhex(old_pattern), bytes.fromhex(new_pattern)
                pos = mmap_file.find(old)

                if pos != -1:
                    mmap_file[pos: pos + len(old)] = new
                    print(f"找到并替换：{old_pattern} -> {new_pattern}")
                else:
                    print(f"错误：未找到模式 {old_pattern}")
                    success = False
                    break  # 遇到第一个失败立即跳出循环

            # 如果成功则提交更改
            if success:
                mmap_file.flush()
                return True, "替换成功"
            else:
                # 回滚当前原子操作的所有更改
                mmap_file.seek(original_pos)
                for old_pattern in old_patterns:
                    old = bytes.fromhex(old_pattern)
                    pos = mmap_file.find(old)
                    if pos != -1:
                        mmap_file[pos:pos + len(old)] = backup_data[:len(old)]
                        backup_data = backup_data[len(old):]
                mmap_file.flush()
                return False, "部分模式替换失败，已回滚。"

        except Exception as e:
            print(f"发生错误: {str(e)}")
            # 尝试回滚
            if 'backup_data' in locals() and backup_data:
                mmap_file.seek(original_pos)
                for old_pattern in old_patterns:
                    old = bytes.fromhex(old_pattern)
                    pos = mmap_file.find(old)
                    if pos != -1:
                        mmap_file[pos:pos + len(old)] = backup_data[:len(old)]
                        backup_data = backup_data[len(old):]
                mmap_file.flush()
            return False, f"发生错误: {str(e)}"


# Windows API 常量
FO_DELETE = 0x03
FOF_ALLOWUNDO = 0x40


# 设置 SHFileOperation 结构
class SHFileOpStruct(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("wFunc", ctypes.c_uint),
        ("pFrom", ctypes.c_wchar_p),
        ("pTo", ctypes.c_wchar_p),
        ("fFlags", ctypes.c_uint),
        ("fAnyOperationsAborted", ctypes.c_bool),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", ctypes.c_wchar_p)
    ]


def move_files_to_recycle_bin(file_paths):
    file_paths = [os.path.abspath(path) for path in file_paths]

    # 确保所有文件或文件夹都存在
    valid_paths = [path for path in file_paths if os.path.exists(path)]
    if not valid_paths:
        print("没有可删除的文件或文件夹")
        return False

    # 组合多个路径，以 null 字符分隔，并以双 null 结尾
    file_paths_str = "\0".join(valid_paths) + "\0\0"

    # 创建 SHFileOpStruct 实例
    file_op = SHFileOpStruct()
    file_op.wFunc = FO_DELETE
    file_op.pFrom = ctypes.cast(ctypes.create_unicode_buffer(file_paths_str), ctypes.c_wchar_p)
    file_op.fFlags = FOF_ALLOWUNDO  # 允许撤销操作（即放入回收站）

    # 调用 Windows API
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(file_op))

    # 返回操作是否成功
    if result == 0:
        print(f"以下文件已成功移动到回收站:\n" + "\n".join(valid_paths))
        return True
    else:
        print(f"文件移动失败，错误代码: {result}")
        return False


def get_recent_folders_from_dir(directory, minutes=720):
    """
    获取指定目录下最近修改的文件夹列表。
    只返回最近修改的文件夹，不包括文件。
    :param directory: 指定文件夹
    :param minutes: 在最近的n分钟之内
    :return:
    """
    now = dt.datetime.now()
    some_minutes_ago = now - dt.timedelta(minutes=minutes)
    recent_folders = []
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        if os.path.isdir(item_path):
            modification_time = dt.datetime.fromtimestamp(os.path.getmtime(item_path))
            if modification_time >= some_minutes_ago:
                recent_folders.append(item_path)
    return recent_folders


def calculate_md5(file_path, chunk_size=4096):
    """计算文件的 MD5 哈希值"""
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            md5.update(chunk)
    return md5.hexdigest()


def is_latest_file_by_day(file_path) -> bool:
    # 获取文件的修改时间（时间戳）
    modification_time = os.path.getmtime(file_path)
    # 转换为日期格式
    modification_date = dt.datetime.fromtimestamp(modification_time).date()
    # 获取今天的日期
    today = dt.datetime.now().date()
    return modification_date >= today


def find_dir(start_dir, dirname):
    """递归查找指定文件"""
    for root, dirs, files in os.walk(start_dir):
        if dirname in dirs:
            return os.path.join(root, dirname)
    return None


def find_file(start_dir, filename):
    """递归查找指定文件"""
    for root, dirs, files in os.walk(start_dir):
        if filename in files:
            return os.path.join(root, filename)
    return None


def get_file_names_matching_wildcards(wildcards: list, search_dir: str = "."):
    res_set = set()
    for wildcard in wildcards:
        pattern = os.path.join(search_dir, wildcard).replace("/", "\\")
        matched_paths = glob.glob(pattern)
        res_set.update(matched_paths)
    # Printer().debug(pattern, matched_paths)
    return [os.path.basename(path) for path in list(res_set)]


def get_file_version(file_path):
    try:
        version_info = win32api.GetFileVersionInfo(file_path, '\\')  # type: ignore
        version = (
            f"{win32api.HIWORD(version_info['FileVersionMS'])}."  # type: ignore
            f"{win32api.LOWORD(version_info['FileVersionMS'])}."  # type: ignore
            f"{win32api.HIWORD(version_info['FileVersionLS'])}."  # type: ignore
            f"{win32api.LOWORD(version_info['FileVersionLS'])}"  # type: ignore
        )
        return version
    except Exception as e:
        print(f"Error getting version for {file_path}: {e}")
        return None


def extract_version(folder):
    matches = re.compile(r'(\d+(?:\.\d+){0,4})').findall(folder)  # 找到所有匹配的版本号
    if matches:
        # 取最右边的版本号
        version_str = matches[-1]
        version_parts = list(map(int, version_str.split(".")))

        # 如果版本号不足 4 位，补足 0；如果超过 4 位，只取前 4 位
        while len(version_parts) < 4:
            version_parts.append(0)
        key = version_parts[:4]  # 使用 4 个数字的版本号作为key
        # print(key)
        return key
    return [0, 0, 0, 0]  # 如果没有匹配到版本号，默认返回0.0.0.0


def get_newest_full_version_dir(versions):
    # 找到最大版本号的文件夹
    max_version_dir = max(versions, key=extract_version).replace('\\', '/')
    print(max_version_dir)
    return max_version_dir


def get_newest_full_version(versions):
    # 找到最大版本号的文件夹
    # print(versions)
    max_full_version = max(versions, key=extract_version)
    # print(max_full_version)
    return max_full_version


def get_sorted_full_versions(versions):
    # 按版本号排序
    sorted_versions = sorted(versions, key=extract_version, reverse=True)
    # 返回按版本号排序的文件夹列表
    return sorted_versions


def get_shortcut_target(shortcut_path):
    """
    从快捷方式文件中获取目标路径。
    :param shortcut_path: 快捷方式文件的路径
    :return: 目标路径，如果出错或不是快捷方式，则返回 None
    """
    try:
        # 使用 win32com 读取快捷方式
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(shortcut_path))

        # 获取快捷方式的目标路径并返回
        shortcut_target = Path(shortcut.TargetPath).resolve()
        return shortcut_target
    except Exception as e:
        # 捕获任何异常并返回 None
        print(f"错误: {e}")
        return None


def check_shortcut_in_folder(folder_path, target_path):
    """
    检查指定文件夹中的所有快捷方式，如果有快捷方式指向目标路径，返回 True 和快捷方式路径。

    :param folder_path: 文件夹路径
    :param target_path: 目标路径
    :return: 如果找到匹配的快捷方式，则返回 (True, 快捷方式路径)，否则返回 (False, None)
    """
    # 确保目标路径是绝对路径
    target_path = Path(target_path).resolve()
    paths = []

    # 获取文件夹中的所有文件
    for file in os.listdir(folder_path):
        file_path = Path(folder_path) / file
        # 检查文件是否是快捷方式 (.lnk)
        if file_path.suffix.lower() == '.lnk' and get_shortcut_target(file_path) == target_path:
            paths.append(file_path)

    if isinstance(paths, list) and len(paths) != 0:
        # 如果找到匹配的快捷方式，返回 True 和快捷方式路径
        return True, paths
    # 如果没有找到匹配的快捷方式，返回 False
    return False, None


def create_shortcut_for_(target_path, shortcut_path, ico_path=None):
    """
    创建一个快捷方式。
    :param shortcut_path: 快捷方式的路径
    :param target_path: 目标路径
    :param ico_path: 快捷方式的图标（可选）
    """
    # 创建快捷方式
    with winshell.shortcut(shortcut_path) as shortcut:
        shortcut.path = target_path
        shortcut.working_directory = os.path.dirname(target_path)
        # 修正icon_location的传递方式，传入一个包含路径和索引的元组
        if ico_path:
            shortcut.icon_location = (ico_path, 0)


import os
import mmap


def compare_binary_files_optimized(file1: str, file2: str):
    if os.path.getsize(file1) != os.path.getsize(file2):
        return f"文件大小不同：{os.path.getsize(file1)} vs {os.path.getsize(file2)} 字节，无法对比。"

    result = []
    with open(file1, "rb") as f1, open(file2, "rb") as f2:
        size = os.path.getsize(file1)
        mm1 = mmap.mmap(f1.fileno(), 0, access=mmap.ACCESS_READ)
        mm2 = mmap.mmap(f2.fileno(), 0, access=mmap.ACCESS_READ)

        i = 0
        shown_ranges = []
        while i < size:
            if mm1[i] != mm2[i]:
                range_start = max(i - 32, 0)
                diff_set = set()
                j = i
                while j < size and j < i + 64:
                    if mm1[j] != mm2[j]:
                        diff_set.add(j - range_start)
                    j += 1
                range_end = j

                if shown_ranges and shown_ranges[-1][1] >= range_start:
                    prev_start, prev_end, prev_diff1, prev_diff2 = shown_ranges.pop()
                    merged_start = prev_start
                    merged_end = max(prev_end, range_end)
                    new_diff1 = prev_diff1.union({x + (range_start - merged_start) for x in diff_set})
                    new_diff2 = prev_diff2.union({x + (range_start - merged_start) for x in diff_set})
                    shown_ranges.append((merged_start, merged_end, new_diff1, new_diff2))
                else:
                    shown_ranges.append((range_start, range_end, set(diff_set), set(diff_set)))

                i = range_end
            else:
                i += 1

        for start, end, diff1, diff2 in shown_ranges:
            result.append(f"{start:08X}~{end:08X}")
            data1 = mm1[start:end]
            data2 = mm2[start:end]
            result.append(f"{file1}:\n{format_bytes_line(data1, diff1)}")
            result.append(f"{file2}:\n{format_bytes_line(data2, diff2)}")

        mm1.close()
        mm2.close()

    return '\n'.join(result) if result else "两个文件完全一致！"


def format_bytes_line(data: bytes, diff_indices: set, group_size: int = 64) -> str:
    hexes = []
    for i, byte in enumerate(data):
        hex_str = f"{byte:02X}"
        if i in diff_indices:
            hexes.append(f"({hex_str})")
        else:
            hexes.append(hex_str)

    # 连续括号合并成一个
    result = " ".join(hexes)
    while ") (" in result:
        result = result.replace(") (", " ")

    return result


if __name__ == "__main__":
    file1 = r"E:\Now\Desktop\[4.0.6.3]Weixin.dll"
    file2 = r"E:\Now\Desktop\[4.0.6.3]Weixin_BuR.dll"
    result = compare_binary_files_optimized(file1, file2)
    print(result)
