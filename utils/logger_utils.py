# logger_utils.py
# 这个是很底层的工具类，不要导入项目其他的模块
import builtins
import functools
import inspect
import io
import logging
import os
import sys
import time
import traceback
from dataclasses import dataclass
from typing import Optional, Callable, Any, List, Tuple

import colorlog


@dataclass
class MethodCall:
    method_name: str
    start_time: float
    end_time: float
    depth: int


class PerformanceDebugger:
    """
    This is an advanced performance debugging tool that can help you track down the bottlenecks in your code.
    It can be used to measure the time taken by each method call and the time taken by each line of code.
    """

    def __init__(self, name: str = "Performance Testing", auto_break: bool = False):
        self.name = name
        self.auto_break = auto_break
        self.start_time: Optional[float] = None
        self.last_checkpoint: Optional[float] = None
        self.checkpoints: List[Tuple[str, float]] = []
        self.method_calls: List[MethodCall] = []
        self._current_method: Optional[MethodCall] = None
        self._base_depth: int = 0
        self._last_method_time: float = 0  # 新增：记录上一个方法的结束时间

    def start(self) -> None:
        """开始计时"""
        self.start_time = time.time()
        self.last_checkpoint = self.start_time
        self._last_method_time = self.start_time  # 初始化上一个方法的结束时间
        self.checkpoints = [("start", self.start_time)]
        self.method_calls = []
        self._current_method = None
        self._base_depth = len(inspect.stack())
        print(f"\n[{self.name}] start timing!")
        print("--------output--------")

    def checkpoint(self, name: Optional[str] = None) -> None:
        """记录检查点"""
        if self.start_time is None:
            raise RuntimeError("Please call the start() method first.")

        current_time = time.time()
        since_last = current_time - self.last_checkpoint
        since_start = current_time - self.start_time

        if name is None:
            frame = inspect.currentframe()
            if frame is not None:
                frame = frame.f_back
                if frame is not None:
                    name = f"行号 {frame.f_lineno}"

        self.checkpoints.append((name or "Unnamed checkpoint", current_time))
        self.last_checkpoint = current_time

        print(f"[{self.name}] {name}:")
        print(f"[{since_last:.4f}s/{since_start:.4f}s]")

    def end(self) -> None:
        """结束计时并打印总结"""
        if self.start_time is None:
            raise RuntimeError("Please call the start() method first.")

        total_time = time.time() - self.start_time
        print("--------result--------")

        if len(self.checkpoints) > 1:
            print("Manual checkpoints:")
            for i in range(1, len(self.checkpoints)):
                name, time_point = self.checkpoints[i]
                prev_name, prev_time = self.checkpoints[i - 1]
                since_last = time_point - prev_time
                since_start = time_point - self.start_time
                percentage = since_last / total_time * 100
                indent = ' ' if percentage < 10 else ''
                print(f"[{indent}{percentage:.1f}%/{since_last:.4f}s/{since_start:.4f}s] {prev_name} -> {name}")

        if self.auto_break and self.method_calls:
            print("Automatic breakpoints:")
            for call in self.method_calls:
                since_last = call.start_time - self._last_method_time
                since_start = call.start_time - self.start_time
                percentage = since_last / total_time * 100
                indent = ' ' if percentage < 10 else ''
                print(f"[{indent}{percentage:.1f}%/{since_last:.4f}s/{since_start:.4f}s] {call.method_name}")
                self._last_method_time = call.end_time

        print(f"Total: {total_time:.4f}秒")
        print("----------------------")
        print("Testing completed.\n")

        self.start_time = None
        self.last_checkpoint = None
        self.checkpoints = []
        self.method_calls = []
        self._current_method = None
        self._base_depth = 0
        self._last_method_time = 0

    @classmethod
    def measure_method(cls, name: Optional[str] = None, auto_break: bool = False):
        """装饰器：测量方法执行时间"""

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                debugger = cls(name or func.__name__, auto_break)
                debugger.start()

                if auto_break:
                    def method_wrapper(method):
                        def wrapped(*args, **kwargs):
                            current_depth = len(inspect.stack())
                            if current_depth > debugger._base_depth:
                                start_time = time.time()
                                current_method = MethodCall(
                                    method.__name__,
                                    start_time,
                                    start_time,
                                    current_depth
                                )
                                debugger._current_method = current_method
                                try:
                                    result = method(*args, **kwargs)
                                    return result
                                finally:
                                    if debugger._current_method is not None:
                                        debugger._current_method.end_time = time.time()
                                        debugger.method_calls.append(debugger._current_method)
                                        debugger._current_method = None
                            else:
                                return method(*args, **kwargs)

                        return wrapped

                    for attr_name in dir(args[0]):
                        if not attr_name.startswith('__'):
                            attr = getattr(args[0], attr_name)
                            if callable(attr):
                                setattr(args[0], attr_name, method_wrapper(attr))

                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    print(f"错误：方法执行失败: {str(e)}")
                    print("详细错误信息:")
                    traceback.print_exc()
                    raise
                finally:
                    debugger.end()

            return wrapper

        return decorator

    @classmethod
    def measure_block(cls, name: str, auto_break: bool = False):
        """上下文管理器：测量代码块执行时间"""
        return cls(name, auto_break)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end()


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


