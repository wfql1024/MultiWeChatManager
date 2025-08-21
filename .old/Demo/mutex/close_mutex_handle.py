import ctypes
import ctypes.wintypes
import winreg

import psutil
import win32api
import win32con
import win32security

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
    _pack_ = 1  # 强制1字节对齐
    _fields_ = [
        ("ProcessId", ctypes.wintypes.ULONG),
        ("CreatorBackTraceIndex", ctypes.wintypes.ULONG),
        ("ObjectTypeIndex", ctypes.c_ubyte),
        ("HandleAttributes", ctypes.c_ubyte),
        ("HandleValue", ctypes.wintypes.ULONG),
        ("Object", ctypes.c_void_p),
        ("GrantedAccess", ctypes.wintypes.ULONG),
    ]


# 然后重新尝试之前的代码。


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
    print("进入了 get_handles 方法")
    handles = []
    handle_info_size = 4096 * 4096  # 开始使用1MB的缓冲区
    print(f"初始化 handle_info_size: {handle_info_size}")

    while True:
        handle_info = ctypes.create_string_buffer(handle_info_size)
        return_length = ctypes.c_ulong(0)
        print(f"调用 NtQuerySystemInformation 之前的 handle_info_size: {handle_info_size}")
        status = NtQuerySystemInformation(
            CNST_SYSTEM_HANDLE_INFORMATION,
            handle_info,
            handle_info_size,
            ctypes.byref(return_length)
        )
        print(f"NtQuerySystemInformation 返回 status: {status}")

        if status == 0:
            break
        elif status == STATUS_INFO_LENGTH_MISMATCH:
            handle_info_size *= 2  # 如果缓冲区太小，就将其大小加倍
            print(f"缓冲区太小，新的 handle_info_size: {handle_info_size}")
        else:
            raise ctypes.WinError(status)

    handle_count = ctypes.cast(handle_info, ctypes.POINTER(ctypes.c_ulong)).contents.value
    print(f"获取到的 handle_count: {handle_count}")
    offset = 0
    size_of_handle_info = ctypes.sizeof(SYSTEM_HANDLE_INFORMATION)
    for i in range(handle_count):
        handle = SYSTEM_HANDLE_INFORMATION.from_buffer_copy(handle_info, offset)
        offset += size_of_handle_info
        print(handle.ProcessId)
        if handle.ProcessId == process_id:
            handles.append(handle)
            print(f"匹配的句柄: {handle}")

    print("结束了 get_handles 方法")
    return handles


def find_and_close_wechat_mutex_handle(handle, process_handle):
    print("进入了 find_and_close_wechat_mutex_handle 方法")
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
        print("DuplicateHandle 失败")
        return False

    object_name_info = ctypes.create_string_buffer(1024)
    return_length = ctypes.c_ulong(0)
    print("调用 NtQueryObject 获取 object_name_info")
    status = NtQueryObject(
        duplicate_handle,
        1,  # ObjectNameInformation
        object_name_info,
        1024,
        ctypes.byref(return_length)
    )
    print(f"NtQueryObject 返回 status: {status}")

    if status == 0:
        name_info = ctypes.cast(object_name_info, ctypes.POINTER(OBJECT_NAME_INFORMATION)).contents
        print(f"获取到的 name_info: {name_info}")
        if name_info.Name.Buffer:
            object_name = ctypes.wstring_at(name_info.Name.Buffer, name_info.Name.Length)
            print(f"获取到的 object_name: {object_name}")
            if "_WeChat_App_Instance_Identity_Mutex_Name" in object_name:
                print("找到了 _WeChat_App_Instance_Identity_Mutex_Name")
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
                print("成功关闭了 WeChat Mutex Handle")
                print("结束了 find_and_close_wechat_mutex_handle 方法")
                return True

    kernel32.CloseHandle(duplicate_handle)
    print("结束了 find_and_close_wechat_mutex_handle 方法")
    return False


def close_mutex_handle(process):
    print("进入了 close_mutex_handle 方法")
    try:
        process_handle = win32api.OpenProcess(
            win32con.PROCESS_DUP_HANDLE | win32con.PROCESS_QUERY_INFORMATION,
            False,
            process.pid
        )
        print(f"获取到的 process_handle: {process_handle}")
    except win32api.error as e:
        print(f"捕获到的异常: {e}")
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
            print(f"提升权限后的 process_handle: {process_handle}")
            if not process_handle:
                print(f"无法打开进程 {process.pid}，权限不足。继续执行...")
                print("结束了 close_mutex_handle 方法")
                return False
        else:
            print("重新抛出异常")
            raise  # 如果是其他错误，则重新抛出

    if not process_handle:
        print("没有 process_handle，返回 False")
        print("结束了 close_mutex_handle 方法")
        return False

    print(f"使用process.pid: {process.pid}")
    handles = get_handles(process.pid)
    print(f"获取到的 handles: {handles}")
    exist_mutex_handle = False

    for handle in handles:
        print(f"处理 handle: {handle}")
        if handle.ObjectTypeIndex == OBJECT_TYPE_MUTANT:
            if find_and_close_wechat_mutex_handle(handle, process_handle):
                exist_mutex_handle = True
                print(f"成功关闭了互斥体句柄: {handle}")

    win32api.CloseHandle(process_handle)
    print("结束了 close_mutex_handle 方法")
    return exist_mutex_handle


def get_wechat_path():
    print("进入了 get_wechat_path 方法")
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Tencent\WeChat")
        print(f"打开注册表项: {key}")
        path = winreg.QueryValueEx(key, "InstallPath")[0]
        print(f"获取到的 WeChat 安装路径: {path}")
        winreg.CloseKey(key)
        print("结束了 get_wechat_path 方法")
        return path
    except WindowsError as e:
        print(f"捕获到的异常: {e}")
        print("未找到 WeChat 安装路径")
        print("结束了 get_wechat_path 方法")
        return None


def run_wechat():
    print("进入了 run_wechat 方法")
    for proc in psutil.process_iter(['name', 'pid', 'username']):
        print(f"检查进程: {proc.info}")
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
        print(f"WeChat 可执行文件路径: {wechat_exe}")
        try:
            win32api.WinExec(wechat_exe, 1)
            print("WeChat 启动成功")
        except Exception as e:
            print(f"启动WeChat时出错: {e}")
    else:
        print("未找到WeChat安装路径。")
    print("结束了 run_wechat 方法")


if __name__ == "__main__":
    run_wechat()
