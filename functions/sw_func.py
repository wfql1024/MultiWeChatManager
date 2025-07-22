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
from public_class.enums import LocalCfg, SW, AccKeys, MultirunMode, RemoteCfg
from public_class.global_members import GlobalMembers
from resources import Config, Strings, Constants
from utils import file_utils, process_utils, handle_utils, hwnd_utils, image_utils
from utils.better_wx.inner_utils import patt2hex, custom_wildcard_tokenize
from utils.encoding_utils import VersionUtils, PathUtils, StringUtils
from utils.file_utils import DllUtils
from utils.logger_utils import mylogger as logger, Printer, Logger
from utils.logger_utils import myprinter as printer


class SwInfoFunc:
    """
    当前版本，所使用的适配表结构如下：
    平台sw -> 补丁模式mode -> 分支(精确precise,特征feature,说明channel) -> 版本号 -> 频道 -> 路径地址 -> 特征码
    其中,
        precise: 精确版本适配，只适配当前版本. 结构为 版本号 -> 频道 -> 特征码
        feature: 特征码适配，适配当前版本及其兼容版本. 结构为 版本号 -> 频道 -> 特征码
        channel: 频道，区分不同特征/作者的适配. 结构为 频道 -> (标题,说明,作者)
    """

    @staticmethod
    def resolve_sw_path(sw, addr: str):
        """解析补丁路径, 路径中可以包含%包裹的引用地址, 如%dll_dir%/WeChatWin.dll"""
        resolved_parts = []
        for part in addr.replace("\\", "/").split("/"):
            if not part:
                continue
            if part.startswith("%") and part.endswith("%") and len(part) > 2:
                var_name = part[1:-1]
                try:
                    resolved = SwInfoFunc.get_saved_path_of_(sw, var_name)
                    resolved_parts.append(resolved.strip("/\\"))
                except KeyError:
                    raise ValueError(f"路径变量未定义: %{var_name}%")
            else:
                resolved_parts.append(part)
        return "/".join(resolved_parts)

    @staticmethod
    def _identify_multi_state_patching_of_files_in_channel(sw, channel_addresses_dict):
        """对于非二元状态切换的, 只需要检测原始串即可"""
        addr_res_dict = {}
        for addr in channel_addresses_dict.keys():
            # Printer().debug(f"检查文件地址 {addr} 的特征码适配")
            patch_file = SwInfoFunc.resolve_sw_path(sw, addr)
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

    @staticmethod
    def _identify_binary_state_patching_of_files_in_channel(sw, channel_addresses_dict) -> dict:
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
            patch_file = SwInfoFunc.resolve_sw_path(sw, addr)
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

    @staticmethod
    def _identify_patching_of_channels_in_ver(sw, ver_channels_dict, multi_state=False) -> dict:
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
                addr_res_dict = SwInfoFunc._identify_multi_state_patching_of_files_in_channel(sw, channel_files_dict)
            else:
                addr_res_dict = SwInfoFunc._identify_binary_state_patching_of_files_in_channel(sw, channel_files_dict)
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

    @staticmethod
    def _identify_dll_by_precise_channel_in_mode_dict(
            sw, mode_branches_dict, multi_state=False) -> Tuple[Optional[dict], str]:
        """通过精确版本分支进行识别dll状态"""
        cur_sw_ver = SwInfoFunc.calc_sw_ver(sw)
        if cur_sw_ver is None:
            return None, f"错误：未知当前版本"
        if "precise" not in mode_branches_dict:
            return None, f"错误：该模式没有精确版本分支用以适配"
        precise_vers_dict = mode_branches_dict["precise"]
        if cur_sw_ver not in precise_vers_dict:
            return None, f"错误：精确分支中未找到版本{cur_sw_ver}的适配"
        ver_channels_dict = precise_vers_dict[cur_sw_ver]
        channel_res_dict = SwInfoFunc._identify_patching_of_channels_in_ver(sw, ver_channels_dict, multi_state)
        if len(channel_res_dict) == 0:
            return None, f"错误：该版本{cur_sw_ver}的适配在本地平台中未找到"
        return channel_res_dict, f"成功：找到版本{cur_sw_ver}的适配"

    @staticmethod
    def _update_adaptation_from_remote_to_cache(sw, mode):
        """根据远程表内容更新额外表"""
        config_data = subfunc_file.read_remote_cfg_in_rules()
        if not config_data:
            return
        remote_mode_branches_dict, = subfunc_file.get_remote_cfg(sw, **{mode: None})
        if remote_mode_branches_dict is None:
            return
        # 尝试寻找兼容版本并添加到额外表中
        cur_sw_ver = SwInfoFunc.calc_sw_ver(sw)
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
                        patch_file = SwInfoFunc.resolve_sw_path(sw, addr)
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

    @staticmethod
    def _identify_dll_by_cache_cfg(sw, mode, multi_state=False) -> Tuple[Optional[dict], str]:
        """从缓存表中获取"""
        try:
            mode_branches_dict, = subfunc_file.get_cache_cfg(sw, **{mode: None})
            if mode_branches_dict is None:
                return None, f"错误：平台未适配{mode}"
            return SwInfoFunc._identify_dll_by_precise_channel_in_mode_dict(sw, mode_branches_dict, multi_state)
        except Exception as e:
            Logger().error(e)
            return None, f"错误：{e}"

    @staticmethod
    def identify_dll(sw, mode, multi_state=False) -> Tuple[Optional[dict], str]:
        """
        检查当前补丁状态，返回结果字典,若没有适配则返回None
        结果字典格式: {channel1: (status, msg, addr_res_dict), channel2: (status, msg, addr_res_dict) ...}
        地址字典addr_res_dict格式: {addr1: (status, msg, patch_path, original, modified),
                                    addr2: (status, msg, patch_path, original, modified) ...}
        """
        dll_dir = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.DLL_DIR)
        if dll_dir is None:
            return None, "错误：没有找到dll目录"
        SwInfoFunc._update_adaptation_from_remote_to_cache(sw, mode)
        mode_channel_res_dict, msg = SwInfoFunc._identify_dll_by_cache_cfg(sw, mode, multi_state)
        return mode_channel_res_dict, msg

    @staticmethod
    def clear_adaptation_cache(sw, mode):
        """清除当前版本模式的适配缓存"""
        curr_ver = SwInfoFunc.calc_sw_ver(sw)
        subfunc_file.clear_some_extra_cfg(sw, mode, "precise", curr_ver)

    @staticmethod
    def get_available_coexist_mode(sw):
        """选择一个可用的共存构造模式, 优先返回用户选择的, 若其不可用则返回可用的第一个模式"""
        user_coexist_channel = subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, LocalCfg.COEXIST_MODE)
        channel_res_dict, msg = SwInfoFunc.identify_dll(sw, RemoteCfg.COEXIST, True)
        if isinstance(channel_res_dict, dict):
            if user_coexist_channel in channel_res_dict:
                return user_coexist_channel
            return list(channel_res_dict.keys())[0]
        return None

    @staticmethod
    def detect_path_of_(sw, path_type, ignore_local_record=False):
        """获取指定路径, ignore_local_record为True时忽略本地记录"""
        _, _, result = SwInfoUtils.try_get_path(sw, path_type, ignore_local_record)
        return result

    @staticmethod
    def get_saved_path_of_(sw, path_type) -> Optional[str]:
        """优先获取已保存的路径, 若没有则通过方法自动搜寻"""
        path, = subfunc_file.get_settings(sw, **{path_type: None})
        if PathUtils.is_valid_path(path):
            return path
        return SwInfoFunc.detect_path_of_(sw, path_type, ignore_local_record=True)

    @staticmethod
    def calc_sw_ver(sw) -> Optional[str]:
        """获取软件版本"""
        try:
            exec_path = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.INST_PATH)
            cur_sw_ver = file_utils.get_file_version(exec_path)
            if cur_sw_ver is not None:
                return cur_sw_ver
            dll_dir = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.DLL_DIR)
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

    @staticmethod
    def get_sw_all_exe_pids(sw) -> list:
        """获得平台所有进程的pid"""
        executable_wildcards, = subfunc_file.get_remote_cfg(
            sw,
            executable_wildcards=None,
        )
        inst_path = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.INST_PATH)
        inst_dir = os.path.dirname(inst_path)
        pids = []
        if isinstance(executable_wildcards, list):
            pids.extend(process_utils.psutil_get_pids_by_wildcards(executable_wildcards))
        pids = process_utils.remove_child_pids(pids)
        pids = process_utils.remove_pids_not_in_path(pids, inst_dir)
        return pids

    @staticmethod
    def record_sw_pid_mutex_dict_when_start_login(sw) -> dict:
        """在该平台登录之前,存储 pid 和 互斥体 的映射关系字典"""
        pids = SwInfoFunc.get_sw_all_exe_pids(sw)
        pid_mutex_dict = {}
        for pid in pids:
            pid_mutex_dict[pid] = True
        subfunc_file.update_sw_acc_data(sw, **{AccKeys.PID_MUTEX: pid_mutex_dict})
        return pid_mutex_dict


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
        subfunc_file.clear_some_acc_data(sw, AccKeys.PID_MUTEX)
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

    @staticmethod
    def switch_dll(sw, mode, channel) -> Tuple[Optional[bool], str]:
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
            sw_exe_path = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.INST_PATH)
            if not sw_exe_path:
                return False, "该平台暂未适配"
            # 提醒用户手动终止微信进程
            answer = SwOperator._ask_for_manual_terminate_or_force(sw_exe_path)
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
                    SwOperator._backup_dll(addr_res_tuple_dict)
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
        """等待所有窗口关闭后,主线程执行 callback"""
        root = GlobalMembers.root_class.root
        hwnd_utils.wait_hwnds_close(hwnds, timeout)
        if callable(callback):
            root.after(0, callback)

    @staticmethod
    def _open_sw_origin_and_return_hwnd(sw):
        """打开平台原始程序并返回窗口hwnd"""
        # 获取需要的数据
        root_class = GlobalMembers.root_class
        multirun_mode = root_class.sw_classes[sw].multirun_mode
        login_wnd_class, = subfunc_file.get_remote_cfg(
            sw, login_wnd_class=None)
        if login_wnd_class is None:
            messagebox.showinfo("错误", "尚未适配！")
            return None
        all_excluded_hwnds = []
        # 关闭多余的多开器,记录已经存在的窗口 -------------------------------------------------------------------
        SwOperator.kill_sw_multiple_processes(sw)
        remained_idle_wnd_list = SwOperator.get_idle_login_wnd_and_close_if_necessary(sw)
        all_excluded_hwnds.extend(remained_idle_wnd_list)
        # 检查所有pid及互斥体情况 -------------------------------------------------------------------
        SwInfoFunc.record_sw_pid_mutex_dict_when_start_login(sw)
        sw_proc, sub_proc = SwOperator.open_sw(sw, multirun_mode)
        sw_proc_pid = sw_proc.pid if sw_proc else None
        # 等待打开窗口并获取hwnd *******************************************************************
        sw_hwnd, class_name = hwnd_utils.wait_hwnd_exclusively_by_pid_and_class_wildcards(
            all_excluded_hwnds, sw_proc_pid, [login_wnd_class])
        if sub_proc:
            sub_proc.terminate()
        Printer().debug(sw_hwnd)
        return sw_hwnd

    @staticmethod
    def _manual_login_origin(sw):
        """手动登录原生平台"""
        root_class = GlobalMembers.root_class
        multirun_mode = GlobalMembers.root_class.sw_classes[sw].multirun_mode
        start_time = time.time()
        sw_hwnd = SwOperator._open_sw_origin_and_return_hwnd(sw)
        if isinstance(sw_hwnd, int):
            subfunc_file.set_pid_mutex_all_values_to_false(sw)
            subfunc_file.update_statistic_data(sw, 'manual', '_', multirun_mode, time.time() - start_time)
            print(f"打开了登录窗口{sw_hwnd}")
        else:
            logger.warning(f"打开失败，请重试！")
            messagebox.showerror("错误", "手动登录失败，请重试")
        callback = lambda: root_class.login_ui.refresh_frame(sw)
        SwOperator._wait_hwnds_close_and_do_in_root([sw_hwnd], callback=callback)

    @staticmethod
    def _manual_login_coexist(sw):
        """手动登录共存平台,按顺序,登录第一个还未打开的共存程序,若都已经打开,则创造一个新的共存程序后打开"""
        start_time = time.time()
        root_class = GlobalMembers.root_class
        coexist_channel = SwInfoFunc.get_available_coexist_mode(sw)
        if not isinstance(coexist_channel, str):
            messagebox.showinfo("错误", f"没有可用的共存构造模式!")
            return
        exe_wildcard, sequence = subfunc_file.get_remote_cfg(
            sw, "coexist", "channel", coexist_channel,
            exe_wildcard=None, sequence=None)
        if not isinstance(exe_wildcard, str) or not isinstance(sequence, str):
            messagebox.showinfo("错误", f"尚未适配[exe_wildcard, sequence]!")
            return
        login_wnd_wildcards, = subfunc_file.get_remote_cfg(
            sw, login_wnd_class_wildcards=None)
        if not isinstance(login_wnd_wildcards, list):
            messagebox.showinfo("错误", "尚未适配[login_wnd_wildcards]!")
            return
        all_excluded_hwnds = []
        # 关闭多余的多开器,记录已经存在的窗口 -------------------------------------------------------------------
        SwOperator.kill_sw_multiple_processes(sw)
        remained_idle_wnd_list = SwOperator.get_idle_login_wnd_and_close_if_necessary(sw)
        all_excluded_hwnds.extend(remained_idle_wnd_list)
        # 检查所有pid及互斥体情况 -------------------------------------------------------------------
        SwInfoFunc.record_sw_pid_mutex_dict_when_start_login(sw)
        sw_proc = None
        for s in sequence:
            exe_name = exe_wildcard.replace("?", s)
            # 查找是否有exe_name进程
            exe_pids = process_utils.psutil_get_pids_by_wildcards([exe_name])
            if len(exe_pids) > 0:
                continue
            inst_path = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.INST_PATH)
            inst_dir = os.path.dirname(inst_path)
            need_open_exe = os.path.join(inst_dir, exe_name)
            if not os.path.exists(need_open_exe):
                # 建立这个标号的共存程序
                if messagebox.askokcancel("错误", f"不存在{need_open_exe}!是否创建?"):
                    SwOperator.create_coexist_exe(sw, s)
                    if os.path.isfile(need_open_exe):
                        sw_proc = process_utils.create_process_without_admin(need_open_exe)
                    break
                else:
                    return
            if os.path.isfile(need_open_exe):
                sw_proc = process_utils.create_process_without_admin(need_open_exe)
                break
        sw_proc_pid = sw_proc.pid if sw_proc else None
        # 等待打开窗口并获取hwnd *******************************************************************
        sw_hwnd, class_name = hwnd_utils.wait_hwnd_exclusively_by_pid_and_class_wildcards(
            all_excluded_hwnds, sw_proc_pid, login_wnd_wildcards)
        Printer().debug(sw_hwnd)

        if isinstance(sw_hwnd, int):
            subfunc_file.set_pid_mutex_all_values_to_false(sw)
            subfunc_file.update_statistic_data(sw, 'manual', '_', MultirunMode.BUILTIN, time.time() - start_time)
            print(f"打开了登录窗口{sw_hwnd}")
        else:
            logger.warning(f"打开失败，请重试！")
            messagebox.showerror("错误", "手动登录失败，请重试")
        callback = lambda: root_class.login_ui.refresh_frame(sw)
        SwOperator._wait_hwnds_close_and_do_in_root([sw_hwnd], callback=callback)

    @staticmethod
    def create_coexist_exe(sw, s=None):
        """创建共存程序"""
        if s is None:
            coexist_channel = SwInfoFunc.get_available_coexist_mode(sw)
            exe_wildcard, sequence = subfunc_file.get_remote_cfg(
                sw, "coexist", "channel", coexist_channel,
                exe_wildcard=None, sequence=None)
            for sq in sequence:
                exe_name = exe_wildcard.replace("?", sq)
                # 查找是否有exe_name进程
                exe_pids = process_utils.psutil_get_pids_by_wildcards([exe_name])
                if len(exe_pids) > 0:
                    continue
                inst_path = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.INST_PATH)
                inst_dir = os.path.dirname(inst_path)
                need_open_exe = os.path.join(inst_dir, exe_name)
                if not os.path.exists(need_open_exe):
                    s = sq
                    break

        coexist_channel = SwInfoFunc.get_available_coexist_mode(sw)
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


    @staticmethod
    def start_thread_to_manual_login_origin(sw):
        """建议使用此方式,以线程的方式手动登录,避免阻塞"""
        threading.Thread(
            target=SwOperator._manual_login_origin,
            args=(sw,)
        ).start()

    @staticmethod
    def start_thread_to_manual_login_coexist(sw):
        """建议使用此方式,以线程的方式手动登录,避免阻塞"""
        threading.Thread(
            target=SwOperator._manual_login_coexist,
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
            has_mutex, = subfunc_file.get_sw_acc_data(sw, AccKeys.PID_MUTEX, **{f"{pid}": None})
            if has_mutex is None:
                subfunc_file.update_sw_acc_data(sw, AccKeys.PID_MUTEX, **{f"{pid}": True})
                has_mutex_dict.update({pid: has_mutex})
        print(f"获取互斥体情况完成!互斥体列表：{has_mutex_dict}")
        return has_mutex_dict

    @staticmethod
    def _kill_mutex_by_forced_inner_mode(sw, multirun_mode):
        executable_name, lock_handles, cfg_handles = subfunc_file.get_remote_cfg(
            sw, executable=None, mutant_handle_infos=None, cfg_handle_regex_list=None)
        # ————————————————————————————————python————————————————————————————————
        if multirun_mode == MultirunMode.BUILTIN:
            pids = SwInfoFunc.get_sw_all_exe_pids(sw)
            handle_regex_list, = subfunc_file.get_remote_cfg(sw, mutant_handle_infos=None)
            if handle_regex_list is None:
                return True
            handle_names = [handle["handle_name"] for handle in handle_regex_list]
            if handle_names is None or len(handle_names) == 0:
                return True
            if len(pids) > 0:
                success = handle_utils.pywinhandle_close_handles(
                    handle_utils.pywinhandle_find_handles_by_pids_and_handle_names(
                        pids,
                        handle_names
                    )
                )
                return success
            return True
        # ————————————————————————————————handle————————————————————————————————
        else:
            success, success_lists = handle_utils.close_sw_mutex_by_handle(
                Config.HANDLE_EXE_PATH, executable_name, lock_handles)
            if len(success_lists) > 0:
                print(f"成功关闭：{success_lists}")
            return success

    @staticmethod
    def _kill_mutex_by_inner_mode(sw, multirun_mode):
        """关闭平台进程的所有互斥体，如果不选择python模式，则使用handle模式"""
        # ————————————————————————————————builtin————————————————————————————————
        mutant_handle_wildcards, = subfunc_file.get_remote_cfg(
            sw, mutant_handle_wildcards=None)
        if multirun_mode == MultirunMode.BUILTIN:
            has_mutex_dict = subfunc_file.get_sw_acc_data(sw, AccKeys.PID_MUTEX)
            pids_has_mutex = [pid for pid in has_mutex_dict.keys() if has_mutex_dict[pid] is True]
            pids_has_mutex = [int(x) if isinstance(x, str) and x.isdigit() else x for x in pids_has_mutex]  # 将字符串转换为整数
            if len(pids_has_mutex) > 0 and len(mutant_handle_wildcards) > 0:
                Printer().print_vn(f"[INFO]以下进程含有互斥体：{has_mutex_dict}", )
                handle_infos = handle_utils.pywinhandle_find_handles_by_pids_and_handle_name_wildcards(
                    pids_has_mutex, mutant_handle_wildcards)
                Printer().debug(f"[INFO]查询到互斥体：{handle_infos}")
                success = handle_utils.pywinhandle_close_handles(
                    handle_infos
                )
                return success
            return True
        # ————————————————————————————————handle————————————————————————————————
        else:
            executable_name, lock_handles = subfunc_file.get_remote_cfg(
                sw, executable=None, mutant_handle_infos=None)
            success, success_lists = handle_utils.close_sw_mutex_by_handle(
                Config.HANDLE_EXE_PATH, executable_name, lock_handles)
            return success

    @staticmethod
    def _open_sw_without_freely_multirun(sw, multirun_mode):
        """非全局多开模式下打开微信"""
        start_time = time.time()
        proc = None
        sub_proc = None
        sw_path = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.INST_PATH)
        # ————————————————————————————————WeChatMultiple_Anhkgg.exe————————————————————————————————
        if multirun_mode == "WeChatMultiple_Anhkgg.exe":
            sub_proc = process_utils.create_process_without_admin(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{multirun_mode}",
                creation_flags=subprocess.CREATE_NO_WINDOW
            )
        # ————————————————————————————————WeChatMultiple_lyie15.exe————————————————————————————————
        elif multirun_mode == "WeChatMultiple_lyie15.exe":
            sub_proc = process_utils.create_process_without_admin(
                f"{Config.PROJ_EXTERNAL_RES_PATH}/{multirun_mode}"
            )
            sub_exe_hwnd = hwnd_utils.wait_hwnd_by_class("WTWindow", 8)
            print(f"子程序窗口：{sub_exe_hwnd}")
            if sub_exe_hwnd:
                button_handle = hwnd_utils.get_child_hwnd_list_of_(
                    sub_exe_hwnd
                )[1]
                if button_handle:
                    button_details = hwnd_utils.get_hwnd_details_of_(button_handle)
                    button_cx = int(button_details["width"] / 2)
                    button_cy = int(button_details["height"] / 2)
                    hwnd_utils.do_click_in_wnd(button_handle, button_cx, button_cy)
        # ————————————————————————————————handle————————————————————————————————
        elif multirun_mode == MultirunMode.HANDLE or multirun_mode == MultirunMode.BUILTIN:
            success = SwOperator._kill_mutex_by_inner_mode(sw, multirun_mode)
            # if success:
            #     # 更新 has_mutex 为 False 并保存
            #     print(f"成功关闭：{time.time() - start_time:.4f}秒")
            # else:
            #     print(f"关闭互斥体失败！")
            proc = process_utils.create_process_without_admin(sw_path, None)

        return proc, sub_proc

    @staticmethod
    def open_sw(sw, multirun_mode):
        """
        根据状态以不同方式打开微信
        :param sw: 选择软件标签
        :param multirun_mode: 多开模式
        :return: 微信窗口句柄
        """
        Printer().print_vn(f"[INFO]使用{multirun_mode}模式打开{sw}...")
        sub_proc = None
        sw_path = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.INST_PATH)
        if not sw_path:
            return None
        if multirun_mode == MultirunMode.FREELY_MULTIRUN:
            proc = process_utils.create_process_without_admin(sw_path)
        else:
            proc, sub_proc = SwOperator._open_sw_without_freely_multirun(sw, multirun_mode)
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

    @staticmethod
    def get_idle_login_wnd_and_close_if_necessary(sw, close=False):
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
            if SwOperator._is_hwnd_a_main_wnd_of_sw(hwnd, sw):
                all_idle_hwnds_set.remove(hwnd)
        all_idle_hwnds = list(all_idle_hwnds_set)
        Printer().print_vn(f"[INFO]{sw}登录任务前已存在的登录窗口：{all_idle_hwnds}")
        if close:
            all_idle_hwnds = hwnd_utils.try_close_hwnds_in_set_and_return_remained(all_idle_hwnds_set)
            print(f"[OK]用户选择不保留!清理后剩余的登录窗口:{all_idle_hwnds}")
        return all_idle_hwnds

    @staticmethod
    def get_login_size(sw, multirun_mode):
        redundant_wnd_list, login_wnd_class, executable_name, cfg_handles = subfunc_file.get_remote_cfg(
            sw, redundant_wnd_class=None, login_wnd_class=None, executable=None, cfg_handle_regex_list=None)
        print(login_wnd_class)
        SwOperator.get_idle_login_wnd_and_close_if_necessary(redundant_wnd_list, sw)

        # 关闭配置文件锁
        handle_utils.close_sw_mutex_by_handle(
            Config.HANDLE_EXE_PATH, executable_name, cfg_handles)

        SwOperator.kill_sw_multiple_processes(sw)
        _, sub_exe_process = SwOperator.open_sw(sw, multirun_mode)
        wechat_hwnd = hwnd_utils.wait_hwnd_by_class(login_wnd_class, timeout=8)
        if wechat_hwnd:
            print(f"打开了登录窗口{wechat_hwnd}")
            if sub_exe_process:
                sub_exe_process.terminate()
            time.sleep(2)
            login_wnd_details = hwnd_utils.get_hwnd_details_of_(wechat_hwnd)
            login_wnd = login_wnd_details["window"]
            login_width = login_wnd_details["width"]
            login_height = login_wnd_details["height"]
            logger.info(f"获得了窗口尺寸：{login_width}, {login_height}")
            login_wnd.close()
            return login_width, login_height
        return None

    @staticmethod
    def open_config_file(sw):
        """打开配置文件夹"""
        data_path = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.DATA_DIR)
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
        """清除配置文件"""
        confirm = messagebox.askokcancel(
            "确认清除",
            f"该操作将会清空{sw}登录配置文件，请确认是否需要清除？"
        )
        if confirm:
            data_path = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.DATA_DIR)
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
                # print(file_suffix)
                # print(data_files)
                # print(files_to_delete)
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
        dll_dir = SwInfoFunc.get_saved_path_of_(sw, LocalCfg.DLL_DIR)
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
        pids = process_utils.psutil_get_pids_by_wildcards([executable])
        if len(pids) == 0:
            logger.warning(f"没有运行该程序。")
            return []
        else:
            process_id = pids[0]
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
    def _create_path_finders_of_(path_tag, ignore_local_record=False) -> list:
        """定义方法列表"""
        if path_tag == LocalCfg.INST_PATH:
            return [
                SwInfoUtils.get_sw_install_path_from_process,
                ((lambda sw: []) if ignore_local_record
                 else SwInfoUtils._create_sw_method_to_get_path_from_local_record(LocalCfg.INST_PATH)),
                SwInfoUtils.get_sw_install_path_from_machine_register,
                SwInfoUtils.get_sw_install_path_from_user_register,
                SwInfoUtils.get_sw_install_path_by_guess,
            ]
        elif path_tag == LocalCfg.DATA_DIR:
            return [
                ((lambda sw: []) if ignore_local_record
                 else SwInfoUtils._create_sw_method_to_get_path_from_local_record(LocalCfg.DATA_DIR)),
                SwInfoUtils.get_sw_data_dir_from_user_register,
                SwInfoUtils.get_sw_data_dir_by_guess,
                SwInfoUtils._get_sw_data_dir_from_other_sw,
            ]
        elif path_tag == LocalCfg.DLL_DIR:
            return [
                ((lambda sw: []) if ignore_local_record
                 else SwInfoUtils._create_sw_method_to_get_path_from_local_record(LocalCfg.DLL_DIR)),
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

    @staticmethod
    def _create_sw_method_to_get_path_from_local_record(path_tag):
        """
        创建路径查找函数
        :param path_tag: 路径类型
        :return: 路径查找函数
        """

        def get_sw_path_from_local_record(sw: str) -> list:
            path = subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, path_tag)
            return [path] if path is not None else []

        return get_sw_path_from_local_record

    @staticmethod
    def try_get_path(sw: str, path_type: str, ignore_local_record) \
            -> Union[Tuple[bool, bool, Union[None, str]]]:
        """
        获取微信数据路径的结果元组
        :param ignore_local_record: 是否忽略本地记录
        :param path_type: 路径类型
        :param sw: 平台
        :return: 成功，是否改变，结果
        """
        success = False
        changed = False
        result = None

        path_finders = SwInfoUtils._create_path_finders_of_(path_type, ignore_local_record)
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
