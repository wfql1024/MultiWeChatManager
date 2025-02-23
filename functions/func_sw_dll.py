import os
import shutil
from tkinter import messagebox

import psutil
import winshell

from functions import subfunc_file
from utils import file_utils, process_utils
from utils.file_utils import DLLUtils
from utils.logger_utils import mylogger as logger


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


def check_dll(sw, mode, dll_dir):
    """检查当前的dll状态，判断是否为全局多开或者不可用"""
    patch_dll, = subfunc_file.get_details_from_remote_setting_json(sw, patch_dll="WeChatWin.dll")
    if patch_dll is None:
        return "错误：该平台未适配", None, None

    dll_path = os.path.join(dll_dir, patch_dll).replace("\\", "/")
    cur_sw_ver = file_utils.get_file_version(dll_path)
    config_data = subfunc_file.read_remote_cfg_in_rules()

    if not config_data:
        return "错误：没有数据", None, None

    try:
        result1 = config_data[sw][mode][cur_sw_ver]["STABLE"]["pattern"]
        result2 = config_data[sw][mode][cur_sw_ver]["PATCH"]["pattern"]
        pattern1_hex_list = result1.split(',')
        pattern2_hex_list = result2.split(',')
    except Exception as e:
        logger.error(e)
        return "错误：未找到该版本的适配", None, None

    try:
        for pattern1_hex, pattern2_hex in zip(pattern1_hex_list, pattern2_hex_list):
            has_pattern1 = DLLUtils.find_patterns_from_dll_in_hexadecimal(dll_path, pattern1_hex)
            has_pattern2 = DLLUtils.find_patterns_from_dll_in_hexadecimal(dll_path, pattern2_hex)
            if has_pattern1 and not has_pattern2:
                return "未开启", pattern1_hex, pattern2_hex
            elif has_pattern2 and not has_pattern1:
                return "已开启", pattern1_hex, pattern2_hex
            elif has_pattern1 and has_pattern2:
                return "错误，非独一无二的特征码", None, None
        return "不可用", None, None
    except (PermissionError, FileNotFoundError, KeyError, TimeoutError, RuntimeError, Exception) as e:
        error_msg = {
            PermissionError: "权限不足，无法检查 DLL 文件。",
            FileNotFoundError: "未找到文件，请检查路径。",
            KeyError: "未找到该版本的适配：",
            TimeoutError: "请求超时。",
            RuntimeError: "运行时错误。",
            Exception: "发生错误。"
        }.get(type(e), "发生未知错误。")
        return f"错误：{error_msg}{str(e)}", None, None


def switch_dll(sw, mode, dll_dir):
    """
    切换全局多开状态
    :param sw: 平台
    :param mode: 修改的模式
    :param dll_dir: dll目录
    :return: None表示失败，bool型表示是否切换到补丁模式
    """
    if mode == "multiple":
        mode_text = "全局多开"
    elif mode == "revoke":
        mode_text = "防撤回"
    else:
        return

    patch_dll, executable = subfunc_file.get_details_from_remote_setting_json(sw, patch_dll=None, executable=None)
    if patch_dll is None or executable is None:
        messagebox.showerror("错误", "该版本暂无适配")
        return

    # 提醒用户手动终止微信进程
    answer = ask_for_manual_terminate_or_force(executable)
    if answer is not True:
        return

    # 定义目标路径和文件名
    current_mode, hex_stable_pattern, hex_patch_pattern = check_dll(sw, mode, dll_dir)
    # print(current_mode, hex_stable_pattern, hex_patch_pattern)
    dll_path = os.path.join(dll_dir, patch_dll)
    try:
        if current_mode == "已开启":
            print(f"当前：{mode}已开启")
            success = DLLUtils.edit_patterns_in_dll_in_hexadecimal(
                dll_path, **{hex_patch_pattern: hex_stable_pattern})
            if success:
                messagebox.showinfo("提示", f"成功关闭:{mode_text}")
                return

        elif current_mode == "未开启":
            print(f"当前：{mode}未开启")
            backup_dll(sw, dll_dir)

            success = DLLUtils.edit_patterns_in_dll_in_hexadecimal(
                dll_path, **{hex_stable_pattern: hex_patch_pattern})
            if success:
                messagebox.showinfo("提示", f"成功开启:{mode_text}")
                return
        messagebox.showinfo("提示", "请重试！")
        return
    except (psutil.AccessDenied, PermissionError, Exception) as e:
        error_msg = {
            PermissionError: "权限不足，无法修改 DLL 文件。",
            psutil.AccessDenied: "无法终止微信进程，请以管理员身份运行程序。",
            Exception: "发生错误。"
        }.get(type(e), "发生未知错误。")
        logger.error(f"切换{mode_text}时发生错误: {str(e)}")
        messagebox.showinfo("错误", f"切换{mode_text}时发生错误: {str(e)}\n{error_msg}")
