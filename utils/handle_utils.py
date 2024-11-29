import re
import subprocess

import psutil

from resources import Config
from utils import process_utils
import os
import time
from ctypes import *
from ctypes.wintypes import *

from win32api import *
from win32process import *

from utils.logger_utils import mylogger as logger
import psutil

def get_file_process(file_path):
    for process in psutil.process_iter(['pid', 'name']):
        try:
            for file in process.open_files():
                if file_path == file.path:
                    return process.info
        except psutil.AccessDenied:
            pass
    return None

file_path = 'example.txt'
process_info = get_file_process(file_path)

if process_info:
    print(f"The file {file_path} is being used by process {process_info['name']} (PID: {process_info['pid']})")
else:
    print(f"The file {file_path} is not being used by any process")

ntdll = WinDLL('ntdll')
current_process = GetCurrentProcess()

NTSTATUS = LONG
ULONG_PTR = WPARAM
ACCESS_MASK = DWORD

STATUS_SUCCESS = NTSTATUS(0).value
STATUS_BUFFER_OVERFLOW = NTSTATUS(0x80000005).value
STATUS_NO_MORE_FILES = NTSTATUS(0x80000006).value
STATUS_INFO_LENGTH_MISMATCH = NTSTATUS(0xC0000004).value

DUPLICATE_CLOSE_SOURCE = 0x00000001
DUPLICATE_SAME_ACCESS = 0x00000002
DUPLICATE_SAME_ATTRIBUTES = 0x00000004

STANDARD_RIGHTS_REQUIRED = 0x000F0000
SYNCHRONIZE = 0x00100000
PROCESS_TERMINATE = 0x0001
PROCESS_CREATE_THREAD = 0x0002
PROCESS_SET_SESSIONID = 0x0004
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_DUP_HANDLE = 0x0040
PROCESS_CREATE_PROCESS = 0x0080
PROCESS_SET_QUOTA = 0x0100
PROCESS_SET_INFORMATION = 0x0200
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_SUSPEND_RESUME = 0x0800
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_ALL_ACCESS = (STANDARD_RIGHTS_REQUIRED | SYNCHRONIZE | 0xfff)

SYSTEM_INFORMATION_CLASS = ULONG
SystemExtendedHandleInformation = ULONG(64)

OBJECT_INFORMATION_CLASS = ULONG
ObjectBasicInformation = ULONG(0)
ObjectNameInformation = ULONG(1)
ObjectTypeInformation = ULONG(2)

ntdll.NtQuerySystemInformation.restype = NTSTATUS
ntdll.NtQuerySystemInformation.argtypes = [
    SYSTEM_INFORMATION_CLASS,
    LPVOID,
    ULONG,
    PULONG]

ntdll.NtQueryObject.restype = NTSTATUS
ntdll.NtQueryObject.argtypes = [
    HANDLE,
    OBJECT_INFORMATION_CLASS,
    LPVOID,
    ULONG,
    PULONG]

ntdll.NtDuplicateObject.restype = NTSTATUS
ntdll.NtDuplicateObject.argtypes = [
    HANDLE,
    HANDLE,
    HANDLE,
    PHANDLE,
    ACCESS_MASK,
    ULONG,
    ULONG]


# 定义Windows API相关的常量和结构体
class UNICODE_STRING(Structure):
    _fields_ = [('Length', USHORT),
                ('MaximumLength', USHORT),
                ('Buffer', LPWSTR)]


class SYSTEM_HANDLE(Structure):
    _fields_ = [
        ('Object', LPVOID),
        ('UniqueProcessId', HANDLE),
        ('HandleValue', HANDLE),
        ('GrantedAccess', ULONG),
        ('CreatorBackTraceIndex', USHORT),
        ('ObjectTypeIndex', USHORT),
        ('HandleAttributes', ULONG),
        ('Reserved', ULONG),
    ]


class SYSTEM_HANDLE_INFORMATION_EX(Structure):
    _fields_ = [
        ('HandleCount', ULONG_PTR),
        ('Reserved', ULONG_PTR),
        ('Handles', SYSTEM_HANDLE * 2),
    ]


