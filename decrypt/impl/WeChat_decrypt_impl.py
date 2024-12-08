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
import binascii
import ctypes
import hashlib
import hmac
import os
import shutil
import struct
import tempfile
import time
import uuid
from pathlib import Path

import psutil
import pymem
from Crypto.Cipher import AES
from _ctypes import byref, sizeof, Structure
from win32con import PROCESS_ALL_ACCESS

from decrypt.interface import DecryptInterface
from utils.logger_utils import mylogger as logger


class WeChatDecryptImpl(DecryptInterface):
    # IV_SIZE = 16
    # HMAC_SHA1_SIZE = 20
    # cfg_file = os.path.basename(sys.argv[0]).split('.')[0] + '.ini'

    KEY_SIZE = 32
    DEFAULT_PAGESIZE = 4096
    DEFAULT_ITER = 64000

    # 第一步：找key
    def get_acc_str_key_by_pid(self, pid):
        print("正在获取key...")
        logger.info(f"pid: {pid}")
        logger.info("遍历微信内存，去暴力找key......")
        phone_types = [b'android\x00', b'iphone\x00']
        try:
            pm = pymem.Pymem()
            pm.open_process_from_id(pid)
            p = psutil.Process(pid)

            misc_dbs = [f.path for f in p.open_files() if f.path[-11:] == 'MicroMsg.db']
            if len(misc_dbs) < 1:
                logger.error("没有找到数据库文件Misc.db，请确认是否已登录")
                return False, "没有找到数据库文件Misc.db，请确认是否已登录"

            # 在wechat.exe打开文件列表里面，找到最后文件名是Misc.db的，用这个做db_file,做校验
            misc_db = misc_dbs[0]
            logger.info(f"misc_db:{misc_db}")

            min_entrypoint = min([m.EntryPoint for m in pm.list_modules() if
                                  m.EntryPoint is not None])  # 遍历wechat载入的所有模块（包括它自己），找到所有模块最小的入口地址
            min_base = min([m.lpBaseOfDll for m in pm.list_modules() if
                            m.lpBaseOfDll is not None])  # 遍历wechat载入的所有模块（包括它自己），找到所有模块最小的基址
            min_address = min(min_entrypoint, min_base)  # 找到wechat最低的内存地址段
            logger.info(f"min_entrypoint:{min_entrypoint}, min_base:{min_base}")

            phone_addr = None
            for phone_type in phone_types:
                # 只在 WeChatWin.dll 这个模块的内存地址段中去寻找电话类型的地址
                res = pm.pattern_scan_module(phone_type, "WeChatWin.dll",
                                             return_multiple=True)

                if res:
                    # print(f"匹配到的电话类型地址{res}")
                    phone_addr = res[-1]  # 地址选搜到的最后一个地址
                    break

            if not phone_addr:
                logger.error(f"没有找到电话类型{phone_types}之一的关键字")
                return False, f"没有找到电话类型{phone_types}之一的关键字"

            logger.info(f"phone_addr: {phone_addr:X}")
            # key_addr=pm.pattern_scan_all(hex_key)
            # 判断操作系统位数，只需执行一次
            if phone_addr <= 2 ** 32:  # 如果是32位
                is_32bit = True
                logger.info(f"使用32位寻址去找key")
            else:  # 如果是64位
                is_32bit = False
                logger.info(f"使用64位寻址去找key")

            i = phone_addr  # 从找到的电话类型地址，作为基址，在附近查找
            str_key = None
            logger.info(f"正在从电话类型基址的附近查找……")
            end_time = time.time() + 5
            k = 0
            while i > min_address:
                if time.time() > end_time:
                    logger.info(f"超时了")
                    break
                # j 的数列：-1,2,-3,4,-5...
                k = k + 1
                j = (k if k % 2 != 0 else -k)
                i += j
                # logger.info(i)
                if is_32bit:
                    key_addr_bytes = pm.read_bytes(i, 4)  # 32位寻址下，地址指针占4个字节，找到存key的地址指针
                    key_addr = struct.unpack('<I', key_addr_bytes)[0]
                else:
                    key_addr_bytes = pm.read_bytes(i, 8)  # 64位寻址下，地址指针占8个字节，找到存key的地址指针
                    key_addr = struct.unpack('<Q', key_addr_bytes)[0]
                # if not is_writable_region(pm.process_id, key_addr):  # 要是这个指针指向的区域不能写，那也跳过
                #     continue
                try:
                    key = pm.read_bytes(key_addr, 32)
                except Exception as e:
                    # logger.error(e)
                    continue
                # print("可写入", key)
                str_key = binascii.hexlify(key).decode()
                if check_sqlite_pass(misc_db, str_key):
                    # 到这里就是找到了……
                    logger.info(f"pointer={i:X}, key_addr={key_addr:X}, key={key}")
                    logger.info(f"str_key:{str_key}")
                    logger.info(f"查找用时：{time.time() + 5 - end_time:.4f}秒，地址差为{i - phone_addr:X}")
                    return True, str_key
                else:
                    logger.warning(
                        f"Error key: diff={i - phone_addr:X}, pointer={i:X}, key_addr={key_addr:X}, key={key}")
                    str_key = None

            if not str_key:
                logger.error("超时，没有找到main_key")
                return False, "超时，没有找到main_key"
        except Exception as e:
            logger.error(e)
            return False, e

    # 第二步：拷贝数据库
    def copy_origin_db_to_proj(self, pid, account):
        print("查找所需数据库文件...")
        pm = pymem.Pymem()
        pm.open_process_from_id(pid)
        p = psutil.Process(pid)
        db_to_copy = [f.path for f in p.open_files() if f.path[-11:] == 'MicroMsg.db']
        logger.info(f"找到MicroMsg：{db_to_copy}")
        if len(db_to_copy) < 1:
            return False, "没有找到db文件！"
        # 将数据库文件拷贝到项目
        # user_dir = Config.PROJ_USER_PATH
        temp_dir = tempfile.gettempdir()
        origin_db_path = os.path.join(tempfile.mkdtemp(dir=temp_dir), f"{uuid.uuid4().hex}.db")
        if not os.path.exists(os.path.dirname(origin_db_path)):
            os.makedirs(os.path.dirname(origin_db_path))
        try:
            shutil.copyfile(db_to_copy[0], origin_db_path)
        except Exception as e:
            logger.error(e)
            return False, e

        return True, origin_db_path

    # 第三步：解密
    def decrypt_db_file_by_str_key(self, pid, mm_db_path, str_key):
        print(f"正在对数据库解密...")
        logger.info("正在对数据库解密......")
        sqlite_file_header = bytes("SQLite format 3", encoding='ASCII') + bytes(1)  # 文件头
        main_key = bytes.fromhex(str_key)

        with open(mm_db_path, 'rb') as f:
            blist = f.read()
        logger.info(f"数据库文件长度：{len(blist)}")

        salt = blist[:16]  # 微信将文件头换成了盐
        decrypt_key = hashlib.pbkdf2_hmac('sha1', main_key, salt, DEFAULT_ITER, KEY_SIZE)  # 获得Key
        logger.info(f"计算解密密钥：main_key={main_key}, salt={salt}, decrypt_key={decrypt_key}")

        hmac_salt = bytes([x ^ 0x3a for x in salt])
        hmac_key = hashlib.pbkdf2_hmac('sha1', decrypt_key, hmac_salt, 2, KEY_SIZE)
        logger.info(f"计算验证密钥：decrypt_key={decrypt_key}, hmac_salt={hmac_salt}, hmac_key={hmac_key}")

        hash_mac = hmac.new(hmac_key, digestmod='sha1')  # 用第一页的Hash测试一下
        first = blist[16:DEFAULT_PAGESIZE]  # 丢掉salt
        hash_mac.update(first[:-32])
        for update_func in [
            lambda: hash_mac.update(struct.pack('=I', 1)),
            lambda: hash_mac.update(bytes(ctypes.c_int(1))),  # type: ignore
        ]:
            hash_mac_copy = hash_mac.copy()  # 先复制 hash_mac，避免每次循环修改原 hash_mac
            update_func()  # 执行 update 操作
            if hash_mac_copy.digest() == first[-32:-12]:
                logger.info(f'验证密钥比对成功: {hmac_key}')
                break
        else:
            logger.error(f'验证密钥比对失败: {hmac_key}')
            return False, RuntimeError(f'验证密钥比对失败: {hmac_key}')

        print("解密成功，数据库写入解密后的内容...")
        new_blist = [blist[i:i + DEFAULT_PAGESIZE] for i in range(DEFAULT_PAGESIZE, len(blist), DEFAULT_PAGESIZE)]

        decrypted_mm_db_path = None

        if os.path.exists(mm_db_path):
            logger.info(f"数据库源：{mm_db_path}")
            if os.path.isdir(mm_db_path):
                pass
            elif os.path.isfile(mm_db_path):
                index = mm_db_path.rfind("\\")
                origin = mm_db_path[index + 1:]
                decrypted_mm_db_path = mm_db_path.replace(origin, "edit_" + origin)
        else:
            logger.error(mm_db_path, "不存在")
            return False, FileNotFoundError('db文件已经不存在！')

        with open(decrypted_mm_db_path, 'wb') as f:
            f.write(sqlite_file_header)  # 写入文件头
            t = AES.new(decrypt_key, AES.MODE_CBC, first[-48:-32])
            f.write(t.decrypt(first[:-48]))
            f.write(first[-48:])
            for i in new_blist:
                t = AES.new(decrypt_key, AES.MODE_CBC, i[-48:-32])
                f.write(t.decrypt(i[:-48]))
                f.write(i[-48:])

        logger.info(f"解密成功，已写入{decrypted_mm_db_path}")
        os.remove(mm_db_path)
        return True, decrypted_mm_db_path

    def get_acc_id_and_alias_from_db(self, cursor, acc):
        sql = f"SELECT UserName, Alias FROM 'Contact' WHERE UserName = '{acc}';"
        print(f"执行：{sql}")
        try:
            cursor.execute(sql)
            results = cursor.fetchall()
            return True, results
        except Exception as e:
            logger.error(e)
            return False, e

    def get_acc_nickname_from_db(self, cursor, acc):
        sql = f"SELECT UserName, NickName FROM 'Contact' WHERE UserName = '{acc}';"
        print(f"执行：{sql}")
        try:
            cursor.execute(sql)
            results = cursor.fetchall()
            return True, results
        except Exception as e:
            logger.error(e)
            return False, e

    def get_acc_avatar_from_db(self, cursor, acc):
        sql = f"SELECT UsrName, bigHeadImgUrl FROM 'ContactHeadImgUrl' WHERE UsrName = '{acc}';"
        print(f"执行：{sql}")
        try:
            cursor.execute(sql)
            results = cursor.fetchall()
            return True, results
        except Exception as e:
            logger.error(e)
            return False, e


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
def check_sqlite_pass(db_file, str_key):
    db_file = Path(db_file)
    key = bytes.fromhex(str_key.replace(' ', ''))
    with open(db_file, 'rb') as (f):
        salt = f.read(16)  # 开头的16字节做salt
        first_page_data = f.read(DEFAULT_PAGESIZE - 16)  # 从开头第16字节开始到DEFAULT_PAGESIZE整个第一页
    if not len(salt) == 16:
        logger.error(f"{db_file} read failed ")
        return False
    if not len(first_page_data) == DEFAULT_PAGESIZE - 16:
        logger.error(f"{db_file} read failed ")
        return False

    decrypt_key = hashlib.pbkdf2_hmac('sha1', key, salt, DEFAULT_ITER, KEY_SIZE)
    mac_salt = bytes([x ^ 0x3a for x in salt])
    mac_key = hashlib.pbkdf2_hmac('sha1', decrypt_key, mac_salt, 2, KEY_SIZE)
    hash_mac = hmac.new(mac_key, digestmod='sha1')
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
