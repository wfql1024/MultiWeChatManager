import mmap


def modify_wechat_dll(file_path):
    # 第一种替换操作
    search_pattern_1 = b'\x3D\xB7\x00\x00\x00\x0F\x85'
    replace_pattern_prefix_1 = b'\xE9'

    # 第二种替换操作
    search_pattern_2 = b'\x0F\x84\xBD\x00\x00\x00\xFF\x15\xF4\x24\x65\x01'
    replace_pattern_2 = b'\xE9\xBE\x00\x00\x00\x00\xFF\x15\xF4\x24\x65\x01'

    with open(file_path, 'r+b') as f:
        # 使用mmap来读写文件内容
        mmapped_file = mmap.mmap(f.fileno(), 0)

        # 执行第一种替换操作
        pos = mmapped_file.find(search_pattern_1)
        if pos != -1:
            wx = mmapped_file[pos + 7]
            yz = mmapped_file[pos + 8]
            new_wx = (wx + 1) % 256
            replace_pattern_1 = replace_pattern_prefix_1 + bytes([new_wx, yz, 0x00])
            mmapped_file[pos + 6:pos + 9] = replace_pattern_1
            print("第一种替换操作完成")
        else:
            print("未找到第一种HEX模式")

        # 执行第二种替换操作
        pos = mmapped_file.find(search_pattern_2)
        if pos != -1:
            mmapped_file[pos:pos + len(search_pattern_2)] = replace_pattern_2
            print("第二种替换操作完成")
        else:
            print("未找到第二种HEX模式")

        # 保存修改
        mmapped_file.flush()
        mmapped_file.close()

    print("所有操作完成")


# 使用这个函数来修改WeChatWin.dll文件
dll_path = r'D:\software\Tencent\WeChat\[3.9.11.25]\WeChatWin.dll'  # 使用r''原始字符串表示法
modify_wechat_dll(dll_path)
