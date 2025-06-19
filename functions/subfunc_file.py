import base64
import datetime as dt
import json
import math
import os
import re
import sys
from enum import Enum
from typing import *

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from public_class.enums import LocalCfg, AccKeys, SW
from resources import Config, Strings
from utils import file_utils
from utils.file_utils import JsonUtils, DictUtils
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
            save_a_global_setting_and_callback("next_check_time", next_check_time_str)
            return config_data
        else:
            # 失败加载本地
            return try_read_remote_cfg_locally()
    else:
        # 不到时间直接加载本地
        return try_read_remote_cfg_locally()


def load_remote_cfg() -> dict:
    data = JsonUtils.load_json(Config.REMOTE_SETTING_JSON_PATH)
    return data


def get_remote_cfg(*pre_nodes: str, **kwargs) -> Tuple[Any, ...]:
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


"""额外配置"""


def load_extra_cfg() -> dict:
    data = JsonUtils.load_json(Config.EXTRA_SETTING_JSON_PATH)
    return data


def save_extra_cfg(data):
    return JsonUtils.save_json(Config.EXTRA_SETTING_JSON_PATH, data)


def clear_some_extra_cfg(*addr) -> bool:
    """
    清空某平台的账号记录，在对平台重新设置后触发
    :return: 是否成功
    """
    try:
        print(f"清理{addr}处数据...")
        data = load_extra_cfg()
        DictUtils.clear_nested_values(data, *addr)
        save_extra_cfg(data)
        return True
    except Exception as e:
        logger.error(e)
        return False


def update_extra_cfg(*front_addr, **kwargs) -> bool:
    """更新账户信息到 JSON"""
    try:
        data = load_extra_cfg()
        success = DictUtils.set_nested_values(data, None, *front_addr, **kwargs)
        save_extra_cfg(data)
        return success
    except Exception as e:
        logger.error(e)
        return False


def get_extra_cfg(*front_addr, **kwargs) -> Union[Dict, Tuple[Any, ...]]:
    """
    根据用户输入的变量名，获取对应的账户信息
    :param front_addr: 前置地址，如：("wechat", "account1")
    :param kwargs: 需要获取的键地址及其默认值（如 note="", nickname=None）
    :return: 包含所请求数据的元组
    """
    try:
        data = load_extra_cfg()
        return DictUtils.get_nested_values(data, None, *front_addr, **kwargs)
    except Exception as e:
        logger.error(e)
        return tuple()


"""本地设置:为了线程安全,写方法仅在设置界面可以使用"""


def _load_setting():
    """
    加载设置
    :return:
    """
    # data = IniUtils.load_ini_as_dict(Config.SETTING_INI_PATH)
    data = JsonUtils.load_json(Config.LOCAL_SETTING_JSON_PATH)
    return data


def _save_setting(data):
    # return IniUtils.save_ini_from_dict(Config.SETTING_INI_PATH, data)
    return JsonUtils.save_json(Config.LOCAL_SETTING_JSON_PATH, data)


def clear_some_setting(*addr) -> bool:
    """
    清空某平台的账号记录，在对平台重新设置后触发
    :return: 是否成功
    """
    try:
        print(f"清理{addr}处数据...")
        data = _load_setting()
        DictUtils.clear_nested_values(data, *addr)
        _save_setting(data)
        return True
    except Exception as e:
        logger.error(e)
        return False


def update_settings(*front_addr, **kwargs) -> bool:
    """更新账户信息到 JSON"""
    try:
        data = _load_setting()
        success = DictUtils.set_nested_values(data, None, *front_addr, **kwargs)
        _save_setting(data)
        return success
    except Exception as e:
        logger.error(e)
        return False


def get_settings(*front_addr, **kwargs) -> Union[Any, Tuple[Any, ...]]:
    """
    根据用户输入的变量名，获取对应的账户信息
    :param front_addr: 前置地址，如：("wechat", "account1")
    :param kwargs: 需要获取的键地址及其默认值（如 note="", nickname=None）
    :return: 包含所请求数据的元组
    """
    try:
        data = _load_setting()
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
        origin_value = get_settings(section, key)
        # 如果value是枚举类,则获取其值
        if isinstance(value, Enum):
            value = value.value
        update_settings(section, **{key: value})

        new_value = get_settings(section, key)

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


def save_a_global_setting_and_callback(key, value, callback=None):
    return save_a_setting_and_callback(LocalCfg.GLOBAL_SECTION, key, value, callback)


