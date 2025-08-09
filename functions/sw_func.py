import base64
import glob
import os
import re
import shutil
import subprocess
import threading
import time
import winreg
from tkinter import messagebox
from typing import Union, Tuple, Optional

import psutil
import win32com
import win32con
import win32gui
import winshell
from PIL import Image
from win32com.client import Dispatch

from functions import subfunc_file
from public_class.custom_widget import CustomDialog
from public_class.enums import LocalCfg, SW, AccKeys, MultirunMode, RemoteCfg, CallMode
from public_class.global_members import GlobalMembers
from resources import Config, Strings, Constants
from resources.strings import NEWER_SYS_VER
from utils import file_utils, process_utils, handle_utils, hwnd_utils, image_utils
from utils.better_wx.inner_utils import patt2hex, custom_wildcard_tokenize
from utils.encoding_utils import VersionUtils, PathUtils, StringUtils, CryptoUtils
from utils.file_utils import DllUtils
from utils.logger_utils import mylogger as logger, Printer, Logger
from utils.logger_utils import myprinter as printer
from utils.process_utils import Process


class SwInfoFunc:
    """
    当前版本，所使用的适配表结构如下：
    平台sw -> 补丁模式mode -> 分支(精确precise,特征feature,说明channel) -> 版本号 -> 频道 -> 路径地址 -> 特征码
    其中,
        precise: 精确版本适配，只适配当前版本. 结构为 版本号 -> 频道 -> 特征码
        feature: 特征码适配，适配当前版本及其兼容版本. 结构为 版本号 -> 频道 -> 特征码
        channel: 频道，区分不同特征/作者的适配. 结构为 频道 -> (标题,说明,作者)
    """

    @classmethod
    def resolve_sw_path(cls, sw, addr: str):
        """解析补丁路径, 路径中可以包含%包裹的引用地址, 如%dll_dir%/WeChatWin.dll"""
        resolved_parts = []
        for part in addr.replace("\\", "/").split("/"):
            if not part:
                continue
            if part.startswith("%") and part.endswith("%") and len(part) > 2:
                var_name = part[1:-1]
                try:
                    if var_name == LocalCfg.INST_DIR:
                        inst_path = cls.try_get_path_of_(sw, LocalCfg.INST_PATH)
                        resolved = os.path.dirname(inst_path).replace("\\", "/")
                    else:
                        resolved = cls.try_get_path_of_(sw, var_name)
                    resolved_parts.append(resolved.strip("/\\"))
                except KeyError:
                    raise ValueError(f"路径变量未定义: %{var_name}%")
            else:
                resolved_parts.append(part)
        return "/".join(resolved_parts)

    @classmethod
    def _identify_multi_state_patching_of_files_in_channel(cls, sw, channel_addresses_dict):
        """对于非二元状态切换的, 只需要检测原始串即可"""
        addr_res_dict = {}
        for addr in channel_addresses_dict.keys():
            # Printer().debug(f"检查文件地址 {addr} 的特征码适配")
            patch_file = cls.resolve_sw_path(sw, addr)
            original_list = channel_addresses_dict[addr]["original"]
            modified_list = channel_addresses_dict[addr]["modified"]
            has_original_list = DllUtils.find_hex_patterns_from_file(patch_file, *original_list)
            # 转换为集合检查一致性,集合中只允许有一个元素，True表示list全都是True，False表示list全都是False，其他情况不合法
            Printer().debug(f"特征码列表:\n{has_original_list}")
            has_original_set = set(has_original_list)
            # 判断匹配状态
            if len(has_original_set) == 1 and True in has_original_set:
                available = True
                message = "包含该模式"
            else:
                available = False
                message = "没有该模式"
            # 将结果存入字典
            addr_res_dict[addr] = (available, message, patch_file, original_list, modified_list)

        return addr_res_dict

    @classmethod
    def _identify_binary_state_patching_of_files_in_channel(cls, sw, channel_addresses_dict) -> dict:
        """
        二元状态, 对渠道内的文件分别检测原始串和补丁串来识别状态
        参数: channel_addresses_dict: 渠道-文件适配字典 {addr: {"original": [...], "modified": [...]}}
        返回:
            { addr1: (status, message, patch_file, original_list, modified_list),
                addr2: (status, message, patch_file, original_list, modified_list), ...}
            其中, status: True/False/None; message: 状态描述字符串; patch_file: 补丁文件路径;
                original_list: 原始串列表; modified_list: 补丁串列表
        """
        addr_res_dict = {}
        for addr in channel_addresses_dict.keys():
            # Printer().debug(f"检查文件地址 {addr} 的特征码适配")
            patch_file = cls.resolve_sw_path(sw, addr)
            original_list = channel_addresses_dict[addr]["original"]
            modified_list = channel_addresses_dict[addr]["modified"]
            has_original_list = DllUtils.find_hex_patterns_from_file(patch_file, *original_list)
            has_modified_list = DllUtils.find_hex_patterns_from_file(patch_file, *modified_list)
            # 转换为集合检查一致性,集合中只允许有一个元素，True表示list全都是True，False表示list全都是False，其他情况不合法
            has_original_set = set(has_original_list)
            has_modified_set = set(has_modified_list)
            # 初始化默认值
            status = None
            message = "未知状态"
            # 判断匹配状态
            if len(has_original_set) == 1 and len(has_modified_set) == 1:
                all_original = True if True in has_original_set else False if False in has_original_set else None
                all_modified = True if True in has_modified_set else False if False in has_modified_set else None
                if all_original is True and all_modified is False:
                    status = False
                    message = "未开启"
                elif all_original is False and all_modified is True:
                    status = True
                    message = "已开启"
                elif all_original is True or all_modified is True:
                    message = "文件有多处匹配，建议优化补丁替换列表"
            else:
                message = "文件匹配结果不一致"
            # 将结果存入字典
            addr_res_dict[addr] = (status, message, patch_file, original_list, modified_list)

        return addr_res_dict

    @classmethod
    def _identify_patching_of_channels_in_ver(cls, sw, ver_channels_dict, multi_state=False) -> dict:
        """
        对版本适配字典中的所有通道进行状态识别
        参数:
            ver_adaptation: 版本适配字典 {channel: {addr: {"original": [...], "modified": [...]}}}
            only_original: 是否为多元状态, 二元状态为False, 多元状态为True; 多元状态只需要检测原始串
        返回:
            { channel1: (status, message, addr_res_dict),
                channel2: (status, message, addr_res_dict), ...}
            status: True/False/None
            message: 状态描述字符串
        """
        results = {}
        status_set = set()
        for channel in ver_channels_dict.keys():
            addr_msg_dict = {}
            channel_files_dict = ver_channels_dict[channel]
            if multi_state:
                addr_res_dict = cls._identify_multi_state_patching_of_files_in_channel(sw, channel_files_dict)
            else:
                addr_res_dict = cls._identify_binary_state_patching_of_files_in_channel(sw, channel_files_dict)
            # 对频道的所有地址状态进行判定,全为True则为True,全为False则为False,其他情况为None
            for addr in addr_res_dict.keys():
                if isinstance(addr_res_dict[addr], tuple) and len(addr_res_dict[addr]) == 5:
                    status, addr_msg, _, _, _ = addr_res_dict[addr]
                    if (multi_state is False and status is None) or (multi_state is True and status is not True):
                        addr_msg_dict[addr] = addr_msg
                else:
                    status = None
                    addr_msg_dict[addr] = "返回格式错误"
                status_set.add(status)
            channel_status = status_set.pop() \
                if len(status_set) == 1 and next(iter(status_set)) in (True, False) else None
            results[channel] = channel_status, f"文件情况:{addr_msg_dict}", addr_res_dict
        return results

    @classmethod
    def _identify_dll_by_precise_channel_in_mode_dict(
            cls, sw, mode_branches_dict, multi_state=False) -> Tuple[Optional[dict], str]:
        """通过精确版本分支进行识别dll状态"""
        cur_sw_ver = cls.calc_sw_ver(sw)
        if cur_sw_ver is None:
            return None, f"错误：未知当前版本"
        if "precise" not in mode_branches_dict:
            return None, f"错误：该模式没有精确版本分支用以适配"
        precise_vers_dict = mode_branches_dict["precise"]
        if cur_sw_ver not in precise_vers_dict:
            return None, f"错误：精确分支中未找到版本{cur_sw_ver}的适配"
        ver_channels_dict = precise_vers_dict[cur_sw_ver]
        channel_res_dict = cls._identify_patching_of_channels_in_ver(sw, ver_channels_dict, multi_state)
        if len(channel_res_dict) == 0:
            return None, f"错误：该版本{cur_sw_ver}的适配在本地平台中未找到"
        return channel_res_dict, f"成功：找到版本{cur_sw_ver}的适配"

    @classmethod
    def _update_adaptation_from_remote_to_cache(cls, sw, mode):
        """根据远程表内容更新额外表"""
        config_data = subfunc_file.read_remote_cfg_in_rules()
        if not config_data:
            return
        remote_mode_branches_dict, = subfunc_file.get_remote_cfg(sw, **{mode: None})
        if remote_mode_branches_dict is None:
            return
        # 尝试寻找兼容版本并添加到额外表中
        cur_sw_ver = cls.calc_sw_ver(sw)
        if "precise" in remote_mode_branches_dict:
            precise_vers_dict = remote_mode_branches_dict["precise"]
            if cur_sw_ver in precise_vers_dict:
                # 用精确版本特征码查找适配
                precise_ver_adaptations = precise_vers_dict[cur_sw_ver]
                for channel, adaptation in precise_ver_adaptations.items():
                    subfunc_file.update_extra_cfg(
                        sw, mode, "precise", cur_sw_ver, **{channel: adaptation})
        if "feature" in remote_mode_branches_dict:
            feature_vers = list(remote_mode_branches_dict["feature"].keys())
            compatible_ver = VersionUtils.find_compatible_version(cur_sw_ver, feature_vers)
            cache_ver_channels_dict = subfunc_file.get_cache_cfg(sw, mode, "precise", cur_sw_ver)
            if compatible_ver:
                # 用兼容版本特征码查找适配
                feature_ver_channels_dict = remote_mode_branches_dict["feature"][compatible_ver]
                for channel in feature_ver_channels_dict.keys():
                    if cache_ver_channels_dict is not None and channel in cache_ver_channels_dict:
                        print("已存在缓存的精确适配")
                        continue
                    channel_res_dict = {}
                    channel_failed = False
                    feature_channel_addr_dict = feature_ver_channels_dict[channel]
                    for addr in feature_channel_addr_dict.keys():
                        addr_feature_dict = feature_channel_addr_dict[addr]
                        # 对原始串和补丁串需要扫描匹配, 其余节点拷贝
                        patch_file = cls.resolve_sw_path(sw, addr)
                        original_feature = addr_feature_dict["original"]
                        modified_feature = addr_feature_dict["modified"]
                        addr_res_dict = SwInfoUtils.search_patterns_and_replaces_by_features(
                            patch_file, (original_feature, modified_feature))
                        if not addr_res_dict:
                            channel_failed = True
                            break
                        channel_res_dict[addr] = addr_res_dict
                        for key in addr_feature_dict:
                            if key not in ["original", "modified"]:
                                channel_res_dict[addr][key] = addr_feature_dict[key]
                    if not channel_failed:
                        # 添加到缓存表中
                        subfunc_file.update_extra_cfg(
                            sw, mode, "precise", cur_sw_ver, **{channel: channel_res_dict})

    @classmethod
    def _identify_dll_by_cache_cfg(cls, sw, mode, multi_state=False) -> Tuple[Optional[dict], str]:
        """从缓存表中获取"""
        try:
            mode_branches_dict, = subfunc_file.get_cache_cfg(sw, **{mode: None})
            if mode_branches_dict is None:
                return None, f"错误：平台未适配{mode}"
            return cls._identify_dll_by_precise_channel_in_mode_dict(sw, mode_branches_dict, multi_state)
        except Exception as e:
            Logger().error(e)
            return None, f"错误：{e}"

    @classmethod
    def identify_dll(cls, sw, mode, multi_state=False) -> Tuple[Optional[dict], str]:
        """
        检查当前补丁状态，返回结果字典,若没有适配则返回None
        结果字典格式: {channel1: (status, msg, addr_res_dict), channel2: (status, msg, addr_res_dict) ...}
        地址字典addr_res_dict格式: {addr1: (status, msg, patch_path, original, modified),
                                    addr2: (status, msg, patch_path, original, modified) ...}
        """
        dll_dir = cls.try_get_path_of_(sw, LocalCfg.DLL_DIR)
        if dll_dir is None:
            return None, "错误：没有找到dll目录"
        cls._update_adaptation_from_remote_to_cache(sw, mode)
        mode_channel_res_dict, msg = cls._identify_dll_by_cache_cfg(sw, mode, multi_state)
        return mode_channel_res_dict, msg

    @classmethod
    def clear_adaptation_cache(cls, sw, mode):
        """清除当前版本模式的适配缓存"""
        curr_ver = cls.calc_sw_ver(sw)
        subfunc_file.clear_some_extra_cfg(sw, mode, "precise", curr_ver)

    @classmethod
    def get_available_coexist_mode(cls, sw):
        """选择一个可用的共存构造模式, 优先返回用户选择的, 若其不可用则返回可用的第一个模式"""
        user_coexist_channel = subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, LocalCfg.COEXIST_MODE)
        channel_res_dict, msg = cls.identify_dll(sw, RemoteCfg.COEXIST, True)
        if isinstance(channel_res_dict, dict):
            if user_coexist_channel in channel_res_dict:
                return user_coexist_channel
            return list(channel_res_dict.keys())[0]
        return None

    @staticmethod
    def detect_path_of_(sw, path_type) -> Optional[str]:
        """通过内置方法列表获取路径"""
        _, _, result = SwInfoUtils.try_detect_path(sw, path_type)
        return result

    @classmethod
    def try_get_path_of_(cls, sw, path_type) -> Optional[str]:
        """优先获取已保存的路径, 若没有则通过方法自动搜寻"""
        path = cls.get_saved_path_of_(sw, path_type)
        # Printer().debug(f"从本地记录获取{sw}的{path_type}路径: {path}")
        if path is not None:
            return path
        return cls.detect_path_of_(sw, path_type)

    @staticmethod
    def get_saved_path_of_(sw, path_type) -> Optional[str]:
        path, = subfunc_file.get_settings(sw, **{path_type: None})
        if PathUtils.is_valid_path(path):
            return path
        return None

    @classmethod
    def calc_sw_ver(cls, sw) -> Optional[str]:
        """获取软件版本"""
        try:
            exec_path = cls.try_get_path_of_(sw, LocalCfg.INST_PATH)
            cur_sw_ver = file_utils.get_file_version(exec_path)
            if cur_sw_ver is not None:
                return cur_sw_ver
            # Printer().debug(f"未能通过应用程序获取{sw}的版本, 尝试通过动态链接库版本获取...")
            dll_dir = cls.try_get_path_of_(sw, LocalCfg.DLL_DIR)
            dll_dir_check_suffix, = subfunc_file.get_remote_cfg(sw, dll_dir_check_suffix=None)
            dll_path = os.path.join(dll_dir, dll_dir_check_suffix).replace("\\", "/")
            cur_sw_ver = file_utils.get_file_version(dll_path)
            if cur_sw_ver is not None:
                return cur_sw_ver
            return None
        except Exception as e:
            logger.error(f"从dll文件处获取失败:{e}")
            return None

    @staticmethod
    def get_sw_logo(sw) -> Image:
        """获取平台图标作为logo"""
        # 构建头像文件路径
        user_sw_dir = os.path.join(Config.PROJ_USER_PATH, sw)
        if not os.path.exists(user_sw_dir):
            os.makedirs(user_sw_dir)
        avatar_path = os.path.join(user_sw_dir, f"{sw}.png")

        # 检查是否存在对应account的头像
        if os.path.exists(avatar_path):
            return Image.open(avatar_path)

        # 从图标中提取
        try:
            executable = subfunc_file.get_settings(sw, LocalCfg.INST_PATH)
            if executable:
                image_utils.extract_icon_to_png(executable, avatar_path)
        except Exception as e:
            print(e)

        # # 如果没有，从网络下载
        # url, = subfunc_file.get_sw_acc_data(sw, acc, avatar_url=None)
        # if url is not None and url.endswith("/0"):
        #     image_utils.download_image(url, avatar_path)

        # 第二次检查是否存在对应account的头像
        if os.path.exists(avatar_path):
            return Image.open(avatar_path)

        # 如果没有，检查default.jpg
        default_path = os.path.join(Config.PROJ_USER_PATH, "default.jpg")
        if os.path.exists(default_path):
            return Image.open(default_path)

        # 如果default.jpg也不存在，则将从字符串转换出来
        try:
            base64_string = Strings.DEFAULT_AVATAR_BASE64
            image_data = base64.b64decode(base64_string)
            with open(default_path, "wb") as f:
                f.write(image_data)
            return Image.open(default_path)
        except FileNotFoundError as e:
            print("文件路径无效或无法创建文件:", e)
            return None
        except IOError as e:
            print("图像文件读取失败:", e)
            return None
        except Exception as e:
            print("所有方法都失败，创建空白头像:", e)
            return Image.new('RGB', Constants.AVT_SIZE, color='white')

    @staticmethod
    def get_sw_origin_display_name(sw) -> str:
        """获取账号的展示名"""
        # 依次查找 note, nickname, alias，找到第一个不为 None 的值
        display_name = str(sw)  # 默认值为 sw
        label, = subfunc_file.get_remote_cfg(sw, label=sw)
        subfunc_file.update_settings(sw, label=label)
        for key in ("note", "label"):
            value, = subfunc_file.get_settings(sw, **{key: None})
            if value is not None:
                print(key, value)
                display_name = str(value)
                break
        return display_name

    @classmethod
    def get_sw_all_exe_pids_group_by_name(cls, sw) -> dict:
        """获得平台所有进程的pid, 并根据进程名进行分组, 返回字典"""
        executable_wildcards, = subfunc_file.get_remote_cfg(
            sw,
            executable_wildcards=None,
        )
        inst_path = cls.try_get_path_of_(sw, LocalCfg.INST_PATH)
        inst_dir = os.path.dirname(inst_path)
        name_pids_dict = {}
        if isinstance(executable_wildcards, list):
            name_pids_dict = process_utils.psutil_get_pids_by_wildcards_and_grouping_to_dict(executable_wildcards)
        if len(name_pids_dict) == 0:
            return name_pids_dict
        # 对每组 pid 分别进行处理
        for name in name_pids_dict.keys():
            pid_list = name_pids_dict[name]
            pid_list = process_utils.remove_child_pids(pid_list)
            pid_list = process_utils.remove_pids_not_in_path(pid_list, inst_dir)
            if pid_list:
                name_pids_dict[name] = pid_list
            else:
                del name_pids_dict[name]  # 若该组全部被过滤，则删除 key

        return name_pids_dict

    @classmethod
    def get_sw_all_exe_pids(cls, sw) -> list:
        """返回平台所有进程的 pid 列表"""
        executable_wildcards, = subfunc_file.get_remote_cfg(
            sw,
            executable_wildcards=None,
        )
        inst_path = cls.try_get_path_of_(sw, LocalCfg.INST_PATH)
        inst_dir = os.path.dirname(inst_path)
        pids = []
        if isinstance(executable_wildcards, list):
            name_pids_dict = process_utils.psutil_get_pids_by_wildcards_and_grouping_to_dict(executable_wildcards)
            pids = [pid for pid_list in name_pids_dict.values() for pid in pid_list]
        pids = process_utils.remove_child_pids(pids)
        pids = process_utils.remove_pids_not_in_path(pids, inst_dir)

        return pids

    # @staticmethod
    # def get_root_pids_by_name_wildcards(name_wildcards) -> list:
    #     """根据软件名称通配词获取所有进程的pid, 并移除子进程"""
    #     pids = process_utils.psutil_get_pids_by_wildcards(name_wildcards)
    #     pids = process_utils.remove_child_pids(pids)
    #     return pids

    @staticmethod
    def record_sw_pid_mutex_dict_when_start_login(sw) -> dict:
        """在该平台登录之前,存储 pid 和 互斥体 的映射关系字典"""
        pids = SwInfoFunc.get_sw_all_exe_pids(sw)
        pid_mutex_dict = {}
        for pid in pids:
            pid_mutex_dict[pid] = True
        subfunc_file.update_sw_acc_data(AccKeys.RELAY, sw, **{AccKeys.PID_MUTEX: pid_mutex_dict})
        return pid_mutex_dict

    @staticmethod
    def get_pids_has_mutex_from_record(sw) -> list:
        """从记录中获取所有有互斥体的pid"""
        has_mutex_dict = subfunc_file.get_sw_acc_data(AccKeys.RELAY, sw, AccKeys.PID_MUTEX)
        pids_has_mutex = [pid for pid in has_mutex_dict.keys() if has_mutex_dict[pid] is True]
        pids_has_mutex = [int(x) if isinstance(x, str) and x.isdigit() else x for x in pids_has_mutex]  # 将字符串转换为整数
        return pids_has_mutex

    @staticmethod
    def set_pid_mutex_all_values_to_false(sw):
        """
        将所有微信进程all_acc中都置为没有互斥体，适合每次成功打开一个登录窗口后使用
        （因为登录好一个窗口，说明之前所有的微信都没有互斥体了）
        :return: 是否成功
        """
        # 加载当前账户数据
        pid_mutex_data = subfunc_file.get_sw_acc_data(AccKeys.RELAY, sw, AccKeys.PID_MUTEX)
        if pid_mutex_data is None:
            return False

        # 将所有字段的值设置为 False
        for pid in pid_mutex_data:
            subfunc_file.update_sw_acc_data(AccKeys.RELAY, sw, AccKeys.PID_MUTEX, **{pid: False})
        return True

    @staticmethod
    def update_has_mutex_from_pid_mutex(sw):
        """
        将json中登录列表pid_mutex结点中的情况加载回所有已登录账号，适合刷新结束时使用
        :return: 是否成功
        """
        has_mutex = False
        sw_dict = subfunc_file.get_sw_acc_data(sw)
        if not isinstance(sw_dict, dict):
            return False, has_mutex
        pid_mutex_dict = subfunc_file.get_sw_acc_data(AccKeys.RELAY, sw, AccKeys.PID_MUTEX)
        if not isinstance(pid_mutex_dict, dict):
            return False, has_mutex

        for acc, acc_details in sw_dict.items():
            if isinstance(acc_details, dict):
                pid = acc_details.get(AccKeys.PID, None)
                if pid is not None:
                    acc_mutex = pid_mutex_dict.get(f"{pid}", True)
                    if acc_mutex is True:
                        has_mutex = True
                    subfunc_file.update_sw_acc_data(sw, acc, has_mutex=acc_mutex)
        return True, has_mutex


