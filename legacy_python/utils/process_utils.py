import ctypes
import datetime
import fnmatch
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from ctypes import wintypes
from ctypes.wintypes import DWORD, HANDLE, LPCWSTR, BOOL
from typing import List, Optional, Tuple

import psutil

from legacy_python.utils.logger_utils import mylogger as logger, Printer, Logger


class Process:
    def __init__(self, handle_process, handle_thread):
        self.h_process = handle_process
        self.h_thread = handle_thread
        self.pid = self._get_pid()

    def _get_pid(self):
        """从句柄获取进程 PID"""
        GetProcessId = ctypes.windll.kernel32.GetProcessId
        GetProcessId.argtypes = [wintypes.HANDLE]
        GetProcessId.restype = wintypes.DWORD
        return GetProcessId(self.h_process)

    def terminate(self):
        kernel32.TerminateProcess(self.h_process, 0)
        kernel32.CloseHandle(self.h_thread)
        kernel32.CloseHandle(self.h_process)


# def create_process_without_admin(
#         executable, args=None, creation_flags=subprocess.CREATE_NO_WINDOW) -> Optional[Process]:
#     """在管理员身份的程序中，以非管理员身份创建进程，即打开的子程序不得继承父进程的权限"""
#     cur_sys_ver = platform.release()
#     if cur_sys_ver not in ["11", "10"]:
#
#         # return process_utils.create_process_with_logon(
#         #     "xxxxx@xx.com", "xxxx", executable, args, creation_flags)  # 使用微软账号登录，下策
#         # return process_utils.create_process_with_task_scheduler(executable, args)  # 会继承父进程的权限，废弃
#         # # 拿默认令牌通过资源管理器身份创建
#         # return process_utils.create_process_with_re_token_default(executable, args, creation_flags)
#         # # 拿Handle令牌通过资源管理器身份创建
#         return create_process_with_re_token_handle(executable, args, creation_flags)
#     else:
#         return create_process_for_win7(executable, args, creation_flags)

"""创建进程的各种方式"""

# 定义必要的常量和结构体
LOGON_WITH_PROFILE = 0x00000001
CREATE_NO_WINDOW = 0x08000000


class STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", wintypes.LPBYTE),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


# 加载Advapi32.dll
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
# 定义CreateProcessWithLogonW函数
CreateProcessWithLogonW = advapi32.CreateProcessWithLogonW

CreateProcessWithLogonW.argtypes = [
    wintypes.LPWSTR,  # lpUsername
    wintypes.LPWSTR,  # lpDomain
    wintypes.LPWSTR,  # lpPassword
    wintypes.DWORD,  # dwLogonFlags
    wintypes.LPWSTR,  # lpApplicationName
    wintypes.LPWSTR,  # lpCommandLine
    wintypes.DWORD,  # dwCreationFlags
    wintypes.LPVOID,  # lpEnvironment
    wintypes.LPWSTR,  # lpCurrentDirectory
    ctypes.POINTER(STARTUPINFO),  # lpStartupInfo
    ctypes.POINTER(PROCESS_INFORMATION),  # lpProcessInformation
]
CreateProcessWithLogonW.restype = wintypes.BOOL


def create_process_with_logon(username, password, executable, args=None, create_flags=subprocess.CREATE_NO_WINDOW):
    startup_info = STARTUPINFO()
    startup_info.cb = ctypes.sizeof(STARTUPINFO)
    process_info = PROCESS_INFORMATION()

    command_line = f'"{executable}"'
    if args:
        command_line += " " + args

    if not CreateProcessWithLogonW(
            username,  # 用户名
            None,  # 域名（本地用户为None）
            password,  # 密码
            LOGON_WITH_PROFILE,  # 登录标志
            None,  # 应用程序名（使用命令行）
            command_line,  # 命令行
            create_flags,  # 创建标志
            None,  # 环境变量
            None,  # 当前目录
            ctypes.byref(startup_info),  # 启动信息
            ctypes.byref(process_info),  # 进程信息
    ):
        raise ctypes.WinError(ctypes.get_last_error())

    h_process = process_info.hProcess
    h_thread = process_info.hThread
    return Process(h_process, h_thread)


