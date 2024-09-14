# func_setting.py
import os
import re

from resources import Config
from utils import ini_utils, wechat_utils, file_utils


def save_wechat_install_path_to_ini(value):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                         Config.INI_KEY_INSTALL_PATH, value)


def save_wechat_data_path_to_ini(value):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                         Config.INI_KEY_DATA_PATH, value)


def save_wechat_dll_dir_path_to_ini(value):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                         Config.INI_KEY_DLL_DIR_PATH, value)


def save_screen_size_to_ini(value):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                         Config.INI_KEY_SCREEN_SIZE, value)


def save_login_size_to_ini(value):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                         Config.INI_KEY_LOGIN_SIZE, value)


def get_wechat_install_path_from_ini():
    return ini_utils.get_setting_from_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                          Config.INI_KEY_INSTALL_PATH)


def get_wechat_data_path_from_ini():
    return ini_utils.get_setting_from_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                          Config.INI_KEY_DATA_PATH)


def get_wechat_dll_dir_path_from_ini():
    return ini_utils.get_setting_from_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                          Config.INI_KEY_DLL_DIR_PATH)


def get_wechat_dll_dir_path_by_files():
    install_path = get_wechat_install_path()
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
        print(f"{dll_dir}")
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


def get_screen_size_from_ini():
    result = ini_utils.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY_SCREEN_SIZE
    )
    if not result or result == "":
        return None
    else:
        screen_width, screen_height = result.split('*')
        return int(screen_width), int(screen_height)


def get_login_size_from_ini():
    return ini_utils.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY_LOGIN_SIZE
    )


def get_wechat_install_path():
    path_finders = [
        wechat_utils.get_wechat_install_path_from_process,
        get_wechat_install_path_from_ini,
        wechat_utils.get_wechat_install_path_from_machine_register,
        wechat_utils.get_wechat_install_path_from_user_register,
        lambda: os.path.join(os.environ.get('ProgramFiles'), 'Tencent', 'WeChat', 'WeChat.exe').replace('\\', '/'),
        lambda: os.path.join(os.environ.get('ProgramFiles(x86)'), 'Tencent', 'WeChat', 'WeChat.exe').replace('\\', '/'),
    ]

    for index, finder in enumerate(path_finders):
        # print(f"当前方法：{finder.__name__} (索引: {index})")
        path = finder()
        if wechat_utils.is_valid_wechat_install_path(path):
            save_wechat_install_path_to_ini(path)
            print(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
            return path

    return None


def get_wechat_data_path():
    # 获取地址的各种方法
    path_finders = [
        get_wechat_data_path_from_ini,
        wechat_utils.get_wechat_data_path_from_user_register,
        lambda: os.path.join(os.path.expanduser('~'), 'Documents', 'WeChat Files').replace('\\', '/'),
        lambda: os.path.join(os.environ.get('APPDATA'), 'Tencent', 'WeChat').replace('\\', '/')
    ]

    # 尝试各种方法
    for index, finder in enumerate(path_finders):
        # print(f"当前方法：{finder.__name__}")
        found_path = finder()
        # 对得到地址进行检验，正确则返回并保存
        if wechat_utils.is_valid_wechat_data_path(found_path):
            save_wechat_data_path_to_ini(found_path)
            print(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
            return found_path

    return None


def get_wechat_dll_dir_path():
    path_finders = [
        get_wechat_dll_dir_path_from_ini,
        wechat_utils.get_wechat_dll_dir_path_by_memo_maps,
        get_wechat_dll_dir_path_by_files,
    ]

    for index, finder in enumerate(path_finders):
        # print(f"当前方法：{finder.__name__}")
        found_path = finder()
        if wechat_utils.is_valid_wechat_dll_dir_path(found_path):
            save_wechat_dll_dir_path_to_ini(found_path)
            print(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
            return found_path

    return None


def update_current_ver():
    install_path = get_wechat_install_path()
    if os.path.exists(install_path):
        return file_utils.get_file_version(install_path)
    return None


def fetch_sub_exe():
    # 检查选择的子程序，若没有则添加默认
    chosen_sub_exe = ini_utils.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY_SUB_EXE,
    )
    if not chosen_sub_exe or chosen_sub_exe == "":
        ini_utils.save_setting_to_ini(
            Config.SETTING_INI_PATH,
            Config.INI_SECTION,
            Config.INI_KEY_SUB_EXE,
            Config.DEFAULT_SUB_EXE
        )
        chosen_sub_exe = Config.DEFAULT_SUB_EXE
    return chosen_sub_exe


def toggle_sub_executable(file_name, initialization):
    ini_utils.save_setting_to_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY_SUB_EXE,
        file_name
    )
    initialization()

# if __name__ == "__main__":
#     get_wechat_dll_dir_path_by_files()
