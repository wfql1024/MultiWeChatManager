import base64
import json
import math
import os
import re
import sys
from typing import Tuple, Any

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from resources import Config, Strings
from utils import json_utils, ini_utils, file_utils, image_utils
from utils.logger_utils import mylogger as logger


def decrypt_response(response_text):
    # 分割加密数据和密钥
    encrypted_data, key = response_text.rsplit(' ', 1)

    # 解码 Base64 数据
    encrypted_data = base64.b64decode(encrypted_data)
    aes_key = key.ljust(16)[:16].encode()  # 确保密钥长度

    # 提取 iv 和密文
    iv = encrypted_data[:16]
    ciphertext = encrypted_data[16:]

    # 解密
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)

    return plaintext.decode()


def save_sw_install_path_to_setting_ini(value, sw="WeChat"):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, sw,
                                         Config.INI_KEY_INSTALL_PATH, value)


def save_sw_data_dir_to_setting_ini(value, sw="WeChat"):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, sw,
                                         Config.INI_KEY_DATA_PATH, value)


def save_sw_dll_dir_to_setting_ini(value, sw="WeChat"):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, sw,
                                         Config.INI_KEY_DLL_DIR_PATH, value)


def save_screen_size_to_setting_ini(value):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_GLOBAL_SECTION,
                                         Config.INI_KEY_SCREEN_SIZE, value)


def save_sw_login_size_to_setting_ini(value, sw="WeChat"):
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, sw,
                                         Config.INI_KEY_LOGIN_SIZE, value)


def save_sw_sort_order_to_setting_ini(order, sw):
    col = order["login"]['col']
    asc = order["login"]['asc']
    ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, sw,
                                  Config.INI_KEY["login_sort"], f"{col},{asc}")
    col = order["logout"]['col']
    asc = order["logout"]['asc']
    ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, sw,
                                  Config.INI_KEY["logout_sort"], f"{col},{asc}")



def set_enable_new_func_in_ini():
    return ini_utils.save_setting_to_ini(Config.SETTING_INI_PATH, Config.INI_GLOBAL_SECTION,
                                         Config.INI_KEY["enable_new_func"], True)


def get_sw_install_path_from_setting_ini(sw="WeChat"):
    return [ini_utils.get_setting_from_ini(Config.SETTING_INI_PATH, sw,
                                           Config.INI_KEY_INSTALL_PATH)]


def get_sw_data_dir_from_setting_ini(sw="WeChat"):
    # print(sw)
    results = [ini_utils.get_setting_from_ini(Config.SETTING_INI_PATH, sw,
                                              Config.INI_KEY_DATA_PATH)]
    # print(results)
    return results


def get_sw_dll_dir_from_setting_ini(sw="WeChat"):
    return [ini_utils.get_setting_from_ini(Config.SETTING_INI_PATH, sw,
                                           Config.INI_KEY_DLL_DIR_PATH)]


def get_screen_size_from_setting_ini():
    result = ini_utils.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        Config.INI_GLOBAL_SECTION,
        Config.INI_KEY_SCREEN_SIZE
    )
    if not result or result == "":
        return None
    else:
        screen_width, screen_height = result.split('*')
        return int(screen_width), int(screen_height)


def get_sw_login_size_from_setting_ini(sw="WeChat"):
    return ini_utils.get_setting_from_ini(
        Config.SETTING_INI_PATH,
        sw,
        Config.INI_KEY['login_size']
    )


def update_acc_details_to_json_by_tab(tab, account, **kwargs):
    """更新账户信息到 JSON"""
    try:
        data = json_utils.load_json_data(Config.TAB_ACC_JSON_PATH)
        if tab not in data:
            data[tab] = {}
        tab_info = data.get(tab, {})
        if account not in tab_info:
            tab_info[account] = {}
        # 遍历 kwargs 中的所有参数，并更新到 account_data 中
        for key, value in kwargs.items():
            tab_info[account][key] = value
            # logger.info(f"在json更新[{account}][{key}]:{string_utils.clean_display_name(str(value))}")
        json_utils.save_json_data(Config.TAB_ACC_JSON_PATH, data)
        return True
    except Exception as e:
        logger.error(e)
        return False