class Printer:
    _instance = None
    _initialized = False

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[96m"
    RESET = "\033[0m"

    BOLD = "\033[1m"
    NO_BOLD = "\033[22m"
    REVERSE = "\033[7m"
    NO_REVERSE = "\033[27m"

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if Printer._initialized is not True:
            # self.vital_msg = None
            # self.last_msg = None
            # self.normal_msg = None
            self.vital_msg = None  # 用于保存 Vital 级别的输出
            self.last_msg = None  # 用于存储最后一条消息
            self.normal_msg = None
            Printer._initialized = True

    def print_vn(self, obj=None):
        if obj is not None:
            self.normal(obj)
        vn_message = f"{self.vital_msg} | {self.normal_msg}" if self.vital_msg else f"{self.normal_msg}"
        print(vn_message)
        return vn_message

    def normal(self, obj):
        self.normal_msg = str(obj)
        return self

    def vital(self, obj):
        self.vital_msg = str(obj)
        return self

    def print_last(self, obj=None):
        if obj is not None:
            self.last(obj)
        print(self.last_msg)
        return self.last_msg

    def last(self, obj):
        self.last_msg = str(obj)
        return self

    def debug(self, *args, **kwargs):
        text = " ".join(str(arg) for arg in args)
        kwargs.setdefault("flush", True)
        builtins.print(f"{self.BOLD}{self.BLUE}Debug: {text}{self.RESET}", **kwargs)

    def cmd_in(self, *args, **kwargs):
        print(f"{self.GREEN}{self.BOLD}>", *args, f"{self.RESET}", **kwargs)

    def cmd_out(self, *args, **kwargs):
        print(f"{self.YELLOW}>", *args, f"{self.RESET}", **kwargs)


class Logger:
    _instance = None
    _initialized = False  # 类变量，标记是否初始化过

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, file=None):
        if Logger._initialized:
            return  # 已经初始化过，直接返回，避免重复初始化

        if file is None:
            app = os.path.basename(os.path.abspath(sys.argv[0]))
            file = app.split('.')[0] + '.log'
        self.logger = self._get_logger(file)

        Logger._initialized = True  # 标记初始化完成

    @staticmethod
    def _get_logger(file):
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

    def __getattr__(self, name):
        # 避免转发自身已有的属性或方法
        if name in self.__dict__ or hasattr(type(self), name):
            return self.__dict__[name] if name in self.__dict__ else getattr(type(self), name)
        return getattr(self.logger, name)


mylogger = Logger()
myprinter = Printer()

if __name__ == '__main__':
    pass
