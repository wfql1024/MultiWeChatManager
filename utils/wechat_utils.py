import os
import winreg

import psutil

from utils import process_utils
from utils.logger_utils import mylogger as logger


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


def get_wechat_install_path_from_process():
    for process in psutil.process_iter(['name', 'exe']):
        if process.name() == 'WeChat.exe':
            path = process.exe().replace('\\', '/')
            logger.info(f"通过查找进程方式获取了微信安装地址：{path}")
            return path
    return None


def get_wechat_install_path_from_machine_register():
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\WeChat")
        found_path = winreg.QueryValueEx(key, "InstallLocation")[0].replace('\\', '/')
        winreg.CloseKey(key)
        logger.info(f"通过注册表方式1获取了微信安装地址：{found_path}")
        if found_path:
            return os.path.join(found_path, "WeChat.exe").replace('\\', '/')
    except WindowsError as e:
        logger.error(e)
    return None


def get_wechat_install_path_from_user_register():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Tencent\WeChat")
        found_path = winreg.QueryValueEx(key, "InstallPath")[0].replace('\\', '/')
        winreg.CloseKey(key)
        logger.info(f"通过注册表方式2获取了微信安装地址：{found_path}")
        if found_path:
            return os.path.join(found_path, "WeChat.exe").replace('\\', '/')
    except WindowsError as e:
        logger.error(e)
    return None


def get_wechat_data_dir_from_user_register():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Tencent\WeChat", 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "FileSavePath")
        winreg.CloseKey(key)
        value = os.path.join(value, "WeChat Files").replace('\\', '/')
        return value
    except WindowsError:
        pass
    return None


def get_wechat_dll_dir_by_memo_maps():
    pids = process_utils.get_process_ids_by_name("WeChat.exe")
    if len(pids) == 0:
        logger.warning(f"没有运行微信。")
        return None
    else:
        process_id = pids[0]
        try:
            for f in psutil.Process(process_id).memory_maps():
                normalized_path = f.path.replace('\\', '/')
                # print(normalized_path)
                if normalized_path.endswith('WeChatWin.dll'):
                    dll_dir_path = os.path.dirname(normalized_path)
                    # print(dll_dir_path)
                    return dll_dir_path
        except psutil.AccessDenied:
            logger.error(f"无法访问进程ID为 {process_id} 的内存映射文件，权限不足。")
        except psutil.NoSuchProcess:
            logger.error(f"进程ID为 {process_id} 的进程不存在或已退出。")
        except Exception as e:
            logger.error(f"发生意外错误: {e}")


if __name__ == '__main__':
    pass