# 定义必要的常量和结构体
PROCESS_QUERY_INFORMATION = 0x0400
TOKEN_DUPLICATE = 0x0002
TOKEN_ALL_ACCESS = 0xF01FF
SecurityImpersonation = 2
TokenPrimary = 1

# 加载必要的DLL
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

# 定义函数
GetShellWindow = ctypes.windll.user32.GetShellWindow
GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId
OpenProcess = kernel32.OpenProcess
OpenProcessToken = advapi32.OpenProcessToken
DuplicateTokenEx = advapi32.DuplicateTokenEx
CreateProcessWithTokenW = advapi32.CreateProcessWithTokenW
CloseHandle = kernel32.CloseHandle


def create_process_with_re_token_default(executable, args=None, creation_flags=subprocess.CREATE_NO_WINDOW):
    """
    以文件管理器的令牌打开可执行文件
    :param executable: 可执行文件
    :param args: 传入的其他参数
    :param creation_flags: 窗口标志参数
    :return: 子进程的PID
    """
    SubFunc.redirect_type_to_("default")

    copied_token = None
    re_token = None
    re_process = None

    try:
        # 获取 Explorer 的窗口句柄
        h_program = GetShellWindow()
        if not h_program:
            raise ctypes.WinError(ctypes.get_last_error())

        # 获取 Explorer 进程 ID
        explorer_pid = wintypes.DWORD()
        GetWindowThreadProcessId(h_program, ctypes.byref(explorer_pid))

        # 打开 Explorer 进程
        re_process = OpenProcess(PROCESS_QUERY_INFORMATION, False, explorer_pid.value)
        if not re_process:
            raise ctypes.WinError(ctypes.get_last_error())

        # 打开 Explorer 的进程令牌
        re_token = wintypes.HANDLE()
        if not OpenProcessToken(re_process, TOKEN_DUPLICATE, ctypes.byref(re_token)):
            raise ctypes.WinError(ctypes.get_last_error())

        # 复制令牌
        copied_token = wintypes.HANDLE()
        if not DuplicateTokenEx(re_token, TOKEN_ALL_ACCESS, None, SecurityImpersonation, TokenPrimary,
                                ctypes.byref(copied_token)):
            raise ctypes.WinError(ctypes.get_last_error())

        # 设置启动信息结构
        startup_info = STARTUPINFO()
        startup_info.cb = ctypes.sizeof(STARTUPINFO)
        process_info = PROCESS_INFORMATION()

        # 创建带有 Explorer 令牌的进程
        if not CreateProcessWithTokenW(copied_token, 0, executable, args, creation_flags, None, None,
                                       ctypes.byref(startup_info), ctypes.byref(process_info)):
            raise ctypes.WinError(ctypes.get_last_error())

        # 返回子进程的PID
        # 直接访问 PROCESS_INFORMATION 结构体的字段
        h_process = process_info.hProcess  # 进程句柄
        h_thread = process_info.hThread  # 线程句柄

        return Process(h_process, h_thread)

    finally:
        # 清理句柄
        CloseHandle(copied_token) if copied_token is not None else None
        CloseHandle(re_token) if re_token is not None else None
        CloseHandle(re_process) if re_process is not None else None