class SwOperator:
    @staticmethod
    def get_sw_all_mutex_handles_and_try_kill_if_need(sw, kill=None):
        """获得平台所有剩余互斥锁的句柄"""
        Printer().debug("查杀平台互斥体中...")
        mutant_wildcards, = subfunc_file.get_remote_cfg(
            sw,
            mutant_handle_wildcards=None,
        )
        if not isinstance(mutant_wildcards, list):
            print("未获取到互斥体通配词,将不进行查找...")
            return None
        pids = SwInfoFunc.get_sw_all_exe_pids(sw)
        Printer().debug(f"当前所有进程: {pids}")
        # 清空互斥体节点,维护本次登录的互斥体情况
        subfunc_file.clear_some_acc_data(AccKeys.RELAY, sw, AccKeys.PID_MUTEX)
        pid_mutex_dict = {}
        for pid in pids:
            pid_mutex_dict[pid] = []
        mutant_handle_dicts = handle_utils.pywinhandle_find_handles_by_pids_and_handle_name_wildcards(
            pids, mutant_wildcards)
        Printer().debug(f"查杀前所有互斥体: {mutant_handle_dicts}")
        if kill is True and len(mutant_handle_dicts) != 0:
            handle_utils.pywinhandle_close_handles(mutant_handle_dicts)
            mutant_handle_dicts = handle_utils.pywinhandle_find_handles_by_pids_and_handle_name_wildcards(
                pids, mutant_wildcards)
            Printer().debug(f"查杀后所有互斥体: {mutant_handle_dicts}")
        return mutant_handle_dicts

    @staticmethod
    def _ask_for_manual_terminate_or_force(sw_exe_path):
        """询问手动退出,否则强制退出"""
        executable = os.path.basename(sw_exe_path)
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                if proc.info['name'].lower() == executable.lower():
                    exe_path = proc.info['exe'] or ""
                    # 只保留来自 sw_exe_path 的同名进程
                    if os.path.normcase(exe_path) == os.path.normcase(sw_exe_path):
                        processes.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if processes:
            answer = messagebox.askokcancel(
                "警告",
                f"检测到正在使用{executable}。该操作需要退出进程，请先手动退出，直接继续将会强制关闭。是否继续？"
            )
            if not (answer is True):
                return None
            for proc in processes:
                try:
                    proc.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # 等待进程终止
            gone, alive = psutil.wait_procs(processes, timeout=3)
            still_running = [p.pid for p in alive]
            if len(still_running) != 0:
                messagebox.showerror("错误", f"以下进程仍未终止：{still_running}")
                return False
            return True
        return True

    @staticmethod
    def _backup_dll(addr_res_tuple_dict):
        """备份当前的dll"""
        desktop_path = winshell.desktop()
        has_noticed = False
        for addr in addr_res_tuple_dict:
            _, _, patch_path, _, _ = addr_res_tuple_dict[addr]
            dll_dir = os.path.dirname(patch_path)
            patch_file_name = os.path.basename(patch_path)
            dll_bak_path = os.path.join(dll_dir, f"{patch_file_name}.bak")
            bak_desktop_path = os.path.join(desktop_path, f"{patch_file_name}.bak")
            curr_ver = file_utils.get_file_version(patch_path)
            not_same_version = True
            if os.path.exists(dll_bak_path):
                not_same_version = file_utils.get_file_version(dll_bak_path) != curr_ver
            if not os.path.exists(dll_bak_path) or (
                    os.path.exists(dll_bak_path) and not_same_version):
                print("没有备份")
                if not (has_noticed is True):
                    messagebox.showinfo(
                        "提醒",
                        "当前是您在该版本首次切换模式，已将原本的文件命名添加.bak后缀备份，桌面亦有备份，可另外保存。")
                    has_noticed = True
                shutil.copyfile(patch_path, dll_bak_path)
                shutil.copyfile(patch_path, bak_desktop_path)

    @classmethod
    def switch_dll(cls, sw, mode, channel) -> Tuple[Optional[bool], str]:
        """对二元状态的渠道, 检测当前状态并切换"""
        try:
            if mode == RemoteCfg.MULTI:
                mode_text = "全局多开"
            elif mode == RemoteCfg.REVOKE:
                mode_text = "防撤回"
            else:
                return False, "未知模式"

            # 条件检查及询问用户
            config_data = subfunc_file.read_remote_cfg_in_rules()
            if not config_data:
                return False, "没有数据"
            sw_exe_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.INST_PATH)
            if not sw_exe_path:
                return False, "该平台暂未适配"
            # 提醒用户手动终止微信进程
            answer = cls._ask_for_manual_terminate_or_force(sw_exe_path)
            if not (answer is True):
                return False, "用户取消操作"

            # 操作过程
            channel_res_dict, msg = SwInfoFunc.identify_dll(sw, mode)
            if channel_res_dict is None:
                return False, msg
            if channel not in channel_res_dict:
                return False, f"错误：未找到频道{channel}的适配"
            tag, msg, addr_res_tuple_dict = channel_res_dict[channel]
            for addr in addr_res_tuple_dict:
                addr_res_tuple = addr_res_tuple_dict[addr]
                if not isinstance(addr_res_tuple, tuple) or len(addr_res_tuple) != 5:
                    return False, f"错误：频道{channel}的适配格式不正确"
            # mode_branches_dict, = subfunc_file.get_remote_cfg(sw, **{mode: None})
            # if mode_branches_dict is None:
            #     return False, "该平台暂未适配"

            file_replaces_dict = {}
            try:
                if tag is True:
                    print(f"当前：{mode}已开启")
                    for addr in addr_res_tuple_dict:
                        _, _, patch_path, original_patterns, modified_patterns = addr_res_tuple_dict[addr]
                        file_replaces_dict[patch_path] = [(modified_patterns, original_patterns)]
                    success = DllUtils.batch_atomic_replace_multi_files(file_replaces_dict)
                    if success:
                        return True, f"成功关闭:{mode_text}"
                elif tag is False:
                    print(f"当前：{mode}未开启")
                    cls._backup_dll(addr_res_tuple_dict)
                    for addr in addr_res_tuple_dict:
                        Printer().debug(addr_res_tuple_dict)
                        _, _, patch_path, original_patterns, modified_patterns = addr_res_tuple_dict[addr]
                        file_replaces_dict[patch_path] = [(original_patterns, modified_patterns)]
                    success = DllUtils.batch_atomic_replace_multi_files(file_replaces_dict)
                    if success:
                        return True, f"成功开启:{mode_text}"
                return False, f"切换{mode_text}失败！请稍后重试！"
            except (psutil.AccessDenied, PermissionError, Exception) as e:
                error_msg = {
                    PermissionError: "权限不足，无法修改 DLL 文件。",
                    psutil.AccessDenied: "无法终止微信进程，请以管理员身份运行程序。",
                    Exception: "发生错误。"
                }.get(type(e), "发生未知错误。")
                logger.error(f"切换{mode_text}时发生错误: {str(e)}")
                return False, f"切换{mode_text}时发生错误: {str(e)}\n{error_msg}"
        except Exception as e:
            return False, f"{str(e)}"

    @staticmethod
    def _wait_hwnds_close_and_do_in_root(hwnds, timeout=20, callback=None):
        """等待所有窗口成功关闭后, 主线程执行 callback, 失败则不执行"""
        root = GlobalMembers.root_class.root
        success = hwnd_utils.wait_hwnds_close(hwnds, timeout)
        if success and callable(callback):
            root.after(0, callback)

    @classmethod
    def _open_sw_origin_and_return_hwnd(cls, sw) -> Tuple[Optional[int], str]:
        """打开平台原始程序并返回窗口hwnd"""
        # 获取需要的数据
        login_wnd_class, = subfunc_file.get_remote_cfg(
            sw, login_wnd_class=None)
        if login_wnd_class is None:
            return None, "该平台尚未适配!"
        all_excluded_hwnds = []
        # 关闭多余的多开器,记录已经存在的窗口 -------------------------------------------------------------------
        cls.kill_sw_multiple_processes(sw)
        remained_idle_wnd_list = cls.get_idle_login_wnd_and_close_if_necessary(sw)
        all_excluded_hwnds.extend(remained_idle_wnd_list)
        # 检查所有pid及互斥体情况 -------------------------------------------------------------------
        SwInfoFunc.record_sw_pid_mutex_dict_when_start_login(sw)
        sw_proc, sub_proc = cls.open_sw(sw)
        sw_proc_pid = sw_proc.pid if sw_proc else None
        if sw_proc_pid is None:
            return None, "创建进程失败!"
        # 等待打开窗口并获取hwnd *******************************************************************
        sw_hwnd, class_name = hwnd_utils.uiautomation_wait_hwnd_exclusively_by_pid_and_class_wildcards(
            all_excluded_hwnds, sw_proc_pid, [login_wnd_class])
        if sub_proc:
            sub_proc.terminate()
        Printer().debug(sw_hwnd)
        return sw_hwnd, ""

    @classmethod
    def _manual_login_origin(cls, sw):
        """手动登录原生平台"""
        root_class = GlobalMembers.root_class
        multirun_mode = GlobalMembers.root_class.sw_classes[sw].multirun_mode
        start_time = time.time()
        sw_hwnd, msg = cls._open_sw_origin_and_return_hwnd(sw)
        if isinstance(sw_hwnd, int):
            SwInfoFunc.set_pid_mutex_all_values_to_false(sw)
            subfunc_file.update_statistic_data(sw, 'manual', '_', multirun_mode, time.time() - start_time)
            print(f"打开了登录窗口{sw_hwnd}")
        else:
            messagebox.showerror("错误", f"手动登录失败:{msg}")
            return
        callback = lambda: root_class.login_ui.refresh_frame(sw)
        cls._wait_hwnds_close_and_do_in_root([sw_hwnd], callback=callback)

    @classmethod
    def _manual_login_coexist_core(cls, sw) -> Tuple[bool, str]:
        """手动登录共存平台,按顺序,登录第一个还未打开的共存程序,若都已经打开,则创造一个新的共存程序后打开"""
        start_time = time.time()
        root_class = GlobalMembers.root_class
        coexist_channel = SwInfoFunc.get_available_coexist_mode(sw)
        if not isinstance(coexist_channel, str):
            return False, "没有可用的共存构造模式!"
        exe_wildcard, sequence = subfunc_file.get_remote_cfg(
            sw, "coexist", "channel", coexist_channel,
            exe_wildcard=None, sequence=None)
        if not isinstance(exe_wildcard, str) or not isinstance(sequence, str):
            return False, f"尚未适配[exe_wildcard, sequence]!"
        login_wnd_wildcards, = subfunc_file.get_remote_cfg(
            sw, login_wnd_class_wildcards=None)
        if not isinstance(login_wnd_wildcards, list):
            return False, "尚未适配[login_wnd_wildcards]!"
        all_excluded_hwnds = []
        # 关闭多余的多开器,记录已经存在的窗口 -------------------------------------------------------------------
        cls.kill_sw_multiple_processes(sw)
        remained_idle_wnd_list = cls.get_idle_login_wnd_and_close_if_necessary(sw)
        all_excluded_hwnds.extend(remained_idle_wnd_list)
        # 检查所有pid及互斥体情况 -------------------------------------------------------------------
        SwInfoFunc.record_sw_pid_mutex_dict_when_start_login(sw)
        sw_proc = None
        for s in sequence:
            exe_name = exe_wildcard.replace("?", s)
            # 查找是否有exe_name进程
            exe_pids_dict = process_utils.psutil_get_pids_by_wildcards_and_grouping_to_dict([exe_name])
            if isinstance(exe_pids_dict, dict) and len(exe_pids_dict.get(exe_name, [])) > 0:
                continue
            inst_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.INST_PATH)
            inst_dir = os.path.dirname(inst_path)
            need_open_exe = os.path.join(inst_dir, exe_name)
            if not os.path.exists(need_open_exe):
                # 建立这个标号的共存程序
                if messagebox.askokcancel("错误", f"不存在{need_open_exe}!是否创建?"):
                    cls._create_coexist_exe_core(sw, s)
                    if os.path.isfile(need_open_exe):
                        sw_proc = cls.create_process_without_admin(need_open_exe)
                    break
                else:
                    return False, "用户取消创建！"
            if os.path.isfile(need_open_exe):
                sw_proc = cls.create_process_without_admin(need_open_exe)
                break
        sw_proc_pid = sw_proc.pid if sw_proc else None
        # 等待打开窗口并获取hwnd *******************************************************************
        if sw_proc_pid is None:
            return False, "创建进程失败！"
        sw_hwnd, class_name = hwnd_utils.uiautomation_wait_hwnd_exclusively_by_pid_and_class_wildcards(
            all_excluded_hwnds, sw_proc_pid, login_wnd_wildcards)
        if isinstance(sw_hwnd, int):
            SwInfoFunc.set_pid_mutex_all_values_to_false(sw)
            subfunc_file.update_statistic_data(
                sw, 'manual', '_', MultirunMode.BUILTIN, time.time() - start_time)
            callback = lambda: root_class.login_ui.refresh_frame(sw)
            cls._wait_hwnds_close_and_do_in_root([sw_hwnd], callback=callback)
            return True, ""
        else:
            return False, "超时未检测到登录窗口!"

    @classmethod
    def _manual_login_coexist(cls, sw):
        """手动登录共存平台,按顺序,登录第一个还未打开的共存程序,若都已经打开,则创造一个新的共存程序后打开"""
        success, msg = cls._manual_login_coexist_core(sw)
        if not success:
            Logger().warning(msg)
            messagebox.showinfo("错误", f"手动登录共存平台失败:{msg}")
            return

    @staticmethod
    def _create_coexist_exe_core(sw, s=None):
        """创建共存程序"""
        coexist_channel = SwInfoFunc.get_available_coexist_mode(sw)
        if not isinstance(coexist_channel, str):
            messagebox.showinfo("错误", f"没有可用的共存构造模式!")
            return
        if s is None:
            exe_wildcard, sequence = subfunc_file.get_remote_cfg(
                sw, "coexist", "channel", coexist_channel,
                exe_wildcard=None, sequence=None)
            if not isinstance(exe_wildcard, str) or not isinstance(sequence, str):
                messagebox.showinfo("错误", f"尚未适配[exe_wildcard, sequence]!")
                return
            for sq in sequence:
                exe_name = exe_wildcard.replace("?", sq)
                inst_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.INST_PATH)
                inst_dir = os.path.dirname(inst_path)
                need_open_exe = os.path.join(inst_dir, exe_name)
                if not os.path.exists(need_open_exe):
                    s = sq
                    break

        if not isinstance(coexist_channel, str):
            messagebox.showerror("错误", f"没有可用的共存构造模式!")
            return
        curr_ver = SwInfoFunc.calc_sw_ver(sw)
        channel_addresses_dict = subfunc_file.get_cache_cfg(sw, RemoteCfg.COEXIST, "precise", curr_ver, coexist_channel)
        if not isinstance(channel_addresses_dict, dict):
            messagebox.showerror("错误", f"尚未适配[coexist_channel]!")
            return
        for addr in channel_addresses_dict:
            if "wildcard" not in channel_addresses_dict[addr]:
                messagebox.showerror("错误", f"适配格式错误!")
                return
        new_files = []
        for addr in channel_addresses_dict:
            origin_path = SwInfoFunc.resolve_sw_path(sw, addr)
            name_wildcard = channel_addresses_dict[addr]["wildcard"]
            new_path = os.path.join(os.path.dirname(origin_path), name_wildcard.replace("?", s))
            # 拷贝到新文件
            shutil.copyfile(origin_path, new_path)
            new_files.append(new_path)
            # 修改新文件
            original = channel_addresses_dict[addr]["original"]
            modified = channel_addresses_dict[addr]["modified"]
            coexist_modified = [m.replace("!!", f"{ord(s):02X}") for m in modified]
            success = DllUtils.batch_atomic_replace_multi_files({new_path: [(original, coexist_modified)]})
            if not success:
                messagebox.showerror("错误", f"创建共存程序[{s}]号失败!")
                for new_file in new_files:
                    os.remove(new_file)
                return

    @classmethod
    def create_coexist_exe_and_refresh(cls, sw):
        root_class = GlobalMembers.root_class
        root = root_class.root
        cls._create_coexist_exe_core(sw)
        root.after(0, root_class.login_ui.refresh_frame, sw)

    @classmethod
    def start_thread_to_manual_login_origin(cls, sw):
        """建议使用此方式,以线程的方式手动登录,避免阻塞"""
        threading.Thread(
            target=cls._manual_login_origin,
            args=(sw,)
        ).start()

    @classmethod
    def start_thread_to_manual_login_coexist(cls, sw):
        """建议使用此方式,以线程的方式手动登录,避免阻塞"""
        threading.Thread(
            target=cls._manual_login_coexist,
            args=(sw,)
        ).start()

    @classmethod
    def start_thread_to_create_coexist_exe(cls, sw):
        threading.Thread(
            target=cls.create_coexist_exe_and_refresh,
            args=(sw,)
        ).start()

    @staticmethod
    def kill_sw_multiple_processes(sw):
        """清理多开器的进程"""
        # 遍历所有的进程
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                # 检查进程名是否以"WeChatMultiple_"开头
                if proc.name() and proc.name().startswith(f'{sw}Multiple_'):
                    proc.kill()
                    print(f"Killed process tree for {proc.name()} (PID: {proc.pid})")
            except Exception as e:
                logger.error(e)
        Printer().print_vn(f"[OK]清理多余多开工具{sw}Multiple_***完成!")

    @staticmethod
    def _organize_sw_mutex_dict_from_record(sw):
        """从本地记录拿到当前时间下系统中所有微信进程的互斥体情况"""
        print("获取互斥体情况...")
        executable, = subfunc_file.get_remote_cfg(sw, executable=None)
        if executable is None:
            return dict()
        pids = SwInfoFunc.get_sw_all_exe_pids(sw)
        print(f"获取到的{sw}进程列表：{pids}")
        has_mutex_dict = dict()
        for pid in pids:
            # 没有在all_wechat节点中，则这个是尚未判断的，默认有互斥体
            has_mutex, = subfunc_file.get_sw_acc_data(AccKeys.RELAY, sw, AccKeys.PID_MUTEX, **{f"{pid}": None})
            if has_mutex is None:
                subfunc_file.update_sw_acc_data(AccKeys.RELAY, sw, AccKeys.PID_MUTEX, **{f"{pid}": True})
                has_mutex_dict.update({pid: has_mutex})
        print(f"获取互斥体情况完成!互斥体列表：{has_mutex_dict}")
        return has_mutex_dict

    @classmethod
    def _check_and_create_process_with_logon(cls, executable, args, creation_flags):
        device_info = CryptoUtils.get_device_fingerprint()
        encrypted_username_data = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.ENCRYPTED_USERNAME)
        encrypted_password_data = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.ENCRYPTED_PASSWORD)
        try:
            username = CryptoUtils.decrypt_data(encrypted_username_data, device_info)
            password = CryptoUtils.decrypt_data(encrypted_password_data, device_info)
        except Exception as e:
            Logger().warning(f"解密失败:{e}")
            username = "xxx"
            password = "xxx"
        changed = False
        while True:
            try:
                # 默认用户名/密码（第一次尝试）
                Printer().debug(f"使用账号密码登录-{username}-{password}")
                proc = process_utils.create_process_with_logon(
                    username, password, executable, args, creation_flags
                )
                if changed is True:
                    # 如果修改了密码且验证成功, 则保存新账户密码
                    encrypted_username_data = CryptoUtils.encrypt_data(username, device_info)
                    encrypted_password_data = CryptoUtils.encrypt_data(password, device_info)
                    subfunc_file.save_a_global_setting_and_callback(LocalCfg.ENCRYPTED_USERNAME,
                                                                    encrypted_username_data)
                    subfunc_file.save_a_global_setting_and_callback(LocalCfg.ENCRYPTED_PASSWORD,
                                                                    encrypted_password_data)
                return proc
            except Exception as e:
                # 弹窗提示输入新账号信息
                if not messagebox.askyesno(
                        "启动失败",
                        f"尝试以系统账户启动失败：\n{e}\n\n是否重新输入账户密码信息？"
                        f"\n(注:账户密码仅在本地加密存储且仅可在本设备解密,无泄露风险"
                        f"\n若仍有顾虑请勿使用!)"):
                    return None  # 用户选择“否”或“取消”

                res = CustomDialog.ask_username_password()
                if res is None:
                    print("用户取消了输入")
                else:
                    username, password = res
                    print(f"用户名: {username}, 密码: {password}")

                changed = True

                # 继续循环尝试

    @classmethod
    def create_process_without_admin(cls,
                                     executable, args=None, creation_flags=subprocess.CREATE_NO_WINDOW) -> Optional[
        Process]:
        """在管理员身份的程序中，以非管理员身份创建进程，即打开的子程序不得继承父进程的权限"""
        if NEWER_SYS_VER:
            call_mode = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.CALL_MODE)
            if call_mode == CallMode.LOGON.value:
                return cls._check_and_create_process_with_logon(executable, args, creation_flags)  # 使用微软账号登录, 下策
            elif call_mode == CallMode.DEFAULT.value:
                # 拿默认令牌通过资源管理器身份创建
                return process_utils.create_process_with_re_token_default(executable, args, creation_flags)
            elif call_mode == CallMode.HANDLE.value:
                # 拿Handle令牌通过资源管理器身份创建
                return process_utils.create_process_with_re_token_handle(executable, args, creation_flags)
            return None
        else:
            return process_utils.create_process_for_win7(executable, args, creation_flags)

    @classmethod
    def open_sw(cls, sw, exe=None):
        """
        根据状态以不同方式打开微信
        :param exe: 指定exe名
        :param sw: 选择软件标签
        :return: 微信窗口句柄
        """
        root_class = GlobalMembers.root_class
        multirun_mode = root_class.sw_classes[sw].multirun_mode
        Printer().print_vn(f"[INFO]使用{multirun_mode}模式打开{sw}...")
        proc = None
        sub_proc = None
        sw_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.INST_PATH)
        if exe:
            sw_path = os.path.join(os.path.dirname(sw_path), exe)
        if not sw_path:
            return None
        if multirun_mode == MultirunMode.FREELY_MULTIRUN:
            # ————————————————————————————————全局多开————————————————————————————————
            proc = cls.create_process_without_admin(sw_path)
        elif multirun_mode == MultirunMode.BUILTIN:
            # ————————————————————————————————builtin————————————————————————————————
            mutant_handle_wildcards, = subfunc_file.get_remote_cfg(
                sw, mutant_handle_wildcards=None)
            pids_has_mutex = SwInfoFunc.get_pids_has_mutex_from_record(sw)
            if len(pids_has_mutex) > 0 and len(mutant_handle_wildcards) > 0:
                Printer().print_vn(f"[INFO]以下进程含有互斥体：{pids_has_mutex}", )
                handle_infos = handle_utils.pywinhandle_find_handles_by_pids_and_handle_name_wildcards(
                    pids_has_mutex, mutant_handle_wildcards)
                Printer().debug(f"[INFO]查询到互斥体：{handle_infos}")
                handle_utils.pywinhandle_close_handles(handle_infos)
            proc = cls.create_process_without_admin(sw_path, None)
        else:
            # 其余的多开模式
            ...
        return proc, sub_proc

    @staticmethod
    def _is_hwnd_a_main_wnd_of_sw(hwnd, sw):
        # TODO: 窗口检测逻辑需要优化
        """检测窗口是否是某个平台的主窗口"""
        executable, = subfunc_file.get_remote_cfg(sw, executable=None)
        # 判断hwnd是否属于指定的程序
        pid = hwnd_utils.get_hwnd_details_of_(hwnd)["pid"]
        if psutil.Process(pid).exe() != executable:
            return False
        expected_classes, = subfunc_file.get_remote_cfg(sw, main_wnd_class_wildcards=None)
        class_name = win32gui.GetClassName(hwnd)
        for expected_class in expected_classes:
            regex = StringUtils.wildcard_to_regex(expected_class)
            if sw == SW.WECHAT:
                # 旧版微信可直接通过窗口类名确定主窗口
                if re.fullmatch(regex, class_name):
                    return True
                continue
            elif sw == SW.WEIXIN:
                if not re.fullmatch(regex, class_name):
                    continue
                # 新版微信需要通过窗口控件判定
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                # 检查是否有最大化按钮
                has_maximize = bool(style & win32con.WS_MAXIMIZEBOX)
                if has_maximize:
                    return True
                continue
        return False

    @classmethod
    def get_idle_login_wnd_and_close_if_necessary(cls, sw, close=False):
        """获取所有多余窗口,如果有需要,关闭这些窗口"""
        login_wnd_class, login_wildcards = subfunc_file.get_remote_cfg(
            sw, login_wnd_class=None, coexist_login_wnd_class_wildcards=None)
        # 多余的窗口类名模式
        all_idle_classes = []
        if isinstance(login_wnd_class, str):
            all_idle_classes.append(login_wnd_class)
        if isinstance(login_wildcards, list):
            for wildcard in login_wildcards:
                if isinstance(wildcard, str) and wildcard not in all_idle_classes:
                    all_idle_classes.append(wildcard)

        # 平台所有进程和对应窗口句柄
        all_sw_pids = SwInfoFunc.get_sw_all_exe_pids(sw)
        all_idle_hwnds_set = set()
        for pid in all_sw_pids:
            all_idle_hwnds_set.update(
                hwnd_utils.uiautomation_get_hwnds_by_pid_and_class_wildcards(pid, all_idle_classes))
        # 排除主窗口
        for hwnd in all_idle_hwnds_set:
            if cls._is_hwnd_a_main_wnd_of_sw(hwnd, sw):
                all_idle_hwnds_set.remove(hwnd)
        all_idle_hwnds = list(all_idle_hwnds_set)
        Printer().print_vn(f"[INFO]{sw}登录任务前已存在的登录窗口：{all_idle_hwnds}")
        if close:
            all_idle_hwnds = hwnd_utils.try_close_hwnds_in_set_and_return_remained(all_idle_hwnds_set)
            print(f"[OK]用户选择不保留!清理后剩余的登录窗口:{all_idle_hwnds}")
        return all_idle_hwnds

    @classmethod
    def get_login_size(cls, sw):
        """获取登录窗口尺寸"""
        login_wnd_class_wildcards, = subfunc_file.get_remote_cfg(sw, login_wnd_class_wildcards=None)
        if not isinstance(login_wnd_class_wildcards, list):
            return None
        # 首先检测当前是否有登录窗口, 若有则直接获取
        sw_pids = SwInfoFunc.get_sw_all_exe_pids(sw)
        for pid in sw_pids:
            login_hwnds = hwnd_utils.uiautomation_get_hwnds_by_pid_and_class_wildcards(pid, login_wnd_class_wildcards)
            if len(login_hwnds) > 0:
                login_hwnd = login_hwnds[0]
                login_wnd_details = hwnd_utils.get_hwnd_details_of_(login_hwnd)
                login_width = login_wnd_details["width"]
                login_height = login_wnd_details["height"]
                return login_width, login_height
        # 若没有登录窗口, 则打开一个登录窗口再获取
        login_hwnd, msg = cls._open_sw_origin_and_return_hwnd(sw)
        if not isinstance(login_hwnd, int):
            messagebox.showerror("错误", f"打开登录窗口失败:{msg}")
            return None
        login_wnd_details = hwnd_utils.get_hwnd_details_of_(login_hwnd)
        login_width = login_wnd_details["width"]
        login_height = login_wnd_details["height"]
        # 关闭登录窗口
        win32gui.PostMessage(login_hwnd, win32con.WM_CLOSE, 0, 0)  # 尝试关闭窗口
        return login_width, login_height

    @staticmethod
    def open_config_file(sw):
        """打开配置文件夹"""
        data_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.DATA_DIR)
        if os.path.exists(data_path):
            config_path_suffix, = subfunc_file.get_remote_cfg(sw, config_path_suffix=None)
            if config_path_suffix is None:
                messagebox.showinfo("提醒", f"{sw}平台还没有适配")
                return
            config_path = os.path.join(data_path, config_path_suffix)
            if os.path.exists(config_path):
                os.startfile(config_path)

    @staticmethod
    def clear_config_file(sw, after):
        """清除登录配置文件"""
        confirm = messagebox.askokcancel(
            "确认清除",
            f"该操作将会清空{sw}登录配置文件，请确认是否需要清除？"
        )
        if confirm:
            data_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.DATA_DIR)
            config_path_suffix, config_file_list = subfunc_file.get_remote_cfg(
                sw, config_path_suffix=None, config_file_list=None)
            if (config_path_suffix is None or config_file_list is None or
                    not isinstance(config_file_list, list) or len(config_file_list) == 0):
                messagebox.showinfo("提醒", f"{sw}平台还没有适配")
                return

            files_to_delete = []

            for file in config_file_list:
                config_path = os.path.join(data_path, str(config_path_suffix))
                file_suffix = file.split(".")[-1]
                data_files = glob.glob(os.path.join(config_path, f'*.{file_suffix}').replace("\\", "/"))
                files_to_delete.extend([f for f in data_files if not os.path.split(config_path) == config_path_suffix])
            if len(files_to_delete) > 0:
                # 删除这些文件
                file_utils.move_files_to_recycle_bin(files_to_delete)
                print(f"已删除: {files_to_delete}")
                try:
                    pass
                except Exception as e:
                    logger.error(f"无法删除 {files_to_delete}: {e}")
            after()
            printer.print_last(f"清除{sw}登录配置完成！")

    @staticmethod
    def open_dll_dir(sw):
        """打开注册表所在文件夹，并将光标移动到文件"""
        dll_dir = SwInfoFunc.try_get_path_of_(sw, LocalCfg.DLL_DIR)
        if os.path.exists(dll_dir):
            dll_dir_check_suffix, = subfunc_file.get_remote_cfg(sw, dll_dir_check_suffix=None)
            # 打开文件夹
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.CurrentDirectory = dll_dir
            if dll_dir_check_suffix is not None:
                shell.Run(f'explorer /select,{dll_dir_check_suffix}')


