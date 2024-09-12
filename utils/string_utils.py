def balanced_wrap_text(text, max_width):
    """
    将文本按指定宽度换行，并且对超过这个长度的进行平分两行处理，两行长度尽量相等
    :param text: 要处理的文本
    :param max_width: 每行最大字符数
    :return: 处理后的文本
    """
    wrapped_text = ""

    # 对每一段进行处理
    while len(text) > max_width:
        # 获取超过 max_width 的段落
        segment = text[:max_width]
        text = text[max_width:]

        # 计算分割点，平分成两行
        middle = (len(segment) + 1) // 2
        wrapped_text += segment[:middle] + "\n" + segment[middle:] + "\n"

    # 对剩余不足 max_width 的部分直接输出
    if len(text) > 0:
        wrapped_text += text

    return wrapped_text.strip()  # 移除最后的换行符