def create_process_with_re_token_handle(
        executable, args=None, creation_flags=subprocess.CREATE_NO_WINDOW) -> Optional[Process]:
    """
    以文件管理器的令牌打开可执行文件
    :param executable: 可执行文件
    :param args: 传入的其他参数
    :param creation_flags: 窗口标志参数
    :return: 无
    """
    SubFunc.redirect_type_to_("handle")

    copied_token = None
    re_token = None
    re_process = None

    try:
        # 获取 Explorer 的窗口句柄
        h_program = GetShellWindow()
        if not h_program:
            raise ctypes.WinError(ctypes.get_last_error())

        # 获取 Explorer 进程 ID
        explorer_pid = DWORD()
        GetWindowThreadProcessId(h_program, ctypes.byref(explorer_pid))

        # 打开 Explorer 进程
        re_process = OpenProcess(PROCESS_QUERY_INFORMATION, False, explorer_pid.value)
        if not re_process:
            raise ctypes.WinError(ctypes.get_last_error())

        # 打开 Explorer 的进程令牌
        re_token = HANDLE()
        if not OpenProcessToken(re_process, TOKEN_DUPLICATE, ctypes.byref(re_token)):
            raise ctypes.WinError(ctypes.get_last_error())

        # 复制令牌
        copied_token = HANDLE()
        if not DuplicateTokenEx(re_token, TOKEN_ALL_ACCESS, None, SecurityImpersonation, TokenPrimary,
                                ctypes.byref(copied_token)):
            raise ctypes.WinError(ctypes.get_last_error())

        # 设置启动信息结构
        startup_info = ctypes.create_string_buffer(104)  # STARTUPINFO结构体的大小
        process_info = ctypes.create_string_buffer(24)  # PROCESS_INFORMATION结构体的大小

        # 创建带有 Explorer 令牌的进程
        if not CreateProcessWithTokenW(copied_token, 0, executable, args, creation_flags, None, None, startup_info,
                                       process_info):
            raise ctypes.WinError(ctypes.get_last_error())

        print(f"Process started successfully.")

        # 获取 PROCESS_INFORMATION 结构体
        pi = ctypes.cast(process_info, ctypes.POINTER(ctypes.c_void_p))
        h_process = pi[0]  # 进程句柄
        h_thread = pi[1]  # 线程句柄

        return Process(h_process, h_thread)
    except Exception as e:
        logger.error(e)
    finally:
        kernel32.CloseHandle(copied_token) if copied_token is not None else None
        kernel32.CloseHandle(re_token) if re_token is not None else None
        kernel32.CloseHandle(re_process) if re_process is not None else None

    return None


