# 导入必要的库
import subprocess
import re
import time
import psutil


def close_mutex(process_id):
    # 定义句柄名称
    handle_name = "_WeChat_App_Instance_Identity_Mutex_Name"

    start_time = time.time()

    # 获取句柄信息
    handle_info = subprocess.check_output(['handle.exe', '-a', handle_name, '-p', process_id]).decode()
    print(handle_info)
    print(time.time() - start_time)
    # # 将句柄信息写入 2.txt
    # 在powershell中无法直接使用返回的字符串进行正则表达式，所以整了个文件中转

    # with open("2.txt", "w") as f:
    #     f.write(handle_info)
    #
    # # 从 2.txt 读取句柄信息
    # with open("2.txt", "r") as f:
    #     handle_info = f.read()

    # 匹配 PID 和句柄
    match = re.search(r"pid:\s*(\d+).*?(\w+):\s*\\Sessions", handle_info)
    if match:
        wechat_pid = match.group(1)
        handle = match.group(2)
    else:
        exit()

    print(wechat_pid)
    print(handle)
    print(time.time() - start_time)

    # 将 PID 写入 1.txt
    # with open("1.txt", "w") as f:
    #     f.write(f"handle: {handle}\n")
    #     f.write(f"PID: {wechat_pid}\n")

    # 尝试关闭句柄
    try:
        subprocess.run(['handle.exe', '-c', handle, '-p', wechat_pid, '-y'], check=True)
        print(time.time() - start_time)
        # with open("1.txt", "a") as f:
        #     f.write(f"run！PID: {wechat_pid}\n")
    except subprocess.CalledProcessError as e:
        print(f"无法关闭句柄 PID: {wechat_pid}，错误信息: {e}\n")
        # with open("1.txt", "a") as f:
        #     f.write(f"无法关闭句柄 PID: {wechat_pid}，错误信息: {e}\n")


def find_threads_by_pid(wechat_pid):
    try:
        # 获取指定PID的进程
        process = psutil.Process(wechat_pid)
        print(f"Found WeChat process (PID: {wechat_pid})")

        # 获取该进程的所有线程
        threads = process.threads()

        for thread in threads:
            print(f"Thread ID: {thread.id}, User Time: {thread.user_time}, System Time: {thread.system_time}")

        # 你可以在此处对线程进行进一步操作，比如终止某个特定线程
        # psutil 不直接支持终止线程，你需要借助 ctypes 或其他方式操作系统级 API
    except psutil.NoSuchProcess:
        print(f"No process found with PID {wechat_pid}")
    except psutil.AccessDenied:
        print(f"Access denied to process with PID {wechat_pid}")


def find_handle_by_name(wechat_pid, handle_name):
    try:
        # 通过 handle.exe 获取指定 PID 的句柄信息
        handle_info = subprocess.check_output(['handle.exe', '-p', str(wechat_pid)]).decode()
        print(handle_info)

        # 正则表达式匹配与指定名称相关的句柄
        pattern = re.compile(rf"{handle_name}", re.IGNORECASE)

        # 查找匹配的句柄
        matches = pattern.findall(handle_info)
        if matches:
            print(f"Found handle with name '{handle_name}' in process PID: {wechat_pid}")
            print(f"Handle info:\n{handle_info}")
        else:
            print(f"No handle with name '{handle_name}' found in process PID: {wechat_pid}")
    except subprocess.CalledProcessError as e:
        print(f"Error while fetching handle info for PID: {wechat_pid}, Error: {e}")


if __name__ == '__main__':
    # # 示例调用
    # wechat_pids = [50584, 48596]  # 替换为你实际的 WeChat PIDs
    # for pid in wechat_pids:
    #     find_threads_by_pid(pid)

    # # 示例调用
    # wechat_pids = [50584, 46836]  # 替换为实际的 WeChat PIDs
    # handle_name = "_WeChat_App_Instance_Identity_Mutex_Name"
    # for pid in wechat_pids:
    #     find_handle_by_name(pid, handle_name)

    close_mutex('30336')
