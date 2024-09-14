# debug_utils.py
import inspect


def get_call_stack(sequence="/", max_depth=100):
    """
    获取调用栈，并返回当前方法及往前回溯指定层数的方法名称，按顺序用连接符连接。
    :param sequence: 连接符
    :param max_depth: 回溯的层数
    :return: 调用栈字符串，从前往后按连接符连接的方法名。
    """
    # 获取当前的调用栈
    stack = inspect.stack()

    # 从调用方开始，跳过 get_call_stack 本身，回溯至多 max_depth 层
    call_chain = [frame_info.function for frame_info in stack[1:max_depth + 1]]

    # 从前往后，用 '->' 连接方法名
    return sequence.join(reversed(call_chain))


def indent(sequence="··· ", max_depth=100):
    """
    根据调用栈的深度返回缩进字符串，使用自定义的序列循环输出。
    :param sequence: 自定义序列，缩进按照该序列输出并循环。
    :param max_depth: 最大回溯层数，默认值为 100 层。
    :return: 生成的缩进字符串，基于调用栈深度并减去 2 层。
    """
    # 获取当前的调用栈
    stack = inspect.stack()

    # 计算缩进层数，最少为 1 层，最多不超过实际栈深度减去2
    depth = min(max_depth, len(stack) - 3)  # 实际深度减去2层

    if depth <= 0:
        return ""  # 如果层数不足，返回空字符串

    # 按位生成缩进序列，超出部分循环
    indent_str = ''.join(sequence[i % len(sequence)] for i in range(depth))

    return indent_str
