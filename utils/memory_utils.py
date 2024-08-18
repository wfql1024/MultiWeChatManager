import ctypes

kernel32 = ctypes.windll.kernel32
ReadProcessMemory = kernel32.ReadProcessMemory
CloseHandle = kernel32.CloseHandle

# 定义常量
PROCESS_ALL_ACCESS = 0x1F0FFF


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
