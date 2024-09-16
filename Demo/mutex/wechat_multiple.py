import ctypes
import ctypes.wintypes as wt

# 定义必要的常量和结构体
MAX_PATH = 260
PROCESS_ALL_ACCESS = 0x1F0FFF
DUPLICATE_SAME_ACCESS = 0x00000002
DUPLICATE_CLOSE_SOURCE = 0x00000001


class SYSTEM_HANDLE_TABLE_ENTRY_INFO(ctypes.Structure):
    _fields_ = [
        ("UniqueProcessId", wt.USHORT),
        ("CreatorBackTraceIndex", wt.USHORT),
        ("ObjectTypeIndex", wt.CHAR),
        ("HandleAttributes", wt.CHAR),
        ("HandleValue", wt.USHORT),
        ("Object", wt.LPVOID),
        ("GrantedAccess", wt.ULONG),
    ]


class SYSTEM_HANDLE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("NumberOfHandles", wt.ULONG),
        ("Handles", SYSTEM_HANDLE_TABLE_ENTRY_INFO * 1),
    ]


# 加载必要的DLL
kernel32 = ctypes.windll.kernel32
ntdll = ctypes.windll.ntdll
psapi = ctypes.windll.psapi


def get_proc_ids(process_name):
    pids = (wt.DWORD * 1024)()
    cb = wt.DWORD()
    psapi.EnumProcesses(ctypes.byref(pids), ctypes.sizeof(pids), ctypes.byref(cb))
    pids_count = cb.value // ctypes.sizeof(wt.DWORD)

    result = []
    for i in range(pids_count):
        pid = pids[i]
        h_process = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if h_process:
            image_name = (ctypes.c_char * MAX_PATH)()
            if psapi.GetProcessImageFileNameA(h_process, image_name, MAX_PATH) > 0:
                if process_name.encode() in image_name.value:
                    result.append(pid)
            kernel32.CloseHandle(h_process)
    return result


def is_target_pid(pid, pid_list):
    return pid in pid_list


def duplicate_handle_ex(source_pid, source_handle, access):
    print(source_pid)
    h_source_process = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, source_pid)
    if not h_source_process:
        return None

    target_handle = wt.HANDLE()
    success = kernel32.DuplicateHandle(
        h_source_process,
        source_handle,
        kernel32.GetCurrentProcess(),
        ctypes.byref(target_handle),
        0,
        False,
        access
    )
    kernel32.CloseHandle(h_source_process)

    if success:
        return target_handle
    return None


def nt_query_object(handle, object_information_class, buffer_size=512):
    buffer = ctypes.create_string_buffer(buffer_size)
    size = wt.ULONG()
    status = ntdll.NtQueryObject(handle, object_information_class, buffer, buffer_size, ctypes.byref(size))
    if status == 0:
        return buffer.raw[:size.value]
    return None


# 主程序
pids = get_proc_ids("WeChat.exe")
print(pids)

# 获取系统句柄信息
buffer_size = 0x10000
while True:
    buffer = ctypes.create_string_buffer(buffer_size)
    ret_length = wt.ULONG()
    status = ntdll.NtQuerySystemInformation(16, buffer, buffer_size, ctypes.byref(ret_length))
    if status == 0:
        break
    buffer_size *= 2

handle_info = SYSTEM_HANDLE_INFORMATION.from_buffer_copy(buffer)
handles_array = (SYSTEM_HANDLE_TABLE_ENTRY_INFO * (
        buffer_size // ctypes.sizeof(SYSTEM_HANDLE_TABLE_ENTRY_INFO))).from_buffer_copy(
    buffer[ctypes.sizeof(wt.ULONG):])

for handle in handles_array[:handle_info.NumberOfHandles]:
    print(handle)
    if is_target_pid(handle.UniqueProcessId, pids):
        h_handle = duplicate_handle_ex(handle.UniqueProcessId, handle.HandleValue, DUPLICATE_SAME_ACCESS)
        if h_handle:
            object_name = nt_query_object(h_handle, 1)  # ObjectNameInformation
            object_type = nt_query_object(h_handle, 2)  # ObjectTypeInformation

            if object_type and b"Mutant" in object_type:
                if object_name and b"_WeChat_App_Instance_Identity_Mutex_Name" in object_name:
                    h_handle = duplicate_handle_ex(handle.UniqueProcessId, handle.HandleValue, DUPLICATE_CLOSE_SOURCE)
                    if h_handle:
                        print("+ Patch wechat success!")
                        kernel32.CloseHandle(h_handle)

            kernel32.CloseHandle(h_handle)


if __name__ == '__main__':
    from pywinhandle import find_handles, close_handles

    handles = find_handles(handle_names=["_WeChat_App_Instance_Identity_Mutex_Name"])
    close_handles(handles)

