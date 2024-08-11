import ctypes
import ctypes.wintypes
import win32process
import win32con
import win32api
import win32security
import winreg
import psutil

# 添加这行来定义 NTSTATUS
NTSTATUS = ctypes.wintypes.LONG

# 定义必要的常量和结构体
SYSTEM_HANDLE_INFORMATION_SIZE = 64
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
DUPLICATE_CLOSE_SOURCE = 0x1
DUPLICATE_SAME_ACCESS = 0x2
CNST_SYSTEM_HANDLE_INFORMATION = 0x10
OBJECT_TYPE_MUTANT = 17

class SYSTEM_HANDLE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("ProcessId", ctypes.wintypes.USHORT),
        ("CreatorBackTraceIndex", ctypes.wintypes.USHORT),
        ("ObjectTypeIndex", ctypes.c_ubyte),
        ("HandleAttributes", ctypes.c_ubyte),
        ("HandleValue", ctypes.wintypes.USHORT),
        ("Object", ctypes.c_void_p),
        ("GrantedAccess", ctypes.wintypes.ULONG),
    ]

class UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", ctypes.wintypes.USHORT),
        ("MaximumLength", ctypes.wintypes.USHORT),
        ("Buffer", ctypes.c_wchar_p),
    ]

class OBJECT_NAME_INFORMATION(ctypes.Structure):
    _fields_ = [("Name", UNICODE_STRING)]

# 加载必要的DLL
ntdll = ctypes.windll.ntdll
kernel32 = ctypes.windll.kernel32

# 定义必要的函数
NtQuerySystemInformation = ntdll.NtQuerySystemInformation
NtQuerySystemInformation.restype = NTSTATUS
NtQuerySystemInformation.argtypes = [
    ctypes.wintypes.ULONG,
    ctypes.c_void_p,
    ctypes.wintypes.ULONG,
    ctypes.POINTER(ctypes.wintypes.ULONG),
]

NtQueryObject = ntdll.NtQueryObject
NtQueryObject.restype = NTSTATUS
NtQueryObject.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.ULONG,
    ctypes.c_void_p,
    ctypes.wintypes.ULONG,
    ctypes.POINTER(ctypes.wintypes.ULONG),
]

def get_handles(process_id):
    handles = []
    handle_info_size = 1024 * 1024  # 开始使用1MB的缓冲区
    while True:
        handle_info = ctypes.create_string_buffer(handle_info_size)
        return_length = ctypes.c_ulong(0)
        status = NtQuerySystemInformation(
            CNST_SYSTEM_HANDLE_INFORMATION,
            handle_info,
            handle_info_size,
            ctypes.byref(return_length)
        )
        if status == 0:
            break
        elif status == STATUS_INFO_LENGTH_MISMATCH:
            handle_info_size *= 2  # 如果缓冲区太小，就将其大小加倍
        else:
            raise ctypes.WinError(status)

    handle_count = ctypes.cast(handle_info, ctypes.POINTER(ctypes.c_ulong)).contents.value
    handle_array = (SYSTEM_HANDLE_INFORMATION * handle_count).from_buffer(handle_info, ctypes.sizeof(ctypes.c_ulong))

    for handle in handle_array:
        if handle.ProcessId == process_id:
            handles.append(handle)

    return handles

def find_and_close_wechat_mutex_handle(handle, process_handle):
    duplicate_handle = ctypes.wintypes.HANDLE()
    if not kernel32.DuplicateHandle(
        process_handle,
        handle.HandleValue,
        win32api.GetCurrentProcess(),
        ctypes.byref(duplicate_handle),
        0,
        False,
        DUPLICATE_SAME_ACCESS
    ):
        return False

    object_name_info = ctypes.create_string_buffer(1024)
    return_length = ctypes.c_ulong(0)
    status = NtQueryObject(
        duplicate_handle,
        1,  # ObjectNameInformation
        object_name_info,
        1024,
        ctypes.byref(return_length)
    )

    if status == 0:
        name_info = ctypes.cast(object_name_info, ctypes.POINTER(OBJECT_NAME_INFORMATION)).contents
        if name_info.Name.Buffer:
            object_name = ctypes.wstring_at(name_info.Name.Buffer, name_info.Name.Length // 2)
            if "_Instance_Identity_Mutex_Name" in object_name:
                kernel32.DuplicateHandle(
                    process_handle,
                    handle.HandleValue,
                    win32api.GetCurrentProcess(),
                    ctypes.byref(duplicate_handle),
                    0,
                    False,
                    DUPLICATE_CLOSE_SOURCE
                )
                kernel32.CloseHandle(duplicate_handle)
                return True

    kernel32.CloseHandle(duplicate_handle)
    return False

def close_mutex_handle(process):
    try:
        process_handle = win32api.OpenProcess(
            win32con.PROCESS_DUP_HANDLE | win32con.PROCESS_QUERY_INFORMATION,
            False,
            process.pid
        )
    except win32api.error as e:
        if e.winerror == 5:  # 5 是 "拒绝访问" 错误代码
            # 提升权限
            print(f"尝试提升权限以访问进程 {process.pid}...")
            priv_flags = win32security.TOKEN_ADJUST_PRIVILEGES | win32security.TOKEN_QUERY
            token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), priv_flags)
            luid = win32security.LookupPrivilegeValue(None, win32security.SE_DEBUG_NAME)
            win32security.AdjustTokenPrivileges(token, False, [(luid, win32security.SE_PRIVILEGE_ENABLED)])
            process_handle = win32api.OpenProcess(
                win32con.PROCESS_DUP_HANDLE | win32con.PROCESS_QUERY_INFORMATION,
                False,
                process.pid
            )
            if not process_handle:
                print(f"无法打开进程 {process.pid}，权限不足。继续执行...")
                return False
        else:
            raise  # 如果是其他错误，则重新抛出

    if not process_handle:
        return False

    handles = get_handles(process.pid)
    exist_mutex_handle = False

    for handle in handles:
        if handle.ObjectTypeIndex == OBJECT_TYPE_MUTANT:
            if find_and_close_wechat_mutex_handle(handle, process_handle):
                exist_mutex_handle = True

    win32api.CloseHandle(process_handle)
    return exist_mutex_handle

def get_wechat_path():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Tencent\WeChat")
        path = winreg.QueryValueEx(key, "InstallPath")[0]
        winreg.CloseKey(key)
        return path
    except WindowsError:
        return None

def run_wechat():
    for proc in psutil.process_iter(['name', 'pid', 'username']):
        if proc.info['name'] == 'WeChat.exe':
            try:
                print(f"尝试关闭 WeChat 进程 {proc.info['pid']} 的互斥体")
                result = close_mutex_handle(proc)
                print(f"关闭互斥体结果: {'成功' if result else '失败'}")
            except Exception as e:
                print(f"关闭互斥体时出错: {e}")

    path = get_wechat_path()
    if path:
        wechat_exe = f"{path}\\WeChat.exe"
        try:
            win32api.WinExec(wechat_exe, 1)
            print("WeChat 启动成功")
        except Exception as e:
            print(f"启动WeChat时出错: {e}")
    else:
        print("未找到WeChat安装路径。")

if __name__ == "__main__":
    run_wechat()