def get_acc_details_from_json_by_tab(tab, account: str, **kwargs) -> Tuple[Any, ...]:
    """
    根据用户输入的变量名，获取对应的账户信息
    :param tab: 选择软件标签
    :param account: 账户名
    :param kwargs: 需要获取的变量名及其默认值（如 note="", nickname=None）
    :return: 包含所请求数据的元组
    """
    try:
        data = json_utils.load_json_data(Config.TAB_ACC_JSON_PATH)
        account_info = data.get(tab, {}).get(account, {})
        result = tuple()
        for key, default in kwargs.items():
            value = account_info.get(key, default)
            result += (value,)
            # logger.info(f"从json获取[{account}][{key}]：{string_utils.clean_display_name(str(value))}")
        return result
    except Exception as e:
        logger.error(e)
        return tuple()


def get_details_from_remote_setting_json(tab: str, **kwargs) -> Tuple[Any, ...]:
    """
    从远程设置json中获取数据
    :param tab: 选择的软件标签
    :param kwargs: 传入要获取的参数及其默认值
    :return:
    """
    try:
        data = json_utils.load_json_data(Config.REMOTE_SETTING_JSON_PATH)
        info = data.get(tab, {})
        result = tuple()
        for key, default in kwargs.items():
            value = info.get(key, default)
            result += (value,)
            # logger.info(f"从json获取[{account}][{key}]：{string_utils.clean_display_name(str(value))}")
        return result
    except Exception as e:
        logger.error(e)
        return tuple()


def clear_all_acc_in_acc_json(sw):
    """
    清空登录列表all_wechat结点中，适合登录之前使用
    :return: 是否成功
    """
    print("清理互斥体记录...")
    # 加载当前账户数据
    data = json_utils.load_json_data(Config.TAB_ACC_JSON_PATH)
    tab_info = data.get(sw, {})
    # 检查 all_acc 节点是否存在
    if "all_acc" in tab_info:
        # 清除 all_acc 中的所有字段
        tab_info["all_acc"].clear()
        # print(tab_info["all_acc"])
        print("all_acc 节点的所有字段已清空")

    # 保存更新后的数据
    json_utils.save_json_data(Config.TAB_ACC_JSON_PATH, data)
    return True

def clear_acc_info_of_sw(sw):
    """
    清空登录列表all_wechat结点中，适合登录之前使用
    :return: 是否成功
    """
    print("清理该平台账号记录...")
    # 加载当前账户数据
    data = json_utils.load_json_data(Config.TAB_ACC_JSON_PATH)
    tab_info = data.get(sw, {})
    # 检查 all_acc 节点是否存在
    tab_info.clear()
    # 保存更新后的数据
    json_utils.save_json_data(Config.TAB_ACC_JSON_PATH, data)
    return True


def update_all_acc_in_acc_json(tab):
    """
    清空后将json中所有已登录账号的情况加载到登录列表all_wechat结点中，适合登录之前使用
    :return: 是否成功
    """
    print("构建互斥体记录...")
    # 加载当前账户数据
    data = json_utils.load_json_data(Config.TAB_ACC_JSON_PATH)
    tab_info = data.get(tab, {})
    # 初始化 all_wechat 为空字典
    all_wechat = {}

    # 遍历所有的账户
    for account, details in tab_info.items():
        pid = details.get("pid")
        # 检查 pid 是否为整数
        if isinstance(pid, int):
            has_mutex = details.get("has_mutex", False)
            all_wechat[str(pid)] = has_mutex
            print(f"更新 {account} 的 has_mutex 为 {has_mutex}")

    # 更新 all_wechat 到 JSON 文件
    update_acc_details_to_json_by_tab(tab, "all_acc", **all_wechat)
    return True


def set_all_acc_values_to_false(tab):
    """
    将所有微信进程all_acc中都置为没有互斥体，适合每次成功打开一个登录窗口后使用
    （因为登录好一个窗口，说明之前所有的微信都没有互斥体了）
    :return: 是否成功
    """
    # 加载当前账户数据
    data = json_utils.load_json_data(Config.TAB_ACC_JSON_PATH)

    tab_info = data.get(tab, {})
    # 获取 all_acc 节点，如果不存在就创建一个空的
    all_acc = tab_info.get("all_acc", {})

    # 将所有字段的值设置为 False
    for pid in all_acc:
        all_acc[pid] = False

    # 保存更新后的数据
    json_utils.save_json_data(Config.TAB_ACC_JSON_PATH, data)
    return True


