import mmap
import os
import sys
from typing import Tuple

# 用法: 将两个文件拖到脚本上运行

# 差异前后各多显示多少字节
LEFT_CONTEXT = 64
RIGHT_CONTEXT = 96

LOW_LINE = "\u0332"  # ̲x 下划线
DOT_BELOW = "\u0323"  # x̣ 下点
DOT_ABOVE = "\u0307"  # ẋ 上点
MACRON = "\u0304"  # x̄ 上横线
OVERLINE = "\u0305"  # x̅ 顶线上横线（比 MACRON 高）
DOUBLE_MACRON = "\u035E"  # x͞ 双横线
TILDE = "\u0303"  # x̃ 上波浪线
CARON = "\u030C"  # x̌ 上尖帽
BREVE = "\u0306"  # x̆ 上短弧
CIRCUMFLEX = "\u0302"  # x̂ 上小帽子
GRAVE = "\u0300"  # x̀ 左上撇
ACUTE = "\u0301"  # x́ 右上撇
RING_ABOVE = "\u030A"  # x̊ 上圆圈
DOUBLE_VERTICAL_LINE_ABOVE = "\u030E"  # x̎ 上双竖线
VERTICAL_LINE_BELOW = "\u0329"  # x̩ 下竖线
SEAGULL_BELOW = "\u033C"  # x̼ 下海鸥线
DOUBLE_TILDE = "\u0360"  # x͠ 上双波浪

DIFF_TAG = LOW_LINE


def format_ascii_line(data: bytes, diff_indices: set) -> Tuple[str, str]:
    chars = []
    chars2 = []
    for i, byte in enumerate(data):
        c = chr(byte) if 32 <= byte <= 126 else '.'
        if i in diff_indices:
            chars.append(f" {DIFF_TAG + c}")
            chars2.append(f"{DIFF_TAG + c}")
        else:
            chars.append(f" {c}")
            chars2.append(f"{c}")

    res1 = " ".join(chars)
    res2 = "".join(chars2)
    return res1, res2


def format_bytes_line(data: bytes, diff_indices: set) -> str:
    hexes = []
    for i, byte in enumerate(data):
        hex_str = f"{byte:02X}"
        if i in diff_indices:
            hexes.append(''.join(DIFF_TAG + c for c in hex_str))
        else:
            hexes.append(hex_str)

    res = " ".join(hexes)
    return res


def compare_binary_files_optimized(file1: str, file2: str):
    if os.path.getsize(file1) != os.path.getsize(file2):
        return f"文件大小不同：{os.path.getsize(file1)} vs {os.path.getsize(file2)} 字节，无法对比。"

    with open(file1, "rb") as f1, open(file2, "rb") as f2:
        size = os.path.getsize(file1)
        mm1 = mmap.mmap(f1.fileno(), 0, access=mmap.ACCESS_READ)
        mm2 = mmap.mmap(f2.fileno(), 0, access=mmap.ACCESS_READ)

        i = 0
        while i < size:
            if mm1[i] != mm2[i]:
                range_start = max(i - LEFT_CONTEXT, 0)
                real_right = min(i + RIGHT_CONTEXT, size)
                tmp_right = min(real_right + LEFT_CONTEXT, size)

                # 初次检测范围内的差异
                diff_set = set()
                for j in range(range_start, real_right):
                    if mm1[j] != mm2[j]:
                        diff_set.add(j - range_start)

                # 检测右边扩展部分是否还有差异
                while tmp_right > real_right:
                    new_diff_found = False
                    for j in range(real_right, tmp_right):
                        if j >= size:
                            break
                        if mm1[j] != mm2[j]:
                            diff_set.add(j - range_start)
                            new_diff_found = True
                    if new_diff_found:
                        real_right = tmp_right
                        tmp_right = min(real_right + LEFT_CONTEXT, size)
                    else:
                        break

                data1 = mm1[range_start:real_right]
                data2 = mm2[range_start:real_right]

                print(f"## 区间={range_start:08X}~{real_right:08X}  长度={real_right - range_start}")

                hex_line1 = format_bytes_line(data1, diff_set)
                ascii_line1a, ascii_line1b = format_ascii_line(data1, diff_set)
                print(f"### {file1}:\n{hex_line1}\n{ascii_line1a}\n{ascii_line1b}")

                hex_line2 = format_bytes_line(data2, diff_set)
                ascii_line2a, ascii_line2b = format_ascii_line(data2, diff_set)
                print(f"### {file2}:\n{hex_line2}\n{ascii_line2a}\n{ascii_line2b}")

                print("\n")

                i = real_right  # 从新范围的右边界继续扫描
            else:
                i += 1

        mm1.close()
        mm2.close()
        return None


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
