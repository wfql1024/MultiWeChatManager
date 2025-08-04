# handle_utils.py
import ctypes
import fnmatch
import re
import subprocess
import time
from ctypes import *
from ctypes.wintypes import *

from win32api import *
from win32process import *

from resources import Config
from utils import process_utils
from utils.encoding_utils import StringUtils
from utils.logger_utils import Printer, Logger
from utils.pywinhandle.src import pywinhandle

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
OpenProcess = kernel32.OpenProcess
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


class UNICODE_STRING(Structure):
    _fields_ = [
        ('Length', USHORT),
        ('MaximumLength', USHORT),
        ('Buffer', LPWSTR * 4096),
    ]


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


# 方法区 ------------------------------------------------------------------------------------------------------------


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


def close_handles_matched(handle_exe, matches):
    """
    封装关闭句柄的操作，遍历所有匹配项并尝试关闭每个句柄。

    参数:
        handle_exe (str): 用于关闭句柄的可执行文件路径
        matches (list): 包含进程 ID 和句柄的元组列表，格式为 [(wechat_pid, handle), ...]

    返回:
        list: 成功关闭的句柄列表，格式为 [(wechat_pid, handle), ...]
    """
    # 用于存储成功关闭的句柄和成功元组
    handles_closed = []
    successes = []

    # 遍历所有匹配项，尝试关闭每个句柄
    for wechat_pid, handle in matches:
        Printer().print_vn(f"hwnd:{handle}, pid:{wechat_pid}")
        stdout = None
        # 尝试执行命令获取输出
        try:
            # 构建命令
            formatted_handle_exe = handle_exe.replace("\\", "/")
            formatted_handle = handle.replace("\\", "/")
            command = " ".join([f'"{formatted_handle_exe}"', '-c', f'"{formatted_handle}"',
                                '-p', str(wechat_pid), '-y'])
            Printer().print_vn(f"指令：{command}")
            # 使用 Popen 启动子程序并捕获输出
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
            # 检查子进程是否具有管理员权限
            if process_utils.is_pid_elevated(process.pid):
                Printer().print_vn(f"子进程 {process.pid} 以管理员权限运行")
            else:
                Printer().print_vn(f"子进程 {process.pid} 没有管理员权限")
            # 获取输出结果
            stdout, stderr = process.communicate()
            # 检查返回的 stdout 和 stderr
            if stdout:
                Printer().print_vn(f"输出：{stdout}完毕。")
            if stderr:
                Printer().print_vn(f"错误：{stderr}")
        except subprocess.CalledProcessError as e:
            Logger().error(f"命令执行失败，退出码 {e.returncode}")
        except Exception as e:
            Logger().error(f"发生异常: {e}")

        # 如果stdout包含"Error closing handle"，则失败，下一个
        if stdout is None or "Error closing handle:" in stdout:
            Printer().print_vn(f"句柄关闭失败: hwnd:{handle}, pid:{wechat_pid}")
            successes.append(False)
            continue

        Printer().print_vn(f"成功关闭句柄: hwnd:{handle}, pid:{wechat_pid}")
        handles_closed.append((wechat_pid, handle))
        successes.append(True)

    Printer().print_vn(f"成功关闭的句柄列表: {handles_closed}")
    return all(successes), handles_closed


def close_sw_mutex_by_handle(handle_exe, exe, handle_regex_dicts):
    """通过handle，根据规则字典对指定程序查找互斥体并关闭"""
    if handle_regex_dicts is None or len(handle_regex_dicts) == 0:
        return False, []

    handles_closed_lists = []
    successes = []
    for handle_regex_dict in handle_regex_dicts:
        try:
            wildcard, regex = handle_regex_dict.get("wildcard"), handle_regex_dict.get("regex")
            Printer().vital(f"handle模式")
            Printer().print_vn(f"进入了关闭互斥体的方法...")
            Printer().print_vn(f"句柄名：{wildcard}")
            Printer().print_vn(f"模式：{regex}")
            start_time = time.time()

            formatted_handle_exe = handle_exe.replace("\\", "/")
            formatted_exe = exe.replace("\\", "/")
            formatted_wildcard = wildcard.replace("\\", "/")
            formatted_handle_name = StringUtils.extract_longest_substring(formatted_wildcard)
            # 获取句柄信息
            handle_cmd = " ".join([f'"{formatted_handle_exe}"', '-a', '-p',
                                   f'"{formatted_exe}"', f'"{formatted_handle_name}"'])
            Printer().vital(f"handle-查找句柄")
            Printer().cmd_in(handle_cmd)
            handle_output = subprocess.check_output(
                handle_cmd, creationflags=subprocess.CREATE_NO_WINDOW, text=True)
            # Printer().print_vn(f"信息：{handle_output}")
            Printer().cmd_out(handle_output)
            Printer().print_vn(f"用时：{time.time() - start_time:.4f}秒")

            # 匹配所有 PID 和句柄信息
            Printer().vital(f"handle-匹配句柄")
            matches = re.findall(regex, handle_output)
            if matches:
                Printer().print_vn(f"含互斥体：{matches}")
                Printer().vital("handle-关闭句柄")
                success, handles_closed = close_handles_matched(Config.HANDLE_EXE_PATH, matches)
                handles_closed_lists.append(handles_closed)
                successes.append(success)
            else:
                Printer().print_vn(f"无互斥体")
        except Exception as e:
            Logger().error(f"关闭句柄失败：{e}")
    return all(successes), handles_closed_lists