def update_has_mutex_from_all_acc(tab):
    """
    将json中登录列表all_wechat结点中的情况加载回所有已登录账号，适合刷新结束时使用
    :return: 是否成功
    """
    mutex = False
    data = json_utils.load_json_data(Config.TAB_ACC_JSON_PATH)
    if tab not in data:
        data[tab] = {}
    tab_info = data.get(tab, {})
    if "all_acc" not in tab_info:
        tab_info["all_acc"] = {}
    for account, details in tab_info.items():
        if account == "all_acc":
            continue
        pid = details.get("pid", None)
        if pid and pid is not None:
            has_mutex = tab_info["all_acc"].get(f"{pid}", True)
            if has_mutex is True:
                mutex = True
            update_acc_details_to_json_by_tab(tab, account, has_mutex=has_mutex)
    return True, mutex


# 更新手动模式的函数
def update_manual_time_statistic(sub_exe, time_spent, tab):
    """更新手动登录统计数据到json"""
    if sub_exe.startswith(f"{tab}Multiple"):
        sub_exe = sub_exe.split('_', 1)[1].rsplit('.exe', 1)[0]

    data = json_utils.load_json_data(Config.STATISTIC_JSON_PATH)
    if tab not in data:
        data[tab] = {}
    tab_info = data.get(tab, {})
    if "manual" not in tab_info:
        tab_info["manual"] = {}
    if sub_exe not in tab_info["manual"]:
        tab_info["manual"][sub_exe] = f"{math.inf},0,0,0"  # 初始化为“最短时间, (次数, 平均用时), 最长时间”

    # 获取当前最小、最大值，次数，平均用时
    current_min, count, avg_time, current_max = map(lambda x: float(x) if x != "null" else 0,
                                                    tab_info["manual"][sub_exe].split(","))

    # 更新最小和最大值
    new_min = min(current_min or math.inf, time_spent)
    new_max = max(current_max or 0, time_spent)

    # 更新次数和平均用时
    new_count = count + 1
    new_avg_time = (avg_time * count + time_spent) / new_count

    tab_info["manual"][sub_exe] = f"{new_min:.4f},{new_count},{new_avg_time:.4f},{new_max:.4f}"
    json_utils.save_json_data(Config.STATISTIC_JSON_PATH, data)


def update_auto_time_statistic(sub_exe, time_spent, index, tab="WeChat"):
    """更新自动登录统计数据到json"""
    print("更新自动登录统计数据到json")
    if sub_exe.startswith(f"{tab}Multiple"):
        sub_exe = sub_exe.split('_', 1)[1].rsplit('.exe', 1)[0]

    data = json_utils.load_json_data(Config.STATISTIC_JSON_PATH)
    if tab not in data:
        data[tab] = {}
    tab_info = data.get(tab, {})
    if "auto" not in tab_info:
        tab_info["auto"] = {}
    if sub_exe not in tab_info["auto"]:
        tab_info["auto"][sub_exe] = {}

    # 检查该行是否存在
    if str(index) not in tab_info["auto"][sub_exe]:
        tab_info["auto"][sub_exe][str(index)] = f"{math.inf},0,0,0"  # 初始化为“最短时间, (次数, 平均用时), 最长时间”

    # 获取当前最小、最大值，次数，平均用时
    current_min, count, avg_time, current_max = map(lambda x: float(x) if x != "null" else 0,
                                                    tab_info["auto"][sub_exe][str(index)].split(","))

    # 更新最小和最大值
    new_min = min(current_min or math.inf, time_spent)
    new_max = max(current_max or 0, time_spent)

    # 更新次数和平均用时
    new_count = count + 1
    new_avg_time = (avg_time * count + time_spent) / new_count

    tab_info["auto"][sub_exe][str(index)] = f"{new_min:.4f},{new_count},{new_avg_time:.4f},{new_max:.4f}"
    # print(tab_info)
    json_utils.save_json_data(Config.STATISTIC_JSON_PATH, data)


