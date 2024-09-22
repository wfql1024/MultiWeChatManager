from typing import Tuple, Any

from resources import Config
from utils import json_utils, ini_utils


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


def update_acc_details_to_json(account, **kwargs) -> None:
    """更新账户信息到 JSON"""
    account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
    if account not in account_data:
        account_data[account] = {}
    # 遍历 kwargs 中的所有参数，并更新到 account_data 中
    for key, value in kwargs.items():
        account_data[account][key] = value
        print(f"更新[{account}][{key}]:{value}")
    json_utils.save_json_data(Config.ACC_DATA_JSON_PATH, account_data)


def get_acc_details_from_json(account: str, **kwargs) -> Tuple[Any, ...]:
    """
    根据用户输入的变量名，获取对应的账户信息
    :param account: 账户名
    :param kwargs: 需要获取的变量名及其默认值（如 note="", nickname=None）
    :return: 包含所请求数据的元组
    """
    account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
    account_info = account_data.get(account, {})
    result = tuple()
    for key, default in kwargs.items():
        result += (account_info.get(key, default),)
        print(f"获取[{account}][{key}]：{account_info.get(key, default)}")
    print(f"└—————————————————————————————————————————")
    return result


def clear_all_wechat_in_json():
    """
    清空登录列表all_wechat结点中，适合登录之前使用
    :return: 是否成功
    """
    # 加载当前账户数据
    account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)

    # 检查 all_wechat 节点是否存在
    if "all_wechat" in account_data:
        # 清除 all_wechat 中的所有字段
        account_data["all_wechat"].clear()
        print("all_wechat 节点的所有字段已清空")

    # 保存更新后的数据
    json_utils.save_json_data(Config.ACC_DATA_JSON_PATH, account_data)
    return True


def update_all_wechat_in_json():
    """
    清空后将json中所有已登录账号的情况加载到登录列表all_wechat结点中，适合登录之前使用
    :return: 是否成功
    """
    # 加载当前账户数据
    account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)

    # 初始化 all_wechat 为空字典
    all_wechat = {}

    # 遍历所有的账户
    for account, details in account_data.items():
        pid = details.get("pid")
        # 检查 pid 是否为整数
        if isinstance(pid, int):
            has_mutex = details.get("has_mutex", False)
            all_wechat[str(pid)] = has_mutex

    # 更新 all_wechat 到 JSON 文件
    update_acc_details_to_json("all_wechat", **all_wechat)
    return True


def set_all_wechat_values_to_false():
    """
    将所有微信进程all_wechat中都置为没有互斥体，适合每次成功打开一个登录窗口后使用
    （因为登录好一个窗口，说明之前所有的微信都没有互斥体了）
    :return: 是否成功
    """
    # 加载当前账户数据
    account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)

    # 获取 all_wechat 节点，如果不存在就创建一个空的
    all_wechat = account_data.get("all_wechat", {})

    # 将所有字段的值设置为 False
    for pid in all_wechat:
        all_wechat[pid] = False

    # 保存更新后的数据
    json_utils.save_json_data(Config.ACC_DATA_JSON_PATH, account_data)


def update_has_mutex_from_all_wechat():
    """
    将json中登录列表all_wechat结点中的情况加载回所有已登录账号，适合刷新结束时使用
    :return: 是否成功
    """
    account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
    if "all_wechat" not in account_data:
        account_data["all_wechat"] = {}
    for account, details in account_data.items():
        if account == "all_wechat":
            continue
        pid = details.get("pid", None)
        if pid and pid is not None:
            has_mutex = account_data["all_wechat"].get(f"{pid}", True)
            update_acc_details_to_json(account, has_mutex=has_mutex)


