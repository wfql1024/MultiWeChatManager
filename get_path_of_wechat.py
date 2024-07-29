import configparser
import os

import psutil


def get_wechat_path_from_ini():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ini_path = os.path.join(script_dir, 'path.ini').replace('\\', '/')
    if os.path.exists(ini_path):
        config = configparser.ConfigParser()
        config.read(ini_path)
        if 'WxMultiple' in config and 'WxPath' in config['WxMultiple']:
            wx_path = config['WxMultiple']['WxPath']
            if os.path.exists(wx_path):
                return wx_path
    return None


def save_wechat_path_to_ini(wx_path):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ini_path = os.path.join(script_dir, 'path.ini').replace('\\', '/')
    config = configparser.ConfigParser()
    if os.path.exists(ini_path):
        config.read(ini_path)
    if 'WxMultiple' not in config:
        config['WxMultiple'] = {}
    config['WxMultiple']['WxPath'] = wx_path
    with open(ini_path, 'w') as configfile:
        config.write(configfile)


def get_wechat_path_from_process():
    for process in psutil.process_iter(['name', 'exe']):
        if process.info['name'] == 'WeChat.exe':
            return process.info['exe'].replace('\\', '/')
    return None


def get_wechat_path():
    wechat_install_path = get_wechat_path_from_ini()

    if not wechat_install_path:
        wechat_install_path = os.path.join(os.environ.get('ProgramFiles(x86)'), 'Tencent', 'WeChat',
                                           'WeChat.exe').replace('\\', '/')
        if not os.path.exists(wechat_install_path):
            wechat_install_path = os.path.join(os.environ.get('ProgramFiles'), 'Tencent', 'WeChat',
                                               'WeChat.exe').replace('\\', '/')

        if not os.path.exists(wechat_install_path):
            wechat_install_path = get_wechat_path_from_process()

        if not wechat_install_path or not os.path.exists(wechat_install_path):
            return None

        save_wechat_path_to_ini(wechat_install_path)

    return wechat_install_path


if __name__ == "__main__":
    path = get_wechat_path()
    if path:
        print(f"微信安装路径: {path}")
    else:
        print("未能找到微信安装路径")
