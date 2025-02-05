import sys
import time
from ctypes import wintypes
from ctypes.wintypes import DWORD, HANDLE, LPCWSTR, BOOL
import psutil
import ctypes
import os
import subprocess

"""create_process_with_logon使用"""

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


def create_process_with_logon(username, password, executable, args=None):
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
            CREATE_NO_WINDOW,  # 创建标志
            None,  # 环境变量
            None,  # 当前目录
            ctypes.byref(startup_info),  # 启动信息
            ctypes.byref(process_info),  # 进程信息
    ):
        raise ctypes.WinError(ctypes.get_last_error())

    return process_info.dwProcessId


# 定义必要的常量和结构体
PROCESS_QUERY_INFORMATION = 0x0400
TOKEN_DUPLICATE = 0x0002
TOKEN_ALL_ACCESS = 0xF01FF
SecurityImpersonation = 2
TokenPrimary = 1


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


def create_process_with_medium_il_better(executable, args=None, creation_flags=subprocess.CREATE_NO_WINDOW):
    """
    以文件管理器的令牌打开可执行文件
    :param executable: 可执行文件
    :param args: 传入的其他参数
    :param creation_flags: 窗口标志参数
    :return: 子进程的PID
    """
    h_token2 = None
    h_token = None
    h_process = None

    try:
        # 获取 Explorer 的窗口句柄
        h_program = GetShellWindow()
        if not h_program:
            raise ctypes.WinError(ctypes.get_last_error())

        # 获取 Explorer 进程 ID
        explorer_pid = wintypes.DWORD()
        GetWindowThreadProcessId(h_program, ctypes.byref(explorer_pid))

        # 打开 Explorer 进程
        h_process = OpenProcess(PROCESS_QUERY_INFORMATION, False, explorer_pid.value)
        if not h_process:
            raise ctypes.WinError(ctypes.get_last_error())

        # 打开 Explorer 的进程令牌
        h_token = wintypes.HANDLE()
        if not OpenProcessToken(h_process, TOKEN_DUPLICATE, ctypes.byref(h_token)):
            raise ctypes.WinError(ctypes.get_last_error())

        # 复制令牌
        h_token2 = wintypes.HANDLE()
        if not DuplicateTokenEx(h_token, TOKEN_ALL_ACCESS, None, SecurityImpersonation, TokenPrimary,
                                ctypes.byref(h_token2)):
            raise ctypes.WinError(ctypes.get_last_error())

        # 设置启动信息结构
        startup_info = STARTUPINFO()
        startup_info.cb = ctypes.sizeof(STARTUPINFO)
        process_info = PROCESS_INFORMATION()

        # 构建命令行
        command_line = f'"{executable}"'
        if args:
            command_line += " " + args

        # 创建带有 Explorer 令牌的进程
        if not CreateProcessWithTokenW(h_token2, 0, None, command_line, creation_flags, None, None,
                                       ctypes.byref(startup_info), ctypes.byref(process_info)):
            raise ctypes.WinError(ctypes.get_last_error())

        # 返回子进程的PID
        return process_info.dwProcessId

    finally:
        # 清理句柄
        if "h_token2" in locals():
            CloseHandle(h_token2) if h_token2 is not None else None
        if "h_token" in locals():
            CloseHandle(h_token) if h_token is not None else None
        if "h_process" in locals():
            CloseHandle(h_process) if h_process is not None else None


def create_process_with_medium_il(executable, args=None, creation_flags=subprocess.CREATE_NO_WINDOW):
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


