import ctypes

import psutil

# 相关常量
PROCESS_ALL_ACCESS = 0x001F0FFF
DUPLICATE_SAME_ACCESS = 0x2
CNST_SYSTEM_HANDLE_INFORMATION = 0x10
STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
OBJECT_TYPE_MUTANT = 17


# 相关结构体
class SYSTEM_HANDLE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("ProcessId", ctypes.c_ushort),
        ("CreatorBackTraceIndex", ctypes.c_ushort),
        ("ObjectTypeNumber", ctypes.c_byte),
        ("Flags", ctypes.c_byte),
        ("Handle", ctypes.c_ushort),
        ("Object", ctypes.c_void_p),
        ("GrantedAccess", ctypes.c_ulong),
    ]


# 新增方法：通过新的方式获取WeChat互斥体句柄
def new_get_wechat_mutex_handles():
    handles = []

    # 获取所有WeChat进程的PID
    pids = [p.info["pid"] for p in psutil.process_iter(attrs=["pid", "name"]) if p.info["name"] == "WeChat.exe"]
    print(f"找到的WeChat进程ID: {pids}")

    for pid in pids:
        print(f"处理进程ID: {pid}")

        process_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not process_handle:
            print(f"无法打开进程，PID: {pid}")
            continue

        # 枚举进程的句柄
        handle_info_size = ctypes.sizeof(SYSTEM_HANDLE_INFORMATION) * 20000
        handle_info = ctypes.create_string_buffer(handle_info_size)
        return_length = ctypes.c_ulong(0)

        while ctypes.windll.ntdll.NtQuerySystemInformation(
                CNST_SYSTEM_HANDLE_INFORMATION, handle_info, handle_info_size, ctypes.byref(return_length)
        ) == STATUS_INFO_LENGTH_MISMATCH:
            handle_info_size = return_length.value
            handle_info = ctypes.create_string_buffer(handle_info_size)

        handle_count = return_length.value // ctypes.sizeof(SYSTEM_HANDLE_INFORMATION)
        handle_array = ctypes.cast(handle_info, ctypes.POINTER(SYSTEM_HANDLE_INFORMATION * handle_count)).contents

        for handle in handle_array:
            if handle.ProcessId == pid and handle.ObjectTypeNumber == OBJECT_TYPE_MUTANT:
                # 进一步检查句柄的名称，查找目标互斥体
                # ...（此处可以复用之前的FindAndCloseWeChatMutexHandle方法）
                print(f"找到匹配的句柄: {handle.Handle}")
                handles.append(handle)

        ctypes.windll.kernel32.CloseHandle(process_handle)

    return handles


# 调用新增方法
mutex_handles = new_get_wechat_mutex_handles()
print(f"获取到的WeChat互斥体句柄: {mutex_handles}")
