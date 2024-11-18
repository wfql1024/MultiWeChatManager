import ctypes
import subprocess
import sys
from ctypes import wintypes
from ctypes.wintypes import DWORD, HANDLE, LPCWSTR, BOOL

import psutil

kernel32 = ctypes.windll.kernel32
OpenProcess = kernel32.OpenProcess
CloseHandle = kernel32.CloseHandle
K32EnumProcessModules = kernel32.K32EnumProcessModules
K32GetModuleFileNameExA = kernel32.K32GetModuleFileNameExA

# 定义常量和类型
PROCESS_ALL_ACCESS = 0x1F0FFF

# 设置函数参数和返回类型
K32EnumProcessModules.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(ctypes.wintypes.HMODULE),
                                  ctypes.wintypes.DWORD, ctypes.POINTER(ctypes.wintypes.DWORD)]
K32EnumProcessModules.restype = ctypes.wintypes.BOOL

K32GetModuleFileNameExA.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.HMODULE, ctypes.POINTER(ctypes.c_char),
                                    ctypes.wintypes.DWORD]
K32GetModuleFileNameExA.restype = ctypes.wintypes.DWORD

# 加载 Windows API 库
advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
user32 = ctypes.WinDLL('user32', use_last_error=True)

# 常量定义
CREATE_NO_WINDOW = 0x08000000  # 隐藏窗口
PROCESS_QUERY_INFORMATION = 0x0400
TOKEN_DUPLICATE = 0x0002
TOKEN_ALL_ACCESS = 0xF01FF
SecurityImpersonation = 2
TokenPrimary = 1
CREATE_NEW_CONSOLE = 0x00000010

# 函数声明
OpenProcess.restype = HANDLE
OpenProcess.argtypes = [DWORD, BOOL, DWORD]

OpenProcessToken = advapi32.OpenProcessToken
OpenProcessToken.restype = BOOL
OpenProcessToken.argtypes = [HANDLE, DWORD, ctypes.POINTER(HANDLE)]

DuplicateTokenEx = advapi32.DuplicateTokenEx
DuplicateTokenEx.restype = BOOL
DuplicateTokenEx.argtypes = [HANDLE, DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_int, ctypes.c_int,
                             ctypes.POINTER(HANDLE)]

CreateProcessWithTokenW = advapi32.CreateProcessWithTokenW
CreateProcessWithTokenW.restype = BOOL
CreateProcessWithTokenW.argtypes = [HANDLE, DWORD, LPCWSTR, LPCWSTR, DWORD, ctypes.c_void_p, LPCWSTR, ctypes.c_void_p,
                                    ctypes.c_void_p]

GetShellWindow = user32.GetShellWindow
GetShellWindow.restype = HANDLE

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.restype = DWORD
GetWindowThreadProcessId.argtypes = [HANDLE, ctypes.POINTER(DWORD)]


def is_process_admin(pid):
    try:
        process = psutil.Process(pid)
        return process.is_running() and ctypes.windll.shell32.IsUserAnAdmin()
    except psutil.AccessDenied:
        return False


def get_process_by_name(process_name):
    """通过进程名获取单个进程ID和句柄"""
    for proc in psutil.process_iter(['name', 'pid']):
        if proc.name().lower() == process_name.lower():
            pid = proc.pid
            handle = OpenProcess(PROCESS_ALL_ACCESS, False, pid)
            return pid, handle
    return None, None


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


