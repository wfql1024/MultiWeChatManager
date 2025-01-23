# func_setting.py
import os
from tkinter import messagebox, simpledialog
from typing import Union, Tuple

import yaml

from functions import subfunc_file
from resources import Config
from utils import ini_utils, sw_utils, file_utils
from utils.logger_utils import mylogger as logger


def cycle_get_a_path_with_funcs(path_type: str, sw: str, path_finders: list, check_sw_path_func) \
        -> Union[Tuple[bool, bool, Union[None, str]]]:
    """
    获取微信数据路径的结果元组
    :param path_type: 路径类型
    :param sw: 平台
    :param path_finders: 是否从设置窗口调用
    :param check_sw_path_func: 校验函数，参数为sw和path
    :return: 成功，是否改变，结果
    """
    success = False
    changed = False
    result = None

    # 尝试各种方法
    for index, finder in enumerate(path_finders):
        if finder is None:
            continue
        paths = finder(sw)
        path_list = list(paths)  # 如果确定返回值是可迭代对象，强制转换为列表
        if not path_list:
            continue
        # 检验地址并退出所有循环
        for path in path_list:
            if check_sw_path_func(sw, path):
                logger.info(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果")
                standardized_path = os.path.abspath(path).replace('\\', '/')
                changed = subfunc_file.save_sw_setting(sw, path_type, standardized_path)
                result = standardized_path
                success = True
                break
        if success:
            break

    return success, changed, result


def get_sw_install_path(sw: str, from_setting_window=False) -> Union[None, str]:
    """
    获取微信安装路径
    :param sw: 平台
    :param from_setting_window: 是否从设置窗口调用
    :return: 路径
    """
    print("获取安装路径...")
    _, _, result = get_sw_install_path_by_tuple(sw, from_setting_window)
    return result


def get_sw_install_path_by_tuple(sw: str, from_setting_window=False) \
        -> Union[Tuple[bool, bool, Union[None, str]]]:
    """
    获取微信安装路径的结果元组
    :param sw: 平台
    :param from_setting_window: 是否从设置窗口调用
    :return: 成功，是否改变，结果
    """
    path_finders = [
        sw_utils.get_sw_install_path_from_process,
        (lambda lsw: []) if from_setting_window else subfunc_file.get_sw_install_path_from_setting_ini,
        sw_utils.get_sw_install_path_from_machine_register,
        sw_utils.get_sw_install_path_from_user_register,
        sw_utils.get_sw_install_path_by_guess,
    ]

    check_func = sw_utils.is_valid_sw_install_path
    path_type = 'inst_path'

    return cycle_get_a_path_with_funcs(path_type, sw, path_finders, check_func)


def get_sw_data_dir(sw: str, from_setting_window=False):
    """
    获取微信数据路径
    :param sw: 平台
    :param from_setting_window: 是否从设置窗口调用
    :return: 路径
    """
    print("获取安装路径...")
    _, _, result = get_sw_data_dir_to_tuple(sw, from_setting_window)
    return result


def get_sw_data_dir_to_tuple(sw: str, from_setting_window=False) \
        -> Union[Tuple[bool, bool, Union[None, str]]]:
    """
    获取微信数据路径的结果元组
    :param sw: 平台
    :param from_setting_window: 是否从设置窗口调用
    :return: 成功，是否改变，结果
    """
    path_finders = [
        (lambda lsw: []) if from_setting_window else subfunc_file.get_sw_data_dirs_from_setting_ini,
        sw_utils.get_sw_data_dir_from_user_register,
        sw_utils.get_sw_data_dir_by_guess,
        get_sw_data_dir_from_other_sw,
    ]
    check_func = sw_utils.is_valid_sw_data_dir
    path_type = 'data_dir'

    return cycle_get_a_path_with_funcs(path_type, sw, path_finders, check_func)


def get_sw_dll_dir(sw: str, from_setting_window=False):
    """获取微信dll所在文件夹"""
    print("获取dll目录...")
    _, _, result = get_sw_dll_dir_to_tuple(sw, from_setting_window)
    return result


def get_sw_dll_dir_to_tuple(sw: str, from_setting_window=False):
    """获取微信dll所在文件夹"""
    path_finders = [
        (lambda lsw: []) if from_setting_window else subfunc_file.get_sw_dll_dir_from_setting_ini,
        sw_utils.get_sw_dll_dir_by_memo_maps,
        get_sw_dll_dir_by_files,
    ]
    check_func = sw_utils.is_valid_sw_dll_dir
    path_type = 'dll_dir'

    return cycle_get_a_path_with_funcs(path_type, sw, path_finders, check_func)


def get_sw_inst_path_and_ver(sw: str, from_setting_window=False):
    """获取当前使用的版本号"""
    # print(sw)
    install_path = get_sw_install_path(sw, from_setting_window)
    # print(install_path)
    if install_path is not None:
        if os.path.exists(install_path):
            return install_path, file_utils.get_file_version(install_path)
        return install_path, None
    return None, None


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
    print(f"成功设置窗口缩放比例为 {scale}！")
    return


def get_sw_data_dir_from_other_sw(sw: str) -> list:
    """通过其他软件的方式获取微信数据文件夹"""
    data_dir_name, = subfunc_file.get_details_from_remote_setting_json(
        sw, data_dir_name=None)
    paths = []
    if data_dir_name is None or data_dir_name == "":
        paths = []
    if sw == "Weixin":
        other_path = get_sw_data_dir("WeChat")
        if other_path and other_path != "":
            paths = [os.path.join(os.path.dirname(other_path), data_dir_name).replace('\\', '/')]
        else:
            paths = []
    if sw == "WeChat":
        other_path = get_sw_data_dir("Weixin")
        if other_path and other_path != "":
            return [os.path.join(os.path.dirname(other_path), data_dir_name).replace('\\', '/')]
        else:
            return []

    return paths


def get_sw_dll_dir_by_files(sw: str) -> list:
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


def read_yaml(file_path):
    """读取YML文件并解析"""
    with open(file_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)


def insert_tree_data(tree, data):
    """将YML数据插入到Treeview中"""
    for top_key, top_value in data.items():
        # 插入一级节点（如global, WeChat等）
        top_node = tree.insert("", "end", text=top_key, values=(top_key, ""))

        # 插入二级节点（name 和 value）
        for sub_key, sub_value in top_value.items():
            tree.insert(top_node, "end", text=sub_key, values=(sub_value["name"], sub_value["value"]))


def create_setting_tab():
    pass
    # self.tab_mng = ttk.Frame(self.tab_control)
    # self.tab_control.add(self.tab_mng, text='管理')
    # # 读取YML文件并解析
    # data = read_yaml(Config.LOCAL_SETTING_YML_PATH)
    # # 创建Treeview控件
    # tree = ttk.Treeview(self.tab_mng, columns=("name", "value"), show="headings")
    # tree.pack(expand=True, fill=tk.BOTH)
    # # 定义列标题
    # tree.heading("name", text="Name")
    # tree.heading("value", text="Value")
    # # 填充树数据
    # insert_tree_data(tree, data)


if __name__ == "__main__":
    pass
