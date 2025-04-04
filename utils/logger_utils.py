# logger_utils.py
# 这个是很底层的工具类，不要导入项目其他的模块
import inspect
import io
import logging
import os
import sys

import colorlog


class DebugUtils:
    def __init__(self):
        pass

    @staticmethod
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

    @staticmethod
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

        # 从前往后连接方法名
        return sequence.join(reversed(call_chain))

    @staticmethod
    def get_call_stack_indent(sequence="··· ", max_depth=100):
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


class RedirectText(io.TextIOBase):
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
        lines = text.splitlines()  # 分割成行
        for line in lines:
            if self.debug:
                # 去掉最后一行（可能为空或包含特殊符号）
                # 保存每行内容到 logs，注意需要排除结尾符号
                if len(line) > 0:
                    # 从你的工具中获取前缀、堆栈等结构化部分
                    stack_prefix = DebugUtils.get_call_stack_indent()  # 缩进前缀
                    call_stack = DebugUtils.get_call_stack()  # 堆栈
                    output_prefix = DebugUtils.get_call_stack_indent()  # 输出前缀
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
                self.message_queue.put(line)  # 仅将内容放入队列

        # 继续在控制台输出
        if self.original_stdout:
            self.original_stdout.write(text)

    def flush(self):
        """确保标准输出的缓冲区被清空"""
        if self.original_stdout:
            self.original_stdout.flush()

    @property
    def writable(self):
        """告知 Python 这个流是可写的"""
        return True

    @property
    def encoding(self):
        """返回 stdout 的编码，确保兼容性"""
        return getattr(self.original_stdout, "encoding", "utf-8")

    def get_logs(self):
        """返回保存的日志"""
        return self.logs  # 返回结构化日志


class PrinterUtils:
    def __init__(self):
        self.vital_message = None  # 用于保存 Vital 级别的输出

    def normal(self, obj):
        print(f"{self.vital_message} | {str(obj)}" if self.vital_message else str(obj))

    def vital(self, obj):
        self.vital_message = str(obj)


class LoggerUtils:
    def __init__(self, file):
        self.logger = self.get_logger(file)

    @staticmethod
    def get_logger(file):
        # 定log输出格式，配置同时输出到标准输出与log文件，返回logger这个对象
        log_colors_config = {
            # 终端输出日志颜色配置
            'DEBUG': 'white',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
        default_formats = {
            # 终端输出格式
            'color_format':
                f'%(log_color)s%(levelname)s - %(asctime)s - %(filename)s[line:%(lineno)d][%(funcName)s] - %(message)s',
            # 日志输出格式
            'log_format': '%(levelname)s - %(asctime)s - %(filename)s[line:%(lineno)d][%(funcName)s] - %(message)s'
        }

        logger = logging.getLogger('mylogger')
        logger.setLevel(logging.DEBUG)
        fh_log_format = logging.Formatter(default_formats["log_format"])
        ch_log_format = colorlog.ColoredFormatter(default_formats["color_format"], log_colors=log_colors_config)

        # 创建文件处理器
        log_fh = logging.FileHandler(file)
        log_fh.setLevel(logging.DEBUG)
        log_fh.setFormatter(fh_log_format)
        logger.addHandler(log_fh)
        # 创建控制台处理器
        log_ch = logging.StreamHandler()
        log_ch.setFormatter(ch_log_format)
        log_ch.setLevel(logging.DEBUG)
        logger.addHandler(log_ch)

        return logger


app_path = os.path.basename(os.path.abspath(sys.argv[0]))
log_file = app_path.split('.')[0] + '.log'
mylogger = LoggerUtils.get_logger(log_file)
myprinter = PrinterUtils()

if __name__ == '__main__':
    pass
