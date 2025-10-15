import ctypes
import subprocess
import sys
from ctypes import wintypes
from ctypes.wintypes import DWORD, HANDLE, LPCWSTR, BOOL

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
