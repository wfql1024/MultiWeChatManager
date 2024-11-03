import sys
import logging
import os
import colorlog


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
                '%(log_color)s%(levelname)s - %(asctime)s - %(filename)s[line:%(lineno)d] - %(message)s',
            # 日志输出格式
            'log_format': '%(levelname)s - %(asctime)s - %(filename)s[line:%(lineno)d] - %(message)s'
        }

        logger = logging.getLogger('mylogger')
        logger.setLevel(logging.DEBUG)
        fh_log_format = logging.Formatter(default_formats["log_format"])
        ch_log_format = colorlog.ColoredFormatter(default_formats["color_format"], log_colors=log_colors_config)

        # 创建文件处理器
        log_fh = logging.FileHandler(file, encoding='utf-8')
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

if __name__ == '__main__':
    pass
