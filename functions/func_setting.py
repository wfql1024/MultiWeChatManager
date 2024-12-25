# func_setting.py
import os
from tkinter import messagebox, simpledialog

from functions import subfunc_file
from resources import Config
from utils import ini_utils, sw_utils, file_utils
from utils.logger_utils import mylogger as logger


def get_sw_data_dir_from_other_sw(sw="WeChat"):
    """通过其他软件的方式获取微信数据文件夹"""
    data_dir_name, = subfunc_file.get_details_from_remote_setting_json(
        sw, data_dir_name=None)
    if data_dir_name is None or data_dir_name == "":
        return []
    if sw == "Weixin":
        old_path = get_sw_data_dir(sw="WeChat")
        if old_path and old_path != "":
            return [os.path.join(os.path.dirname(old_path), data_dir_name).replace('\\', '/')]
        else:
            return []


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
    print("获取安装路径...")
    path_finders = [
        sw_utils.get_sw_install_path_from_process,
        None if from_setting_window else subfunc_file.get_sw_install_path_from_setting_ini,
        sw_utils.get_sw_install_path_from_machine_register,
        sw_utils.get_sw_install_path_from_user_register,
        sw_utils.get_sw_install_path_by_guess,
    ]

    for index, finder in enumerate(path_finders):
        if finder is not None:
            paths = finder(sw)
            if paths is None:
                continue
            path_list = list(paths)  # 如果确定返回值是可迭代对象，强制转换为列表
            if len(path_list) == 0:
                continue
            for path in path_list:
                if sw_utils.is_valid_sw_install_path(path, sw):
                    standardized_path = os.path.abspath(path).replace('\\', '/')
                    subfunc_file.save_sw_setting(sw, 'inst_path', standardized_path)
                    logger.info(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
                    return standardized_path
    return None


def get_sw_data_dir(sw, from_setting_window=False):
    """获取微信数据存储文件夹"""
    print("获取数据目录...")
    # 获取地址的各种方法
    path_finders = [
        None if from_setting_window else subfunc_file.get_sw_data_dir_from_setting_ini,
        sw_utils.get_sw_data_dir_from_user_register,
        sw_utils.get_sw_data_dir_by_guess,
        get_sw_data_dir_from_other_sw,
    ]

    # 尝试各种方法
    for index, finder in enumerate(path_finders):

        if finder is not None:
            paths = finder(sw)
            if paths is None:
                continue
            path_list = list(paths)  # 如果确定返回值是可迭代对象，强制转换为列表
            if len(path_list) == 0:
                continue
            # 对得到地址进行检验，正确则返回并保存
            for path in path_list:
                if sw_utils.is_valid_sw_data_dir(path, sw):
                    standardized_path = os.path.abspath(path).replace('\\', '/')
                    subfunc_file.save_sw_setting(sw, 'data_dir', standardized_path)
                    logger.info(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
                    return standardized_path
    return None


def get_sw_dll_dir(sw, from_setting_window=False):
    """获取微信dll所在文件夹"""
    print("获取dll目录...")
    path_finders = [
        None if from_setting_window else subfunc_file.get_sw_dll_dir_from_setting_ini,
        sw_utils.get_sw_dll_dir_by_memo_maps,
        get_sw_dll_dir_by_files,
    ]
    for index, finder in enumerate(path_finders):
        if finder is not None:
            paths = finder(sw)
            if paths is None:
                continue
            path_list = list(paths)  # 如果确定返回值是可迭代对象，强制转换为列表
            if len(path_list) == 0:
                continue
            # 对得到地址进行检验，正确则返回并保存
            for path in path_list:
                if sw_utils.is_valid_sw_dll_dir(path, sw):
                    standardized_path = os.path.abspath(path).replace('\\', '/')
                    subfunc_file.save_sw_setting(sw, 'dll_dir', standardized_path)
                    logger.info(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
                    return standardized_path
    return None


def get_sw_inst_path_and_ver(sw, from_setting_window=False):
    """获取当前使用的版本号"""
    # print(sw)
    install_path = get_sw_install_path(sw, from_setting_window)
    # print(install_path)
    if install_path is not None:
        if os.path.exists(install_path):
            return install_path, file_utils.get_file_version(install_path)
        return install_path, None
    return None, None


def toggle_sub_executable(file_name, after, sw="WeChat"):
    """
    切换多开子程序，之后进入初始化
    :param sw: 选择软件标签
    :param file_name: 选择的子程序文件名
    :param after: 初始化方法
    :return: 成功与否
    """
    ini_utils.save_setting_to_ini(
        Config.SETTING_INI_PATH,
        sw,
        Config.INI_KEY["sub_exe"],
        file_name
    )
    after()
    return True


def toggle_view(view, after, sw="WeChat"):
    """
    切换视图，之后进入初始化
    :param sw: 选择软件标签
    :param view: 选择的视图
    :param after: 初始化方法
    :return: 成功与否
    """
    ini_utils.save_setting_to_ini(
        Config.SETTING_INI_PATH,
        sw,
        Config.INI_KEY["view"],
        view
    )
    after()
    return True


def toggle_tab_record(tab):
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

def toggle_sign_visibility(value, after):
    """
    切换签名显示
    :param value: 值
    :param after: 后续操作
    :return: 成功与否
    """
    ini_utils.save_setting_to_ini(
        Config.SETTING_INI_PATH,
        Config.INI_GLOBAL_SECTION,
        Config.INI_KEY["sign_visible"],
        value
    )
    after()

def set_wnd_scale(after, scale=None):
    if scale is None:
        # 创建输入框
        try:
            user_input = simpledialog.askstring(
                title="输入 Scale",
                prompt="请输入一个 75-500 之间的数字（含边界）："
            )
            if user_input is None:  # 用户取消或关闭输入框
                after()
                return

            # 尝试将输入转换为整数并验证范围
            scale = int(user_input)
            if not (75 <= scale <= 500):
                raise ValueError("输入值不在 75-500 范围内")
        except (ValueError, TypeError):
            messagebox.showerror("错误", "无效输入，操作已取消")
            after()
            return

    ini_utils.save_setting_to_ini(
        Config.SETTING_INI_PATH,
        Config.INI_GLOBAL_SECTION,
        Config.INI_KEY["scale"],
        str(scale)
    )
    messagebox.showinfo("提示", "修改成功，将在重新启动程序后生效！")
    after()
    return


if __name__ == "__main__":
    path_lsit = list(None or [])
    print(path_lsit)
