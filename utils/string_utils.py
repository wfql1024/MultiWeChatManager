def clean_display_name(display_name):
    """
    清理 display_name 中的字符，替换所有 Unicode 码点 > U+FFFF 的字符为 '_'
    并记录其位置和码点。

    Args:
        display_name (str): 原始显示名称字符串。

    Returns:
        str: 清理后的字符串。
    """
    new_display_name = []
    for index, char in enumerate(display_name):
        code_point = ord(char)
        if code_point > 0xFFFF:
            print(f"警告: 在位置 {index} 发现不支持的字符 '{char}' (U+{code_point:04X})，已替换为 '_'")
            new_display_name.append('_')
        else:
            new_display_name.append(char)
    return ''.join(new_display_name)


def balanced_wrap_text(text, max_width=10) -> str:
    """
    将文本按指定宽度尽量平分两行处理，超过 max_width 的部分尽量让上行更长。
    :param text: 要处理的文本
    :param max_width: 每行最大字符数
    :return: 处理后的文本
    """
    # 如果文本长度小于等于 max_width，直接返回文本
    if len(text) <= max_width:
        return text

    # 计算平分点，使得上行尽量更长
    middle = (len(text) + 1) // 2

    # 将文本平分为两行
    return text[:middle] + "\n" + text[middle:]


if __name__ == '__main__':
    print(balanced_wrap_text("a"))
    print(balanced_wrap_text("ab"))
    print(balanced_wrap_text("abc"))
    print(balanced_wrap_text("abcd"))
    print(balanced_wrap_text("abcde"))
    print(balanced_wrap_text("abcdef"))
    print(balanced_wrap_text("abcdefg"))
    print(balanced_wrap_text("abcdefgh"))
    print(balanced_wrap_text("abcdefghi"))
    print(balanced_wrap_text("abcdefghij"))
    print(balanced_wrap_text("abcdefghijk"))
    print(balanced_wrap_text("abcdefghijkl"))
    print(balanced_wrap_text("abcdefghijklm"))
    print(balanced_wrap_text("abcdefghijklmn"))
    print(balanced_wrap_text("abcdefghijklmno"))
    print(balanced_wrap_text("abcdefghijklmnop"))
    print(balanced_wrap_text("abcdefghijklmnopq"))
    print(balanced_wrap_text("abcdefghijklmnopqr"))
    print(balanced_wrap_text("abcdefghijklmnopqrs"))
    print(balanced_wrap_text("abcdefghijklmnopqrst"))
