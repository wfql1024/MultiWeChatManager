import os
import time
from datetime import datetime

import psutil

import functions.func_setting as func_get_path
import utils.json_utils as json_utils
from resources.config import Config
from utils import process_utils, string_utils


def get_config_status(account) -> str:
    """
    通过账号的配置状态
    :param account: 账号
    :return: 配置状态
    """
    data_path = func_get_path.get_wechat_data_path()
    if not data_path:
        return "无法获取配置路径"

    config_path = os.path.join(data_path, "All Users", "config", f"{account}.data")
    if os.path.exists(config_path):
        mod_time = os.path.getmtime(config_path)
        date = datetime.fromtimestamp(mod_time)
        return f"{date.month}-{date.day} {date.hour:02}:{date.minute:02}"
    else:
        return "无配置"


def update_acc_details_to_json(account, **kwargs) -> None:
    """更新账户信息到 JSON"""
    account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
    if account not in account_data:
        account_data[account] = {}
    # 遍历 kwargs 中的所有参数，并更新到 account_data 中
    for key, value in kwargs.items():
        account_data[account][key] = value
    json_utils.save_json_data(Config.ACC_DATA_JSON_PATH, account_data)


from typing import Tuple, Any


def get_acc_details_from_json(account: str, *args: str) -> Tuple[Any, ...]:
    """
    根据用户输入的变量名，获取对应的账户信息
    :param account: 账户名
    :param args: 需要获取的变量名（如 'note', 'nickname', 'alias'）
    :return: 包含所请求数据的元组
    """
    account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
    account_info = account_data.get(account, {})

    # 根据 args 中传递的变量名，返回对应的值
    result = tuple(account_info.get(arg, None) for arg in args)

    return result


def get_account_display_name(account) -> str:
    """
    获取账号的展示名
    :param account: 微信账号
    :return: 展示在界面的名字
    """
    account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
    account_info = account_data.get(account, {})
    # 依次查找 note, nickname, alias，找到第一个不为 None 的值
    display_name = next(
        (
            account_info.get(key)
            for key in ("note", "nickname", "alias")
            if account_info.get(key)
        ),
        account
    )
    return string_utils.balanced_wrap_text(display_name, 10)


def get_account_list() -> tuple[None, None, None] | tuple[list, list[str], list]:
    """
    获取账号及其登录情况

    :Returns: ["已登录账号"]，["未登录账号"]，[("已登录进程", int(账号))]
    """

    def update_acc_list_by_pid(process_id: int):
        """
        为存在的微信进程匹配出对应的账号，并更新[已登录账号]和[(已登录进程,账号)]
        :param process_id: 微信进程id
        :return: 无
        """
        try:
            # 获取指定进程的内存映射文件路径
            for f in psutil.Process(process_id).memory_maps():
                # 将路径中的反斜杠替换为正斜杠
                normalized_path = f.path.replace('\\', '/')
                # 检查路径是否以 data_path 开头
                if normalized_path.startswith(data_path):
                    print(
                        f"┌———匹配到进程{process_id}使用的符合的文件，待对比，已用时：{time.time() - start_time:.4f}秒")
                    print(f"提取中：{f.path}")
                    path_parts = f.path.split(os.path.sep)
                    try:
                        wxid_index = path_parts.index(os.path.basename(data_path)) + 1
                        wxid = path_parts[wxid_index]
                        wechat_processes.append((wxid, process_id))
                        logged_in_wxids.add(wxid)
                        print(f"└———提取到进程{process_id}对应账号{wxid}，已用时：{time.time() - start_time:.4f}秒")
                        break
                    except ValueError:
                        pass
        except psutil.AccessDenied:
            print(f"无法访问进程ID为 {process_id} 的内存映射文件，权限不足。")
        except psutil.NoSuchProcess:
            print(f"进程ID为 {process_id} 的进程不存在或已退出。")
        except Exception as e:
            print(f"发生意外错误: {e}")

    start_time = time.time()
    data_path = func_get_path.get_wechat_data_path()
    if not data_path:
        return None, None, None

    wechat_processes = []
    logged_in_wxids = set()

    pids = process_utils.get_process_ids_by_name("WeChat.exe")
    print(f"读取到微信所有进程，用时：{time.time() - start_time:.4f} 秒")
    if len(pids) != 0:
        for pid in pids:
            update_acc_list_by_pid(pid)
    print(f"完成判断进程对应账号，用时：{time.time() - start_time:.4f} 秒")

    # 获取文件夹并分类
    excluded_folders = {'All Users', 'Applet', 'Plugins', 'WMPF'}
    folders = set(
        folder for folder in os.listdir(data_path)
        if os.path.isdir(os.path.join(data_path, folder))
    ) - excluded_folders
    logged_in = list(logged_in_wxids & folders)
    not_logged_in = list(folders - logged_in_wxids)

    print("logged_in", logged_in)
    print("not_logged_in", not_logged_in)
    print(f"完成账号分类，用时：{time.time() - start_time:.4f} 秒")

    # 更新数据
    pid_dict = dict(wechat_processes)
    for acc in logged_in + not_logged_in:
        # 如果找不到 acc 对应的 PID，存入空字符串 ""
        update_acc_details_to_json(acc, pid=pid_dict.get(acc, ""))

    print(f"完成记录账号对应pid，用时：{time.time() - start_time:.4f} 秒")

    return logged_in, not_logged_in, wechat_processes


if __name__ == '__main__':
    pass