def create_process_with_task_scheduler(executable, args):
    """
    使用任务计划程序启动子进程
    :param executable: 可执行文件
    :param args: 传入的其他参数
    :return: 无
    """
    # 构建任务名称和XML文件路径
    task_name = f"TempTask_{int(time.time())}"
    executable = executable.replace("/", "\\")
    # 获取当前时间并格式化为 HH:mm
    start_time = (datetime.datetime.now() + datetime.timedelta(minutes=2)).strftime("%H:%M")
    task_command = f'"{executable}"' if args is None else f'"{executable}" {args}'

    # # 创建无窗口启动信息
    # startup_info = subprocess.STARTUPINFO()
    # startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    # startup_info.wShowWindow = win32con.SW_HIDE  # 隐藏窗口

    # 创建任务命令，/SC ONCE 与 /ST 配合，用当前时间触发任务
    schtasks_command = f'schtasks /Create /TN "{task_name}" /SC ONCE /ST {start_time} /TR {task_command} /RL HIGHEST /F'
    # 打印出完整的命令，供手动在cmd中调试
    print(f"创建任务：{schtasks_command}")
    subprocess.Popen(schtasks_command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # print(f"任务 '{task_name}' 创建成功并立即执行。")

    # schtasks 立即运行任务
    schtasks_run_cmd = f'schtasks /Run /TN "{task_name}"'
    print(f"执行任务：{schtasks_run_cmd}")
    process = subprocess.Popen(schtasks_run_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"任务执行进程：{process}")

    # 删除任务（无窗口）
    schtasks_del_cmd = f'schtasks /Delete /TN "{task_name}" /F'
    print(f"删除任务：{schtasks_del_cmd}")
    subprocess.Popen(schtasks_del_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    pids = []
    pid = None
    end_time = time.time() + 5
    while len(pids) == 0:
        name_pids_dict = psutil_get_pids_by_wildcards_and_grouping_to_dict(os.path.basename(executable))
        pids: list = name_pids_dict.get(os.path.basename(executable), [])
        if time.time() > end_time:
            break
    if len(pids) > 0:
        pid = pids[0]
        print(pid)

    end_time = time.time() + 5
    h_process = None
    while h_process is None or h_process == 0:
        h_process = OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if time.time() > end_time:
            break
    print(f"成功获取进程句柄:{h_process}")
    return Process(h_process, None)


def create_process_for_win7(executable, args=None, creation_flags=0):
    """win7以下使用Popen方法启动进程并不会继承父进程的权限，因此直接使用"""
    command = [executable]  # 添加可执行文件路径到命令列表中
    if args:
        command.extend(args)  # 添加额外的参数
    # 启动进程，不使用管理员权限
    try:
        process = subprocess.Popen(
            command,
            creationflags=creation_flags,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print("Process started successfully:", executable)
        h_process = get_handle_by_pid(process.pid)
        return Process(h_process, None)
    except Exception as e:
        print("Error starting process:", e)
        return None


"""PID操作"""

# 定义常量和类型
PROCESS_ALL_ACCESS = 0x1F0FFF


def remove_child_pids(pids):
    """从 pids 列表中删除所有子进程 PID"""
    pid_set = set(pids)

    for pid in pids:
        try:
            process = psutil.Process(pid)
            for child in process.children(recursive=True):
                pid_set.discard(child.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass  # 忽略无权限或进程不存在的情况

    # 保留原顺序
    return [pid for pid in pids if pid in pid_set]


def remove_pids_not_in_path(pids: List[int], path_keyword: str) -> List[int]:
    """从 pids 列表中排除那些不在指定路径关键字中的进程"""
    # 获取所有进程信息（包含可执行路径）
    path_keyword = path_keyword.replace("/", "\\").lower()
    filtered = []
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            exe_path = proc.exe() or ""
            # Printer().debug(exe_path)
            if path_keyword in exe_path.lower():
                filtered.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue  # 无权限或已退出的进程跳过

    return filtered


def get_exe_name_by_pid(pid, precise=False):
    try:
        process = psutil.Process(pid)
        exe_path = process.exe()
        if precise is not True:
            exe_path = os.path.basename(exe_path)
        return exe_path
    except psutil.NoSuchProcess:
        print(f"No process found with PID: {pid}")
        return None


"""PID信息"""


def get_handle_by_pid(pid: int):
    handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not handle:
        raise ctypes.WinError()
    return handle


def is_pid_elevated(pid):
    try:
        process = psutil.Process(pid)
        return process.is_running() and ctypes.windll.shell32.IsUserAnAdmin()
    except psutil.AccessDenied:
        return False


def get_file_from_pid(pid):
    """通过pid获取进程打开文件的列表"""
    try:
        process = psutil.Process(pid)
        memory_maps = process.memory_maps()
        paths = [f.path for f in memory_maps]
    except psutil.NoSuchProcess:
        print(f"No process found with PID: {pid}")
        paths = []
    except Exception as e:
        print(f"An error occurred: {e}")
        paths = []

    return paths


def iter_open_files(pid):
    """通过pid获得使用文件列表的迭代器"""
    try:
        for f in psutil.Process(pid).memory_maps():
            yield f.path
    except psutil.NoSuchProcess:
        print(f"No process found with PID: {pid}")
    except Exception as e:
        print(f"An error occurred: {e}")


def taskkill_kill_process_tree(pid):
    cmd_args = ['taskkill', '/T', '/F', '/PID', f'{pid}']
    cmd = ' '.join(cmd_args)
    Printer().cmd_in(cmd)
    result = subprocess.run(
        cmd_args,
        startupinfo=None,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print(f"结束了 {pid} 的进程树")
        return True
    else:
        Printer().cmd_out(f"{result.stderr.strip()}")
        print(f"结束 {pid} 进程树失败!")
        return False


def psutil_kill_process_tree_if_matched_in_wildcards(pid, wildcards: Optional[list] = None) -> bool:
    """
    强制结束指定 PID 且符合匹配模式的进程列表及其所有子进程。返回 True 表示成功杀掉（或已不存在），False 表示失败。
    wildcards不传入为无条件结束;若传入列表,则只结束匹配的进程(列表为空会没有匹配,不会结束进程)
    """
    matched = False
    try:
        process = psutil.Process(pid)
        # 获取所有子进程（递归）
        children = process.children(recursive=True)
        if wildcards is None:
            matched = True
        else:
            if isinstance(wildcards, list):
                matched = any(fnmatch.fnmatch(process.name(), wildcard) for wildcard in wildcards)

        if matched:
            for child in children:
                try:
                    child.kill()
                    print(f"已结束子进程 {child.pid}")
                except Exception as e:
                    print(f"无法结束子进程 {child.pid}：{e}")
            try:
                process.kill()
                print(f"已结束主进程 {pid}")
                return True
            except Exception as e:
                print(f"无法结束主进程 {pid}：{e}")
                return False
        else:
            print(f"进程 {pid} 不匹配指定的通配符列表")
        return False
    except psutil.NoSuchProcess:
        print(f"进程 {pid} 已经不存在。")
        return True
    except psutil.AccessDenied:
        print(f"对进程 {pid} 无权限")
        return False
    except Exception as e:
        Logger().warning(f"发生错误：{e}")
        return False


def check_pid_alive_and_get_process_psutil(pid) -> Tuple[Optional[bool], Optional[Process]]:
    """检查进程是否存活"""
    try:
        process = psutil.Process(pid)
        alive = process.is_running()
        if alive:
            return True, process
        else:
            return False, None
    except psutil.NoSuchProcess:
        return False, None
    except psutil.AccessDenied:
        return None, None


def is_pid_alive_tasklist(pid):
    """判断进程id是否存在"""
    output = 'default'
    try:
        args = ['tasklist', '/FI', f'PID eq {pid}']
        print(f"执行命令：{args}")
        output = subprocess.check_output(args)
        # 尝试直接使用 utf-8 解码
        decoded_output = output.decode('utf-8')
        return str(pid) in decoded_output
    except UnicodeDecodeError as e:
        print(f"解码错误：{e}")
        # 如果 utf-8 解码失败，尝试使用 gbk 解码
        try:
            decoded_output = output.decode('GBK')
            print(decoded_output.strip())
            return str(pid) in decoded_output
        except UnicodeDecodeError:
            print("解码失败，无法解析输出。")
            return False
    except subprocess.CalledProcessError:
        return False


"""通过进程名"""


def get_pid_and_handle_by_name(process_name):
    """通过进程名获取第一个符合的进程ID及其句柄"""
    for proc in psutil.process_iter(['name', 'pid']):
        if proc.name().lower() == process_name.lower():
            pid = proc.pid
            handle = OpenProcess(PROCESS_ALL_ACCESS, False, pid)
            return pid, handle
    return None, None


def try_terminate_executable(executable_name):
    """检查指定的可执行文件是否正在运行，如果是，则终止它，并返回剩余的进程列表"""
    # 尝试终止微信进程
    wechat_processes = []
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.name().lower() == executable_name.lower():
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
        return [p for p in wechat_processes if p.is_running()]
    return None


def psutil_get_pids_by_wildcards_and_grouping_to_dict(wildcards: list) -> dict:
    """
    使用 psutil 模糊匹配进程名，支持 Unix 和 Windows
    wildcards 支持通配符，比如 "WeChat?.exe"
    返回 dict：key 为进程名，value 为匹配到的 pid 列表
    """
    if wildcards is None:
        return {}

    result = {}
    for proc in psutil.process_iter(['name']):
        try:
            name = proc.info['name']
            if name:
                for wildcard in wildcards:
                    if fnmatch.fnmatch(name, wildcard):
                        result.setdefault(name, []).append(proc.pid)
                        break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return result


def get_process_ids_by_precise_name_impl_by_tasklist(process_name) -> list:
    """通过进程名获取所有的进程id"""
    matching_processes = []
    try:
        # 设置创建不显示窗口的子进程标志
        startupinfo = None
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # 直接执行 tasklist 命令并获取输出
        cmd = ['tasklist', '/FI', f'IMAGENAME eq {process_name}', '/FO', 'CSV', '/NH']
        Printer().cmd_in(" ".join(cmd))  # 打印命令
        origin_output = subprocess.check_output(
            cmd,
            startupinfo=startupinfo
        )
        Printer().cmd_out(origin_output)

        output = "解码错误"
        try:
            output = origin_output.decode('utf-8').strip()
        except UnicodeDecodeError as e:
            # print(f"解码错误：{e}")
            try:
                # print(f"{origin_output.decode('GBK').strip()}")
                output = origin_output.decode('GBK').strip()
            except UnicodeDecodeError as ue:
                print(ue)
        Printer().cmd_out(f"{output}")

        # 解析输出并获取进程 ID
        for line in output.split('\n'):
            process_info = [x.strip('"') for x in line.split(',')]
            if len(process_info) >= 2 and process_info[1].isdigit():
                matching_processes.append(int(process_info[1]))

    except subprocess.CalledProcessError:
        pass
    Printer().debug(matching_processes)

    return matching_processes


class SubFunc:
    @staticmethod
    def redirect_type_to_(mode):
        if mode == "handle":
            # print("使用HANDLE变量")
            # 函数声明
            # GetShellWindow: 获取Shell窗口的句柄
            GetShellWindow.restype = HANDLE  # 返回值是句柄（HANDLE）

            # GetWindowThreadProcessId: 获取与窗口关联的线程ID和进程ID
            GetWindowThreadProcessId.restype = DWORD  # 返回值是线程ID（DWORD）
            GetWindowThreadProcessId.argtypes = [HANDLE, ctypes.POINTER(DWORD)]  # 参数类型：窗口句柄、进程ID指针

            # OpenProcess: 打开一个已存在的进程对象，并返回进程句柄
            OpenProcess.restype = HANDLE  # 返回值是句柄（HANDLE）
            OpenProcess.argtypes = [DWORD, BOOL, DWORD]  # 参数类型：访问权限、继承标志、进程ID

            # OpenProcessToken: 打开与进程关联的访问令牌
            OpenProcessToken.restype = BOOL  # 返回值是布尔值（成功或失败）
            OpenProcessToken.argtypes = [HANDLE, DWORD, ctypes.POINTER(HANDLE)]  # 参数类型：进程句柄、访问权限、令牌句柄指针

            # DuplicateTokenEx: 复制访问令牌
            DuplicateTokenEx.restype = BOOL  # 返回值是布尔值（成功或失败）
            DuplicateTokenEx.argtypes = [HANDLE, DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_int, ctypes.c_int,
                                         ctypes.POINTER(HANDLE)]  # 参数类型：源令牌、访问权限、安全描述符、模拟级别、令牌类型、目标令牌指针

            # CreateProcessWithTokenW: 使用指定令牌创建新进程
            CreateProcessWithTokenW.restype = BOOL  # 返回值是布尔值（成功或失败）
            CreateProcessWithTokenW.argtypes = [HANDLE, DWORD, LPCWSTR, LPCWSTR, DWORD, ctypes.c_void_p, LPCWSTR,
                                                ctypes.c_void_p,
                                                ctypes.c_void_p]  # 参数类型：令牌、登录标志、应用程序名、命令行、创建标志、环境变量、当前目录、启动信息、进程信息

        elif mode == "default":
            # print("使用默认变量")
            # 设置函数的重定义（默认值）
            GetShellWindow.restype = ctypes.c_void_p  # 默认返回值类型（指针）

            GetWindowThreadProcessId.restype = ctypes.c_ulong  # 默认返回值类型（DWORD）
            GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]  # 默认参数类型

            OpenProcess.restype = ctypes.c_void_p  # 默认返回值类型（指针）
            OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]  # 默认参数类型

            OpenProcessToken.restype = ctypes.c_int  # 默认返回值类型（int）
            OpenProcessToken.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p)]  # 默认参数类型

            DuplicateTokenEx.restype = ctypes.c_int  # 默认返回值类型（int）
            DuplicateTokenEx.argtypes = [
                ctypes.c_void_p,  # 源令牌
                ctypes.c_ulong,  # 访问权限
                ctypes.POINTER(ctypes.c_void_p),  # 安全描述符
                ctypes.c_int,  # 模拟级别
                ctypes.c_int,  # 令牌类型
                ctypes.POINTER(ctypes.c_void_p),  # 目标令牌指针
            ]

            CreateProcessWithTokenW.restype = ctypes.c_int  # 默认返回值类型（int）
            CreateProcessWithTokenW.argtypes = [
                ctypes.c_void_p,  # 令牌
                ctypes.c_ulong,  # 登录标志
                ctypes.c_void_p,  # 应用程序名（LPCWSTR）
                ctypes.c_void_p,  # 命令行（LPCWSTR）
                ctypes.c_ulong,  # 创建标志
                ctypes.c_void_p,  # 环境变量
                ctypes.c_void_p,  # 当前目录
                ctypes.c_void_p,  # 启动信息
                ctypes.c_void_p,  # 进程信息
            ]

    @staticmethod
    def create_task_xml(task_name, executable, args=None):
        """
        创建一个不带定时触发器的计划任务 XML 文件
        :param executable: 可执行文件路径
        :param args: 传入的参数
        :param task_name: 任务名称
        :return: 生成的 XML 文件路径
        """
        # 创建根节点
        root = ET.Element('Task', version="1.2", xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task")

        # 创建任务的 RegistrationInfo
        reg_info = ET.SubElement(root, 'RegistrationInfo')
        date = ET.SubElement(reg_info, 'Date')
        date.text = "2025-02-06T14:58:32"  # 设置任务创建日期，可以使用当前日期和时间
        author = ET.SubElement(reg_info, 'Author')
        author.text = os.getlogin()  # 获取当前登录用户
        uri = ET.SubElement(reg_info, 'URI')
        uri.text = f"\\{task_name}"

        # 创建 Principals 节点
        principals = ET.SubElement(root, 'Principals')
        principal = ET.SubElement(principals, 'Principal', id="Author")
        user_id = ET.SubElement(principal, 'UserId')
        user_id.text = "S-1-5-18"  # Local System
        run_level = ET.SubElement(principal, 'RunLevel')
        run_level.text = "HighestAvailable"  # 运行权限

        # 创建 Settings 节点
        settings = ET.SubElement(root, 'Settings')
        enabled = ET.SubElement(settings, 'Enabled')
        enabled.text = 'true'  # 启用任务
        disallow_battery_start = ET.SubElement(settings, 'DisallowStartIfOnBatteries')
        disallow_battery_start.text = 'false'
        stop_on_battery_end = ET.SubElement(settings, 'StopIfGoingOnBatteries')
        stop_on_battery_end.text = 'false'
        allow_hard_terminate = ET.SubElement(settings, 'AllowHardTerminate')
        allow_hard_terminate.text = 'true'

        # 创建 Actions 节点
        actions = ET.SubElement(root, 'Actions')
        action = ET.SubElement(actions, 'Exec')
        command = ET.SubElement(action, 'Command')
        command.text = executable  # 设置要执行的命令

        # 如果有参数，添加 Arguments 节点
        if args:
            arguments = ET.SubElement(action, 'Arguments')
            arguments.text = args

        # 创建 XML 树
        tree = ET.ElementTree(root)

        # 保存 XML 文件
        task_xml_path = os.path.join(os.getenv("TEMP"), f"{task_name}.xml")
        tree.write(task_xml_path, encoding="UTF-8", xml_declaration=True)

        return task_xml_path
