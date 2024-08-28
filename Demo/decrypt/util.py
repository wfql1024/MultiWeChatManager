import ctypes
import hashlib
import hmac
import logging
import os
import sys
from pathlib import Path

app_path = os.path.dirname(os.path.abspath(sys.argv[0]))
IV_SIZE = 16
HMAC_SHA1_SIZE = 20
KEY_SIZE = 32
DEFAULT_PAGESIZE = 4096
DEFAULT_ITER = 64000


def check_sqlite_pass(db_file, password):
    db_file = Path(db_file)
    if type(password) == str:  # 要是类型是string的，就转bytes
        password = bytes.fromhex(password.replace(' ', ''))
    with open(db_file, 'rb') as (f):
        salt = f.read(16)  # 开头的16字节做salt
        first_page_data = f.read(DEFAULT_PAGESIZE - 16)  # 从开头第16字节开始到DEFAULT_PAGESIZE整个第一页
    if not len(salt) == 16:
        print(f"{db_file} read failed ")
        return False
    if not len(first_page_data) == DEFAULT_PAGESIZE - 16:
        print(f"{db_file} read failed ")
        return False
    # print(f"{salt=}")
    # print(f"{first_page_data=}")
    key = hashlib.pbkdf2_hmac('sha1', password, salt, DEFAULT_ITER, KEY_SIZE)
    mac_salt = bytes([x ^ 58 for x in salt])
    mac_key = hashlib.pbkdf2_hmac('sha1', key, mac_salt, 2, KEY_SIZE)
    hash_mac = hmac.new(mac_key, digestmod='sha1')
    hash_mac.update(first_page_data[:-32])
    hash_mac.update(bytes(ctypes.c_int(1)))
    if hash_mac.digest() == first_page_data[-32:-12]:
        print(f'{db_file},valid password Success')
        return True
    else:
        print(f'{db_file},valid password Error')
        return False


def get_logger(log_file):
    # 定log输出格式，配置同时输出到标准输出与log文件，返回logger这个对象
    logger = logging.getLogger('mylogger')
    logger.setLevel(logging.DEBUG)
    log_format = logging.Formatter(
        '%(asctime)s - %(filename)s- %(levelname)s - %(message)s')
    log_fh = logging.FileHandler(log_file)
    log_fh.setLevel(logging.DEBUG)
    log_fh.setFormatter(log_format)
    log_ch = logging.StreamHandler()
    log_ch.setLevel(logging.DEBUG)
    log_ch.setFormatter(log_format)
    logger.addHandler(log_fh)
    logger.addHandler(log_ch)
    return logger


if __name__ == '__main__':
    pass
