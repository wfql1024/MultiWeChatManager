import ctypes
import datetime as dt
import hashlib
import json
import mmap
import re
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from Crypto.Util.Padding import unpad
from pathlib import Path
import win32api
import win32com.client
import winshell
import configparser
import os
from typing import IO
from utils import logger_utils
import yaml
from typing import Any, Optional

logger = logger_utils.mylogger


class DictUtils:
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
    def get_nested_values(data: Any, default_value: Any, *front_addr, **kwargs):
        """
        按照地址格式获取 任意数据 中的 一个或多个 子字典或值（可以设置默认值）
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
            result = tuple()
            for key, default in kwargs.items():
                value = DictUtils._get_nested_value(sub_data, key, default)
                result += (value,)
            return result
        except Exception as e:
            logger.error(e)
            return tuple()

    @staticmethod
    def set_nested_values(data: dict, value: Any, *front_addr: Optional[str], **kwargs):
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
    def clear_nested_values(data: dict, *front_addr, **kwargs):
        """
        按照地址格式清空字典中的子字典或值（可以设置默认值），该方法不会对不存在的键路径进行创建
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
                    # 无法对自身操作
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
                # print("地址没错")
                with open(json_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(e)
            return {}

    @staticmethod
    def save_json(account_data_file, account_data):
        try:
            with open(account_data_file, 'w', encoding='utf-8') as f:
                json_string = json.dumps(account_data, ensure_ascii=False, indent=4)
                f.write(json_string)
        except Exception as e:
            logger.error(e)


class IniUtils:
    @staticmethod
    def get_setting_from_ini(ini_path, section, key, default_value=None, validation_func=None):
        try:
            # 检查文件是否存在
            if not os.path.exists(ini_path):
                logger.warning(f"文件不存在: {ini_path}，创建空文件")
                open(ini_path, 'w').close()  # 创建空文件
                return None

            # 读取配置文件
            config = configparser.ConfigParser()
            config.read(ini_path)

            # 检查节和键是否存在
            if section in config and key in config[section]:
                current_value = config[section][key]
                # 验证配置值
                if validation_func is None or validation_func(current_value):
                    # logger.info(f"读取 {ini_path}[{section}]{key} = {current_value}")
                    return current_value

            # 如果节或键不存在，返回默认值
            logger.warning(f"配置项不存在: {ini_path}[{section}]{key}")
            return default_value

        except Exception as e:
            logger.error(f"读取配置文件失败: {ini_path}, 错误: {e}")
            return None

    @staticmethod
    def save_setting_to_ini(ini_path, section, key, value):
        config = configparser.ConfigParser()

        ini_path = ini_path.replace('\\', '/')
        # 先确保目录存在，如果不存在则创建
        ini_dir = os.path.dirname(ini_path)
        if not os.path.exists(ini_dir):
            os.makedirs(ini_dir, exist_ok=True)  # 创建文件夹
            logger.warning(f"文件夹不存在，已创建: {ini_dir}")

        # 确保目录存在后再读取文件
        if os.path.exists(ini_path):
            try:
                files_read = config.read(ini_path)
                if not files_read:
                    logger.warning(f"Unable to read {ini_path}")
            except Exception as e:
                logger.error(f"Failed to read {ini_path}: {e}")

        # 检查 section 是否存在
        if section not in config:
            config[section] = {}

        config[section][key] = str(value)

        # 写入配置文件
        try:
            with open(ini_path, 'w') as configfile:
                configfile: IO[str] = configfile
                config.write(configfile)  # type: ignore
                # logger.info(f"写入{value} -----> {os.path.basename(ini_path)}[{section}]{key}")
        except IOError as e:
            logger.error(f"Failed to write to {ini_path}: {e}")


class DllUtils:
    @staticmethod
    def find_patterns_from_dll_in_hexadecimal(dll_path, *hex_patterns):
        """
        在 DLL 文件中查找指定的十六进制模式，并返回一个布尔列表。
        :param dll_path: DLL 文件的路径
        :param hex_patterns: 一个或多个十六进制模式，每个模式为一个字符串
        :return: 一个布尔列表，每个元素对应一个模式，True 表示找到，False 表示未找到
        """
        with open(dll_path, 'rb') as f:
            dll_content = f.read()

        # 将所有传入的 hex_patterns 转换为字节模式
        patterns = [bytes.fromhex(pattern) for pattern in hex_patterns]

        # 如果只有一个模式，直接返回布尔值
        if len(patterns) == 1:
            return patterns[0] in dll_content

        # 如果有多个模式，返回布尔列表
        return [pattern in dll_content for pattern in patterns]

    @staticmethod
    def edit_patterns_in_dll_in_hexadecimal(dll_path, **hex_patterns_dicts):
        """
        在 DLL 文件中查找指定的十六进制模式，并替换为新的十六进制模式。
        :param dll_path: DLL 文件的路径
        :param hex_patterns_dicts: 一个或多个十六进制模式的字典，每个字典包含旧模式和新模式
        :return: 一个布尔列表，每个元素对应一个模式，True 表示替换成功，False 表示未找到对应模式
        """
        print(hex_patterns_dicts)
        results = []

        with open(dll_path, 'r+b') as f:
            # 使用 mmap 来更高效地操作文件内容
            mmap_file = mmap.mmap(f.fileno(), 0)
            # 遍历所有传入的旧模式和新模式
            for old_pattern, new_pattern in hex_patterns_dicts.items():
                old, new = bytes.fromhex(old_pattern), bytes.fromhex(new_pattern)
                pos = mmap_file.find(old)
                # 查找并替换模式
                if pos != -1:
                    mmap_file[pos: pos + len(old)] = new
                    print(f"替换完成：{old_pattern} -> {new_pattern}")
                    results.append(True)  # 替换成功
                else:
                    print(f"未找到对应的HEX模式：{old_pattern}")
                    results.append(False)  # 替换失败

            mmap_file.flush()
            mmap_file.close()

        # 如果传入多个模式，返回布尔列表；如果只有一个，返回单一布尔值
        return results if len(results) > 1 else results[0]


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
    file_op.pFrom = file_paths_str
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


def is_latest_file_by_day(file_path):
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


def get_file_version(file_path):
    version_info = win32api.GetFileVersionInfo(file_path, '\\')  # type: ignore
    version = (
        f"{win32api.HIWORD(version_info['FileVersionMS'])}."  # type: ignore
        f"{win32api.LOWORD(version_info['FileVersionMS'])}."  # type: ignore
        f"{win32api.HIWORD(version_info['FileVersionLS'])}."  # type: ignore
        f"{win32api.LOWORD(version_info['FileVersionLS'])}"  # type: ignore
    )
    return version


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


class CryptoUtils:
    @staticmethod
    def decrypt_json_file(input_file, output_file, key):
        # 确保密钥长度为 16、24 或 32 字节
        key = key.ljust(16)[:16].encode()

        with open(input_file, 'rb') as f:
            file_data = f.read()

        iv = file_data[:16]
        ciphertext = file_data[16:]
        cipher = AES.new(key, AES.MODE_CBC, iv)

        plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
        with open(output_file, 'wb') as f:
            f.write(plaintext)

    @staticmethod
    def encrypt_json_file(input_file, output_file, key):
        # 确保密钥长度为 16、24 或 32 字节
        key = key.ljust(16)[:16].encode()
        cipher = AES.new(key, AES.MODE_CBC)
        iv = cipher.iv

        with open(input_file, 'rb') as f:
            plaintext = f.read()

        # 加密并写入文件
        ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))
        with open(output_file, 'wb') as f:
            f.write(iv + ciphertext)


if __name__ == '__main__':
    # 测试
    pass
