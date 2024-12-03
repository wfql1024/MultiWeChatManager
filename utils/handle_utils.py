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


def close_all_new_weixin_mutex_by_handle(handle_exe):
    """
    通过微信进程id查找互斥体并关闭
    :return: 是否成功
    """
    match_lists = []
    print(f"进入了关闭互斥体的方法...")
    # 定义句柄名称
    handle_name = "lock.ini"
    start_time = time.time()
    # 获取句柄信息
    handle_info = subprocess.check_output([handle_exe, '-a', '-p', f"Weixin", handle_name]).decode()
    print(f"完成获取句柄信息：{handle_info}")
    print(f"{time.time() - start_time}")
    # 匹配所有 PID 和句柄信息
    matches = re.findall(r"pid:\s*(\d+)\s+type:\s*File\s+([0-9A-Fa-f]+):", handle_info)
    print(matches)
    match_lists.append(matches)

    # 定义句柄名称
    handle_name = "global_config"
    start_time = time.time()
    # 获取句柄信息
    handle_info = subprocess.check_output([handle_exe, '-a', '-p', f"Weixin", handle_name]).decode()
    print(f"完成获取句柄信息：{handle_info}")
    print(f"{time.time() - start_time}")
    # 匹配所有 PID 和句柄信息
    matches = re.findall(r"pid:\s*(\d+)\s+type:\s*File\s+([0-9A-Fa-f]+):", handle_info)
    print(matches)
    match_lists.append(matches)

    successful_closes = []
    for match_list in match_lists:
        if match_list:
            print(f"找到文件锁：{match_list}")
            # 关闭句柄
            successful_closes.append(close_handles_by_matches(handle_exe, match_list))
        else:
            print(f"没有找到任何互斥体")

    return successful_closes


def close_all_old_wechat_mutex_by_handle(handle_exe, sw, dict_list):
    """
    通过微信进程id查找互斥体并关闭
    :return: 是否成功
    """
    success_lists = []
    for item in dict_list:
        handle_name, regex = item.get("handle_name"), item.get("regex")
        print(handle_name, regex)
        print(f"进入了关闭互斥体的方法...")
        start_time = time.time()

        # 获取句柄信息
        handle_info = subprocess.check_output([handle_exe, '-a', '-p', sw, handle_name]).decode()
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
    close_all_new_weixin_mutex_by_handle(Config.HANDLE_EXE_PATH)
    # 构建源文件和目标文件路径
    # source_dir = r"E:\Now\Desktop\不吃鱼的猫"
    source_dir = r"E:\Now\Desktop\极峰创科"
    target_dir = r'E:\data\Tencent\xwechat_files\all_users\config'

    # 如果目录存在，先删除
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)

    time.sleep(1)

    # 复制配置文件
    try:
        shutil.copytree(source_dir, target_dir)
    except Exception as e:
        print(f"复制配置文件失败: {e}")

    os.startfile('D:\software\Tencent\Weixin\Weixin.exe')











