import configparser
import os
import winreg

import psutil

from resources import Config


def is_valid_wechat_install_path(path):
    return os.path.exists(path)


def is_valid_wechat_data_path(path):
    config_data_path = os.path.join(path, "All Users", "config", "config.data").replace('\\', '/')
    return os.path.isfile(config_data_path)


def is_valid_wechat_latest_version_path(path):
    valid_path = get_wechat_latest_version_path_by_sort()
    if valid_path and path == valid_path or not valid_path and os.path.exists(os.path.join(path, "WeChatWin.dll")):
        return True


def get_setting_from_ini(ini_filename, section, key, validation_func=None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ini_path = os.path.join(script_dir, ini_filename).replace('\\', '/')
    if os.path.exists(ini_path):
        config = configparser.ConfigParser()
        config.read(ini_path)
        if section in config and key in config[section]:
            current_setting = config[section][key]
            if validation_func is None or validation_func(current_setting):
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


def get_wechat_install_path_from_process():
    for process in psutil.process_iter(['name', 'exe']):
        if process.name() == 'WeChat.exe':
            return process.exe().replace('\\', '/')
    return None


def get_wechat_install_path_from_register():
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\WeChat")
        found_path = winreg.QueryValueEx(key, "InstallLocation")[0].replace('\\', '/')
        winreg.CloseKey(key)
        return found_path
    except WindowsError:
        return None


def get_wechat_install_path():
    path_finders = [
        lambda: get_setting_from_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                     Config.INI_KEY_INSTALL_PATH, is_valid_wechat_install_path),
        lambda: os.path.join(get_wechat_install_path_from_register(), 'WeChat.exe').replace('\\', '/'),
        lambda: os.path.join(os.environ.get('ProgramFiles'), 'Tencent', 'WeChat', 'WeChat.exe').replace('\\', '/'),
        lambda: os.path.join(os.environ.get('ProgramFiles(x86)'), 'Tencent', 'WeChat', 'WeChat.exe').replace('\\', '/'),
        get_wechat_install_path_from_process
    ]

    for finder in path_finders:
        path = finder()
        if path and os.path.exists(path):
            save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                Config.INI_KEY_INSTALL_PATH, path)
            return path

    return None


def get_wechat_data_path_from_register():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Tencent\WeChat", 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "FileSavePath")
        winreg.CloseKey(key)
        value = os.path.join(value, "WeChat Files").replace('\\', '/')
        if is_valid_wechat_data_path(value):
            return value
    except WindowsError:
        pass
    return None


def get_wechat_data_path():
    path_finders = [
        lambda: get_setting_from_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                     Config.INI_KEY_DATA_PATH, is_valid_wechat_data_path),
        get_wechat_data_path_from_register,
        lambda: os.path.join(os.path.expanduser('~'), 'Documents', 'WeChat Files').replace('\\', '/'),
        lambda: os.path.join(os.environ.get('APPDATA'), 'Tencent', 'WeChat').replace('\\', '/')
    ]

    for finder in path_finders:
        found_path = finder()
        if found_path and is_valid_wechat_data_path(found_path):
            save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                Config.INI_KEY_DATA_PATH, found_path)
            return found_path

    return None


def get_wechat_latest_version_path():
    path_finders = [
        lambda: get_setting_from_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                     Config.INI_KEY_VER_PATH, is_valid_wechat_latest_version_path),
        get_wechat_latest_version_path_by_sort()
    ]

    for finder in path_finders:
        found_path = finder
        if found_path and is_valid_wechat_latest_version_path(found_path):
            save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                Config.INI_KEY_VER_PATH, found_path)
            return found_path

    return None


def get_wechat_latest_version_path_by_sort():
    install_path = get_wechat_install_path()  # 获得完整路径
    # 删除路径末尾的 WeChat.exe，保留目录部分
    install_path = os.path.dirname(install_path)

    version_folders = [f for f in os.listdir(install_path) if f.startswith("[") and f.endswith("]")]
    if not version_folders:
        return None

    latest_version = max(version_folders, key=lambda v: list(map(int, v[1:-1].split("."))))
    return os.path.join(install_path, latest_version).replace('\\', '/')


if __name__ == "__main__":
    test_path = get_wechat_install_path()
    if test_path:
        print(f"微信安装路径: {test_path}")
    else:
        print("未能找到微信安装路径")
    # path = get_wechat_install_path_from_process()
    # if path:
    #     print(f"微信安装路径: {path}")
    # else:
    #     print("未能找到微信安装路径")
    # path = get_wechat_install_path_from_register()
    # if path:
    #     print(f"微信安装路径: {path}")
    # else:
    #     print("未能找到微信安装路径")
    test_path = get_wechat_data_path()
    if test_path:
        print(f"微信数据存储路径: {test_path}")
    else:
        print("未能找到微信数据存储路径")
    # path = get_wechat_data_path_from_register()
    # if path:
    #     print(f"微信安装路径: {path}")
    # else:
    #     print("未能找到微信数据存储路径")
    test_path = get_wechat_latest_version_path_by_sort()
    if test_path:
        print(f"微信最新版本路径: {test_path}")
    else:
        print("未能找到微信最新版本路径")
