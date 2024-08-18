import ctypes
import time
from ctypes import wintypes

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


def get_process_ids_by_name(process_name):
    """通过进程名获取所有匹配进程的ID和句柄"""
    matching_processes = []
    start_time = time.time()
    processes = psutil.process_iter(['name'])
    for proc in processes:
        if proc.name().lower() == process_name.lower():
            pid = proc.pid
            matching_processes.append(pid)
    return matching_processes


def get_process_by_name(process_name):
    """通过进程名获取进程ID和句柄"""
    for proc in psutil.process_iter(['name', 'pid']):
        if proc.name().lower() == process_name.lower():
            pid = proc.pid
            handle = OpenProcess(PROCESS_ALL_ACCESS, False, pid)
            return pid, handle
    return None, None


def get_process_handle(pid):
    handle = OpenProcess(PROCESS_ALL_ACCESS, False, pid)

    if handle == 0 or handle == -1:  # 0 和 -1 都表示失败
        error = ctypes.get_last_error()
        print(f"无法获取进程句柄，错误码：{error}")
        return None

    return handle


def get_module_base_address(process_handle, module_name):
    """获取指定模块（DLL）在目标进程中的基址"""
    hModules = (ctypes.wintypes.HMODULE * 1024)()
    cbNeeded = ctypes.wintypes.DWORD()
    module_name_bytes = module_name.encode('ascii')

    if K32EnumProcessModules(process_handle, hModules, ctypes.sizeof(hModules), ctypes.byref(cbNeeded)):
        for i in range(cbNeeded.value // ctypes.sizeof(ctypes.wintypes.HMODULE)):
            module_path = ctypes.create_string_buffer(260)
            if K32GetModuleFileNameExA(process_handle, hModules[i], module_path, ctypes.sizeof(module_path)):
                if module_path.value.decode('ascii').lower().endswith(module_name.lower()):
                    return hModules[i]
    return None


def get_base_address(process_name, pid, process_handle, module_name):
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
    try:
        for f in psutil.Process(pid).memory_maps():
            yield f.path
    except psutil.NoSuchProcess:
        print(f"No process found with PID: {pid}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == '__main__':
    pass
    # print(get_file_from_pid(20040))
