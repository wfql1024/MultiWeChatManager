#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calc_imm.py
从 Rust 逻辑翻译的偏移量计算工具。
可计算 x64 指令（如 LEA RIP+imm32 或 CALL rel32）的跳转偏移。
"""

import argparse
import struct
import sys
# calc_imm_mmap.py
import mmap
import re

# ========== 基础计算逻辑 ==========

def calculate_jump_offset(current_addr: int, target_addr: int, offset_adjust: int) -> int:
    """
    对应 Rust 中的 calculate_jump_offset
    current_addr: 当前指令地址 (LEA/CALL 起始地址)
    target_addr: 目标地址 (要跳转/引用的数据)
    offset_adjust: 指令长度，如 LEA 为7、CALL 为5
    """
    next_instr_addr = current_addr + offset_adjust
    raw_offset = target_addr - next_instr_addr

    # 转为有符号 32 位整数
    if raw_offset < -0x80000000 or raw_offset > 0x7FFFFFFF:
        raise ValueError("Offset out of range for int32")
    return raw_offset


def jump_offset_to_bytes(raw_offset: int) -> bytes:
    """
    对应 Rust 中的 calculate_jump_offset_bytes
    """
    if -0x80 <= raw_offset <= 0x7F:
        return struct.pack("<b", raw_offset)
    else:
        return struct.pack("<i", raw_offset)


# ========== 可选：PE 文件偏移转换功能 ==========
try:
    import pefile
except ImportError:
    pefile = None


def file_offset_to_va(pe_path: str, file_offset: int) -> int:
    """从文件偏移算出 VA"""
    if pefile is None:
        raise ImportError("需要安装 pefile: pip install pefile")
    pe = pefile.PE(pe_path)
    for section in pe.sections:
        start = section.PointerToRawData
        end = start + section.SizeOfRawData
        if start <= file_offset < end:
            va = pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress + (file_offset - start)
            return va
    raise ValueError("无法在节表中找到匹配的 file_offset")


def va_to_file_offset(pe_path: str, va: int) -> int:
    """从 VA 算出文件偏移"""
    if pefile is None:
        raise ImportError("需要安装 pefile: pip install pefile")
    pe = pefile.PE(pe_path)
    rva = va - pe.OPTIONAL_HEADER.ImageBase
    for section in pe.sections:
        start = section.VirtualAddress
        end = start + section.Misc_VirtualSize
        if start <= rva < end:
            offset = section.PointerToRawData + (rva - start)
            return offset
    raise ValueError("无法在节表中找到匹配的 VA")




def get_hex_index_by_str(text: str, pattern: str) -> int:
    """找到变量在 hex 模板字符串中的偏移（字节单位）"""
    match = re.search(re.escape(pattern), text)
    if not match:
        raise ValueError(f"未找到变量 {pattern}")
    return match.start() // 2  # 每字节两位hex


def calculate_jump_offset_bytes(current_off: int, target_off: int, offset_adjust: int = 0, length: int = 4) -> bytes:
    """
    计算相对跳转偏移
    current_off: 当前指令在 mmap 内部的偏移
    target_off: 目标地址在 mmap 内部的偏移
    offset_adjust: 通常是当前指令长度
    length: 偏移长度（1 或 4）
    """
    next_instr = current_off + offset_adjust
    rel = target_off - next_instr
    if length == 1:
        if not (-128 <= rel <= 127):
            raise ValueError("超出短跳范围")
        return struct.pack("<b", rel)
    elif length == 4:
        if not (-0x80000000 <= rel <= 0x7FFFFFFF):
            raise ValueError("超出长跳范围")
        return struct.pack("<i", rel)
    else:
        raise ValueError("不支持的跳转长度")


def calc_offset_from_mmap(mmap_obj: mmap.mmap,
                          current_off: int,
                          target_off: int,
                          pattern_arg: str,
                          var_pattern: str,
                          hex_template: str,
                          length: int = 4) -> bytes:
    """
    模拟 Rust 的 substitute_add 逻辑（mmap版）
    current_off, target_off 是 mmap 内的偏移
    hex_template: 替换模板（含 $[...] 占位）
    """
    if pattern_arg == "?":
        index = get_hex_index_by_str(hex_template, var_pattern)
        current_adjust, target_adjust = index + length, 0
    elif "," in pattern_arg:
        offsets = pattern_arg.split(",")
        if offsets[0] == "?":
            index = get_hex_index_by_str(hex_template, var_pattern)
            current_adjust = index + length
            target_adjust = int(offsets[1], 0)
        else:
            current_adjust = int(offsets[0], 0)
            target_adjust = int(offsets[1], 0)
    else:
        current_adjust, target_adjust = int(pattern_arg, 0), 0

    return calculate_jump_offset_bytes(
        current_off + current_adjust,
        target_off + target_adjust,
        0,
        length
    )


# === 示例用法 ===
if __name__ == "__main__":
    # 模拟打开一个文件映射
    # fake_bin = bytearray(b"\xE8\x00\x00\x00\x00" + b"\x90"*100)  # call + nop区域
    file = r"E:\Now\Desktop\[4.1.2.17]Weixin.dll"
    with open(file, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    # with mmap.mmap(-1, len(fake_bin)) as mm:
    #     mm.write(fake_bin)
    #     mm.seek(0)

        # 模拟模板
        hex_template = "488D15$[target|?|?]000000"
        var_pattern = "$[target|?|?]"

        # 当前 call 在偏移 0
        current_off = 30589040
        # 假设目标函数在文件偏移 0x120
        target_off = 0x08A077C9

        patch_bytes = calc_offset_from_mmap(mm, current_off, target_off, "?", var_pattern, hex_template, 4)
        print("计算结果:", patch_bytes.hex().upper())
        # 输出示例：E8 FB FF FF FF （如果是负偏移）


# ========== 主入口 ==========

def main():
    parser = argparse.ArgumentParser(description="计算 x64 指令跳转偏移 (LEA/CALL)")
    parser.add_argument("--current", type=lambda x: int(x, 0), help="当前指令地址 (VA)")
    parser.add_argument("--target", type=lambda x: int(x, 0), help="目标地址 (VA)")
    parser.add_argument("--adjust", type=int, default=7, help="指令长度 (默认 7)")
    parser.add_argument("--pe", type=str, help="PE 文件路径 (可选)")
    parser.add_argument("--file-offset-target", type=lambda x: int(x, 0),
                        help="目标文件偏移 (需配合 --pe 使用)")
    parser.add_argument("--example", action="store_true", help="运行示例测试")
    args = parser.parse_args()

    if args.example:
        # 模拟 Rust 测试用例
        current = 0x00007FFB7FD99D4B + 8 + 5
        target = 0x00007FFB7FD99BFF
        print(f"示例: current={hex(current)}, target={hex(target)}, adjust=0")
        offset = calculate_jump_offset(current, target, 0)
        print("Raw offset:", offset)
        print("Bytes:", jump_offset_to_bytes(offset).hex(" ").upper())
        return

    if not args.current:
        print("错误: 必须提供 --current")
        sys.exit(1)

    # 如果指定了 pe + file-offset-target，则自动换算 VA
    if args.pe and args.file_offset_target is not None:
        target_va = file_offset_to_va(args.pe, args.file_offset_target)
        print(f"目标 file_offset {hex(args.file_offset_target)} => VA = {hex(target_va)}")
    elif args.target:
        target_va = args.target
    else:
        print("错误: 必须提供 --target 或 --pe + --file-offset-target")
        sys.exit(1)

    offset = calculate_jump_offset(args.current, target_va, args.adjust)
    imm_bytes = jump_offset_to_bytes(offset)

    print(f"当前指令地址: {hex(args.current)}")
    print(f"目标地址: {hex(target_va)}")
    print(f"偏移调整值: {args.adjust}")
    print(f"计算结果: raw_offset = {offset} (0x{offset & 0xFFFFFFFF:08X})")
    print("写入字节 (小端序):", imm_bytes.hex(" ").upper())




# if __name__ == "__main__":
#     main()
