import re

import win32api


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
    dll_dir = max(versions, key=extract_version).replace('\\', '/')
    print(dll_dir)
    return dll_dir


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
