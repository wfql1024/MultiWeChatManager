# func_setting.py
import os

from functions import subfunc_file
from resources import Config
from utils import ini_utils, wechat_utils, file_utils
from utils.logger_utils import mylogger as logger


def get_sw_dll_dir_by_files(sw="WeChat"):
    """通过文件遍历方式获取dll文件夹"""
    dll_name, executable = subfunc_file.get_details_from_remote_setting_json(
        sw, dll_dir_check_suffix=None, executable=None)
    install_path = get_sw_install_path(sw)
    if install_path and install_path != "":
        install_dir = os.path.dirname(install_path)
    else:
        return []

    version_folders = []
    # 遍历所有文件及子文件夹
    for root, dirs, files in os.walk(install_dir):
        if dll_name in files:
            version_folders.append(root)  # 将包含WeChatWin.dll的目录添加到列表中

    if not version_folders:
        return []

    # 只有一个文件夹，直接返回
    if len(version_folders) == 1:
        dll_dir = version_folders[0].replace('\\', '/')
        print(f"只有一个文件夹：{dll_dir}")
        return [dll_dir]

    return [file_utils.get_newest_full_version_dir(version_folders)]


def get_sw_install_path(sw, from_setting_window=False):
    """获取微信安装路径"""
    path_finders = [
        wechat_utils.get_sw_install_path_from_process,
        None if from_setting_window else subfunc_file.get_sw_install_path_from_setting_ini,
        wechat_utils.get_sw_install_path_from_machine_register,
        wechat_utils.get_sw_install_path_from_user_register,
        wechat_utils.get_sw_install_path_by_guess,
    ]

    for index, finder in enumerate(path_finders):
        if finder is not None:
            path_list = finder(sw)
            if len(path_list) == 0 or path_list is None:
                continue
            for path in path_list:
                if wechat_utils.is_valid_sw_install_path(path, sw):
                    standardized_path = os.path.abspath(path).replace('\\', '/')
                    subfunc_file.save_sw_install_path_to_setting_ini(standardized_path, sw)
                    logger.info(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
                    return standardized_path
    return None


def get_sw_data_dir(sw, from_setting_window=False):
    """获取微信数据存储文件夹"""
    # 获取地址的各种方法
    path_finders = [
        None if from_setting_window else subfunc_file.get_sw_data_dir_from_setting_ini,
        wechat_utils.get_sw_data_dir_from_user_register,
        wechat_utils.get_sw_data_dir_by_guess,
    ]

    # 尝试各种方法
    for index, finder in enumerate(path_finders):

        if finder is not None:
            path_list = finder(sw=sw)
            # print(f"执行了当前方法：{finder.__name__}")
            if len(path_list) == 0 or path_list is None:
                continue
            # 对得到地址进行检验，正确则返回并保存
            for path in path_list:
                if wechat_utils.is_valid_sw_data_dir(path, sw):
                    standardized_path = os.path.abspath(path).replace('\\', '/')
                    subfunc_file.save_sw_data_dir_to_setting_ini(standardized_path, sw)
                    logger.info(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
                    return standardized_path
    return None


def get_sw_dll_dir(sw, from_setting_window=False):
    """获取微信dll所在文件夹"""
    path_finders = [
        None if from_setting_window else subfunc_file.get_sw_dll_dir_from_setting_ini,
        wechat_utils.get_sw_dll_dir_by_memo_maps,
        get_sw_dll_dir_by_files,
    ]
    for index, finder in enumerate(path_finders):
        if finder is not None:
            path_list = finder(sw)
            if len(path_list) == 0 or path_list is None:
                continue
            # 对得到地址进行检验，正确则返回并保存
            for path in path_list:
                if wechat_utils.is_valid_sw_dll_dir(path, sw):
                    standardized_path = os.path.abspath(path).replace('\\', '/')
                    subfunc_file.save_sw_dll_dir_to_setting_ini(standardized_path, sw)
                    logger.info(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
                    return standardized_path
    return None


def get_sw_cur_ver(sw="WeChat"):
    """获取当前使用的版本号"""
    # print(sw)
    install_path = get_sw_install_path(sw=sw)
    # print(install_path)
    if install_path is not None:
        if os.path.exists(install_path):
            return file_utils.get_file_version(install_path)
        return None


def fetch_global_setting_or_set_default(setting_key):
    """
    获取配置项，若没有则添加默认
    :return: 已选择的子程序
    """
    value = ini_utils.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        Config.INI_GLOBAL_SECTION,
        Config.INI_KEY[setting_key],
    )
    if not value or value == "":
        ini_utils.save_setting_to_ini(
            Config.SETTING_INI_PATH,
            Config.INI_GLOBAL_SECTION,
            Config.INI_KEY[setting_key],
            Config.INI_DEFAULT_VALUE[setting_key]
        )
        value = Config.INI_DEFAULT_VALUE[setting_key]
    return value

def fetch_sw_setting_or_set_default(setting_key, sw="WeChat"):
    """
    获取配置项，若没有则添加默认
    :return: 已选择的子程序
    """
    value = ini_utils.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        sw,
        Config.INI_KEY[setting_key],
    )
    if not value or value == "":
        ini_utils.save_setting_to_ini(
            Config.SETTING_INI_PATH,
            sw,
            Config.INI_KEY[setting_key],
            Config.INI_DEFAULT_VALUE[sw][setting_key]
        )
        value = Config.INI_DEFAULT_VALUE[sw][setting_key]
    return value


def toggle_sub_executable(file_name, initialization, sw="WeChat"):
    """
    切换多开子程序，之后进入初始化
    :param sw: 选择软件标签
    :param file_name: 选择的子程序文件名
    :param initialization: 初始化方法
    :return: 成功与否
    """
    ini_utils.save_setting_to_ini(
        Config.SETTING_INI_PATH,
        sw,
        Config.INI_KEY["sub_exe"],
        file_name
    )
    initialization()
    return True


def toggle_view(view, initialization, sw="WeChat"):
    """
    切换视图，之后进入初始化
    :param sw: 选择软件标签
    :param view: 选择的视图
    :param initialization: 初始化方法
    :return: 成功与否
    """
    ini_utils.save_setting_to_ini(
        Config.SETTING_INI_PATH,
        sw,
        Config.INI_KEY["view"],
        view
    )
    initialization()
    return True

def toggle_tab(tab):
    """
        切换待刷新的标签
        :param tab: 选择的标签
        :return: 成功与否
        """
    ini_utils.save_setting_to_ini(
        Config.SETTING_INI_PATH,
        Config.INI_GLOBAL_SECTION,
        Config.INI_KEY["tab"],
        tab
    )
    return True
# if __name__ == "__main__":
#     get_wechat_dll_dir_path_by_files()
