# debug_utils.py
import inspect


def get_call_stack(max_depth=2):
    """
    获取调用栈，并返回当前方法及往前回溯指定层数的方法名称，按顺序用 '->' 连接。
    :param max_depth: 回溯的层数，默认为 2 层。
    :return: 调用栈字符串，从前往后按 '->' 连接的方法名。
    """
    # 获取当前的调用栈
    stack = inspect.stack()

    # 从调用方开始，跳过 get_call_stack 本身，回溯至多 max_depth 层
    call_chain = [frame_info.function for frame_info in stack[1:max_depth + 1]]

    # 从前往后，用 '->' 连接方法名
    return ' -> '.join(reversed(call_chain))
