# func_setting.py
import os
from functions import subfunc_file
from resources import Config
from utils import ini_utils, wechat_utils, file_utils
from utils.logger_utils import mylogger as logger


def get_wechat_dll_dir_by_files():
    """通过文件遍历获取dll文件夹"""
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

    return file_utils.get_newest_full_version_dir(version_folders)


def get_wechat_install_path(from_setting_window=None):
    """获取微信安装路径"""
    path_finders = [
        wechat_utils.get_wechat_install_path_from_process,
        (lambda: None) if from_setting_window else subfunc_file.get_wechat_install_path_from_setting_ini,
        wechat_utils.get_wechat_install_path_from_machine_register,
        wechat_utils.get_wechat_install_path_from_user_register,
        lambda: os.path.join(os.environ.get('ProgramFiles'), 'Tencent', 'WeChat', 'WeChat.exe').replace('\\', '/'),
        lambda: os.path.join(os.environ.get('ProgramFiles(x86)'), 'Tencent', 'WeChat', 'WeChat.exe').replace('\\', '/'),
    ]

    for index, finder in enumerate(path_finders):
        found_path = finder()
        if wechat_utils.is_valid_wechat_install_path(found_path):
            standardized_path = os.path.abspath(found_path).replace('\\', '/')
            subfunc_file.save_wechat_install_path_to_setting_ini(standardized_path)
            logger.info(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
            return standardized_path

    return None


def get_wechat_data_dir(from_setting_window=None):
    """获取微信数据存储文件夹"""
    # 获取地址的各种方法
    path_finders = [
        (lambda: None) if from_setting_window else subfunc_file.get_wechat_data_dir_from_setting_ini,
        wechat_utils.get_wechat_data_dir_from_user_register,
        lambda: os.path.join(os.path.expanduser('~'), 'Documents', 'WeChat Files').replace('\\', '/'),
        lambda: os.path.join(os.environ.get('APPDATA'), 'Tencent', 'WeChat').replace('\\', '/')
    ]

    # 尝试各种方法
    for index, finder in enumerate(path_finders):
        # print(f"当前方法：{finder.__name__}")
        found_path = finder()
        # 对得到地址进行检验，正确则返回并保存
        if wechat_utils.is_valid_wechat_data_path(found_path):
            standardized_path = os.path.abspath(found_path).replace('\\', '/')
            subfunc_file.save_wechat_data_path_to_setting_ini(standardized_path)
            logger.info(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
            return standardized_path

    return None


def get_wechat_dll_dir(from_setting_window=None):
    """获取微信dll所在文件夹"""
    path_finders = [
        (lambda: None) if from_setting_window else subfunc_file.get_wechat_dll_dir_from_setting_ini,
        wechat_utils.get_wechat_dll_dir_by_memo_maps,
        get_wechat_dll_dir_by_files,
    ]
    for index, finder in enumerate(path_finders):
        found_path = finder()
        if wechat_utils.is_valid_wechat_dll_dir_path(found_path):
            standardized_path = os.path.abspath(found_path).replace('\\', '/')
            subfunc_file.save_wechat_dll_dir_path_to_setting_ini(standardized_path)
            logger.info(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
            return standardized_path
    return None


def get_cur_wechat_ver():
    """获取当前使用的版本号"""
    install_path = get_wechat_install_path()
    if install_path is not None:
        if os.path.exists(install_path):
            return file_utils.get_file_version(install_path)
        return None


def fetch_setting_or_set_default(setting_key):
    """
    获取配置项，若没有则添加默认
    :return: 已选择的子程序
    """
    chosen_sub_exe = ini_utils.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY[setting_key],
    )
    if not chosen_sub_exe or chosen_sub_exe == "":
        ini_utils.save_setting_to_ini(
            Config.SETTING_INI_PATH,
            Config.INI_SECTION,
            Config.INI_KEY[setting_key],
            Config.INI_DEFAULT_VALUE[setting_key]
        )
        chosen_sub_exe = Config.INI_DEFAULT_VALUE[setting_key]
    return chosen_sub_exe


def toggle_sub_executable(file_name, initialization):
    """
    切换多开子程序，之后进入初始化
    :param file_name: 选择的子程序文件名
    :param initialization: 初始化方法
    :return: 成功与否
    """
    ini_utils.save_setting_to_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY["sub_exe"],
        file_name
    )
    initialization()
    return True


def toggle_view(view, initialization):
    """
    切换视图，之后进入初始化
    :param view: 选择的视图
    :param initialization: 初始化方法
    :return: 成功与否
    """
    ini_utils.save_setting_to_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY["view"],
        view
    )
    initialization()
    return True

# if __name__ == "__main__":
#     get_wechat_dll_dir_path_by_files()
