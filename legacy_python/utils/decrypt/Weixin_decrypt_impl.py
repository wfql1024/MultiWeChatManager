# -*- coding: utf-8 -*-#
# -------------------------------------------------------------------------------
# 微信数据库采用的加密算法是256位的AES-CBC。数据库的默认的页大小是4096字节即4KB，其中每一个页都是被单独加解密的。
# IV：加密文件的每一个页都有一个随机的初始化向量，它被保存在每一页的末尾。
# HMAC：加密文件的每一页都存有着消息认证码，算法使用的是HMAC-SHA1（安卓数据库使用的是SHA512）。它也被保存在每一页的末尾。
# 盐值：每一个数据库文件的开头16字节都保存了一段唯一且随机的盐值，作为HMAC的验证和数据的解密。
# 用来计算HMAC的key与解密的key是不同的：
#   decrypt_key：解密用的密钥是主密钥str_key和之前提到的16字节的盐值通过PKCS5_PBKF2_HMAC1密钥扩展算法迭代64000次计算得到的。
#   hmac_key：而计算HMAC的密钥是刚提到的解密密钥和16字节"盐值异或0x3a的值"通过PKCS5_PBKF2_HMAC1密钥扩展算法迭代2次计算得到的。
# 为了保证数据部分长度是16字节即AES块大小的整倍数，每一页的末尾将填充一段空字节，使得保留字段的长度为48字节。
# 综上：
#   加密文件结构为第一页4KB数据前16字节为盐值，紧接着4032字节数据，再加上16字节IV和20字节HMAC以及12字节空字节；
#   而后的页均是4048字节长度的加密数据段和48字节的保留段。解密的key配合每一页的16字节IV即可解密加密数据段。
#
# 基本步骤：
# - 拿到主密钥str_key
# - 拿到第一页的16字节盐salt
# - 计算解密密钥decrypt_key：PKCS5_PBKF2_HMAC1(str_key + salt) -> decrypt_key
# - 验证解密密钥：
#   - salt的每一个字节和0x3a异或计算认证盐hmac_salt：x ^ 0x3a for x in salt
#   - 计算认证密钥hmac_key：PKCS5_PBKF2_HMAC1(decrypt_key + hmac_salt) -> hmac_key
#   - 认证是否解密成功Correct：SHA1(hmac_key) :: HMAC
# - 若验证成功，解密每一页：
#   - 拿到每一页的IV
#   - AES(decrypt_key + IV).decrypt(加密数据encrypted_data) -> 解密数据decrypted_data
#
# 图示：
#                                                                ┌————————————————————┐
#   ┌-------┐         str_key                   ┌————————————————————encrypted_data   |
#   | 第一页 |            ↓                      ↓                |                 每 |
#   | salt——|————>  decrypt_key   ————>   decrypted_data  <——————|———————  IV      一 |
#   └---↓---┘            ↓                      ↑                |                 页 |
#   hmac_salt  ————>  hmac_key    ————>      Correct √    <——————|——————  HMAC        |
#                                                                └————————————————————*
# -------------------------------------------------------------------------------

import ctypes
import hashlib
import hmac
import os
import re
import struct
import subprocess
from pathlib import Path

from _ctypes import byref, sizeof, Structure
from win32con import PROCESS_ALL_ACCESS

from legacy_python.public.config import Config
from legacy_python.utils.decrypt.interface import DecryptInterface
from legacy_python.utils.logger_utils import mylogger as logger

KEY_SIZE = 32
DEFAULT_PAGESIZE = 4096
DEFAULT_ITER = 64000
# 几种内存段可以写入的类型
MEMORY_WRITE_PROTECTIONS = {0x40: "PAGEEXECUTE_READWRITE", 0x80: "PAGE_EXECUTE_WRITECOPY", 0x04: "PAGE_READWRITE",
                            0x08: "PAGE_WRITECOPY"}


class MemoryBasicInformation(Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_uint32),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_uint32),
        ("Protect", ctypes.c_uint32),
        ("Type", ctypes.c_uint32),
    ]


# 第一步：找key -> 1. 判断可写
def is_writable_region(pid, address):  # 判断给定的内存地址是否是可写内存区域，因为可写内存区域，才能指针指到这里写数据
    process_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    mbi = MemoryBasicInformation()
    mbi_pointer = byref(mbi)
    size = sizeof(mbi)
    success = ctypes.windll.kernel32.VirtualQueryEx(
        process_handle,
        ctypes.c_void_p(address),  # 64位系统的话，会提示int超范围，这里把指针转换下
        mbi_pointer,
        size)
    ctypes.windll.kernel32.CloseHandle(process_handle)
    if not success:
        return False
    if not success == size:
        return False
    return mbi.Protect in MEMORY_WRITE_PROTECTIONS


