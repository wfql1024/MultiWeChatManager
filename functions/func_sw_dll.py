import mmap
import os
import shutil
import time
from tkinter import messagebox

import psutil
import winshell

from functions import subfunc_file
from utils import file_utils

# TODO:提取查找字节和修改字节的方法到utils，提取出一个检查是否有进程没有关闭的方法

def check_dll(sw, mode, dll_dir, cur_sw_ver):

    """检查当前的dll状态，判断是否为全局多开或者不可用"""
    patch_dll, = subfunc_file.get_details_from_remote_setting_json(sw, patch_dll="WeChatWin.dll")
    dll_path = os.path.join(dll_dir, patch_dll).replace("\\", "/")

    try:
        with open(dll_path, 'rb') as f:
            dll_content = f.read()

        config_data = subfunc_file.try_get_local_cfg()

        if not config_data:
            return "错误：没有数据", None, None

        result1 = config_data[sw][mode][cur_sw_ver]["STABLE"]["pattern"]
        result2 = config_data[sw][mode][cur_sw_ver]["PATCH"]["pattern"]

        pattern1_hex_list = result1.split(',')
        pattern2_hex_list = result2.split(',')

        for pattern1_hex, pattern2_hex in zip(pattern1_hex_list, pattern2_hex_list):
            pattern1 = bytes.fromhex(pattern1_hex)
            pattern2 = bytes.fromhex(pattern2_hex)

            has_pattern1 = pattern1 in dll_content
            has_pattern2 = pattern2 in dll_content

            if has_pattern1 and not has_pattern2:
                return "未开启", pattern1, pattern2
            elif has_pattern2 and not has_pattern1:
                return "已开启", pattern1, pattern2
            elif has_pattern1 and has_pattern2:
                return "错误，匹配到多条", None, None
        return "不可用", None, None
    except (PermissionError, FileNotFoundError, KeyError, TimeoutError, RuntimeError, Exception) as e:
        subfunc_file.force_fetch_remote_encrypted_cfg()
        error_msg = {
            PermissionError: "权限不足，无法检查 DLL 文件。",
            FileNotFoundError: "未找到文件，请检查路径。",
            KeyError: "未找到该版本的适配：",
            TimeoutError: "请求超时。",
            RuntimeError: "运行时错误。",
            Exception: "发生错误。"
        }.get(type(e), "发生未知错误。")
        return f"错误：{error_msg}{str(e)}", None, None

def switch_dll(sw, mode, dll_dir, ver):
    """切换全局多开状态"""
    patch_dll, executable = subfunc_file.get_details_from_remote_setting_json(sw, patch_dll=None, executable=None)
    if patch_dll is None or executable is None:
        messagebox.showerror("错误", "该版本暂无适配")
        return False

    # 尝试终止微信进程
    wechat_processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.name().lower() == executable.lower():
            wechat_processes.append(proc)
    if wechat_processes:
        print("发现正在运行的微信进程，尝试关闭...")
        for proc in wechat_processes:
            try:
                proc.terminate()
            except psutil.AccessDenied:
                print(f"无法终止进程 {proc.pid}，可能需要管理员权限。")
            except Exception as e:
                print(f"终止进程 {proc.pid} 时出错: {str(e)}")
        # 等待进程完全关闭
        time.sleep(2)
        # 检查是否所有进程都已关闭
        still_running = [p for p in wechat_processes if p.is_running()]
        if still_running:
            print("警告：以下微信进程仍在运行：")
            for p in still_running:
                print(f"PID: {p.pid}")
            print("请手动关闭这些进程后再继续。")
            return False

    # 获取桌面路径
    desktop_path = winshell.desktop()
    # 定义目标路径和文件名
    dll_path = os.path.join(dll_dir, patch_dll)
    bak_path = os.path.join(dll_dir, f"{patch_dll}.bak")
    bak_desktop_path = os.path.join(desktop_path, f"{patch_dll}.bak")
    not_same_version = True
    if os.path.exists(bak_path):
        not_same_version = file_utils.get_file_version(bak_path) != file_utils.get_file_version(dll_path)

    try:
        with open(dll_path, 'r+b') as f:
            result = None
            mmap_file = mmap.mmap(f.fileno(), 0)

            current_mode, stable_pattern, patch_pattern = check_dll(sw, mode, dll_dir, ver)

            if current_mode == "已开启":
                print(f"当前：{mode}已开启")
                pos = mmap_file.find(patch_pattern)
                if pos != -1:
                    mmap_file[pos:pos + len(patch_pattern)] = stable_pattern
                    print("替换完成")
                    result = False
                else:
                    print("未找到对应的HEX模式")
            elif current_mode == "未开启":
                print(f"当前：{mode}未开启")
                if not os.path.exists(bak_path) or (
                        os.path.exists(bak_path) and not_same_version):
                    print("没有备份")
                    messagebox.showinfo("提醒",
                                        "当前是您该版本首次切换模式，已将原本的WeChatWin.dll拷贝为WeChatWin_bak.dll，并也拷贝到桌面，可另外备份保存。")
                    shutil.copyfile(dll_path, bak_path)
                    shutil.copyfile(dll_path, bak_desktop_path)
                pos = mmap_file.find(stable_pattern)
                if pos != -1:
                    mmap_file[pos:pos + len(stable_pattern)] = patch_pattern
                    print("替换完成")
                    result = True
                else:
                    print("未找到对应的HEX模式")
            else:
                print("非法操作")

            mmap_file.flush()
            mmap_file.close()

        print("所有操作完成")
        return result

    except PermissionError:
        print("权限不足，无法修改 DLL 文件。请以管理员身份运行程序。")
        return result
    except Exception as e:
        print(f"修改 DLL 文件时出错: {str(e)}")
        return result