def get_module_base_address(process_handle, module_name):
    """
    获取指定模块（DLL）在目标进程中的基址
    :param process_handle: 句柄
    :param module_name: 模块名（如dll）
    :return: 基址
    """
    h_modules = (ctypes.wintypes.HMODULE * 1024)()
    cb_needed = ctypes.wintypes.DWORD()
    module_name_bytes = module_name.encode('ascii')

    if K32EnumProcessModules(process_handle, h_modules, ctypes.sizeof(h_modules), ctypes.byref(cb_needed)):
        for i in range(cb_needed.value // ctypes.sizeof(ctypes.wintypes.HMODULE)):
            module_path = ctypes.create_string_buffer(260)
            if K32GetModuleFileNameExA(process_handle, h_modules[i], module_path, ctypes.sizeof(module_path)):
                if module_path.value.decode('ascii').lower().endswith(module_name_bytes.lower()):
                    return h_modules[i]
    return None


def get_base_address(process_name, pid, process_handle, module_name):
    """通过句柄和模块名获得基址"""
    if not process_handle:
        print(f"无法打开 {process_name} 的进程 {pid} 及其句柄 {process_handle}")
        return None

    try:
        base_address = get_module_base_address(process_handle, module_name)
        if not base_address:
            print(f"无法获取 {module_name} 的基址")
            return None

        return base_address
    finally:
        CloseHandle(process_handle)


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


def process_exists(pid):
    """判断进程id是否存在"""
    output = 'default'
    try:
        output = subprocess.check_output(['tasklist', '/FI', f'PID eq {pid}'])
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


def get_process_ids_by_name(process_name):
    """通过进程名获取所有的进程id"""
    matching_processes = []
    try:
        # 设置创建不显示窗口的子进程标志
        startupinfo = None
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # 直接执行 tasklist 命令并获取输出
        origin_output = subprocess.check_output(
            ['tasklist', '/FI', f'IMAGENAME eq {process_name}', '/FO', 'CSV', '/NH'],
            startupinfo=startupinfo
        )
        print(f"{origin_output}")

        try:
            output = origin_output.decode('utf-8').strip()
        except UnicodeDecodeError as e:
            print(f"解码错误：{e}")
            print(f"{origin_output.decode('GBK').strip()}")
            return []  # 或者根据需求返回其他值或执行其他逻辑
        # print(f"{debug_utils.get_call_stack_indent()}{output}")

        # 解析输出并获取进程 ID
        for line in output.split('\n'):
            process_info = [x.strip('"') for x in line.split(',')]
            if process_info[0].lower() == process_name.lower():
                matching_processes.append(int(process_info[1]))

    except subprocess.CalledProcessError:
        pass

    return matching_processes


def create_process_for_win7(executable, args=None, creation_flags=0):
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
        return process
    except Exception as e:
        print("Error starting process:", e)
        return None


def create_process_with_medium_il(executable, args=None, creation_flags=CREATE_NEW_CONSOLE):
    """
    以文件管理器的令牌打开可执行文件
    :param executable: 可执行文件
    :param args: 传入的其他参数
    :param creation_flags: 窗口标志参数
    :return: 无
    """
    # 获取 Explorer 的窗口句柄
    h_program = GetShellWindow()
    if not h_program:
        raise ctypes.WinError(ctypes.get_last_error())

    # 获取 Explorer 进程 ID
    explorer_pid = DWORD()
    GetWindowThreadProcessId(h_program, ctypes.byref(explorer_pid))

    # 打开 Explorer 进程
    h_process = OpenProcess(PROCESS_QUERY_INFORMATION, False, explorer_pid.value)
    if not h_process:
        raise ctypes.WinError(ctypes.get_last_error())

    # 打开 Explorer 的进程令牌
    h_token = HANDLE()
    if not OpenProcessToken(h_process, TOKEN_DUPLICATE, ctypes.byref(h_token)):
        kernel32.CloseHandle(h_process)
        raise ctypes.WinError(ctypes.get_last_error())

    # 复制令牌
    h_token2 = HANDLE()
    if not DuplicateTokenEx(h_token, TOKEN_ALL_ACCESS, None, SecurityImpersonation, TokenPrimary,
                            ctypes.byref(h_token2)):
        kernel32.CloseHandle(h_token)
        kernel32.CloseHandle(h_process)
        raise ctypes.WinError(ctypes.get_last_error())

    # 设置启动信息结构
    startup_info = ctypes.create_string_buffer(104)  # STARTUPINFO结构体的大小
    process_info = ctypes.create_string_buffer(24)  # PROCESS_INFORMATION结构体的大小

    # 创建带有 Explorer 令牌的进程
    if not CreateProcessWithTokenW(h_token2, 0, executable, args, creation_flags, None, None, startup_info,
                                   process_info):
        kernel32.CloseHandle(h_token2)
        kernel32.CloseHandle(h_token)
        kernel32.CloseHandle(h_process)
        raise ctypes.WinError(ctypes.get_last_error())

    # 清理句柄
    kernel32.CloseHandle(h_token2)
    kernel32.CloseHandle(h_token)
    kernel32.CloseHandle(h_process)

    print(f"Process started successfully.")

    # 获取 PROCESS_INFORMATION 结构体
    pi = ctypes.cast(process_info, ctypes.POINTER(ctypes.c_void_p))
    h_process = pi[0]  # 进程句柄
    h_thread = pi[1]  # 线程句柄

    class Process:
        def __init__(self, handle_process, handle_thread):
            self.h_process = handle_process
            self.h_thread = handle_thread

        def terminate(self):
            kernel32.TerminateProcess(self.h_process, 0)
            kernel32.CloseHandle(self.h_thread)
            kernel32.CloseHandle(self.h_process)

    return Process(h_process, h_thread)


if __name__ == '__main__':
    pass
    # print(get_file_from_pid(20040))
