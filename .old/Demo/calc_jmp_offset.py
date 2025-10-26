import pefile


class DLLPatcher:
    def __init__(self, mm, auto_close=False):
        self.pe = None
        self.image_base = 0x140000000  # DLL默认基址
        self.mm = mm
        self.auto_close = auto_close
        self.load_pe()  # 自动加载PE

    def load_pe(self):
        """从mmap加载PE文件"""
        try:
            self.pe = pefile.PE(data=self.mm, fast_load=True)
            # 使用实际的映像基址
            self.image_base = self.pe.OPTIONAL_HEADER.ImageBase
            print(f"映像基址: 0x{self.image_base:X}")
            return True
        except Exception as e:
            print(f"加载PE文件失败: {e}")
            return False

    def close(self):
        """关闭patcher，但不关闭mmap"""
        self.pe = None
        self.image_base = 0x140000000
        # 不关闭mmap，让调用者自己管理
        # self.mm = None  # 甚至可以保留mmap引用

    def __enter__(self):
        """上下文管理器支持"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器支持"""
        if self.auto_close:
            self.close()
        # 如果auto_close为False，即使使用with语句也不会自动关闭

    def foa_to_rva(self, foa):
        """将文件偏移地址转换为相对虚拟地址"""
        if not self.pe:
            return None

        # 遍历所有节区
        for section in self.pe.sections:
            section_start = section.PointerToRawData
            section_end = section.PointerToRawData + section.SizeOfRawData

            if section_start <= foa < section_end:
                # 在节区内：FOA -> RVA
                rva = foa - section.PointerToRawData + section.VirtualAddress
                print(f"FOA 0x{foa:X} -> 节区 '{section.Name.decode().strip()}' -> RVA 0x{rva:X}")
                return rva

        # 如果不在任何节区内，可能在PE头部
        if foa < self.pe.OPTIONAL_HEADER.SizeOfHeaders:
            print(f"FOA 0x{foa:X} -> PE头部 -> RVA 0x{foa:X}")
            return foa

        print(f"警告: FOA 0x{foa:X} 不在有效的PE范围内")
        return None

    def calculate_jump_offset(self, target_foa, patch_foa, instruction_offset):
        """计算跳转偏移量"""
        # 转换为RVA
        target_rva = self.foa_to_rva(target_foa)
        patch_rva = self.foa_to_rva(patch_foa)

        if target_rva is None or patch_rva is None:
            return None

        # 转换为虚拟地址
        target_voa = self.image_base + target_rva
        patch_voa = self.image_base + patch_rva

        print(f"目标VOA: 0x{target_voa:X}")
        print(f"补丁VOA: 0x{patch_voa:X}")

        # 计算偏移量
        offset_value = target_voa - (patch_voa + instruction_offset)
        print(
            f"偏移量计算: 0x{target_voa:X} - (0x{patch_voa:X} + {instruction_offset}) = {offset_value} (0x{offset_value & 0xFFFFFFFF:X})")
        return offset_value

        # # 转换为4字节小端序有符号整数
        # offset_bytes = offset_value.to_bytes(4, 'little', signed=True)
        # return offset_bytes
