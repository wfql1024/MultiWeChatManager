import sys
import os
import mmap

# 用法: 将两个文件拖到脚本上运行

# 差异前后各多显示多少字节
LEFT_CONTEXT = 32
RIGHT_CONTEXT = 120


def format_ascii_line(data: bytes, diff_indices: set) -> str:
    chars = []
    for i, byte in enumerate(data):
        c = chr(byte) if 32 <= byte <= 126 else '.'
        if i in diff_indices:
            chars.append(f"({c})")
        else:
            chars.append(c)
    # 连续括号不用合并，保持一一对应
    return ''.join(chars)



def format_bytes_line(data: bytes, diff_indices: set, group_size: int = 64) -> str:
    hexes = []
    for i, byte in enumerate(data):
        hex_str = f"{byte:02X}"
        if i in diff_indices:
            hexes.append(f"({hex_str})")
        else:
            hexes.append(hex_str)

    # 连续括号合并成一个
    result = " ".join(hexes)
    while ") (" in result:
        result = result.replace(") (", " ")

    return result


def compare_binary_files_optimized(file1: str, file2: str):
    if os.path.getsize(file1) != os.path.getsize(file2):
        return f"文件大小不同：{os.path.getsize(file1)} vs {os.path.getsize(file2)} 字节，无法对比。"

    result = []
    with open(file1, "rb") as f1, open(file2, "rb") as f2:
        size = os.path.getsize(file1)
        mm1 = mmap.mmap(f1.fileno(), 0, access=mmap.ACCESS_READ)
        mm2 = mmap.mmap(f2.fileno(), 0, access=mmap.ACCESS_READ)

        i = 0
        while i < size:
                if mm1[i] != mm2[i]:
                        range_start = max(i - LEFT_CONTEXT, 0)
                        diff_set = set()
                        j = i
                        while j < size and j < i + RIGHT_CONTEXT :
                                if mm1[j] != mm2[j]:
                                        diff_set.add(j - range_start)
                                j += 1
                        range_end = j

                        data1 = mm1[range_start:range_end]
                        data2 = mm2[range_start:range_end]

                        print(f"{range_start:08X}~{range_end:08X}")

                        hex_line1 = format_bytes_line(data1, diff_set)
                        ascii_line1 = format_ascii_line(data1, diff_set)
                        print(f"{file1}:\n{hex_line1}\n{ascii_line1}")

                        hex_line2 = format_bytes_line(data2, diff_set)
                        ascii_line2 = format_ascii_line(data2, diff_set)
                        print(f"{file2}:\n{hex_line2}\n{ascii_line2}")

                        print("=====================================")

                        i = range_end
                else:
                        i += 1




        mm1.close()
        mm2.close()




if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("请将两个文件一起拖到脚本上运行")
        input("按任意键退出...")
        sys.exit(1)

    file1, file2 = sys.argv[1], sys.argv[2]
    print(f"正在对比：\n{file1}\n{file2}\n")
    result = compare_binary_files_optimized(file1, file2)
    input("\n对比完成，按任意键退出...")
    input("....")