class OBJECT_BASIC_INFORMATION(Structure):
    _fields_ = [
        ('Attributes', ULONG),
        ('GrantedAccess', ACCESS_MASK),
        ('HandleCount', ULONG),
        ('PointerCount', ULONG),
        ('PagedPoolCharge', ULONG),
        ('NonPagedPoolCharge', ULONG),
        ('Reserved', ULONG * 3),
        ('NameInfoSize', ULONG),
        ('TypeInfoSize', ULONG),
        ('SecurityDescriptorSize', ULONG),
        ('CreationTime', LARGE_INTEGER),
    ]


class OBJECT_NAME_INFORMATION(Structure):
    _fields_ = [
        ('Name', UNICODE_STRING),
    ]


class OBJECT_TYPE_INFORMATION(Structure):
    _fields_ = [
        ('TypeName', UNICODE_STRING),
        ('Reserved', ULONG * 22),
    ]


def query_system_handle_information():
    current_length = 0x10000
    while True:
        if current_length > 0x4000000:
            return

        class SYSTEM_HANDLE_INFORMATION_EX(Structure):
            _fields_ = [
                ('HandleCount', ULONG_PTR),
                ('Reserved', ULONG_PTR),
                ('Handles', SYSTEM_HANDLE * current_length)
            ]

        buf = SYSTEM_HANDLE_INFORMATION_EX()
        return_length = c_ulong(current_length)
        status = ntdll.NtQuerySystemInformation(SystemExtendedHandleInformation, byref(buf), return_length,
                                                byref(return_length))
        if status == STATUS_SUCCESS:
            return buf
        elif status == STATUS_INFO_LENGTH_MISMATCH:
            current_length *= 8
            continue
        else:
            return None


def query_object_basic_info(h):
    basic_info = OBJECT_BASIC_INFORMATION()
    return_length = c_ulong(sizeof(OBJECT_BASIC_INFORMATION))
    status = ntdll.NtQueryObject(h, ObjectBasicInformation, byref(basic_info), return_length, byref(return_length))
    if status == STATUS_SUCCESS:
        return basic_info
    elif status == STATUS_INFO_LENGTH_MISMATCH:
        return None
    else:
        return None


def query_object_name_info(h, length):
    name_info = OBJECT_NAME_INFORMATION()
    return_length = c_ulong(length + sizeof(OBJECT_NAME_INFORMATION))
    status = ntdll.NtQueryObject(h, ObjectNameInformation, byref(name_info), return_length, byref(return_length))
    if status == STATUS_SUCCESS:
        return name_info
    elif status == STATUS_INFO_LENGTH_MISMATCH:
        return None
    else:
        return None


def query_object_type_info(h, length):
    type_info = OBJECT_TYPE_INFORMATION()
    return_length = c_ulong(length + sizeof(OBJECT_TYPE_INFORMATION))
    status = ntdll.NtQueryObject(h, ObjectTypeInformation, byref(type_info), return_length, byref(return_length))
    if status == STATUS_SUCCESS:
        return type_info
    elif status == STATUS_INFO_LENGTH_MISMATCH:
        return None
    else:
        return None


def duplicate_object(source_process_handle, source_handle):
    h = HANDLE()
    status = ntdll.NtDuplicateObject(source_process_handle, source_handle, current_process, byref(h), 0, 0,
                                     DUPLICATE_SAME_ACCESS | DUPLICATE_SAME_ATTRIBUTES)
    if status == STATUS_SUCCESS:
        return h
    else:
        return None


def close(handle):
    return ntdll.NtClose(handle)


