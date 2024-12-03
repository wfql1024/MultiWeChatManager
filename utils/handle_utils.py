import os
import re
import shutil
from http.server import executable

from resources import Config
import time
import subprocess
from utils import process_utils


def close_handles_by_matches(handle_exe, matches):
    """
    封装关闭句柄的操作，遍历所有匹配项并尝试关闭每个句柄。

    参数:
        handle_exe (str): 用于关闭句柄的可执行文件路径
        matches (list): 包含进程 ID 和句柄的元组列表，格式为 [(wechat_pid, handle), ...]

    返回:
        list: 成功关闭的句柄列表，格式为 [(wechat_pid, handle), ...]
    """
    # 用于存储成功关闭的句柄
    successful_closes = []

    # 遍历所有匹配项，尝试关闭每个句柄
    for wechat_pid, handle in matches:
        print(f"尝试关闭互斥体句柄: hwnd:{handle}, pid:{wechat_pid}")
        try:
            stdout = None
            try:
                # 构建命令
                command = " ".join([handle_exe, '-c', handle, '-p', str(wechat_pid), '-y'])
                print(f"执行命令：{command}")

                # 使用 Popen 启动子程序并捕获输出
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                           shell=True)

                # 检查子进程是否具有管理员权限
                if process_utils.is_process_admin(process.pid):
                    print(f"子进程 {process.pid} 以管理员权限运行")
                else:
                    print(f"子进程 {process.pid} 没有管理员权限")

                # 获取输出结果
                stdout, stderr = process.communicate()

                # 检查返回的 stdout 和 stderr
                if stdout:
                    print(f"输出：{stdout}完毕。")
                if stderr:
                    print(f"错误：{stderr}")
            except subprocess.CalledProcessError as e:
                print(f"命令执行失败，退出码 {e.returncode}")

            # 如果stdout包含"Error closing handle"，跳过该句柄
            if stdout is not None and "Error closing handle:" in stdout:
                continue

            print(f"成功关闭句柄: hwnd:{handle}, pid:{wechat_pid}")
            successful_closes.append((wechat_pid, handle))
        except subprocess.CalledProcessError as e:
            print(f"无法关闭句柄 PID: {wechat_pid}, 错误信息: {e}")

    print(f"成功关闭的句柄列表: {successful_closes}")
    return successful_closes


def close_sw_mutex_by_handle(handle_exe, exe, dict_list):
    """
    通过微信进程id查找互斥体并关闭
    :return: 是否成功
    """
    if dict_list is None or len(dict_list) == 0:
        return []
    success_lists = []
    for item in dict_list:
        handle_name, regex = item.get("handle_name"), item.get("regex")
        print(handle_name, regex)
        print(f"进入了关闭互斥体的方法...")
        start_time = time.time()

        # 获取句柄信息
        handle_info = subprocess.check_output([handle_exe, '-a', '-p', exe, handle_name]).decode()
        print(f"完成获取句柄信息：{handle_info}")
        print(f"{time.time() - start_time}")

        # 匹配所有 PID 和句柄信息
        matches = re.findall(regex, handle_info)
        if matches:
            print(f"找到互斥体：{matches}")
            success_lists.append(close_handles_by_matches(Config.HANDLE_EXE_PATH, matches))
        else:
            print(f"没有找到任何互斥体")
    return success_lists


if __name__ == '__main__':
    pass











