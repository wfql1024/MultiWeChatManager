import ctypes
import os
import re
import subprocess
import time
from ctypes import wintypes

from resources import Config
from utils import process_utils


def close_mutex_of_pids_by_handle():
    """
    通过微信进程id查找互斥体并关闭
    :return: 是否成功
    """
    print(f"进入了关闭互斥体的方法...")
    # 定义句柄名称
    handle_name = "_WeChat_App_Instance_Identity_Mutex_Name"
    start_time = time.time()
    handle_exe_path = os.path.join(Config.PROJ_EXTERNAL_RES_PATH, 'handle.exe')

    # 获取句柄信息
    handle_info = subprocess.check_output([handle_exe_path, '-a', '-p', f"WeChat", handle_name]).decode()
    print(f"完成获取句柄信息：{handle_info}")
    print(f"{time.time() - start_time}")

    # 匹配所有 PID 和句柄信息
    matches = re.findall(r"pid:\s*(\d+).*?(\w+):\s*\\Sessions", handle_info)
    if matches:
        print(f"找到互斥体：{matches}")
    else:
        print(f"没有找到任何互斥体")
        return []

    # 用于存储成功关闭的句柄
    successful_closes = []

    # 遍历所有匹配项，尝试关闭每个句柄
    for wechat_pid, handle in matches:
        print(f"尝试关闭互斥体句柄: hwnd:{handle}, pid:{wechat_pid}")
        try:
            stdout = None
            try:
                command = " ".join([handle_exe_path, '-c', handle, '-p', str(wechat_pid), '-y'])
                print(f"执行命令：{command}")
                # 使用 Popen 启动子程序并捕获输出
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                           shell=True)
                # 检查子程序是否具有管理员权限
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
                print(f"Command failed with exit code {e.returncode}")
            if stdout is not None and "Error closing handle:" in stdout:
                continue
            print(f"成功关闭句柄: hwnd:{handle}, pid:{wechat_pid}")
            successful_closes.append((wechat_pid, handle))
        except subprocess.CalledProcessError as e:
            print(f"无法关闭句柄 PID: {wechat_pid}, 错误信息: {e}")

    print(f"成功关闭的句柄列表: {successful_closes}")
    return successful_closes