def find_handles(process_ids=None, handle_names=None):
    result = []
    system_info = query_system_handle_information()
    if system_info.HandleCount is None:
        return result
    for i in range(system_info.HandleCount):
        handle_info = system_info.Handles[i]
        handle = handle_info.HandleValue
        process_id = handle_info.UniqueProcessId
        if process_ids and process_id not in process_ids:
            continue
        try:
            source_process = OpenProcess(PROCESS_ALL_ACCESS | PROCESS_DUP_HANDLE | PROCESS_SUSPEND_RESUME, False,
                                         process_id)
        except:
            continue
        handle_name = None
        handle_type = None
        duplicated_handle = duplicate_object(source_process.handle, handle)
        if duplicated_handle:
            basic_info = query_object_basic_info(duplicated_handle)
            if basic_info:
                if basic_info.NameInfoSize > 0:
                    name_info = query_object_name_info(duplicated_handle, basic_info.NameInfoSize)
                    if name_info:
                        handle_name = name_info.Name.Buffer[0]
                if basic_info.TypeInfoSize > 0:
                    type_info = query_object_type_info(duplicated_handle, basic_info.TypeInfoSize)
                    if type_info:
                        handle_type = type_info.TypeName.Buffer[0]
            close(duplicated_handle)
        if handle_names:
            if not handle_name:
                continue
            matched = False
            for target in handle_names:
                if target == handle_name or target in handle_name:
                    matched = True
                    break
            if not matched:
                continue
        result.append(dict(process_id=process_id, handle=handle, name=handle_name, type=handle_type))
        logger.info(str(result))
    return result


def close_handles(handles):
    try:
        processes = {}
        for h in handles:
            process_id = h['process_id']
            handle = h['handle']
            process = processes.get(process_id)
            if not process:
                process = OpenProcess(PROCESS_DUP_HANDLE, False, process_id)
                processes[process_id] = process
            DuplicateHandle(process, handle, 0, 0, 0, DUPLICATE_CLOSE_SOURCE)
        for p in processes.values():
            CloseHandle(p)
            logger.info(f"Closed:{str(processes)}")
        return True
    except Exception as e:
        logger.error(e)
        return False



ntdll = windll.ntdll
# NtQueryObject 函数定义
def query_object_name(handle):
    name_info = OBJECT_NAME_INFORMATION()
    return_length = c_ulong(0)
    status = ntdll.NtQueryObject(handle, 1, byref(name_info), c_ulong(1024), byref(return_length))

    if status == 0:  # STATUS_SUCCESS
        return name_info.Name.Buffer[:name_info.Name.Length // 2]  # 返回文件路径
    return None


# 获取进程句柄并查找文件路径
def find_handles_and_file_paths(process_ids=None):
    result = []
    system_info = query_system_handle_information()
    if system_info.HandleCount is None:
        return result

    for i in range(system_info.HandleCount):
        handle_info = system_info.Handles[i]
        handle = handle_info.HandleValue
        process_id = handle_info.UniqueProcessId
        if process_ids and process_id not in process_ids:
            continue

        try:
            source_process = OpenProcess(PROCESS_ALL_ACCESS | PROCESS_DUP_HANDLE | PROCESS_SUSPEND_RESUME, False,
                                         process_id)
        except:
            continue

        handle_name = None
        handle_type = None
        duplicated_handle = duplicate_object(source_process.handle, handle)

        if duplicated_handle:
            basic_info = query_object_basic_info(duplicated_handle)
            if basic_info:
                if basic_info.TypeInfoSize > 0:
                    type_info = query_object_type_info(duplicated_handle, basic_info.TypeInfoSize)
                    if type_info:
                        handle_type = type_info.TypeName.Buffer[0]

            # 获取文件路径
            if handle_type == 'File':
                file_path = query_object_name(duplicated_handle)
                if file_path:
                    handle_name = file_path.decode('utf-16')  # 解码为字符串

            if handle_name:
                result.append(dict(process_id=process_id, handle=handle, name=handle_name, type=handle_type))

            close(duplicated_handle)

    return result


def close_mutex_of_pids_by_handle():
    """
    通过微信进程id查找互斥体并关闭
    :return: 是否成功
    """
    print(f"进入了关闭互斥体的方法...")
    # 定义句柄名称
    handle_name = "_WeChat_App_Instance_Identity_Mutex_Name"
    start_time = time.time()
    handle_exe_path = os.path.join(Config.PROJ_EXTERNAL_RES_PATH, 'handle.exe')

    # 获取句柄信息
    handle_info = subprocess.check_output([handle_exe_path, '-a', '-p', f"WeChat", handle_name]).decode()
    print(f"完成获取句柄信息：{handle_info}")
    print(f"{time.time() - start_time}")

    # 匹配所有 PID 和句柄信息
    matches = re.findall(r"pid:\s*(\d+).*?(\w+):\s*\\Sessions", handle_info)
    if matches:
        print(f"找到互斥体：{matches}")
    else:
        print(f"没有找到任何互斥体")
        return []

    # 用于存储成功关闭的句柄
    successful_closes = []

    # 遍历所有匹配项，尝试关闭每个句柄
    for wechat_pid, handle in matches:
        print(f"尝试关闭互斥体句柄: hwnd:{handle}, pid:{wechat_pid}")
        try:
            stdout = None
            try:
                command = " ".join([handle_exe_path, '-c', handle, '-p', str(wechat_pid), '-y'])
                print(f"执行命令：{command}")
                # 使用 Popen 启动子程序并捕获输出
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                           shell=True)
                # 检查子程序是否具有管理员权限
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
                print(f"Command failed with exit code {e.returncode}")
            if stdout is not None and "Error closing handle:" in stdout:
                continue
            print(f"成功关闭句柄: hwnd:{handle}, pid:{wechat_pid}")
            successful_closes.append((wechat_pid, handle))
        except subprocess.CalledProcessError as e:
            print(f"无法关闭句柄 PID: {wechat_pid}, 错误信息: {e}")

    print(f"成功关闭的句柄列表: {successful_closes}")
    return successful_closes