# 第一步：找key -> 2. 检验是否正确
def check_sqlite_pass(db_file, password):
    db_file = Path(db_file)
    if type(password) is str:  # 要是类型是string的，就转bytes
        password = bytes.fromhex(password.replace(' ', ''))
    with open(db_file, 'rb') as (f):
        salt = f.read(16)  # 开头的16字节做salt
        first_page_data = f.read(DEFAULT_PAGESIZE - 16)  # 从开头第16字节开始到DEFAULT_PAGESIZE整个第一页
    if not len(salt) == 16:
        logger.error(f"{db_file} read failed ")
        return False
    if not len(first_page_data) == DEFAULT_PAGESIZE - 16:
        logger.error(f"{db_file} read failed ")
        return False

    print(db_file, password)
    key = hashlib.pbkdf2_hmac('sha512', password, salt, DEFAULT_ITER, KEY_SIZE)
    mac_salt = bytes([x ^ 0x3a for x in salt])
    mac_key = hashlib.pbkdf2_hmac('sha512', key, mac_salt, 2, KEY_SIZE)
    hash_mac = hmac.new(mac_key, digestmod='sha512')
    hash_mac.update(first_page_data[:-32])
    for update_func in [
        lambda: hash_mac.update(struct.pack('=I', 1)),
        lambda: hash_mac.update(bytes(ctypes.c_int(1))),  # type: ignore
    ]:
        hash_mac_copy = hash_mac.copy()  # 复制 hash_mac，避免每次循环修改原 hash_mac
        update_func()  # 执行 update 操作

        if hash_mac_copy.digest() == first_page_data[-32:-12]:
            return True  # 匹配成功，返回 True
    return False  # 所有尝试失败，返回 False


class WeixinDecryptImpl(DecryptInterface):
    # IV_SIZE = 16
    # HMAC_SHA1_SIZE = 20
    # cfg_file = os.path.basename(sys.argv[0]).split('.')[0] + '.ini'

    KEY_SIZE = 32
    DEFAULT_PAGESIZE = 4096
    DEFAULT_ITER = 64000

    # 第一步：找key
    def get_acc_str_key_by_pid(self, pid):
        print("正在获取key...")
        str_key = 'this is a hypothetical key'

        return True, str_key

    # 第二步：拷贝数据库
    def copy_origin_db_to_proj(self, pid, account):
        print("查找所需数据库文件...")
        # pm = pymem.Pymem()
        # pm.open_process_from_id(pid)
        # p = psutil.Process(pid)
        # target_dbs = [f.path for f in p.open_files() if f.path[-10:] == 'contact.db']
        # logger.info(f"找到数据库文件：{target_dbs}")
        # if len(target_dbs) < 1:
        #     return False, "没有找到db文件！"
        # 将数据库文件拷贝到项目
        usr_dir = Config.PROJ_USER_PATH
        origin_db_path = usr_dir + rf"\Weixin\{account}\contact.db"
        # if not os.path.exists(os.path.dirname(origin_db_path)):
        #     os.makedirs(os.path.dirname(origin_db_path))
        # try:
        #     shutil.copyfile(target_dbs[0], origin_db_path)
        # except Exception as e:
        #     logger.error(e)
        #     return False, e

        return True, origin_db_path

    # 第三步：解密
    def decrypt_db_file_by_str_key(self, pid, origin_db_path, str_key):
        print(f"正在对数据库解密...")
        logger.info("正在对数据库解密......")
        dump_exe = Config.WECHAT_DUMP_EXE_PATH
        info = subprocess.check_output([dump_exe, '-p', f"{pid}", '-a']).decode()
        key_pattern = r"output to\s+(.+)"
        match = re.search(key_pattern, info)
        decrypted_db_path = None
        if match:
            output = match.group(1)
            decrypted_db_path = os.path.join(output, "contact", "contact.db")
            print(f"output to: {decrypted_db_path}")
        else:
            print("Failed.")
        return True, decrypted_db_path

    def get_acc_id_and_alias_from_db(self, cursor, acc):
        acc_id = acc[:-5]
        sql = f"SELECT username, alias FROM 'contact' WHERE username = '{acc_id}';"
        print(f"执行：{sql}")
        try:
            cursor.execute(sql)
            results = cursor.fetchall()
            return True, results
        except Exception as e:
            logger.error(e)
            return False, e

    def get_acc_nickname_from_db(self, cursor, acc):
        acc_id = acc[:-5]
        sql = f"SELECT username, nick_name FROM 'contact' WHERE username = '{acc_id}';"
        print(f"执行：{sql}")
        try:
            cursor.execute(sql)
            results = cursor.fetchall()
            return True, results
        except Exception as e:
            logger.error(e)
            return False, e

    def get_acc_avatar_from_db(self, cursor, acc):
        acc_id = acc[:-5]
        sql = f"SELECT username, big_head_url FROM 'contact' WHERE username = '{acc_id}';"
        print(f"执行：{sql}")
        try:
            cursor.execute(sql)
            results = cursor.fetchall()
            return True, results
        except Exception as e:
            logger.error(e)
            return False, e