def _pywinhandle_query_system_handle_information():
    current_length = 0x1000000
    while True:
        # 添加了限制会容易找不到
        # if current_length > 0x4000000:
        #     return
        # start_time = time.time()
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
        # print(f"{current_length}:{time.time() - start_time}")
        if status == STATUS_SUCCESS:
            return buf
        elif status == STATUS_INFO_LENGTH_MISMATCH:
            current_length *= 4
            continue
        else:
            return None


def _traverse_system_handles_by_index(system_info, i, process_ids):
    handle_info = system_info.Handles[i]
    handle = handle_info.HandleValue
    process_id = handle_info.UniqueProcessId
    process_ids = [int(x) if isinstance(x, str) and x.isdigit() else x for x in process_ids]
    if isinstance(process_ids, list) and process_id not in process_ids:
        return None
    try:
        source_process = OpenProcess(PROCESS_ALL_ACCESS | PROCESS_DUP_HANDLE | PROCESS_SUSPEND_RESUME, False,
                                     process_id)
    except:
        return None
    handle_name = None
    handle_type = None
    duplicated_handle = pywinhandle.duplicate_object(source_process, handle)
    # Printer().debug(f"Duplicated handle: {duplicated_handle}")
    # try:
    #     Printer().debug("----------------------------------------------------------")
    #     Printer().debug(f"Duplicated handle: {duplicated_handle}")
    #     basic_info = query_object_basic_info(duplicated_handle)
    #     Printer().debug(f"Basic info: {basic_info}")
    #     name_info_size = basic_info.NameInfoSize
    #     Printer().debug(f"Name info size: {name_info_size}")
    #     type_info_size = basic_info.TypeInfoSize
    #     Printer().debug(f"Type info size: {type_info_size}")
    #     name_info = query_object_name_info(duplicated_handle, basic_info.NameInfoSize)
    #     handle_name = name_info.Name.Buffer[0]
    #     type_info = query_object_type_info(duplicated_handle, basic_info.TypeInfoSize)
    #     handle_type = type_info.TypeName.Buffer[0]
    #     # Printer().debug(f"Handle name: {handle_name}, Handle type: {handle_type}")
    # except:
    #     pass
    # Printer().debug(f"Basic info: {basic_info}")
    if duplicated_handle:
        basic_info = pywinhandle.query_object_basic_info(duplicated_handle)
        if basic_info:
            if basic_info.NameInfoSize >= 0:
                name_info = pywinhandle.query_object_name_info(duplicated_handle, basic_info.NameInfoSize)
                if name_info:
                    handle_name = name_info.Name.Buffer[0]
            if basic_info.TypeInfoSize >= 0:
                type_info = pywinhandle.query_object_type_info(duplicated_handle, basic_info.TypeInfoSize)
                if type_info:
                    handle_type = type_info.TypeName.Buffer[0]
        pywinhandle.close(duplicated_handle)
    return process_id, handle, handle_name, handle_type


def pywinhandle_find_handles_by_pids_and_handle_names(process_ids=None, handle_names=None):
    result = []
    system_info = _pywinhandle_query_system_handle_information()
    if system_info.HandleCount is None:
        return result
    for i in range(system_info.HandleCount):
        res = _traverse_system_handles_by_index(system_info, i, process_ids)
        if isinstance(res, tuple) and len(res) == 4:
            process_id, handle, handle_name, handle_type = res
        else:
            continue
        if handle_names:
            if not handle_name:
                continue
            # Printer().debug(handle_name)
            # print(handle_name)
            matched = False
            for target in handle_names:
                if target == handle_name or target in handle_name:
                    matched = True
                    break
            if not matched:
                continue
        result.append(dict(process_id=process_id, handle=handle, name=handle_name, type=handle_type))
        # Logger().info(str(result))
    return result


def pywinhandle_find_handles_by_pids_and_handle_name_wildcards(process_ids=None, handle_name_wildcards=None):
    """根据传入的pid列表和句柄通配列表查找符合条件的句柄,传入空值表示不限制."""
    Printer().debug(f"参数: {process_ids}, {handle_name_wildcards}")
    result = []
    system_info = _pywinhandle_query_system_handle_information()
    if system_info.HandleCount is None:
        return result
    for i in range(system_info.HandleCount):
        res = _traverse_system_handles_by_index(system_info, i, process_ids)
        if isinstance(res, tuple) and len(res) == 4:
            process_id, handle, handle_name, handle_type = res
        else:
            continue
        if isinstance(handle_name_wildcards, list):
            if not handle_name:
                continue
            # print(handle_name)
            matched = False
            for wildcard in handle_name_wildcards:
                if fnmatch.fnmatch(handle_name, wildcard):
                    matched = True
                    break
                if fnmatch.fnmatch(handle_name, f"*{wildcard}*"):
                    matched = True
                    break
            if not matched:
                continue
        result.append(dict(process_id=process_id, handle=handle, name=handle_name, type=handle_type))
    return result


def pywinhandle_close_handles(handle_dicts):
    try:
        processes = {}
        for h in handle_dicts:
            process_id = h['process_id']
            handle = h['handle']
            process = processes.get(process_id)
            if not process:
                process = OpenProcess(PROCESS_DUP_HANDLE, False, process_id)
                processes[process_id] = process
            DuplicateHandle(process, handle, 0, 0, 0, DUPLICATE_CLOSE_SOURCE)
        for p in processes.values():
            CloseHandle(p)
        return True
    except Exception as e:
        Logger().error(e)
        return False
