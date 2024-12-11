import configparser
import os

from utils import logger_utils

logger = logger_utils.mylogger


def get_setting_from_ini(ini_filename, section, key, default_value=None, validation_func=None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ini_path = os.path.join(script_dir, ini_filename).replace('\\', '/')
    if os.path.exists(ini_path):
        config = configparser.ConfigParser()
        config.read(ini_path)
        if section in config and key in config[section]:
            current_setting = config[section][key]
            if validation_func is None or validation_func(current_setting):
                # logger.info(f"读取{os.path.basename(ini_filename)}[{section}]{key} ====== {current_setting}")
                return current_setting
            if current_setting is None:
                return default_value
    return None


def save_setting_to_ini(ini_path, section, key, value):
    ini_path = ini_path.replace('\\', '/')
    config = configparser.ConfigParser()

    # 先确保目录存在，如果不存在则创建
    ini_dir = os.path.dirname(ini_path)
    if not os.path.exists(ini_dir):
        os.makedirs(ini_dir, exist_ok=True)  # 创建文件夹
        logger.warning(f"文件夹不存在，已创建: {ini_dir}")

    # 确保目录存在后再读取文件
    if os.path.exists(ini_path):
        files_read = config.read(ini_path)
        if not files_read:
            logger.warning(f"Unable to read {ini_path}")

    # 检查 section 是否存在
    if section not in config:
        config[section] = {}

    config[section][key] = str(value)

    # 写入配置文件
    try:
        with open(ini_path, 'w') as configfile:
            config.write(configfile)
            # logger.info(f"写入{value} -----> {os.path.basename(ini_path)}[{section}]{key}")
    except IOError as e:
        logger.error(f"Failed to write to {ini_path}: {e}")