def update_refresh_time_statistic(view, acc_count, time_spent, tab="WeChat"):
    """更新刷新时间统计"""
    if time_spent > 2:
        return
    data = json_utils.load_json_data(Config.STATISTIC_JSON_PATH)
    if tab not in data:
        data[tab] = {}
    tab_info = data.get(tab, {})
    if "refresh" not in tab_info:
        tab_info["refresh"] = {}
    if view not in tab_info["refresh"]:
        tab_info["refresh"][view] = {}
    if acc_count not in tab_info["refresh"][view]:
        tab_info["refresh"][view][acc_count] = f"{math.inf},0,0,0"  # 初始化为“最短时间, (次数, 平均用时), 最长时间”

    # 获取当前最小、最大值，次数，平均用时
    current_min, count, avg_time, current_max = map(lambda x: float(x) if x != "null" else 0,
                                                    tab_info["refresh"][view][acc_count].split(","))

    # 更新最小和最大值
    new_min = min(current_min or math.inf, time_spent)
    new_max = max(current_max or 0, time_spent)

    # 更新次数和平均用时
    new_count = count + 1
    new_avg_time = (avg_time * count + time_spent) / new_count

    tab_info["refresh"][view][acc_count] = f"{new_min:.4f},{new_count},{new_avg_time:.4f},{new_max:.4f}"
    json_utils.save_json_data(Config.STATISTIC_JSON_PATH, data)

