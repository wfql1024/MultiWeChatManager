import base64
import glob
import mmap
import os
import re
import shutil
import subprocess
import threading
import time
import winreg
from tkinter import messagebox
from typing import Union, Tuple, Optional, List

import psutil
import win32com
import win32con
import win32gui
import winshell
from PIL import Image
from win32com.client import Dispatch

from components import CustomDialogW
from functions import subfunc_file
from public import Strings, Config
from public.custom_classes import FlowControlError
from public.enums import LocalCfg, SW, AccKeys, MultirunMode, RemoteCfg, CallMode, WndType
from public.global_members import GlobalMembers
from public.strings import NEWER_SYS_VER
from utils import file_utils, process_utils, handle_utils, hwnd_utils, image_utils
from utils.better_wx.inner_utils import patt2hex, custom_wildcard_tokenize
from utils.encoding_utils import VersionUtils, PathUtils, CryptoUtils, ByteUtils
from utils.file_utils import rw_lock
from utils.hwnd_utils import HwndGetter, Win32HwndGetter
from utils.logger_utils import mylogger as logger, Printer, Logger
from utils.logger_utils import myprinter as printer
from utils.process_utils import Process


class Software:
    def __init__(self, sw):
        self.sw = sw
        self.label = None
        self.frame = None
        self.view = None
        self.can_freely_multirun = None
        self.multirun_mode = None
        self.anti_revoke = None
        self.classic_ui = None
        self.treeview_ui = None
        self.inst_path = None
        self.data_dir = None
        self.dll_dir = None
        self.ver = None
        self.login_accounts = None
        self.logout_accounts = None
        self.widget_dict = {}
        self.is_original = None
        self.force_rescan = None


