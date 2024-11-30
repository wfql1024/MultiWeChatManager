import json
import math
import os
import re
import sys
from typing import Tuple, Any

import requests

from resources import Config, Strings
from utils import json_utils, ini_utils, file_utils, image_utils
from utils.logger_utils import mylogger as logger


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


def save_sort_order_to_setting_ini(order):
    col, asc = order["login"]
    ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                  Config.INI_KEY["login_col_to_sort"], col)
    ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                  Config.INI_KEY["login_sort_asc"], asc)
    col, asc = order["logout"]
    ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                  Config.INI_KEY["logout_col_to_sort"], col)
    ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                  Config.INI_KEY["logout_sort_asc"], asc)


def set_enable_new_func_in_ini(value):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                         Config.INI_KEY["enable_new_func"], value)


def get_wechat_install_path_from_setting_ini():
    return ini_utils.get_setting_from_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                          Config.INI_KEY_INSTALL_PATH)


def get_wechat_data_dir_from_setting_ini():
    return ini_utils.get_setting_from_ini(Config.SETTING_INI_PATH, Config.INI_SECTION,
                                          Config.INI_KEY_DATA_PATH)


def get_wechat_dll_dir_from_setting_ini():
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


def update_acc_details_to_acc_json(account, **kwargs):
    """更新账户信息到 JSON"""
    try:
        account_data = json_utils.load_json_data(Config.ACC_DATA_JSON_PATH)
        if account not in account_data:
            account_data[account] = {}
        # 遍历 kwargs 中的所有参数，并更新到 account_data 中
        for key, value in kwargs.items():
            account_data[account][key] = value
            # logger.info(f"在json更新[{account}][{key}]:{string_utils.clean_display_name(str(value))}")
        json_utils.save_json_data(Config.ACC_DATA_JSON_PATH, account_data)
        return True
    except Exception as e:
        logger.error(e)
        return False


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
        value = account_info.get(key, default)
        result += (value,)
        # logger.info(f"从json获取[{account}][{key}]：{string_utils.clean_display_name(str(value))}")
    return result


def clear_all_wechat_in_acc_json():
    """
    清空登录列表all_wechat结点中，适合登录之前使用
    :return: 是否成功
    """
    print("清理互斥体记录...")
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
    print("构建互斥体记录...")
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


def update_refresh_time_statistic(view, acc_count, time_spent):
    """更新刷新时间统计"""
    if time_spent > 2:
        return
    data = json_utils.load_json_data(Config.STATISTIC_JSON_PATH)
    if "refresh" not in data:
        data["refresh"] = {}
    if view not in data["refresh"]:
        data["refresh"][view] = {}
    if acc_count not in data["refresh"][view]:
        data["refresh"][view][acc_count] = f"{math.inf},0,0,0"  # 初始化为“最短时间, (次数, 平均用时), 最长时间”

    # 获取当前最小、最大值，次数，平均用时
    current_min, count, avg_time, current_max = map(lambda x: float(x) if x != "null" else 0,
                                                    data["refresh"][view][acc_count].split(","))

    # 更新最小和最大值
    new_min = min(current_min or math.inf, time_spent)
    new_max = max(current_max or 0, time_spent)

    # 更新次数和平均用时
    new_count = count + 1
    new_avg_time = (avg_time * count + time_spent) / new_count

    data["refresh"][view][acc_count] = f"{new_min:.4f},{new_count},{new_avg_time:.4f},{new_max:.4f}"
    json_utils.save_json_data(Config.STATISTIC_JSON_PATH, data)


def fetch_config_data_from_remote():
    """尝试从多个源获取配置数据，优先从 GITEE 获取，成功后停止"""
    print(f"正从远程源下载...")
    urls = [Strings.VER_ADAPTATION_JSON_GITEE, Strings.VER_ADAPTATION_JSON_GITHUB]

    for url in urls:
        print(f"正在尝试从此处下载: {url}...")
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                with open(Config.VER_ADAPTATION_JSON_PATH, 'w', encoding='utf-8') as config_file:
                    config_file.write(response.text)  # 将下载的 JSON 保存到文件
                print(f"成功从 {url} 获取并保存 JSON 文件")
                return json.loads(response.text)  # 返回加载的 JSON 数据
            else:
                print(f"获取失败: {response.status_code}，尝试下一个源...")
        except requests.exceptions.Timeout:
            print(f"请求 {url} 超时，尝试下一个源...")
        except Exception as e:
            print(f"从 {url} 获取时发生错误: {e}，尝试下一个源...")

    raise RuntimeError("所有源获取配置数据失败")


def get_app_current_version():
    # 获取版本号
    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
        version_number = file_utils.get_file_version(exe_path)  # 获取当前执行文件的版本信息
    else:
        with open(Config.VERSION_FILE, 'r', encoding='utf-8') as version_file:
            version_info = version_file.read()
            # 使用正则表达式提取文件版本
            match = re.search(r'filevers=\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', version_info)
            if match:
                version_number = '.'.join([match.group(1), match.group(2), match.group(3), match.group(4)])
            else:
                version_number = "未知版本"

    return f"v{version_number}-{Config.VER_STATUS}"


