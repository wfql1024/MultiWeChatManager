import ctypes
import ctypes.wintypes
import struct

import process_utils
from memory_utils import read_memory_until_null, read_memory
from process_utils import get_base_address

# 加载必要的Windows API
kernel32 = ctypes.windll.kernel32
ReadProcessMemory = kernel32.ReadProcessMemory
CloseHandle = kernel32.CloseHandle

# 定义常量
PROCESS_ALL_ACCESS = 0x1F0FFF


def read_wechat_memory(pid, offset, size, data_type):
    process_handle = process_utils.get_process_handle(pid)
    base_address = get_base_address("WeChat", pid, process_handle, "WeChatWin.dll")
    print(f"获取到基址：{hex(base_address)}")
    if not base_address:
        return None

    process_handle = process_utils.get_process_handle(pid)
    if not process_handle:
        print("无法打开WeChat.exe进程")
        return None

    try:
        actual_address = base_address + offset
        print(f"使用偏移{hex(offset)}得到地址：{hex(actual_address)}")
        if size == 0:
            data = read_memory_until_null(process_handle, actual_address)
        else:
            data = read_memory(process_handle, actual_address, size)

        if data_type == 'string':
            data = data.split(b'\x00')[0]  # 分割字符串，获取第一个非空部分
            return data.decode('utf-8', errors='ignore').strip()
        elif data_type == 'int':
            return int.from_bytes(data, byteorder='little')
        elif data_type == 'double':
            return struct.unpack('d', data)[0]
        elif data_type == 'float':
            return struct.unpack('f', data)[0]
        elif data_type == 'bool':
            return bool(int.from_bytes(data, byteorder='little'))
        elif data_type == 'long':
            return int.from_bytes(data, byteorder='little')
        elif data_type == 'ascii_number':
            return int(data.decode('ascii'))
        else:
            return data  # 返回原始字节数据
    except Exception as e:
        print(f"读取内存时发生错误: {e}")
        return None
    finally:
        CloseHandle(process_handle)


def read_wechat_config(pid, config):
    print("进入通过配置读取微信数据")
    print(pid)
    return read_wechat_memory(pid, config.offset, config.size, config.data_type)


def read_wechat_string(pid, offset, size):
    return read_wechat_memory(pid, offset, size, 'string')


def read_wechat_int(pid, offset):
    return read_wechat_memory(pid, offset, 4, 'int')


def read_wechat_double(pid, offset):
    return read_wechat_memory(pid, offset, 8, 'double')


def read_wechat_float(pid, offset):
    return read_wechat_memory(pid, offset, 4, 'float')


def read_wechat_bool(pid, offset):
    return read_wechat_memory(pid, offset, 1, 'bool')


def read_wechat_long(pid, offset):
    return read_wechat_memory(pid, offset, 8, 'long')


def read_wechat_ascii_number(pid, offset, size):
    return read_wechat_memory(pid, offset, size, 'ascii_number')
