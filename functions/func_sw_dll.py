import os
import shutil
from tkinter import messagebox
from typing import Tuple, Optional

import psutil
import winshell

from functions import subfunc_file
from public_class.enums import RemoteCfg
from utils import file_utils, process_utils
from utils.file_utils import DllUtils
from utils.logger_utils import mylogger as logger


class SwOperator:
    pass


def ask_for_manual_terminate_or_force(executable):
    processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.name().lower() == executable.lower():
            processes.append(proc)
    if processes:
        answer = messagebox.askokcancel(
            "警告",
            f"检测到正在使用{executable}。该操作需要退出进程，请先手动退出，否则将会强制关闭。是否继续？"
        )
        if answer is not True:
            return

        still_running = process_utils.try_terminate_executable(executable)
        if len(still_running) != 0:
            messagebox.showerror("错误", f"无法终止微信进程：{still_running}")
            return False
        return True

    return True


def backup_dll(sw, dll_dir):
    """备份当前的dll"""
    # 获取桌面路径
    desktop_path = winshell.desktop()

    patch_dll, = subfunc_file.get_details_from_remote_setting_json(sw, patch_dll=None)
    dll_path = os.path.join(dll_dir, patch_dll)

    bak_path = os.path.join(dll_dir, f"{patch_dll}.bak")
    bak_desktop_path = os.path.join(desktop_path, f"{patch_dll}.bak")
    curr_ver = file_utils.get_file_version(dll_path)
    not_same_version = True
    if os.path.exists(bak_path):
        not_same_version = file_utils.get_file_version(bak_path) != curr_ver

    if not os.path.exists(bak_path) or (
            os.path.exists(bak_path) and not_same_version):
        print("没有备份")
        messagebox.showinfo("提醒",
                            "当前是您该版本首次切换模式，已将原本的WeChatWin.dll拷贝为WeChatWin_bak.dll，并也拷贝到桌面，可另外备份保存。")
        shutil.copyfile(dll_path, bak_path)
        shutil.copyfile(dll_path, bak_desktop_path)


def identify_dll(sw, mode, dll_dir):
    """检查当前的dll状态，判断是否为全局多开或者不可用"""
    # 条件检查
    config_data = subfunc_file.read_remote_cfg_in_rules()
    if not config_data:
        return None, "错误：没有数据"
    patch_dll, ver_dict = subfunc_file.get_details_from_remote_setting_json(sw, patch_dll=None, **{mode: None})
    if patch_dll is None or ver_dict is None:
        return None, f"错误：{mode}平台未适配"
    ver_dict = config_data.get(sw, {}).get(mode, None)
    dll_path = os.path.join(dll_dir, patch_dll).replace("\\", "/")
    tag, msg, _, _ = SwOperatorUtils.identify_dll_of_ver_by_dict(ver_dict, dll_path)
    return tag, msg


def switch_dll(sw, mode, dll_dir) -> Tuple[Optional[bool], str]:
    """
    切换全局多开状态
    :param sw: 平台
    :param mode: 修改的模式
    :param dll_dir: dll目录
    :return: 成功与否，提示信息
    """
    if mode == RemoteCfg.MULTI:
        mode_text = "全局多开"
    elif mode == RemoteCfg.REVOKE:
        mode_text = "防撤回"
    else:
        return False, "未知模式"

    config_data = subfunc_file.read_remote_cfg_in_rules()
    if not config_data:
        return False, "没有数据"
    executable, = subfunc_file.get_details_from_remote_setting_json(sw, executable=None)
    if executable is None:
        return False, "该平台暂未适配"
    # 提醒用户手动终止微信进程
    answer = ask_for_manual_terminate_or_force(executable)
    if answer is not True:
        return False, "用户取消操作"

    # 条件检查
    patch_dll, = subfunc_file.get_details_from_remote_setting_json(sw, patch_dll=None)
    if patch_dll is None:
        return False, "该平台未适配"
    dll_path = os.path.join(dll_dir, patch_dll).replace("\\", "/")
    ver_dict = config_data.get(sw, {}).get(mode, None)
    # 定义目标路径和文件名
    tag, msg, original_patterns, modified_patterns = SwOperatorUtils.identify_dll_of_ver_by_dict(
        ver_dict, dll_path)
    dll_path = os.path.join(dll_dir, patch_dll)
    try:
        if tag is True:
            print(f"当前：{mode}已开启")
            success = DllUtils.batch_atomic_replace_hex_patterns(
                dll_path, (modified_patterns, original_patterns))
            if success:
                return True, f"成功关闭:{mode_text}"

        elif tag is False:
            print(f"当前：{mode}未开启")
            backup_dll(sw, dll_dir)

            success = DllUtils.batch_atomic_replace_hex_patterns(
                dll_path, (original_patterns, modified_patterns))
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


class SwOperatorUtils:
    @staticmethod
    def identify_dll_of_ver_by_dict(data, dll_path) \
            -> Tuple[Optional[bool], str, Optional[list], Optional[list]]:
        cur_sw_ver = file_utils.get_file_version(dll_path)
        ver_adaptation = data.get(cur_sw_ver, None)
        print(ver_adaptation)
        if ver_adaptation is None:
            return None, f"错误：未找到版本{cur_sw_ver}的适配", None, None

        # 一个版本可能有多个匹配，只要有一个匹配成功就返回
        for match in ver_adaptation:
            original_list = match["original"]
            modified_list = match["modified"]
            has_original_list = DllUtils.find_patterns_from_dll_in_hexadecimal(dll_path, *original_list)
            has_modified_list = DllUtils.find_patterns_from_dll_in_hexadecimal(dll_path, *modified_list)
            # list转成集合，集合中只允许有一个元素，True表示list全都是True，False表示list全都是False，其他情况不合法
            has_original_set = set(has_original_list)
            has_modified_set = set(has_modified_list)
            if len(has_original_set) != 1 or len(has_modified_set) != 1:
                continue
            all_original = True if True in has_original_set else False if False in has_original_set else None
            all_modified = True if True in has_modified_set else False if False in has_modified_set else None
            if all_original is True and all_modified is False:
                return False, "未开启", original_list, modified_list
            elif all_original is False and all_modified is True:
                return True, "已开启", original_list, modified_list
            elif all_original is True or all_modified is True:
                return None, "错误，非独一无二的特征码", None, None
        return None, "不可用", None, None
        # try:
        # except (PermissionError, FileNotFoundError, KeyError, TimeoutError, RuntimeError, Exception) as e:
        #     logger.error(e)
        #     error_msg = {
        #         PermissionError: "权限不足，无法检查 DLL 文件。",
        #         FileNotFoundError: "未找到文件，请检查路径。",
        #         KeyError: "未找到该版本的适配：",
        #         TimeoutError: "请求超时。",
        #         RuntimeError: "运行时错误。",
        #         Exception: "发生错误。"
        #     }.get(type(e), "发生未知错误。")
        #     return None, f"错误：{error_msg}{str(e)}", None, None
