import configparser
import os
import winreg

import psutil

from resources import Config


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


def is_valid_wechat_latest_version_path(path) -> bool:
    valid_path = get_wechat_latest_version_path_by_sort()
    if valid_path and path == valid_path:
        return True
    elif not valid_path and path and path != "":
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
                print(f"在{os.path.basename(ini_filename)}[{section}]{key}中获取到数据：{current_setting}")
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


def get_wechat_latest_version_path_by_sort():
    install_path = get_wechat_install_path()  # 获得完整路径
    # install_path = "D:/software/Tencent/WeChat/WeChat.exe"
    # 删除路径末尾的 WeChat.exe，保留目录部分
    if install_path and install_path != "":
        install_path = os.path.dirname(install_path)

    version_folders = [f for f in os.listdir(install_path) if f.startswith("[") and f.endswith("]")]
    if not version_folders:
        return None

    latest_version = max(version_folders, key=lambda v: list(map(int, v[1:-1].split("."))))
    return os.path.join(install_path, latest_version).replace('\\', '/')


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


def get_wechat_latest_version_path():
    path_finders = [
        get_wechat_latest_version_path_by_sort,
        lambda: get_setting_from_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                     Config.INI_KEY_VER_PATH)
    ]

    for index, finder in enumerate(path_finders):
        # print(f"当前方法：{finder.__name__}")
        found_path = finder()
        if is_valid_wechat_latest_version_path(found_path):
            save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                Config.INI_KEY_VER_PATH, found_path)
            print(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
            return found_path

    # print("——————————所有方法都已测试——————————")

    return None


if __name__ == "__main__":
    get_wechat_install_path()
    get_wechat_data_path()
    get_wechat_latest_version_path()
