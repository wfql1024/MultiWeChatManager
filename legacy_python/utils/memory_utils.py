import ctypes
from ctypes import wintypes

kernel32 = ctypes.windll.kernel32
ReadProcessMemory = kernel32.ReadProcessMemory
CloseHandle = kernel32.CloseHandle

# 定义常量
PROCESS_ALL_ACCESS = 0x1F0FFF

K32EnumProcessModules = kernel32.K32EnumProcessModules
K32GetModuleFileNameExA = kernel32.K32GetModuleFileNameExA

# 设置函数参数和返回类型
K32EnumProcessModules.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE),
                                  wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
K32EnumProcessModules.restype = wintypes.BOOL

K32GetModuleFileNameExA.argtypes = [wintypes.HANDLE, wintypes.HMODULE, ctypes.POINTER(ctypes.c_char),
                                    wintypes.DWORD]
K32GetModuleFileNameExA.restype = wintypes.DWORD


def get_module_base_address(process_handle, module_name):
    """
    获取指定模块（DLL）在目标进程中的基址
    :param process_handle: 句柄
    :param module_name: 模块名（如dll）
    :return: 基址
    """
    h_modules = (wintypes.HMODULE * 1024)()
    cb_needed = wintypes.DWORD()
    module_name_bytes = module_name.encode('ascii')

    if K32EnumProcessModules(process_handle, h_modules, ctypes.sizeof(h_modules), ctypes.byref(cb_needed)):
        for i in range(cb_needed.value // ctypes.sizeof(wintypes.HMODULE)):
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


def read_memory(process_handle, address, buffer_size):
    """从指定地址读取内存"""
    buffer = ctypes.create_string_buffer(buffer_size)
    bytes_read = ctypes.c_size_t()
    if not ReadProcessMemory(process_handle, ctypes.c_void_p(address), buffer, buffer_size, ctypes.byref(bytes_read)):
        raise ctypes.WinError()
    if bytes_read.value != buffer_size:
        raise ValueError(f"读取的字节数 ({bytes_read.value}) 不等于请求的字节数 ({buffer_size})")
    return buffer.raw


def read_memory_until_null(process_handle, address):
    """读取内存直到遇到连续的空字符"""
    buffer_size = 8  # 每次读取的块大小
    data = b""
    while True:
        buffer = ctypes.create_string_buffer(buffer_size)
        bytes_read = ctypes.c_size_t()
        if not ReadProcessMemory(process_handle, ctypes.c_void_p(address), buffer, buffer_size,
                                 ctypes.byref(bytes_read)):
            raise ctypes.WinError()
        if bytes_read.value == 0:
            break
        data += buffer.raw[:bytes_read.value]
        address += bytes_read.value
        if b"\x00" * buffer_size in buffer.raw[:bytes_read.value]:
            break
    return data
