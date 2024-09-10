import configparser
import os
import re
import winreg

import psutil

from resources import Config
from utils import process_utils, debug_utils


def is_valid_wechat_install_path(path) -> bool:
    if path and path != "":
        return os.path.exists(path)
    else:
        return False


def is_valid_wechat_data_path(path) -> bool:
    if path and path != "":
        config_data_path = os.path.join(path, "All Users", "config", "config.data").replace('\\', '/')
        return os.path.isfile(config_data_path)
    else:
        return False


def is_valid_wechat_dll_dir_path(path) -> bool:
    if path and path != "":
        return os.path.exists(os.path.join(path, "WeChatWin.dll"))
    else:
        return False


def get_setting_from_ini(ini_filename, section, key, validation_func=None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ini_path = os.path.join(script_dir, ini_filename).replace('\\', '/')
    if os.path.exists(ini_path):
        config = configparser.ConfigParser()
        config.read(ini_path)
        if section in config and key in config[section]:
            current_setting = config[section][key]
            if validation_func is None or validation_func(current_setting):
                print(f"{os.path.basename(ini_filename)}[{section}]{key}》》》》》》》》》{current_setting}")
                return current_setting
    return None


def save_setting_to_ini(ini_path, section, key, value):
    ini_path = ini_path.replace('\\', '/')
    config = configparser.ConfigParser()

    if os.path.exists(ini_path):
        config.read(ini_path)

    if section not in config:
        config[section] = {}

    config[section][key] = value

    if not os.path.exists(Config.PROJ_USER_PATH):  # 如果路径不存在
        os.makedirs(Config.PROJ_USER_PATH)  # 创建 user_files 文件夹
        print(f"已创建文件夹: {Config.PROJ_USER_PATH}")

    with open(ini_path, 'w') as configfile:
        config.write(configfile)
        print(f"{debug_utils.get_call_stack(3)}::{os.path.basename(ini_path)}[{section}]{key}《《《《《《《《《{value}")


def get_wechat_install_path_from_process():
    for process in psutil.process_iter(['name', 'exe']):
        if process.name() == 'WeChat.exe':
            path = process.exe().replace('\\', '/')
            print(f"通过查找进程方式获取了微信安装地址：{path}")
            return path
    return None


def get_wechat_install_path_from_machine_register():
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\WeChat")
        found_path = winreg.QueryValueEx(key, "InstallLocation")[0].replace('\\', '/')
        winreg.CloseKey(key)
        print(f"通过注册表方式1获取了微信安装地址：{found_path}")
        if found_path:
            return os.path.join(found_path, "WeChat.exe").replace('\\', '/')
    except WindowsError as e:
        print(e)
    return None


def get_wechat_install_path_from_user_register():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Tencent\WeChat")
        found_path = winreg.QueryValueEx(key, "InstallPath")[0].replace('\\', '/')
        winreg.CloseKey(key)
        print(f"通过注册表方式2获取了微信安装地址：{found_path}")
        if found_path:
            return os.path.join(found_path, "WeChat.exe").replace('\\', '/')
    except WindowsError as e:
        print(e)
    return None


def get_wechat_data_path_from_user_register():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Tencent\WeChat", 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "FileSavePath")
        winreg.CloseKey(key)
        value = os.path.join(value, "WeChat Files").replace('\\', '/')
        return value
    except WindowsError:
        pass
    return None


def get_wechat_dll_dir_path_by_files():
    install_path = get_wechat_install_path()  # 获得完整路径
    # install_path = "D:/software/Tencent/WeChat/WeChat.exe"
    # 删除路径末尾的 WeChat.exe，保留目录部分
    if install_path and install_path != "":
        install_path = os.path.dirname(install_path)

    version_folders = []

    # 遍历所有文件及子文件夹
    for root, dirs, files in os.walk(install_path):
        if 'WeChatWin.dll' in files:
            version_folders.append(root)  # 将包含WeChatWin.dll的目录添加到列表中

    if not version_folders:
        return None

    # 只有一个文件夹，直接返回
    if len(version_folders) == 1:
        dll_dir = version_folders[0].replace('\\', '/')
        print(dll_dir)
        return dll_dir

    # 使用正则表达式匹配 1-5 个数字组成的版本号
    version_pattern = re.compile(r'(\d+(?:\.\d+){0,4})')

    # 提取并比较版本号
    def extract_version(folder):
        matches = version_pattern.findall(folder)  # 找到所有匹配的版本号
        if matches:
            # 取最右边的版本号
            version_str = matches[-1]
            version_parts = list(map(int, version_str.split(".")))

            # 如果版本号不足 5 位，补足 0；如果超过 5 位，只取前 5 位
            while len(version_parts) < 5:
                version_parts.append(0)
            key = version_parts[:5]  # 使用 5 个数字的版本号作为key
            # print(key)
            return key
        return [0, 0, 0, 0, 0]  # 如果没有匹配到版本号，默认返回0.0.0.0

    # 找到最大版本号的文件夹
    dll_dir = max(version_folders, key=extract_version).replace('\\', '/')
    print(dll_dir)
    return dll_dir


def get_wechat_dll_dir_path_by_memo_maps():
    pids = process_utils.get_process_ids_by_name("WeChat.exe")
    if len(pids) == 0:
        print("没有运行微信。")
        return None
    else:
        process_id = pids[0]
        try:
            for f in psutil.Process(process_id).memory_maps():
                normalized_path = f.path.replace('\\', '/')
                # print(normalized_path)
                # 检查路径是否以 data_path 开头
                if normalized_path.endswith('WeChatWin.dll'):
                    dll_dir_path = os.path.dirname(normalized_path)
                    # print(dll_dir_path)
                    return dll_dir_path
        except psutil.AccessDenied:
            print(f"无法访问进程ID为 {process_id} 的内存映射文件，权限不足。")
        except psutil.NoSuchProcess:
            print(f"进程ID为 {process_id} 的进程不存在或已退出。")
        except Exception as e:
            print(f"发生意外错误: {e}")


def get_wechat_install_path():
    path_finders = [
        lambda: get_setting_from_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                     Config.INI_KEY_INSTALL_PATH),
        get_wechat_install_path_from_machine_register,
        get_wechat_install_path_from_user_register,
        lambda: os.path.join(os.environ.get('ProgramFiles'), 'Tencent', 'WeChat', 'WeChat.exe').replace('\\', '/'),
        lambda: os.path.join(os.environ.get('ProgramFiles(x86)'), 'Tencent', 'WeChat', 'WeChat.exe').replace('\\', '/'),
        get_wechat_install_path_from_process
    ]

    for index, finder in enumerate(path_finders):
        # print(f"当前方法：{finder.__name__} (索引: {index})")
        path = finder()
        if is_valid_wechat_install_path(path):
            save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                Config.INI_KEY_INSTALL_PATH, path)
            print(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
            return path
        # print("——————————所有方法都已测试——————————")

    return None


def get_wechat_data_path():
    # 获取地址的各种方法
    path_finders = [
        lambda: get_setting_from_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                     Config.INI_KEY_DATA_PATH),
        get_wechat_data_path_from_user_register,
        lambda: os.path.join(os.path.expanduser('~'), 'Documents', 'WeChat Files').replace('\\', '/'),
        lambda: os.path.join(os.environ.get('APPDATA'), 'Tencent', 'WeChat').replace('\\', '/')
    ]

    # 尝试各种方法
    for index, finder in enumerate(path_finders):
        # print(f"当前方法：{finder.__name__}")
        found_path = finder()
        # 对得到地址进行检验，正确则返回并保存
        if is_valid_wechat_data_path(found_path):
            save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                Config.INI_KEY_DATA_PATH, found_path)
            print(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
            return found_path

    # print("——————————所有方法都已测试——————————")

    return None


def get_wechat_dll_dir_path():
    path_finders = [
        lambda: get_setting_from_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                     Config.INI_KEY_DLL_PATH),
        get_wechat_dll_dir_path_by_memo_maps,
        get_wechat_dll_dir_path_by_files,
    ]

    for index, finder in enumerate(path_finders):
        # print(f"当前方法：{finder.__name__}")
        found_path = finder()
        if is_valid_wechat_dll_dir_path(found_path):
            save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                Config.INI_KEY_DLL_PATH, found_path)
            print(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
            return found_path

    # print("——————————所有方法都已测试——————————")

    return None


if __name__ == "__main__":
    get_wechat_dll_dir_path_by_files()
