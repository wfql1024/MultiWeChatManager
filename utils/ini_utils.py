import configparser
import os


def get_setting_from_ini(ini_filename, section, key, validation_func=None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ini_path = os.path.join(script_dir, ini_filename).replace('\\', '/')
    if os.path.exists(ini_path):
        config = configparser.ConfigParser()
        config.read(ini_path)
        if section in config and key in config[section]:
            current_setting = config[section][key]
            if validation_func is None or validation_func(current_setting):
                # print(f"{debug_utils.get_call_stack(10)}↓")
                print(f"┌———读取{os.path.basename(ini_filename)}[{section}]{key} ====== {current_setting}")
                return current_setting
    return None


def save_setting_to_ini(ini_path, section, key, value):
    ini_path = ini_path.replace('\\', '/')
    config = configparser.ConfigParser()

    # 先确保目录存在，如果不存在则创建
    ini_dir = os.path.dirname(ini_path)
    if not os.path.exists(ini_dir):
        os.makedirs(ini_dir, exist_ok=True)  # 创建文件夹
        print(f"已创建文件夹: {ini_dir}")

    # 确保目录存在后再读取文件
    if os.path.exists(ini_path):
        files_read = config.read(ini_path)
        if not files_read:
            print(f"Warning: Unable to read {ini_path}")

    # 检查 section 是否存在
    if section not in config:
        config[section] = {}

    config[section][key] = value

    # 写入配置文件
    try:
        with open(ini_path, 'w') as configfile:
            config.write(configfile)
            print(f"└———写入{value} -----> {os.path.basename(ini_path)}[{section}]{key}")
    except IOError as e:
        print(f"Failed to write to {ini_path}: {e}")