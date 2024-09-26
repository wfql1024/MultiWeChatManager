import functools
import logging
import sys
from io import StringIO

# 配置日志系统
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PrintToLogger:
    def __init__(self, logger):
        self.logger = logger

    def write(self, message):
        if message.strip():  # 忽略空白行
            self.logger.info(message.strip())

    def flush(self):
        pass


def log_prints(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # 保存原始的 stdout
        original_stdout = sys.stdout
        # 创建一个 StringIO 对象来捕获输出
        string_io = StringIO()
        # 创建一个 PrintToLogger 对象
        print_to_logger = PrintToLogger(logger)

        try:
            # 重定向 stdout 到我们的 PrintToLogger 对象
            sys.stdout = print_to_logger
            # 执行原始函数
            return func(*args, **kwargs)
        finally:
            # 恢复原始的 stdout
            sys.stdout = original_stdout

    return wrapper


def get_logger(file):
    # 定log输出格式，配置同时输出到标准输出与log文件，返回logger这个对象
    logger = logging.getLogger('mylogger')
    logger.setLevel(logging.DEBUG)
    log_format = logging.Formatter('%(asctime)s - %(filename)s - %(levelname)s - %(message)s')

    # 创建文件处理器
    log_fh = logging.FileHandler(file)
    log_fh.setLevel(logging.DEBUG)
    log_fh.setFormatter(log_format)
    logger.addHandler(log_fh)

    # 创建控制台处理器，检查是否已添加
    if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        log_ch = logging.StreamHandler()
        log_ch.setLevel(logging.DEBUG)
        log_ch.setFormatter(log_format)
        logger.addHandler(log_ch)

    return logger


class LoggerUtils:
    def __init__(self, file):
        self.logger = get_logger(file)


# 使用示例
@log_prints
def my_function():
    print("This is a test message")
    print("Another test message")
