# logger_utils.py
# 这个是很底层的工具类，不要导入项目其他的模块
import inspect
import logging
import os
import queue
import sys

import colorlog


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