class SwInfoUtils:
    @staticmethod
    def is_valid_sw_path(path_type, sw, path) -> bool:
        try:
            if path is None or path == "":
                return False
            print(path_type)
            path = str(path).replace('\\', '/')
            if path_type == LocalCfg.INST_PATH:
                executable, = subfunc_file.get_remote_cfg(sw, executable=None)
                path_ext = os.path.splitext(path)[1].lower()
                exe_ext = os.path.splitext(executable)[1].lower()
                return path_ext == exe_ext
            elif path_type == LocalCfg.DATA_DIR:
                suffix, = subfunc_file.get_remote_cfg(sw, data_dir_check_suffix=None)
                return os.path.isdir(os.path.join(path, str(suffix)))
            elif path_type == LocalCfg.DLL_DIR:
                suffix, = subfunc_file.get_remote_cfg(sw, dll_dir_check_suffix=None)
                return os.path.isfile(os.path.join(path, suffix))
            return False
        except Exception as e:
            print(e)
            return False

    @staticmethod
    def get_sw_install_path_from_process(sw: str) -> list:
        executable, = subfunc_file.get_remote_cfg(sw, executable=None)
        results = []
        for process in psutil.process_iter(['name', 'exe']):
            if process.name() == executable:
                path = process.exe().replace('\\', '/')
                results.append(path)
                logger.info(f"通过查找进程方式获取了安装地址：{path}")
                break
        return results

    @staticmethod
    def get_sw_install_path_from_machine_register(sw: str) -> list:
        sub_key, executable = subfunc_file.get_remote_cfg(
            sw, mac_reg_sub_key=None, executable=None)
        results = []
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_key)

            found_path = winreg.QueryValueEx(key, "InstallLocation")[0].replace('\\', '/')
            winreg.CloseKey(key)
            logger.info(f"通过设备注册表获取了安装地址：{found_path}")
            if found_path:
                results.append(os.path.join(found_path, executable).replace('\\', '/'))

            found_path = winreg.QueryValueEx(key, "DisplayIcon")[0].replace('\\', '/')
            winreg.CloseKey(key)
            logger.info(f"通过设备注册表获取了安装地址：{found_path}")
            if found_path:
                results.append(found_path.replace('\\', '/'))
        except Exception as e:
            logger.error(e)
        return results

    @staticmethod
    def get_sw_install_path_from_user_register(sw: str) -> list:
        sub_key, executable = subfunc_file.get_remote_cfg(
            sw, user_reg_sub_key=None, executable=None)
        results = []
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key)
            found_path = winreg.QueryValueEx(key, "InstallPath")[0].replace('\\', '/')
            winreg.CloseKey(key)
            logger.info(f"通过用户注册表获取了安装地址：{found_path}")
            if found_path:
                results.append(os.path.join(found_path, executable).replace('\\', '/'))
        except Exception as we:
            logger.warning(we)
        return results

    @staticmethod
    def get_sw_install_path_by_guess(sw: str) -> list:
        suffix, = subfunc_file.get_remote_cfg(sw, inst_path_guess_suffix=None)
        if suffix is None:
            return []
        guess_paths = [
            os.path.join(os.environ.get('ProgramFiles'), suffix).replace('\\', '/'),
            os.path.join(os.environ.get('ProgramFiles(x86)'), suffix).replace('\\', '/'),
        ]
        return guess_paths

    @staticmethod
    def get_sw_data_dir_from_user_register(sw: str) -> list:
        sub_key, dir_name = subfunc_file.get_remote_cfg(
            sw, user_reg_sub_key=None, data_dir_name=None)
        results = []
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, "FileSavePath")
            winreg.CloseKey(key)
            value = os.path.join(value, dir_name).replace('\\', '/')
            results.append(value)
        except Exception as we:
            logger.warning(we)
        return results

    @staticmethod
    def get_sw_data_dir_by_guess(sw: str) -> list:
        data_dir_name, data_dir_guess_suffix = subfunc_file.get_remote_cfg(
            sw, data_dir_name=None, data_dir_guess_suffix=None)
        if data_dir_name is None or data_dir_guess_suffix is None:
            return []
        guess_paths = [
            os.path.join(os.path.expanduser('~'), 'Documents', data_dir_name).replace('\\', '/'),
        ]
        return guess_paths

    @staticmethod
    def get_sw_dll_dir_by_memo_maps(sw: str) -> list:
        dll_name, executable = subfunc_file.get_remote_cfg(
            sw, dll_dir_check_suffix=None, executable=None)
        results = []
        exe_pids_dict = process_utils.psutil_get_pids_by_wildcards_and_grouping_to_dict([executable])
        if not isinstance(exe_pids_dict, dict) or len(exe_pids_dict.get(executable, [])) == 0:
            logger.warning(f"没有运行该程序。")
            return []
        else:
            process_id = exe_pids_dict.get(executable, [])[0]
            try:
                for f in psutil.Process(process_id).memory_maps():
                    normalized_path = f.path.replace('\\', '/')
                    if normalized_path.endswith(dll_name):
                        dll_dir_path = os.path.dirname(normalized_path)
                        results.append(dll_dir_path)
            except psutil.AccessDenied:
                logger.error(f"无法访问进程ID为 {process_id} 的内存映射文件，权限不足。")
            except psutil.NoSuchProcess:
                logger.error(f"进程ID为 {process_id} 的进程不存在或已退出。")
            except Exception as e:
                logger.error(f"发生意外错误: {e}")
        return results

    @staticmethod
    def _get_replacement_pairs(regex, repl_bytes, data):
        """返回(匹配的串,相应替换后的串)元祖列表"""
        matches = list(regex.finditer(data))
        replacement_pairs = []
        for match in matches:
            original = match.group()  # 原始匹配的字节串
            replaced = regex.sub(repl_bytes, original)  # 替换后的字节串
            replacement_pairs.append((original, replaced))

        return replacement_pairs

    @staticmethod
    def bytes_to_hex_str(byte_data: bytes) -> str:
        """将 bytes 转换为 'xx xx xx' 形式的十六进制字符串"""
        return ' '.join([f"{byte:02x}" for byte in byte_data])

    @staticmethod
    def search_patterns_and_replaces_by_features(dll_path, features_tuple: tuple):
        """
        从特征列表中搜索特征码并替换
        :param dll_path: DLL文件
        :param features_tuple: 特征码列表二元组(原始特征码列表，补丁特征码列表)
        :return: 替换后的二进制数据
        """
        # 检查特征码长度是否一致
        original_features, modified_features = features_tuple
        if len(original_features) != len(modified_features):
            print(f"[ERR] Original and modified features length mismatch")
            return None

        result_dict = {
            "original": [],
            "modified": []
        }

        # data = b'\x89\xF3\x12\xA0\x75\x21\x48\xB8\x72\x65\x76\x6F\x6B\x65\x6D\x73\x48\x89\x05\x3A\xDB\x7F\x00\x66\xC7\x05\x44\x12\x91\xFF\x67\x00\xC6\x05\x88\x42\x33\x11\x01\x48\x8D\xF0\xCC\x21\x9E'
        with open(dll_path, "rb") as f:
            data = f.read()
        # print(f"原始数据: {SwInfoUtils.bytes_to_hex_str(data)}")
        for original_feature, modified_feature in zip(original_features, modified_features):
            print("--------------------------------------------------------")
            print(f"原始特征码: {original_feature}")
            print(f"补丁特征码: {modified_feature}")
            # print("分词器处理:去除末尾的省略号;若开头有省略号,则识别为{省略号}")
            listed_original_hex = custom_wildcard_tokenize(original_feature)
            listed_modified_hex = custom_wildcard_tokenize(modified_feature)
            # print("判断类型:若...在开头,则以??补充至相同长度;...仅能出现在开头或不存在,否则报错")
            if listed_modified_hex[0] is ...:
                listed_modified_hex = ["??"] * (
                        len(listed_original_hex) - len(listed_modified_hex) + 1) + listed_modified_hex[1:]
            else:
                if ... in listed_original_hex:
                    print(f"[ERR] Wildcard <{patt2hex(listed_original_hex)}> has invalid token ...")
                    continue
                elif ... in listed_modified_hex:
                    print(f"[ERR] Wildcard <{patt2hex(listed_modified_hex)}> has invalid token ...")
                    continue
            # print("对...不在开头的情况,在末尾补充??至相同长度")
            if len(listed_modified_hex) < len(listed_original_hex):
                listed_modified_hex += ["??"] * (len(listed_original_hex) - len(listed_modified_hex))
            if len(listed_modified_hex) != len(listed_original_hex):
                print(f"[ERR] Pattern and listed_modified_hex length mismatch")
                continue
            print(f"> 特征码翻译: {patt2hex(listed_original_hex, 0)} => {patt2hex(listed_modified_hex, 0)}")

            # print(f"构建正则表达式和替换模式：对原始的:将??替换为(.);对补丁和替换:非??则保持,对??的话,若原始为??,则替换为(.)和补位符号,否则摘抄原始值")
            original_regex_bytes = b""
            modified_regex_bytes = b""
            repl_bytes = b""
            group_count = 1
            repl_pos_list = []  # 索引列表
            cur_pos = 0
            for p, r in zip(listed_original_hex, listed_modified_hex):
                if p == "??":
                    original_regex_bytes += b"(.)"
                    if r == "??":
                        repl_bytes += b"\\" + str(group_count).encode()
                        modified_regex_bytes += b"(.)"
                    elif r == "!!":
                        repl_bytes += b"!"
                        modified_regex_bytes += re.escape(b"!")
                        repl_pos_list.append(cur_pos)
                    else:
                        repl_bytes += bytes.fromhex(r)
                        modified_regex_bytes += re.escape(bytes.fromhex(r))
                    group_count += 1
                else:
                    original_regex_bytes += re.escape(bytes.fromhex(p))
                    if r == "??":
                        repl_bytes += bytes.fromhex(p)
                        modified_regex_bytes += re.escape(bytes.fromhex(p))
                    elif r == "!!":
                        repl_bytes += b"!"
                        modified_regex_bytes += re.escape(b"!")
                        repl_pos_list.append(cur_pos)
                    else:
                        repl_bytes += bytes.fromhex(r)
                        modified_regex_bytes += re.escape(bytes.fromhex(r))
                cur_pos += 1
            print("构建匹配模式：")
            print(f"original_regex_bytes: {original_regex_bytes}")
            print(f"modified_regex_bytes: {modified_regex_bytes}")
            print(f"repl_bytes: {repl_bytes}")
            # print(f"regex_hex: {bytes_to_hex_str(original_regex_bytes)}")
            # print(f"patched_hex: {bytes_to_hex_str(modified_regex_bytes)}")
            # print(f"repl_hex: {bytes_to_hex_str(repl_bytes)}")
            original_regex = re.compile(original_regex_bytes, re.DOTALL)

            pairs = SwInfoUtils._get_replacement_pairs(original_regex, repl_bytes, data)
            if len(pairs) == 0:
                print("未识别到特征码")
                return None
            for pair in pairs:
                original, modified = pair
                original_hex = SwInfoUtils.bytes_to_hex_str(original)
                modified_hex = SwInfoUtils.bytes_to_hex_str(modified)
                # repl_pos_list 中记录的是第几个字节需要替换
                for pos in repl_pos_list:
                    hex_pos = pos * 3  # 每个字节对应两个 hex 字符 和 一个 空格
                    modified_hex = modified_hex[:hex_pos] + "!!" + modified_hex[hex_pos + 2:]

                print("识别到：")
                print(f"Original: {original_hex}")
                print(f"Modified: {modified_hex}")
                result_dict["original"].append(original_hex)
                result_dict["modified"].append(modified_hex)

        return result_dict

    @staticmethod
    def _create_path_finders_of_(path_tag) -> list:
        """定义方法列表"""
        if path_tag == LocalCfg.INST_PATH:
            return [
                SwInfoUtils.get_sw_install_path_from_process,
                # ((lambda sw: []) if ignore_local_record
                #  else SwInfoUtils._create_sw_method_to_get_path_from_local_record(LocalCfg.INST_PATH)),
                SwInfoUtils.get_sw_install_path_from_machine_register,
                SwInfoUtils.get_sw_install_path_from_user_register,
                SwInfoUtils.get_sw_install_path_by_guess,
            ]
        elif path_tag == LocalCfg.DATA_DIR:
            return [
                # ((lambda sw: []) if ignore_local_record
                #  else SwInfoUtils._create_sw_method_to_get_path_from_local_record(LocalCfg.DATA_DIR)),
                SwInfoUtils.get_sw_data_dir_from_user_register,
                SwInfoUtils.get_sw_data_dir_by_guess,
                SwInfoUtils._get_sw_data_dir_from_other_sw,
            ]
        elif path_tag == LocalCfg.DLL_DIR:
            return [
                # ((lambda sw: []) if ignore_local_record
                #  else SwInfoUtils._create_sw_method_to_get_path_from_local_record(LocalCfg.DLL_DIR)),
                SwInfoUtils.get_sw_dll_dir_by_memo_maps,
                SwInfoUtils._get_sw_dll_dir_by_files,
            ]
        else:
            return [
                (lambda sw: [])
            ]

    @staticmethod
    def _create_check_method_of_(path_type):
        """定义检查方法"""

        def check_sw_path_func(sw, path):
            return SwInfoUtils.is_valid_sw_path(path_type, sw, path)

        return check_sw_path_func

    # @staticmethod
    # def _create_sw_method_to_get_path_from_local_record(path_tag):
    #     """
    #     创建路径查找函数
    #     :param path_tag: 路径类型
    #     :return: 路径查找函数
    #     """
    #
    #     def get_sw_path_from_local_record(sw: str) -> list:
    #         path = subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, path_tag)
    #         return [path] if path is not None else []
    #
    #     return get_sw_path_from_local_record

    @staticmethod
    def try_detect_path(sw: str, path_type: str) \
            -> Union[Tuple[bool, bool, Union[None, str]]]:
        """
        获取微信数据路径的结果元组
        :param path_type: 路径类型
        :param sw: 平台
        :return: 成功，是否改变，结果
        """
        success = False
        changed = False
        result = None

        path_finders = SwInfoUtils._create_path_finders_of_(path_type)
        check_sw_path_func = SwInfoUtils._create_check_method_of_(path_type)
        if check_sw_path_func is None:
            return success, changed, result

        # 尝试各种方法
        for index, finder in enumerate(path_finders):
            if finder is None:
                continue
            paths = finder(sw=sw)
            logger.info(f"使用{finder.__name__}方法得到{sw}的路径列表：{paths}")
            path_list = list(paths)  # 如果确定返回值是可迭代对象，强制转换为列表
            if not path_list:
                continue
            # 检验地址并退出所有循环
            for path in path_list:
                if check_sw_path_func(sw, path):
                    print(f"通过第 {index + 1} 个方法 {finder.__name__} 获得结果 {path}")
                    standardized_path = os.path.abspath(path).replace('\\', '/')
                    changed = subfunc_file.save_a_setting_and_callback(sw, path_type, standardized_path)
                    result = standardized_path
                    success = True
                    break
            if success:
                break

        return success, changed, result

    @staticmethod
    def _get_sw_data_dir_from_other_sw(sw: str) -> list:
        """通过其他软件的方式获取微信数据文件夹"""
        data_dir_name, = subfunc_file.get_remote_cfg(
            sw, data_dir_name=None)
        paths = []
        if data_dir_name is None or data_dir_name == "":
            paths = []
        # 微信和新版微信的数据文件夹通常会选择在同一级目录, 微信是WeChat Files, 新版是xwechat_files
        other_sws = [SW.WECHAT, SW.WEIXIN]
        if sw in other_sws:
            for osw in other_sws:
                if sw == osw:
                    continue
                other_path = SwInfoFunc.get_saved_path_of_(osw, LocalCfg.DATA_DIR)
                if other_path is not None:
                    return [os.path.join(os.path.dirname(other_path), data_dir_name).replace('\\', '/')]
        # QQ, 新版QQ, TIM使用同一个文件夹作为数据文件夹
        other_sws = [SW.QQNT, SW.TIM, SW.QQ]
        if sw in other_sws:
            for osw in other_sws:
                if sw == osw:
                    continue
                other_path = SwInfoFunc.get_saved_path_of_(osw, LocalCfg.DATA_DIR)
                if other_path is not None:
                    return [other_path]
        return paths

    @staticmethod
    def _get_sw_dll_dir_by_files(sw: str) -> list:
        """通过文件遍历方式获取dll文件夹"""
        dll_name, = subfunc_file.get_remote_cfg(
            sw, dll_dir_check_suffix=None)
        install_path = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.INST_PATH)
        if install_path is not None and install_path != "":
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


class SwOperatorUtils:
    pass
