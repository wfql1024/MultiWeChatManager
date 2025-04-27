import base64
import datetime as dt
import json
import math
import os
import re
import subprocess
import sys
import time
from typing import *

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from public_class.enums import LocalCfg, AccKeys
from resources import Config, Strings
from utils import file_utils, image_utils, sys_utils
from utils.file_utils import IniUtils, JsonUtils, DictUtils
from utils.logger_utils import mylogger as logger

"""获取远程配置，此配置只读，不提供修改方法"""


def force_fetch_remote_encrypted_cfg(url=None):
    """强制从网络中获取最新的配置文件"""

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

    print(f"正从远程源下载...")
    urls = [Strings.REMOTE_SETTING_JSON_GITEE, Strings.REMOTE_SETTING_JSON_GITHUB]

    if url is not None:
        urls = [url].extend(urls)

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

    return None


def try_read_remote_cfg_locally():
    """
    尝试从本地读取配置数据，优先从本地获取，成功后停止；失败会从网络下载远程配置
    :return: 是否成功；数据
    """
    config_data = None
    try:
        with open(Config.REMOTE_SETTING_JSON_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except Exception as e:
        logger.error(f"错误：读取本地 JSON 文件失败: {e}，尝试从云端下载")
        try:
            config_data = force_fetch_remote_encrypted_cfg()
            logger.info(f"成功从云端下载了配置文件!")
        except Exception as e:
            logger.error(f"错误：从云端下载 JSON 文件失败: {e}")
    return config_data


def read_remote_cfg_in_rules():
    """
    有策略地获取远程配置：
        检查是否到了需要强制更新的日期，
        如果是，则强制从网络获取，失败则使用本地，成功则将日期往后推；
        如果不是，则从本地获取。
    :return:
    """
    # 获取存储的日期
    next_check_time_str = fetch_global_setting_or_set_default_or_none("next_check_time")
    if next_check_time_str is None:
        next_check_time = dt.datetime.today().date()
        today = dt.datetime.today().date()
    else:
        # 将字符串日期解析为日期对象
        next_check_time = dt.datetime.strptime(next_check_time_str, "%Y-%m-%d").date()
        today = dt.datetime.today().date()
    # 如果今天的日期大于等于 next_check_time，执行代码并更新 next_check_time
    if today >= next_check_time:
        # 强制获取远程配置
        config_data = force_fetch_remote_encrypted_cfg()
        if config_data is not None:
            # 更新 next_check_time 为明天
            next_check_time = today + dt.timedelta(days=1)
            next_check_time_str = next_check_time.strftime("%Y-%m-%d")
            save_a_global_setting("next_check_time", next_check_time_str)
            return config_data
        else:
            # 失败加载本地
            return try_read_remote_cfg_locally()
    else:
        # 不到时间直接加载本地
        return try_read_remote_cfg_locally()


def load_remote_cfg():
    """
    加载远程配置
    :return:
    """
    data = JsonUtils.load_json(Config.REMOTE_SETTING_JSON_PATH)
    return data


def get_details_from_remote_setting_json(*pre_nodes: str, **kwargs) -> Tuple[Any, ...]:
    """
    从远程设置json中获取数据
    :param pre_nodes: 选择的软件标签
    :param kwargs: 传入要获取的参数及其默认值
    :return:
    """
    try:
        data = load_remote_cfg()
        return DictUtils.get_nested_values(data, None, *pre_nodes, **kwargs)
    except Exception as e:
        logger.error(e)
        return tuple()


"""本地设置"""


def load_setting():
    """
    加载设置
    :return:
    """
    data = IniUtils.load_ini_as_dict(Config.SETTING_INI_PATH)
    return data


def save_setting(data):
    """
    保存设置
    :return:
    """
    return IniUtils.save_ini_from_dict(Config.SETTING_INI_PATH, data)


def clear_some_setting(*addr) -> bool:
    """
    清空某平台的账号记录，在对平台重新设置后触发
    :return: 是否成功
    """
    try:
        print(f"清理{addr}处数据...")
        data = load_setting()
        DictUtils.clear_nested_values(data, *addr)
        save_setting(data)
        return True
    except Exception as e:
        logger.error(e)
        return False


def update_settings(*front_addr, **kwargs) -> bool:
    """更新账户信息到 JSON"""
    try:
        data = load_setting()
        success = DictUtils.set_nested_values(data, None, *front_addr, **kwargs)
        save_setting(data)
        return success
    except Exception as e:
        logger.error(e)
        return False


def get_settings(*front_addr, **kwargs) -> Union[Dict, Tuple[Any, ...]]:
    """
    根据用户输入的变量名，获取对应的账户信息
    :param front_addr: 前置地址，如：("wechat", "account1")
    :param kwargs: 需要获取的键地址及其默认值（如 note="", nickname=None）
    :return: 包含所请求数据的元组
    """
    try:
        data = load_setting()
        return DictUtils.get_nested_values(data, None, *front_addr, **kwargs)
    except Exception as e:
        logger.error(e)
        return tuple()


def save_a_setting_and_callback(section, key, value, callback=None):
    """
    保存设置并回调
    :param section: 配置文件中的section
    :param key: 配置文件中的key
    :param value: 配置文件中的value
    :param callback: 回调函数
    :return:
    """
    try:
        changed = False
        data = load_setting()
        origin_value = DictUtils.get_nested_values(data, None, section, key)
        DictUtils.set_nested_values(data, value, section, key)
        save_setting(data)

        data = load_setting()
        new_value = DictUtils.get_nested_values(data, None, section, key)

        if callback is not None:
            callback()
        if new_value != origin_value:
            print(f"成功修改{section}的{key}为{value}！")
            changed = True
        else:
            print(f"一致的值：{section}的{key}为{value}！")
        return changed
    except Exception as e:
        logger.error(e)
        return False


def save_a_global_setting(key, value, callback=None):
    return save_a_setting_and_callback(LocalCfg.GLOBAL_SECTION, key, value, callback)


def fetch_global_setting_or_set_default_or_none(setting_key):
    """
    获取配置项，若没有则添加默认，若没有默认则返回None
    :return: 已选择的子程序
    """
    return fetch_sw_setting_or_set_default_or_none(LocalCfg.GLOBAL_SECTION, setting_key)


def fetch_sw_setting_or_set_default_or_none(sw, setting_key):
    """
    获取配置项，若没有则设置默认值，若没有默认值则返回None
    :return: 已选择的子程序
    """
    data = load_setting()
    value = DictUtils.get_nested_values(data, None, sw, setting_key)
    if not value or value == "" or value == "None" or value == "none":
        try:
            value = Config.INI_DEFAULT_VALUE[sw][setting_key]
            DictUtils.set_nested_values(data, value, sw, setting_key)
        except KeyError:
            return None
    return value


"""账号数据相关，该文件记录账号及登录时期的互斥体情况"""


def load_acc_data() -> dict:
    """
    加载账号数据，请在这个方法中修改账号数据的加载方式，如格式、文件位置
    :return: 账号数据字典
    """
    data = JsonUtils.load_json(Config.TAB_ACC_JSON_PATH)
    return data


def save_acc_data(data) -> bool:
    """
    保存账号数据，请在这个方法中修改账号数据的保存方式，如格式、文件位置
    :param data: 账号数据字典
    """
    return JsonUtils.save_json(Config.TAB_ACC_JSON_PATH, data)


def clear_some_acc_data(*addr) -> bool:
    """
    清空某平台的账号记录，在对平台重新设置后触发
    :return: 是否成功
    """
    try:
        print(f"清理{addr}处数据...")
        data = load_acc_data()
        DictUtils.clear_nested_values(data, *addr)
        save_acc_data(data)
        return True
    except Exception as e:
        logger.error(e)
        return False


def update_sw_acc_data(*front_addr, **kwargs) -> bool:
    """更新账户信息到 JSON"""
    try:
        data = load_acc_data()
        success = DictUtils.set_nested_values(data, None, *front_addr, **kwargs)
        save_acc_data(data)
        return success
    except Exception as e:
        logger.error(e)
        return False


def get_sw_acc_data(*front_addr, **kwargs) -> Union[Dict, Tuple[Any, ...]]:
    """
    根据用户输入的变量名，获取对应的账户信息
    :param front_addr: 前置地址，如：("wechat", "account1")
    :param kwargs: 需要获取的键地址及其默认值（如 note="", nickname=None）
    :return: 包含所请求数据的元组
    """
    try:
        data = load_acc_data()
        return DictUtils.get_nested_values(data, None, *front_addr, **kwargs)
    except Exception as e:
        logger.error(e)
        return tuple()


"""账号互斥体相关"""


def update_all_acc_in_acc_json(sw):
    """
    清空后将json中所有已登录账号的情况加载到登录列表all_wechat结点中，适合登录之前使用
    :return: 是否成功
    """
    print("构建互斥体记录...")
    # 加载当前账户数据
    sw_data = get_sw_acc_data(sw)
    if sw_data is None:
        return False

    pid_mutex = {}
    # 遍历所有的账户，从有pid的账户中获取pid和has_mutex，并存入pid_mutex
    for account, details in sw_data.items():
        if isinstance(details, dict):
            pid = details.get(AccKeys.PID)
            # 检查 pid 是否为整数
            if isinstance(pid, int):
                has_mutex = details.get(AccKeys.HAS_MUTEX, False)
                pid_mutex[str(pid)] = has_mutex
                print(f"更新 {account} 的 has_mutex 为 {has_mutex}")
    update_sw_acc_data(sw, AccKeys.PID_MUTEX, **pid_mutex)
    return True


def set_all_acc_values_to_false(sw):
    """
    将所有微信进程all_acc中都置为没有互斥体，适合每次成功打开一个登录窗口后使用
    （因为登录好一个窗口，说明之前所有的微信都没有互斥体了）
    :return: 是否成功
    """
    # 加载当前账户数据
    pid_mutex_data = get_sw_acc_data(sw, AccKeys.PID_MUTEX)
    if pid_mutex_data is None:
        return False

    # 将所有字段的值设置为 False
    for pid in pid_mutex_data:
        update_sw_acc_data(sw, AccKeys.PID_MUTEX, **{pid: False})
    return True


def update_has_mutex_from_all_acc(sw):
    """
    将json中登录列表all_wechat结点中的情况加载回所有已登录账号，适合刷新结束时使用
    :return: 是否成功
    """
    has_mutex = False
    sw_data = get_sw_acc_data(sw)
    if sw_data is None:
        return False, has_mutex
    pid_mutex_data = get_sw_acc_data(sw, AccKeys.PID_MUTEX)
    if pid_mutex_data is None:
        return False, has_mutex

    for acc, acc_details in sw_data.items():
        if acc == AccKeys.PID_MUTEX:
            continue
        if isinstance(acc_details, dict):
            pid = acc_details.get(AccKeys.PID, None)
            if pid is not None:
                acc_mutex = pid_mutex_data.get(f"{pid}", True)
                if acc_mutex is True:
                    has_mutex = True
                update_sw_acc_data(sw, acc, has_mutex=acc_mutex)
    return True, has_mutex


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
                update_sw_acc_data(sw, acc, avatar_url=matched_url)
                changed = True
    return changed


def get_avatar_url_from_other_sw(now_sw, now_acc_list):
    print("尝试用窃取法获取头像")
    changed = False
    all_sw, = get_details_from_remote_setting_json("global", all_sw=None)
    # print(all_sw)

    # 对所有其他软件进行遍历
    for other_sw in all_sw.keys():
        # print(other_sw, now_sw)
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
        data = load_acc_data()
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
                    now_sw_avatar_url, = get_sw_acc_data(now_sw, now_acc, avatar_url=None)
                    other_sw_avatar_url, = get_sw_acc_data(other_sw, other_acc, avatar_url=None)
                    if other_sw_avatar_url is not None and now_sw_avatar_url is None:
                        # 只有当前平台没有头像url，且另一个平台有头像url，则进行偷取和下载
                        avatar_path = os.path.join(Config.PROJ_USER_PATH, now_sw, f"{now_acc}", f"{now_acc}.jpg")
                        logger.info(f"{now_acc}: {other_sw_avatar_url}")
                        success = image_utils.download_image(other_sw_avatar_url, avatar_path)
                        if success is True:
                            update_sw_acc_data(now_sw, now_acc, avatar_url=other_sw_avatar_url)
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
            success = update_sw_acc_data(sw, acc, nickname=cleaned_str)
            if success is True:
                changed = True
    return changed


def get_nickname_from_other_sw(now_sw, now_acc_list):
    print("尝试用窃取法获取昵称")
    changed = False
    all_sw, = get_details_from_remote_setting_json("global", all_sw=None)
    # print(all_sw)

    # 对所有其他软件进行遍历
    for other_sw in all_sw.keys():
        # print(other_sw, now_sw)
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
        data = load_acc_data()
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
                    now_sw_nickname, = get_sw_acc_data(now_sw, now_acc, nickname=None)
                    other_sw_nickname, = get_sw_acc_data(other_sw, other_acc, nickname=None)
                    if other_sw_nickname is not None and now_sw_nickname is None:
                        # 只有当前平台没有昵称，且另一个平台有昵称，则进行偷取和上传
                        update_sw_acc_data(now_sw, now_acc, nickname=other_sw_nickname)
                        changed = True
    return changed


def get_curr_wx_id_from_config_file(sw, data_dir):
    config_path_suffix, config_files = get_details_from_remote_setting_json(
        sw, config_path_suffix=None, config_file_list=None)
    if config_files is None or len(config_files) == 0:
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


"""统计数据相关"""


def update_statistic_data(sw, mode, main_key, sub_key, time_spent):
    """更新时间统计"""
    print(sw, mode, main_key, sub_key, time_spent)
    if mode == "manual" and time_spent > 20:
        return
    if mode == "auto" and time_spent > 60:
        return
    if mode == 'refresh' and time_spent > 2:
        return

    data = JsonUtils.load_json(Config.STATISTIC_JSON_PATH)
    if sw not in data:
        logger.info(f"sw不存在：{sw}")
        data[sw] = {}
    tab_info = data.get(sw, {})
    if mode not in tab_info:
        logger.info(f"mode不存在：{mode}")
        tab_info[mode] = {}
    if main_key not in tab_info[mode]:
        logger.info(f"main_key不存在：{main_key}")
        tab_info[mode][main_key] = {}
    if sub_key not in tab_info[mode][main_key]:
        logger.info(f"sub_key不存在：{sub_key}")
        tab_info[mode][main_key][sub_key] = f"{math.inf},0,0,0"  # 初始化为“最短时间, (次数, 平均用时), 最长时间”

    # 获取当前最小、最大值，次数，平均用时
    current_min, count, avg_time, current_max = map(lambda x: float(x) if x != "null" else 0,
                                                    tab_info[mode][main_key][sub_key].split(","))

    # 更新最小和最大值
    new_min = min(current_min or math.inf, time_spent)
    new_max = max(current_max or 0, time_spent)

    # 更新次数和平均用时
    new_count = count + 1
    new_avg_time = (avg_time * count + time_spent) / new_count

    tab_info[mode][main_key][sub_key] = f"{new_min:.4f},{new_count},{new_avg_time:.4f},{new_max:.4f}"
    JsonUtils.save_json(Config.STATISTIC_JSON_PATH, data)


"""软件版本及更新相关"""


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


def get_file_with_correct_md5(folders: list, md5s: list):
    """
    从文件夹中找到md5匹配的文件
    :param folders: 文件夹列表
    :param md5s: md5列表
    :return: Union[匹配的文件路径, None]
    """
    lower_md5s = [md5.lower() for md5 in md5s]
    for folder in folders:
        for root, _, files in os.walk(folder):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                try:
                    file_md5 = file_utils.calculate_md5(file_path)
                    # 检查 MD5 是否匹配正确的 MD5 列表
                    if file_md5.lower() in lower_md5s:
                        return file_path  # 返回匹配的文件路径
                except Exception as e:
                    logger.error(e)
    return None  # 如果没有找到匹配项则返回 None


def merge_refresh_nodes():
    """统计数据结构改变后，将所有的节点分流到classic和tree中"""
    data = JsonUtils.load_json(Config.STATISTIC_JSON_PATH)
    # 确保 refresh 节点存在
    if "refresh" not in data or not isinstance(data["refresh"], dict):
        return data

    print("数据结构调整：需要进行刷新节点分流...")
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
    JsonUtils.save_json(Config.STATISTIC_JSON_PATH, data)
    return data


def move_data_to_wechat():
    """统计数据结构改变后，将原本所有的数据移动到WeChat节点下"""
    data = JsonUtils.load_json(Config.STATISTIC_JSON_PATH)

    # 检查是否已有 "WeChat" 节点
    if "WeChat" not in data:
        print("数据结构调整：将数据置于到微信节点下...")
        wechat_data = {
            "WeChat": data
        }
        JsonUtils.save_json(Config.STATISTIC_JSON_PATH, wechat_data)


def swap_cnt_and_mode_levels_in_auto():
    """将auto表中的次数节点和模式节点交换层级"""
    data = JsonUtils.load_json(Config.STATISTIC_JSON_PATH)
    for sw in data.keys():
        auto_info = data.get(sw, {}).get("auto", {})
        # print(auto_info)

        # 已经升级结构的标志
        if 'avg' in auto_info.keys():
            continue

        print(f"数据结构调整：对调{sw}节点下的二三级层级...")
        tmp = {}
        # 交换层级
        for second_level_key, third_level_dict in auto_info.items():
            print(auto_info[second_level_key].keys())
            for third_level_key, value in third_level_dict.items():
                # 如果第三级键还未在结果字典中初始化，则创建一个新的字典
                if third_level_key not in tmp:
                    tmp[third_level_key] = {}
                # 将二级键作为新的第三级键
                tmp[third_level_key][second_level_key] = value
        # print(tmp)

        # 执行完更新后就添加avg节点
        if 'avg' not in tmp.keys():
            tmp['avg'] = {}

        # 转换好的结果重新赋给json文件中
        data[sw]['auto'] = tmp
    JsonUtils.save_json(Config.STATISTIC_JSON_PATH, data)


def downgrade_item_lvl_under_manual():
    """将manual表中的节点降级"""
    data = JsonUtils.load_json(Config.STATISTIC_JSON_PATH)
    for sw in data.keys():
        manual_info = data.get(sw, {}).get("manual", {})
        # print(manual_info)

        # 已经升级结构的标志
        if '_' in manual_info.keys():
            continue

        print("数据结构调整：将手动节点内容降低一个层级...")
        tmp = manual_info
        manual_info = {
            "_": tmp
        }

        # 转换好的结果重新赋给json文件中
        data[sw]['manual'] = manual_info
    JsonUtils.save_json(Config.STATISTIC_JSON_PATH, data)


def get_packed_executable():
    """获取打包后的可执行文件路径"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的可执行文件
        return sys.executable
    else:
        # 如果是源代码运行
        return None


def check_auto_start_or_toggle_to_(target_state=None):
    startup_folder = sys_utils.get_startup_folder()
    print(startup_folder)
    app_path = get_packed_executable()
    print(app_path)

    if app_path is None:
        auto_start, paths = False, None
        shortcut_path = None
    else:
        auto_start, paths = file_utils.check_shortcut_in_folder(startup_folder, app_path)
        shortcut_name = os.path.splitext(os.path.basename(app_path))[0]
        shortcut_path = os.path.join(startup_folder, f"{shortcut_name}.lnk")

    if target_state is None:
        return True, auto_start

    else:
        try:
            if target_state is True:
                file_utils.create_shortcut_for_(app_path, shortcut_path)
            elif target_state is False:
                file_utils.move_files_to_recycle_bin(paths)
            return True, None
        except Exception as e:
            logger.error(e)
            return False, str(e)


def create_and_export_task():
    """创建任务并导出 XML"""
    task_name = f"TempTask_{int(time.time())}"
    exported_xml_path = Config.TASK_TP_XML_PATH

    # 1. 创建任务
    subprocess.run([
        "schtasks", "/Create", "/TN", task_name, "/SC", "ONCE", "/ST", "12:00",
        "/TR", "C:\\Windows\\System32\\notepad.exe", "/RL", "HIGHEST", "/F"
    ], check=True)

    # 2. 导出任务 XML
    result = subprocess.run(["schtasks", "/Query", "/TN", task_name, "/XML"],
                            capture_output=True,
                            check=True)

    # 使用错误处理来忽略无法解码的字节
    xml_data = result.stdout.decode("utf-16", errors="ignore")

    # 重新保存为 UTF-8
    with open(exported_xml_path, "w", encoding="utf-8") as f:
        f.write(xml_data)

    print(f"任务 XML 导出成功: {exported_xml_path}")


if __name__ == '__main__':
    create_and_export_task()
