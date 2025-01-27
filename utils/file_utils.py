import ctypes
import datetime as dt
import hashlib
import mmap
import os
import win32com.client
from pathlib import Path
import re
import win32api
import winshell


class DLLUtils:
    @staticmethod
    def find_patterns_from_dll_in_hexadecimal(dll_path, *hex_patterns):
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


def move_to_recycle_bin(file_path):
    file_path = os.path.abspath(file_path)
    # 确保文件存在
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return False

    # 将文件路径转换为字符串并以 null 结尾
    file_path = file_path + "\0"

    # 创建 SHFileOpStruct 实例
    file_op = SHFileOpStruct()
    file_op.wFunc = FO_DELETE
    file_op.pFrom = file_path
    file_op.fFlags = FOF_ALLOWUNDO  # 允许撤销操作（即放入回收站）

    # 调用 Windows API
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(file_op))

    # 返回操作是否成功
    if result == 0:
        print(f"文件已成功移动到回收站: {file_path}")
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

if __name__ == '__main__':
    # 测试
    pass
