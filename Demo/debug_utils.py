# debug_utils.py
import inspect
import sys


class RedirectText:
    """
    用以传送打印到窗口状态栏的类，将输出按结构化的方式分割处理，并保存所有输出。
    """

    def __init__(self, text_var, message_queue, debug):
        self.debug = debug
        self.text_var = text_var
        self.message_queue = message_queue
        self.original_stdout = sys.stdout  # 保存原始标准输出
        self.logs = []  # 用于保存结构化的输出

    def write(self, text):
        if self.debug:
            lines = text.splitlines()  # 分割成行
            # 去掉最后一行（可能为空或包含特殊符号）
            # 保存每行内容到 logs，注意需要排除结尾符号
            for line in lines:
                if len(line) > 0:
                    # 从你的工具中获取前缀、堆栈等结构化部分
                    stack_prefix = indent()  # 缩进前缀
                    call_stack = get_call_stack()  # 堆栈
                    output_prefix = indent()  # 输出前缀
                    output_content = line  # 实际输出内容

                    # 保存为字典
                    log_entry = {
                        'stack_prefix': stack_prefix,
                        'call_stack': call_stack,
                        'output_prefix': output_prefix,
                        'output_content': output_content
                    }

                    self.message_queue.put(output_content)  # 将原始内容放入队列
                    self.logs.append(log_entry)  # 保存结构化日志条目
        else:
            lines = text.splitlines()
            for line in lines:
                self.message_queue.put(line)  # 仅将内容放入队列

        # 继续在控制台输出
        if self.original_stdout:
            self.original_stdout.write(text)

    def flush(self):
        # 确保标准输出的缓冲区被清空
        self.original_stdout.flush()

    def get_logs(self):
        # 返回保存的日志
        return self.logs  # 返回结构化日志


def simplify_call_stack(text):
    # 需要掐头去尾处理的标识符
    prefixes_to_remove = ["callit/", "run/"]
    suffix_to_remove = "/write"

    # 处理掐头
    for prefix in prefixes_to_remove:
        if prefix in text:
            # 去除prefix及之前的内容
            text = text.split(prefix, 1)[-1]

    # 处理去尾
    if text.endswith(suffix_to_remove):
        # 去除后缀
        text = text[: -len(suffix_to_remove)]

    return text


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
    depth = min(max_depth, len(stack) - 1)  # 实际深度减去2层

    if depth <= 0:
        return ""  # 如果层数不足，返回空字符串

    # 按位生成缩进序列，超出部分循环
    indent_str = ''.join(sequence[i % len(sequence)] for i in range(depth))

    return indent_str