class SwInfoFunc:
    """
    当前版本，所使用的适配表结构如下：
    平台sw -> 补丁模式mode -> "channels" -> 方案频道channel -> "feature/precise_ver_adaptations"
     -> 版本号 -> 路径补丁包 -> 补丁包列表
    """

    @staticmethod
    def get_sw_class(sw) -> Software:
        return GlobalMembers.root_class.sw_classes[sw]

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
    def get_coexist_path_from_address(cls, sw, address, channel, s):
        """解析地址并得到共存路径"""
        # Printer().debug(address)
        coexist_patch_wildcard_addr_dict = subfunc_file.get_remote_cfg(
            sw, RemoteCfg.COEXIST, RemoteCfg.CHANNELS, channel, "patch_wildcard")
        coexist_patch_wildcard_addr = coexist_patch_wildcard_addr_dict.get(address, "")
        # Printer().debug(f"{coexist_patch_wildcard_addr}")
        coexist_patch_wildcard = cls.resolve_sw_path(sw, coexist_patch_wildcard_addr)
        coexist_patch_file = coexist_patch_wildcard.replace("?", s).replace("\\", "/")
        return coexist_patch_file

    @classmethod
    def extract_addresses_from_remote_cfg(cls, sw):
        """
        从给定数据结构中提取所有addr到集合
        :param sw: 顶级软件键，比如"Weixin"
        :return: addr集合
        """
        addr_set = set()
        sw_dict = subfunc_file.get_remote_cfg(sw)
        # 第二级：固定的几个功能类别
        for feature in [RemoteCfg.REVOKE, RemoteCfg.MULTI, RemoteCfg.COEXIST]:
            feature_dict = sw_dict.get(feature, {})
            try:
                channels = feature_dict.get(RemoteCfg.CHANNELS, {})
                # 第四级：遍历所有channel
                for channel, channel_dict in channels.items():
                    # print(channel_dict)
                    adaptations = channel_dict.get(RemoteCfg.FEATURES, {})
                    print(adaptations)
                    # 遍历所有版本
                    for version, version_list in adaptations.items():
                        for item in version_list:
                            addr = item.get("addr")
                            if addr:
                                addr_set.add(addr)
            except Exception as e:
                print(e)
                continue
        return list(addr_set)

    @classmethod
    def _update_adaptation_from_remote_to_cache(cls, sw, mode, skip_cache=True):
        """根据远程表内容更新缓存表, skip_cache 决定已有正确格式缓存时是否跳过扫描"""
        channels_dict, = subfunc_file.get_remote_cfg(sw, mode, channels=None)
        if not isinstance(channels_dict, dict):
            return
        cur_sw_ver = cls.calc_sw_ver(sw)
        for channel in channels_dict:
            try:
                precise_ver_adaptation = channels_dict[channel][RemoteCfg.PRECISES][cur_sw_ver]
                subfunc_file.update_cache_cfg(
                    sw, mode, RemoteCfg.CHANNELS, channel,
                    RemoteCfg.PRECISES, **{cur_sw_ver: precise_ver_adaptation}
                )
            except KeyError:
                pass

            try:
                feature_vers_dict = channels_dict[channel][RemoteCfg.FEATURES]
                feature_vers = list(feature_vers_dict.keys())
                compatible_ver = VersionUtils.pkg_find_compatible_version(cur_sw_ver, feature_vers)
                # 用兼容版本特征码查找适配
                feature_ver_addr_dicts = feature_vers_dict[compatible_ver]
                # 检查是否弃用
                if feature_ver_addr_dicts is None:
                    print(f"[{channel}]该渠道在该版本已弃用!")
                    # 强制删掉本地缓存
                    cache_vers_dict = subfunc_file.get_cache_cfg(
                        sw, mode, RemoteCfg.CHANNELS, channel, RemoteCfg.PRECISES)
                    if isinstance(cache_vers_dict, dict):
                        del cache_vers_dict[cur_sw_ver]
                        subfunc_file.update_cache_cfg(
                            sw, mode, RemoteCfg.CHANNELS, channel, **{RemoteCfg.PRECISES: cache_vers_dict})
                    continue
                if skip_cache is True:
                    # 检查是否已有缓存
                    cache_ver_addr_dicts = subfunc_file.get_cache_cfg(
                        sw, mode, RemoteCfg.CHANNELS, channel, RemoteCfg.PRECISES, cur_sw_ver)
                    if isinstance(cache_ver_addr_dicts, list) and len(cache_ver_addr_dicts) != 0:
                        if all((isinstance(addr_dict["patches"], list) and isinstance(addr_dict["addr"], str))
                               for addr_dict in cache_ver_addr_dicts):
                            print(f"[{channel}]渠道在该版本已存在缓存的适配")
                            continue
                ver_addr_res_dicts = []
                channel_failed = False
                # 对每个地址的每个扫描字典, 都至少要扫描出一个, 否则判定失败!!!
                for addr_dict in feature_ver_addr_dicts:
                    ver_addr_res_dict = {}
                    addr = addr_dict.get("addr", None)
                    addr_feature_list = addr_dict.get("patch_rules", None)
                    if not isinstance(addr, str) or not isinstance(addr_feature_list, list):
                        channel_failed = True
                        break
                    patch_file = cls.resolve_sw_path(sw, addr)
                    if not os.path.exists(patch_file):
                        channel_failed = True
                        break

                    with open(patch_file, "rb") as f:
                        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
                        addr_res_dicts = []  # 存放本 addr 下所有 processed 结果
                        try:
                            addr_failed = False
                            for feature_rule in addr_feature_list:
                                # Printer().debug("检查:", mode, channel, addr, feature_rule)
                                res_dicts = SwInfoUtils.resolve_rule_dict_and_return_res_dicts(mm, feature_rule)
                                # Printer().debug("结果:", res_dicts)
                                if len(res_dicts) == 0:
                                    addr_failed = True
                                    break
                                addr_res_dicts.extend(res_dicts)
                            if len(addr_res_dicts) == 0 or addr_failed is True:
                                channel_failed = True
                                break
                            # 能到达这里代表当前地址字典能够正常扫描
                            # 将地址字典中除了 patch_rules 节点外所有节点都拷贝出来, 扫描结果放在 patches 节点中.
                            for key in addr_dict:
                                if key == "patch_rules":
                                    continue
                                ver_addr_res_dict[key] = addr_dict[key]
                            ver_addr_res_dict["patches"] = addr_res_dicts
                            ver_addr_res_dicts.append(ver_addr_res_dict)
                        finally:
                            mm.close()
                print(ver_addr_res_dicts)
                if channel_failed is not True:
                    # 添加到缓存表中
                    subfunc_file.update_cache_cfg(
                        sw, mode, RemoteCfg.CHANNELS, channel,
                        RemoteCfg.PRECISES, **{cur_sw_ver: ver_addr_res_dicts})
            except KeyError:
                pass
            except Exception as e:
                print(e)

    @classmethod
    def _identify_multi_state_patching_of_files_in_channel(
            cls, sw, addr_patches_dicts, coexist_channel=None, ordinal=None):
        """
        对于非二元状态切换的, 只需要检测列表中的文件是否存在
        返回:
            { addr1: {"status": status, "msg": message}, addr2: {...}, ...}
            其中, status: True/False/None; message: 携带信息
        """
        addr_res_dict = {}
        for addr_patches_dict in addr_patches_dicts:
            addr = addr_patches_dict.get("addr", None)
            if not isinstance(addr, str):
                addr_res_dict["Error"] = {"status": None, "msg": "存在无地址的补丁模式"}
                continue
            # Printer().debug(f"检查文件地址 {addr} 的特征码适配")
            if not isinstance(coexist_channel, str) or not isinstance(ordinal, str):
                patch_file = cls.resolve_sw_path(sw, addr)
            else:
                patch_file = cls.get_coexist_path_from_address(sw, addr, coexist_channel, ordinal)
            if not os.path.exists(patch_file):
                addr_res_dict[addr] = {"status": None, "msg": "文件不存在"}
                continue
            addr_res_dict[addr] = {"status": True, "msg": ""}

        return addr_res_dict

    @classmethod
    def _identify_binary_state_patching_of_files_in_channel(
            cls, sw, addr_patches_dicts, channel=None, ordinal=None) -> dict:
        """
        二元状态, 对涉及文件的涉及补丁包进行判断打补丁状态, 若都打上则返回True, 否则返回False
        参数: addr_patches_dicts: 结构参考上级方法
        返回:
            { addr1: {"status": status, "msg": message}, addr2: {...}, ...}
            其中, status: True/False/None; message: 携带信息
        """
        # Printer().debug("所有地址适配字典", addr_patches_dicts)
        addr_res_dict = {}
        for addr_patches_dict in addr_patches_dicts:
            # Printer().debug("单个地址适配字典", addr_patches_dict)
            addr = addr_patches_dict.get("addr", None)
            if not isinstance(addr, str):
                addr_res_dict["Error"] = {"status": None, "msg": "存在无地址的补丁模式"}
                continue
            # Printer().debug(f"检查文件地址 {addr} 的特征码适配")
            if not isinstance(channel, str) or not isinstance(ordinal, str):
                patch_file = cls.resolve_sw_path(sw, addr)
            else:
                patch_file = cls.get_coexist_path_from_address(sw, addr, channel, ordinal)
            if not os.path.exists(patch_file):
                addr_res_dict[addr] = {"status": None, "msg": "文件不存在"}
                continue
            with open(patch_file, "rb") as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    addr_patching_dicts = addr_patches_dict["patches"]
                    result_set = set()
                    for addr_patching_dict in addr_patching_dicts:
                        if "custom_template" in addr_patching_dict:
                            continue  # 自定义的直接跳过
                        instr_addr = addr_patching_dict["offset"]
                        modified_hex = addr_patching_dict["modified"]
                        modified_bytes = ByteUtils.hex_str_to_bytes(modified_hex)
                        # 检查文件中对应地址的字节是否与 modified_bytes 相等
                        with rw_lock.gen_rlock():
                            file_slice = mm[instr_addr: instr_addr + len(modified_bytes)]
                        is_patched = file_slice == modified_bytes
                        # Printer().debug(patch_file, modified_bytes, is_patched)
                        result_set.add(is_patched)

                    # 判断最终状态
                    status = result_set == {True}  # True = 补丁已全部打，False = 未打
                    message = "已开启" if status else "未开启"
                    addr_res_dict[addr] = {"status": status, "msg": message}
        return addr_res_dict

    @classmethod
    def _identify_patching_by_addr_patches_dicts_in_ver(
            cls, sw, addr_patch_rules_dicts, multi_state=False, coexist_channel=None, ordinal=None) -> dict:
        """
        对版本适配字典中的地址补丁包进行状态识别
        参数: addr_patches_dicts: 地址-补丁适配字典列表 [{"addr": addr, "patches": [...]}, {...}, ...]
            其中, "patches"的列表结构: [{"offset": offset, "modified": modified_hex, "original": original_hex}, {...}, ...]
        返回: 字典: {"status": channel_status, "msg": msg_str}
            其中, channel_status: 渠道状态, True/False/None
                msg_str = f"问题文件: {addresses_msg_dict}"
        """
        # Printer().debug(sw, addr_patch_rules_dicts, multi_state, coexist_channel, ordinal)
        status_set = set()
        addresses_msg_dict = {}  # 存储问题路径及消息
        if multi_state:
            addresses_res_dict = cls._identify_multi_state_patching_of_files_in_channel(
                sw, addr_patch_rules_dicts, coexist_channel, ordinal)
        else:
            addresses_res_dict = cls._identify_binary_state_patching_of_files_in_channel(
                sw, addr_patch_rules_dicts, coexist_channel, ordinal)
        # Printer().debug(f"所有地址识别结果: {addresses_res_dict}")

        # 中间层: 识别后得到 addresses_res_dict = {addr1: {"status": status, "msg": message}, addr2: {...}, ...}
        # 从中间层中提取状态和消息
        for addr in addresses_res_dict.keys():
            status = None
            try:
                addr_res_dict = addresses_res_dict[addr]
                status = addr_res_dict["status"]
                if status is None:
                    addresses_msg_dict[addr] = addr_res_dict["msg"]
            except KeyError:
                addresses_msg_dict[addr] = "返回格式错误"
            status_set.add(status)
        if None in status_set:
            channel_status = None
        elif status_set == {True}:
            channel_status = True
        else:
            channel_status = False
        msg_str = f"问题文件: {addresses_msg_dict}"
        return {"status": channel_status, "msg": msg_str}

    @classmethod
    def identify_dll_core(
            cls, sw, mode, channel=None, coexist_channel=None, ordinal=None
    ) -> Tuple[Optional[dict], str]:
        """
        检查当前补丁状态，返回结果字典(若没有适配则返回None)和消息
        结果字典格式: {channel1: {status:bool, msg:str}, channel2: {...}, ...}
        """
        dll_dir = cls.try_get_path_of_(sw, LocalCfg.DLL_DIR)
        if dll_dir is None:
            return None, "错误：没有找到dll目录"
        multi_state, = subfunc_file.get_remote_cfg(sw, mode, multi_state=None)
        multi_state: bool = True if multi_state is True else False
        # Printer().debug(sw, mode, multi_state)
        # 不跳过已有只对主程序生效
        sw_class = cls.get_sw_class(sw)
        skip_cache = sw_class.force_rescan is not True
        if coexist_channel is None or ordinal is None:
            sw_class.force_rescan = False
            cls._update_adaptation_from_remote_to_cache(sw, mode, skip_cache)
        else:
            cls._update_adaptation_from_remote_to_cache(sw, mode)
        # 通过缓存配置进行检测
        # - 获取缓存配置
        try:
            mode_dict, = subfunc_file.get_cache_cfg(sw, **{mode: None})
            if mode_dict is None:
                return None, f"错误：平台未适配{mode}"
        except Exception as e:
            Logger().error(e)
            return None, f"错误：{e}"
        # - 获取当前版本
        cur_sw_ver = cls.calc_sw_ver(sw)
        if cur_sw_ver is None:
            return None, f"错误：未知当前版本"
        # - 检查 channels 配置
        if (not isinstance(mode_dict, dict) or RemoteCfg.CHANNELS not in mode_dict
                or not isinstance(mode_dict[RemoteCfg.CHANNELS], dict)):
            return None, "错误：该模式没有适配频道列表或适配频道列表格式错误"
        channels_dict = mode_dict["channels"]
        # - 只检测指定 channel，或全部 channel
        channels_to_check = [channel] if channel else list(channels_dict.keys())
        channels_res_dict = {}
        for ch in channels_to_check:
            try:
                addr_patches_dicts = channels_dict[ch][RemoteCfg.PRECISES][cur_sw_ver]
                # Printer().debug("准备遍历渠道检测: ",sw, ch, addr_patches_dicts)
                if isinstance(addr_patches_dicts, list):
                    channels_res_dict[ch] = cls._identify_patching_by_addr_patches_dicts_in_ver(
                        sw, addr_patches_dicts, multi_state=multi_state, coexist_channel=coexist_channel,
                        ordinal=ordinal)
            except KeyError:
                continue
        if not channels_res_dict:
            return None, f"错误：该版本 {cur_sw_ver} 的适配在本地平台中未找到"
        # Printer().debug(f"{sw} - {mode} 识别结果: {channels_res_dict}")
        return channels_res_dict, f"成功：找到版本 {cur_sw_ver} 的适配"

    @classmethod
    def clear_adaptation_cache(cls, sw, mode):
        """清除当前版本模式的适配缓存"""
        curr_ver = cls.calc_sw_ver(sw)
        channels_dict = subfunc_file.get_cache_cfg(sw, mode, RemoteCfg.CHANNELS)
        for channel in channels_dict:
            precise_vers_dict = subfunc_file.get_cache_cfg(
                sw, mode, RemoteCfg.CHANNELS, channel, RemoteCfg.PRECISES)
            del precise_vers_dict[curr_ver]
            subfunc_file.update_cache_cfg(
                sw, mode, RemoteCfg.CHANNELS, channel, **{RemoteCfg.PRECISES: precise_vers_dict})

    @staticmethod
    def get_sw_wnd_class_matching_dicts(sw, wnd_type) -> Optional[list]:
        """从远程配置中获取适合当前版本的窗口类名检查字典"""
        type_vers_dict: dict = subfunc_file.get_remote_cfg(sw, RemoteCfg.WND_CLASS, wnd_type, "matching")
        if not isinstance(type_vers_dict, dict):
            return None
        curr_ver = SwInfoFunc.calc_sw_ver(sw)
        compatible_version = VersionUtils.pkg_find_compatible_version(curr_ver, list(type_vers_dict.keys()))
        # Printer().debug(f"找到合适版本{compatible_version}")
        if compatible_version is None:
            return None
        return type_vers_dict[compatible_version]

    @staticmethod
    def get_sw_original_wnd_class_name(sw, wnd_type) -> Optional[str]:
        type_vers_dict: dict = subfunc_file.get_remote_cfg(sw, RemoteCfg.WND_CLASS, wnd_type, "original")
        if not isinstance(type_vers_dict, dict):
            return None
        curr_ver = SwInfoFunc.calc_sw_ver(sw)
        compatible_version = VersionUtils.pkg_find_compatible_version(curr_ver, list(type_vers_dict.keys()))
        if compatible_version is None:
            return None
        return type_vers_dict[compatible_version]["class_name"]

    @staticmethod
    def get_login_hwnds_of_sw(sw):
        """获取平台所有的登录窗口句柄"""
        login_hwnds = []
        login_class_check_dicts = SwInfoFunc.get_sw_wnd_class_matching_dicts(sw, WndType.LOGIN)
        all_sw_pids = SwInfoFunc.get_sw_all_exe_pids(sw)
        for pid in all_sw_pids:
            hwnds_of_pid = Win32HwndGetter.win32_get_hwnds_by_pid_and_class_wildcards(pid)
            for matching_dict in login_class_check_dicts:
                Printer().print_vn(f"PID: {pid}, 筛选条件: {matching_dict}")
                hwnd_list = HwndGetter.uiautomation_filter_hwnds_by_matching_dict(hwnds_of_pid, matching_dict)
                if len(hwnd_list) == 1:
                    login_hwnds.append(hwnd_list[0])
        return login_hwnds

    @staticmethod
    def ensure_coexist_acc_formatted(sw, coexist_exe):
        coexist_exe_dict = subfunc_file.get_sw_acc_data(sw, coexist_exe)
        if not isinstance(coexist_exe_dict, dict):
            subfunc_file.update_sw_acc_data(sw, **{coexist_exe: {}})
        coexist_exe_dict = subfunc_file.get_sw_acc_data(sw, coexist_exe)
        if "linked_acc" not in coexist_exe_dict:
            subfunc_file.update_sw_acc_data(sw, coexist_exe, linked_acc=None)
        if "channel" not in coexist_exe_dict:
            subfunc_file.update_sw_acc_data(sw, coexist_exe, channel=None)
        if RemoteCfg.ORDINALS not in coexist_exe_dict:
            subfunc_file.update_sw_acc_data(sw, coexist_exe, **{RemoteCfg.ORDINALS: None})

    @classmethod
    def _get_all_coexist_acc_and_ensure_formatted(cls, sw, inst_dir, executable_wildcards):
        """获取所有的共存程序,并在字典中确保存在对应的账号节点和 linked_acc 属性"""
        # 处理共存版账号,创建字典和节点
        all_exes = file_utils.get_file_names_matching_wildcards(executable_wildcards, inst_dir)
        origin_exe, = subfunc_file.get_remote_cfg(sw, executable=None)
        all_coexist_exes = []
        for coexist_exe in all_exes:
            if coexist_exe == origin_exe:
                continue
            all_coexist_exes.append(coexist_exe)
            cls.ensure_coexist_acc_formatted(sw, coexist_exe)
        return all_coexist_exes

    @classmethod
    def get_sw_all_accounts_existed(cls, sw, only=None):
        """获取平台所有账号, origin为原生账号, coexist为共存账号"""

        def _get_origin_accounts():
            data_dir = SwInfoFunc.try_get_path_of_(sw, LocalCfg.DATA_DIR)
            excluded_dirs, = subfunc_file.get_remote_cfg(sw, excluded_dir_list=None)
            return {entry.name for entry in os.scandir(data_dir) if entry.is_dir()} - set(excluded_dirs)

        def _get_coexist_accounts():
            inst_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.INST_PATH)
            inst_dir = os.path.dirname(inst_path)
            executable_wildcards, = subfunc_file.get_remote_cfg(sw, executable_wildcards=None)
            if executable_wildcards is None:
                return set()
            coexist_accs = cls._get_all_coexist_acc_and_ensure_formatted(sw, inst_dir, executable_wildcards)
            Printer().print_vn(coexist_accs)
            return set(coexist_accs)

        if only == "origin":
            return list(_get_origin_accounts())
        elif only == "coexist":
            return list(_get_coexist_accounts())
        else:
            return list(_get_origin_accounts() | _get_coexist_accounts())

    @classmethod
    def identity_and_get_available_coexist_mode(cls, sw):
        """选择一个可用的共存构造模式, 优先返回用户选择的, 若其不可用则返回可用的第一个模式"""
        user_coexist_channel = subfunc_file.fetch_sw_setting_or_set_default_or_none(sw, LocalCfg.COEXIST_MODE)
        channel_res_dict, msg = cls.identify_dll_core(sw, RemoteCfg.COEXIST)
        if isinstance(channel_res_dict, dict):
            if user_coexist_channel in channel_res_dict:
                return user_coexist_channel, channel_res_dict, msg
            return list(channel_res_dict.keys())[0], channel_res_dict, msg
        return None, {}, msg

    @classmethod
    def _check_if_sw_can_freely_multirun(cls, sw):
        sw_class = cls.get_sw_class(sw)
        mode_channels_res_dict, msg = SwInfoFunc.identify_dll_core(sw, RemoteCfg.MULTI.value)
        sw_class.can_freely_multirun = None
        # 以有无适配为准; 若没有适配,检查是否是原生支持多开
        if mode_channels_res_dict is None:
            # 没有适配, 检查是否是原生支持多开
            native_multirun, = subfunc_file.get_remote_cfg(
                sw, RemoteCfg.MULTI, **{RemoteCfg.NATIVE.value: None})
            if native_multirun is True:
                sw_class.can_freely_multirun = True
                return True
        else:
            # 列出所有频道
            for channel, channel_res_dict in mode_channels_res_dict.items():
                freely_multirun_status = channel_res_dict["status"]
                # 只要有freely_multirun为True，就将其设为True
                if freely_multirun_status is True:
                    sw_class.can_freely_multirun = True
                    return True
        return False

    @classmethod
    def get_sw_multirun_mode(cls, sw):
        sw_class = SwInfoFunc.get_sw_class(sw)
        can_freely_multirun = cls._check_if_sw_can_freely_multirun(sw)
        if can_freely_multirun:
            sw_class.multirun_mode = MultirunMode.FREELY_MULTIRUN
        else:
            rest_mode_value = subfunc_file.fetch_sw_setting_or_set_default_or_none(
                sw, LocalCfg.REST_MULTIRUN_MODE)
            sw_class.multirun_mode = rest_mode_value
        return sw_class.multirun_mode

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
            return Image.new('RGB', Config.AVT_SIZE, color='white')

    @staticmethod
    def get_sw_origin_display_name(sw) -> str:
        """获取账号的展示名"""
        display_name = str(sw)  # 默认值为 sw
        # 1. 先查本地 remark
        remark, = subfunc_file.get_settings(sw, **{LocalCfg.REMARK: None})
        if remark is not None:
            return str(remark)
        # 2. 再查远程 alias（不再存本地）
        alias, = subfunc_file.get_remote_cfg(sw, **{RemoteCfg.ALIAS: None})
        if alias is not None:
            return str(alias)
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

    @staticmethod
    def record_sw_pid_mutex_dict_when_start_login(sw, set_all_to_true=None):
        """在该平台登录之前,存储 pid 和 互斥体 的映射关系字典, 默认全置为True"""
        pids = SwInfoFunc.get_sw_all_exe_pids(sw)
        pid_mutex_dict = {}
        if isinstance(set_all_to_true, bool):
            # 一刀切, 所有进程都设置为含有互斥体或没有互斥体
            Printer().print_vn(f"[INFO]将所有进程设为含有互斥体: {set_all_to_true}")
            for pid in pids:
                pid_mutex_dict[pid] = set_all_to_true
        else:
            # 是否默认全为True
            all_has_mutex_by_default = subfunc_file.fetch_global_setting_or_set_default_or_none(LocalCfg.ALL_HAS_MUTEX)
            all_has_mutex_by_default: bool = True if all_has_mutex_by_default is True else False
            if all_has_mutex_by_default is True:
                Printer().print_vn("[INFO]将所有进程默认含有互斥体")
                for pid in pids:
                    pid_mutex_dict[pid] = True
            else:
                # 从当前所有进程中获取所有有互斥体的进程
                Printer().print_vn("[INFO]不默认所有进程含有互斥体, 检查中...")
                pids_has_mutex = SwOperator.try_kill_mutex_if_need_and_return_remained_pids(sw)
                for p in pids:
                    pid_mutex_dict[p] = True if p in pids_has_mutex else False
        Printer().print_vn(f"[INFO]登录前所有互斥体:{pid_mutex_dict}")
        subfunc_file.update_sw_acc_data(AccKeys.RELAY, sw, **{AccKeys.PID_MUTEX: pid_mutex_dict})

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
    def kill_all_mutexes_now(sw):
        """查杀所有互斥体: 进程互斥体, 配置文件锁"""
        pids = SwInfoFunc.get_sw_all_exe_pids(sw)
        mutant_handle_wildcards, config_handle_wildcards = subfunc_file.get_remote_cfg(
            sw, mutant_handle_wildcards=None, config_handle_wildcards=None)
        handle_wildcards = []
        if isinstance(mutant_handle_wildcards, list):
            handle_wildcards.extend(mutant_handle_wildcards)
        if isinstance(config_handle_wildcards, list):
            handle_wildcards.extend(config_handle_wildcards)
        if isinstance(handle_wildcards, list) and len(handle_wildcards) > 0:
            handle_infos = handle_utils.pywinhandle_find_handles_by_pids_and_handle_name_wildcards(
                pids, handle_wildcards)
            Printer().debug(f"[INFO]查询到互斥体: {handle_infos}")
            if len(handle_infos) == 0:
                return True, f"{sw}已经不含互斥体和文件锁!"
            success = handle_utils.pywinhandle_close_handles(
                handle_infos
            )
            if success is True:
                return True, f"{sw}已关闭互斥体和解锁文件!"
            else:
                return False, f"{sw}关闭互斥体和解锁文件失败!"
        else:
            return False, f"未查询到{sw}的互斥体列表和配置文件列表!"

    @staticmethod
    def try_kill_mutex_if_need_and_return_remained_pids(sw, kill=None):
        """检查并可选择是否关闭互斥体, 返回剩余的含有互斥体的 pid 列表"""
        mutant_wildcards, = subfunc_file.get_remote_cfg(
            sw,
            mutant_handle_wildcards=None,
        )
        if not isinstance(mutant_wildcards, list):
            print("未获取到互斥体通配词,将不进行查找...")
            return None
        pids_with_mutex = []
        pids = SwInfoFunc.get_sw_all_exe_pids(sw)
        Printer().debug(f"当前所有进程: {pids}")
        mutant_handle_dicts = handle_utils.pywinhandle_find_handles_by_pids_and_handle_name_wildcards(
            pids, mutant_wildcards)
        Printer().debug(f"查杀前所有互斥体: {mutant_handle_dicts}")
        if kill is True and len(mutant_handle_dicts) != 0:
            handle_utils.pywinhandle_close_handles(mutant_handle_dicts)
            mutant_handle_dicts = handle_utils.pywinhandle_find_handles_by_pids_and_handle_name_wildcards(
                pids, mutant_wildcards)
            Printer().debug(f"查杀后所有互斥体: {mutant_handle_dicts}")
        for mutant_handle in mutant_handle_dicts:
            pids_with_mutex.append(mutant_handle['process_id'])
        return pids_with_mutex

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
    def backup_sw_all_patching_files(sw):
        """备份所有补丁文件, 若存在则跳过"""
        all_patching_addresses = SwInfoFunc.extract_addresses_from_remote_cfg(sw)
        all_patching_files = [SwInfoFunc.resolve_sw_path(sw, addr) for addr in all_patching_addresses]
        Printer().debug(f"所有需要备份的文件: {all_patching_files}")
        file_utils.backup_files(all_patching_files)

    @staticmethod
    def _backup_dll(patching_dict):
        """备份当前的dll"""
        desktop_path = winshell.desktop()
        has_noticed = False
        for addr in patching_dict:
            patch_path = patching_dict[addr]["path"]
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
    def switch_dll_core(cls, sw, mode, channel, coexist_channel=None, ordinal=None, target=None) -> Tuple[
        Optional[bool], str]:
        """对二元状态的渠道, 检测当前状态并切换"""
        Printer().debug(sw, mode, channel, coexist_channel, ordinal)
        if mode == RemoteCfg.MULTI:
            mode_text = "全局多开"
        elif mode == RemoteCfg.REVOKE:
            mode_text = "防撤回"
        else:
            return False, "未知模式"
        try:
            # 条件检查及询问用户
            inst_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.INST_PATH)
            inst_dir = os.path.dirname(inst_path)
            if isinstance(coexist_channel, str) and isinstance(ordinal, str):
                exe_wildcard = subfunc_file.get_remote_cfg(
                    sw, RemoteCfg.COEXIST, RemoteCfg.CHANNELS, coexist_channel, "exe_wildcard")
                coexist_exe = exe_wildcard.replace("?", ordinal)
                sw_exe_path = os.path.join(inst_dir, coexist_exe).replace("\\", "/")
            else:
                sw_exe_path = inst_path
            Printer().debug(sw_exe_path)
            # 提醒用户手动终止微信进程
            answer = cls._ask_for_manual_terminate_or_force(sw_exe_path)
            if not (answer is True):
                return False, "用户取消操作"
            # 如果 target 没指定，则先识别当前状态，再取反
            if target is None:
                channels_res_dict, _ = SwInfoFunc.identify_dll_core(sw, mode, channel, coexist_channel, ordinal)
                tag = channels_res_dict[channel]["status"]
                Printer().debug(f"未指定, 检测到状态{tag}")
                if tag is None:
                    return False, f"无法识别当前 {mode} 状态，补丁未应用"
                target = not tag  # 取反作为目标状态

            curr_ver = SwInfoFunc.calc_sw_ver(sw)
            # 获取补丁表 { "dll路径(占位)": [ {addr, original, modified}, ... ] }
            addr_patches_dicts = subfunc_file.get_cache_cfg(
                sw, mode, RemoteCfg.CHANNELS, channel, RemoteCfg.PRECISES, curr_ver
            )
            # Printer().debug(curr_ver, addr_patches_dicts)
            for addr_patches_dict in addr_patches_dicts:
                if "addr" not in addr_patches_dict or "patches" not in addr_patches_dict:
                    return False, "缓存适配格式错误!"
            files = []  # 存储文件句柄
            mmaps = []  # 存储 mmap 对象
            try:
                # 先打开并写入所有文件（不 flush）
                for addr_patches_dict in addr_patches_dicts:
                    addr = addr_patches_dict.get("addr", None)
                    patches = addr_patches_dict.get("patches", None)
                    if isinstance(coexist_channel, str) and isinstance(ordinal, str):
                        real_dll_path = SwInfoFunc.get_coexist_path_from_address(
                            sw, addr, coexist_channel, ordinal)
                    else:
                        real_dll_path = SwInfoFunc.resolve_sw_path(sw, addr)
                    # Printer().debug(real_dll_path)
                    with rw_lock.gen_wlock():
                        f = open(real_dll_path, "r+b")
                        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_WRITE)
                        files.append(f)
                        mmaps.append(mm)
                        for patch in patches:
                            file_offset = patch["offset"]
                            hex_str = patch["modified"] if target else patch["original"]
                            patch_bytes = bytes.fromhex(hex_str.replace(" ", ""))
                            mm[file_offset:file_offset + len(patch_bytes)] = patch_bytes
                # 如果所有写入都没报错，统一 flush
                for _mm in mmaps:
                    _mm.flush()
                return True, f"成功{'开启' if target else '关闭'}: {mode_text}"
            except Exception as e:
                print(f"[ERR] {e}")
                # 出错时不 flush，直接 close，即放弃所有改动
                return False, f"切换{mode_text}失败！请稍后重试！"
            finally:
                for _mm in mmaps:
                    _mm.close()
                for _f in files:
                    _f.close()
        except (psutil.AccessDenied, PermissionError, Exception) as e:
            error_msg = {
                PermissionError: "权限不足，无法修改 DLL 文件。",
                psutil.AccessDenied: "无法终止微信进程，请以管理员身份运行程序。",
                Exception: "发生错误。"
            }.get(type(e), "发生未知错误。")
            logger.error(f"切换{mode_text}时发生错误: {str(e)}")
            return False, f"切换{mode_text}时发生错误: {str(e)}\n{error_msg}"

    @classmethod
    def choose_channel_in_conflicts_and_switch_dll_to_(
            cls, sw, mode, channel, conflicts: list, coexist_channel=None, ordinal=None, target=None):
        """
        处理互斥方案打补丁
        :param sw: 软件标识
        :param mode: 模式
        :param channel: 当前操作方案
        :param conflicts: 冲突方案列表
        :param coexist_channel: 可选共存方案
        :param ordinal: 可选序号
        :param target: True=打补丁, False=撤销补丁, None=自动判断
        :return: True/False, 提示信息
        """
        # 如果 target 没指定，则先识别当前状态，再取反
        if target is None:
            channels_res_dict, _ = SwInfoFunc.identify_dll_core(sw, mode, channel, coexist_channel, ordinal)
            tag = channels_res_dict[channel]["status"]
            Printer().debug(f"未指定, 检测到状态{tag}")
            if tag is None:
                return False, f"无法识别当前 {mode} 状态，补丁未应用"
            target = not tag  # 取反作为目标状态

        # 先处理冲突方案
        if target is True:
            for conflict_channel in conflicts:
                if conflict_channel == channel:
                    continue
                # 冲突方案打回原始
                success, msg = cls.switch_dll_core(sw, mode, conflict_channel, target=False,
                                                   coexist_channel=coexist_channel, ordinal=ordinal)
                if not success:
                    return False, f"切换冲突方案 {conflict_channel} 失败: {msg}"

        # 再处理目标方案
        success, msg = cls.switch_dll_core(sw, mode, channel, target=target,
                                           coexist_channel=coexist_channel, ordinal=ordinal)
        if not success:
            return False, f"切换目标方案 {channel} 失败: {msg}"

        return True, f"{mode} - {channel} 切换成功"

    @staticmethod
    def _wait_hwnds_close_and_do_in_root(hwnds, timeout=20, callback=None):
        """等待所有窗口成功关闭后, 主线程执行 callback, 失败则不执行"""
        root = GlobalMembers.root_class.root
        success = hwnd_utils.wait_hwnds_close(hwnds, timeout)
        if success and callable(callback):
            root.after(0, callback)

    @classmethod
    def open_sw_and_return_hwnd(cls, sw, exe=None) -> Tuple[Optional[int], str]:
        """打开平台原始程序并返回窗口hwnd"""
        login_hwnd_rules_dicts = SwInfoFunc.get_sw_wnd_class_matching_dicts(sw, WndType.LOGIN)
        if login_hwnd_rules_dicts is None:
            return None, "该平台尚未适配!"
        all_excluded_hwnds = []
        # 关闭多余的多开器,记录已经存在的窗口 -------------------------------------------------------------------
        remained_idle_wnd_list = cls.get_idle_login_wnd_and_close_if_necessary(sw)
        all_excluded_hwnds.extend(remained_idle_wnd_list)
        # 检查所有pid及互斥体情况 -------------------------------------------------------------------
        SwInfoFunc.record_sw_pid_mutex_dict_when_start_login(sw)
        sw_proc, sub_proc = cls.open_sw(sw, exe)
        sw_proc_pid = sw_proc.pid if sw_proc else None
        if sw_proc_pid is None:
            return None, "创建进程失败!"
        # 等待打开窗口并获取hwnd *******************************************************************
        sw_hwnd, class_name = HwndGetter.uiautomation_wait_hwnd_exclusively_by_pid_and_rules_dicts(
            all_excluded_hwnds, sw_proc_pid, login_hwnd_rules_dicts)
        if sub_proc:
            sub_proc.terminate()
        Printer().debug(sw_hwnd)
        if sw_hwnd is None:
            return None, "超时未检测到窗口"
        return sw_hwnd, ""

    @classmethod
    def _manual_login_origin(cls, sw):
        """手动登录原生平台"""
        root_class = GlobalMembers.root_class
        multirun_mode = SwInfoFunc.get_sw_class(sw).multirun_mode
        start_time = time.time()
        sw_hwnd, msg = cls.open_sw_and_return_hwnd(sw)
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
        coexist_channel, _, _ = SwInfoFunc.identity_and_get_available_coexist_mode(sw)
        if not isinstance(coexist_channel, str):
            return False, "没有可用的共存构造模式!"
        exe_wildcard, ordinals = subfunc_file.get_remote_cfg(
            sw, RemoteCfg.COEXIST, RemoteCfg.CHANNELS, coexist_channel,
            exe_wildcard=None, **{RemoteCfg.ORDINALS: None})
        if not isinstance(exe_wildcard, str) or not isinstance(ordinals, str):
            return False, f"尚未适配[exe_wildcard, ordinals]!"
        login_hwnd_rules_dicts = SwInfoFunc.get_sw_wnd_class_matching_dicts(sw, WndType.LOGIN)
        if login_hwnd_rules_dicts is None:
            return False, "尚未适配[login_hwnd_rules_dicts]!"

        # 找到第一个没使用或没创建的共存程序名, 若没创建则询问创建
        exe_name = None
        for ordinal in ordinals:
            exe_name = exe_wildcard.replace("?", ordinal)
            inst_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.INST_PATH)
            inst_dir = os.path.dirname(inst_path)
            coexist_exe_path = os.path.join(inst_dir, exe_name).replace("\\", "/")
            # 判定不存在的条件: 文件不存在或者文件没有被运行
            if not os.path.isfile(coexist_exe_path):
                if messagebox.askokcancel("提醒", f"不存在{coexist_exe_path}!是否创建?"):
                    cls.create_coexist_exe_core(sw, coexist_channel, ordinal)
                else:
                    return False, "用户取消创建！"
                break
            # 检测是否登录
            exe_pids_dict = process_utils.psutil_get_pids_by_wildcards_and_grouping_to_dict([exe_name])
            if not isinstance(exe_pids_dict, dict):
                break
            exe_pids = exe_pids_dict.get(exe_name, [])
            if len(exe_pids) == 0:
                break
            exe_pids = process_utils.remove_pids_not_in_path(exe_pids, coexist_exe_path)
            if len(exe_pids) == 0:
                break

        # 直接执行
        print(f"将打开{exe_name}")
        sw_hwnd, msg = cls.open_sw_and_return_hwnd(sw, exe_name)
        if isinstance(sw_hwnd, int):
            SwInfoFunc.set_pid_mutex_all_values_to_false(sw)
            subfunc_file.update_statistic_data(
                sw, 'manual', '_', MultirunMode.BUILTIN, time.time() - start_time)
            callback = lambda: root_class.login_ui.refresh_frame(sw)
            cls._wait_hwnds_close_and_do_in_root([sw_hwnd], callback=callback)
            return True, ""
        else:
            return False, msg

    @classmethod
    def _manual_login_coexist(cls, sw):
        """手动登录共存平台,按顺序,登录第一个还未打开的共存程序,若都已经打开,则创造一个新的共存程序后打开"""
        success, msg = cls._manual_login_coexist_core(sw)
        if not success:
            Logger().warning(msg)
            messagebox.showinfo("错误", f"手动登录共存平台失败:{msg}")
            return

    @staticmethod
    def create_coexist_exe_core(sw, coexist_channel=None, ordinal=None) -> Tuple[Optional[str], str]:
        """创建共存程序"""
        # 确认共存方案和序列号
        if coexist_channel is None:
            coexist_channel, _, _ = SwInfoFunc.identity_and_get_available_coexist_mode(sw)
            if not isinstance(coexist_channel, str):
                return None, "没有可用的共存构造模式!"
        exe_wildcard, ordinals = subfunc_file.get_remote_cfg(
            sw, RemoteCfg.COEXIST, RemoteCfg.CHANNELS, coexist_channel,
            exe_wildcard=None, **{RemoteCfg.ORDINALS: None})
        if not isinstance(exe_wildcard, str) or not isinstance(ordinals, str):
            return None, "尚未适配[exe_wildcard, ordinals]!"
        if ordinal is None:
            for o in ordinals:
                exe_name = exe_wildcard.replace("?", o)
                inst_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.INST_PATH)
                inst_dir = os.path.dirname(inst_path)
                need_open_exe = os.path.join(inst_dir, exe_name)
                if not os.path.exists(need_open_exe):
                    ordinal = o
                    break

        if not isinstance(coexist_channel, str):
            return None, "没有可用的共存构造模式!"
        curr_ver = SwInfoFunc.calc_sw_ver(sw)
        addr_patches_dicts = subfunc_file.get_cache_cfg(
            sw, RemoteCfg.COEXIST, RemoteCfg.CHANNELS, coexist_channel, RemoteCfg.PRECISES, curr_ver)
        Printer().debug(addr_patches_dicts)
        if not isinstance(addr_patches_dicts, list):
            return None, "尚未适配[coexist_channel]!"
        for addr_patches_dict in addr_patches_dicts:
            if ("wildcard" not in addr_patches_dict or "addr" not in addr_patches_dict
                    or "patches" not in addr_patches_dict):
                return None, "适配格式错误!"
        new_files = []
        for addr_patches_dict in addr_patches_dicts:
            addr = addr_patches_dict["addr"]
            origin_path = SwInfoFunc.resolve_sw_path(sw, addr)
            name_wildcard = addr_patches_dict["wildcard"]
            new_path = os.path.join(os.path.dirname(origin_path), name_wildcard.replace("?", ordinal))
            # 拷贝到新文件
            shutil.copyfile(origin_path, new_path)
            new_files.append(new_path)
            # 修改新文件
            patches = addr_patches_dict["patches"]
            try:
                with rw_lock.gen_wlock():
                    f = open(new_path, "r+b")
                    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_WRITE)
                    for patch in patches:
                        file_offset = patch["offset"]
                        hex_str = patch["modified"]
                        coexist_hex = hex_str.replace("!!", f"{ord(ordinal):02X}")
                        patch_bytes = bytes.fromhex(coexist_hex.replace(" ", ""))
                        mm[file_offset:file_offset + len(patch_bytes)] = patch_bytes
                    mm.flush()
            except Exception as e:
                messagebox.showerror("错误", f"创建共存程序[{ordinal}]号失败!({e})")
                for new_file in new_files:
                    os.remove(new_file)
                return None, "创建共存程序失败!"
            finally:
                mm.close()
                f.close()
        # 更新配置
        new_coexist_exe_name = exe_wildcard.replace("?", ordinal)
        SwInfoFunc.ensure_coexist_acc_formatted(sw, new_coexist_exe_name)
        subfunc_file.update_sw_acc_data(
            sw, new_coexist_exe_name, channel=coexist_channel, **{AccKeys.ORDINAL: ordinal})
        return new_coexist_exe_name, ""

    @staticmethod
    def del_coexist_exe(sw, accounts) -> Tuple[list, dict]:
        failed_acc_msg_dict = {}
        success_accs = []
        curr_ver = SwInfoFunc.calc_sw_ver(sw)
        for acc in accounts:
            coexist_channel, ordinal = subfunc_file.get_sw_acc_data(
                sw, acc, **{AccKeys.COEXIST_CHANNEL: None, AccKeys.ORDINAL: None})
            channel_addresses_dict: dict = subfunc_file.get_cache_cfg(
                sw, RemoteCfg.COEXIST, RemoteCfg.CHANNELS, coexist_channel, RemoteCfg.PRECISES, curr_ver)
            try:
                try:
                    if not isinstance(channel_addresses_dict, dict):
                        raise FlowControlError
                    for addr in channel_addresses_dict:
                        origin_path = SwInfoFunc.resolve_sw_path(sw, addr)
                        name_wildcard = channel_addresses_dict[addr]["wildcard"]
                        del_path = os.path.join(
                            os.path.dirname(origin_path), name_wildcard.replace("?", ordinal)).replace("\\", "/")
                        os.remove(del_path)
                except Exception as e:
                    print(e)
                    # 未适配的, 只删除入口程序
                    sw_exe_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.INST_PATH)
                    del_path = os.path.join(
                        os.path.dirname(sw_exe_path), acc).replace("\\", "/")
                    os.remove(del_path)
                success_accs.append(acc)
            except PermissionError as pe:
                failed_acc_msg_dict[acc] = f"请确保已经退出该程序!({pe})"
                continue
            except Exception as e:
                failed_acc_msg_dict[acc] = f"发生错误!({e})"
                continue
        return success_accs, failed_acc_msg_dict

    @staticmethod
    def rebuild_coexist_exes(sw, accounts: list):
        failed_accounts_msg_dict = {}
        success_exes = []
        for acc in accounts:
            coexist_channel, ordinal = subfunc_file.get_sw_acc_data(
                sw, acc, **{AccKeys.COEXIST_CHANNEL: None, AccKeys.ORDINAL: None})
            # Printer().debug(self.sw, coexist_channel, ordinal)
            new_exe, msg = SwOperator.create_coexist_exe_core(sw, coexist_channel, ordinal)
            if not isinstance(new_exe, str):
                failed_accounts_msg_dict[acc] = msg
            else:
                success_exes.append(new_exe)
        if len(failed_accounts_msg_dict) != 0:
            msg_str = "\n".join(f"{acc}: {failed_accounts_msg_dict[acc]}" for acc in failed_accounts_msg_dict)
            messagebox.showerror("失败", f"失败账号及原因:\n{msg_str}")
        return success_exes

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

                res = CustomDialogW.ask_username_password()
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
    def open_sw(cls, sw, exe=None) -> Tuple[Optional[Process], Optional[Process]]:
        """
        根据状态以不同方式打开微信
        :param exe: 指定exe名
        :param sw: 选择软件标签
        :return: 返回主进程和子进程
        """
        multirun_mode = SwInfoFunc.get_sw_class(sw).multirun_mode
        Printer().print_vn(f"[INFO]使用{multirun_mode}模式打开{sw}...")
        proc = None
        sub_proc = None
        sw_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.INST_PATH)
        if exe:
            sw_path = os.path.join(os.path.dirname(sw_path), exe)
        if not sw_path:
            return None, None
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

    @classmethod
    def get_idle_login_wnd_and_close_if_necessary(cls, sw, close=False):
        """获取所有多余窗口,如果有需要,关闭这些窗口"""
        # 多余的窗口: 登录窗口 + 多开器进程
        all_idle_hwnds = SwInfoFunc.get_login_hwnds_of_sw(sw)
        all_idle_hwnds_set = set(all_idle_hwnds)
        Printer().print_vn(f"[INFO]{sw}登录任务前已存在的登录窗口：{all_idle_hwnds}")
        if close:
            SwOperator.kill_sw_multiple_processes(sw)
            all_idle_hwnds = hwnd_utils.try_close_hwnds_in_set_and_return_remained(all_idle_hwnds_set)
            print(f"[OK]用户选择不保留!清理后剩余的登录窗口:{all_idle_hwnds}")
        return all_idle_hwnds

    @classmethod
    def get_login_size(cls, sw):
        """获取登录窗口尺寸"""
        login_hwnds = SwInfoFunc.get_login_hwnds_of_sw(sw)
        if len(login_hwnds) > 0:
            login_hwnd = login_hwnds[0]
            login_wnd_details = hwnd_utils.get_hwnd_details_of_(login_hwnd)
            login_width = login_wnd_details["width"]
            login_height = login_wnd_details["height"]
            return login_width, login_height
        # 若没有登录窗口, 则打开一个登录窗口再获取
        login_hwnd, msg = cls.open_sw_and_return_hwnd(sw)
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
            config_addresses, = subfunc_file.get_remote_cfg(sw, config_addresses=None)
            if not isinstance(config_addresses, list) or len(config_addresses) == 0:
                messagebox.showinfo("提醒", f"{sw}平台还没有适配")
                return
            config_dir = os.path.dirname(SwInfoFunc.resolve_sw_path(sw, config_addresses[0]))
            if os.path.exists(config_dir):
                os.startfile(config_dir)

    @staticmethod
    def clear_config_file(sw, after):
        """清除登录配置文件"""
        confirm = messagebox.askokcancel(
            "确认清除",
            f"该操作将会移动{sw}登录配置文件到回收站，可右键撤销删除, 是否继续？"
        )
        if confirm:
            config_addresses, = subfunc_file.get_remote_cfg(sw, config_addresses=None)
            if not isinstance(config_addresses, list) or len(config_addresses) == 0:
                messagebox.showinfo("提醒", f"{sw}平台还没有适配")
                return

            files_to_delete = []
            for addr in config_addresses:
                origin_cfg_path = SwInfoFunc.resolve_sw_path(sw, addr)
                origin_cfg_dir = os.path.dirname(origin_cfg_path)
                origin_cfg_basename = os.path.basename(origin_cfg_path)
                acc_cfg_path_glob_wildcard = os.path.join(origin_cfg_dir, f"*_{origin_cfg_basename}")
                acc_cfg_paths = glob.glob(acc_cfg_path_glob_wildcard)
                acc_cfg_paths = [f.replace("\\", "/") for f in acc_cfg_paths]
                files_to_delete.extend([f for f in acc_cfg_paths if f != origin_cfg_path])

            if len(files_to_delete) > 0:
                # 移动文件到回收站
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

    @classmethod
    def _resolve_simple_rule(cls, mm, feature_rule_dict):
        original_features = feature_rule_dict["original"]
        modified_features = feature_rule_dict["modified"]
        # 调用扫描函数
        simple_res_dicts = cls.search_patterns_and_fill_replaces_by_features(
            mm, (original_features, modified_features)
        )
        return simple_res_dicts

    @classmethod
    def _resolve_jmp_offset_rule(cls, mm, rule_dict: dict) -> List[dict]:
        """
        处理 jmp_offset 类型补丁
        file_path: 文件映射
        rule_dict: 当前规则字典
        返回 [(original_str, modified_str), ...]
        """
        res_list = []

        original_feature = rule_dict.get("original")
        modified_feature = rule_dict.get("modified")
        target_features = rule_dict.get("targets", [])

        # 扫描 original_feature，得到精确匹配列表
        res_dicts = SwInfoUtils.search_patterns_and_fill_replaces_by_features(
            mm, ([original_feature], [modified_feature])
        )
        for res_dict in res_dicts:
            original_str = res_dict["original"]
            expanded_modified = res_dict["modified"]
            start_addr = res_dict["offset"]

            tokens = expanded_modified.split()
            i = 0
            while i < len(tokens):
                if tokens[i] == "!!":
                    j = i
                    while j < len(tokens) and tokens[j] == "!!":
                        j += 1
                    # 此时 i~j-1 是连续 !!
                    relative_pos = i
                    length = j - i
                    # 只接受长度 = 4，否则直接失败
                    if length != 4:
                        return []  # 或者直接 break / raise，根据你整体逻辑来

                    target_feature = target_features.pop(0)
                    print(f"目标特征码: {target_feature}")
                    target_res_dicts = SwInfoUtils.search_first_pattern_and_get_address_of_marked(
                        mm, [target_feature])
                    print(f"目标地址结果: {target_res_dicts}")
                    if len(target_res_dicts) != 0:
                        target_addr = target_res_dicts.pop(0).get("marked_addr")
                        print(f"目标地址: {target_addr}")
                        next_instr_addr = start_addr + relative_pos + length
                        print(f"下一条指令地址: {next_instr_addr}")
                        offset = target_addr - next_instr_addr
                        # 计算成小端序 4 字节 hex
                        offset_bytes = ByteUtils.int_to_little_endian_hex(offset, 4)
                        print(f"作差计算偏移并小端存储: {offset_bytes}")

                        # 直接替换连续 !!
                        replace_parts = offset_bytes.split()
                        if len(replace_parts) != length:
                            raise ValueError(f"替换字节长度 {len(replace_parts)} 与连续 !! 长度 {length} 不匹配")
                        tokens[i:j] = replace_parts
                        filled_modified = " ".join(tokens)
                        print(f"偏移写入后的补丁串: {filled_modified}")
                    i = j
                else:
                    i += 1
            filled_modified = " ".join(tokens)
            res_list.append(
                {
                    "offset": start_addr,
                    "original": original_str,
                    "modified": filled_modified
                }
            )

        return res_list

    @classmethod
    def resolve_rule_dict_and_return_res_dicts(cls, mm, feature_rule_dict: dict) -> List[dict]:
        res_dicts = []
        if feature_rule_dict.get("type") == "simple":
            simple_res_dicts = cls._resolve_simple_rule(mm, feature_rule_dict)
            if isinstance(simple_res_dicts, list):
                res_dicts.extend(simple_res_dicts)
        elif feature_rule_dict.get("type") == "jmp_offset":
            jmp_offset_res_dicts = cls._resolve_jmp_offset_rule(mm, feature_rule_dict)
            if isinstance(jmp_offset_res_dicts, list):
                res_dicts.extend(jmp_offset_res_dicts)
        else:
            print("未知类型")

        return res_dicts

    @staticmethod
    def _get_replacement_pairs(mm, regex, repl_bytes):
        """返回(匹配的串, 相应替换后的串, 匹配起始地址)元组列表"""
        replacement_pairs = []
        with rw_lock.gen_rlock():
            matches = list(regex.finditer(mm))
        for match in matches:
            start_addr = match.start()
            original = match.group()  # 原始匹配的字节串
            replaced = regex.sub(repl_bytes, original)  # 替换后的字节串
            replacement_pairs.append({
                "addr": start_addr,
                "original": original,
                "modified": replaced
            })
        return replacement_pairs

    @staticmethod
    def bytes_to_hex_str(byte_data) -> str:
        """将 bytes 转换为 'xx xx xx' 形式的十六进制字符串"""
        return ' '.join([f"{byte:02x}" for byte in byte_data])

    @staticmethod
    def search_patterns_and_fill_replaces_by_features(mm, features_tuple: tuple) -> Optional[List[dict]]:
        """
        从特征列表中搜索特征码并替换
        :param mm: 数据
        :param features_tuple: 特征码列表二元组(原始特征码列表，补丁特征码列表)
        :return: 替换后的二进制数据
        """
        # 检查特征码长度是否一致
        original_features, modified_features = features_tuple
        if len(original_features) != len(modified_features):
            print(f"[ERR] Original and modified features length mismatch")
            return None

        res_dicts = []
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

            pairs = SwInfoUtils._get_replacement_pairs(mm, original_regex, repl_bytes)
            if len(pairs) == 0:
                print("未识别到特征码")
                return None

            for pair_dict in pairs:
                original_bytes = pair_dict["original"]
                modified_bytes = pair_dict["modified"]
                start_addr = pair_dict["addr"]

                original_hex = SwInfoUtils.bytes_to_hex_str(original_bytes)
                modified_hex = SwInfoUtils.bytes_to_hex_str(modified_bytes)

                # repl_pos_list 中记录的是第几个字节需要替换
                for pos in repl_pos_list:
                    hex_pos = pos * 3  # 每个字节对应两个 hex 字符和一个空格
                    modified_hex = modified_hex[:hex_pos] + "!!" + modified_hex[hex_pos + 2:]

                print("识别到：")
                print(f"Original: {original_hex}")
                print(f"Modified: {modified_hex}")

                # 每条记录封装成字典存入列表
                res_dicts.append({
                    "offset": start_addr,
                    "original": original_hex,
                    "modified": modified_hex
                })

        return res_dicts

    @staticmethod
    def _calc_feature_to_regex(feature) -> Optional[re.Pattern]:
        # 分词处理
        listed_target_hex = custom_wildcard_tokenize(feature)
        # 检查非法 ... 使用
        if ... in listed_target_hex:
            print(f"[ERR] Wildcard <{patt2hex(listed_target_hex)}> has invalid token ...")
            return None
        # 构建正则表达式
        regex_bytes = b""
        for p in listed_target_hex:
            if p == "??":
                regex_bytes += b"(.)"
            else:
                regex_bytes += re.escape(bytes.fromhex(p))
        print("构建匹配模式：")
        print(f"regex_bytes: {regex_bytes}")
        regex = re.compile(regex_bytes, re.DOTALL)
        return regex

    @classmethod
    def search_patterns_by_features(cls, dll_path: str, features: list) -> Optional[List[dict]]:
        """
        从目标特征码列表中扫描目标地址
        :param dll_path: DLL文件路径
        :param features: 特征码列表
        :return: [{'original': 匹配到的原始串, 'addr': 起始地址}, ...]
        """
        res_dicts = []
        with open(dll_path, "rb") as f:
            data = f.read()
        for feature in features:
            print("--------------------------------------------------------")
            print(f"目标特征码: {feature}")
            regex = cls._calc_feature_to_regex(feature)
            if regex is None:
                continue
            # 找匹配
            matches = list(regex.finditer(data))
            if len(matches) == 0:
                print("未识别到目标特征码")
                return None
            for match in matches:
                original = match.group()
                start_addr = match.start()

                original_hex = SwInfoUtils.bytes_to_hex_str(original)

                print("识别到：")
                print(f"Original: {original_hex}, Addr: {start_addr:#x}")

                res_dicts.append({
                    "original": original_hex,
                    "addr": start_addr
                })
        return res_dicts

    @classmethod
    def search_first_pattern_and_get_address_of_marked(
            cls, mm, target_features: list) -> List[dict]:
        """
        搜索第一个带!标记的特征串, 返回其地址 + 标记偏移
        :param mm: DLL文件路径
        :param target_features: 带!的特征码列表 (例如: ["48 8B !05 ?? ?? ?? ?? 48 8B"])
        :return: {'original': 原始特征码匹配串, 'marked_addr': 地址(基地址 + !偏移)}
        """
        res_dicts = []
        for feature in target_features:
            # 找第一个 ! 出现的位置
            tokens = feature.split()
            bang_index = None
            for i, tok in enumerate(tokens):
                if tok.startswith("!"):
                    bang_index = i
                    tokens[i] = tok[1:]  # 去掉 !
                    break
            if bang_index is None:
                continue  # 跳过没有 ! 的特征串
            # 清洗掉剩余的 ! 符号
            clean_feature = " ".join(tok.lstrip("!") for tok in tokens)
            # 扫描
            regex = cls._calc_feature_to_regex(clean_feature)
            with rw_lock.gen_rlock():
                match = regex.search(mm)
            if match:
                original = match.group()
                start_addr = match.start()
                # 最终结果
                original_hex = SwInfoUtils.bytes_to_hex_str(original)
                res_dicts.append({
                    "original": original_hex,
                    "marked_addr": start_addr + bang_index
                })
        return res_dicts

    @staticmethod
    def _create_path_finders_of_(path_tag) -> list:
        """定义方法列表"""
        if path_tag == LocalCfg.INST_PATH:
            return [
                SwInfoUtils.get_sw_install_path_from_process,
                SwInfoUtils.get_sw_install_path_from_machine_register,
                SwInfoUtils.get_sw_install_path_from_user_register,
                SwInfoUtils.get_sw_install_path_by_guess,
            ]
        elif path_tag == LocalCfg.DATA_DIR:
            return [
                SwInfoUtils.get_sw_data_dir_from_user_register,
                SwInfoUtils.get_sw_data_dir_by_guess,
                SwInfoUtils._get_sw_data_dir_from_other_sw,
            ]
        elif path_tag == LocalCfg.DLL_DIR:
            return [
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