if __name__ == '__main__':
    # def update_acc_list_by_pid(process_id: int):
    #     """
    #     为存在的微信进程匹配出对应的账号，并更新[已登录账号]和[(已登录进程,账号)]
    #     :param process_id: 微信进程id
    #     :return: 无
    #     """
    #     # print(data_path)
    #     try:
    #         # 获取指定进程的内存映射文件路径
    #         for f in psutil.Process(process_id).open_files():
    #             print(f)
    #             # 将路径中的反斜杠替换为正斜杠
    #             normalized_path = f.path.replace('\\', '/')
    #             print(normalized_path)
    #
    #             # # 检查路径是否以 data_path 开头
    #             # if normalized_path.startswith(data_path):
    #             #     # print(
    #             #     #     f"┌———匹配到进程{process_id}使用的符合的文件，待比对，已用时：{time.time() - start_time:.4f}秒")
    #             #     # print(f"提取中：{f.path}")
    #             #     path_parts = f.path.split(os.path.sep)
    #             #     try:
    #             #         wx_id_index = path_parts.index(os.path.basename(data_path)) + 1
    #             #         wx_id = path_parts[wx_id_index]
    #             #         wechat_processes.append((wx_id, process_id))
    #             #         logged_in_ids.add(wx_id)
    #             #         print(f"进程{process_id}对应账号{wx_id}，已用时：{time.time() - start_time:.4f}秒")
    #             #         break
    #             #     except ValueError:
    #             #         pass
    #     except psutil.AccessDenied:
    #         logger.error(f"无法访问进程ID为 {process_id} 的内存映射文件，权限不足。")
    #     except psutil.NoSuchProcess:
    #         logger.error(f"进程ID为 {process_id} 的进程不存在或已退出。")
    #     except Exception as e:
    #         logger.error(f"发生意外错误: {e}")
    #
    #
    # process_ids = process_utils.get_process_ids_by_name("Weixin.exe")
    # update_acc_list_by_pid(process_ids[0])

    file_path = r'C:\Users\25359\AppData\Roaming\Tencent\xwechat\lock\lock.ini'
    process_info = get_file_process(file_path)

    if process_info:
        print(f"The file {file_path} is being used by process {process_info['name']} (PID: {process_info['pid']})")
    else:
        print(f"The file {file_path} is not being used by any process")

    # # 获取所有进程的句柄和对应的文件路径
    # process_ids = process_utils.get_process_ids_by_name("Weixin.exe")
    # handles = find_handles_and_file_paths(process_ids=process_ids)
    # print(f"找到的句柄信息：{handles}")
    #
    # # 打印结果
    # for handle in handles:
    #     print(handle)










