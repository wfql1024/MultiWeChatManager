import ctypes

import psutil

import process_utils
from read_wechat_memory import read_wechat_config
from wechat_config import OFFSET, CURRENT_VERSION

kernel32 = ctypes.windll.kernel32
OpenProcess = kernel32.OpenProcess

PROCESS_ALL_ACCESS = 0x1F0FFF


def main():
    wechat_processes = process_utils.get_process_ids_by_name("WeChat.exe")
    for pid in wechat_processes:
        # 测试读取昵称
        nickname_config = OFFSET.get_config(CURRENT_VERSION, "NICKNAME")
        nickname = read_wechat_config(pid, nickname_config)
        print(f"读取的{nickname_config.alias}: {nickname}")

        # 测试读取手机类型
        phone_type_config = OFFSET.get_config(CURRENT_VERSION, "PHONE_TYPE")
        phone_type = read_wechat_config(pid, phone_type_config)
        print(f"读取的{phone_type_config.alias}: {phone_type}")

        # 测试读取手机号
        phone_config = OFFSET.get_config(CURRENT_VERSION, "PHONE_NUMBER")
        phone_number = read_wechat_config(pid, phone_config)
        print(f"读取的{phone_config.alias}: {phone_number}")


if __name__ == "__main__":
    main()