def try_get_local_cfg():
    """
    尝试从本地获取配置数据，优先从本地获取，成功后停止；失败会从网络下载远程配置
    :return:
    """
    if not (os.path.exists(Config.REMOTE_SETTING_JSON_PATH)
            and file_utils.is_latest_file_by_day(Config.REMOTE_SETTING_JSON_PATH)):
        config_data = force_fetch_remote_encrypted_cfg()
    else:
        # print("本地版本对照表存在，读取中...")
        try:
            with open(Config.REMOTE_SETTING_JSON_PATH, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except Exception as e:
            print(f"错误：读取本地 JSON 文件失败: {e}，尝试从云端下载")
            config_data = force_fetch_remote_encrypted_cfg()
            print(f"从云端下载了文件：{config_data}")
            raise RuntimeError("本地 JSON 文件读取失败")
    return config_data

def force_fetch_remote_encrypted_cfg():
    """尝试从多个源获取配置数据，优先从 GITEE 获取，成功后停止"""
    print(f"正从远程源下载...")
    urls = [Strings.REMOTE_SETTING_JSON_GITEE, Strings.REMOTE_SETTING_JSON_GITHUB]

    for url in urls:
        print(f"正在尝试从此处下载: {url}...")
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                with open(Config.REMOTE_SETTING_JSON_PATH, 'w', encoding='utf-8') as config_file:
                    decrypted_data = decrypt_response(response.text)
                    config_file.write(decrypted_data)  # 将下载的 JSON 保存到文件
                print(f"成功从 {url} 获取并保存 JSON 文件")
                return json.loads(decrypted_data)  # 返回加载的 JSON 数据
            else:
                print(f"获取失败: {response.status_code}，尝试下一个源...")
        except requests.exceptions.Timeout:
            logger.warning(f"请求 {url} 超时，尝试下一个源...")
        except Exception as e:
            logger.error(f"从 {url} 获取时发生错误: {e}，尝试下一个源...")

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


def get_avatar_url_from_file(sw, acc_list, data_dir):
    changed = False

    for acc in acc_list:
        acc_info_dat_path = os.path.join(data_dir, acc, 'config', 'AccInfo.dat')
        # print(acc_info_dat_path)
        if not os.path.isfile(acc_info_dat_path):
            continue
        with open(acc_info_dat_path, 'r', encoding="utf-8", errors="ignore") as f:
            acc_info = f.read()
        # 获取文件内容，去掉多余的换行符
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
            avatar_path = os.path.join(Config.PROJ_USER_PATH, sw, f"{acc}", f"{acc}.jpg")
            logger.info(f"{acc}: {matched_url}")
            success = image_utils.download_image(matched_url, avatar_path)
            if success is True:
                update_acc_details_to_json_by_tab(sw, acc, avatar_url=matched_url)
                changed = True
    return changed


def get_avatar_url_from_other_sw(now_sw, now_acc_list):
    print("尝试用窃取法获取头像")
    changed = False
    all_sw, = get_details_from_remote_setting_json("global", all_sw=None)
    print(all_sw)

    # 对所有其他软件进行遍历
    for other_sw in all_sw:
        print(other_sw, now_sw)
        # 平台相同，跳过
        if other_sw == now_sw:
            continue

        other_sw_cut, = get_details_from_remote_setting_json(
            other_sw, cut_to_compatible_id=None)
        if other_sw_cut is None:
            # 没有适配，跳过
            logger.warning(f"没有{other_sw}对应的适配")
            continue
        other_sw_left_cut = other_sw_cut[0]
        other_sw_right_cut = (-other_sw_cut[1]) if other_sw_cut[1] != 0 else None
        # print(other_sw_left_cut, other_sw_right_cut)

        now_sw_cut, = get_details_from_remote_setting_json(
            now_sw, cut_to_compatible_id=None)
        if now_sw_cut is None:
            # 没有适配，跳过
            logger.warning(f"没有{other_sw}对应的适配")
            continue
        now_sw_left_cut = now_sw_cut[0]
        now_sw_right_cut = (-now_sw_cut[1]) if now_sw_cut[1] != 0 else None
        # print(now_sw_left_cut, now_sw_right_cut)

        # 加载其他平台的账号列表
        data = json_utils.load_json_data(Config.TAB_ACC_JSON_PATH)
        other_acc_list = data.get(other_sw, {})
        for now_acc in now_acc_list:
            # 对账号进行裁剪
            now_sw_been_cut_acc = now_acc[now_sw_left_cut:now_sw_right_cut]

            # 遍历其他平台的账号
            for other_acc in other_acc_list:
                # 对账号进行裁剪
                other_sw_been_cut_acc = other_acc[other_sw_left_cut:other_sw_right_cut]
                # print(item)

                # 裁剪后是一致的账号，才进行后续操作
                if now_sw_been_cut_acc == other_sw_been_cut_acc:
                    # 分别获取两个平台的头像url
                    now_sw_avatar_url, = get_acc_details_from_json_by_tab(now_sw, now_acc, avatar_url=None)
                    other_sw_avatar_url, = get_acc_details_from_json_by_tab(other_sw, other_acc, avatar_url=None)
                    if other_sw_avatar_url is not None and now_sw_avatar_url is None:
                        # 只有当前平台没有头像url，且另一个平台有头像url，则进行偷取和下载
                        avatar_path = os.path.join(Config.PROJ_USER_PATH, now_sw, f"{now_acc}", f"{now_acc}.jpg")
                        logger.info(f"{now_acc}: {other_sw_avatar_url}")
                        success = image_utils.download_image(other_sw_avatar_url, avatar_path)
                        if success is True:
                            update_acc_details_to_json_by_tab(now_sw, now_acc, avatar_url=other_sw_avatar_url)
                            changed = True
    return changed


def get_nickname_from_file(sw, acc_list, data_dir):
    changed = False
    for acc in acc_list:
        acc_info_dat_path = os.path.join(data_dir, acc, 'config', 'AccInfo.dat')
        if not os.path.isfile(acc_info_dat_path):
            continue
        with open(acc_info_dat_path, 'r', encoding="utf-8", errors="ignore") as f:
            acc_info = f.read()
        # 获取文件
        str_line = ''.join(acc_info.strip().splitlines())
        # print(f"最后四行：{str_line}")
        nickname_str_pattern = rf'{acc}(.*?)https://'
        match = re.search(nickname_str_pattern, str_line)
        if match:
            matched_str = match.group(1)
            cleaned_str = re.sub(r'[0-9a-fA-F]{32}.*', '', matched_str)
            cleaned_str = re.sub(r'\x1A.*?\x12', '', cleaned_str)
            cleaned_str = re.sub(r'[^\x20-\x7E\xC0-\xFF\u4e00-\u9fa5]+', '', cleaned_str)
            success = update_acc_details_to_json_by_tab(sw, acc, nickname=cleaned_str)
            if success is True:
                changed = True
    return changed


def get_nickname_from_other_sw(now_sw, now_acc_list):
    print("尝试用窃取法获取昵称")
    changed = False
    all_sw, = get_details_from_remote_setting_json("global", all_sw=None)
    print(all_sw)

    # 对所有其他软件进行遍历
    for other_sw in all_sw:
        print(other_sw, now_sw)
        # 平台相同，跳过
        if other_sw == now_sw:
            continue

        other_sw_cut, = get_details_from_remote_setting_json(
            other_sw, cut_to_compatible_id=None)
        if other_sw_cut is None:
            # 没有适配，跳过
            logger.warning(f"没有{other_sw}对应的适配")
            continue
        other_sw_left_cut = other_sw_cut[0]
        other_sw_right_cut = (-other_sw_cut[1]) if other_sw_cut[1] != 0 else None
        # print(other_sw_left_cut, other_sw_right_cut)

        now_sw_cut, = get_details_from_remote_setting_json(
            now_sw, cut_to_compatible_id=None)
        if now_sw_cut is None:
            # 没有适配，跳过
            logger.warning(f"没有{other_sw}对应的适配")
            continue
        now_sw_left_cut = now_sw_cut[0]
        now_sw_right_cut = (-now_sw_cut[1]) if now_sw_cut[1] != 0 else None
        # print(now_sw_left_cut, now_sw_right_cut)

        # 加载其他平台的账号列表
        data = json_utils.load_json_data(Config.TAB_ACC_JSON_PATH)
        other_acc_list = data.get(other_sw, {})
        for now_acc in now_acc_list:
            # 对账号进行裁剪
            now_sw_been_cut_acc = now_acc[now_sw_left_cut:now_sw_right_cut]

            # 遍历其他平台的账号
            for other_acc in other_acc_list:
                # 对账号进行裁剪
                other_sw_been_cut_acc = other_acc[other_sw_left_cut:other_sw_right_cut]
                # print(item)

                # 裁剪后是一致的账号，才进行后续操作
                if now_sw_been_cut_acc == other_sw_been_cut_acc:
                    # 分别获取两个平台的昵称
                    now_sw_nickname, = get_acc_details_from_json_by_tab(now_sw, now_acc, nickname=None)
                    other_sw_nickname, = get_acc_details_from_json_by_tab(other_sw, other_acc, nickname=None)
                    if other_sw_nickname is not None and now_sw_nickname is None:
                        # 只有当前平台没有昵称，且另一个平台有昵称，则进行偷取和上传
                        update_acc_details_to_json_by_tab(now_sw, now_acc, nickname=other_sw_nickname)
                        changed = True
    return changed


def get_curr_wx_id_from_config_file(data_dir, sw):
    config_path_suffix, config_files = get_details_from_remote_setting_json(
        sw, config_path_suffix=None, config_file_list=None)
    if len(config_files) == 0 or config_files is None:
        return None
    file = config_files[0]
    config_data_path = os.path.join(str(data_dir), str(config_path_suffix), str(file)).replace("\\", "/")
    if os.path.isfile(config_data_path):
        with open(config_data_path, 'r', encoding="utf-8", errors="ignore") as f:
            acc_info = f.read()
        # 获取文件中的最后四行
        str_line = ''.join(acc_info.strip().splitlines())
        wxid_pattern = r'wxid_[a-zA-Z0-9_]+\\config'
        match = re.search(wxid_pattern, str_line)
        if match:
            # 提取 wxid_……
            matched_str = match.group(0)
            wx_id = matched_str.split("\\")[0]  # 获取 wxid_...... 部分
            return wx_id
    else:
        return None


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

        # 将当前节点合并到 tree
        if isinstance(value, str):  # 如果是字符串
            refresh_data["tree"][key] = value
        elif isinstance(value, dict):  # 如果是字典
            refresh_data["tree"].update(value)

        # 删除原始节点
        del refresh_data[key]
    json_utils.save_json_data(Config.STATISTIC_JSON_PATH, data)
    return data


def move_data_to_wechat():
    data = json_utils.load_json_data(Config.STATISTIC_JSON_PATH)

    # 检查是否已有 "WeChat" 节点
    if "WeChat" not in data:
        wechat_data = {
            "WeChat": data
        }
        json_utils.save_json_data(Config.STATISTIC_JSON_PATH, wechat_data)
