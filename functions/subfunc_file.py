import math
from typing import Tuple, Any

from resources import Config
from utils import json_utils, ini_utils


def save_wechat_install_path_to_setting_ini(value):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                         Config.INI_KEY_INSTALL_PATH, value)


def save_wechat_data_path_to_setting_ini(value):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                         Config.INI_KEY_DATA_PATH, value)


def save_wechat_dll_dir_path_to_setting_ini(value):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                         Config.INI_KEY_DLL_DIR_PATH, value)


def save_screen_size_to_setting_ini(value):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                         Config.INI_KEY_SCREEN_SIZE, value)


def save_login_size_to_setting_ini(value):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                         Config.INI_KEY_LOGIN_SIZE, value)


def set_unlock_revoke_in_ini(value):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                         Config.INI_KEY_UNLOCK_REVOKE, value)


def get_wechat_install_path_from_setting_ini():
    return ini_utils.get_setting_from_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                          Config.INI_KEY_INSTALL_PATH)


def get_wechat_data_path_from_setting_ini():
    return ini_utils.get_setting_from_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                          Config.INI_KEY_DATA_PATH)


def get_wechat_dll_dir_path_from_setting_ini():
    return ini_utils.get_setting_from_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                          Config.INI_KEY_DLL_DIR_PATH)


def get_screen_size_from_setting_ini():
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


def get_login_size_from_setting_ini():
    return ini_utils.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY_LOGIN_SIZE
    )


def get_unlock_revoke_from_ini():
    return ini_utils.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        Config.INI_SECTION,
        Config.INI_KEY_UNLOCK_REVOKE,
        default_value="false"
    )


def update_acc_details_to_acc_json(account, **kwargs) -> None:
    """更新账户信息到 JSON"""
    account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
    if account not in account_data:
        account_data[account] = {}
    # 遍历 kwargs 中的所有参数，并更新到 account_data 中
    for key, value in kwargs.items():
        account_data[account][key] = value
        print(f"更新[{account}][{key}]:{value}")
    json_utils.save_json_data(Config.ACC_DATA_JSON_PATH, account_data)


def get_acc_details_from_acc_json(account: str, **kwargs) -> Tuple[Any, ...]:
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
    print(f"└———")
    return result


def clear_all_wechat_in_acc_json():
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


def update_all_wechat_in_acc_json():
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
    update_acc_details_to_acc_json("all_wechat", **all_wechat)
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
    return True


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
            update_acc_details_to_acc_json(account, has_mutex=has_mutex)

    return True


# 更新手动模式的函数
def update_manual_time_statistic(sub_exe, time_spent):
    """更新手动登录统计数据到json"""
    if sub_exe.startswith("WeChatMultiple"):
        sub_exe = sub_exe.split('_', 1)[1].rsplit('.exe', 1)[0]

    data = json_utils.load_json_data(Config.STATISTIC_JSON_PATH)
    if "manual" not in data:
        data["manual"] = {}
    if sub_exe not in data["manual"]:
        data["manual"][sub_exe] = f"{math.inf},0,0,0"  # 初始化为“最短时间, (次数, 平均用时), 最长时间”

    # 获取当前最小、最大值，次数，平均用时
    current_min, count, avg_time, current_max = map(lambda x: float(x) if x != "null" else 0,
                                                    data["manual"][sub_exe].split(","))

    # 更新最小和最大值
    new_min = min(current_min or math.inf, time_spent)
    new_max = max(current_max or 0, time_spent)

    # 更新次数和平均用时
    new_count = count + 1
    new_avg_time = (avg_time * count + time_spent) / new_count

    data["manual"][sub_exe] = f"{new_min:.4f},{new_count},{new_avg_time:.4f},{new_max:.4f}"
    json_utils.save_json_data(Config.STATISTIC_JSON_PATH, data)


def update_auto_time_statistic(sub_exe, time_spent, index):
    """更新自动登录统计数据到json"""
    if sub_exe.startswith("WeChatMultiple"):
        sub_exe = sub_exe.split('_', 1)[1].rsplit('.exe', 1)[0]

    data = json_utils.load_json_data(Config.STATISTIC_JSON_PATH)
    if "auto" not in data:
        data["auto"] = {}
    if sub_exe not in data["auto"]:
        data["auto"][sub_exe] = {}

    # 检查该行是否存在
    if str(index) not in data["auto"][sub_exe]:
        data["auto"][sub_exe][str(index)] = f"{math.inf},0,0,0"  # 初始化为“最短时间, (次数, 平均用时), 最长时间”

    # 获取当前最小、最大值，次数，平均用时
    current_min, count, avg_time, current_max = map(lambda x: float(x) if x != "null" else 0,
                                                    data["auto"][sub_exe][str(index)].split(","))

    # 更新最小和最大值
    new_min = min(current_min or math.inf, time_spent)
    new_max = max(current_max or 0, time_spent)

    # 更新次数和平均用时
    new_count = count + 1
    new_avg_time = (avg_time * count + time_spent) / new_count

    data["auto"][sub_exe][str(index)] = f"{new_min:.4f},{new_count},{new_avg_time:.4f},{new_max:.4f}"
    json_utils.save_json_data(Config.STATISTIC_JSON_PATH, data)


def update_refresh_time_statistic(acc_count, time_spent):
    """更新刷新时间统计"""
    data = json_utils.load_json_data(Config.STATISTIC_JSON_PATH)
    if "refresh" not in data:
        data["refresh"] = {}
    if acc_count not in data["refresh"]:
        data["refresh"][acc_count] = f"{math.inf},0,0,0"  # 初始化为“最短时间, (次数, 平均用时), 最长时间”

    # 获取当前最小、最大值，次数，平均用时
    current_min, count, avg_time, current_max = map(lambda x: float(x) if x != "null" else 0,
                                                    data["refresh"][acc_count].split(","))

    # 更新最小和最大值
    new_min = min(current_min or math.inf, time_spent)
    new_max = max(current_max or 0, time_spent)

    # 更新次数和平均用时
    new_count = count + 1
    new_avg_time = (avg_time * count + time_spent) / new_count

    data["refresh"][acc_count] = f"{new_min:.4f},{new_count},{new_avg_time:.4f},{new_max:.4f}"
    json_utils.save_json_data(Config.STATISTIC_JSON_PATH, data)
