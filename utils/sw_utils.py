import os
import winreg

import psutil

from functions import subfunc_file
from utils import process_utils
from utils.logger_utils import mylogger as logger


def is_valid_sw_install_path(sw, path) -> bool:
    if path is None:
        return False
    if path == "":
        return False
    executable, = subfunc_file.get_details_from_remote_setting_json(sw, executable=None)

    path_ext = os.path.splitext(path)[1].lower()
    exe_ext = os.path.splitext(executable)[1].lower()

    return path_ext == exe_ext



def is_valid_sw_data_dir(sw, path) -> bool:
    if path is None:
        return False
    if path == "":
        return False
    suffix, = subfunc_file.get_details_from_remote_setting_json(sw, data_dir_check_suffix=None)
    config_data_path = os.path.join(path, suffix).replace('\\', '/')
    # print("检查路径", config_data_path)
    # print(os.path.exists(config_data_path))
    return os.path.exists(config_data_path)


def is_valid_sw_dll_dir(sw, path) -> bool:
    if path is None:
        return False
    if path == "":
        return False
    suffix, = subfunc_file.get_details_from_remote_setting_json(sw, dll_dir_check_suffix=None)
    return os.path.isfile(os.path.join(path, suffix))


def get_sw_install_path_from_process(sw:str) -> list:
    executable, = subfunc_file.get_details_from_remote_setting_json(sw, executable=None)
    results = []
    for process in psutil.process_iter(['name', 'exe']):
        if process.name() == executable:
            path = process.exe().replace('\\', '/')
            results.append(path)
            logger.info(f"通过查找进程方式获取了安装地址：{path}")
            break
    return results


def get_sw_install_path_from_machine_register(sw:str) -> list:
    sub_key, executable = subfunc_file.get_details_from_remote_setting_json(
        sw, mac_reg_sub_key=None, executable=None)
    results = []
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             sub_key)
        found_path = winreg.QueryValueEx(key, "InstallLocation")[0].replace('\\', '/')
        winreg.CloseKey(key)
        logger.info(f"通过设备注册表获取了安装地址：{found_path}")
        if found_path:
            results.append(os.path.join(found_path, executable).replace('\\', '/'))

        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             sub_key)
        found_path = winreg.QueryValueEx(key, "DisplayIcon")[0].replace('\\', '/')
        winreg.CloseKey(key)
        logger.info(f"通过设备注册表获取了安装地址：{found_path}")
        if found_path:
            results.append(found_path.replace('\\', '/'))
    except WindowsError as e:
        logger.error(e)
    return results


def get_sw_install_path_from_user_register(sw:str) -> list:
    sub_key, executable = subfunc_file.get_details_from_remote_setting_json(
        sw, user_reg_sub_key=None, executable=None)
    results = []
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key)
        found_path = winreg.QueryValueEx(key, "InstallPath")[0].replace('\\', '/')
        winreg.CloseKey(key)
        logger.info(f"通过用户注册表获取了安装地址：{found_path}")
        if found_path:
            results.append(os.path.join(found_path, executable).replace('\\', '/'))
    except WindowsError as we:
        logger.error(we)
    return results


def get_sw_install_path_by_guess(sw:str) -> list:
    suffix, = subfunc_file.get_details_from_remote_setting_json(sw, inst_path_guess_suffix=None)
    guess_paths = [
        os.path.join(os.environ.get('ProgramFiles'), suffix).replace('\\', '/'),
        os.path.join(os.environ.get('ProgramFiles(x86)'), suffix).replace('\\', '/'),
    ]
    return guess_paths


def get_sw_data_dir_from_user_register(sw:str) -> list:
    sub_key, dir_name = subfunc_file.get_details_from_remote_setting_json(
        sw, user_reg_sub_key=None, data_dir_name=None)
    results = []
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "FileSavePath")
        winreg.CloseKey(key)
        value = os.path.join(value, dir_name).replace('\\', '/')
        results.append(value)
    except WindowsError as we:
        logger.error(we)
    return results


def get_sw_data_dir_by_guess(sw:str) -> list:
    data_dir_name, data_dir_guess_suffix = subfunc_file.get_details_from_remote_setting_json(
        sw, data_dir_name=None, data_dir_guess_suffix=None)
    guess_paths = [
        os.path.join(os.path.expanduser('~'), 'Documents', data_dir_name).replace('\\', '/'),
    ]
    return guess_paths


def get_sw_dll_dir_by_memo_maps(sw:str) -> list:
    dll_name, executable = subfunc_file.get_details_from_remote_setting_json(
        sw, dll_dir_check_suffix=None, executable=None)
    results = []
    pids = process_utils.get_process_ids_by_name(executable)
    if len(pids) == 0:
        logger.warning(f"没有运行该程序。")
        return []
    else:
        process_id = pids[0]
        try:
            for f in psutil.Process(process_id).memory_maps():
                normalized_path = f.path.replace('\\', '/')
                # print(normalized_path)
                if normalized_path.endswith(dll_name):
                    dll_dir_path = os.path.dirname(normalized_path)
                    # print(dll_dir_path)
                    results.append(dll_dir_path)
        except psutil.AccessDenied:
            logger.error(f"无法访问进程ID为 {process_id} 的内存映射文件，权限不足。")
        except psutil.NoSuchProcess:
            logger.error(f"进程ID为 {process_id} 的进程不存在或已退出。")
        except Exception as e:
            logger.error(f"发生意外错误: {e}")
    return results