def get_avatar_url_from_acc_info_file(acc_list, data_dir):
    changed = False
    for acc in acc_list:
        acc_info_dat_path = os.path.join(data_dir, acc, 'config', 'AccInfo.dat')
        print(acc_info_dat_path)
        if not os.path.isfile(acc_info_dat_path):
            continue
        with open(acc_info_dat_path, 'r', encoding="utf-8", errors="ignore") as f:
            acc_info = f.read()
        # 获取文件中的最后三行
        info_line = '\n'.join(acc_info.strip().splitlines())
        # 定义正则表达式来匹配 https 开头并以 /0 或 /132 结尾的 URL
        url_patterns = [r'https://[^\s]*?/0', r'https://[^\s]*?/132']
        # 使用正则表达式查找匹配的 URL
        matched_url = None
        for p in url_patterns:
            match = re.search(p, info_line)
            if match:
                matched_url = match.group(0)  # 获取匹配的 URL
                # logger.info("Found URL:", matched_url)
                break
            else:
                # logger.warning("No matching URL found.")
                pass
        if matched_url and matched_url.endswith('/132'):
            matched_url = matched_url.rstrip('/132') + '/0'
        if matched_url:
            avatar_path = os.path.join(Config.PROJ_USER_PATH, f"{acc}", f"{acc}.jpg")
            logger.info(f"{acc}: {matched_url}")
            success = image_utils.download_image(matched_url, avatar_path)
            if success is True:
                update_acc_details_to_acc_json(acc, avatar_url=matched_url)
                changed = True
    return changed



def get_nickname_from_acc_info_file(acc_list, data_dir):
    changed = False
    for acc in acc_list:
        acc_info_dat_path = os.path.join(data_dir, acc, 'config', 'AccInfo.dat')
        if not os.path.isfile(acc_info_dat_path):
            continue
        with open(acc_info_dat_path, 'r', encoding="utf-8", errors="ignore") as f:
            acc_info = f.read()
        # 获取文件中的最后四行
        str_line = ''.join(acc_info.strip().splitlines())
        # print(f"最后四行：{str_line}")
        nickname_str_pattern = rf'{acc}(.*?)https://'
        match = re.search(nickname_str_pattern, str_line)
        if match:
            matched_str = match.group(1)
            cleaned_str = re.sub(r'[0-9a-fA-F]{32}.*', '', matched_str)
            cleaned_str = re.sub(r'\x1A.*?\x12', '', cleaned_str)
            cleaned_str = re.sub(r'[^\x20-\x7E\xC0-\xFF\u4e00-\u9fa5]+', '', cleaned_str)
            success = update_acc_details_to_acc_json(acc, nickname=cleaned_str)
            if success is True:
                changed = True
    return changed



def get_curr_wx_id_from_config_file(data_dir):
    config_data_path = os.path.join(data_dir, 'All Users', 'config', 'config.data')
    with open(config_data_path, 'r', encoding="utf-8", errors="ignore") as f:
        acc_info = f.read()
    # 获取文件中的最后四行
    str_line = ''.join(acc_info.strip().splitlines()[-4:])
    wxid_pattern = r'wxid_[a-zA-Z0-9_]+\\config'
    match = re.search(wxid_pattern, str_line)
    if match:
        # 提取 wxid_……
        matched_str = match.group(0)
        wx_id = matched_str.split("\\")[0]  # 获取 wxid_...... 部分
        return wx_id


def get_file_with_correct_md5(folders, md5s):
    for folder in folders:
        for root, _, files in os.walk(folder):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                try:
                    file_md5 = file_utils.calculate_md5(file_path)
                    # 检查 MD5 是否匹配正确的 MD5 列表
                    if file_md5 in md5s:
                        return file_path  # 返回匹配的文件路径
                except Exception as e:
                    logger.error(e)
    return None  # 如果没有找到匹配项则返回 None


def merge_refresh_nodes():
    data = json_utils.load_json_data(Config.STATISTIC_JSON_PATH)
    # 确保 refresh 节点存在
    if "refresh" not in data or not isinstance(data["refresh"], dict):
        return data

    refresh_data = data["refresh"]

    # 初始化 classic 和 tree，如果不存在则创建
    refresh_data.setdefault("classic", {})
    refresh_data.setdefault("tree", {})

    # 遍历 refresh 中的所有节点
    for key, value in list(refresh_data.items()):
        # 跳过 classic 和 tree 节点
        if key in ("classic", "tree"):
            continue

        # 将当前节点合并到 classic
        if isinstance(value, str):  # 如果是字符串
            refresh_data["classic"][key] = value
        elif isinstance(value, dict):  # 如果是字典
            refresh_data["classic"].update(value)

        # 将当前节s点合并到 tree
        if isinstance(value, str):  # 如果是字符串
            refresh_data["tree"][key] = value
        elif isinstance(value, dict):  # 如果是字典
            refresh_data["tree"].update(value)

        # 删除原始节点
        del refresh_data[key]
    json_utils.save_json_data(Config.STATISTIC_JSON_PATH, data)
    return data