def create_process_with_task_scheduler(executable, args=None):
    """
    使用任务计划程序启动子进程
    :param executable: 可执行文件
    :param args: 传入的其他参数
    :return: 无
    """
    # 构建任务名称和XML文件路径
    task_name = "TempTask"
    xml_path = os.path.join(os.getenv("TEMP"), "task.xml")

    # 构建命令行
    command_line = f'"{executable}"'
    if args:
        command_line += " " + args

    # 创建任务XML
    xml_content = f"""
    <Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
      <Principals>
        <Principal id="Author">
          <UserId>S-1-5-18</UserId>
          <RunLevel>LeastPrivilege</RunLevel>
        </Principal>
      </Principals>
      <Settings>
        <Enabled>true</Enabled>
        <Hidden>false</Hidden>
        <RunOnlyIfLoggedOn>false</RunOnlyIfLoggedOn>
        <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
        <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
        <AllowHardTerminate>true</AllowHardTerminate>
        <StartWhenAvailable>false</StartWhenAvailable>
        <AllowStartOnDemand>true</AllowStartOnDemand>
        <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
      </Settings>
      <Actions Context="Author">
        <Exec>
          <Command>{executable}</Command>
          <Arguments>{args if args else ""}</Arguments>
        </Exec>
      </Actions>
    </Task>
    """
    with open(xml_path, "w") as f:
        f.write(xml_content)

    # 创建任务
    subprocess.run(["schtasks", "/Create", "/TN", task_name, "/XML", xml_path], check=True)

    # 运行任务
    subprocess.run(["schtasks", "/Run", "/TN", task_name], check=True)

    # 删除任务
    subprocess.run(["schtasks", "/Delete", "/TN", task_name, "/F"], check=True)

    # 删除临时XML文件
    os.remove(xml_path)


# 定义常量和类型
PROCESS_ALL_ACCESS = 0x1F0FFF


def remove_child_pids(pids):
    """从 pids 列表中删除所有子进程 PID，并跳过删除后的 PID"""
    # 获取所有进程信息
    all_processes = {p.pid: p for p in psutil.process_iter(['pid', 'name'])}

    i = 0
    while i < len(pids):
        pid = pids[i]
        if pid in all_processes:
            process = all_processes[pid]
            children = process.children()  # 获取当前进程的所有子进程

            # 遍历子进程，删除 pids 中存在的 PID
            for child in children:
                if child.pid in pids:
                    pids.remove(child.pid)  # 删除子进程 PID
        i += 1

    return pids


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


def is_process_admin(pid):
    try:
        process = psutil.Process(pid)
        return process.is_running() and ctypes.windll.shell32.IsUserAnAdmin()
    except psutil.AccessDenied:
        return False


def get_pids_and_handles_by_name(process_name):
    """通过进程名获取单个进程ID和句柄"""
    for proc in psutil.process_iter(['name', 'pid']):
        if proc.name().lower() == process_name.lower():
            pid = proc.pid
            handle = OpenProcess(PROCESS_ALL_ACCESS, False, pid)
            return pid, handle
    return None, None


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


def get_process_ids_by_name(process_name) -> list:
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
        # print(f"{origin_output}")

        try:
            output = origin_output.decode('utf-8').strip()
        except UnicodeDecodeError as e:
            print(f"解码错误：{e}")
            print(f"{origin_output.decode('GBK').strip()}")
            return []  # 或者根据需求返回其他值或执行其他逻辑
        print(f"{output}")

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


# 加载 Windows API 库
user32 = ctypes.WinDLL('user32', use_last_error=True)

# 函数声明
OpenProcess.restype = HANDLE
OpenProcess.argtypes = [DWORD, BOOL, DWORD]

OpenProcessToken.restype = BOOL
OpenProcessToken.argtypes = [HANDLE, DWORD, ctypes.POINTER(HANDLE)]

DuplicateTokenEx.restype = BOOL
DuplicateTokenEx.argtypes = [HANDLE, DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_int, ctypes.c_int,
                             ctypes.POINTER(HANDLE)]

CreateProcessWithTokenW.restype = BOOL
CreateProcessWithTokenW.argtypes = [HANDLE, DWORD, LPCWSTR, LPCWSTR, DWORD, ctypes.c_void_p, LPCWSTR, ctypes.c_void_p,
                                    ctypes.c_void_p]

GetShellWindow.restype = HANDLE

GetWindowThreadProcessId.restype = DWORD
GetWindowThreadProcessId.argtypes = [HANDLE, ctypes.POINTER(DWORD)]

if __name__ == '__main__':
    pass
    # print(get_file_from_pid(20040))
