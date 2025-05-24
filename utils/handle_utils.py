# handle_utils.py
import ctypes
import re
import subprocess
import time

from win32con import PROCESS_ALL_ACCESS

from resources import Config
from utils import process_utils
from utils.logger_utils import mylogger as logger
from utils.logger_utils import myprinter as printer

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
OpenProcess = kernel32.OpenProcess


def get_process_handle(pid):
    """
    通过pid获得句柄
    :param pid: 进程id
    :return: 获得的句柄
    """
    handle = OpenProcess(PROCESS_ALL_ACCESS, False, pid)

    if handle == 0 or handle == -1:  # 0 和 -1 都表示失败
        error = ctypes.get_last_error()
        print(f"无法获取进程句柄，错误码：{error}")
        return None

    return handle


def close_handles_by_matches(handle_exe, matches):
    """
    封装关闭句柄的操作，遍历所有匹配项并尝试关闭每个句柄。

    参数:
        handle_exe (str): 用于关闭句柄的可执行文件路径
        matches (list): 包含进程 ID 和句柄的元组列表，格式为 [(wechat_pid, handle), ...]

    返回:
        list: 成功关闭的句柄列表，格式为 [(wechat_pid, handle), ...]
    """
    # 用于存储成功关闭的句柄和成功元组
    handles_closed = []
    successes = []

    # 遍历所有匹配项，尝试关闭每个句柄
    for wechat_pid, handle in matches:
        printer.print_vn(f"hwnd:{handle}, pid:{wechat_pid}")
        stdout = None
        # 尝试执行命令获取输出
        try:
            # 构建命令
            formatted_handle_exe = handle_exe.replace("\\", "/")
            formatted_handle = handle.replace("\\", "/")
            command = " ".join([f'"{formatted_handle_exe}"', '-c', f'"{formatted_handle}"',
                                '-p', str(wechat_pid), '-y'])
            printer.print_vn(f"指令：{command}")
            # 使用 Popen 启动子程序并捕获输出
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
            # 检查子进程是否具有管理员权限
            if process_utils.is_process_admin(process.pid):
                printer.print_vn(f"子进程 {process.pid} 以管理员权限运行")
            else:
                printer.print_vn(f"子进程 {process.pid} 没有管理员权限")
            # 获取输出结果
            stdout, stderr = process.communicate()
            # 检查返回的 stdout 和 stderr
            if stdout:
                printer.print_vn(f"输出：{stdout}完毕。")
            if stderr:
                printer.print_vn(f"错误：{stderr}")
        except subprocess.CalledProcessError as e:
            logger.error(f"命令执行失败，退出码 {e.returncode}")
        except Exception as e:
            logger.error(f"发生异常: {e}")

        # 如果stdout包含"Error closing handle"，则失败，下一个
        if stdout is None or "Error closing handle:" in stdout:
            printer.print_vn(f"句柄关闭失败: hwnd:{handle}, pid:{wechat_pid}")
            successes.append(False)
            continue

        printer.print_vn(f"成功关闭句柄: hwnd:{handle}, pid:{wechat_pid}")
        handles_closed.append((wechat_pid, handle))
        successes.append(True)

    printer.print_vn(f"成功关闭的句柄列表: {handles_closed}")
    return all(successes), handles_closed


def close_sw_mutex_by_handle(handle_exe, exe, handle_regex_dicts):
    """通过handle，根据规则字典对指定程序查找互斥体并关闭"""
    if handle_regex_dicts is None or len(handle_regex_dicts) == 0:
        return False, []

    handles_closed_lists = []
    successes = []
    for handle_regex_dict in handle_regex_dicts:
        try:
            handle_name, regex = handle_regex_dict.get("handle_name"), handle_regex_dict.get("regex")
            printer.vital(f"handle模式")
            printer.print_vn(f"进入了关闭互斥体的方法...")
            printer.print_vn(f"句柄名：{handle_name}")
            printer.print_vn(f"模式：{regex}")
            start_time = time.time()

            formatted_handle_exe = handle_exe.replace("\\", "/")
            formatted_exe = exe.replace("\\", "/")
            formatted_handle_name = handle_name.replace("\\", "/")
            # 获取句柄信息
            handle_cmd = " ".join([f'"{formatted_handle_exe}"', '-a', '-p',
                                   f'"{formatted_exe}"', f'"{formatted_handle_name}"'])
            printer.vital(f"handle-查找句柄")
            printer.print_vn(f"指令：{handle_cmd}")
            handle_output = subprocess.check_output(handle_cmd,
                                                    creationflags=subprocess.CREATE_NO_WINDOW,
                                                    text=True)
            printer.print_vn(f"信息：{handle_output}")
            printer.print_vn(f"用时：{time.time() - start_time:.4f}秒")

            # 匹配所有 PID 和句柄信息
            printer.vital(f"handle-匹配句柄")
            matches = re.findall(regex, handle_output)
            if matches:
                printer.print_vn(f"含互斥体：{matches}")
                printer.vital("handle-关闭句柄")
                success, handles_closed = close_handles_by_matches(Config.HANDLE_EXE_PATH, matches)
                handles_closed_lists.append(close_handles_by_matches(Config.HANDLE_EXE_PATH, matches))
                successes.append(success)
            else:
                printer.print_vn(f"无互斥体")
        except Exception as e:
            logger.error(f"关闭句柄失败：{e}")
    return all(successes), handles_closed_lists


if __name__ == '__main__':
    pass