def fetch_global_setting_or_set_default_or_none(setting_key):
    """
    获取配置项，若没有则添加默认，若没有默认则返回None
    :return: 已选择的子程序
    """
    return fetch_sw_setting_or_set_default_or_none(LocalCfg.GLOBAL_SECTION, setting_key)


def fetch_sw_setting_or_set_default_or_none(sw: str, setting_key: str, enum_cls: Optional[Type[Enum]] = None):
    """
    获取配置项，若没有则设置默认值，若没有默认值则返回None
    若传入枚举类，会严格验证值是否在枚举范围内，无效则使用枚举第一个值

    :param sw: 平台标识
    :param setting_key: 配置键名
    :param enum_cls: 可选枚举类（用于严格验证值）
    :return: 配置值（保证符合枚举约束）或None
    """
    # 原值
    value, = get_settings(sw, **{setting_key: None})
    if value in (None, "", "None", "none", "null", "NULL"):
        try:
            # 默认值
            try:
                sw_dict = Config.INI_DEFAULT_VALUE[sw]
            except KeyError as ke:
                print(ke)
                sw_dict = Config.INI_DEFAULT_VALUE[SW.DEFAULT]
            value = sw_dict[setting_key]
            pass
        except (KeyError, AttributeError) as e:
            print(e)
            # 空值
            value = None
    if isinstance(value, Enum):
        value = value.value
    # 若使用了枚举,检测值是否在枚举范围内，无效则使用枚举第一个值
    if enum_cls is not None:
        valid_values = {e.value for e in enum_cls}  # 保持原始大小写
        if value not in valid_values:
            value = next(iter(enum_cls)).value  # 使用第一个枚举值

    update_settings(sw, **{setting_key: value})
    return value


"""账号数据相关，该文件记录账号及登录时期的互斥体情况"""


def _load_acc_data() -> dict:
    """
    加载账号数据，请在这个方法中修改账号数据的加载方式，如格式、文件位置
    :return: 账号数据字典
    """
    data = JsonUtils.load_json(Config.TAB_ACC_JSON_PATH)
    return data


def _save_acc_data(data) -> bool:
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
        data = _load_acc_data()
        DictUtils.clear_nested_values(data, *addr)
        _save_acc_data(data)
        return True
    except Exception as e:
        logger.error(e)
        return False


def update_sw_acc_data(*front_addr, **kwargs) -> bool:
    """更新账户信息到 JSON"""
    try:
        data = _load_acc_data()
        success = DictUtils.set_nested_values(data, None, *front_addr, **kwargs)
        _save_acc_data(data)
        return success
    except Exception as e:
        logger.error(e)
        return False


def get_sw_acc_data(*front_addr, **kwargs) -> Union[Any, Tuple[Any, ...]]:
    """
    根据用户输入的变量名，获取对应的账户信息
    :param front_addr: 前置地址，如：("wechat", "account1")
    :param kwargs: 需要获取的键地址及其默认值（如 note="", nickname=None）
    :return: 包含所请求数据的元组
    """
    try:
        data = _load_acc_data()
        return DictUtils.get_nested_values(data, None, *front_addr, **kwargs)
    except Exception as e:
        logger.error(e)
        return tuple()


"""账号互斥体相关"""


def update_pid_mutex_of_(sw):
    """
    清空后将json中所有已登录账号的情况加载到登录列表all_wechat结点中，适合登录之前使用
    :return: 是否成功
    """
    print("构建互斥体记录...")
    # 加载当前账户数据
    sw_data = get_sw_acc_data(sw)
    if not isinstance(sw_data, dict):
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


def set_pid_mutex_values_to_false(sw):
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


def update_has_mutex_from_pid_mutex(sw):
    """
    将json中登录列表pid_mutex结点中的情况加载回所有已登录账号，适合刷新结束时使用
    :return: 是否成功
    """
    has_mutex = False
    sw_dict = get_sw_acc_data(sw)
    if not isinstance(sw_dict, dict):
        return False, has_mutex
    pid_mutex_dict = get_sw_acc_data(sw, AccKeys.PID_MUTEX)
    if not isinstance(pid_mutex_dict, dict):
        return False, has_mutex

    for acc, acc_details in sw_dict.items():
        if acc == AccKeys.PID_MUTEX:
            continue
        if isinstance(acc_details, dict):
            pid = acc_details.get(AccKeys.PID, None)
            if pid is not None:
                acc_mutex = pid_mutex_dict.get(f"{pid}", True)
                if acc_mutex is True:
                    has_mutex = True
                update_sw_acc_data(sw, acc, has_mutex=acc_mutex)
    return True, has_mutex


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